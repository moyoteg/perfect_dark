'use strict';

/**
 * Electron shell for the Perfect Dark Animation Lab.
 * Spawns serve_animlab.py and loads the lab UI in an embedded BrowserWindow.
 */

const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const path = require('path');

function requireKitPaths() {
  const candidates = [
    path.join(__dirname, '../../../tools/pd_kit/electron_paths.js'),
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

const APP_TITLE = kitPaths.appConfig('animLab').productName;
const LOG_FILE = kitPaths.kitLogFile(app.getPath('home'), 'animLab');
const DEFAULT_HOST = '127.0.0.1';
const PORT_MIN = 8776;
const PORT_MAX = 8795;
const SERVE_MARKER = path.join('journal', 'anim_lab', 'serve_animlab.py');
const BUNDLED_SUBDIR = 'anim-lab';

/** @type {import('child_process').ChildProcess | null} */
let serverProcess = null;
/** @type {BrowserWindow | null} */
let mainWindow = null;
/** @type {string} */
let activePort = '';
/** @type {boolean} */
let quitting = false;
/** @type {number} */
let restartAttempts = 0;
/** @type {{ pythonBin: string, serveScript: string, repoRoot: string, stateDir: string, bundleDir: string } | null} */
let serverContext = null;

const MAX_RESTART_ATTEMPTS = 3;

function log(...args) {
  const line = `[${new Date().toISOString().slice(0, 19).replace('T', ' ')}] [electron] ${args.join(' ')}`;
  try {
    fs.mkdirSync(path.dirname(LOG_FILE), { recursive: true });
    fs.appendFileSync(LOG_FILE, `${line}\n`, 'utf8');
  } catch {
    // ignore
  }
  console.log(line);
}

function normalizeRepoRoot(raw) {
  if (!raw) return '';
  let p = raw.trim();
  if (p.includes('/Library/MobileDocuments/')) {
    p = p.replace(/\/Library\/MobileDocuments\//g, '/Library/Mobile Documents/');
  }
  return p;
}

function fileReadable(filePath) {
  try {
    fs.accessSync(filePath, fs.constants.R_OK);
    const fd = fs.openSync(filePath, 'r');
    const buf = Buffer.alloc(1);
    fs.readSync(fd, buf, 0, 1, 0);
    fs.closeSync(fd);
    return true;
  } catch {
    return false;
  }
}

async function ensureLocalFile(filePath, maxAttempts = 12) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (fileReadable(filePath)) return true;
    // eslint-disable-next-line no-await-in-loop
    await new Promise((r) => setTimeout(r, 350));
  }
  return false;
}

function resolveBundledLabDir() {
  const resourceDir = process.resourcesPath || __dirname;
  const candidates = [
    path.join(resourceDir, BUNDLED_SUBDIR),
    path.join(__dirname, BUNDLED_SUBDIR),
  ];
  for (const bundleDir of candidates) {
    const serveScript = path.join(bundleDir, 'serve_animlab.py');
    const html = path.join(bundleDir, 'anim_lab.html');
    if (fileReadable(serveScript) && fileReadable(html)) {
      return bundleDir;
    }
  }
  return '';
}

function repoRootLooksValid(root) {
  if (!root) return false;
  if (resolveBundledLabDir()) return fs.existsSync(root);
  return fileReadable(path.join(root, SERVE_MARKER));
}

function readBakedRepoRoot() {
  const resourceDir = process.resourcesPath || __dirname;
  const candidates = [
    path.join(__dirname, 'repo-config.json'),
    path.join(resourceDir, 'repo-config.json'),
    path.join(resourceDir, 'repo_root.txt'),
  ];
  for (const cfgPath of candidates) {
    try {
      if (!fileReadable(cfgPath)) continue;
      let root = '';
      if (cfgPath.endsWith('.json')) {
        const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
        root = normalizeRepoRoot(cfg.repoRoot || '');
      } else {
        root = normalizeRepoRoot(fs.readFileSync(cfgPath, 'utf8'));
      }
      if (repoRootLooksValid(root)) return root;
    } catch {
      // try next
    }
  }
  return '';
}

function discoverRepoRoot(startDir) {
  let candidate = path.resolve(startDir);
  for (let i = 0; i < 12; i += 1) {
    if (fileReadable(path.join(candidate, SERVE_MARKER))) return candidate;
    const parent = path.dirname(candidate);
    if (parent === candidate) break;
    candidate = parent;
  }
  return '';
}

function resolveRepoRoot() {
  const fromEnv = normalizeRepoRoot(process.env.PD_REPO_ROOT || '');
  if (fromEnv && repoRootLooksValid(fromEnv)) {
    log(`REPO_ROOT from PD_REPO_ROOT=${fromEnv}`);
    return fromEnv;
  }
  const baked = readBakedRepoRoot();
  if (baked) {
    log(`REPO_ROOT from baked config=${baked}`);
    return baked;
  }
  const fromExe = discoverRepoRoot(path.dirname(app.getPath('exe')));
  if (fromExe) {
    log(`REPO_ROOT discovered from exe=${fromExe}`);
    return fromExe;
  }
  const fromCwd = discoverRepoRoot(process.cwd());
  if (fromCwd) {
    log(`REPO_ROOT discovered from cwd=${fromCwd}`);
    return fromCwd;
  }
  return '';
}

function resolveLabPaths(repoRoot) {
  const bundleDir = resolveBundledLabDir();
  if (bundleDir) {
    return {
      bundleDir,
      serveScript: path.join(bundleDir, 'serve_animlab.py'),
      source: 'bundle',
    };
  }
  const repoLab = path.join(repoRoot, 'journal', 'anim_lab');
  const repoServe = path.join(repoLab, 'serve_animlab.py');
  if (fileReadable(repoServe)) {
    return { bundleDir: '', serveScript: repoServe, source: 'repo' };
  }
  return null;
}

function resolveStateDir(repoRoot, source) {
  return kitPaths.resolveKitStateDir(
    app.getPath('home'),
    'animLab',
    repoRoot,
    'journal/anim_lab',
    'PD_ANIM_LAB_STATE_DIR'
  );
}

function resolvePython() {
  const candidates = [];
  const seen = new Set();
  const add = (p) => {
    if (!p || seen.has(p)) return;
    seen.add(p);
    candidates.push(p);
  };
  if (process.env.PD_PYTHON) add(process.env.PD_PYTHON);
  add('/opt/homebrew/bin/python3');
  add('/usr/local/bin/python3');
  add('/Library/Frameworks/Python.framework/Versions/Current/bin/python3');
  const home = app.getPath('home');
  for (const ver of ['3.14', '3.13', '3.12', '3.11', '3.10']) {
    add(path.join(home, 'Library/Python', ver, 'bin/python3'));
  }
  add('/usr/bin/python3');

  for (const py of candidates) {
    try {
      if (!fs.existsSync(py)) continue;
      const { status } = require('child_process').spawnSync(py, [
        '-c',
        'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)',
      ]);
      if (status === 0) return py;
    } catch {
      // try next
    }
  }
  return '';
}

function fetchHealth(port) {
  return new Promise((resolve) => {
    const req = http.get(
      { hostname: DEFAULT_HOST, port, path: '/api/health', timeout: 2000 },
      (res) => {
        let body = '';
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          try {
            resolve(JSON.parse(body));
          } catch {
            resolve(null);
          }
        });
      }
    );
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
  });
}

