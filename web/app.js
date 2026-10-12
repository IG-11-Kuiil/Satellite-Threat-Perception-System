'use strict';
const $ = (id) => document.getElementById(id);
let mode = 'comparison', busy = false, result = null, view = 'annotated';
let healthState = null;
const profileLabels = {aerial:'YOLO11s-OBB / DOTA v1',aerial_large:'YOLO26m-OBB / DOTA v1',general:'YOLOv8s / COCO'};
const files = { first: null, second: null }, urls = { first: null, second: null };
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
function showError(message) { $('error').textContent = message; $('error').hidden = !message; }
function updateReady() {
  const required = mode === 'comparison' ? 2 : 1;
  const loaded = Number(Boolean(files.first)) + (required === 2 ? Number(Boolean(files.second)) : 0);
  $('image-count').textContent = `${loaded} / ${required} LOADED`;
  $('run-button').disabled = busy || loaded < required;
  $('run-button').firstElementChild.textContent = busy ? 'Analysis in progress' : mode === 'comparison' ? 'Run change detection' : 'Analyze image';
  $('run-hint').textContent = busy ? 'Processing on the local engine.' : loaded === required ? 'Ready for analysis. First run loads the detector.' : required === 2 ? 'Upload both images to begin.' : 'Upload an image to begin.';
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll('.mode-card, .remove-file, .settings-body input, .settings-body select').forEach(el => { el.disabled = value; });
  ['first', 'second'].forEach(slot => { $(`file-${slot}`).disabled = value; $(`drop-${slot}`).classList.toggle('disabled', value); });
  $('verify-weak').disabled = value || $('model-profile').value !== 'aerial';
  updateReady();
}
function chooseMode(value) {
  if (busy) return;
  mode = value;
  if (result && result.mode !== value) {
    $('results').hidden = true; $('empty-results').hidden = false;
    $('result-meta').textContent = 'AWAITING ANALYSIS';
  }
  document.querySelectorAll('.mode-card').forEach(el => { const selected = el.dataset.mode === mode; el.classList.toggle('selected', selected); el.setAttribute('aria-pressed', selected); });
  $('second-container').hidden = mode === 'single';
  $('upload-grid').classList.toggle('single', mode === 'single');
  $('first-label').textContent = mode === 'comparison' ? 'BEFORE IMAGE' : 'SOURCE IMAGE';
  $('first-role').textContent = mode === 'comparison' ? 'BASELINE' : 'OBSERVATION';
  $('input-note').textContent = mode === 'comparison' ? 'Use the same ground area, crop, and scale in both images. Baseline first, later observation second.' : 'Upload overhead imagery to detect aircraft, assess proximity groups, and review scene activity.';
  showError(''); updateReady();
}
function setFile(slot, file) {
  if (busy) return;
  if (file && file.size > 20 * 1024 * 1024) { showError('Each image must be 20 MB or smaller.'); return; }
  if (file && !/\.(png|jpe?g|webp|tiff?)$/i.test(file.name)) { showError('Choose PNG, JPEG, WebP, or TIFF imagery.'); return; }
  if (urls[slot]) URL.revokeObjectURL(urls[slot]);
  files[slot] = file; urls[slot] = file ? URL.createObjectURL(file) : null;
  const drop = $(`drop-${slot}`), preview = $(`preview-${slot}`);
  drop.querySelector('.upload-empty strong').textContent = 'Drop imagery here';
  preview.hidden = !file;
  drop.querySelector('.upload-empty').hidden = Boolean(file);
  drop.querySelector('.preview-overlay').hidden = !file;
  document.querySelector(`.remove-file[data-slot="${slot}"]`).hidden = !file;
  const info = $(`info-${slot}`);
  info.textContent = file ? `${file.name} Â· ${(file.size / 1024 / 1024).toFixed(1)} MB` : 'No image selected';
  info.title = file?.name || '';
  if (file) {
    preview.src = urls[slot];
    preview.onload = () => { if (files[slot] === file) info.textContent = `${file.name} Â· ${preview.naturalWidth} Ã— ${preview.naturalHeight}`; };
    preview.onerror = () => { if (files[slot] === file) { preview.hidden = true; drop.querySelector('.upload-empty').hidden = false; drop.querySelector('.upload-empty strong').textContent = /\.tiff?$/i.test(file.name) ? 'TIFF image loaded' : 'Preview unavailable'; info.textContent = `${file.name} Â· ready for server validation`; } };
  } else {
    preview.removeAttribute('src'); $(`file-${slot}`).value = '';
    drop.querySelector('.upload-empty strong').textContent = 'Drop imagery here';
  }
  showError(''); updateReady();
}
document.querySelectorAll('.mode-card').forEach(el => el.addEventListener('click', () => chooseMode(el.dataset.mode)));
for (const slot of ['first', 'second']) {
  $(`file-${slot}`).addEventListener('change', event => setFile(slot, event.target.files[0] || null));
  const drop = $(`drop-${slot}`);
  for (const name of ['dragenter', 'dragover']) drop.addEventListener(name, event => { event.preventDefault(); if (!busy) drop.classList.add('dragging'); });
  for (const name of ['dragleave', 'drop']) drop.addEventListener(name, event => { event.preventDefault(); drop.classList.remove('dragging'); });
  drop.addEventListener('drop', event => { if (event.dataTransfer.files.length > 1) return showError('Drop one image into each slot.'); setFile(slot, event.dataTransfer.files[0] || null); });
}
document.querySelectorAll('.remove-file').forEach(el => el.addEventListener('click', () => setFile(el.dataset.slot, null)));
for (const id of ['confidence', 'proximity']) $(id).addEventListener('input', () => { $(`${id}-value`).textContent = `${$(id).value}%`; });

