'use strict';

/**
 * PD Map Launcher — unified map playtesting and map learn curriculum UI.
 * Spawns only whitelisted scripts under scripts/ (security boundary).
 */

const { app, BrowserWindow, ipcMain, shell, nativeImage } = require('electron');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const { bindSingleInstance } = require('../pd_kit/electron_single_instance.js');

const APP_TITLE = 'PD Map Launcher';
const LOG_FILE_NAME = 'map-launcher.log';

/** @type {import('electron').NativeImage | null} */
let appIcon = null;

/** macOS menu bar / Dock label; npm start otherwise shows "Electron". */
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

/** Resolve bundled icon paths for dev runs and packaged .app builds. */
function resolveAppIconCandidates() {
  const candidates = [
    path.join(__dirname, 'assets', 'map-launcher-1024.png'),
    path.join(__dirname, 'assets', 'MapLauncherAppIcon.icns'),
    path.join(__dirname, 'build', 'icon.icns'),
  ];
  if (repoRoot) {
    candidates.push(path.join(repoRoot, '.tmp-map-editor-app-build', 'map-launcher-1024.png'));
    candidates.push(path.join(repoRoot, '.tmp-map-editor-app-build', 'MapLauncherAppIcon.icns'));
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

configureAppIdentity();

/** Whitelisted launch targets surfaced in the Map Launcher tab. */
const MAP_LAUNCHERS = [
  {
    id: 'matrix-battle-64',
    title: 'Matrix Battle 64',
    description: 'Deploy matrix_battle_64 to uff slot — 50 sims, teams Combat, Dark difficulty.',
    script: 'scripts/play-matrix-battle.sh',
    logPath: 'journal/map_learn/.matrix_battle_64_test.log',
    category: 'matrix',
    options: [
      { key: 'numSims', flag: '--num-sims', type: 'number', label: 'Simulants', default: 50, min: 1, max: 64 },
      { key: 'noPlay', flag: '--no-play', type: 'checkbox', label: 'Deploy only (no play)' },
    ],
  },
  {
    id: 'matrix-laptop-sentry',
    title: 'Matrix Laptop Sentry',
    description: 'matrix_battle_sentry with --laptop-sentry-x4 and unlimited deploys.',
    script: 'scripts/play-matrix-laptop-sentry.sh',
    logPath: 'journal/map_learn/.matrix_battle_sentry_test.log',
    category: 'matrix',
    options: [
      { key: 'numSims', flag: '--num-sims', type: 'number', label: 'Simulants', default: 50, min: 1, max: 64 },
      { key: 'noPlay', flag: '--no-play', type: 'checkbox', label: 'Deploy only (no play)' },
    ],
  },
  {
    id: 'matrix-sentry-unlimited',
    title: 'Matrix Sentry Unlimited',
    description: 'matrix_battle_sentry_inf — infinite sentry ammo + unlimited deploys.',
    script: 'scripts/play-matrix-sentry-unlimited.sh',
    logPath: 'journal/map_learn/.matrix_battle_sentry_inf_test.log',
    category: 'matrix',
    options: [
      { key: 'numSims', flag: '--num-sims', type: 'number', label: 'Simulants', default: 50, min: 1, max: 64 },
      { key: 'noPlay', flag: '--no-play', type: 'checkbox', label: 'Deploy only (no play)' },
    ],
  },
  {
    id: 'war-colors-sentry',
    title: 'War Colors / Conker Sentry',
    description: 'STAGE_EXTRA26 (bg_mp13) — retail spawn pads, mod_kakariko seg/tiles, sentry flags.',
    script: 'scripts/play-conker-war-sentry.sh',
    logPath: 'journal/map_learn/.conker_war_sentry_inf_test.log',
    category: 'war',
    options: [
      { key: 'solo', flag: '--solo', type: 'checkbox', label: 'Solo (human only, spawn smoke test)' },
      { key: 'fullBattle', flag: '--full-battle', type: 'checkbox', label: 'Full battle (50 sims)' },
      { key: 'numSims', flag: '--num-sims', type: 'number', label: 'Simulants', default: 8, min: 1, max: 64 },
      { key: 'noPlay', flag: '--no-play', type: 'checkbox', label: 'Setup only (no play)' },
      { key: 'clean', flag: '--clean', type: 'checkbox', label: 'Purge mp13 overrides only' },
    ],
  },
  {
    id: 'launch-aio-mod',
    title: 'Launch AIO Mod (Retail Menu)',
    description: 'Full all-in-one mod stack — gex, kakariko, dark noon via retail menu path.',
    script: 'scripts/launch-perfect-dark-aio.sh',
    logPath: null,
    category: 'retail',
    options: [],
  },
  {
    id: 'play-learn-step',
    title: 'Play Learn Step',
    description: 'Deploy and launch the current curriculum step into the uff test slot.',
    script: 'scripts/play-learn-step.sh',
    logPath: 'journal/map_learn/.last_validation_launch.log',
    category: 'curriculum',
    options: [
      { key: 'step', type: 'number', label: 'Curriculum step', default: 1, min: 1, max: 31, positional: true },
      { key: 'noPlay', flag: '--no-play', type: 'checkbox', label: 'Deploy only (no play)' },
    ],
  },
  {
    id: 'validate-next',
    title: 'Validate Next Step',
    description: 'Advance validation state and launch the next curriculum / registered map.',
    script: 'scripts/validate-maps.sh',
    scriptArgs: ['next'],
    logPath: 'journal/map_learn/.last_validation_launch.log',
    category: 'curriculum',
    options: [],
  },
  {
    id: 'play-last-test-map',
    title: 'Play Last Test Map',
    description: 'Re-run the last Map Editor Test/Play launch script.',
    script: 'scripts/play-last-test-map.sh',
    logPath: 'journal/uff_viewer/.last_play.log',
    category: 'editor',
    options: [],
  },
];

/** Curriculum phases for grouped UI (matches journal/map_learn/CURRICULUM.md). */
const CURRICULUM_PHASES = [
  { id: 'spawns', title: 'Spawns & Pads', steps: [1, 2] },
  { id: 'weapons-loadout', title: 'Weapons, Ammo & Loadout', steps: [3, 4, 5] },
  { id: 'bots-waypoints', title: 'Waypoints & Bots', steps: [6] },
  { id: 'koth-ctf', title: 'KOTH & CTF', steps: [7, 8, 9, 10] },
  { id: 'pipeline', title: 'Pipeline & Fixtures', steps: [11, 12, 13, 14, 15, 16, 17, 18] },
  { id: 'match-modes', title: 'Match Modes (Scenarios 1–3)', steps: [19, 20, 21, 22] },
  { id: 'bots-launch', title: 'Bots, Loadout & Boot Stage', steps: [23, 24, 25, 26, 27] },
  { id: 'advanced', title: 'Advanced (Hill, Seg, Hygiene, Cover)', steps: [28, 29, 30, 31] },
];

const CURRICULUM_EXPECTED_COUNT = 31;

/** @type {Array<object>} */
let learnMapLaunchers = [];
/** @type {Array<object>} */
let allMapLaunchers = MAP_LAUNCHERS;

/** Whitelisted learn / pdmap actions (Map Learning tab). */
const LEARN_ACTIONS = {
  startLoop: { script: 'scripts/map-learn-loop.sh', detached: true },
  validateStatus: { script: 'scripts/validate-maps.sh', args: ['status'] },
  validateList: { script: 'scripts/validate-maps.sh', args: ['list'] },
  pdmapValidate: { command: 'python3', args: ['tools/pdmap.py', 'validate', 'my_arena', 'testarena'] },
  pdmapCurriculumGenerate: { command: 'python3', args: ['tools/pdmap.py', 'learn', 'curriculum', 'generate'] },
  pdmapLearnRun: { command: 'python3', args: ['tools/pdmap.py', 'learn', 'run'] },
};

/** @type {BrowserWindow | null} */
let mainWindow = null;
/** Focus requested before app.whenReady (second-instance race). */
let pendingFocus = false;
/** @type {string} */
let repoRoot = '';
/** @type {string} */
let logFile = '';

function log(...args) {
  const line = `[${new Date().toISOString().slice(0, 19).replace('T', ' ')}] [map-launcher] ${args.join(' ')}`;
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

function normalizeRepoRoot(raw) {
  if (!raw) return '';
  return raw.trim().replace(/\/Library\/MobileDocuments\//g, '/Library/Mobile Documents/');
}

/** repo-config.json is written by scripts/launch-map-launcher.sh (open(1) drops env vars). */
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

function readVersionFile(fileName) {
  try {
    return fs.readFileSync(path.join(repoRoot, fileName), 'utf8').trim();
  } catch {
    return '0.0.0';
  }
}

function learnDir() {
  return path.join(repoRoot, 'journal', 'map_learn');
}

function scenarioLabel(scenario) {
  const labels = {
    0: 'Combat',
    1: 'Hold Briefcase',
    2: 'Hacker Central',
    3: 'Pop a Cap',
    4: 'KOTH',
    5: 'CTF',
  };
  return labels[scenario] ?? `Scenario ${scenario}`;
}

function phaseIdForStep(stepNum) {
  for (const phase of CURRICULUM_PHASES) {
    if (phase.steps.includes(stepNum)) return phase.id;
  }
  return 'other';
}

/** Bundled static manifest (regenerate via scripts/generate-curriculum-manifest.sh). */
function bundledCurriculumManifestPath() {
  return path.join(__dirname, 'curriculum-manifest.json');
}

function loadCurriculumManifestFromBundledJson() {
  const manifestPath = bundledCurriculumManifestPath();
  try {
    const raw = fs.readFileSync(manifestPath, 'utf8');
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length === 0) {
      log(`Bundled curriculum manifest empty: ${manifestPath}`);
      return [];
    }
    log(`Loaded ${parsed.length} curriculum entries from bundled manifest`);
    return parsed;
  } catch (err) {
    log(`Bundled curriculum manifest unavailable (${manifestPath}): ${err}`);
    return [];
  }
}

function loadCurriculumManifestFallback() {
  const mapsDir = path.join(learnDir(), 'maps');
  try {
    const rows = fs
      .readdirSync(mapsDir)
      .filter((name) => /^learn_\d{2}_.+\.json$/.test(name))
      .map((fileName) => {
        const match = fileName.match(/^learn_(\d{2})_(.+)\.json$/);
        const step = parseInt(match[1], 10);
        return {
          step,
          name: fileName.replace(/\.json$/, ''),
          title: match[2].replace(/_/g, ' '),
          expected: '',
          scenario: 0,
          segMode: 'empty',
          jsonPath: path.join('journal/map_learn/maps', fileName),
        };
      })
      .sort((a, b) => a.step - b.step);
    if (rows.length > 0) {
      log(`Loaded ${rows.length} curriculum entries from journal/map_learn/maps scan`);
    }
    return rows;
  } catch (err) {
    log(`Curriculum fallback scan failed: ${err}`);
    return [];
  }
}

function loadCurriculumManifestFromPython() {
  if (!repoRoot) return [];
  const py = `
import json
from tools.pdmap.learn.curriculum import curriculum_steps
rows = []
for step in curriculum_steps():
    rows.append({
        "step": step.step,
        "name": step.name,
        "title": step.title,
        "expected": step.expected,
        "scenario": step.scenario,
        "segMode": step.seg_mode,
        "jsonPath": f"journal/map_learn/maps/{step.name}.json",
    })
print(json.dumps(rows))
`;
  try {
    const raw = execFileSync('python3', ['-c', py], {
      cwd: repoRoot,
      encoding: 'utf8',
      env: { ...process.env, PD_REPO_ROOT: repoRoot },
      maxBuffer: 1024 * 1024,
    });
    const parsed = JSON.parse(raw.trim());
    if (!Array.isArray(parsed) || parsed.length === 0) {
      return [];
    }
    log(`Loaded ${parsed.length} curriculum entries via python (curriculum.py)`);
    return parsed;
  } catch (err) {
    log(`Curriculum manifest via python failed: ${err}`);
    return [];
  }
}

/** Python → bundled JSON → on-disk learn_*.json scan (in that order). */
function loadCurriculumManifest() {
  const fromPython = loadCurriculumManifestFromPython();
  if (fromPython.length > 0) return fromPython;

  const fromBundled = loadCurriculumManifestFromBundledJson();
  if (fromBundled.length > 0) return fromBundled;

  return loadCurriculumManifestFallback();
}

function buildLearnMapLaunchers(manifest) {
  return manifest.map((entry) => {
    const step = entry.step;
    const padded = String(step).padStart(2, '0');
    return {
      id: `learn-step-${padded}`,
      title: `Step ${step}: ${entry.title}`,
      description: entry.expected || entry.title,
      script: 'scripts/play-learn-step.sh',
      logPath: 'journal/map_learn/.last_validation_launch.log',
      category: 'learn',
      phase: phaseIdForStep(step),
      step,
      mapName: entry.name,
      scenario: entry.scenario,
      scenarioLabel: scenarioLabel(entry.scenario),
      segMode: entry.segMode || 'empty',
      jsonPath: entry.jsonPath,
      options: [
        { key: 'noPlay', flag: '--no-play', type: 'checkbox', label: 'Deploy only (no play)' },
      ],
    };
  });
}

function initLearnMapLaunchers() {
  const manifest = loadCurriculumManifest();
  learnMapLaunchers = buildLearnMapLaunchers(manifest);
  allMapLaunchers = [...MAP_LAUNCHERS, ...learnMapLaunchers];
  log(`Loaded ${learnMapLaunchers.length}/${CURRICULUM_EXPECTED_COUNT} curriculum map launchers`);
}

function serializeMapLauncher(entry) {
  const jsonFull = entry.jsonPath ? path.join(repoRoot, entry.jsonPath) : '';
  return {
    id: entry.id,
    title: entry.title,
    description: entry.description,
    category: entry.category,
    phase: entry.phase || null,
    step: entry.step ?? null,
    mapName: entry.mapName || null,
    scenario: entry.scenario ?? null,
    scenarioLabel: entry.scenarioLabel || null,
    segMode: entry.segMode || null,
    jsonPath: entry.jsonPath || null,
    jsonExists: entry.jsonPath ? fs.existsSync(jsonFull) : null,
    script: entry.script,
    logPath: entry.logPath,
    options: entry.options || [],
    scriptExists: Boolean(resolveScript(entry.script)),
  };
}

function getCurriculumInfo() {
  const steps = learnMapLaunchers.map(serializeMapLauncher);
  const phases = CURRICULUM_PHASES.map((phase) => ({
    id: phase.id,
    title: phase.title,
    steps: phase.steps
      .map((stepNum) => steps.find((entry) => entry.step === stepNum))
      .filter(Boolean),
  }));
  return {
    expectedCount: CURRICULUM_EXPECTED_COUNT,
    totalCount: steps.length,
    complete: steps.length === CURRICULUM_EXPECTED_COUNT,
    phases,
    steps,
  };
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

function resolveWarColorsSimOptions(opts) {
  const resolved = { ...opts };

  // Solo and full-battle are mutually exclusive presets; never emit conflicting flags.
  if (resolved.solo) {
    resolved.fullBattle = false;
    resolved.numSims = 0;
    return resolved;
  }
  if (resolved.fullBattle) {
    resolved.numSims = 50;
    return resolved;
  }

  const sims = Number(resolved.numSims);
  if (!Number.isFinite(sims) || sims < 1) {
    resolved.numSims = 8;
  }
  return resolved;
}

function buildScriptArgs(mapDef, options) {
  const args = [...(mapDef.scriptArgs || [])];
  let opts = options || {};

  if (mapDef.id === 'war-colors-sentry') {
    opts = resolveWarColorsSimOptions(opts);
  }

  if (mapDef.step != null) {
    args.unshift(String(mapDef.step));
  }

  for (const opt of mapDef.options || []) {
    if (opt.positional && opt.key === 'step') {
      if (mapDef.step != null) continue;
      args.unshift(String(opts.step ?? opt.default ?? 1));
      continue;
    }
    if (opt.type === 'checkbox') {
      if (opts[opt.key]) args.push(opt.flag);
      continue;
    }
    if (opt.type === 'number' && opt.flag) {
      // Solo mode: --solo zeroes sims in bootmp; omit --num-sims to avoid confusion.
      if (mapDef.id === 'war-colors-sentry' && opt.key === 'numSims' && opts.solo) {
        continue;
      }
      const value = opts[opt.key];
      if (value !== undefined && value !== null && value !== '') {
        args.push(opt.flag, String(value));
      }
    }
  }

  return args;
}

function runScript(scriptRel, args, options) {
  const scriptPath = resolveScript(scriptRel);
  if (!scriptPath) {
    return Promise.resolve({ ok: false, error: `Script not found or not whitelisted: ${scriptRel}` });
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
      log(`Started detached ${scriptRel} pid=${child.pid}`);
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
      resolve({ ok: code === 0, code, output: output.slice(-8000) });
    });
  });
}

function runCommand(command, args) {
  return new Promise((resolve) => {
    const child = spawn(command, args || [], {
      cwd: repoRoot,
      env: { ...process.env, PD_REPO_ROOT: repoRoot },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let output = '';
    child.stdout.on('data', (chunk) => {
      output += String(chunk);
    });
    child.stderr.on('data', (chunk) => {
      output += String(chunk);
    });
    child.on('close', (code) => {
      resolve({ ok: code === 0, code, output: output.slice(-8000) });
    });
  });
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

function isProcessAlive(pid) {
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function findGamePids() {
  const binary = gameBinaryPath();
  const pids = [];
  try {
    const raw = execFileSync('pgrep', ['-x', 'pd.arm64'], { encoding: 'utf8' });
    for (const line of raw.split('\n')) {
      const pid = parseInt(line.trim(), 10);
      if (!Number.isFinite(pid)) continue;
      try {
        const cmd = execFileSync('ps', ['-p', String(pid), '-o', 'command='], { encoding: 'utf8' }).trim();
        if (cmd.includes(binary)) {
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

function getGameStatus() {
  const lastPid = readPidFile('journal/map_learn/.last_play.pid');
  const running = findGamePids();
  const lastAlive = isProcessAlive(lastPid);
  return {
    lastPid,
    lastAlive,
    running,
    binary: gameBinaryPath(),
    binaryBuilt: fs.existsSync(gameBinaryPath()),
  };
}

function tailLog(relativePath, lineCount) {
  const count = Math.min(Math.max(lineCount || 40, 1), 500);
  const fullPath = path.join(repoRoot, relativePath || '');
  if (!fullPath.startsWith(repoRoot) || !fs.existsSync(fullPath)) {
    return { ok: false, error: 'Log file not found', path: relativePath };
  }
  try {
    const content = fs.readFileSync(fullPath, 'utf8');
    const lines = content.split('\n');
    const tail = lines.slice(-count).join('\n');
    return { ok: true, path: relativePath, lines: tail, size: content.length };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

function readLearnRuns(limit) {
  const runsDir = path.join(learnDir(), 'runs');
  const max = limit || 12;
  try {
    const files = fs
      .readdirSync(runsDir)
      .filter((name) => name.endsWith('.json'))
      .map((name) => {
        const full = path.join(runsDir, name);
        const stat = fs.statSync(full);
        let summary = null;
        try {
          summary = JSON.parse(fs.readFileSync(full, 'utf8'));
        } catch {
          summary = { run_id: name.replace('.json', ''), parseError: true };
        }
        return {
          file: name,
          path: path.join('journal/map_learn/runs', name),
          mtime: stat.mtime.toISOString(),
          summary,
        };
      })
      .sort((a, b) => (a.mtime < b.mtime ? 1 : -1))
      .slice(0, max);
    return files;
  } catch {
    return [];
  }
}

function getLearnStatus() {
  const loopPid = readPidFile('journal/map_learn/.learn-loop.pid');
  const loopAlive = isProcessAlive(loopPid);
  let validationStep = '0';
  try {
    validationStep = fs.readFileSync(path.join(learnDir(), '.validation_step'), 'utf8').trim();
  } catch {
    // default
  }
  let state = null;
  try {
    state = JSON.parse(fs.readFileSync(path.join(learnDir(), 'state.json'), 'utf8'));
  } catch {
    state = null;
  }
  const loopLog = tailLog('journal/map_learn/loop.log', 20);
  const internalLog = tailLog('journal/map_learn/.loop-internal.log', 15);
  return {
    loopPid,
    loopAlive,
    validationStep,
    state,
    loopLog: loopLog.ok ? loopLog.lines : '',
    internalLog: internalLog.ok ? internalLog.lines : '',
    recentRuns: readLearnRuns(10),
    curriculumDoc: 'journal/map_learn/CURRICULUM.md',
    learnPlanDoc: 'journal/map_learn/LEARN_PLAN.md',
  };
}

function killGame() {
  const status = getGameStatus();
  let killed = [];

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
  return { ok: true, killed, status: getGameStatus() };
}

function stopLearnLoop() {
  const loopPid = readPidFile('journal/map_learn/.learn-loop.pid');
  if (!loopPid || !isProcessAlive(loopPid)) {
    return { ok: true, stopped: false, message: 'Learn loop is not running' };
  }
  try {
    process.kill(loopPid, 'SIGTERM');
    log(`Stopped learn loop pid=${loopPid}`);
    return { ok: true, stopped: true, pid: loopPid };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

function launcherById(mapId) {
  return allMapLaunchers.find((entry) => entry.id === mapId) || null;
}

function registerIpc() {
  ipcMain.handle('launcher:get-info', () => ({
    title: APP_TITLE,
    kitVersion: readVersionFile('KIT_VERSION'),
    portVersion: readVersionFile('PORT_VERSION'),
    repoRoot,
    game: getGameStatus(),
    maps: MAP_LAUNCHERS.map((entry) => serializeMapLauncher(entry)),
    curriculum: getCurriculumInfo(),
    learn: getLearnStatus(),
  }));

  ipcMain.handle('launcher:launch-map', async (_event, mapId, options) => {
    const mapDef = launcherById(mapId);
    if (!mapDef) {
      return { ok: false, error: `Unknown map launcher: ${mapId}` };
    }
    if (!fs.existsSync(gameBinaryPath()) && mapDef.id !== 'play-last-test-map') {
      return { ok: false, error: `Game binary missing: ${gameBinaryPath()}. Run make -j8 first.` };
    }
    const args = buildScriptArgs(mapDef, options);
    log(`Launch ${mapId}: ${mapDef.script} ${args.join(' ')}`);
    const result = await runScript(mapDef.script, args, { detached: true });
    if (!result.ok) return result;

    // Give scripts time to write .last_play.pid on macOS Terminal launch path.
    await new Promise((r) => setTimeout(r, 1500));
    return {
      ...result,
      game: getGameStatus(),
      logPath: mapDef.logPath,
      logTail: mapDef.logPath ? tailLog(mapDef.logPath, 30) : null,
    };
  });

  ipcMain.handle('launcher:kill-game', () => killGame());
  ipcMain.handle('launcher:game-status', () => getGameStatus());
  ipcMain.handle('launcher:tail-log', (_event, logPath, lines) => tailLog(logPath, lines));

  ipcMain.handle('launcher:start-learn-loop', async () => {
    const status = getLearnStatus();
    if (status.loopAlive) {
      return { ok: true, alreadyRunning: true, pid: status.loopPid };
    }
    return runScript(LEARN_ACTIONS.startLoop.script, [], { detached: true });
  });

  ipcMain.handle('launcher:stop-learn-loop', () => stopLearnLoop());

  ipcMain.handle('launcher:learn-status', () => getLearnStatus());

  ipcMain.handle('launcher:run-learn-action', async (_event, action, extraArgs) => {
    const def = LEARN_ACTIONS[action];
    if (!def) {
      return { ok: false, error: `Unknown learn action: ${action}` };
    }
    log(`Learn action ${action}`);
    if (def.script) {
      return runScript(def.script, [...(def.args || []), ...(extraArgs || [])]);
    }
    if (def.command) {
      return runCommand(def.command, def.args);
    }
    return { ok: false, error: 'Action misconfigured' };
  });

  ipcMain.handle('launcher:reveal-path', async (_event, targetPath) => {
    const resolved = path.isAbsolute(targetPath) ? targetPath : path.join(repoRoot, targetPath);
    if (!fs.existsSync(resolved)) {
      return { ok: false, error: 'Path not found' };
    }
    shell.showItemInFolder(resolved);
    return { ok: true };
  });

  ipcMain.handle('launcher:open-doc', async (_event, relativePath) => {
    const docPath = path.join(repoRoot, relativePath);
    if (!docPath.startsWith(repoRoot) || !fs.existsSync(docPath)) {
      return { ok: false, error: `Doc not found: ${relativePath}` };
    }
    const err = await shell.openPath(docPath);
    if (err) return { ok: false, error: err };
    return { ok: true };
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 900,
    minWidth: 960,
    minHeight: 680,
    title: APP_TITLE,
    icon: appIcon || undefined,
    backgroundColor: '#0b0d12',
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
  mainWindow.once('ready-to-show', () => {
    log('Window ready-to-show');
    focusMainWindow();
  });
  // Fallback: some macOS/GPU paths never emit ready-to-show when show:false was used.
  const showFallback = setTimeout(() => {
    if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
      log('WARNING: forcing window visible (ready-to-show fallback)');
      focusMainWindow();
    }
  }, 2500);
  mainWindow.once('show', () => clearTimeout(showFallback));
  mainWindow.webContents.on('did-fail-load', (_event, code, description, url) => {
    log(`ERROR: did-fail-load code=${code} url=${url} ${description}`);
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

/** Bring the launcher window (and Dock tile) to the foreground on macOS. */
function focusMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    createWindow();
    return;
  }
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  if (!mainWindow.isVisible()) {
    mainWindow.center();
  }
  mainWindow.show();
  mainWindow.focus();
  if (process.platform === 'darwin') {
    if (app.dock) {
      app.dock.show();
    }
    app.focus({ steal: true });
  }
}

/** Defer focus until after app.whenReady (second-instance can arrive early). */
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
  logFile = path.join(
    app.getPath('home'),
    'Library',
    'Logs',
    'PerfectDarkKit',
    LOG_FILE_NAME
  );
  applyAppIcon();
  if (!repoRoot) {
    log('WARNING: repo root not resolved — curriculum uses bundled manifest only');
  } else {
    log(`REPO_ROOT=${repoRoot}`);
  }
  registerIpc();
  createWindow();
  initLearnMapLaunchers();
  if (pendingFocus) {
    pendingFocus = false;
    focusMainWindow();
  }
});

app.on('activate', () => {
  focusMainWindow();
});

app.on('window-all-closed', () => {
  app.quit();
});
