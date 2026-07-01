'use strict';

/**
 * Perfect Dark Kit hub — wraps and launches Map Editor, Animation Lab,
 * Asset Upgrader, and the PC port from one entry-point .app.
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

const APP_TITLE = kitPaths.loadManifest().name || 'Perfect Dark Kit';
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

function readManifest() {
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

function appBundlePath(appKey) {
  const cfg = kitPaths.appConfig(appKey);
  const bundleName = cfg.bundleFileName;
  const candidates = [
    path.join(wrappedAppsDir(), bundleName),
    path.join(releaseDir(), bundleName),
    path.join(repoRoot, bundleName),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return '';
}

function toolCards() {
  const manifest = readManifest();
  const keys = ['mapEditor', 'animLab', 'assetUpgrader'];
  return keys.map((key) => {
    const cfg = kitPaths.appConfig(key);
    const appPath = appBundlePath(key);
    const wrappedPath = path.join(wrappedAppsDir(), cfg.bundleFileName);
    const manifestApp = manifest && manifest.apps ? manifest.apps[key] : null;
    return {
      key,
      title: cfg.productName,
      shortTitle: cfg.productName.replace(/^Perfect Dark Kit — /, ''),
      description: describeApp(key),
      built: Boolean(appPath),
      wrapped: fs.existsSync(wrappedPath),
      path: appPath,
    };
  });
}

function describeApp(key) {
  switch (key) {
    case 'mapEditor':
      return 'Design Combat Sim arenas, deploy assets, and Test/Play in one flow.';
    case 'animLab':
      return 'Browse the animation catalog and run the guard parade test map.';
    case 'assetUpgrader':
      return 'Batch-upgrade mod textures for the PC port loader.';
    default:
      return '';
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 980,
    height: 720,
    minWidth: 820,
    minHeight: 620,
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
    const manifest = readManifest();
    const gamePath = manifest?.gameBinary?.path || path.join(repoRoot, 'build', 'pd.arm64');
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
      manifestBuiltAt: manifest?.builtAt || null,
    };
  });

  ipcMain.handle('kit:launch-app', async (_event, appKey) => {
    const appPath = appBundlePath(appKey);
    if (!appPath) {
      return { ok: false, error: `App not built for ${appKey}. Run ./scripts/build-pd-kit.sh --apps-only` };
    }
    log(`Launch ${appKey}: ${appPath}`);
    await new Promise((resolve, reject) => {
      execFile('open', [appPath], (err) => (err ? reject(err) : resolve()));
    });
    return { ok: true, path: appPath };
  });

  ipcMain.handle('kit:launch-game', async (_event, options) => {
    const mod = (options && options.mod) || 'mod_allinone';
    const testMap = Boolean(options && options.testMap);
    const binary = path.join(repoRoot, 'build', 'pd.arm64');
    if (!fs.existsSync(binary)) {
      return { ok: false, error: `Game binary missing: ${binary}` };
    }
    const args = [`--moddir`, path.join(repoRoot, 'mods', mod)];
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

  ipcMain.handle('kit:reveal-path', async (_event, targetPath) => {
    if (!targetPath || !fs.existsSync(targetPath)) {
      return { ok: false, error: 'Path not found' };
    }
    shell.showItemInFolder(targetPath);
    return { ok: true };
  });

  ipcMain.handle('kit:build-kit', async () => {
    const script = path.join(repoRoot, 'scripts', 'build-pd-kit.sh');
    if (!fs.existsSync(script)) {
      return { ok: false, error: 'build-pd-kit.sh not found' };
    }
    return new Promise((resolve) => {
      const child = spawn('/bin/bash', [script, '--apps-only'], {
        cwd: repoRoot,
        env: { ...process.env, PD_REPO_ROOT: repoRoot },
      });
      let output = '';
      child.stdout.on('data', (chunk) => {
        output += String(chunk);
      });
      child.stderr.on('data', (chunk) => {
        output += String(chunk);
      });
      child.on('close', (code) => {
        resolve({ ok: code === 0, code, output });
      });
    });
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