async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Invalid request. Check the uploaded images and settings.');
  return data;
}
function progress(fraction, message) {
  $('progress-panel').hidden = false;
  const percent = Math.round(Math.max(0, Math.min(1, fraction)) * 100);
  $('progress-value').textContent = `${percent}%`;
  $('progress-fill').style.width = `${percent}%`;
  $('progress-message').textContent = message;
}
async function watchJob(id) {
  let failures = 0;
  while (true) {
    let job;
    try { job = await api(`/api/jobs/${id}`); failures = 0; }
    catch (error) { failures++; if (failures >= 5) throw new Error('Connection interrupted. Your run may still be processing. Reopen it from Recent runs when the local server is available.'); await delay(2000); continue; }
    progress(job.progress || 0, job.message);
    if (job.status === 'completed') { renderResult(job.result); return; }
    if (job.status === 'failed') throw new Error(job.error || 'Analysis failed. Check your images and try again.');
    await delay(1000);
  }
}
$('run-button').addEventListener('click', async () => {
  if (busy || !files.first || (mode === 'comparison' && !files.second)) return;
  showError(''); setBusy(true);
  // Hide the previous assessment so it cannot be mistaken for this new run.
  $('results').hidden = true; $('empty-results').hidden = false;
  $('result-meta').textContent = 'ANALYSIS IN PROGRESS';
  progress(0, 'Uploading and validating imageryâ€¦');
  const form = new FormData();
  form.append('mode', mode); form.append('image', files.first);
  if (mode === 'comparison') form.append('after', files.second);
  form.append('confidence', Number($('confidence').value) / 100);
  form.append('proximity', Number($('proximity').value) / 100);
  form.append('tiled', $('tiled').checked); form.append('vehicles', $('vehicles').checked);
  form.append('resolution', $('resolution').value);
  form.append('model_profile', $('model-profile').value);
  form.append('verify_weak', $('verify-weak').checked);
  try { const job = await api('/api/analyze', { method: 'POST', body: form }); await refreshHistory(); await watchJob(job.id); }
  catch (error) { showError(error.message || 'Could not reach the local analysis engine.'); }
  finally { setBusy(false); $('progress-panel').hidden = true; refreshHistory(); checkHealth(); }
});

