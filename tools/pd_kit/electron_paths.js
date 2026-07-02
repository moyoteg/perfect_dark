'use strict';

/**
 * Shared Perfect Dark Kit paths for Electron shells.
 * Reads tools/pd_kit/kit.json relative to the repo root.
 */

const fs = require('fs');
const path = require('path');

/** @type {Record<string, unknown> | null} */
let cachedManifest = null;

function discoverRepoRoot(startDir) {
  let candidate = path.resolve(startDir);
  for (let i = 0; i < 14; i += 1) {
    const manifest = path.join(candidate, 'tools', 'pd_kit', 'kit.json');
    if (fs.existsSync(manifest)) {
      return candidate;
    }
    const parent = path.dirname(candidate);
    if (parent === candidate) break;
    candidate = parent;
  }
  return '';
}

function loadManifest() {
  if (cachedManifest) return cachedManifest;
  const roots = [
    process.env.PD_REPO_ROOT,
    discoverRepoRoot(__dirname),
    discoverRepoRoot(process.cwd()),
  ].filter(Boolean);
  for (const root of roots) {
    const manifestPath = path.join(root, 'tools', 'pd_kit', 'kit.json');
    try {
      cachedManifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
      return cachedManifest;
    } catch {
      // try next root
    }
  }
  cachedManifest = {
    name: 'Perfect Dark Kit',
    supportDirName: 'PerfectDarkKit',
    logsDirName: 'PerfectDarkKit',
    apps: {
      kitHub: {
        id: 'kit-hub',
        productName: 'Perfect Dark Kit',
        shortTitle: 'Kit',
        bundleFileName: 'Perfect Dark Kit.app',
        logFile: 'kit-hub.log',
      },
      mapEditor: {
        id: 'map-editor',
        productName: 'PD Map Editor',
        shortTitle: 'Map Editor',
        bundleFileName: 'PD Map Editor.app',
        logFile: 'map-editor.log',
        legacySupportDir: 'PerfectDarkMapEditor',
      },
      animLab: {
        id: 'anim-lab',
        productName: 'PD Anim Lab',
        shortTitle: 'Anim Lab',
        bundleFileName: 'PD Anim Lab.app',
        logFile: 'anim-lab.log',
        legacySupportDir: 'PerfectDarkAnimLab',
      },
      assetUpgrader: {
        id: 'asset-upgrader',
        productName: 'PD Asset Upgrader',
        shortTitle: 'Asset Upgrader',
        bundleFileName: 'PD Asset Upgrader.app',
        logFile: 'asset-upgrader.log',
      },
      playLastTestMap: {
        id: 'play-last-test-map',
        productName: 'Play Last Test Map',
        shortTitle: 'Replay Test',
        bundleFileName: 'Play Last Test Map.app',
        logFile: 'play-last-test-map.log',
        optional: true,
      },
      llmPlay: {
        id: 'llm-play',
        productName: 'LLM Play',
        shortTitle: 'LLM Play',
        bundleFileName: 'LLM Play.app',
        logFile: 'llm-play.log',
        optional: true,
        siblingPath: '../llm-play/LLM Play.app',
      },
    },
  };
  return cachedManifest;
}

function readVersionFile(repoRoot, fileName) {
  if (!repoRoot) return '';
  try {
    return fs.readFileSync(path.join(repoRoot, fileName), 'utf8').trim();
  } catch {
    return '';
  }
}

function kitVersion(repoRoot) {
  if (process.env.PD_KIT_VERSION) return process.env.PD_KIT_VERSION;
  return readVersionFile(repoRoot, 'KIT_VERSION') || '0.0.0';
}

function portVersion(repoRoot) {
  if (process.env.PD_PORT_VERSION) return process.env.PD_PORT_VERSION;
  return readVersionFile(repoRoot, 'PORT_VERSION') || '0.0.0';
}

function appConfig(componentKey) {
  const manifest = loadManifest();
  const apps = manifest.apps || {};
  const cfg = apps[componentKey];
  if (!cfg) {
    throw new Error(`Unknown kit component: ${componentKey}`);
  }
  return cfg;
}

function kitSupportRoot(homeDir) {
  const manifest = loadManifest();
  return path.join(
    homeDir,
    'Library',
    'Application Support',
    manifest.supportDirName || 'PerfectDarkKit'
  );
}

function kitLogsRoot(homeDir) {
  const manifest = loadManifest();
  return path.join(homeDir, 'Library', 'Logs', manifest.logsDirName || 'PerfectDarkKit');
}

function kitLogFile(homeDir, componentKey) {
  const cfg = appConfig(componentKey);
  const root = kitLogsRoot(homeDir);
  fs.mkdirSync(root, { recursive: true });
  return path.join(root, cfg.logFile || `${cfg.id || componentKey}.log`);
}

function kitSupportDir(homeDir, componentKey) {
  const cfg = appConfig(componentKey);
  const dir = path.join(kitSupportRoot(homeDir), cfg.id || componentKey);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function legacySupportDir(homeDir, componentKey) {
  const cfg = appConfig(componentKey);
  if (!cfg.legacySupportDir) return '';
  return path.join(homeDir, 'Library', 'Application Support', cfg.legacySupportDir);
}

function resolveKitStateDir(homeDir, componentKey, repoPath, repoRelativePath, envVarName) {
  const envState = (process.env[envVarName] || '').trim();
  if (envState) {
    fs.mkdirSync(envState, { recursive: true });
    return envState;
  }

  const repoDir = path.join(repoPath, repoRelativePath);
  try {
    const probe = path.join(repoDir, '.pd_kit_write_probe');
    fs.writeFileSync(probe, 'ok', 'utf8');
    fs.unlinkSync(probe);
    return repoDir;
  } catch {
    // fall through
  }

  const kitDir = kitSupportDir(homeDir, componentKey);
  const legacy = legacySupportDir(homeDir, componentKey);
  if (legacy && fs.existsSync(legacy)) {
    try {
      if (fs.readdirSync(kitDir).length === 0 && fs.readdirSync(legacy).length > 0) {
        return legacy;
      }
    } catch {
      // ignore
    }
  }
  return kitDir;
}

module.exports = {
  loadManifest,
  discoverRepoRoot,
  kitVersion,
  portVersion,
  appConfig,
  kitLogFile,
  kitSupportDir,
  resolveKitStateDir,
  requireKitModule,
};

function requireKitModule(moduleName) {
  const candidates = [
    path.join(__dirname, moduleName),
    path.join(process.resourcesPath || '', 'pd_kit', moduleName),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return require(candidate);
    }
  }
  throw new Error(`Perfect Dark Kit module not found: ${moduleName}`);
}
