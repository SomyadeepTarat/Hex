const links = document.querySelectorAll('.nav-item');
links.forEach((link) => {
  link.addEventListener('click', () => {
    links.forEach((item) => item.classList.remove('active'));
    link.classList.add('active');
  });
});

async function refreshDemoData() {
  const status = document.querySelector('#pipeline-status');
  try {
    const response = await fetch('http://localhost:8001/api/demo', { cache: 'no-store' });
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    const data = await response.json();
    document.querySelector('#sim-count').innerHTML = `${data.simulated_records} <small>simulated</small>`;
    status.textContent = `${data.privacy_filtered_records} records filtered in memory`;
    const generalOccupied = data.hospitals.reduce((sum, row) => sum + row.occupied_general_beds, 0);
    const generalTotal = data.hospitals.reduce((sum, row) => sum + row.general_beds, 0);
    const icuOccupied = data.hospitals.reduce((sum, row) => sum + row.occupied_icu_beds, 0);
    const icuTotal = data.hospitals.reduce((sum, row) => sum + row.icu_beds, 0);
    const occupancy = generalTotal ? (100 * generalOccupied / generalTotal) : 0;
    document.querySelector('#network-occupancy').innerHTML = `${occupancy.toFixed(1)}<small>%</small>`;
    document.querySelector('#occupancy-note').textContent = `${generalOccupied} of ${generalTotal} simulated general beds occupied`;
    document.querySelector('#occupancy-bar').style.width = `${occupancy}%`;
    document.querySelector('#zone-count').innerHTML = `${data.zones.length} <small>zones</small>`;
    document.querySelector('#zone-labels').textContent = data.zones.map((zone) => zone.display_name).join(', ');
    document.querySelector('#hospital-list').innerHTML = data.hospitals.map((hospital) => {
      const percent = hospital.general_beds ? Math.round(100 * hospital.occupied_general_beds / hospital.general_beds) : 0;
      return `<div class="hospital-row"><div class="hospital-icon">✚</div><div class="hospital-info"><b>${hospital.name}</b><small>${hospital.zone_id} · ${hospital.general_beds} GENERAL BEDS</small></div><div class="hospital-load"><b>${percent}%</b><div class="mini-progress"><i style="width:${percent}%"></i></div></div></div>`;
    }).join('');
    document.querySelector('#capacity-summary').innerHTML = `<div><span class="capacity-dot general"></span> General beds <b>${generalOccupied} / ${generalTotal}</b></div><div><span class="capacity-dot icu"></span> ICU beds <b>${icuOccupied} / ${icuTotal}</b></div>`;
    const byDay = new Map();
    data.simulated_cases.forEach((item) => {
      const day = item.reported_at.slice(0, 10);
      byDay.set(day, (byDay.get(day) || 0) + 1);
    });
    const recentDays = [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b)).slice(-3);
    const maxCases = Math.max(1, ...recentDays.map(([, count]) => count));
    document.querySelector('.y-labels').innerHTML = [maxCases, Math.ceil(maxCases * .75), Math.ceil(maxCases * .5), Math.ceil(maxCases * .25), 0].map((n) => `<span>${n}</span>`).join('');
    document.querySelector('#case-chart').innerHTML = recentDays.map(([day, count]) => {
      const height = Math.max(5, 77 * count / maxCases);
      return `<div class="bar-group"><i style="height:${height}%"></i><small>${new Date(`${day}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: '2-digit' }).toUpperCase()}</small></div>`;
    }).join('');
    document.querySelector('#signal-title').textContent = 'Synthetic symptom summary';
    document.querySelector('#signal-copy').textContent = `${data.simulated_records} simulated cases generated from ${data.source_records} fictional input records. Summary only; not an outbreak alert.`;
    document.querySelector('#symptom-tags').innerHTML = data.top_symptoms
      .map(([name, count]) => `<span>${name.replaceAll('_', ' ').toUpperCase()} · ${count}</span>`)
      .join('');
    document.querySelector('#generated-at').textContent = `Updated ${new Date(data.generated_at).toLocaleTimeString()}`;
  } catch {
    status.textContent = 'Start Python demo API on port 8001';
  }
}

refreshDemoData();
setInterval(refreshDemoData, 10000);