function healthOk(port) {
  return new Promise((resolve) => {
    const req = http.get(
      { hostname: DEFAULT_HOST, port, path: '/api/health', timeout: 2000 },
      (res) => { res.resume(); resolve(res.statusCode === 200); }
    );
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

async function findHealthyPort(minPort, maxPort, expectedBundleDir = '') {
  for (let port = minPort; port <= maxPort; port += 1) {
    // eslint-disable-next-line no-await-in-loop
    const health = await fetchHealth(port);
    if (!health || health.ok !== true || health.service !== 'anim-lab') continue;
    if (expectedBundleDir && health.bundleDir !== expectedBundleDir) continue;
    return String(port);
  }
  return '';
}

async function waitForServerReady(stateDir) {
  const portFile = path.join(stateDir, '.anim_lab_server.port');
  for (let attempt = 0; attempt < 80; attempt += 1) {
    let portFromFile = '';
    try {
      if (fs.existsSync(portFile)) {
        portFromFile = fs.readFileSync(portFile, 'utf8').trim();
      }
    } catch {
      // ignore
    }
    if (portFromFile && (await healthOk(Number(portFromFile)))) return portFromFile;
    const scanned = await findHealthyPort(PORT_MIN, PORT_MAX, serverContext?.bundleDir || '');
    if (scanned && serverProcess && !serverProcess.killed) return scanned;
    if (serverProcess && serverProcess.exitCode !== null) {
      throw new Error(`serve_animlab.py exited with code ${serverProcess.exitCode}`);
    }
    // eslint-disable-next-line no-await-in-loop
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error(`Timed out waiting for /api/health on ports ${PORT_MIN}–${PORT_MAX}`);
}

function buildSpawnEnv(repoRoot, stateDir, bundleDir) {
  const pythonPath = [
    repoRoot,
    bundleDir,
    path.join(repoRoot, 'journal', 'anim_lab'),
    process.env.PYTHONPATH || '',
  ].filter(Boolean).join(':');
  const env = {
    ...process.env,
    PD_REPO_ROOT: repoRoot,
    PD_ANIM_LAB_STATE_DIR: stateDir,
    PYTHONPATH: pythonPath,
    PATH: `/opt/homebrew/bin:/usr/local/bin:${process.env.PATH || ''}`,
  };
  if (bundleDir) env.PD_ANIM_LAB_BUNDLE_DIR = bundleDir;
  return env;
}

function spawnServer(pythonBin, serveScript, repoRoot, stateDir, bundleDir) {
  const spawnArgs = [serveScript, '--host', DEFAULT_HOST, '--port', String(PORT_MIN), '--auto-port'];
  const spawnEnv = buildSpawnEnv(repoRoot, stateDir, bundleDir);
  log(`Starting serve_animlab.py from ${serveScript}`);
  const child = spawn(pythonBin, spawnArgs, {
    cwd: repoRoot,
    env: spawnEnv,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.stdout.on('data', (chunk) => {
    const text = chunk.toString().trim();
    if (text) log(`[serve_animlab] ${text}`);
  });
  child.stderr.on('data', (chunk) => {
    const text = chunk.toString().trim();
    if (text) log(`[serve_animlab:err] ${text}`);
  });
  child.on('exit', (code, signal) => handleServerExit(code, signal));
  return child;
}

async function handleServerExit(code, signal) {
  log(`serve_animlab.py exited code=${code} signal=${signal || ''}`);
  serverProcess = null;
  if (quitting) return;

  const stillHealthy = await findHealthyPort(PORT_MIN, PORT_MAX, serverContext?.bundleDir || '');
  if (stillHealthy) {
    activePort = stillHealthy;
    restartAttempts = 0;
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.loadURL(labUrl(stillHealthy));
    }
    return;
  }

  if (!serverContext || restartAttempts >= MAX_RESTART_ATTEMPTS) {
    if (mainWindow) {
      dialog.showErrorBox(APP_TITLE, `Animation Lab server stopped (code ${code}).\n\nLog: ${LOG_FILE}`);
      app.quit();
    }
    return;
  }

  restartAttempts += 1;
  try {
    serverProcess = spawnServer(
      serverContext.pythonBin,
      serverContext.serveScript,
      serverContext.repoRoot,
      serverContext.stateDir,
      serverContext.bundleDir
    );
    activePort = await waitForServerReady(serverContext.stateDir);
    restartAttempts = 0;
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.loadURL(labUrl(activePort));
    }
  } catch (err) {
    log(`Restart failed: ${err.message}`);
  }
}

function showStartupError(message) {
  log(`ERROR: ${message}`);
  dialog.showErrorBox(APP_TITLE, `${message}\n\nLog: ${LOG_FILE}`);
}

function labUrl(port) {
  return `http://${DEFAULT_HOST}:${port}/?v=${Date.now()}`;
}

function createWindow(url) {
  mainWindow = new BrowserWindow({
    title: APP_TITLE,
    width: 1180,
    height: 860,
    minWidth: 900,
    minHeight: 640,
    backgroundColor: '#0a0a12',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadURL(url);
  mainWindow.on('closed', () => { mainWindow = null; });
}

function killServer() {
  if (!serverProcess || serverProcess.killed) return;
  try {
    serverProcess.kill('SIGTERM');
  } catch {
    // ignore
  }
  serverProcess = null;
}

async function bootstrap() {
  log('=== electron anim-lab start ===');

  const repoRoot = resolveRepoRoot();
  if (!repoRoot) {
    showStartupError(
      'Could not locate the Perfect Dark repository.\n\n' +
        'Set PD_REPO_ROOT or rebuild with ./scripts/build-anim-lab-electron.sh'
    );
    app.quit();
    return;
  }

  const labPaths = resolveLabPaths(repoRoot);
  if (!labPaths) {
    showStartupError(
      `Animation Lab not found (bundled Resources/anim-lab/ or journal/anim_lab).\n\n` +
        'Rebuild: ./scripts/build-anim-lab-electron.sh'
    );
    app.quit();
    return;
  }

  const { serveScript, bundleDir, source } = labPaths;
  const stateDir = resolveStateDir(repoRoot, source);

  if (!(await ensureLocalFile(serveScript))) {
    showStartupError(`Server script not readable:\n${serveScript}`);
    app.quit();
    return;
  }

  const existing = await findHealthyPort(PORT_MIN, PORT_MAX, bundleDir);
  if (existing) {
    activePort = existing;
    log(`Reusing healthy server on port ${activePort}`);
    createWindow(labUrl(activePort));
    return;
  }

  const pythonBin = resolvePython();
  if (!pythonBin) {
    showStartupError('Python 3.10+ required. Install: brew install python');
    app.quit();
    return;
  }

  serverContext = { pythonBin, serveScript, repoRoot, stateDir, bundleDir };
  serverProcess = spawnServer(pythonBin, serveScript, repoRoot, stateDir, bundleDir);

  try {
    activePort = await waitForServerReady(stateDir);
  } catch (err) {
    showStartupError(`Server failed to start: ${err.message}`);
    quitting = true;
    killServer();
    app.quit();
    return;
  }

  log(`Server healthy on port ${activePort}`);
  createWindow(labUrl(activePort));
}

app.whenReady().then(bootstrap);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  quitting = true;
  killServer();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0 && activePort) {
    createWindow(labUrl(activePort));
  }
});

process.on('SIGINT', () => { quitting = true; killServer(); app.quit(); });
process.on('SIGTERM', () => { quitting = true; killServer(); app.quit(); });
