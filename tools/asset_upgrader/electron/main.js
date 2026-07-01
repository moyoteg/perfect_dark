'use strict';

/**
 * Electron supervisor for the Perfect Dark asset upgrader pipeline.
 * Spawns tools/asset_upgrader.py, watches snapshot.json, and streams logs.
 */

const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
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
const { bindSingleInstance } = kitPaths.requireKitModule('electron_single_instance.js');

const APP_TITLE = kitPaths.appConfig('assetUpgrader').productName;
const LOG_FILE = kitPaths.kitLogFile(app.getPath('home'), 'assetUpgrader');
const CONFIG_NAME = 'supervisor-config.json';
const DEFAULT_MOD = 'mods/mod_allinone';
const DEFAULT_DEPLOY = 'mods/mod_upgraded';

/** @type {import('child_process').ChildProcess | null} */
let childProcess = null;
/** @type {BrowserWindow | null} */
let mainWindow = null;
/** @type {{ repoRoot: string, workdir: string, pythonBin: string, modPath: string, deployDir: string, model: string, prompt: string, limit: number, dryRun: boolean, sleep: number } | null} */
let runtimeConfig = null;

function normalizeRepoRoot(raw) {
  if (!raw) return '';
  return raw.trim().replace(/\/Library\/MobileDocuments\//g, '/Library/Mobile Documents/');
}

function readBakedRepoRoot() {
  const candidates = [
    path.join(__dirname, 'repo-config.json'),
    path.join(process.resourcesPath || '', 'repo-config.json'),
  ];
  for (const cfgPath of candidates) {
    try {
      if (!fs.existsSync(cfgPath)) continue;
      const parsed = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
      if (parsed.repoRoot) return normalizeRepoRoot(parsed.repoRoot);
    } catch {
      // ignore
    }
  }
  return normalizeRepoRoot(path.resolve(__dirname, '../../..'));
}

function detectRepoRoot() {
  let root = readBakedRepoRoot();
  if (fs.existsSync(path.join(root, 'tools', 'asset_upgrader.py'))) return root;
  root = normalizeRepoRoot(process.cwd());
  if (fs.existsSync(path.join(root, 'tools', 'asset_upgrader.py'))) return root;
  return readBakedRepoRoot();
}

function configPath(repoRoot) {
  return path.join(repoRoot, 'work', 'asset_upgrader', CONFIG_NAME);
}

function loadConfig(repoRoot) {
  const defaults = {
    repoRoot,
    workdir: path.join(repoRoot, 'work', 'asset_upgrader'),
    pythonBin: path.join(repoRoot, '.venv-asset-upgrader', 'bin', 'python3'),
    modPath: DEFAULT_MOD,
    deployDir: DEFAULT_DEPLOY,
    backend: 'local',
    model: 'gpt-image-1',
    prompt: '',
    limit: 0,
    dryRun: false,
    sleep: 1.0,
  };
  try {
    const stored = JSON.parse(fs.readFileSync(configPath(repoRoot), 'utf8'));
    return { ...defaults, ...stored, repoRoot };
  } catch {
    return defaults;
  }
}

function saveConfigToDisk(config) {
  fs.mkdirSync(path.dirname(configPath(config.repoRoot)), { recursive: true });
  fs.writeFileSync(configPath(config.repoRoot), `${JSON.stringify(config, null, 2)}\n`, 'utf8');
}

function resolvePython(config) {
  if (config.pythonBin && fs.existsSync(config.pythonBin)) return config.pythonBin;
  return 'python3';
}

function snapshotPath(config) {
  return path.join(config.workdir, 'snapshot.json');
}

function readSnapshot(config) {
  try {
    return JSON.parse(fs.readFileSync(snapshotPath(config), 'utf8'));
  } catch {
    return {
      total: 0,
      by_stage: {},
      assets: [],
      running: Boolean(childProcess),
    };
  }
}

function emitLog(line) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('upgrader:log', line);
  }
}

