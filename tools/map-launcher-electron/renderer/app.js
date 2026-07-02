'use strict';

const mapGrid = document.getElementById('mapGrid');
const gameStatusText = document.getElementById('gameStatusText');
const gameStatusDot = document.querySelector('.status-dot');
const killGameBtn = document.getElementById('killGameBtn');
const refreshBtn = document.getElementById('refreshBtn');
const logOutput = document.getElementById('logOutput');
const logPathLabel = document.getElementById('logPathLabel');
const revealLogBtn = document.getElementById('revealLogBtn');
const statusLine = document.getElementById('statusLine');
const actionOutput = document.getElementById('actionOutput');
const repoLine = document.getElementById('repoLine');
const kitVersionPill = document.getElementById('kitVersionPill');
const portVersionPill = document.getElementById('portVersionPill');
const appSubtitle = document.getElementById('appSubtitle');

const loopStatusText = document.getElementById('loopStatusText');
const loopLogOutput = document.getElementById('loopLogOutput');
const validationStepText = document.getElementById('validationStepText');
const runsList = document.getElementById('runsList');
const curriculumPhases = document.getElementById('curriculumPhases');
const curriculumCountNote = document.getElementById('curriculumCountNote');
const launcherCurriculumPhases = document.getElementById('launcherCurriculumPhases');
const launcherCurriculumCountNote = document.getElementById('launcherCurriculumCountNote');
const launcherCurriculumBadge = document.getElementById('launcherCurriculumBadge');
const learningCurriculumBadge = document.getElementById('learningCurriculumBadge');
const launcherTabBadge = document.getElementById('launcherTabBadge');
const learningTabBadge = document.getElementById('learningTabBadge');
const startLoopBtn = document.getElementById('startLoopBtn');
const stopLoopBtn = document.getElementById('stopLoopBtn');

/** @type {string | null} */
let currentLogPath = null;
/** @type {ReturnType<typeof setInterval> | null} */
let pollTimer = null;

function setStatus(message, kind) {
  statusLine.textContent = message;
  statusLine.className = `status ${kind || ''}`.trim();
}

function showActionOutput(text) {
  if (!text) {
    actionOutput.classList.add('hidden');
    actionOutput.textContent = '';
    return;
  }
  actionOutput.classList.remove('hidden');
  actionOutput.textContent = text;
}

function readCardOptions(card, mapDef) {
  const options = {};
  for (const opt of mapDef.options || []) {
    if (opt.type === 'checkbox') {
      const el = card.querySelector(`[data-opt="${opt.key}"]`);
      options[opt.key] = el ? el.checked : false;
    } else if (opt.type === 'number') {
      const el = card.querySelector(`[data-opt="${opt.key}"]`);
      const raw = el ? el.value : opt.default;
      options[opt.key] = parseInt(raw, 10);
    }
  }
  return options;
}

function renderOptions(mapDef) {
  if (!mapDef.options || mapDef.options.length === 0) {
    return '';
  }
  const rows = mapDef.options
    .map((opt) => {
      if (opt.type === 'checkbox') {
        return `
          <label class="option-row">
            <span>${opt.label}</span>
            <input type="checkbox" data-opt="${opt.key}" />
          </label>`;
      }
      if (opt.type === 'number') {
        return `
          <label class="option-row">
            <span>${opt.label}</span>
            <input type="number" data-opt="${opt.key}" value="${opt.default ?? 0}" min="${opt.min ?? 0}" max="${opt.max ?? 99}" />
          </label>`;
      }
      return '';
    })
    .join('');
  return `<div class="card-options">${rows}</div>`;
}

function mapCardBadges(mapDef) {
  const badges = [];
  if (mapDef.scriptExists) {
    badges.push(['Ready', 'ok']);
  } else {
    badges.push(['Script missing', 'warn']);
  }
  if (mapDef.jsonExists === false) {
    badges.push(['JSON missing', 'warn']);
  }
  return badges;
}

async function launchMapCard(mapDef, card, launchBtn) {
  const options = readCardOptions(card, mapDef);
  setStatus(`Launching ${mapDef.title}…`, '');
  showActionOutput('');
  launchBtn.disabled = true;
  const result = await window.pdMapLauncher.launchMap(mapDef.id, options);
  launchBtn.disabled = false;
  if (!result.ok) {
    setStatus(result.error || 'Launch failed', 'error');
    return;
  }
  setStatus(`${mapDef.title} started`, 'ok');
  if (result.logPath) {
    currentLogPath = result.logPath;
    logPathLabel.textContent = result.logPath;
    revealLogBtn.disabled = false;
  }
  if (result.logTail && result.logTail.ok) {
    logOutput.textContent = result.logTail.lines || '(empty log)';
  }
  await refreshGameStatus();
}

