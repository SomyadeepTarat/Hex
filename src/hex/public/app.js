const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {fever:'Fever',cough:'Cough',shortness_of_breath:'Breathing difficulty',fatigue:'Fatigue',vomiting:'Vomiting',severe_breathing_difficulty:'Severe breathing difficulty',severe_chest_pain:'Severe chest pain'};
let stage = 'symptoms', search = null, signature = '', zoneSignature = '', requestNumber = 0, polling = false;
const greeting = $('conversation-log').innerHTML;

function message(text, role = 'assistant') {
  const entry = document.createElement('div');
  entry.className = `chat-message ${role}`;
  entry.innerHTML = `<span class="message-label">${role === 'user' ? 'YOU' : 'HEX'}</span><p>${esc(text)}</p>`;
  $('conversation-log').append(entry);
}

function reset() {
  stage='symptoms'; search=null; requestNumber++;
  $('search-form').reset(); $('search-form').hidden=false;
  $('symptom-step').hidden=false; $('zone-step').hidden=true;
  $('conversation-log').innerHTML=greeting; $('results').innerHTML=''; $('error').textContent='';
}
$('restart').onclick=reset;
$('edit-symptoms').onclick=()=>{ stage='symptoms'; $('symptom-step').hidden=false; $('zone-step').hidden=true; $('conversation-log').innerHTML=greeting; $('results').innerHTML=''; search=null; requestNumber++; };

