'use strict';

const gameStatusText = document.getElementById('gameStatusText');
const statusDot = document.getElementById('statusDot');
const killGameBtn = document.getElementById('killGameBtn');
const playSoloBtn = document.getElementById('playSoloBtn');
const deployOnlyBtn = document.getElementById('deployOnlyBtn');
const withBotsBtn = document.getElementById('withBotsBtn');
const agentList = document.getElementById('agentList');
const logOutput = document.getElementById('logOutput');
const revealLogBtn = document.getElementById('revealLogBtn');
const repoLine = document.getElementById('repoLine');
const statusLine = document.getElementById('statusLine');
const subtitle = document.getElementById('subtitle');
const eyebrow = document.getElementById('eyebrow');
const locationSelect = document.getElementById('locationSelect');
const agentsBlurb = document.getElementById('agentsBlurb');

/** @type {ReturnType<typeof setInterval> | null} */
let pollTimer = null;
/** @type {string} */
let repoRoot = '';
/** @type {string} */
let currentLocation = 'g5';
/** @type {string} */
let currentLogPath = 'journal/agent_office/.last_launch.log';
/** Block double-clicks while a deploy/play script is running. */
let launchInFlight = false;

function setStatus(message, kind) {
  statusLine.textContent = message;
  statusLine.className = `status ${kind || ''}`.trim();
}

function setButtonsDisabled(disabled) {
  playSoloBtn.disabled = disabled;
  deployOnlyBtn.disabled = disabled;
  withBotsBtn.disabled = disabled;
}

function renderGameStatus(game) {
  const running = game.running && game.running.length > 0;
  if (running) {
    gameStatusText.textContent = `Game running (PID ${game.running.map((e) => e.pid).join(', ')})`;
    statusDot.className = 'status-dot running';
    killGameBtn.disabled = false;
  } else if (game.lastPid && game.lastAlive) {
    gameStatusText.textContent = `Game running (PID ${game.lastPid})`;
    statusDot.className = 'status-dot running';
    killGameBtn.disabled = false;
  } else {
    gameStatusText.textContent = game.binaryBuilt
      ? 'Ready — no game running'
      : 'Build missing: run make -j8 in repo root';
    statusDot.className = 'status-dot idle';
    killGameBtn.disabled = true;
  }

  const canLaunch = Boolean(game.binaryBuilt);
  playSoloBtn.disabled = !canLaunch;
  withBotsBtn.disabled = !canLaunch;
  deployOnlyBtn.disabled = false;
}

function renderAgents(layout) {
  agentList.innerHTML = '';
  const agents = layout?.agents || [];
  if (agents.length === 0) {
    agentList.innerHTML = '<li class="muted">No agent metadata loaded.</li>';
    return;
  }
  agents.forEach((agent) => {
    const li = document.createElement('li');
    const role = agent.role || agent.label;
    li.innerHTML = `
      <span class="agent-name">${role}</span>
      <span class="agent-meta">pad ${agent.padHex}${agent.facing ? ` · ${agent.facing}` : ''}</span>
    `;
    agentList.appendChild(li);
  });
}

function renderLocationOptions(locations, selected) {
  if (!locationSelect) return;
  locationSelect.innerHTML = '';
  (locations || []).forEach((entry) => {
    const option = document.createElement('option');
    option.value = entry.id;
    option.textContent = entry.label;
    if (entry.id === selected) option.selected = true;
    locationSelect.appendChild(option);
  });
}

async function refreshLog() {
  const tail = await window.virtualAgentOffice.tailLog(50, currentLocation);
  if (tail.ok) {
    logOutput.textContent = tail.lines || '(empty log)';
  }
}

async function refreshGameStatus() {
  const game = await window.virtualAgentOffice.getGameStatus(currentLocation);
  renderGameStatus(game);
}

async function refresh() {
  const info = await window.virtualAgentOffice.getInfo(currentLocation);
  repoRoot = info.repoRoot || '';
  currentLocation = info.location || currentLocation;
  currentLogPath = info.logPath || currentLogPath;
  repoLine.textContent = repoRoot || 'Repo root not resolved — set PD_REPO_ROOT';
  renderLocationOptions(info.locations, currentLocation);
  if (info.layout?.description) subtitle.textContent = info.layout.description;
  const active = (info.locations || []).find((entry) => entry.id === currentLocation);
  if (active?.eyebrow && eyebrow) eyebrow.textContent = active.eyebrow;
  if (agentsBlurb) {
    agentsBlurb.textContent =
      currentLocation === 'ci'
        ? 'Friendly NPCs in the CI pre-mission lobby (Y≈35) — open briefing circle, no doors needed.'
        : 'Friendly NPCs in the G5 pre-mission lobby — retail guard-foyer briefing ring.';
  }
  renderAgents(info.layout);
  renderGameStatus(info.game);
  await refreshLog();
}

async function launch(mode, label) {
  if (launchInFlight) {
    setStatus('Launch already in progress…', 'warn');
    return;
  }
  launchInFlight = true;
  setStatus(`Starting ${label}…`, '');
  setButtonsDisabled(true);
  let result;
  try {
    result = await window.virtualAgentOffice.launch(mode, currentLocation);
  } finally {
    launchInFlight = false;
    setButtonsDisabled(false);
  }
  if (!result.ok) {
    setStatus(result.error || 'Launch failed', 'error');
    return;
  }
  if (result.alreadyRunning) {
    setStatus(result.message || 'Game already running — use Quit Game first', 'warn');
    await refreshGameStatus();
    return;
  }
  if (mode === 'deploy-only') {
    setStatus('Deploy complete', 'ok');
  } else if (result.launchOk) {
    const note = result.launchNote ? ` — ${result.launchNote}` : '';
    setStatus(`${label} started — look for the Perfect Dark game window${note}`, 'ok');
  } else {
    setStatus(`${label} started (waiting for game process — check log)`, 'warn');
  }
  if (result.logTail?.ok) {
    logOutput.textContent = result.logTail.lines || '';
  }
  await refreshGameStatus();
}

playSoloBtn.addEventListener('click', () => launch('solo', 'Enter Office'));
deployOnlyBtn.addEventListener('click', () => launch('deploy-only', 'Deploy'));
withBotsBtn.addEventListener('click', () => launch('with-bots', 'Office with bots'));

killGameBtn.addEventListener('click', async () => {
  setStatus('Quitting game…', '');
  const result = await window.virtualAgentOffice.killGame(currentLocation);
  if (result.killed?.length) {
    setStatus(`Quit PID(s): ${result.killed.join(', ')}`, 'ok');
  } else {
    setStatus('No running game found', 'warn');
  }
  renderGameStatus(result.status);
});

revealLogBtn.addEventListener('click', async () => {
  if (!repoRoot) return;
  await window.virtualAgentOffice.revealPath(`${repoRoot}/${currentLogPath}`);
});

locationSelect?.addEventListener('change', async () => {
  currentLocation = locationSelect.value || 'g5';
  await refresh();
});

refresh().catch((err) => setStatus(String(err), 'error'));

pollTimer = setInterval(async () => {
  await refreshGameStatus();
  await refreshLog();
}, 4000);

window.addEventListener('beforeunload', () => {
  if (pollTimer) clearInterval(pollTimer);
});
