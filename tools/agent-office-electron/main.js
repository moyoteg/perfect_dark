'use strict';

/**
 * Virtual Agent Office — one-click deploy + launch for the dataDyne G5 agent sim map.
 */

const { app, BrowserWindow, ipcMain, shell, nativeImage } = require('electron');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function requireKitPaths() {
  const candidates = [
    path.join(__dirname, '../pd_kit/electron_paths.js'),
    path.join(__dirname, '../../tools/pd_kit/electron_paths.js'),
    path.join(process.resourcesPath || '', 'pd_kit', 'electron_paths.js'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return require(candidate);
    }
  }
  throw new Error('Perfect Dark Kit paths module not found');
}

const kitPaths = requireKitPaths();
const { bindSingleInstance } = kitPaths.requireKitModule('electron_single_instance.js');

const APP_TITLE = 'Virtual Agent Office';
const LOG_FILE_NAME = 'virtual-agent-office.log';
const DEPLOY_LOG = 'journal/agent_office/.last_launch.log';
const DIRECTOR_SCRIPT = 'scripts/start-agent-office-director.sh';
const DIRECTOR_LOG = 'journal/agent_office/office_director.log';
const DIRECTOR_PID = 'journal/agent_office/.office_director.pid';

/** @type {Record<string, { id: string, label: string, eyebrow: string, bootStage: string, script: string, logDir: string, deployLog: string, pidFile: string, mapName: string, layoutImport: string }>} */
const LOCATIONS = {
  g5: {
    id: 'g5',
    label: 'dataDyne G5 Building',
    eyebrow: 'Perfect Dark · dataDyne G5',
    bootStage: '0x83',
    script: 'scripts/play-agent-office.sh',
    logDir: 'journal/agent_office',
    deployLog: 'journal/agent_office/.last_launch.log',
    pidFile: 'journal/agent_office/.last_play.pid',
    mapName: 'agent_office',
    layoutImport: 'from tools.pdmap.agent_office import agent_office_layout_payload',
  },
  ci: {
    id: 'ci',
    label: 'Carrington Institute',
    eyebrow: 'Perfect Dark · Carrington Institute',
    bootStage: '0x84',
    script: 'scripts/play-agent-office-ci.sh',
    logDir: 'journal/agent_office_ci',
    deployLog: 'journal/agent_office_ci/.last_launch.log',
    pidFile: 'journal/agent_office_ci/.last_play.pid',
    mapName: 'agent_office_ci',
    layoutImport: 'from tools.pdmap.agent_office_ci import agent_office_ci_layout_payload',
  },
};

/** @type {import('electron').NativeImage | null} */
let appIcon = null;
/** @type {BrowserWindow | null} */
let mainWindow = null;
let pendingFocus = false;
/** @type {string} */
let repoRoot = '';
/** @type {string} */
let logFile = '';
/** Prevent overlapping deploy/play script spawns (one in flight per location+mode). */
const launchInFlight = new Set();

function log(...args) {
  const line = `[${new Date().toISOString().slice(0, 19).replace('T', ' ')}] [agent-office] ${args.join(' ')}`;
  try {
    if (logFile) {
      fs.mkdirSync(path.dirname(logFile), { recursive: true });
      fs.appendFileSync(logFile, `${line}\n`, 'utf8');
    }
  } catch {
    // ignore
  }
  console.log(line);
}

function configureAppIdentity() {
  app.setName(APP_TITLE);
  if (process.platform === 'darwin') {
    app.setAboutPanelOptions({
      applicationName: APP_TITLE,
      applicationVersion: app.getVersion(),
      version: app.getVersion(),
    });
  }
}

configureAppIdentity();

