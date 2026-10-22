const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label = value => value==='general_concern'?'a health concern for general assessment':String(value).replaceAll('_',' ');
let stage='symptoms',search=null,lastNeeds=null,signature='',zoneSignature='',sequence=0,busy=false,polling=false;
const greeting=$('conversation-log').innerHTML;
function message(text,role='assistant'){
  const entry=document.createElement('div');entry.className=`chat-message ${role}`;
  entry.innerHTML=`<span class="message-label">${role==='user'?'YOU':'HEX'}</span><p>${esc(text)}</p>`;$('conversation-log').append(entry);
}
async function api(path,body){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
  try{const response=await fetch(`/api/public/${path}`,{signal:controller.signal,cache:'no-store',...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
    const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Please review your care request.');return data;
  }finally{clearTimeout(timer);}
}
function reset(){stage='symptoms';search=null;lastNeeds=null;sequence++;busy=false;$('search-form').reset();$('search-form').hidden=false;$('symptom-step').hidden=false;$('zone-step').hidden=true;$('conversation-log').innerHTML=greeting;$('results').innerHTML='';$('error').textContent='';setBusy(false);}
function edit(){stage='symptoms';search=null;lastNeeds=null;sequence++;busy=false;$('search-form').hidden=false;$('symptom-step').hidden=false;$('zone-step').hidden=true;$('results').innerHTML='';$('error').textContent='';setBusy(false);$('description').focus();}
function setBusy(value){$('search-form').querySelectorAll('button').forEach(b=>b.disabled=value);}
$('restart').onclick=reset;$('edit-symptoms').onclick=edit;
function renderOptions(data,automatic=false){
  if(data.emergency_guidance_required){$('results').innerHTML=`<div class="warning"><b>Seek immediate emergency assistance</b><p>${esc(data.guidance)}</p></div><button class="text-button" id="edit-request">Edit my request</button>`;$('edit-request').onclick=edit;return;}
  const needs=data.interpretation;lastNeeds=needs;const chosen=data.suggested_facility;
  const understood=needs.symptom_tags.length?needs.symptom_tags.map(label).join(', '):needs.requested_specialty||needs.requested_resources.length?'a service request':'no supported care category yet';
  $('results').innerHTML=`<article class="facility-result primary-result"><div class="result-label">${chosen?'SUGGESTED FACILITY · REPORTED FACTS':data.outcome==='clarification_required'?'PLEASE CLARIFY':'NO CONFIRMED CURRENT MATCH'}</div><h3>${esc(data.title||chosen?.name||'No current suitable option confirmed')}</h3><p class="interpreted"><b>We understood:</b> ${esc(understood)}${needs.requested_specialty?` · requested specialist: ${esc(label(needs.requested_specialty))}`:''}${needs.requested_resources.length?` · resources: ${esc(needs.requested_resources.map(label).join(', '))}`:''}. This is your care request, not a diagnosis.</p>${needs.clarification&&needs.clarification!==data.explanation?`<p class="clarification">${esc(needs.clarification)}</p>`:''}<p class="care-explanation">${esc(data.explanation)}</p>${chosen?`<span class="result-tag">${chosen.distance_km==null?'Distance unknown':`${chosen.distance_km} km · fictional demo route`}</span><span class="result-tag">${esc(chosen.freshness_state)} report</span><span class="result-tag">${chosen.available_staffed_beds??'Unknown'} reported beds free</span>`:''}${chosen&&needs.follow_up_question?`<p class="clarification"><b>Optional follow-up:</b> ${esc(needs.follow_up_question)}</p>`:''}${data.next_steps?.length?`<div class="next-steps"><b>What you can do next</b><ul>${data.next_steps.map(s=>`<li>${esc(s)}</li>`).join('')}</ul></div>`:''}<p class="result-source">${esc(data.explanation_source||'Local verified comparison')}${automatic?' · refreshed locally after a hospital report changed':''}</p>${data.provider_notice?`<details class="provider-notice"><summary>Optional AI unavailable · local results shown</summary><p>${esc(data.provider_notice)}</p></details>`:''}</article><div class="alternative-options">${data.alternatives.filter(h=>data.outcome!=='clarification_required'&&h.hospital_id!==data.suggested_hospital_id).map(h=>`<article class="facility-result"><div class="result-label">${h.eligible?'ALTERNATIVE REPORTED OPTION':'NOT CONFIRMED FOR YOUR REQUEST'}</div><h3>${esc(h.name)}</h3><p>${h.distance_km==null?'Distance unknown':`${h.distance_km} km · fictional route`} · ${esc(h.freshness_state)} operational report</p><p>${esc((h.exclusion_reasons.length?h.exclusion_reasons:h.match_reasons).join('; '))}</p><p>Reported expertise: ${esc(h.specialties.map(label).join(', ')||'unknown')}. Capabilities report: ${esc(h.capabilities_freshness_state)}.</p></article>`).join('')}</div><p class="result-limit">${esc(data.limitations.join(' '))}</p><button type="button" id="edit-request" class="continue-button">Edit my care request ↺</button>`;
  $('edit-request').onclick=edit;
}
async function askForOptions(automatic=false){
  if(!search||busy)return false;busy=true;const number=++sequence;if(!automatic){$('error').textContent='Comparing current reports and care needs…';setBusy(true);}
  const input={...search};if(automatic){input.use_groq=false;if(lastNeeds){input.symptoms=lastNeeds.symptom_tags;input.requested_specialty=search.requested_specialty||lastNeeds.requested_specialty;input.requested_resources=[...new Set([...search.requested_resources,...lastNeeds.requested_resources])];}}
  try{const data=await api('recommendations',input);if(number!==sequence)return false;renderOptions(data,automatic);stage='results';$('search-form').hidden=true;$('error').textContent='';if(!automatic)message(data.emergency_guidance_required?'Seek immediate help; do not wait for hospital matching.':data.suggested_facility?'Here is the reported option that fits your request, and why.':data.title||'Here is what could and could not be confirmed.');return true;
  }catch(error){if(number===sequence){$('error').textContent=error.name==='AbortError'?'The request timed out. Please try again.':`Could not refresh care options: ${error.message}`;if(automatic)$('results').innerHTML='<p class="empty">Previous suggestions may be out of date. Edit your request and try again.</p>'; }return false;
  }finally{if(number===sequence){busy=false;setBusy(false);}}
}
$('search-form').onsubmit=async event=>{
  event.preventDefault();if(busy)return;$('error').textContent='';
  if(stage==='symptoms'){
    const description=$('description').value.trim();const symptoms=[...document.querySelectorAll('.checks input:checked')].map(i=>i.value);
    search={message:description,symptoms,zone_id:null,requested_specialty:$('specialty').value||null,requested_resources:[...document.querySelectorAll('.resource-checks input:checked')].map(i=>i.value),use_groq:$('use-groq').checked};
    if(!description&&!symptoms.length&&!search.requested_specialty&&!search.requested_resources.length){$('error').textContent='Describe your concern, select symptoms, or choose a care preference.';return;}
    const number=++sequence;busy=true;setBusy(true);
    try{const preview=await api('symptom-preview',search);if(number!==sequence)return;message(description||symptoms.map(label).join(', ')||'A requested care service','user');
      if(preview.emergency_guidance_required){renderOptions(preview);stage='results';$('search-form').hidden=true;return;}
      message('Thanks. Which area are you in? I will compare your full request with the latest hospital reports.');stage='zone';$('symptom-step').hidden=true;$('zone-step').hidden=false;$('zone').focus();
    }catch(error){$('error').textContent=error.name==='AbortError'?'The care check timed out. Please try again.':error.message;}
    finally{if(number===sequence){busy=false;setBusy(false);}}
  }else{search.zone_id=$('zone').value||null;message($('zone').selectedOptions[0].textContent,'user');await askForOptions();}
};
function renderReports(hospitals){$('hospital-status').innerHTML=hospitals.map(h=>{const age=Date.now()-Date.parse(h.reported_at),current=Number.isFinite(age)&&age>=0&&age<=900000;const beds=h.staffed_general_beds==null||h.occupied_general_beds==null?null:Math.max(0,h.staffed_general_beds-h.occupied_general_beds);return `<article class="hospital-report"><div class="report-top"><span>${esc(h.zone_id)}</span><span class="report-mark">+</span></div><h3>${esc(h.name)}</h3><p class="report-detail">${h.accepting_patients===true?'Accepting patients':h.accepting_patients===false?'Not accepting patients':'Accepting status unknown'}</p><p class="report-capacity">${beds??'Unknown'} staffed beds reported free</p><p class="report-detail">Expertise: ${esc((h.specialties||[]).map(label).join(', ')||'Unknown')}<br>Oxygen stations: ${esc(h.resources?.oxygen_stations??'unknown')} · X-ray slots: ${esc(h.resources?.xray_slots??'unknown')}</p><p class="report-status ${current?'current':''}">${current?'Current report':'Stale / unknown report'} · ${h.reported_at?esc(new Date(h.reported_at).toLocaleString()):'No timestamp'}</p></article>`;}).join('');}
async function refreshReports(){
  if(polling)return;polling=true;
  try{const data=await api('hospitals');renderReports(data.hospitals);$('connection').textContent=`Reports checked ${new Date().toLocaleTimeString()}`;
    const zones=JSON.stringify(data.zones);if(zones!==zoneSignature){const previous=$('zone').value;$('zone').innerHTML='<option value="">Any zone</option>'+data.zones.map(z=>`<option value="${esc(z.zone_id)}">${esc(z.display_name)} · ${esc(z.zone_id)}</option>`).join('');$('zone').value=previous;zoneSignature=zones;}
    const next=JSON.stringify(data.hospitals)+data.hospitals.map(h=>[h.reported_at,h.capabilities_reported_at].map(t=>{const age=Date.now()-Date.parse(t);return Number.isFinite(age)&&age>=0&&age<=900000;}).join()).join();
    if(stage==='results'&&search&&signature&&next!==signature){if(busy)return;if(!await askForOptions(true))return;}
    signature=next;
  }catch(error){$('connection').textContent='Hospital reports offline · previous information may be stale';}finally{polling=false;}
}
api('assistant-status').then(s=>{$('assistant-status').textContent=s.configured?'Groq is configured. Enable it for an intentional request.':'Local matching is ready; Groq is not configured on the server.';}).catch(()=>{$('assistant-status').textContent='Assistant status unavailable.';});
refreshReports();setInterval(refreshReports,5000);