function emitSnapshot(config) {
  const snapshot = readSnapshot(config);
  snapshot.running = Boolean(childProcess);
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('upgrader:snapshot', snapshot);
  }
}

function emitRunState(running) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('upgrader:run-state', { running });
  }
}

function runSnapshotRefresh(config) {
  const python = resolvePython(config);
  const script = path.join(config.repoRoot, 'tools', 'asset_upgrader.py');
  const proc = spawn(python, [script, 'snapshot', '--workdir', config.workdir], {
    cwd: config.repoRoot,
    env: process.env,
  });
  proc.on('close', () => emitSnapshot(config));
}

function startPipeline(config) {
  if (childProcess) return { ok: false, error: 'Pipeline already running' };

  const python = resolvePython(config);
  const script = path.join(config.repoRoot, 'tools', 'asset_upgrader.py');
  const args = [
    script,
    'run',
    '--path',
    config.modPath,
    '--deploy-dir',
    config.deployDir,
    '--backend',
    config.backend || 'local',
    '--model',
    config.model,
    '--sleep',
    String(config.sleep),
  ];
  if (config.limit > 0) args.push('--limit', String(config.limit));
  if (config.dryRun) args.push('--dry-run');
  if (config.prompt) args.push('--prompt', config.prompt);

  emitLog(`$ ${python} ${args.join(' ')}`);
  childProcess = spawn(python, args, {
    cwd: config.repoRoot,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  });
  emitRunState(true);

  childProcess.stdout.on('data', (chunk) => {
    String(chunk).split('\n').filter(Boolean).forEach((line) => emitLog(line));
    runSnapshotRefresh(config);
  });
  childProcess.stderr.on('data', (chunk) => {
    String(chunk).split('\n').filter(Boolean).forEach((line) => emitLog(`[stderr] ${line}`));
  });
  childProcess.on('close', (code) => {
    emitLog(`Pipeline exited with code ${code}`);
    childProcess = null;
    emitRunState(false);
    runSnapshotRefresh(config);
  });
  return { ok: true };
}

function stopPipeline() {
  if (!childProcess) return { ok: false, error: 'No pipeline running' };
  childProcess.kill('SIGTERM');
  childProcess = null;
  emitRunState(false);
  return { ok: true };
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 960,
    minHeight: 640,
    title: APP_TITLE,
    backgroundColor: '#0f1117',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

function focusMainWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
    return;
  }
  createWindow();
}

if (!bindSingleInstance(app, focusMainWindow)) {
  process.exit(0);
}

function registerIpc() {
  ipcMain.handle('upgrader:get-config', () => runtimeConfig);

  ipcMain.handle('upgrader:save-config', (_event, config) => {
    runtimeConfig = { ...runtimeConfig, ...config };
    saveConfigToDisk(runtimeConfig);
    return runtimeConfig;
  });

  ipcMain.handle('upgrader:get-snapshot', () => readSnapshot(runtimeConfig));

  ipcMain.handle('upgrader:refresh-snapshot', () => {
    runSnapshotRefresh(runtimeConfig);
    return readSnapshot(runtimeConfig);
  });

  ipcMain.handle('upgrader:start-run', (_event, options) => {
    runtimeConfig = { ...runtimeConfig, ...options };
    saveConfigToDisk(runtimeConfig);
    return startPipeline(runtimeConfig);
  });

  ipcMain.handle('upgrader:stop-run', () => stopPipeline());

  ipcMain.handle('upgrader:pick-directory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
      defaultPath: runtimeConfig.repoRoot,
    });
    if (result.canceled || !result.filePaths.length) return null;
    const picked = result.filePaths[0];
    return path.relative(runtimeConfig.repoRoot, picked) || picked;
  });
}

app.whenReady().then(() => {
  const repoRoot = detectRepoRoot();
  runtimeConfig = loadConfig(repoRoot);
  registerIpc();
  createWindow();
  runSnapshotRefresh(runtimeConfig);

  setInterval(() => {
    if (!childProcess) emitSnapshot(runtimeConfig);
  }, 3000);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (childProcess) childProcess.kill('SIGTERM');
});
