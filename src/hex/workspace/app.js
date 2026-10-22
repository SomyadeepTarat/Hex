const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let user, hospitals = [], state, selected, proposalId, polling = false;
let token = sessionStorage.getItem('hexToken');
async function api(path, method='GET', body) {
  const response = await fetch(`/api${path}`, {method, headers:{'Content-Type':'application/json', ...(token ? {Authorization:`Bearer ${token}`} : {})}, ...(body ? {body:JSON.stringify(body)} : {})});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the entered values and try again.');
  return data;
}
const notice = s => { $('notice').textContent = s; };
const values = form => Object.fromEntries([...new FormData(form)].map(([k,v])=>[k, Number(v)]));
function fill(formId, data) {
  for (const [key,value] of Object.entries(data || {})) {
    const field = $(formId).elements.namedItem(key);
    if (field) { if(field.type==='checkbox')field.checked=!!value;else field.value=value; }
  }
}
function fillSelected() {
  selected = $('hospital-select').value;
  fill('status-form', hospitals.find(h=>h.hospital_id===selected));
  fill('constraints-form', state?.constraints.find(c=>c.hospital_id===selected));
  $('chat-example').textContent = `Try: Set ${selected} maximum additional staffed beds to 12.`;
}
function renderPlan() {
  const r = state.result;
  $('plan-state').textContent = state.error ? `Planning failed: ${state.error}. Public availability remains accessible.` : state.updating ? 'Updating recommendations…' : state.outdated ? 'Previous result is outdated.' : 'Plan is current · automatically recomputed after updates';
  $('plan-state').classList.toggle('updating',!!(state.updating||state.outdated||state.error));
  if(!r){$('recommendation').innerHTML='<p class="helper">No completed result yet. The latest reported status remains available to the public.</p>';$('strategies').innerHTML='';$('ml').textContent='Awaiting a completed analysis.';return;}
  $('recommendation').innerHTML = `<div class="recommendation-summary"><div><small>RECOMMENDED AMONG EVALUATED PLANS</small><p class="recommendation-name">${esc(r.recommendation.strategy_id.replaceAll('_',' '))}</p></div><div class="scenario-counts"><div><b>${r.scenarios.count}</b>futures evaluated</div><div><b>${r.scenarios.horizon_days}</b>day horizon</div></div></div><p class="helper">${r.detection.alert?'Respiratory surge detected.':'No respiratory surge detected.'} ${esc(r.recommendation.explanation)}</p>`;
  const flex=r.strategies.find(s=>s.strategy_id==='flex_capacity');
  $('strategies').innerHTML = `<table class="strategy-table"><thead><tr><th>Evaluated plan</th><th>Worst unmet bed-days</th><th>Mean unmet bed-days</th><th>Cost units</th></tr></thead><tbody>${r.strategies.map(s=>`<tr class="${s.strategy_id===r.recommendation.strategy_id?'recommended':''}"><td>${esc(s.strategy_id.replaceAll('_',' '))}${s.strategy_id===r.recommendation.strategy_id?'<span class="recommended-tag">SELECTED</span>':''}</td><td>${s.worst_case_unmet_bed_days.toFixed(1)}</td><td>${s.mean_unmet_bed_days?.toFixed(1)??'—'}</td><td>${s.intervention_cost}</td></tr>`).join('')}</tbody></table><p class="helper">A bed-day measures one person waiting for a bed for one day. Waiting demand carries forward.</p>${flex?`<p class="allocation-line">Proposed extra beds: ${esc(Object.entries(flex.additional_staffed_beds||{}).map(([id,n])=>`${id}: ${n}`).join(' · '))}</p>`:''}`;
  const m=r.ml;
  if(m?.available){const e=m.evaluation,t=e.temporal_test,u=e.unseen_city_test;
    $('ml').innerHTML=`<p>${esc(m.model)} trained on ${e.training_rows.toLocaleString()} rows from a ${e.dataset_rows.toLocaleString()}-row synthetic dataset covering 12 cities, 36 hospitals and two years.</p><div class="metric-grid"><div class="metric"><b>${t.mae.toFixed(2)}</b><small>Held-out MAE · admissions/day</small></div><div class="metric"><b>${t.persistence_mae.toFixed(2)}</b><small>Persistence baseline MAE</small></div><div class="metric"><b>${u.mae.toFixed(2)}</b><small>Unseen-city MAE</small></div></div><p>Current next-day forecast: ${esc(Object.entries(m.next_day_admissions).map(([id,n])=>`${id}: ${n.toFixed(1)}`).join(' · '))}</p><p class="helper">${esc(e.split)}</p>`;
  }else $('ml').textContent='Model artifact unavailable. Run the training command.';
}
async function refresh(initial=false) {
  if(!user || polling)return;polling=true;
  try{
    const [network, next, audit] = await Promise.all([api('/public/hospitals'),api('/planning/state'),api('/audit')]);
    hospitals=network.hospitals;state=next;
    const ownHospital=hospitals.find(h=>h.hospital_id===user.hospital_id);
    $('identity').textContent=user.role==='government'?'City network · Administrator':`${ownHospital?.name||user.hospital_id} · Hospital operator`;
    const staffed=hospitals.reduce((sum,h)=>sum+(h.staffed_general_beds||0),0);
    const occupied=hospitals.reduce((sum,h)=>sum+(h.occupied_general_beds||0),0);
    $('kpi-staffed').textContent=staffed.toLocaleString();$('kpi-occupied').textContent=occupied.toLocaleString();$('kpi-available').textContent=Math.max(0,staffed-occupied).toLocaleString();
    $('kpi-scenarios').textContent=state.settings.scenario_count;$('kpi-horizon').textContent=`${state.settings.horizon_days}-day planning horizon`;
    $('network').innerHTML=`<table class="capacity-table"><thead><tr><th>HOSPITAL / LAST REPORT</th><th>OCCUPANCY</th><th>AVAILABLE</th><th>STATUS</th></tr></thead><tbody>${hospitals.map(h=>{
      const known=h.staffed_general_beds!=null&&h.occupied_general_beds!=null;
      const percent=h.staffed_general_beds?100*h.occupied_general_beds/h.staffed_general_beds:0;
      const age=h.reported_at?Date.now()-Date.parse(h.reported_at):NaN;
      const freshness=Number.isFinite(age)&&age>=0&&age<=900000?'Current':Number.isFinite(age)?'Stale':'Unknown';
      return `<tr><td><b>${esc(h.name)}</b><small>${freshness} · ${h.reported_at?esc(new Date(h.reported_at).toLocaleTimeString()):'No report'}</small></td><td>${known?`${h.occupied_general_beds} / ${h.staffed_general_beds}`:'Unknown'}<br><span class="occupancy-meter"><i style="width:${Math.min(100,percent)}%"></i></span></td><td>${known?Math.max(0,h.staffed_general_beds-h.occupied_general_beds):'—'}</td><td><span class="status-pill ${h.accepting_patients?'':'closed'}">${h.accepting_patients?'Accepting':'Not accepting'}</span></td></tr>`;
    }).join('')}</tbody></table>`;
    if(initial){$('hospital-select').innerHTML=hospitals.filter(h=>user.role==='government'||h.hospital_id===user.hospital_id).map(h=>`<option value="${esc(h.hospital_id)}">${esc(h.name)}</option>`).join('');fillSelected();fill('settings-form', state.settings);}
    renderPlan();
    $('audit').innerHTML=audit.events.slice(0,10).map(e=>`<div class="audit-entry"><div>${esc(e.operation.replaceAll('_',' '))} <span>· ${esc(e.target)} · ${esc(e.actor_id)}</span></div><small>${esc(new Date(e.created_at).toLocaleString())}</small></div>`).join('') || '<p>No saved changes yet.</p>';
    $('workspace-connection').textContent=`Connected · checked ${new Date().toLocaleTimeString()}`;$('workspace-connection').classList.remove('offline');
  }catch(e){notice(e.message);$('workspace-connection').textContent='Unable to refresh';$('workspace-connection').classList.add('offline');}finally{polling=false;}
}
async function enter(){user=await api('/auth/me');$('login').hidden=true;$('workspace').hidden=false;$('identity').textContent=`${user.username} · ${user.role==='government'?'Network administrator':user.hospital_id}`;$('admin').hidden=user.role!=='government';document.querySelector('h1').textContent=user.role==='government'?'Network operations':'Hospital operations';await refresh(true);}
$('login-form').onsubmit=async e=>{e.preventDefault();const username=new FormData(e.target).get('username');try{const result=await api('/auth/login','POST',{username,password:username==='coordinator'?'demo-government':'demo-hospital'});token=result.token;sessionStorage.setItem('hexToken',token);await enter();}catch(err){alert(err.message);}};
$('logout').onclick=async()=>{try{await api('/auth/logout','POST');}finally{token=null;user=null;sessionStorage.removeItem('hexToken');$('workspace').hidden=true;$('login').hidden=false;$('workspace-connection').textContent='Signed out';document.querySelector('h1').textContent='Operations overview';}};
$('hospital-select').onchange=fillSelected;
$('status-form').onsubmit=async e=>{e.preventDefault();try{const data=values(e.target);data.accepting_patients=e.target.elements.accepting_patients.checked;await api(`/hospitals/${selected}/status`,'PUT',data);notice('Status published. Patient suggestions refresh within five seconds; preparedness is recomputing.');await refresh();}catch(err){notice(err.message);}};
$('constraints-form').onsubmit=async e=>{e.preventDefault();try{await api(`/hospitals/${selected}/constraints`,'PUT',values(e.target));notice('Planning limits saved. Recomputing; reported public beds are unchanged.');await refresh();}catch(err){notice(err.message);}};
$('settings-form').onsubmit=async e=>{e.preventDefault();try{await api('/planning/settings','PUT',values(e.target));notice('Network settings saved.');await refresh();}catch(err){notice(err.message);}};
$('rerun').onclick=async()=>{try{await api('/planning/run','POST');await refresh();}catch(err){notice(err.message);}};
$('chat-form').onsubmit=async e=>{e.preventDefault();try{const p=await api('/chat/proposals','POST',{message:new FormData(e.target).get('message')});proposalId=p.proposal_id;$('proposal').innerHTML=p.action==='propose_change'?`<div class="proposal"><b>${esc(p.target)} · ${esc(p.field.replaceAll('_',' '))}</b><p>${esc(p.old_value)} → ${esc(p.new_value)}</p><p>Preview only. No change has been saved.</p><button id="apply">Apply change & recompute</button></div>`:`<p>${esc(p.explanation)}</p>${p.current_constraints?`<pre>${esc(JSON.stringify(p.current_constraints,null,2))}</pre>`:''}`;if($('apply'))$('apply').onclick=async()=>{try{await api(`/chat/proposals/${proposalId}/apply`,'POST');$('proposal').textContent='Applied. Updated plan is being computed.';await refresh(true);}catch(err){$('proposal').textContent=err.message;}};}catch(err){notice(err.message);}};
for(const mode of ['normal','surge'])$(mode).onclick=async()=>{try{await api(`/demo/feed/${mode}`,'POST');notice(`Loaded the ${mode} case feed. Preparedness is being recalculated.`);await refresh();}catch(err){notice(err.message);}};
if(token)enter().catch(()=>{sessionStorage.removeItem('hexToken');token=null;});
setInterval(()=>refresh(),5000);
document.querySelectorAll('.sidebar nav a').forEach(link=>link.addEventListener('click',()=>{document.querySelectorAll('.sidebar nav a').forEach(a=>a.classList.remove('active'));link.classList.add('active');}));