function bindWarColorsSimOptions(card) {
  const soloEl = card.querySelector('[data-opt="solo"]');
  const fullBattleEl = card.querySelector('[data-opt="fullBattle"]');
  const numSimsEl = card.querySelector('[data-opt="numSims"]');
  if (!soloEl || !fullBattleEl || !numSimsEl) return;

  const sync = () => {
    if (soloEl.checked) {
      fullBattleEl.checked = false;
      numSimsEl.value = '0';
      numSimsEl.disabled = true;
    } else if (fullBattleEl.checked) {
      soloEl.checked = false;
      numSimsEl.value = '50';
      numSimsEl.disabled = true;
    } else {
      numSimsEl.disabled = false;
      if (parseInt(numSimsEl.value, 10) < 1) {
        numSimsEl.value = '8';
      }
    }
  };

  soloEl.addEventListener('change', sync);
  fullBattleEl.addEventListener('change', sync);
  sync();
}

function attachLaunchCard(card, mapDef, gameBuilt) {
  const disabled =
    !mapDef.scriptExists ||
    mapDef.jsonExists === false ||
    (!gameBuilt && mapDef.id !== 'play-last-test-map');
  const badges = mapCardBadges(mapDef);
  const meta =
    mapDef.mapName && mapDef.scenarioLabel
      ? `<p class="card-meta"><code>${mapDef.mapName}</code> · ${mapDef.scenarioLabel}${mapDef.segMode ? ` · seg ${mapDef.segMode}` : ''}</p>`
      : '';
  card.innerHTML = `
    <h3>${mapDef.title}</h3>
    ${meta}
    <p>${mapDef.description}</p>
    ${renderOptions(mapDef)}
    <div class="card-footer">
      ${badges.map(([label, kind]) => `<span class="badge ${kind}">${label}</span>`).join('')}
      <button type="button" class="primary launch-btn" ${disabled ? 'disabled' : ''}>Launch</button>
    </div>
  `;
  const launchBtn = card.querySelector('.launch-btn');
  if (mapDef.id === 'war-colors-sentry') {
    bindWarColorsSimOptions(card);
  }
  launchBtn.addEventListener('click', () => launchMapCard(mapDef, card, launchBtn));
}

function renderMaps(maps, gameBuilt) {
  mapGrid.innerHTML = '';
  maps.forEach((mapDef) => {
    const card = document.createElement('article');
    card.className = 'card';
    card.dataset.mapId = mapDef.id;
    attachLaunchCard(card, mapDef, gameBuilt);
    mapGrid.appendChild(card);
  });
}

function updateCurriculumBadges(curriculum) {
  const badges = [launcherTabBadge, learningTabBadge, launcherCurriculumBadge, learningCurriculumBadge];
  if (!curriculum || curriculum.totalCount === 0) {
    badges.forEach((el) => {
      if (el) el.classList.add('hidden');
    });
    return;
  }

  const label = `${curriculum.totalCount} map${curriculum.totalCount === 1 ? '' : 's'}`;
  if (launcherTabBadge) {
    launcherTabBadge.textContent = String(curriculum.totalCount);
    launcherTabBadge.classList.toggle('warn', !curriculum.complete);
    launcherTabBadge.classList.remove('hidden');
  }
  if (learningTabBadge) {
    learningTabBadge.textContent = String(curriculum.totalCount);
    learningTabBadge.classList.toggle('warn', !curriculum.complete);
    learningTabBadge.classList.remove('hidden');
  }
  for (const el of [launcherCurriculumBadge, learningCurriculumBadge]) {
    if (!el) continue;
    el.textContent = label;
    el.classList.toggle('warn', !curriculum.complete);
    el.classList.remove('hidden');
  }
}

