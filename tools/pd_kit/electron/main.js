'use strict';

/**
 * Perfect Dark Kit hub — launches every kit app, pipeline action, and doc
 * from one entry-point .app (manifest: tools/pd_kit/kit.json).
 */

const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn, execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

function requireKitPaths() {
  const candidates = [
    path.join(__dirname, '../electron_paths.js'),
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

const kitManifest = kitPaths.loadManifest();
const APP_TITLE = kitManifest.name || 'Perfect Dark Kit';
const LOG_FILE = kitPaths.kitLogFile(app.getPath('home'), 'kitHub');
const WRAPPED_APPS_DIR = 'Apps';
const MANIFEST_NAME = 'kit-manifest.json';

/** @type {BrowserWindow | null} */
let mainWindow = null;
/** @type {string} */
let repoRoot = '';

function log(...args) {
  const line = `[${new Date().toISOString().slice(0, 19).replace('T', ' ')}] [kit-hub] ${args.join(' ')}`;
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
  return raw.trim().replace(/\/Library\/MobileDocuments\//g, '/Library/Mobile Documents/');
}

function readBakedRepoRoot() {
  const resourceDir = process.resourcesPath || __dirname;
  const candidates = [
    path.join(resourceDir, 'repo-config.json'),
    path.join(resourceDir, 'repo_root.txt'),
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
  if (fromEnv && fs.existsSync(fromEnv)) {
    return fromEnv;
  }
  const baked = readBakedRepoRoot();
  if (baked && fs.existsSync(baked)) {
    return baked;
  }
  const fromExe = discoverRepoRoot(path.dirname(app.getPath('exe')));
  if (fromExe) return fromExe;
  return discoverRepoRoot(process.cwd());
}

function wrappedAppsDir() {
  return path.join(process.resourcesPath || '', WRAPPED_APPS_DIR);
}

function releaseDir() {
  return path.join(repoRoot, 'scripts', 'release');
}

function readReleaseManifest() {
  const candidates = [
    path.join(process.resourcesPath || '', MANIFEST_NAME),
    path.join(releaseDir(), MANIFEST_NAME),
  ];
  for (const manifestPath of candidates) {
    try {
      if (fs.existsSync(manifestPath)) {
        return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
      }
    } catch {
      // try next
    }
  }
  return null;
}

function hubAppKeys() {
  const apps = kitManifest.apps || {};
  const wraps = apps.kitHub && Array.isArray(apps.kitHub.wraps) ? apps.kitHub.wraps : [];
  return wraps.filter((key) => key !== 'kitHub' && apps[key]);
}

function appBundlePath(appKey) {
  const cfg = kitPaths.appConfig(appKey);
  const bundleName = cfg.bundleFileName;
  const candidates = [
    path.join(wrappedAppsDir(), bundleName),
    path.join(releaseDir(), bundleName),
    path.join(repoRoot, bundleName),
  ];
  if (cfg.siblingPath) {
    candidates.push(path.resolve(repoRoot, cfg.siblingPath));
  }
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return '';
}

/** True when no .app exists but kit.json lists a dev launch script in the repo. */
function devLaunchAvailable(appKey) {
  const cfg = kitPaths.appConfig(appKey);
  if (!cfg.devLaunchScript) return false;
  return fs.existsSync(path.join(repoRoot, cfg.devLaunchScript));
}

function toolCards() {
  return hubAppKeys().map((key) => {
    const cfg = kitPaths.appConfig(key);
    const appPath = appBundlePath(key);
    const devMode = !appPath && devLaunchAvailable(key);
    const wrappedPath = path.join(wrappedAppsDir(), cfg.bundleFileName);
    return {
      key,
      title: cfg.productName,
      shortTitle: cfg.shortTitle || cfg.productName,
      description: cfg.description || '',
      category: cfg.category || 'authoring',
      optional: Boolean(cfg.optional),
      built: Boolean(appPath) || devMode,
      devMode,
      wrapped: fs.existsSync(wrappedPath),
      path: appPath || (devMode ? path.join(repoRoot, cfg.devLaunchScript) : ''),
      buildScript: cfg.buildScript || cfg.devLaunchScript || null,
    };
  });
}

function actionGroups() {
  const groups = kitManifest.actionGroups || [];
  return groups.map((group) => ({
    id: group.id,
    title: group.title,
    actions: (group.actions || []).map((action) => ({
      key: action.key,
      shortTitle: action.shortTitle,
      description: action.description || '',
      script: action.script,
      args: action.args || [],
      requiresGame: Boolean(action.requiresGame),
      longRunning: Boolean(action.longRunning),
    })),
  }));
}

function docLinks() {
  return (kitManifest.docs || []).map((doc) => ({
    key: doc.key,
    title: doc.title,
    path: doc.path,
    exists: fs.existsSync(path.join(repoRoot, doc.path)),
  }));
}

function gameBinaryPath() {
  const manifest = readReleaseManifest();
  return manifest?.gameBinary?.path || path.join(repoRoot, 'build', 'pd.arm64');
}

function runScript(scriptRel, args, options) {
  const scriptPath = path.join(repoRoot, scriptRel);
  if (!fs.existsSync(scriptPath)) {
    return Promise.resolve({ ok: false, error: `Script not found: ${scriptPath}` });
  }
  return new Promise((resolve) => {
    const child = spawn('/bin/bash', [scriptPath, ...(args || [])], {
      cwd: repoRoot,
      env: { ...process.env, PD_REPO_ROOT: repoRoot },
      detached: Boolean(options && options.detached),
      stdio: options && options.detached ? 'ignore' : ['ignore', 'pipe', 'pipe'],
    });
    if (options && options.detached) {
      child.unref();
      resolve({ ok: true, pid: child.pid, detached: true });
      return;
    }
    let output = '';
    child.stdout.on('data', (chunk) => {
      output += String(chunk);
    });
    child.stderr.on('data', (chunk) => {
      output += String(chunk);
    });
    child.on('close', (code) => {
      resolve({ ok: code === 0, code, output: output.slice(-4000) });
    });
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 920,
    minWidth: 900,
    minHeight: 700,
    title: APP_TITLE,
    backgroundColor: '#0b0d12',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

function registerIpc() {
  ipcMain.handle('kit:get-info', () => {
    const gamePath = gameBinaryPath();
    return {
      name: APP_TITLE,
      kitVersion: kitPaths.kitVersion(repoRoot),
      portVersion: kitPaths.portVersion(repoRoot),
      repoRoot,
      releaseDir: releaseDir(),
      wrappedAppsDir: wrappedAppsDir(),
      gameBinary: {
        path: gamePath,
        built: fs.existsSync(gamePath),
      },
      tools: toolCards(),
      actionGroups: actionGroups(),
      docs: docLinks(),
      manifestBuiltAt: readReleaseManifest()?.builtAt || null,
    };
  });

  ipcMain.handle('kit:launch-app', async (_event, appKey) => {
    const cfg = kitPaths.appConfig(appKey);
    const appPath = appBundlePath(appKey);
    if (appPath) {
      log(`Launch ${appKey}: ${appPath}`);
      await new Promise((resolve, reject) => {
        execFile('open', [appPath], (err) => (err ? reject(err) : resolve()));
      });
      return { ok: true, path: appPath };
    }
    if (cfg.devLaunchScript) {
      const scriptPath = path.join(repoRoot, cfg.devLaunchScript);
      if (fs.existsSync(scriptPath)) {
        log(`Launch ${appKey} (dev): ${scriptPath}`);
        const result = await runScript(cfg.devLaunchScript, [], { detached: true });
        return { ok: result.ok, path: scriptPath, devMode: true };
      }
    }
    const hint = cfg.buildScript
      ? ` Run: ./${cfg.buildScript}`
      : cfg.devLaunchScript
        ? ` Run: ./${cfg.devLaunchScript}`
        : ' Run: ./scripts/build-pd-kit.sh --apps-only';
    return { ok: false, error: `${cfg.shortTitle || appKey} is not built.${hint}` };
  });

  ipcMain.handle('kit:launch-game', async (_event, options) => {
    const mod = (options && options.mod) || 'mod_allinone';
    const testMap = Boolean(options && options.testMap);
    const binary = gameBinaryPath();
    if (!fs.existsSync(binary)) {
      return { ok: false, error: `Game binary missing: ${binary}` };
    }
    const args = ['--moddir', path.join(repoRoot, 'mods', mod)];
    if (testMap) args.push('--test-map');
    log(`Launch game: ${binary} ${args.join(' ')}`);
    const child = spawn(binary, args, {
      cwd: repoRoot,
      detached: true,
      stdio: 'ignore',
    });
    child.unref();
    return { ok: true, pid: child.pid, command: `${binary} ${args.join(' ')}` };
  });

  ipcMain.handle('kit:run-action', async (_event, actionKey) => {
    const groups = kitManifest.actionGroups || [];
    let action = null;
    for (const group of groups) {
      action = (group.actions || []).find((entry) => entry.key === actionKey);
      if (action) break;
    }
    if (!action) {
      return { ok: false, error: `Unknown action: ${actionKey}` };
    }
    if (action.requiresGame && !fs.existsSync(gameBinaryPath())) {
      return { ok: false, error: 'Game binary not built. Use Build Game first.' };
    }
    log(`Run action ${actionKey}: ${action.script} ${(action.args || []).join(' ')}`);
    if (action.longRunning && actionKey !== 'buildApps' && actionKey !== 'buildFullKit') {
      return runScript(action.script, action.args, { detached: true });
    }
    return runScript(action.script, action.args);
  });

  ipcMain.handle('kit:open-doc', async (_event, docKey) => {
    const doc = (kitManifest.docs || []).find((entry) => entry.key === docKey);
    if (!doc) {
      return { ok: false, error: `Unknown doc: ${docKey}` };
    }
    const docPath = path.join(repoRoot, doc.path);
    if (!fs.existsSync(docPath)) {
      return { ok: false, error: `Doc not found: ${doc.path}` };
    }
    const err = await shell.openPath(docPath);
    if (err) {
      return { ok: false, error: err };
    }
    return { ok: true, path: docPath };
  });

  ipcMain.handle('kit:reveal-path', async (_event, targetPath) => {
    if (!targetPath || !fs.existsSync(targetPath)) {
      return { ok: false, error: 'Path not found' };
    }
    shell.showItemInFolder(targetPath);
    return { ok: true };
  });

  ipcMain.handle('kit:build-kit', async () => {
    return runScript('scripts/build-pd-kit.sh', ['--skip-game', '--apps-only']);
  });
}

function focusMainWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
}

if (!bindSingleInstance(app, focusMainWindow)) {
  process.exit(0);
}

app.whenReady().then(() => {
  repoRoot = resolveRepoRoot();
  if (!repoRoot) {
    log('WARNING: repo root not resolved — some actions will fail');
  } else {
    log(`REPO_ROOT=${repoRoot}`);
  }
  registerIpc();
  createWindow();
});

app.on('window-all-closed', () => {
  app.quit();
});
