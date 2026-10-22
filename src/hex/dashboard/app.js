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
