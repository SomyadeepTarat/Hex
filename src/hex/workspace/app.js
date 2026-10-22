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
  if(!r)return;
  $('recommendation').innerHTML = `<p class="big">${esc(r.recommendation.strategy_id.replaceAll('_',' '))}</p><p>${r.detection.alert?'Respiratory surge detected':'No respiratory surge detected'} · ${r.scenarios.count} futures · ${r.scenarios.horizon_days} days</p><p class="helper">Best among the evaluated feasible plans. ${esc(r.recommendation.explanation)}</p>`;
  $('strategies').innerHTML = `<table><thead><tr><th>Plan</th><th>Worst unmet bed-days</th><th>Cost units</th></tr></thead><tbody>${r.strategies.map(s=>`<tr><td>${esc(s.strategy_id.replaceAll('_',' '))}</td><td>${s.worst_case_unmet_bed_days.toFixed(1)}</td><td>${s.intervention_cost}</td></tr>`).join('')}</tbody></table><p class="helper">A bed-day measures one person waiting for a bed for one day. Waiting demand carries forward.</p><p>Proposed extra beds: ${esc(Object.entries(r.strategies.find(s=>s.strategy_id==='flex_capacity').additional_staffed_beds).map(([id,n])=>`${id}: ${n}`).join(' · '))}</p>`;
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
    $('network').innerHTML=hospitals.map(h=>`<div class="hospital-line"><b>${esc(h.name)}</b> · ${h.staffed_general_beds-h.occupied_general_beds} reported beds free<small>${h.accepting_patients?'Accepting patients':'Not accepting patients'} · reported ${esc(new Date(h.reported_at).toLocaleString())}</small></div>`).join('');
    if(initial){$('hospital-select').innerHTML=hospitals.filter(h=>user.role==='government'||h.hospital_id===user.hospital_id).map(h=>`<option value="${esc(h.hospital_id)}">${esc(h.name)}</option>`).join('');fillSelected();fill('settings-form', state.settings);}
    renderPlan();
    $('audit').innerHTML=audit.events.slice(0,10).map(e=>`<div class="hospital-line">${esc(e.operation.replaceAll('_',' '))} · ${esc(e.target)}<small>${esc(new Date(e.created_at).toLocaleString())}</small></div>`).join('') || '<p>No changes yet.</p>';
  }catch(e){notice(e.message);}finally{polling=false;}
}
async function enter(){user=await api('/auth/me');$('login').hidden=true;$('workspace').hidden=false;$('identity').textContent=`${user.username} · ${user.role==='government'?'Network administrator':user.hospital_id}`;$('admin').hidden=user.role!=='government';await refresh(true);}
$('login-form').onsubmit=async e=>{e.preventDefault();const username=new FormData(e.target).get('username');try{const result=await api('/auth/login','POST',{username,password:username==='coordinator'?'demo-government':'demo-hospital'});token=result.token;sessionStorage.setItem('hexToken',token);await enter();}catch(err){alert(err.message);}};
$('logout').onclick=async()=>{try{await api('/auth/logout','POST');}finally{token=null;user=null;sessionStorage.removeItem('hexToken');$('workspace').hidden=true;$('login').hidden=false;}};
$('hospital-select').onchange=fillSelected;
$('status-form').onsubmit=async e=>{e.preventDefault();try{const data=values(e.target);data.accepting_patients=e.target.elements.accepting_patients.checked;await api(`/hospitals/${selected}/status`,'PUT',data);notice('Status published. Patient suggestions refresh within five seconds; preparedness is recomputing.');await refresh();}catch(err){notice(err.message);}};
$('constraints-form').onsubmit=async e=>{e.preventDefault();try{await api(`/hospitals/${selected}/constraints`,'PUT',values(e.target));notice('Planning limits saved. Recomputing; reported public beds are unchanged.');await refresh();}catch(err){notice(err.message);}};
$('settings-form').onsubmit=async e=>{e.preventDefault();try{await api('/planning/settings','PUT',values(e.target));notice('Network settings saved.');await refresh();}catch(err){notice(err.message);}};
$('rerun').onclick=async()=>{try{await api('/planning/run','POST');await refresh();}catch(err){notice(err.message);}};
$('chat-form').onsubmit=async e=>{e.preventDefault();try{const p=await api('/chat/proposals','POST',{message:new FormData(e.target).get('message')});proposalId=p.proposal_id;$('proposal').innerHTML=p.action==='propose_change'?`<div class="proposal"><b>${esc(p.target)} · ${esc(p.field.replaceAll('_',' '))}</b><p>${esc(p.old_value)} → ${esc(p.new_value)}</p><p>Preview only. No change has been saved.</p><button id="apply">Apply change & recompute</button></div>`:`<p>${esc(p.explanation)}</p>${p.current_constraints?`<pre>${esc(JSON.stringify(p.current_constraints,null,2))}</pre>`:''}`;if($('apply'))$('apply').onclick=async()=>{try{await api(`/chat/proposals/${proposalId}/apply`,'POST');$('proposal').textContent='Applied. Updated plan is being computed.';await refresh(true);}catch(err){$('proposal').textContent=err.message;}};}catch(err){notice(err.message);}};
for(const mode of ['normal','surge'])$(mode).onclick=async()=>{try{await api(`/demo/feed/${mode}`,'POST');notice(`Loaded the ${mode} synthetic hospital case feed. Public symptom searches remain separate.`);await refresh();}catch(err){notice(err.message);}};
if(token)enter().catch(()=>{sessionStorage.removeItem('hexToken');token=null;});
setInterval(()=>refresh(),5000);
