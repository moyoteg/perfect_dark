'use strict';

const WORKING_STAGES = new Set(['extracted', 'upgraded', 'encoded']);
let currentFilter = 'all';
let searchQuery = '';
let running = false;
/** @type {Array<object>} */
let visibleAssets = [];
let compareIndex = -1;

const els = {
  runBadge: document.getElementById('runBadge'),
  refreshBtn: document.getElementById('refreshBtn'),
  startBtn: document.getElementById('startBtn'),
  stopBtn: document.getElementById('stopBtn'),
  modPath: document.getElementById('modPath'),
  deployDir: document.getElementById('deployDir'),
  backend: document.getElementById('backend'),
  model: document.getElementById('model'),
  limit: document.getElementById('limit'),
  sleep: document.getElementById('sleep'),
  dryRun: document.getElementById('dryRun'),
  noResume: document.getElementById('noResume'),
  includeBase: document.getElementById('includeBase'),
  prompt: document.getElementById('prompt'),
  pickModBtn: document.getElementById('pickModBtn'),
  searchInput: document.getElementById('searchInput'),
  statTotal: document.getElementById('statTotal'),
  statDeployed: document.getElementById('statDeployed'),
  statWorking: document.getElementById('statWorking'),
  statFailed: document.getElementById('statFailed'),
  progressFill: document.getElementById('progressFill'),
  progressLabel: document.getElementById('progressLabel'),
  assetRows: document.getElementById('assetRows'),
  tableHint: document.getElementById('tableHint'),
  logView: document.getElementById('logView'),
  compareDialog: document.getElementById('compareDialog'),
  compareTitle: document.getElementById('compareTitle'),
  compareMeta: document.getElementById('compareMeta'),
  compareBefore: document.getElementById('compareBefore'),
  compareAfter: document.getElementById('compareAfter'),
  compareBeforeOverlay: document.getElementById('compareBeforeOverlay'),
  compareAfterOverlay: document.getElementById('compareAfterOverlay'),
  compareSlider: document.getElementById('compareSlider'),
  comparePrev: document.getElementById('comparePrev'),
  compareNext: document.getElementById('compareNext'),
  compareClose: document.getElementById('compareClose'),
};

function appendLog(line) {
  els.logView.textContent += `${line}\n`;
  els.logView.scrollTop = els.logView.scrollHeight;
}

function setRunning(next) {
  running = next;
  els.startBtn.disabled = next;
  els.stopBtn.disabled = !next;
  els.runBadge.textContent = next ? 'Running' : 'Idle';
  els.runBadge.className = `badge ${next ? 'running' : 'idle'}`;
}

function readForm() {
  return {
    modPath: els.modPath.value.trim(),
    deployDir: els.deployDir.value.trim(),
    backend: els.backend.value,
    model: els.model.value.trim(),
    limit: Number(els.limit.value) || 0,
    sleep: Number(els.sleep.value) || 0,
    dryRun: els.dryRun.checked,
    noResume: els.noResume.checked,
    includeBase: els.includeBase.checked,
    prompt: els.prompt.value.trim(),
  };
}

function applyConfig(config) {
  els.modPath.value = config.modPath || 'mods/mod_allinone';
  els.deployDir.value = config.deployDir || 'mods/mod_upgraded';
  els.backend.value = config.backend || 'local';
  
  // Set default model based on selected backend if model is empty or default
  if (config.model) {
    els.model.value = config.model;
  } else if (config.backend === 'mlx') {
    els.model.value = 'RealESRGAN_x4plus';
  } else if (config.backend === 'openai') {
    els.model.value = 'gpt-image-1';
  } else {
    els.model.value = '';
  }
  
  els.limit.value = config.limit || 0;
  els.sleep.value = config.sleep ?? 1;
  els.dryRun.checked = Boolean(config.dryRun);
  els.noResume.checked = Boolean(config.noResume);
  els.includeBase.checked = Boolean(config.includeBase);
  els.prompt.value = config.prompt || '';
  syncBackendFields();
}