function element(tag, className, text) { const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el; }
function signed(value) { return value > 0 ? `+${value}` : String(value); }
function metric(label, value, detail, amber = false) {
  const card = element('div', `metric${amber ? ' amber' : ''}`);
  card.append(element('div', 'metric-label', label), element('div', 'metric-value', value), element('div', 'metric-detail', detail));
  return card;
}
function sceneName(label) { return label === 'scene' ? 'Source scene' : `${label[0].toUpperCase()}${label.slice(1)} scene`; }
function renderResult(data) {
  if (!busy) chooseMode(data.mode);
  result = data; view = 'annotated';
  const resultUrl = new URL(window.location.href);
  resultUrl.searchParams.set('run', data.id);
  window.history.replaceState(null, '', resultUrl);
  $('result-model').textContent = data.model;
  $('empty-results').hidden = true; $('results').hidden = false;
  $('result-meta').textContent = `RUN ${data.id.slice(0, 8).toUpperCase()} / ${new Date(data.created_at).toLocaleString()}`;
  const scenes = Object.values(data.scenes), latest = data.scenes.after || data.scenes.scene;
  const metrics = $('metrics'); metrics.replaceChildren();
  if (data.change) {
    metrics.append(metric('AIRCRAFT CHANGE', signed(data.change.aircraft_change.difference), `${data.scenes.before.aircraft_count} baseline â†’ ${latest.aircraft_count} current`),
      metric('ACTIVITY TREND', data.change.activity_trend, `${data.change.activity_change.previous_level} â†’ ${data.change.activity_change.current_level}`),
      metric('REVIEW PRIORITY', data.change.priority, 'Based on change magnitude', data.change.priority === 'High'),
      metric('REVIEW FLAGS', scenes.reduce((n, s) => n + (s.review_required_count ?? s.low_confidence_count), 0), 'Weak, partial, or cross-model review candidates', scenes.some(s => (s.review_required_count ?? s.low_confidence_count))));
  } else {
    metrics.append(metric('AIRCRAFT DETECTED', latest.aircraft_count, latest.vehicles_enabled ? `${latest.vehicle_count} experimental vehicle detections` : 'Vehicle detection disabled'),
      metric('ASSET PRESENCE', latest.activity_level, 'Prototype count band'),
      metric('PROXIMITY GROUPS', latest.spatial.group_count, `${latest.spatial.isolated_count} isolated aircraft`),
      metric('REVIEW FLAGS', latest.review_required_count ?? latest.low_confidence_count, 'Weak, partial, or cross-model review candidates', (latest.review_required_count ?? latest.low_confidence_count) > 0));
  }
  const chip = $('priority-chip');
  chip.textContent = data.change ? `${data.change.priority.toUpperCase()} PRIORITY` : 'SCENE ASSESSMENT';
  chip.className = `chip ${data.change?.priority.toLowerCase() || ''}`;
  $('assessment-text').textContent = data.change_summary || latest.summary;
  $('policy-caption').textContent = `Prototype policy: ${data.assessment_policy?.id || 'legacy count rules'}. Presence and review bands are not military threat ratings. Formal analytic confidence: not assessed.`;
  const summaries = $('scene-summaries'); summaries.replaceChildren();
  if (data.change) for (const [label, scene] of Object.entries(data.scenes)) {
    const block = element('div', 'scene-summary'); block.append(element('h3', '', sceneName(label).toUpperCase()), element('p', '', scene.summary)); summaries.append(block);
  }
  const warnings = new Set([...(data.change?.warnings || []), ...scenes.flatMap(s => s.warnings)]);
  $('warnings').replaceChildren(...[...warnings].map(text => element('li', '', text)));
  $('download-report').href = data.report_url; $('download-json').href = data.json_url;
  $('table-scene').replaceChildren(...Object.keys(data.scenes).map(label => { const option = element('option', '', sceneName(label)); option.value = label; return option; }));
  $('table-scene').value = data.scenes.after ? 'after' : 'scene';
  renderImages(); renderTable(); updateViewButtons();
  $('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function renderImages() {
  const container = $('scene-images'); container.replaceChildren(); container.classList.toggle('single', result.mode === 'single');
  for (const [label, scene] of Object.entries(result.scenes)) {
    const card = element('div', 'scene-card'), header = element('div', 'scene-card-header');
    header.append(element('span', '', sceneName(label).toUpperCase()), element('span', '', `${scene.width} Ã— ${scene.height} PX`));
    const button = element('button'); button.type = 'button'; button.setAttribute('aria-label', `Expand ${sceneName(label).toLowerCase()} ${view} imagery`);
    const image = element('img'); image.src = view === 'annotated' ? scene.annotated_url : scene.original_url; image.alt = `${sceneName(label)} â€” ${view} imagery`;
    button.append(image); button.addEventListener('click', () => { $('dialog-image').src = image.src; $('dialog-title').textContent = `${sceneName(label).toUpperCase()} / ${view.toUpperCase()}`; $('image-dialog').showModal(); });
    const details = element('div', 'scene-metrics');
    details.append(element('span', '', `${scene.aircraft_count} AIRCRAFT`), element('span', '', `${scene.spatial.group_count} GROUPS`), element('span', '', `${scene.activity_level} ACTIVITY`));
    if (scene.duplicates_removed !== undefined) details.append(element('span', '', `${scene.duplicates_removed} DUPLICATE CANDIDATES REMOVED`));
    if (scene.review_candidate_count) details.append(element('span', 'review-candidate-tag', `${scene.primary_aircraft_count} PRIMARY + ${scene.review_candidate_count} REVIEW CANDIDATE(S)`));
    card.append(header, button, details); container.append(card);
  }
}
function updateViewButtons() { document.querySelectorAll('[data-view]').forEach(button => { const selected = button.dataset.view === view; button.classList.toggle('selected', selected); button.setAttribute('aria-pressed', selected); }); }
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => { view = button.dataset.view; updateViewButtons(); renderImages(); }));
function renderTable() {
  const scene = result.scenes[$('table-scene').value], tbody = $('detections-table'); tbody.replaceChildren();
  if (!scene.detections.length) { const row = element('tr', 'no-detections'), cell = element('td', '', 'No assets detected at these settings. Review the imagery manually; absence of detections is not proof of absence.'); cell.colSpan = 4; row.append(cell); tbody.append(row); return; }
  for (const detection of scene.detections) {
    const row = element('tr'); row.append(element('td', '', detection.id), element('td', '', detection.class));
    const cell = element('td'), confidence = element('div', `confidence-cell${detection.confidence < .4 ? ' low' : ''}`), bar = element('span', 'confidence-bar'), fill = element('i');
    fill.style.width = `${Math.round(detection.confidence * 100)}%`; bar.append(fill);
    confidence.append(bar, element('span', '', `${Math.round(detection.confidence * 100)}%`)); cell.append(confidence); row.append(cell);
    if (detection.accepted_by === 'cross_model_review') {
      cell.append(element('small','support-score',`${Math.round(detection.supporting_confidence*100)}% supporting model Â· REVIEW`));
      cell.title = `Primary: ${detection.confidence.toFixed(3)}; ${detection.supporting_model}: ${detection.supporting_confidence.toFixed(3)}. Needs manual confirmation.`;
    }
    row.append(element('td', '', `${Math.round((detection.bbox[0] + detection.bbox[2]) / 2)}, ${Math.round((detection.bbox[1] + detection.bbox[3]) / 2)}`)); tbody.append(row);
  }
}
$('table-scene').addEventListener('change', renderTable);
async function refreshHistory() {
  try {
    const runs = await api('/api/jobs'), container = $('history'); container.replaceChildren();
    $('mobile-history').replaceChildren(element('option', '', 'Recent runs'));
    $('mobile-history').firstElementChild.value = '';
    for (const run of runs) {
      const option = element('option', '', `${run.status === 'failed' ? 'Failed Â· ' : ''}${run.filenames.join(' â†’ ')}`);
      option.value = run.id; $('mobile-history').append(option);
    }
    if (!runs.length) { container.append(element('p', 'sidebar-note', 'Your analyses will appear here.')); return; }
    for (const run of runs.slice(0, 6)) {
      const button = element('button', 'history-item'); button.title = run.filenames.join(' â†’ ');
      button.append(element('strong', '', run.filenames.join(' â†’ ')));
      const detail = element('small'); detail.append(element('span', '', new Date(run.created_at).toLocaleDateString()), element('span', run.status === 'completed' ? 'complete' : '', run.status.toUpperCase())); button.append(detail);
      button.addEventListener('click', () => openRun(run.id)); container.append(button);
    }
  } catch { $('history').replaceChildren(element('p', 'sidebar-note', 'Recent runs unavailable.')); }
}
$('refresh-history').addEventListener('click', refreshHistory);
async function openRun(id) {
  if (busy || !id) return; showError('');
  try { const job = await api(`/api/jobs/${id}`); if (job.status === 'completed') renderResult(job.result); else if (job.status === 'failed') showError(job.error || 'This run failed.'); else { setBusy(true); await watchJob(id); } }
  catch (error) { showError(error.message); }
  finally { setBusy(false); $('progress-panel').hidden = true; refreshHistory(); }
}
$('mobile-history').addEventListener('change', event => openRun(event.target.value));
$('mobile-method').addEventListener('click', () => $('method-dialog').showModal());
async function checkHealth() {
  try { healthState = await api('/api/health'); $('system-status').textContent = 'ENGINE ONLINE'; $('system-dot').classList.remove('offline'); updateProfile(); }
  catch { $('system-status').textContent = 'ENGINE OFFLINE'; $('system-dot').classList.add('offline'); $('model-status').textContent = 'Start the local server to analyze imagery.'; }
}
function updateProfile() {
  const key = $('model-profile').value, profile = healthState?.model_profiles?.[key];
  $('verify-weak').disabled = busy || key !== 'aerial';
  $('selected-model').textContent = profileLabels[key];
  $('engine-model').textContent = profileLabels[key];
  $('profile-hint').textContent = key === 'aerial' ? 'Recommended aerial detector. Trained on DOTA v1.' : key === 'aerial_large' ? 'Larger aerial model. May produce false positives on text or watermarks; review carefully.' : 'Legacy COCO detector. Can miss unusual overhead aircraft.';
  if (healthState) $('model-status').textContent = profile?.loaded ? 'Detector loaded and ready.' : profile?.cached ? 'Weights cached. Loads on next run.' : 'Model downloads on first use.';
}
$('model-profile').addEventListener('change', () => { updateProfile(); });
$('method-button').addEventListener('click', () => $('method-dialog').showModal());
document.querySelectorAll('.close-dialog').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => { if (event.target === dialog) { const rect = dialog.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close(); } }));
function updateClock() { $('clock').textContent = new Date().toLocaleTimeString([], { hour12: false }) + ' LOCAL'; }
updateClock(); setInterval(updateClock, 1000); checkHealth(); refreshHistory(); setInterval(checkHealth, 30000);
const requestedRun = new URLSearchParams(window.location.search).get('run');
if (requestedRun) openRun(requestedRun);