function renderCurriculum(curriculum, gameBuilt, containerEl, countNoteEl) {
  if (!containerEl) return;
  containerEl.innerHTML = '';
  if (!curriculum || !curriculum.phases || curriculum.phases.length === 0 || curriculum.totalCount === 0) {
    if (countNoteEl) {
      countNoteEl.textContent = 'No curriculum steps found — run pdmap learn curriculum generate';
    }
    return;
  }

  const countText = `${curriculum.totalCount} / ${curriculum.expectedCount} curriculum steps`;
  if (countNoteEl) {
    countNoteEl.textContent = curriculum.complete
      ? `${countText} — grouped by phase; deploy via play-learn-step.sh into the uff test slot`
      : `${countText} (incomplete — expected ${curriculum.expectedCount})`;
  }

  curriculum.phases.forEach((phase) => {
    if (!phase.steps || phase.steps.length === 0) return;
    const section = document.createElement('section');
    section.className = 'curriculum-phase';
    section.dataset.phaseId = phase.id;
    section.innerHTML = `
      <div class="phase-head">
        <h3>${phase.title}</h3>
        <span class="phase-count">${phase.steps.length} step${phase.steps.length === 1 ? '' : 's'}</span>
      </div>
      <div class="grid curriculum-grid"></div>
    `;
    const grid = section.querySelector('.curriculum-grid');
    phase.steps.forEach((mapDef) => {
      const card = document.createElement('article');
      card.className = 'card card-compact';
      card.dataset.mapId = mapDef.id;
      attachLaunchCard(card, mapDef, gameBuilt);
      grid.appendChild(card);
    });
    containerEl.appendChild(section);
  });
}

function renderAllCurriculum(curriculum, gameBuilt) {
  updateCurriculumBadges(curriculum);
  renderCurriculum(curriculum, gameBuilt, launcherCurriculumPhases, launcherCurriculumCountNote);
  renderCurriculum(curriculum, gameBuilt, curriculumPhases, curriculumCountNote);
}

function renderGameStatus(game) {
  const running = game.running && game.running.length > 0;
  if (running) {
    const pids = game.running.map((e) => e.pid).join(', ');
    gameStatusText.textContent = `Running pd.arm64 (PID ${pids})`;
    gameStatusDot.className = 'status-dot running';
    killGameBtn.disabled = false;
  } else if (game.lastPid && game.lastAlive) {
    gameStatusText.textContent = `Last launch PID ${game.lastPid} (running)`;
    gameStatusDot.className = 'status-dot running';
    killGameBtn.disabled = false;
  } else {
    gameStatusText.textContent = game.binaryBuilt
      ? 'No game running'
      : `Binary missing: build/pd.arm64 — run make -j8`;
    gameStatusDot.className = 'status-dot idle';
    killGameBtn.disabled = true;
  }
}

function renderLearnStatus(learn) {
  loopStatusText.textContent = learn.loopAlive
    ? `Learn loop running (PID ${learn.loopPid})`
    : 'Learn loop stopped';
  stopLoopBtn.disabled = !learn.loopAlive;
  startLoopBtn.disabled = learn.loopAlive;

  validationStepText.textContent = learn.validationStep
    ? `Validation step: ${learn.validationStep}`
    : 'Validation step: 0 (default)';

  const logParts = [];
  if (learn.loopLog) logParts.push(`loop.log:\n${learn.loopLog}`);
  if (learn.internalLog) logParts.push(`internal:\n${learn.internalLog}`);
  loopLogOutput.textContent = logParts.join('\n\n') || '(no loop log yet)';

  runsList.innerHTML = '';
  if (!learn.recentRuns || learn.recentRuns.length === 0) {
    runsList.innerHTML = '<p class="muted">No learn runs yet.</p>';
    return;
  }

  learn.recentRuns.forEach((run) => {
    const s = run.summary || {};
    const card = document.createElement('article');
    card.className = 'run-card';
    card.innerHTML = `
      <header>
        <strong>${s.run_id || run.file}</strong>
        <span class="run-meta">${run.mtime}</span>
      </header>
      <div class="run-stats">
        <span>iteration: ${s.iteration ?? '—'}</span>
        <span>facts: +${s.facts_added ?? 0} / ${s.facts_total ?? '—'}</span>
        <span>coverage: ${s.doc_coverage_ratio != null ? `${Math.round(s.doc_coverage_ratio * 100)}%` : '—'}</span>
        <span>gaps: ${Array.isArray(s.gaps) ? s.gaps.length : '—'}</span>
      </div>
    `;
    runsList.appendChild(card);
  });
}

async function refreshGameStatus() {
  const game = await window.pdMapLauncher.getGameStatus();
  renderGameStatus(game);
  return game;
}

async function refreshLogTail() {
  if (!currentLogPath) return;
  const tail = await window.pdMapLauncher.tailLog(currentLogPath, 40);
  if (tail.ok) {
    logOutput.textContent = tail.lines || '(empty log)';
  }
}