function syncBackendFields() {
  const backend = els.backend.value;
  const openai = backend === 'openai';
  const mlx = backend === 'mlx';

  els.model.disabled = !openai && !mlx;
  els.sleep.disabled = !openai;
  els.prompt.disabled = !openai;

  // Auto-switch defaults when changing select input if using placeholder values
  if (mlx && (els.model.value === 'gpt-image-1' || !els.model.value)) {
    els.model.value = 'RealESRGAN_x4plus';
  } else if (openai && (els.model.value === 'RealESRGAN_x4plus' || !els.model.value)) {
    els.model.value = 'gpt-image-1';
  } else if (!openai && !mlx) {
    els.model.value = '';
  }
}

function stageClass(stage) {
  if (stage === 'failed') return 'failed';
  if (stage === 'deployed') return 'deployed';
  return '';
}

function fileUrl(absPath) {
  if (!absPath) return '';
  const normalized = absPath.replace(/\\/g, '/');
  return `file://${encodeURI(normalized)}?t=${Date.now()}`;
}

function thumbHtml(path, label, extraClass = '') {
  if (!path) return `<span class="thumb empty ${extraClass}" title="${label} missing">—</span>`;
  const src = fileUrl(path);
  return `<img class="thumb ${extraClass}" src="${src}" alt="${label}" title="Click row to compare" />`;
}

function filterAssets(assets) {
  const q = searchQuery.trim().toLowerCase();
  return (assets || []).filter((asset) => {
    if (currentFilter === 'failed' && asset.stage !== 'failed') return false;
    if (currentFilter === 'deployed' && asset.stage !== 'deployed') return false;
    if (currentFilter === 'working' && !WORKING_STAGES.has(asset.stage)) return false;
    if (!q) return true;
    const hay = `${asset.texture_id || ''} ${asset.key || ''} ${asset.mod_name || ''}`.toLowerCase();
    return hay.includes(q);
  });
}

function renderSnapshot(snapshot) {
  const byStage = snapshot.by_stage || {};
  const total = snapshot.total || 0;
  const deployed = byStage.deployed || 0;
  const failed = byStage.failed || 0;
  const working = (byStage.extracted || 0) + (byStage.upgraded || 0) + (byStage.encoded || 0);
  const done = deployed + failed;
  const pct = total ? Math.round((done / total) * 100) : 0;

  els.statTotal.textContent = String(total);
  els.statDeployed.textContent = String(deployed);
  els.statWorking.textContent = String(working);
  els.statFailed.textContent = String(failed);
  els.progressFill.style.width = `${pct}%`;
  els.progressLabel.textContent = total
    ? `${done}/${total} finished (${pct}%) — click any row for full comparison`
    : 'No catalog yet — start a run to scan textures.';

  visibleAssets = filterAssets(snapshot.assets);
  const maxRows = 500;
  const rows = visibleAssets.slice(0, maxRows);

  els.assetRows.innerHTML = rows.map((asset, index) => {
    const hasExtracted = asset.stage !== 'pending';
    const hasUpgraded = ['upgraded', 'encoded', 'deployed'].includes(asset.stage);
    const before = thumbHtml(hasExtracted ? asset.extracted_png : null, 'Original', 'original-rendering');
    const after = thumbHtml(hasUpgraded ? asset.upgraded_png : null, 'Enhanced', 'enhanced-rendering');
    return `<tr data-index="${index}" class="asset-row" tabindex="0">
      <td><code>${asset.texture_id || asset.key}</code></td>
      <td>${asset.mod_name || 'base'}</td>
      <td class="stage ${stageClass(asset.stage)}">${asset.stage || 'pending'}</td>
      <td class="thumb-cell">${before}</td>
      <td class="thumb-cell">${after}</td>
      <td>${asset.error ? `<span class="stage failed">${asset.error}</span>` : ''}</td>
    </tr>`;
  }).join('');

  if (visibleAssets.length > maxRows) {
    els.tableHint.textContent = `Showing first ${maxRows} of ${visibleAssets.length} matches. Narrow search to find more.`;
  } else if (visibleAssets.length === 0) {
    els.tableHint.textContent = total ? 'No textures match the current filter.' : '';
  } else {
    els.tableHint.textContent = `${visibleAssets.length} texture(s). Click a row to open side-by-side comparison.`;
  }

  els.assetRows.querySelectorAll('.asset-row').forEach((row) => {
    const open = () => openCompare(Number(row.dataset.index));
    row.addEventListener('click', open);
    row.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        open();
      }
    });
  });
}

