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
const kitDomain = require(path.join(__dirname, '../kit_domain.js'));
const {
  KitHubSurfaceTier,
  KIT_LAUNCH_COOLDOWN_MS,
  resolveHubAppKeys,
  buildKitToolCardRecord,
  shouldExposeOptionalCompanionCard,
  validateKitGetInfoSurface,
  decideKitLaunchCooldown,
  resolveKitAppLaunchRoute,
  buildKitAppNotBuiltMessage,
  buildKitGameLaunchArgv,
  evaluateKitGameLaunchReadiness,
  resolveKitActionFromManifest,
  evaluateKitActionRunGate,
  shouldDetachKitActionRun,
  emitKitHubLifecycleEvent,
} = kitDomain;
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
/** @type {Map<string, number>} */
const launchCooldownUntil = new Map();

function appendKitLogLine(line) {
  try {
    fs.mkdirSync(path.dirname(LOG_FILE), { recursive: true });
    fs.appendFileSync(LOG_FILE, `${line}\n`, 'utf8');
  } catch {
    // ignore
  }
  if (line.startsWith('{')) {
    console.log(`[kit-hub] ${line}`);
  } else {
    console.log(line);
  }
}

function log(...args) {
  const line = `[${new Date().toISOString().slice(0, 19).replace('T', ' ')}] [kit-hub] ${args.join(' ')}`;
  appendKitLogLine(line);
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

function buildToolCard(appKey, hubSurfaceTier) {
  const cfg = kitPaths.appConfig(appKey);
  const bundlePath = appBundlePath(appKey);
  const resolution = {
    bundlePath: bundlePath || null,
    devLaunchAvailable: devLaunchAvailableFor(appKey),
    wrappedInHub: fs.existsSync(path.join(wrappedAppsDir(), cfg.bundleFileName)),
  };
  const record = buildKitToolCardRecord(appKey, cfg, resolution, hubSurfaceTier);
  if (record.devMode && cfg.devLaunchScript) {
    record.path = path.join(repoRoot, cfg.devLaunchScript);
  } else if (bundlePath) {
    record.path = bundlePath;
  }
  return record;
}

function toolCards() {
  return resolveHubAppKeys(kitManifest, KitHubSurfaceTier.CORE_WRAP).map((key) =>
    buildToolCard(key, KitHubSurfaceTier.CORE_WRAP)
  );
}

function moreToolCards() {
  return resolveHubAppKeys(kitManifest, KitHubSurfaceTier.OPTIONAL_COMPANION)
    .map((key) => buildToolCard(key, KitHubSurfaceTier.OPTIONAL_COMPANION))
    .filter(shouldExposeOptionalCompanionCard);
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
  // Prefer the newest bundle when Kit Hub wraps an older copy (e.g. Agent Office rebuild).
  let best = '';
  let bestMtime = 0;
  for (const candidate of candidates) {
    if (!fs.existsSync(candidate)) continue;
    try {
      const mtime = fs.statSync(candidate).mtimeMs;
      if (mtime > bestMtime) {
        bestMtime = mtime;
        best = candidate;
      }
    } catch {
      // skip unreadable bundle
    }
  }
  return best;
}

/** True when no .app exists but kit.json lists a dev launch script in the repo. */
function devLaunchAvailableFor(appKey) {
  const cfg = kitPaths.appConfig(appKey);
  if (!cfg.devLaunchScript) return false;
  return fs.existsSync(path.join(repoRoot, cfg.devLaunchScript));
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

function openAppBundle(appPath) {
  return new Promise((resolve, reject) => {
    execFile('open', [appPath], (err) => (err ? reject(err) : resolve()));
  });
}

function commitKitLaunchCooldown(appKey, evaluation) {
  if (evaluation.allowed && evaluation.cooldown_until_ms) {
    launchCooldownUntil.set(appKey, evaluation.cooldown_until_ms);
  }
}

function emitKitAppLaunchEvent(event) {
  emitKitHubLifecycleEvent(appendKitLogLine, {
    operation: 'kit:launch-app',
    ...event,
  });
}

function emitKitGameLaunchEvent(event) {
  emitKitHubLifecycleEvent(appendKitLogLine, {
    operation: 'kit:launch-game',
    ...event,
  });
}

function emitKitActionRunEvent(event) {
  emitKitHubLifecycleEvent(appendKitLogLine, {
    operation: 'kit:run-action',
    ...event,
  });
}

function createWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
    return;
  }
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
  // Cache-bust so renderer updates are never stuck on a stale HTML/CSS/JS snapshot.
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'), {
    query: { v: `${app.getVersion()}-${Date.now()}` },
  });
  mainWindow.on('closed', () => { mainWindow = null; });
}

function buildKitGetInfoPayload() {
  const gamePath = gameBinaryPath();
  const tools = toolCards();
  const moreTools = moreToolCards();
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
    tools,
    moreTools,
    actionGroups: actionGroups(),
    docs: docLinks(),
    manifestBuiltAt: readReleaseManifest()?.builtAt || null,
  };
}