function inferTags(text) {
  const patterns = [
    ['severe_breathing_difficulty',/severe breathing|cannot breathe|can't breathe|blue lips/i],
    ['severe_chest_pain',/severe chest pain/i], ['fever',/\bfever\b|high temperature/i],
    ['cough',/\bcough(?:ing)?\b/i], ['shortness_of_breath',/breathless|shortness of breath|breathing difficulty/i],
    ['fatigue',/fatigue|tired|exhausted/i], ['vomiting',/vomit|nausea|throwing up/i]
  ];
  return patterns.filter(([,re])=>re.test(text)).map(([tag])=>tag);
}

async function askForOptions(automatic=false) {
  if(!search)return;
  const request=++requestNumber;
  if(!automatic){$('error').textContent='Checking the latest reported information…';$('search-form').querySelectorAll('button').forEach(b=>b.disabled=true);}
  try {
    const response=await fetch('/api/public/recommendations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(search),cache:'no-store'});
    const data=await response.json();
    if(request!==requestNumber)return;
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Please review the selected symptoms.');
    if(!automatic)message(data.emergency_guidance_required ? 'Please seek urgent help rather than waiting for a facility search.' : data.suggested_facility ? 'Here’s what matches the current reports. Please confirm availability with the facility before you go.' : 'I can see hospital reports, but they aren’t current enough to make a confident suggestion. Here’s the last reported information.');
    renderOptions(data); stage='results'; $('search-form').hidden=true; $('error').textContent='';
    if(!automatic)$('conversation-log').lastElementChild?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
  } catch(error) {
    if(request===requestNumber){$('error').textContent=`I couldn’t check care options: ${error.message}. Please try again.`;}
  } finally { $('search-form').querySelectorAll('button').forEach(b=>b.disabled=false); }
}

function renderOptions(data) {
  if(data.emergency_guidance_required){$('results').innerHTML=`<div class="warning"><b>Urgent guidance</b><p>${esc(data.guidance || data.limitations?.join(' ') || 'Seek immediate medical attention; do not wait for a facility suggestion.')}</p></div>`;return;}
  const selected=data.suggested_hospital_id;
  const options=[...(data.alternatives||[])].sort((a,b)=>(b.hospital_id===selected)-(a.hospital_id===selected));
  $('results').innerHTML=options.map(h=>`<article class="facility-result"><div class="result-label">${h.hospital_id===selected?'SUGGESTED FACILITY':'LAST REPORTED OPTION'}</div><h3>${esc(h.name)}</h3><p>${esc(h.zone_id)} · ${h.available_staffed_beds==null?'Staffed availability unknown':`${h.available_staffed_beds} staffed beds last reported available`}</p><ul>${(h.match_reasons||[]).filter(reason=>search?.zone_id||reason!=='other zone').map(reason=>`<li>${esc(reason)}</li>`).join('')}</ul><span class="result-tag">${esc(h.freshness_state)} report</span><span class="result-tag">${esc(String(h.availability_state).replaceAll('_',' '))}</span><p>Reported: ${h.reported_at?esc(new Date(h.reported_at).toLocaleString()):'Unknown'}</p></article>`).join('') + `<p class="result-limit">${esc((data.limitations||[]).map(text=>text.replace('Synthetic decision-support demo; this is not a diagnosis.','This service does not provide a diagnosis.')).join(' '))}</p>`;
}

$('search-form').onsubmit=async event=>{
  event.preventDefault(); $('error').textContent='';
  if(stage==='symptoms') {
    const text=$('description').value.trim();
    if(text){
      const tags=inferTags(text);
      if(tags.some(tag=>tag==='severe_breathing_difficulty'||tag==='severe_chest_pain')){
        message('Severe symptoms','user'); search={symptoms:tags,zone_id:null}; await askForOptions(); return;
      }
      if(!tags.length){$('error').textContent='I can match the symptom options above. Please choose what applies, or contact a healthcare professional for symptoms outside this list.';return;}
      tags.forEach(tag=>{const input=document.querySelector(`.checks input[value="${tag}"]`);if(input)input.checked=true;});
      $('description').value='';
      message(`I matched your description to ${tags.map(t=>labels[t]).join(', ')}. Please review the selected options, then continue. You can unselect anything that doesn’t apply.`);
      return;
    }
    const symptoms=[...document.querySelectorAll('.checks input:checked')].map(input=>input.value);
    if(!symptoms.length){$('error').textContent='Choose at least one symptom to get started.';return;}
    message(symptoms.map(tag=>labels[tag]).join(', '),'user'); search={symptoms,zone_id:null};
    if(symptoms.includes('severe_breathing_difficulty')){await askForOptions();return;}
    message('Which part of the city are you in? An approximate zone is enough.');
    stage='zone'; $('symptom-step').hidden=true; $('zone-step').hidden=false; $('zone').focus();
  } else {
    search.zone_id=$('zone').value||null;
    message($('zone').selectedOptions[0].textContent,'user');
    await askForOptions();
  }
};

function renderReports(hospitals) {
  $('hospital-status').innerHTML=hospitals.map(h=>{
    const age=h.reported_at?Date.now()-Date.parse(h.reported_at):NaN;
    const current=Number.isFinite(age)&&age>=0&&age<=900000;
    const beds=h.staffed_general_beds==null||h.occupied_general_beds==null?null:Math.max(0,h.staffed_general_beds-h.occupied_general_beds);
    return `<article class="hospital-report"><div class="report-top"><span>${esc(h.zone_id)}</span><span class="report-mark">+</span></div><h3>${esc(h.name)}</h3><p class="report-detail">${h.accepting_patients===true?'Reports accepting patients':h.accepting_patients===false?'Reports not accepting patients':'Accepting status unknown'}</p><p class="report-capacity">${beds==null?'Availability unknown':`${beds} staffed beds last reported available`}</p><p class="report-status ${current?'current':''}">${current?'Current report':Number.isFinite(age)?'Stale report':'Unknown report time'} · ${h.reported_at?esc(new Date(h.reported_at).toLocaleString()):'No timestamp'}</p></article>`;
  }).join('');
}

async function refreshReports() {
  if(polling)return; polling=true;
  try{
    const response=await fetch('/api/public/hospitals',{cache:'no-store'});
    if(!response.ok)throw new Error(`Hospital service returned ${response.status}`);
    const data=await response.json(); renderReports(data.hospitals);
    $('connection').textContent=`Reports checked ${new Date().toLocaleTimeString()}`;
    const previous=$('zone').value;
    const zones=data.zones?.length?data.zones:[...new Set(data.hospitals.map(h=>h.zone_id))].map(zone_id=>({zone_id}));
    const nextZones=JSON.stringify(zones);
    if(nextZones!==zoneSignature){$('zone').innerHTML='<option value="">Any zone</option>'+zones.map(z=>`<option value="${esc(z.zone_id)}">${esc(z.display_name||z.zone_id)}</option>`).join('');$('zone').value=previous;zoneSignature=nextZones;}
    const next=JSON.stringify([data.hospitals,data.hospitals.map(h=>Date.now()-Date.parse(h.reported_at)<=900000)]);
    if(stage==='results'&&search&&signature&&next!==signature)askForOptions(true);
    signature=next;
  }catch(error){$('connection').textContent='Unable to reach hospital reports';$('hospital-status').innerHTML='<p class="empty">Open this page through the running HEX server at /find-care/ to see hospital reports.</p>';}
  finally{polling=false;}
}
refreshReports(); setInterval(refreshReports,5000);