function updateCompareSlider() {
  const pct = Number(els.compareSlider.value);
  els.compareAfterOverlay.style.clipPath = `inset(0 ${100 - pct}% 0 0)`;
}

function openCompare(index) {
  if (index < 0 || index >= visibleAssets.length) return;
  compareIndex = index;
  const asset = visibleAssets[index];
  const hasExtracted = asset.stage !== 'pending';
  const hasUpgraded = ['upgraded', 'encoded', 'deployed'].includes(asset.stage);
  const beforeSrc = hasExtracted ? fileUrl(asset.extracted_png) : '';
  const afterSrc = hasUpgraded ? fileUrl(asset.upgraded_png) : '';

  els.compareTitle.textContent = `Texture ${asset.texture_id || asset.key}`;
  els.compareMeta.textContent = [
    asset.mod_name || 'base',
    asset.stage || 'pending',
    asset.source_path || '',
  ].filter(Boolean).join(' · ');

  els.compareBefore.src = beforeSrc;
  els.compareAfter.src = afterSrc || beforeSrc;
  els.compareBeforeOverlay.src = beforeSrc;
  els.compareAfterOverlay.src = afterSrc || beforeSrc;
  els.compareBefore.style.display = beforeSrc ? 'block' : 'none';
  els.compareAfter.style.display = afterSrc ? 'block' : 'none';
  els.compareSlider.value = '50';
  updateCompareSlider();

  els.comparePrev.disabled = index <= 0;
  els.compareNext.disabled = index >= visibleAssets.length - 1;

  if (!els.compareDialog.open) els.compareDialog.showModal();
}

function closeCompare() {
  if (els.compareDialog.open) els.compareDialog.close();
}

async function init() {
  const config = await window.upgraderAPI.getConfig();
  applyConfig(config);
  const snapshot = await window.upgraderAPI.getSnapshot();
  renderSnapshot(snapshot);

  window.upgraderAPI.onLogLine(appendLog);
  window.upgraderAPI.onSnapshotUpdated(renderSnapshot);
  window.upgraderAPI.onRunState(({ running: isRunning }) => setRunning(isRunning));

  els.backend.addEventListener('change', syncBackendFields);

  els.refreshBtn.addEventListener('click', async () => {
    const options = readForm();
    await window.upgraderAPI.saveConfig(options);
    const next = await window.upgraderAPI.refreshSnapshot();
    renderSnapshot(next);
  });

  els.startBtn.addEventListener('click', async () => {
    const options = readForm();
    await window.upgraderAPI.saveConfig(options);
    appendLog('Starting pipeline…');
    const result = await window.upgraderAPI.startRun(options);
    if (!result.ok) appendLog(`Start failed: ${result.error}`);
  });

  els.stopBtn.addEventListener('click', async () => {
    await window.upgraderAPI.stopRun();
    appendLog('Stop requested.');
  });

  els.pickModBtn.addEventListener('click', async () => {
    const rel = await window.upgraderAPI.pickDirectory();
    if (rel) els.modPath.value = rel;
  });

  els.searchInput.addEventListener('input', () => {
    searchQuery = els.searchInput.value;
    window.upgraderAPI.getSnapshot().then(renderSnapshot);
  });

  document.querySelectorAll('.filter').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      window.upgraderAPI.getSnapshot().then(renderSnapshot);
    });
  });

  els.compareSlider.addEventListener('input', updateCompareSlider);
  els.comparePrev.addEventListener('click', () => openCompare(compareIndex - 1));
  els.compareNext.addEventListener('click', () => openCompare(compareIndex + 1));
  els.compareClose.addEventListener('click', closeCompare);
  els.compareDialog.addEventListener('click', (event) => {
    if (event.target === els.compareDialog) closeCompare();
  });
  els.compareDialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    closeCompare();
  });
}

init().catch((err) => appendLog(String(err)));