function logKitGetInfoLifecycle(startedAt, payload) {
  const surfaceViolations = validateKitGetInfoSurface(payload.tools, payload.moreTools);
  emitKitHubLifecycleEvent(appendKitLogLine, {
    operation: 'kit:get-info',
    outcome: surfaceViolations.length ? 'invariant_violation' : 'succeeded',
    scenario_id: surfaceViolations.length ? 'KH-INV' : 'KH-02',
    core_tool_count: payload.tools.length,
    optional_tool_count: payload.moreTools.length,
    game_binary_built: payload.gameBinary.built,
    invariant_status: surfaceViolations.length ? surfaceViolations.join(';') : 'ok',
    latency_ms: Date.now() - startedAt,
  });
  return surfaceViolations;
}

function runKitHubHeadlessSmoke() {
  const startedAt = Date.now();
  try {
    const payload = buildKitGetInfoPayload();
    const surfaceViolations = logKitGetInfoLifecycle(startedAt, payload);
    const smokeOk = surfaceViolations.length === 0;
    console.log(
      `KIT_HUB_SMOKE_RESULT=${JSON.stringify({
        ok: smokeOk,
        violations: surfaceViolations,
        core_tool_count: payload.tools.length,
        optional_tool_count: payload.moreTools.length,
      })}`
    );
    process.exitCode = smokeOk ? 0 : 1;
  } catch (err) {
    console.log(
      `KIT_HUB_SMOKE_RESULT=${JSON.stringify({
        ok: false,
        error: err?.message || String(err),
      })}`
    );
    process.exitCode = 1;
  }
  app.quit();
}

