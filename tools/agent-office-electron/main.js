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
const WORKSPACE_CONFIG = 'journal/agent_office/workspace_config.json';
const TENANTS_REGISTRY = 'journal/agent_office/tenants.json';
const OFFICE_API_PORT = process.env.AGENT_OFFICE_API_PORT || '8791';
const OFFICE_API_BASE = `http://127.0.0.1:${OFFICE_API_PORT}`;
/** Pass 27: Slack OAuth browser redirect lands on Office Service GET callback. */
const SLACK_OAUTH_REDIRECT_URI = `${OFFICE_API_BASE}/slack/oauth/callback`;
const SLACK_OAUTH_BROWSER_POLL_MS = 1500;
const SLACK_OAUTH_BROWSER_TIMEOUT_MS = 5 * 60 * 1000;

/** Active Office Service tenant (MULTI_TENANT.md). Defaults to migration tenant. */
let currentTenantId = String(process.env.OFFICE_TENANT_ID || 'default').trim() || 'default';

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
  ci_lobby: {
    id: 'ci_lobby',
    label: 'Carrington Institute (Fresh / Lobby)',
    eyebrow: 'Perfect Dark · CI retail lobby',
    bootStage: '0x26',
    launchMatch: '--agent-office-ci-lobby',
    script: 'scripts/play-agent-office-ci-lobby.sh',
    logDir: 'journal/agent_office_ci',
    deployLog: 'journal/agent_office_ci/.last_launch_lobby.log',
    pidFile: 'journal/agent_office_ci/.last_play_lobby.pid',
    mapName: 'agent_office_ci',
    layoutImport: 'from tools.pdmap.agent_office_ci import agent_office_ci_layout_payload',
  },
  lab: {
    id: 'lab',
    label: 'Office Lab / Matrix',
    eyebrow: 'Perfect Dark · Matrix sandbox',
    bootStage: '0x85',
    script: 'scripts/play-agent-office-lab.sh',
    logDir: 'journal/agent_office_lab',
    deployLog: 'journal/agent_office_lab/.last_launch.log',
    pidFile: 'journal/agent_office_lab/.last_play.pid',
    mapName: 'agent_office_lab',
    layoutImport: 'from tools.pdmap.agent_office_lab import agent_office_lab_layout_payload',
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
  } catch (err) {
    process.stderr.write(`[agent-office] log write failed: ${err?.message || err}\n`);
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
    } catch (err) {
      log(`Skipped unreadable repo config ${cfgPath}: ${err?.message || err}`);
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

function workspaceConfigPath() {
  return path.join(repoRoot, WORKSPACE_CONFIG);
}

/** Build workspace config via Python helper (keeps channel map in sync with Office Service). */
function buildWorkspaceConfigPy(locationKey, displayName, codename) {
  const py = `
import json, sys
sys.path.insert(0, "tools/agent_office_llm")
from service.workspace_config import build_workspace_config, save_workspace_config
loc = sys.argv[1]
name = sys.argv[2]
code = sys.argv[3]
cfg = build_workspace_config(loc, name, code)
path = save_workspace_config(cfg)
print(json.dumps({"ok": True, "path": str(path), "config": cfg}))
`;
  try {
    const raw = execFileSync('python3', ['-c', py, locationKey, displayName, codename || ''], {
      cwd: repoRoot,
      encoding: 'utf8',
      env: { ...process.env, PD_REPO_ROOT: repoRoot },
      maxBuffer: 256 * 1024,
    });
    return JSON.parse(raw.trim());
  } catch (err) {
    log(`Workspace config build failed: ${err}`);
    return { ok: false, error: String(err) };
  }
}

function loadWorkspaceConfigFile() {
  const full = workspaceConfigPath();
  if (!fs.existsSync(full)) {
    return { ok: false, error: 'Workspace config not found' };
  }
  try {
    const config = JSON.parse(fs.readFileSync(full, 'utf8'));
    return { ok: true, path: WORKSPACE_CONFIG, config };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

function saveWorkspaceConfig(locationKey, displayName, codename) {
  if (!repoRoot) {
    return { ok: false, error: 'Repo root not resolved' };
  }
  const name = String(displayName || '').trim();
  if (!name) {
    return { ok: false, error: 'display_name is required' };
  }
  return buildWorkspaceConfigPy(normalizeLocation(locationKey), name, String(codename || '').trim());
}

function normalizeTenantId(raw) {
  const value = String(raw || '')
    .trim()
    .toLowerCase();
  if (!value || !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(value)) {
    return 'default';
  }
  return value;
}

function loadTenantsRegistry() {
  const fallback = [
    {
      id: 'default',
      display_name: 'Default Office',
      default_location: 'g5',
      cast: 'standard8',
    },
  ];
  if (!repoRoot) {
    return { ok: true, tenants: fallback, active: currentTenantId };
  }
  const full = path.join(repoRoot, TENANTS_REGISTRY);
  try {
    if (!fs.existsSync(full)) {
      return { ok: true, tenants: fallback, active: currentTenantId, path: full };
    }
    const parsed = JSON.parse(fs.readFileSync(full, 'utf8'));
    const rows = Array.isArray(parsed?.tenants) ? parsed.tenants : [];
    const tenants = rows
      .map((row) => ({
        id: normalizeTenantId(row?.id),
        display_name: String(row?.display_name || row?.id || 'Office').trim() || 'Office',
        default_location: String(row?.default_location || 'g5').trim() || 'g5',
        cast: String(row?.cast || 'standard8').trim() || 'standard8',
        notes: String(row?.notes || ''),
      }))
      .filter((row) => row.id);
    return {
      ok: true,
      tenants: tenants.length ? tenants : fallback,
      active: currentTenantId,
      path: full,
    };
  } catch (err) {
    return { ok: false, error: String(err), tenants: fallback, active: currentTenantId };
  }
}

function setCurrentTenant(tenantId) {
  currentTenantId = normalizeTenantId(tenantId);
  process.env.OFFICE_TENANT_ID = currentTenantId;
  return { ok: true, tenant: currentTenantId, ...loadTenantsRegistry() };
}

function officeApiHeaders(extra = {}) {
  return {
    'X-Office-Tenant': currentTenantId || 'default',
    ...extra,
  };
}

/** Pass 26: Slack OAuth install status from Office Service. */
async function fetchSlackOAuthStatus() {
  try {
    const response = await fetch(`${OFFICE_API_BASE}/slack/oauth/status`, {
      headers: officeApiHeaders(),
      signal: AbortSignal.timeout(2500),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 27: begin Slack OAuth with browser redirect_uri on Office Service. */
async function beginSlackOAuthInstall() {
  try {
    const response = await fetch(`${OFFICE_API_BASE}/slack/oauth/begin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ redirect_uri: SLACK_OAUTH_REDIRECT_URI }),
      signal: AbortSignal.timeout(5000),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 25/26: POST callback — retained for headless tests and manual curl completion. */
async function completeSlackOAuthInstall(code, state) {
  const codeText = String(code || '').trim();
  const stateText = String(state || '').trim();
  if (!codeText || !stateText) {
    return { ok: false, error: 'code and state are required' };
  }
  try {
    const response = await fetch(`${OFFICE_API_BASE}/slack/oauth/callback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: codeText, state: stateText }),
      signal: AbortSignal.timeout(5000),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Pass 27: open Slack authorize URL in system browser; poll until GET callback completes install. */
async function connectSlackOAuthBrowser() {
  const begin = await beginSlackOAuthInstall();
  if (!begin.ok) {
    return begin;
  }
  const authUrl = String(begin.authorization_url || '').trim();
  if (!authUrl) {
    return { ok: false, error: 'missing authorization_url from /slack/oauth/begin' };
  }

  const opened = await shell.openExternal(authUrl);
  if (opened) {
    return { ok: false, error: `could not open browser: ${opened}` };
  }

  const deadline = Date.now() + SLACK_OAUTH_BROWSER_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await sleep(SLACK_OAUTH_BROWSER_POLL_MS);
    const status = await fetchSlackOAuthStatus();
    if (!status.ok) {
      continue;
    }
    if (status.status === 'installed') {
      return { ok: true, status: status.status, install: status };
    }
    if (status.status === 'awaiting_security_approval') {
      return {
        ok: true,
        status: status.status,
        awaitingSecurityApproval: true,
        install: status,
      };
    }
    if (status.status === 'revoked') {
      return { ok: false, error: 'OAuth install was revoked before completion' };
    }
  }

  return {
    ok: false,
    error: 'OAuth timed out — finish authorize in browser or retry Connect Slack',
    pending: true,
  };
}

/** Pass 26: revoke Slack OAuth install and revert to local-first. */
async function disconnectSlackOAuthInstall() {
  try {
    const response = await fetch(`${OFFICE_API_BASE}/slack/oauth/disconnect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
      signal: AbortSignal.timeout(5000),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 30: GET pending Security approval card for Slack token use. */
async function fetchSlackOAuthSecurityApproval() {
  try {
    const response = await fetch(`${OFFICE_API_BASE}/slack/oauth/security-approval`, {
      signal: AbortSignal.timeout(2500),
    });
    if (response.status === 404) {
      return { ok: true, pending: false };
    }
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, pending: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 30: Security desk approve — exchange code and complete Slack install. */
async function approveSlackOAuthSecurity(approvalId, decidedBy = 'electron') {
  const approvalText = String(approvalId || '').trim();
  if (!approvalText) {
    return { ok: false, error: 'approval_id is required' };
  }
  try {
    const response = await fetch(`${OFFICE_API_BASE}/slack/oauth/security-approval/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_id: approvalText, decided_by: decidedBy }),
      signal: AbortSignal.timeout(10000),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 30: Security desk deny — revoke staged install without token exchange. */
async function denySlackOAuthSecurity(approvalId, decidedBy = 'electron') {
  const approvalText = String(approvalId || '').trim();
  if (!approvalText) {
    return { ok: false, error: 'approval_id is required' };
  }
  try {
    const response = await fetch(`${OFFICE_API_BASE}/slack/oauth/security-approval/deny`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_id: approvalText, decided_by: decidedBy }),
      signal: AbortSignal.timeout(5000),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Fetch Slack-shaped channel list from Office Service (Phase 2 unread badges). */
async function fetchSlackChannels() {
  try {
    const response = await fetch(`${OFFICE_API_BASE}/slack/channels`, {
      signal: AbortSignal.timeout(2500),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Mark a channel read via Office Service (clears unread badge). */
async function markSlackChannelRead(channelId) {
  const id = String(channelId || '').trim();
  if (!id) {
    return { ok: false, error: 'channel id is required' };
  }
  try {
    const response = await fetch(`${OFFICE_API_BASE}/slack/channels/${encodeURIComponent(id)}/read`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
      signal: AbortSignal.timeout(2500),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** List persisted walk-up DM threads (Pass 6 sidebar stub). */
async function fetchDmThreads() {
  try {
    const response = await fetch(`${OFFICE_API_BASE}/dm`, {
      signal: AbortSignal.timeout(2500),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Fetch one agent DM thread tail (Pass 6). */
async function fetchDmThread(agentId) {
  const id = String(agentId || '').trim();
  if (!id) {
    return { ok: false, error: 'agent id is required' };
  }
  try {
    const response = await fetch(`${OFFICE_API_BASE}/dm/${encodeURIComponent(id)}`, {
      signal: AbortSignal.timeout(2500),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Mark a DM thread read via Office Service (Pass 8 unread badges). */
async function markDmThreadRead(agentId) {
  const id = String(agentId || '').trim();
  if (!id) {
    return { ok: false, error: 'agent id is required' };
  }
  try {
    const response = await fetch(`${OFFICE_API_BASE}/dm/${encodeURIComponent(id)}/read`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
      signal: AbortSignal.timeout(2500),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 34: list connector gateway approvals from Office Service. */
async function fetchConnectorApprovals() {
  try {
    const response = await fetch(`${OFFICE_API_BASE}/approvals`, {
      signal: AbortSignal.timeout(2500),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, approvals: body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 34: approve pending connector action after human confirms. */
async function approveConnectorApproval(approvalId, decidedBy = 'electron') {
  const id = String(approvalId || '').trim();
  if (!id) {
    return { ok: false, error: 'approval_id is required' };
  }
  try {
    const response = await fetch(`${OFFICE_API_BASE}/approvals/${encodeURIComponent(id)}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decided_by: decidedBy }),
      signal: AbortSignal.timeout(10000),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, task: body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 34: deny pending connector action. */
async function denyConnectorApproval(approvalId, decidedBy = 'electron') {
  const id = String(approvalId || '').trim();
  if (!id) {
    return { ok: false, error: 'approval_id is required' };
  }
  try {
    const response = await fetch(`${OFFICE_API_BASE}/approvals/${encodeURIComponent(id)}/deny`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decided_by: decidedBy }),
      signal: AbortSignal.timeout(5000),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, task: body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 34: dispatch Comms task + stage slack.post_message for human approval. */
async function dispatchConnectorTask(agentId, intent, channel, text) {
  const agent = String(agentId || 'comms').trim();
  const intentText = String(intent || '').trim();
  const channelText = String(channel || '#general').trim() || '#general';
  const bodyText = String(text || '').trim();
  if (!intentText) {
    return { ok: false, error: 'intent is required' };
  }
  if (!bodyText) {
    return { ok: false, error: 'message text is required' };
  }
  try {
    const dispatchRes = await fetch(`${OFFICE_API_BASE}/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent_id: agent,
        intent: intentText,
        created_by: 'electron',
      }),
      signal: AbortSignal.timeout(5000),
    });
    const task = await dispatchRes.json();
    if (!dispatchRes.ok) {
      return { ok: false, error: task?.error || `HTTP ${dispatchRes.status}`, status: dispatchRes.status };
    }
    const performRes = await fetch(`${OFFICE_API_BASE}/tasks/${encodeURIComponent(task.id)}/perform`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        actions: [{
          connector: 'slack',
          action: 'post_message',
          args: { channel: channelText, text: bodyText },
        }],
      }),
      signal: AbortSignal.timeout(5000),
    });
    const performed = await performRes.json();
    if (!performRes.ok) {
      return { ok: false, error: performed?.error || `HTTP ${performRes.status}`, status: performRes.status };
    }
    return {
      ok: true,
      task: performed,
      staged: performed.status === 'awaiting_approval',
    };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 33: post Comms outbound message to Slack via Office Service. */
async function postSlackOutbound(channel, text) {
  const channelText = String(channel || '').trim();
  const bodyText = String(text || '').trim();
  if (!channelText) {
    return { ok: false, error: 'channel is required' };
  }
  if (!bodyText) {
    return { ok: false, error: 'message text is required' };
  }
  try {
    const response = await fetch(`${OFFICE_API_BASE}/slack/outbound/post`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ channel: channelText, text: bodyText }),
      signal: AbortSignal.timeout(8000),
    });
    const body = await response.json();
    if (!response.ok) {
      return {
        ok: false,
        error: body?.error || `HTTP ${response.status}`,
        status: response.status,
        slackStatus: body?.status,
      };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Pass 10: append human DM line from Electron compose (stub agent reply). */
async function appendDmMessage(agentId, text) {
  const id = String(agentId || '').trim();
  const line = String(text || '').trim();
  if (!id) {
    return { ok: false, error: 'agent id is required' };
  }
  if (!line) {
    return { ok: false, error: 'message text is required' };
  }
  try {
    const response = await fetch(`${OFFICE_API_BASE}/dm/${encodeURIComponent(id)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from: 'human', text: line, stub_reply: true }),
      signal: AbortSignal.timeout(5000),
    });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body?.error || `HTTP ${response.status}`, status: response.status };
    }
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

function loadOfficeLayout(locationKey) {
  const loc = LOCATIONS[normalizeLocation(locationKey)];
  const fn = loc.layoutImport.split(' import ')[1] || 'agent_office_layout_payload';
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

function findGamePids(bootStage, launchMatch) {
  const binary = gameBinaryPath();
  const pids = [];
  try {
    const raw = execFileSync('pgrep', ['-x', 'pd.arm64'], { encoding: 'utf8' });
    for (const line of raw.split('\n')) {
      const pid = parseInt(line.trim(), 10);
      if (!Number.isFinite(pid)) continue;
      try {
        const cmd = execFileSync('ps', ['-p', String(pid), '-o', 'command='], { encoding: 'utf8' }).trim();
        if (!cmd.includes(binary) || !cmd.includes('--boot-stage') || !cmd.includes(bootStage)) {
          continue;
        }
        if (launchMatch && !cmd.includes(launchMatch)) {
          continue;
        }
        pids.push({ pid, command: cmd.slice(0, 200) });
      } catch (err) {
        if (process.env.PD_KIT_DEBUG === '1') {
          log(`ps lookup skipped for pid ${pid}: ${err?.message || err}`);
        }
      }
    }
  } catch (err) {
    if (process.env.PD_KIT_DEBUG === '1') {
      log(`pgrep pd.arm64 returned no processes: ${err?.message || err}`);
    }
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

function clearStalePidFile(relativePath, lastPid) {
  if (!lastPid || isProcessAlive(lastPid)) return;
  try {
    fs.unlinkSync(path.join(repoRoot, relativePath));
  } catch (err) {
    if (err && err.code !== 'ENOENT') {
      log(`Stale pid file unlink warning (${relativePath}): ${err.message}`);
    }
  }
}

function processCpuPercent(pid) {
  try {
    const raw = execFileSync('ps', ['-p', String(pid), '-o', '%cpu='], { encoding: 'utf8' }).trim();
    const value = parseFloat(raw);
    return Number.isFinite(value) ? value : 0;
  } catch {
    return 0;
  }
}

/** Hung CI/G5 boots often sit at ~100% CPU in doorsCalcFrac when setup doors are corrupt. */
function isLikelyHungGamePid(pid) {
  if (!pid || !isProcessAlive(pid)) return false;
  return processCpuPercent(pid) >= 90;
}

function getGameStatus(locationKey) {
  const loc = LOCATIONS[normalizeLocation(locationKey)];
  const lastPid = readPidFile(loc.pidFile);
  clearStalePidFile(loc.pidFile, lastPid);
  const running = findGamePids(loc.bootStage, loc.launchMatch);
  const lastAlive = isProcessAlive(lastPid);
  return {
    location: loc.id,
    lastPid: lastAlive ? lastPid : null,
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
      } catch (err) {
        if (process.env.PD_KIT_DEBUG === '1') {
          log(`ps lookup skipped for director pid ${pid}: ${err?.message || err}`);
        }
      }
    }
  } catch (err) {
    if (process.env.PD_KIT_DEBUG === '1') {
      log(`pgrep office_director.py returned no processes: ${err?.message || err}`);
    }
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
    } catch (err) {
      log(`SIGTERM skipped for director pid ${pid}: ${err?.message || err}`);
    }
  }

  try {
    fs.unlinkSync(path.join(repoRoot, DIRECTOR_PID));
  } catch (err) {
    if (err && err.code !== 'ENOENT') {
      log(`Unlink director pid file warning: ${err.message}`);
    }
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
  const pids = new Set();

  if (status.lastPid && status.lastAlive) pids.add(status.lastPid);
  for (const entry of status.running) pids.add(entry.pid);

  for (const pid of pids) {
    try {
      process.kill(pid, 'SIGTERM');
      killed.push(pid);
    } catch (err) {
      log(`SIGTERM skipped for game pid ${pid}: ${err?.message || err}`);
    }
  }

  // Hung door-loop boots may ignore SIGTERM; escalate so relaunch is not blocked.
  for (const pid of pids) {
    if (!isProcessAlive(pid)) continue;
    try {
      process.kill(pid, 'SIGKILL');
      if (!killed.includes(pid)) killed.push(pid);
    } catch (err) {
      log(`SIGKILL skipped for game pid ${pid}: ${err?.message || err}`);
    }
  }

  const loc = LOCATIONS[normalizeLocation(locationKey)];
  try {
    fs.unlinkSync(path.join(repoRoot, loc.pidFile));
  } catch (err) {
    if (err && err.code !== 'ENOENT') {
      log(`Unlink game pid file warning: ${err.message}`);
    }
  }

  log(`Kill game pids: ${killed.join(', ') || '(none)'}`);
  return { ok: true, killed, status: getGameStatus(locationKey) };
}

function registerIpc() {
  ipcMain.handle('office:get-info', (_event, locationKey) => {
    const location = normalizeLocation(locationKey);
    const loc = LOCATIONS[location];
    const tenants = loadTenantsRegistry();
    return {
      title: APP_TITLE,
      kitVersion: readVersionFile('KIT_VERSION'),
      portVersion: readVersionFile('PORT_VERSION'),
      repoRoot,
      location,
      tenant: currentTenantId,
      tenants: tenants.tenants,
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

  ipcMain.handle('office:get-tenants', () => loadTenantsRegistry());
  ipcMain.handle('office:set-tenant', (_event, tenantId) => setCurrentTenant(tenantId));

  ipcMain.handle('office:launch', async (_event, mode, locationKey, options) => {
    const location = normalizeLocation(locationKey);
    const loc = LOCATIONS[location];
    const launchKey = `${location}:${mode}`;

    if (launchInFlight.has(launchKey)) {
      return { ok: false, error: 'Launch already in progress — wait for deploy to finish.' };
    }

    if (!fs.existsSync(gameBinaryPath()) && mode !== 'deploy-only') {
      return { ok: false, error: `Game binary missing: ${gameBinaryPath()}. Run make -j8 first.` };
    }

    let hungPid = null;
    // Never auto-relaunch a healthy game; kill and replace hung boots (100% CPU door loops).
    if (mode !== 'deploy-only') {
      const existing = getGameStatus(location);
      const runningPid = existing.running?.[0]?.pid || (existing.lastAlive ? existing.lastPid : null);
      hungPid = runningPid && isLikelyHungGamePid(runningPid) ? runningPid : null;
      if (hungPid) {
        log(`Hung game PID ${hungPid} (~100% CPU) — force-killing before relaunch`);
        killGame(location);
      } else {
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
    }

    const args = [];
    if (mode === 'deploy-only') args.push('--no-play');
    if (mode === 'with-bots') args.push('--with-bots');
    if (hungPid) args.push('--force');
    if (options && options.fastRun) args.push('--fast-run');

    if (options && options.disableTextures) {
      process.env.PDMAP_DISABLE_TEXTURES = '1';
    } else {
      delete process.env.PDMAP_DISABLE_TEXTURES;
    }

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

  ipcMain.handle('office:get-workspace-config', () => loadWorkspaceConfigFile());

  ipcMain.handle('office:save-workspace-config', (_event, payload) => {
    const locationKey = normalizeLocation(payload?.locationKey || payload?.location);
    const displayName = String(payload?.displayName || '').trim();
    const codename = String(payload?.codename || '').trim();
    return saveWorkspaceConfig(locationKey, displayName, codename);
  });

  ipcMain.handle('office:get-slack-channels', () => fetchSlackChannels());

  ipcMain.handle('office:mark-channel-read', (_event, channelId) => markSlackChannelRead(channelId));

  ipcMain.handle('office:get-dm-threads', () => fetchDmThreads());

  ipcMain.handle('office:get-dm-thread', (_event, agentId) => fetchDmThread(agentId));

  ipcMain.handle('office:mark-dm-read', (_event, agentId) => markDmThreadRead(agentId));

  ipcMain.handle('office:append-dm-message', (_event, agentId, text) => appendDmMessage(agentId, text));

  ipcMain.handle('office:get-slack-oauth-status', () => fetchSlackOAuthStatus());

  ipcMain.handle('office:begin-slack-oauth', () => beginSlackOAuthInstall());

  ipcMain.handle('office:connect-slack-oauth-browser', () => connectSlackOAuthBrowser());

  ipcMain.handle('office:complete-slack-oauth', (_event, code, state) =>
    completeSlackOAuthInstall(code, state),
  );

  ipcMain.handle('office:disconnect-slack-oauth', () => disconnectSlackOAuthInstall());

  ipcMain.handle('office:get-slack-oauth-security-approval', () => fetchSlackOAuthSecurityApproval());

  ipcMain.handle('office:approve-slack-oauth-security', (_event, approvalId) =>
    approveSlackOAuthSecurity(approvalId),
  );

  ipcMain.handle('office:deny-slack-oauth-security', (_event, approvalId) =>
    denySlackOAuthSecurity(approvalId),
  );

  ipcMain.handle('office:post-slack-outbound', (_event, channel, text) =>
    postSlackOutbound(channel, text),
  );

  ipcMain.handle('office:get-connector-approvals', () => fetchConnectorApprovals());

  ipcMain.handle('office:approve-connector-approval', (_event, approvalId) =>
    approveConnectorApproval(approvalId),
  );

  ipcMain.handle('office:deny-connector-approval', (_event, approvalId) =>
    denyConnectorApproval(approvalId),
  );

  ipcMain.handle('office:dispatch-connector-task', (_event, agentId, intent, channel, text) =>
    dispatchConnectorTask(agentId, intent, channel, text),
  );

  ipcMain.handle('office:get-antigravity-live-agents', async (_event, push) => {
    try {
      const qs = push ? '?push=1' : '';
      const response = await fetch(`${OFFICE_API_BASE}/antigravity/live-agents${qs}`, {
        headers: officeApiHeaders(),
        signal: AbortSignal.timeout(4000),
      });
      const body = await response.json();
      return response.ok ? { ok: true, ...body } : { ok: false, error: body?.error || `HTTP ${response.status}` };
    } catch (err) {
      return { ok: false, error: String(err) };
    }
  });

  ipcMain.handle('office:sync-antigravity-live-agents', async (_event, pushToEngine = true) => {
    try {
      const response = await fetch(`${OFFICE_API_BASE}/antigravity/sync`, {
        method: 'POST',
        headers: officeApiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ push_to_engine: Boolean(pushToEngine) }),
        signal: AbortSignal.timeout(4000),
      });
      const body = await response.json();
      return response.ok ? { ok: true, ...body } : { ok: false, error: body?.error || `HTTP ${response.status}` };
    } catch (err) {
      return { ok: false, error: String(err) };
    }
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