function normalizeRepoRoot(raw) {
  if (!raw) return '';
  return raw.trim().replace(/\/Library\/MobileDocuments\//g, '/Library/Mobile Documents/');
}

function readBakedRepoRoot() {
  const candidates = [
    path.join(__dirname, 'repo-config.json'),
    path.join(process.resourcesPath || '', 'repo-config.json'),
    path.join(process.resourcesPath || '', 'repo_root.txt'),
  ];
  for (const cfgPath of candidates) {
    try {
      if (!fs.existsSync(cfgPath)) continue;
      if (cfgPath.endsWith('.json')) {
        const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
        return normalizeRepoRoot(cfg.repoRoot || '');
      }
      return normalizeRepoRoot(fs.readFileSync(cfgPath, 'utf8'));
    } catch {
      // try next
    }
  }
  return '';
}

function discoverRepoRoot(startDir) {
  let candidate = path.resolve(startDir);
  for (let i = 0; i < 14; i += 1) {
    if (fs.existsSync(path.join(candidate, 'tools', 'pd_kit', 'kit.json'))) {
      return candidate;
    }
    const parent = path.dirname(candidate);
    if (parent === candidate) break;
    candidate = parent;
  }
  return '';
}

function resolveRepoRoot() {
  const fromEnv = normalizeRepoRoot(process.env.PD_REPO_ROOT || '');
  if (fromEnv && fs.existsSync(fromEnv)) return fromEnv;
  const baked = readBakedRepoRoot();
  if (baked && fs.existsSync(baked)) return baked;
  const fromExe = discoverRepoRoot(path.dirname(app.getPath('exe')));
  if (fromExe) return fromExe;
  return discoverRepoRoot(__dirname) || discoverRepoRoot(process.cwd());
}

function resolveAppIconCandidates() {
  const candidates = [
    path.join(__dirname, 'assets', 'agent-office-1024.png'),
    path.join(__dirname, 'assets', 'AgentOfficeAppIcon.icns'),
    path.join(__dirname, 'build', 'icon.icns'),
  ];
  if (repoRoot) {
    candidates.push(path.join(repoRoot, '.tmp-map-editor-app-build', 'agent-office-1024.png'));
    candidates.push(path.join(repoRoot, '.tmp-map-editor-app-build', 'AgentOfficeAppIcon.icns'));
  }
  return candidates;
}

function applyAppIcon() {
  for (const candidate of resolveAppIconCandidates()) {
    if (!fs.existsSync(candidate)) continue;
    const image = nativeImage.createFromPath(candidate);
    if (image.isEmpty()) continue;
    appIcon = image;
    if (process.platform === 'darwin' && app.dock) {
      app.dock.setIcon(image);
    }
    log(`App icon loaded: ${candidate}`);
    return;
  }
  log(`WARNING: no readable app icon under ${path.join(__dirname, 'assets')}`);
}

function gameBinaryPath() {
  return path.join(repoRoot, 'build', 'pd.arm64');
}

function resolveScript(scriptRel) {
  const normalized = path.normalize(scriptRel);
  if (normalized.includes('..') || !normalized.startsWith('scripts/')) {
    return null;
  }
  const full = path.join(repoRoot, normalized);
  if (!fs.existsSync(full)) return null;
  return full;
}

function readVersionFile(fileName) {
  try {
    return fs.readFileSync(path.join(repoRoot, fileName), 'utf8').trim();
  } catch {
    return '0.0.0';
  }
}

function normalizeLocation(raw) {
  const key = String(raw || 'g5').trim().toLowerCase();
  return LOCATIONS[key] ? key : 'g5';
}

function loadOfficeLayout(locationKey) {
  const loc = LOCATIONS[normalizeLocation(locationKey)];
  const fn = loc.id === 'g5' ? 'agent_office_layout_payload' : 'agent_office_ci_layout_payload';
  const py = `
import json
${loc.layoutImport}
print(json.dumps(${fn}()))
`;
  try {
    const raw = execFileSync('python3', ['-c', py], {
      cwd: repoRoot,
      encoding: 'utf8',
      env: { ...process.env, PD_REPO_ROOT: repoRoot },
      maxBuffer: 256 * 1024,
    });
    return JSON.parse(raw.trim());
  } catch (err) {
    log(`Layout payload failed (${loc.id}): ${err}`);
    return {
      label: loc.label,
      description: `${loc.label} — AI agents in a briefing room`,
      agents: [],
    };
  }
}

/** Strip Electron/Chromium vars so child bash + pd.arm64 inherit a clean GUI env on macOS. */
function buildGameLaunchEnv() {
  const env = { ...process.env, PD_REPO_ROOT: repoRoot };
  const stripPrefixes = ['ELECTRON_', 'CHROME_', 'VSCODE_', 'CURSOR_'];
  for (const key of Object.keys(env)) {
    if (stripPrefixes.some((prefix) => key.startsWith(prefix))) {
      delete env[key];
    }
  }
  delete env.ELECTRON_RUN_AS_NODE;
  return env;
}

function runScript(scriptRel, args) {
  const scriptPath = resolveScript(scriptRel);
  if (!scriptPath) {
    return Promise.resolve({ ok: false, error: `Script not found: ${scriptRel}` });
  }

  return new Promise((resolve) => {
    const child = spawn('/bin/bash', [scriptPath, ...(args || [])], {
      cwd: repoRoot,
      env: buildGameLaunchEnv(),
      detached: true,
      stdio: 'ignore',
    });
    child.unref();
    log(`Started ${scriptRel} ${(args || []).join(' ')} pid=${child.pid}`);
    resolve({ ok: true, pid: child.pid, detached: true });
  });
}

function isProcessAlive(pid) {
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function findGamePids(bootStage) {
  const binary = gameBinaryPath();
  const pids = [];
  try {
    const raw = execFileSync('pgrep', ['-x', 'pd.arm64'], { encoding: 'utf8' });
    for (const line of raw.split('\n')) {
      const pid = parseInt(line.trim(), 10);
      if (!Number.isFinite(pid)) continue;
      try {
        const cmd = execFileSync('ps', ['-p', String(pid), '-o', 'command='], { encoding: 'utf8' }).trim();
        if (cmd.includes(binary) && cmd.includes('--boot-stage') && cmd.includes(bootStage)) {
          pids.push({ pid, command: cmd.slice(0, 200) });
        }
      } catch {
        // skip
      }
    }
  } catch {
    // no processes
  }
  return pids;
}

function readPidFile(relativePath) {
  try {
    const raw = fs.readFileSync(path.join(repoRoot, relativePath), 'utf8').trim();
    const pid = parseInt(raw, 10);
    return Number.isFinite(pid) ? pid : null;
  } catch {
    return null;
  }
}

function getGameStatus(locationKey) {
  const loc = LOCATIONS[normalizeLocation(locationKey)];
  const lastPid = readPidFile(loc.pidFile);
  const running = findGamePids(loc.bootStage);
  const lastAlive = isProcessAlive(lastPid);
  return {
    location: loc.id,
    lastPid,
    lastAlive,
    running,
    binary: gameBinaryPath(),
    binaryBuilt: fs.existsSync(gameBinaryPath()),
  };
}

function directorScriptPath() {
  return path.join(repoRoot, DIRECTOR_SCRIPT);
}

function directorPythonPath() {
  return path.join(repoRoot, 'tools', 'agent_office_llm', 'office_director.py');
}

function findDirectorPids() {
  const script = directorPythonPath();
  const pids = [];
  try {
    const raw = execFileSync('pgrep', ['-f', 'office_director.py'], { encoding: 'utf8' });
    for (const line of raw.split('\n')) {
      const pid = parseInt(line.trim(), 10);
      if (!Number.isFinite(pid)) continue;
      try {
        const cmd = execFileSync('ps', ['-p', String(pid), '-o', 'command='], { encoding: 'utf8' }).trim();
        if (cmd.includes(script)) {
          pids.push({ pid, command: cmd.slice(0, 200) });
        }
      } catch {
        // skip
      }
    }
  } catch {
    // no director process
  }
  return pids;
}

function getDirectorStatus() {
  const lastPid = readPidFile(DIRECTOR_PID);
  const running = findDirectorPids();
  return {
    lastPid,
    lastAlive: isProcessAlive(lastPid),
    running,
    script: directorScriptPath(),
    scriptExists: fs.existsSync(directorScriptPath()),
    logPath: DIRECTOR_LOG,
  };
}

async function startDirector() {
  const status = getDirectorStatus();
  const alreadyRunning = Boolean(
    (status.lastPid && status.lastAlive) ||
      (status.running && status.running.length > 0),
  );
  if (alreadyRunning) {
    return { ok: true, alreadyRunning: true, status };
  }
  const result = await runScript(DIRECTOR_SCRIPT, []);
  await new Promise((r) => setTimeout(r, 1500));
  return {
    ...result,
    status: getDirectorStatus(),
    logTail: tailLog(DIRECTOR_LOG, 40, 'office_director'),
  };
}

function stopDirector() {
  const status = getDirectorStatus();
  const killed = [];
  const pids = new Set();
  if (status.lastPid && status.lastAlive) pids.add(status.lastPid);
  for (const entry of status.running) pids.add(entry.pid);

  for (const pid of pids) {
    try {
      process.kill(pid, 'SIGTERM');
      killed.push(pid);
    } catch {
      // ignore
    }
  }

  try {
    fs.unlinkSync(path.join(repoRoot, DIRECTOR_PID));
  } catch {
    // ignore stale/missing pid file
  }
  log(`Stop director pids: ${killed.join(', ') || '(none)'}`);
  return { ok: true, killed, status: getDirectorStatus() };
}

/** macOS OpenGL init often logs compat-profile misses before 4.1 core succeeds. */
function classifyLaunchLog(content, mapName) {
  const text = content || '';
  const hasGlCompatNoise =
    text.includes('could not create GL3.0 context') ||
    text.includes('GL: using core profile or ES');
  const hasGamePid = /Game PID \d+/.test(text);
  const hasDeployComplete =
    text.includes('Deploy complete') ||
    text.includes(`Build complete for ${mapName}`);
  return {
    hasGlCompatNoise,
    hasGamePid,
    hasDeployComplete,
    likelyBenignGlWarnings: hasGlCompatNoise && hasGamePid,
  };
}

function tailLog(relativePath, lineCount, mapName) {
  const count = Math.min(Math.max(lineCount || 40, 1), 500);
  const fullPath = path.join(repoRoot, relativePath || '');
  if (!fullPath.startsWith(repoRoot) || !fs.existsSync(fullPath)) {
    return { ok: false, error: 'Log file not found', path: relativePath };
  }
  try {
    const content = fs.readFileSync(fullPath, 'utf8');
    const lines = content.split('\n');
    return {
      ok: true,
      path: relativePath,
      lines: lines.slice(-count).join('\n'),
      size: content.length,
      launchHints: classifyLaunchLog(content, mapName),
    };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

function killGame(locationKey) {
  const status = getGameStatus(locationKey);
  const killed = [];

  if (status.lastPid && status.lastAlive) {
    try {
      process.kill(status.lastPid, 'SIGTERM');
      killed.push(status.lastPid);
    } catch {
      // ignore
    }
  }

  for (const entry of status.running) {
    if (killed.includes(entry.pid)) continue;
    try {
      process.kill(entry.pid, 'SIGTERM');
      killed.push(entry.pid);
    } catch {
      // ignore
    }
  }

  log(`Kill game pids: ${killed.join(', ') || '(none)'}`);
  return { ok: true, killed, status: getGameStatus(locationKey) };
}

function registerIpc() {
  ipcMain.handle('office:get-info', (_event, locationKey) => {
    const location = normalizeLocation(locationKey);
    const loc = LOCATIONS[location];
    return {
      title: APP_TITLE,
      kitVersion: readVersionFile('KIT_VERSION'),
      portVersion: readVersionFile('PORT_VERSION'),
      repoRoot,
      location,
      locations: Object.values(LOCATIONS).map((entry) => ({
        id: entry.id,
        label: entry.label,
        eyebrow: entry.eyebrow,
        bootStage: entry.bootStage,
      })),
      game: getGameStatus(location),
      director: getDirectorStatus(),
      layout: loadOfficeLayout(location),
      logPath: loc.deployLog,
    };
  });

  ipcMain.handle('office:launch', async (_event, mode, locationKey) => {
    const location = normalizeLocation(locationKey);
    const loc = LOCATIONS[location];
    const launchKey = `${location}:${mode}`;

    if (launchInFlight.has(launchKey)) {
      return { ok: false, error: 'Launch already in progress — wait for deploy to finish.' };
    }

    if (!fs.existsSync(gameBinaryPath()) && mode !== 'deploy-only') {
      return { ok: false, error: `Game binary missing: ${gameBinaryPath()}. Run make -j8 first.` };
    }

    // Never auto-relaunch: if the game is already alive for this map, require Quit first.
    if (mode !== 'deploy-only') {
      const existing = getGameStatus(location);
      const alreadyRunning = Boolean(
        (existing.lastPid && existing.lastAlive) ||
          (existing.running && existing.running.length > 0),
      );
      if (alreadyRunning) {
        const pid =
          existing.running?.[0]?.pid ||
          (existing.lastAlive ? existing.lastPid : null);
        return {
          ok: true,
          alreadyRunning: true,
          game: existing,
          error: undefined,
          message: `Game already running (PID ${pid}). Use Quit Game before launching again.`,
        };
      }
    }

    const args = [];
    if (mode === 'deploy-only') args.push('--no-play');
    if (mode === 'with-bots') args.push('--with-bots');

    launchInFlight.add(launchKey);
    log(`Launch location=${location} mode=${mode} args=${args.join(' ')}`);
    let result;
    try {
      result = await runScript(loc.script, args);
      if (!result.ok) return result;

      await new Promise((r) => setTimeout(r, 6000));
      const game = getGameStatus(location);
      const logTail = tailLog(loc.deployLog, 40, loc.mapName);
      const launchHints = logTail.launchHints || {};
      const gameRunning = Boolean(
        (game.lastPid && game.lastAlive) || (game.running && game.running.length > 0),
      );
      return {
        ...result,
        game,
        logTail,
        launchOk: gameRunning || launchHints.hasDeployComplete,
        launchNote: launchHints.likelyBenignGlWarnings
          ? 'macOS OpenGL: GL3.0 compat warnings are normal; game uses 4.1 core profile.'
          : undefined,
      };
    } finally {
      // Deploy can take 30–90s; keep the guard up long enough to block double-clicks.
      setTimeout(() => launchInFlight.delete(launchKey), 120000);
    }
  });

  ipcMain.handle('office:kill-game', (_event, locationKey) => killGame(locationKey));
  ipcMain.handle('office:game-status', (_event, locationKey) => getGameStatus(locationKey));
  ipcMain.handle('office:start-director', () => startDirector());
  ipcMain.handle('office:stop-director', () => stopDirector());
  ipcMain.handle('office:director-status', () => getDirectorStatus());
  ipcMain.handle('office:tail-director-log', (_event, lines) => tailLog(DIRECTOR_LOG, lines, 'office_director'));
  ipcMain.handle('office:tail-log', (_event, lines, locationKey) => {
    const loc = LOCATIONS[normalizeLocation(locationKey)];
    return tailLog(loc.deployLog, lines, loc.mapName);
  });

  ipcMain.handle('office:reveal-path', async (_event, targetPath) => {
    const resolved = path.isAbsolute(targetPath) ? targetPath : path.join(repoRoot, targetPath);
    if (!fs.existsSync(resolved)) {
      return { ok: false, error: 'Path not found' };
    }
    shell.showItemInFolder(resolved);
    return { ok: true };
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 720,
    height: 820,
    minWidth: 560,
    minHeight: 640,
    title: APP_TITLE,
    icon: appIcon || undefined,
    backgroundColor: '#0a1018',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.on('page-title-updated', (event) => {
    event.preventDefault();
    mainWindow.setTitle(APP_TITLE);
  });

  mainWindow.once('ready-to-show', () => focusMainWindow());
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

function focusMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    createWindow();
    return;
  }
  if (mainWindow.isMinimized()) mainWindow.restore();
  if (!mainWindow.isVisible()) mainWindow.center();
  mainWindow.show();
  mainWindow.focus();
  if (process.platform === 'darwin') {
    if (app.dock) app.dock.show();
    app.focus({ steal: true });
  }
}

function requestFocusMainWindow() {
  if (!app.isReady()) {
    pendingFocus = true;
    return;
  }
  focusMainWindow();
}

if (!bindSingleInstance(app, requestFocusMainWindow)) {
  process.exit(0);
}

app.whenReady().then(() => {
  repoRoot = resolveRepoRoot();
  logFile = path.join(app.getPath('home'), 'Library', 'Logs', 'PerfectDarkKit', LOG_FILE_NAME);
  applyAppIcon();
  if (repoRoot) {
    log(`REPO_ROOT=${repoRoot}`);
  } else {
    log('WARNING: repo root not resolved');
  }
  registerIpc();
  createWindow();
  if (pendingFocus) {
    pendingFocus = false;
    focusMainWindow();
  }
});

app.on('activate', () => focusMainWindow());
app.on('window-all-closed', () => app.quit());