function registerIpc() {
  ipcMain.handle('kit:get-info', () => {
    const startedAt = Date.now();
    try {
      const payload = buildKitGetInfoPayload();
      logKitGetInfoLifecycle(startedAt, payload);
      return payload;
    } catch (err) {
      emitKitHubLifecycleEvent(appendKitLogLine, {
        operation: 'kit:get-info',
        outcome: 'failed',
        error_kind: 'exception',
        reason: err?.message || String(err),
        latency_ms: Date.now() - startedAt,
      });
      log(`get-info failed: ${err?.message || err}`);
      return {
        name: APP_TITLE,
        kitVersion: kitPaths.kitVersion(repoRoot),
        portVersion: kitPaths.portVersion(repoRoot),
        repoRoot,
        releaseDir: releaseDir(),
        wrappedAppsDir: wrappedAppsDir(),
        gameBinary: { path: '', built: false },
        tools: [],
        moreTools: [],
        actionGroups: [],
        docs: [],
        manifestBuiltAt: null,
        error: err?.message || String(err),
      };
    }
  });

  ipcMain.handle('kit:launch-app', async (_event, appKey) => {
    const startedAt = Date.now();
    try {
      const cooldown = decideKitLaunchCooldown(appKey, Date.now(), launchCooldownUntil, KIT_LAUNCH_COOLDOWN_MS);
      if (!cooldown.allowed) {
        emitKitAppLaunchEvent({
          scenario_id: 'KH-04',
          app_key: appKey,
          decision: cooldown.decision,
          reason: cooldown.reason,
          outcome: 'skipped',
          cooldown_remaining_ms: cooldown.cooldown_remaining_ms,
          latency_ms: Date.now() - startedAt,
        });
        return { ok: true, skipped: true, reason: 'cooldown' };
      }
      commitKitLaunchCooldown(appKey, cooldown);

      const cfg = kitPaths.appConfig(appKey);
      const appPath = appBundlePath(appKey);
      const devLaunchAvailable = devLaunchAvailableFor(appKey);
      const route = resolveKitAppLaunchRoute(appPath, devLaunchAvailable);

      if (route.route === 'launched_bundle') {
        await openAppBundle(appPath);
        emitKitAppLaunchEvent({
          scenario_id: 'KH-02',
          app_key: appKey,
          decision: 'allow_launch',
          launch_route: route.route,
          outcome: 'succeeded',
          latency_ms: Date.now() - startedAt,
        });
        return { ok: true, path: appPath };
      }

      if (route.route === 'launched_dev_script') {
        const scriptPath = path.join(repoRoot, cfg.devLaunchScript);
        const result = await runScript(cfg.devLaunchScript, [], { detached: true });
        emitKitAppLaunchEvent({
          scenario_id: 'KH-02',
          app_key: appKey,
          decision: 'allow_launch',
          launch_route: route.route,
          outcome: result.ok ? 'succeeded' : 'failed',
          dev_mode: true,
          error_kind: result.ok ? undefined : 'dev_script_spawn_failed',
          latency_ms: Date.now() - startedAt,
        });
        return { ok: result.ok, path: scriptPath, devMode: true };
      }

      const error = buildKitAppNotBuiltMessage(cfg, appKey);
      emitKitAppLaunchEvent({
        scenario_id: 'KH-05',
        app_key: appKey,
        decision: 'allow_launch',
        launch_route: route.route,
        outcome: 'failed',
        error_kind: 'app_not_built',
        reason: error,
        recovery_action: 'build_apps',
        latency_ms: Date.now() - startedAt,
      });
      return { ok: false, error };
    } catch (err) {
      emitKitAppLaunchEvent({
        app_key: appKey,
        decision: 'allow_launch',
        outcome: 'failed',
        error_kind: 'exception',
        reason: err?.message || String(err),
        latency_ms: Date.now() - startedAt,
      });
      return { ok: false, error: err?.message || String(err) };
    }
  });

  ipcMain.handle('kit:launch-game', async (_event, options) => {
    const startedAt = Date.now();
    try {
      const binary = gameBinaryPath();
      const readiness = evaluateKitGameLaunchReadiness(fs.existsSync(binary));
      if (!readiness.ready) {
        const error = `Game binary missing: ${binary}`;
        emitKitGameLaunchEvent({
          scenario_id: 'KH-GAME-04',
          decision: readiness.decision,
          outcome: 'failed',
          error_kind: readiness.error_kind,
          recovery_action: readiness.recovery_action,
          reason: error,
          latency_ms: Date.now() - startedAt,
        });
        return { ok: false, error };
      }
      const launchPlan = buildKitGameLaunchArgv(options || {}, repoRoot);
      const child = spawn(binary, launchPlan.args, {
        cwd: repoRoot,
        detached: true,
        stdio: 'ignore',
      });
      child.unref();
      const command = `${binary} ${launchPlan.args.join(' ')}`;
      emitKitGameLaunchEvent({
        scenario_id: 'KH-GAME-01',
        decision: readiness.decision,
        outcome: 'succeeded',
        mod: launchPlan.mod,
        test_map: launchPlan.testMap,
        pid: child.pid,
        latency_ms: Date.now() - startedAt,
      });
      return { ok: true, pid: child.pid, command };
    } catch (err) {
      emitKitGameLaunchEvent({
        outcome: 'failed',
        error_kind: 'exception',
        reason: err?.message || String(err),
        latency_ms: Date.now() - startedAt,
      });
      return { ok: false, error: err?.message || String(err) };
    }
  });

  ipcMain.handle('kit:run-action', async (_event, actionKey) => {
    const startedAt = Date.now();
    try {
      const { action, groupId } = resolveKitActionFromManifest(kitManifest, actionKey);
      const gate = evaluateKitActionRunGate(action, fs.existsSync(gameBinaryPath()));
      if (!gate.allowed) {
        const error =
          gate.error_kind === 'unknown_action_key'
            ? `Unknown action: ${actionKey}`
            : 'Game binary not built. Use Build Game first.';
        emitKitActionRunEvent({
          scenario_id: gate.error_kind === 'unknown_action_key' ? 'KH-ACTION-03' : 'KH-ACTION-04',
          action_key: actionKey,
          action_group_id: groupId,
          decision: gate.decision,
          outcome: 'failed',
          error_kind: gate.error_kind,
          recovery_action: gate.recovery_action,
          reason: error,
          latency_ms: Date.now() - startedAt,
        });
        return { ok: false, error };
      }
      const detached = shouldDetachKitActionRun(actionKey, action);
      const result = await runScript(action.script, action.args, { detached });
      emitKitActionRunEvent({
        scenario_id: 'KH-ACTION-01',
        action_key: actionKey,
        action_group_id: groupId,
        decision: gate.decision,
        outcome: result.ok ? 'succeeded' : 'failed',
        detached,
        exit_code: result.code,
        error_kind: result.ok ? undefined : 'script_nonzero_exit',
        latency_ms: Date.now() - startedAt,
      });
      return result;
    } catch (err) {
      emitKitActionRunEvent({
        action_key: actionKey,
        outcome: 'failed',
        error_kind: 'exception',
        reason: err?.message || String(err),
        latency_ms: Date.now() - startedAt,
      });
      return { ok: false, error: err?.message || String(err) };
    }
  });

  ipcMain.handle('kit:open-doc', async (_event, docKey) => {
    try {
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
    } catch (err) {
      log(`Open doc ${docKey} failed: ${err?.message || err}`);
      return { ok: false, error: err?.message || String(err) };
    }
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
  } else {
    createWindow();
  }
}

if (process.env.KIT_HUB_SMOKE !== '1' && !bindSingleInstance(app, focusMainWindow)) {
  process.exit(0);
}

app.whenReady().then(() => {
  repoRoot = resolveRepoRoot();
  emitKitHubLifecycleEvent(appendKitLogLine, {
    operation: 'kit:startup',
    scenario_id: 'KH-STARTUP-01',
    outcome: repoRoot ? 'configuration_loaded' : 'configuration_partial',
    repo_root_resolved: Boolean(repoRoot),
  });
  if (!repoRoot) {
    log('WARNING: repo root not resolved — some actions will fail');
  } else {
    log(`REPO_ROOT=${repoRoot}`);
  }
  registerIpc();
  if (process.env.KIT_HUB_SMOKE === '1') {
    runKitHubHeadlessSmoke();
    return;
  }
  createWindow();
}).catch((err) => {
  log(`Startup failed: ${err?.message || err}`);
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

process.on('unhandledRejection', (reason) => {
  log(`Unhandled rejection: ${reason?.message || reason}`);
});

process.on('uncaughtException', (err) => {
  log(`Uncaught exception: ${err?.message || err}`);
});
