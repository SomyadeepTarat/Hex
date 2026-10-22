const API = '';
let hospitals = [];
let latestSignature = '';
let hasSearched = false;
let requestNumber = 0;
const statusRoot = document.querySelector('#hospital-status');

function renderHospitals(rows) {
  statusRoot.innerHTML = rows.map((h) => {
    const available = h.staffed_general_beds == null || h.occupied_general_beds == null
      ? 'Availability unknown'
      : `${Math.max(0, h.staffed_general_beds - h.occupied_general_beds)} staffed beds reported available`;
    const reportAge = h.reported_at ? Date.now() - Date.parse(h.reported_at) : NaN;
    const freshness = Number.isFinite(reportAge) && reportAge >= 0 && reportAge <= 900000 ? 'Current report' : Number.isFinite(reportAge) ? 'Stale report' : 'Report time unknown';
    const accepting = h.accepting_patients === true ? 'Accepting' : h.accepting_patients === false ? 'Not accepting' : 'Status unknown';
    return `<div class="hospital"><div class="symbol">✚</div><div class="details"><b>${h.name}</b><small>${h.zone_id} · ${accepting} · ${freshness} · Updated ${h.reported_at ? new Date(h.reported_at).toLocaleTimeString() : 'unknown'}</small></div><div class="capacity">${available}<small>Reported status</small></div></div>`;
  }).join('');
}

async function refreshHospitals() {
  try {
    const response = await fetch(`${API}/api/public/hospitals`, { cache: 'no-store' });
    if (!response.ok) throw new Error('offline');
    const data = await response.json();
    const signature = JSON.stringify(data.hospitals);
    hospitals = data.hospitals;
    renderHospitals(hospitals);
    document.querySelector('#connection').textContent = `${data.environment} · refreshed now`;
    if (hasSearched && signature !== latestSignature) document.querySelector('#search-form').requestSubmit();
    latestSignature = signature;
  } catch {
    document.querySelector('#connection').textContent = 'API offline';
    statusRoot.innerHTML = '<div class="empty">Start the HEX API to load reported facility status.</div>';
  }
}

document.querySelector('#search-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  hasSearched = true;
  const currentRequest = ++requestNumber;
  document.querySelector('#error').textContent = '';
  const symptoms = [...document.querySelectorAll('.checks input:checked')].map((input) => input.value);
  const zone_id = document.querySelector('#zone').value || null;
  const results = document.querySelector('#results');
  try {
    const response = await fetch(`${API}/api/public/recommendations`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symptoms, zone_id }), cache: 'no-store',
    });
    const data = await response.json();
    if (currentRequest !== requestNumber) return;
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Select at least one symptom and try again.');
    if (data.emergency_guidance_required) {
      results.innerHTML = `<div class="warning"><b>Urgent guidance</b><br>${data.guidance}</div>`;
      return;
    }
    const selected = data.suggested_facility;
    const alternatives = data.alternatives.filter(h => h.hospital_id !== data.suggested_hospital_id).map((h) => `${h.name} (${h.zone_id}; ${h.freshness_state} status; ${h.availability_state.replace('_', ' ')})`).join(' · ');
    results.innerHTML = selected
      ? `<article class="recommendation"><div class="rec-title">SUGGESTED FACILITY BASED ON REPORTED SERVICES AND AVAILABILITY</div><h2>${selected.name}</h2><div class="reasons">${selected.match_reasons.join(' · ')}<br>Reported ${new Date(selected.reported_at).toLocaleString()} · ${selected.freshness_state} information.</div><div class="alternatives"><b>Alternatives:</b> ${alternatives || 'No other facilities reported.'}<br><br>${data.limitations.join(' ')}</div></article>`
      : `<div class="empty">No facility has current, accepting status. Check the hospital list and contact a facility directly. ${data.limitations.join(' ')}</div>`;
  } catch (error) {
    document.querySelector('#error').textContent = error.message;
  }
});

async function refreshZones() {
  try {
    const data = await (await fetch(`${API}/api/public/hospitals`, { cache: 'no-store' })).json();
    const select = document.querySelector('#zone');
    const existing = select.value;
    const zones = [...new Map(data.hospitals.map((h) => [h.zone_id, h.zone_id])).values()];
    select.innerHTML = '<option value="">Any zone</option>' + zones.map((z) => `<option>${z}</option>`).join('');
    select.value = existing;
  } catch { /* status refresh reports offline state */ }
}

refreshZones();
refreshHospitals();
setInterval(refreshHospitals, 5000);