async function refresh() {
  const info = await window.pdMapLauncher.getInfo();
  kitVersionPill.textContent = `Kit v${info.kitVersion}`;
  portVersionPill.textContent = `Port v${info.portVersion}`;
  repoLine.textContent = info.repoRoot || 'Repo root not resolved — set PD_REPO_ROOT';
  appSubtitle.textContent = info.game.binaryBuilt
    ? 'Launch test maps and manage the map learn curriculum.'
    : 'Build build/pd.arm64 first to enable map launches.';
  renderMaps(info.maps, info.game.binaryBuilt);
  renderAllCurriculum(info.curriculum, info.game.binaryBuilt);
  renderGameStatus(info.game);
  renderLearnStatus(info.learn);
}

// Tabs
document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => {
      t.classList.remove('active');
      t.setAttribute('aria-selected', 'false');
    });
    document.querySelectorAll('.tab-panel').forEach((panel) => {
      panel.hidden = true;
      panel.classList.remove('active');
    });
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    const target = document.getElementById(`tab-${tab.dataset.tab}`);
    if (target) {
      target.hidden = false;
      target.classList.add('active');
    }
  });
});

killGameBtn.addEventListener('click', async () => {
  setStatus('Killing game…', '');
  const result = await window.pdMapLauncher.killGame();
  if (result.killed && result.killed.length) {
    setStatus(`Killed PID(s): ${result.killed.join(', ')}`, 'ok');
  } else {
    setStatus('No running game found', 'warn');
  }
  renderGameStatus(result.status);
});

refreshBtn.addEventListener('click', async () => {
  setStatus('Refreshing…', '');
  await refresh();
  await refreshLogTail();
  setStatus('Refreshed', 'ok');
});

revealLogBtn.addEventListener('click', async () => {
  if (!currentLogPath) return;
  const info = await window.pdMapLauncher.getInfo();
  const full = `${info.repoRoot}/${currentLogPath}`;
  await window.pdMapLauncher.revealPath(full);
});

startLoopBtn.addEventListener('click', async () => {
  setStatus('Starting learn loop…', '');
  const result = await window.pdMapLauncher.startLearnLoop();
  if (!result.ok) {
    setStatus(result.error || 'Failed to start loop', 'error');
    return;
  }
  setStatus(result.alreadyRunning ? 'Learn loop already running' : 'Learn loop started', 'ok');
  const learn = await window.pdMapLauncher.getLearnStatus();
  renderLearnStatus(learn);
});

stopLoopBtn.addEventListener('click', async () => {
  setStatus('Stopping learn loop…', '');
  const result = await window.pdMapLauncher.stopLearnLoop();
  if (!result.ok) {
    setStatus(result.error || 'Failed to stop loop', 'error');
    return;
  }
  setStatus(result.stopped ? `Stopped PID ${result.pid}` : result.message || 'Loop not running', 'ok');
  const learn = await window.pdMapLauncher.getLearnStatus();
  renderLearnStatus(learn);
});

async function runLearnAction(action, label) {
  setStatus(`Running ${label}…`, '');
  showActionOutput('');
  const result = await window.pdMapLauncher.runLearnAction(action);
  if (!result.ok) {
    setStatus(`${label} failed (${result.code ?? 'error'})`, 'error');
    if (result.output) showActionOutput(result.output);
    return;
  }
  setStatus(`${label} completed`, 'ok');
  if (result.output) showActionOutput(result.output);
  const learn = await window.pdMapLauncher.getLearnStatus();
  renderLearnStatus(learn);
}

document.getElementById('validateStatusBtn').addEventListener('click', () => runLearnAction('validateStatus', 'Validation status'));
document.getElementById('validateListBtn').addEventListener('click', () => runLearnAction('validateList', 'Validation list'));
document.getElementById('pdmapValidateBtn').addEventListener('click', () => runLearnAction('pdmapValidate', 'pdmap validate'));
document.getElementById('curriculumGenBtn').addEventListener('click', () => runLearnAction('pdmapCurriculumGenerate', 'Curriculum generate'));
document.getElementById('learnRunBtn').addEventListener('click', () => runLearnAction('pdmapLearnRun', 'pdmap learn run'));

document.querySelectorAll('.doc-link').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const doc = btn.getAttribute('data-doc');
    const result = await window.pdMapLauncher.openDoc(doc);
    if (!result.ok) setStatus(result.error || 'Could not open doc', 'error');
  });
});

refresh().catch((err) => setStatus(String(err), 'error'));

pollTimer = setInterval(async () => {
  await refreshGameStatus();
  await refreshLogTail();
}, 4000);

window.addEventListener('beforeunload', () => {
  if (pollTimer) clearInterval(pollTimer);
});
