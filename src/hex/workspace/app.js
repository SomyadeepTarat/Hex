const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label = s => String(s).replaceAll('_',' ');
let user, hospitals=[], state, selected, proposalId, refreshTask=null;
let token=sessionStorage.getItem('hexToken');
async function api(path,method='GET',body){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),20000);
  try{
    const response=await fetch(`/api${path}`,{method,signal:controller.signal,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},...(body?{body:JSON.stringify(body)}:{})});
    let data;try{data=await response.json();}catch{throw new Error('Server returned an unexpected response. Restart the unified server and reload this page.');}
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(x=>`${x.loc.at(-1)}: ${x.msg}`).join('; '):'Request failed. Please try again.');
    return data;
  }finally{clearTimeout(timer);}
}
function feedback(id,message,error=false){const target=$(id);target.textContent=message;target.classList.toggle('error',error);}
const notice=s=>{$('notice').textContent=s;};
function numericValues(form){
  const data={};for(const [key,value] of new FormData(form)){if(value==='')throw new Error('Fill in all required values.');const number=Number(value);if(!Number.isInteger(number))throw new Error('Use whole numbers for planning values.');data[key]=number;}return data;
}
function fill(formId,data){for(const [key,value] of Object.entries(data||{})){const field=$(formId).elements.namedItem(key);if(field&&field.tagName){if(field.type==='checkbox')field.checked=!!value;else field.value=value;}}}
function fillSelected(){
  selected=$('hospital-select').value;
  const h=hospitals.find(h=>h.hospital_id===selected);
  fill('status-form',h);fill('constraints-form',state?.constraints.find(c=>c.hospital_id===selected));
  fill('capabilities-form',h?.resources);
  for(const checkbox of document.querySelectorAll('#specialty-options input'))checkbox.checked=(h?.specialties||[]).includes(checkbox.value);
  $('chat-example').textContent=`Try: Set ${selected} maximum additional staffed beds to 12.`;
}
function renderPlan(){
  const r=state.result;
  $('plan-state').textContent=state.error?`Planning failed: ${state.error}. Current hospital availability remains accessible.`:state.updating?'Updating recommendations… Your saved changes are queued.':state.outdated?'Previous result is outdated. Recompute to refresh.':'Plan is current';
  $('plan-inputs').textContent=`Saved network inputs: budget ${state.settings.budget_units} units · ${state.settings.scenario_count} futures · ${state.settings.horizon_days} days. Input versions ${state.status_version}/${state.constraints_version}.`;
  if(!r)return;
  const best=r.strategies[0],baseline=r.strategies.find(s=>s.strategy_id==='baseline'),flex=r.strategies.find(s=>s.strategy_id==='flex_capacity');
  let why=baseline.worst_case_unmet_bed_days<1e-9?'The evaluated futures do not exceed staffed capacity over this horizon, so spending on an intervention does not reduce unmet demand.':best.strategy_id==='baseline'?'No evaluated feasible intervention improves the result under the current limits and budget. Raising a limit alone does not guarantee an improved plan.':`This plan reduces worst-case unmet bed-days from ${baseline.worst_case_unmet_bed_days.toFixed(1)} to ${best.worst_case_unmet_bed_days.toFixed(1)} within the saved budget.`;
  $('recommendation').innerHTML=`${state.outdated?'<p class="helper">Showing the previous plan until the newly saved inputs finish computing.</p>':''}<p class="big">${esc(label(best.strategy_id))}</p><p>${r.detection.alert?'Respiratory surge detected':'No respiratory surge detected'} · ${r.scenarios.count} evaluated futures · ${r.scenarios.horizon_days} days</p><p>${esc(why)}</p><p class="helper">Best among evaluated feasible plans. Generated ${esc(new Date(r.generated_at).toLocaleTimeString())} from versions ${r.status_version}/${r.constraints_version}.</p>`;
  $('strategies').innerHTML=`<table><thead><tr><th>Plan</th><th>Worst unmet bed-days</th><th>Cost units</th></tr></thead><tbody>${r.strategies.map(s=>`<tr><td>${esc(label(s.strategy_id))}</td><td>${s.worst_case_unmet_bed_days.toFixed(1)}</td><td>${s.intervention_cost}</td></tr>`).join('')}</tbody></table><p class="helper">A bed-day measures one person waiting for a bed for one day. Waiting demand carries forward.</p><p>Proposed extra beds: ${esc(Object.entries(flex?.additional_staffed_beds||{}).map(([id,n])=>`${id}: ${n}`).join(' · '))}</p>`;
  const m=r.ml;
  if(m?.available){const e=m.evaluation,t=e.temporal_test,u=e.unseen_city_test;$('ml').innerHTML=`<p>${esc(m.model)} trained on ${e.training_rows.toLocaleString()} of ${e.dataset_rows.toLocaleString()} synthetic hospital-days.</p><div class="metric-grid"><div class="metric"><b>${t.mae.toFixed(2)}</b><small>Held-out MAE · admissions/day</small></div><div class="metric"><b>${t.persistence_mae.toFixed(2)}</b><small>Persistence baseline MAE</small></div><div class="metric"><b>${u.mae.toFixed(2)}</b><small>Unseen-city MAE</small></div></div><p>Next-day forecast: ${esc(Object.entries(m.next_day_admissions).map(([id,n])=>`${id}: ${n.toFixed(1)}`).join(' · '))}</p><p class="helper">${esc(e.split)}</p>`;}else $('ml').textContent='Admission model is unavailable. Run the training command.';
}
async function refresh(initial=false){
  if(!user)return;
  if(refreshTask){await refreshTask;if(initial)initializeForms();return;}
  refreshTask=(async()=>{
    const [network,next,audit]=await Promise.all([api('/public/hospitals'),api('/planning/state'),api('/audit')]);hospitals=network.hospitals;state=next;
    $('network').innerHTML=hospitals.map(h=>`<div class="hospital-line"><b>${esc(h.name)}</b> · ${h.staffed_general_beds-h.occupied_general_beds} reported beds free<small>${h.accepting_patients?'Accepting patients':'Not accepting patients'} · reported ${esc(new Date(h.reported_at).toLocaleString())}</small></div>`).join('');
    renderPlan();$('audit').innerHTML=audit.events.slice(0,10).map(e=>`<div class="hospital-line">${esc(label(e.operation))} · ${esc(e.target)}<small>${esc(new Date(e.created_at).toLocaleString())}</small></div>`).join('')||'<p>No changes yet.</p>';
  })();
  try{await refreshTask;if(initial)initializeForms();}finally{refreshTask=null;}
}
function initializeForms(){const previous=selected;$('hospital-select').innerHTML=hospitals.filter(h=>user.role==='government'||h.hospital_id===user.hospital_id).map(h=>`<option value="${esc(h.hospital_id)}">${esc(h.name)}</option>`).join('');if(hospitals.some(h=>h.hospital_id===previous)&&(user.role==='government'||previous===user.hospital_id))$('hospital-select').value=previous;fillSelected();fill('settings-form',state.settings);}
async function enter(){user=await api('/auth/me');$('login').hidden=true;$('workspace').hidden=false;$('identity').textContent=`${user.username} · ${user.role==='government'?'Network administrator':user.hospital_id}`;$('admin').hidden=user.role!=='government';await refresh(true);}
function bindForm(id,feedbackId,action){$(id).onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,button=form.querySelector('button[type=submit],button:not([type])');if(!user||!selected){feedback(feedbackId,'Sign in and select a hospital first.',true);return;}button.disabled=true;feedback(feedbackId,'Saving…');try{await action(form);await refresh(true);}catch(e){feedback(feedbackId,e.name==='AbortError'?'The request timed out. Reload current values before retrying.':e.message,true);}finally{button.disabled=false;}};}
$('login-form').onsubmit=async e=>{e.preventDefault();const username=new FormData(e.target).get('username');try{const r=await api('/auth/login','POST',{username,password:username==='coordinator'?'demo-government':'demo-hospital'});token=r.token;sessionStorage.setItem('hexToken',token);selected=null;await enter();}catch(err){alert(err.message);}};
$('logout').onclick=async()=>{try{await api('/auth/logout','POST');}finally{token=null;user=null;sessionStorage.removeItem('hexToken');$('workspace').hidden=true;$('login').hidden=false;}};
$('hospital-select').onchange=()=>{fillSelected();$('proposal').textContent='';proposalId=null;for(const id of ['constraints-feedback','chat-feedback','capabilities-feedback'])feedback(id,'');};
bindForm('status-form','status-feedback',async form=>{const data={staffed_general_beds:Number(form.elements.staffed_general_beds.value),occupied_general_beds:Number(form.elements.occupied_general_beds.value),accepting_patients:form.elements.accepting_patients.checked};await api(`/hospitals/${selected}/status`,'PUT',data);feedback('status-feedback','Status published. Patient suggestions refresh within five seconds.');});
bindForm('capabilities-form','capabilities-feedback',async form=>{const data={specialties:[...form.querySelectorAll('input[name=specialties]:checked')].map(x=>x.value)};for(const key of ['oxygen_stations','xray_slots','pediatric_beds'])data[key]=Number(form.elements[key].value);await api(`/hospitals/${selected}/capabilities`,'PUT',data);feedback('capabilities-feedback','Expertise and resource report published. Care matching will use this report.');});
bindForm('constraints-form','constraints-feedback',async form=>{const data=numericValues(form);await api(`/hospitals/${selected}/constraints`,'PUT',data);feedback('constraints-feedback',`Saved for ${selected}: at most ${data.max_additional_staffed_beds} extra staffed beds and ${data.transfer_out_limit_per_day} transfers/day. Recomputing. These are limits; the recommendation can remain unchanged when there is no benefit or insufficient budget.`);});
bindForm('settings-form','settings-feedback',async form=>{const data=numericValues(form);await api('/planning/settings','PUT',data);feedback('settings-feedback',`Saved: ${data.budget_units} budget units, ${data.scenario_count} futures, ${data.horizon_days} days. A fresh plan is queued.`);});
$('rerun').onclick=async()=>{try{await api('/planning/run','POST');notice('Recomputation queued.');await refresh();}catch(e){notice(e.message);}};
$('chat-form').onsubmit=async e=>{e.preventDefault();const button=e.currentTarget.querySelector('button');button.disabled=true;feedback('chat-feedback','Interpreting your planning request…');$('proposal').textContent='';try{const p=await api('/chat/proposals','POST',{message:new FormData(e.currentTarget).get('message'),hospital_id:selected});proposalId=p.proposal_id;feedback('chat-feedback',p.action==='propose_change'?'Preview ready. Review and Apply to save.':p.explanation,p.action==='unsupported'||p.action==='clarify');if(p.action==='propose_change'){$('proposal').innerHTML=`<div class="proposal"><b>${esc(p.target)} · ${esc(label(p.field))}</b><p>${esc(p.old_value)} → ${esc(p.new_value)}</p><p>No change has been saved yet.</p><button id="apply">Apply change & recompute</button></div>`;$('apply').onclick=async()=>{const applyButton=$('apply');applyButton.disabled=true;try{await api(`/chat/proposals/${proposalId}/apply`,'POST');$('proposal').textContent=`Applied ${label(p.field)}: ${p.new_value}. Preparedness is recomputing; operational beds are unchanged.`;feedback('chat-feedback','Change saved and audited.');await refresh(true);}catch(err){feedback('chat-feedback',err.message,true);applyButton.disabled=false;}};}else if(p.current_constraints)$('proposal').textContent=JSON.stringify(p.current_constraints,null,2);}catch(err){feedback('chat-feedback',err.message,true);}finally{button.disabled=false;}};
for(const mode of ['normal','surge'])$(mode).onclick=async()=>{try{await api(`/demo/feed/${mode}`,'POST');feedback('settings-feedback',`Loaded ${mode} synthetic feed. Recomputing; public symptom searches remain separate.`);await refresh();}catch(e){feedback('settings-feedback',e.message,true);}};
if(token)enter().catch(e=>{notice(e.message);sessionStorage.removeItem('hexToken');token=null;$('workspace').hidden=true;$('login').hidden=false;});
setInterval(()=>refresh().catch(e=>notice(e.message)),5000);

$('refresh-reports').onclick=async()=>{const button=$('refresh-reports');button.disabled=true;try{const r=await api('/demo/refresh-reports','POST');feedback('settings-feedback',r.message);await refresh();}catch(e){feedback('settings-feedback',e.message,true);}finally{button.disabled=false;}};
