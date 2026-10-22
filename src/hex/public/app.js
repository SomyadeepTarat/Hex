const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let hospitals=[], signature='', lastInput=null, lastNeeds=null, busy=false, sequence=0;
const label = s => s==='general_concern'?'a health concern for general assessment':String(s).replaceAll('_',' ');
async function request(path, body) {
  const response = await fetch(`/api/public/${path}`,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'}:{cache:'no-store'});
  const data = await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Check your description and care preferences.');
  return data;
}
function renderNetwork(){
  $('hospital-status').innerHTML=hospitals.map(h=>{
    const age=Date.now()-Date.parse(h.reported_at),fresh=Number.isFinite(age)&&age>=0&&age<=900000;
    return `<div class="hospital"><div class="symbol">✚</div><div class="details"><b>${esc(h.name)}</b><small>${esc((h.specialties||[]).map(label).join(' · '))}<br>${h.accepting_patients?'Accepting':'Not accepting'} · ${fresh?'Current':'Stale / unknown'} report · ${esc(h.reported_at?new Date(h.reported_at).toLocaleTimeString():'unknown')}</small></div><div class="capacity">${h.staffed_general_beds==null||h.occupied_general_beds==null?'Unknown':Math.max(0,h.staffed_general_beds-h.occupied_general_beds)} reported beds free<small>Oxygen stations: ${esc(h.resources?.oxygen_stations??'unknown')} · X-ray slots: ${esc(h.resources?.xray_slots??'unknown')}</small></div></div>`;
  }).join('');
}
function renderResult(data, automatic){
  const result=$('results');
  if(data.emergency_guidance_required){result.innerHTML=`<div class="warning"><h2>Seek immediate emergency assistance</h2><p>${esc(data.guidance)}</p></div>`;return;}
  const needs=data.interpretation;lastNeeds=needs;
  const interpretation=`<div class="interpreted">${needs.reported_concern?`<b>Your description:</b> ${esc(needs.reported_concern)}<br>`:''}<b>We understood:</b> ${esc(needs.symptom_tags.map(label).join(', ')||(needs.requested_specialty||needs.requested_resources.length?'a service request':'no supported care category yet'))}${needs.requested_specialty?` · specialist requested: ${esc(label(needs.requested_specialty))}`:''}${needs.requested_resources.length?` · resources requested: ${esc(needs.requested_resources.map(label).join(', '))}`:''}. This describes your request, not a diagnosis. Please correct it if needed.</div>`;
  const selected=data.suggested_facility;
  result.innerHTML=`<article class="recommendation"><div class="rec-title">${selected?'SUGGESTED FACILITY · BASED ON REPORTED FACTS':data.outcome==='clarification_required'?'PLEASE CLARIFY':'NO CONFIRMED CURRENT MATCH'}</div><h2>${esc(data.title||selected?.name||'We cannot confirm a suitable current option')}</h2>${interpretation}${needs.clarification&&needs.clarification!==data.explanation?`<p class="clarification">${esc(needs.clarification)}</p>`:''}<div class="explanation">${esc(data.explanation)}</div>${selected?`<div class="evidence"><span>${selected.distance_km==null?'Distance unknown':`${selected.distance_km} km · synthetic route`}</span><span>${esc(selected.freshness_state)} operational report</span><span>${esc(selected.available_staffed_beds??'Unknown')} staffed beds reported free</span></div>`:''}${selected&&needs.follow_up_question?`<p class="clarification"><b>Optional follow-up:</b> ${esc(needs.follow_up_question)}</p>`:''}${data.next_steps?.length?`<div class="next-steps"><b>What you can do next</b><ul>${data.next_steps.map(step=>`<li>${esc(step)}</li>`).join('')}</ul></div>`:''}<p class="provider">${esc(data.explanation_source||'Local verified comparison')}${automatic?' · Refreshed locally after a hospital status/freshness change':''}</p>${data.provider_notice?`<p class="fineprint">${esc(data.provider_notice)}</p>`:''}<div class="comparison">${data.alternatives.filter(h=>h.hospital_id!==data.suggested_hospital_id).map(h=>`<article><h3>${esc(h.name)}${h.distance_km==null?'':` · ${h.distance_km} km (synthetic)`}</h3><p>${esc(h.exclusion_reasons.length?h.exclusion_reasons.join('; '):h.match_reasons.join('; '))}.<br>Expertise: ${esc(h.specialties.map(label).join(', ')||'unknown')}. Capabilities report: ${esc(h.capabilities_freshness_state)}.</p></article>`).join('')}</div><p class="fineprint">${esc(data.limitations.join(' '))}</p></article>`;
}
async function suggest(input,automatic=false){
  if(busy&&automatic)return;
  const current=++sequence;busy=true;
  if(!automatic){$('submit').disabled=true;$('submit').textContent=input.use_groq?'Interpreting and comparing…':'Comparing reported facilities…';}
  try{const data=await request('recommendations',input);if(current!==sequence)return;renderResult(data,automatic);$('error').textContent='';}
  catch(e){if(current===sequence){$('error').textContent=e.message;$('results').innerHTML='<div class="empty">The suggestion could not be refreshed. Please try again; previous availability may have changed.</div>';}}
  finally{if(current===sequence){busy=false;$('submit').disabled=false;$('submit').textContent='Find and explain a suitable hospital →';}}
}
$('search-form').onsubmit=async e=>{e.preventDefault();lastInput={message:$('message').value.trim(),symptoms:[...document.querySelectorAll('.checks input:checked')].map(x=>x.value),zone_id:$('zone').value||null,requested_specialty:$('specialty').value||null,requested_resources:[...document.querySelectorAll('.resource-checks input:checked')].map(x=>x.value),use_groq:$('use-groq').checked};lastNeeds=null;await suggest(lastInput);};
for(const chip of document.querySelectorAll('[data-example]'))chip.onclick=()=>{$('message').value=chip.dataset.example;$('message').focus();};
async function refresh(){
  try{const data=await request('hospitals');hospitals=data.hospitals;renderNetwork();$('connection').textContent='Connected · synthetic reports';
    if($('zone').options.length===1)$('zone').innerHTML='<option value="">Choose an area</option>'+data.zones.map(z=>`<option value="${esc(z.zone_id)}">${esc(z.display_name)} · ${esc(z.zone_id)}</option>`).join('');
    // Include freshness transitions: a report becoming stale must invalidate a suggestion.
    const next=JSON.stringify(hospitals)+hospitals.map(h=>[h.reported_at,h.capabilities_reported_at].map(t=>Math.floor((Date.now()-Date.parse(t))/900000)).join(':')).join();
    if(lastInput&&signature&&next!==signature){
      if(busy)return; // Keep the old signature so the next poll retries the changed snapshot.
      const input={...lastInput,use_groq:false};
      if(lastNeeds){input.symptoms=lastNeeds.symptom_tags;input.requested_specialty=lastInput.requested_specialty||lastNeeds.requested_specialty;input.requested_resources=[...new Set([...lastInput.requested_resources,...lastNeeds.requested_resources])];}
      await suggest(input,true);
    }
    signature=next;
  }catch(e){$('connection').textContent='Offline · availability may be outdated';}
}
request('assistant-status').then(s=>{$('assistant-status').textContent=s.configured?'Groq is configured. Enable it above for a request.':'Local matching is ready. Add GROQ_API_KEY to the server .env file to enable Groq.';}).catch(()=>{$('assistant-status').textContent='Assistant connection unavailable. Check the server connection.';});
refresh();setInterval(refresh,5000);
