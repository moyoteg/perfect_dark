'use strict';

const gameStatusText = document.getElementById('gameStatusText');
const statusDot = document.getElementById('statusDot');
const killGameBtn = document.getElementById('killGameBtn');
const playSoloBtn = document.getElementById('playSoloBtn');
const deployOnlyBtn = document.getElementById('deployOnlyBtn');
const withBotsBtn = document.getElementById('withBotsBtn');
const startDirectorBtn = document.getElementById('startDirectorBtn');
const stopDirectorBtn = document.getElementById('stopDirectorBtn');
const revealDirectorLogBtn = document.getElementById('revealDirectorLogBtn');
const directorStatusText = document.getElementById('directorStatusText');
const directorDot = document.getElementById('directorDot');
const agentList = document.getElementById('agentList');
const logOutput = document.getElementById('logOutput');
const revealLogBtn = document.getElementById('revealLogBtn');
const repoLine = document.getElementById('repoLine');
const statusLine = document.getElementById('statusLine');
const subtitle = document.getElementById('subtitle');
const eyebrow = document.getElementById('eyebrow');
const locationSelect = document.getElementById('locationSelect');
const agentsBlurb = document.getElementById('agentsBlurb');
const agentDisplayName = document.getElementById('agentDisplayName');
const agentCodename = document.getElementById('agentCodename');
const profileStatus = document.getElementById('profileStatus');
const playSoloHint = document.getElementById('playSoloHint');
const channelList = document.getElementById('channelList');
const channelWorkspaceLabel = document.getElementById('channelWorkspaceLabel');
const channelSyncStatus = document.getElementById('channelSyncStatus');
const dmList = document.getElementById('dmList');
const dmSyncStatus = document.getElementById('dmSyncStatus');
const dmDetail = document.getElementById('dmDetail');
const dmDetailTitle = document.getElementById('dmDetailTitle');
const dmDetailStatus = document.getElementById('dmDetailStatus');
const dmMessageList = document.getElementById('dmMessageList');
const dmComposeForm = document.getElementById('dmComposeForm');
const dmComposeInput = document.getElementById('dmComposeInput');
const dmComposeSend = document.getElementById('dmComposeSend');
const slackIntegrationStatus = document.getElementById('slackIntegrationStatus');
const slackConnectBtn = document.getElementById('slackConnectBtn');
const slackDisconnectBtn = document.getElementById('slackDisconnectBtn');
const slackOutboundForm = document.getElementById('slackOutboundForm');
const slackOutboundChannel = document.getElementById('slackOutboundChannel');
const slackOutboundText = document.getElementById('slackOutboundText');
const slackOutboundSend = document.getElementById('slackOutboundSend');
const slackOutboundStatus = document.getElementById('slackOutboundStatus');
const securityDeskPanel = document.getElementById('securityDeskPanel');
const securityApprovalStatus = document.getElementById('securityApprovalStatus');
const securityApprovalDetails = document.getElementById('securityApprovalDetails');
const securityApproveBtn = document.getElementById('securityApproveBtn');
const securityDenyBtn = document.getElementById('securityDenyBtn');
const connectorStageForm = document.getElementById('connectorStageForm');
const connectorStageIntent = document.getElementById('connectorStageIntent');
const connectorStageChannel = document.getElementById('connectorStageChannel');
const connectorStageText = document.getElementById('connectorStageText');
const connectorStageSend = document.getElementById('connectorStageSend');
const connectorStageStatus = document.getElementById('connectorStageStatus');
const connectorApprovalSection = document.getElementById('connectorApprovalSection');
const connectorApprovalStatus = document.getElementById('connectorApprovalStatus');
const connectorApprovalList = document.getElementById('connectorApprovalList');

/** localStorage key for the human agent profile (Slack-member analogue). */
const AGENT_PROFILE_KEY = 'vao_agent_profile';

/** @type {ReturnType<typeof setInterval> | null} */
let pollTimer = null;
/** @type {string} */
let repoRoot = '';
/** @type {string} */
let currentLocation = 'g5';
/** @type {string} */
let currentLogPath = 'journal/agent_office/.last_launch.log';
/** @type {string} */
let directorLogPath = 'journal/agent_office/office_director.log';
/** Block double-clicks while a deploy/play script is running. */
let launchInFlight = false;
/** Block double-clicks while the director start script is running. */
let directorLaunchInFlight = false;

function setStatus(message, kind) {
  statusLine.textContent = message;
  statusLine.className = `status ${kind || ''}`.trim();
}

function setButtonsDisabled(disabled) {
  playSoloBtn.disabled = disabled || !hasAgentProfile();
  deployOnlyBtn.disabled = disabled;
  withBotsBtn.disabled = disabled;
}

/** @returns {{ displayName: string, codename: string } | null} */
function loadAgentProfile() {
  try {
    const raw = localStorage.getItem(AGENT_PROFILE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const displayName = String(parsed.displayName || '').trim();
    if (!displayName) return null;
    return { displayName, codename: String(parsed.codename || '').trim() };
  } catch {
    return null;
  }
}

function hasAgentProfile() {
  return Boolean(loadAgentProfile()?.displayName);
}

function saveAgentProfile() {
  const displayName = (agentDisplayName?.value || '').trim();
  const codename = (agentCodename?.value || '').trim();
  if (!displayName) {
    localStorage.removeItem(AGENT_PROFILE_KEY);
    renderAgentProfile();
    syncWorkspaceConfig();
    return;
  }
  localStorage.setItem(AGENT_PROFILE_KEY, JSON.stringify({ displayName, codename }));
  renderAgentProfile();
  syncWorkspaceConfig();
}

function renderAgentProfile() {
  const profile = loadAgentProfile();
  if (agentDisplayName && profile) agentDisplayName.value = profile.displayName;
  if (agentCodename && profile) agentCodename.value = profile.codename;

  const ready = Boolean(profile?.displayName);
  if (profileStatus) {
    if (ready) {
      const codenameText = profile.codename ? ` · codename ${profile.codename}` : '';
      profileStatus.textContent = `Signed in as ${profile.displayName}${codenameText}`;
    } else {
      profileStatus.textContent = 'Enter a display name to join this workspace.';
    }
  }
  if (playSoloHint) {
    playSoloHint.textContent = ready
      ? 'Deploy map + solo explore as your agent'
      : 'Create your agent profile first';
  }
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

  const canLaunch = Boolean(game.binaryBuilt) && hasAgentProfile();
  playSoloBtn.disabled = !canLaunch;
  withBotsBtn.disabled = !canLaunch;
  deployOnlyBtn.disabled = false;
  renderAgentProfile();
}

function renderDirectorStatus(director) {
  const running = Boolean(
    (director?.running && director.running.length > 0) ||
      (director?.lastPid && director.lastAlive),
  );
  const pidText = director?.running?.length
    ? director.running.map((entry) => entry.pid).join(', ')
    : director?.lastPid;

  if (running) {
    directorStatusText.textContent = `Director running (PID ${pidText})`;
    directorDot.className = 'status-dot running';
    startDirectorBtn.disabled = true;
    stopDirectorBtn.disabled = false;
  } else {
    directorStatusText.textContent = director?.scriptExists
      ? 'Ready — director stopped'
      : 'Director script missing';
    directorDot.className = 'status-dot idle';
    startDirectorBtn.disabled = !director?.scriptExists;
    stopDirectorBtn.disabled = true;
  }

  if (director?.logPath) {
    directorLogPath = director.logPath;
  }
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

/** Pass 26: block double-clicks while stub Slack OAuth install runs. */
let slackOAuthInFlight = false;
/** Pass 33: block double-clicks while Comms outbound post runs. */
let slackOutboundInFlight = false;
/** Pass 34: block double-clicks while connector stage/dispatch runs. */
let connectorStageInFlight = false;
/** Pass 34: approval ids currently approving/denying. */
const connectorApprovalBusy = new Set();
/** Pass 30: block double-clicks while Security approve/deny runs. */
let securityApprovalInFlight = false;
/** @type {string | null} */
let pendingSecurityApprovalId = null;

function renderSlackOAuth(result) {
  const status = String(result?.status || 'not_installed');
  const integration = String(result?.integration || 'local-first');
  const installed = status === 'installed' && integration === 'slack';
  const awaitingSecurity = status === 'awaiting_security_approval';

  if (slackIntegrationStatus) {
    if (!result?.ok) {
      const offline = result?.error ? ` · ${result.error}` : '';
      slackIntegrationStatus.textContent = `Local-first (Office Service offline${offline})`;
    } else if (awaitingSecurity) {
      const team = result.team_name ? `${result.team_name}` : 'Slack workspace';
      slackIntegrationStatus.textContent = `Authorized · ${team} — awaiting Security desk approval`;
    } else if (status === 'pending') {
      slackIntegrationStatus.textContent = 'OAuth pending — finish connect or retry';
    } else if (installed) {
      const team = result.team_name ? `${result.team_name}` : 'Slack workspace';
      const hint = result.token_hint ? ` · …${result.token_hint}` : '';
      slackIntegrationStatus.textContent = `Connected · ${team}${hint}`;
    } else {
      slackIntegrationStatus.textContent = 'Local-first — Slack not connected';
    }
  }

  if (slackConnectBtn) {
    slackConnectBtn.hidden = installed || awaitingSecurity;
    slackConnectBtn.disabled = slackOAuthInFlight || installed || awaitingSecurity;
  }
  if (slackDisconnectBtn) {
    slackDisconnectBtn.hidden = !installed;
    slackDisconnectBtn.disabled = slackOAuthInFlight || !installed;
  }

  const showOutbound = installed && !awaitingSecurity;
  if (slackOutboundForm) {
    slackOutboundForm.hidden = !showOutbound;
  }
  if (slackOutboundSend) {
    slackOutboundSend.disabled = !showOutbound || slackOutboundInFlight;
  }
  if (!showOutbound && slackOutboundStatus) {
    slackOutboundStatus.hidden = true;
    slackOutboundStatus.textContent = '';
  }
}

function renderSecurityApproval(result) {
  const pending = Boolean(result?.ok && result?.pending);
  const card = result?.security_approval || null;
  const approvalId = card?.approval_id ? String(card.approval_id) : null;
  pendingSecurityApprovalId = pending ? approvalId : null;

  if (securityDeskPanel) {
    securityDeskPanel.hidden = !pending;
  }

  if (!pending) {
    if (securityApprovalStatus) {
      securityApprovalStatus.textContent = result?.ok ? 'No pending approval' : 'Security desk offline';
    }
    if (securityApprovalDetails) securityApprovalDetails.innerHTML = '';
    if (securityApproveBtn) securityApproveBtn.disabled = true;
    if (securityDenyBtn) securityDenyBtn.disabled = true;
    return;
  }

  if (securityApprovalStatus) {
    const connector = card?.connector || 'slack';
    const action = card?.action || 'token_use';
    securityApprovalStatus.textContent = `Pending · ${connector} ${action} (${card?.risk || 'write'} risk)`;
  }

  if (securityApprovalDetails) {
    const team = result?.team_name ? String(result.team_name) : '—';
    securityApprovalDetails.innerHTML = `
      <dt>Agent</dt><dd>${card?.agent_id || 'security'}</dd>
      <dt>Connector</dt><dd>${card?.connector || 'slack'}</dd>
      <dt>Action</dt><dd>${card?.action || 'token_use'}</dd>
      <dt>Risk</dt><dd>${card?.risk || 'write'}</dd>
      <dt>Team</dt><dd>${team}</dd>
      <dt>Approval ID</dt><dd>${approvalId || '—'}</dd>
    `;
  }

  const busy = securityApprovalInFlight || !approvalId;
  if (securityApproveBtn) securityApproveBtn.disabled = busy;
  if (securityDenyBtn) securityDenyBtn.disabled = busy;
}

async function refreshSecurityApproval() {
  const result = await window.virtualAgentOffice.getSlackOAuthSecurityApproval();
  renderSecurityApproval(result);
  return result;
}

async function approveSecurityOAuth() {
  if (securityApprovalInFlight || !pendingSecurityApprovalId) return;
  securityApprovalInFlight = true;
  if (securityApproveBtn) securityApproveBtn.disabled = true;
  if (securityDenyBtn) securityDenyBtn.disabled = true;
  if (securityApprovalStatus) securityApprovalStatus.textContent = 'Approving token use…';

  try {
    const result = await window.virtualAgentOffice.approveSlackOAuthSecurity(pendingSecurityApprovalId);
    if (!result.ok) {
      if (securityApprovalStatus) {
        securityApprovalStatus.textContent = result.error || 'Approve failed';
      }
      return;
    }
    await refreshSlackOAuth();
    await refreshSecurityApproval();
    await refreshSlackChannels();
  } finally {
    securityApprovalInFlight = false;
    await refreshSecurityApproval();
  }
}

async function denySecurityOAuth() {
  if (securityApprovalInFlight || !pendingSecurityApprovalId) return;
  securityApprovalInFlight = true;
  if (securityApproveBtn) securityApproveBtn.disabled = true;
  if (securityDenyBtn) securityDenyBtn.disabled = true;
  if (securityApprovalStatus) securityApprovalStatus.textContent = 'Denying token use…';

  try {
    const result = await window.virtualAgentOffice.denySlackOAuthSecurity(pendingSecurityApprovalId);
    if (!result.ok) {
      if (securityApprovalStatus) {
        securityApprovalStatus.textContent = result.error || 'Deny failed';
      }
      return;
    }
    await refreshSlackOAuth();
    await refreshSecurityApproval();
    await refreshSlackChannels();
  } finally {
    securityApprovalInFlight = false;
    await refreshSecurityApproval();
  }
}

async function refreshSlackOAuth() {
  const result = await window.virtualAgentOffice.getSlackOAuthStatus();
  renderSlackOAuth(result);
  return result;
}

/** Pass 27: open Slack authorize URL in system browser; Office Service GET callback completes install. */
async function connectSlackOAuth() {
  if (slackOAuthInFlight) return;
  slackOAuthInFlight = true;
  if (slackConnectBtn) slackConnectBtn.disabled = true;
  if (slackIntegrationStatus) slackIntegrationStatus.textContent = 'Opening Slack in browser…';

  try {
    const result = await window.virtualAgentOffice.connectSlackOAuthBrowser();
    if (!result.ok) {
      if (slackIntegrationStatus) {
        if (result.pending) {
          slackIntegrationStatus.textContent = 'Waiting for browser — finish authorize in Slack';
        } else {
          slackIntegrationStatus.textContent = result.error || 'Connect failed';
        }
      }
      return;
    }

    await refreshSlackOAuth();
    await refreshSecurityApproval();
    await refreshSlackChannels();
    if (result.awaitingSecurityApproval) {
      if (slackIntegrationStatus) {
        const team = result.install?.team_name || 'Slack workspace';
        slackIntegrationStatus.textContent = `Authorized · ${team} — approve at Security desk`;
      }
      return;
    }
    if (slackIntegrationStatus && result.install?.team_name) {
      slackIntegrationStatus.textContent = `Connected · ${result.install.team_name}`;
    }
  } finally {
    slackOAuthInFlight = false;
    await refreshSlackOAuth();
  }
}

async function disconnectSlackOAuth() {
  if (slackOAuthInFlight) return;
  slackOAuthInFlight = true;
  if (slackDisconnectBtn) slackDisconnectBtn.disabled = true;
  if (slackIntegrationStatus) slackIntegrationStatus.textContent = 'Disconnecting…';

  try {
    const result = await window.virtualAgentOffice.disconnectSlackOAuth();
    if (!result.ok) {
      if (slackIntegrationStatus) {
        slackIntegrationStatus.textContent = result.error || 'Disconnect failed';
      }
      return;
    }
    await refreshSlackOAuth();
    await refreshSlackChannels();
  } finally {
    slackOAuthInFlight = false;
    await refreshSlackOAuth();
  }
}

if (slackConnectBtn) {
  slackConnectBtn.addEventListener('click', () => connectSlackOAuth());
}
if (slackDisconnectBtn) {
  slackDisconnectBtn.addEventListener('click', () => disconnectSlackOAuth());
}
if (securityApproveBtn) {
  securityApproveBtn.addEventListener('click', () => approveSecurityOAuth());
}
if (securityDenyBtn) {
  securityDenyBtn.addEventListener('click', () => denySecurityOAuth());
}

/** Pass 33: Comms desk outbound compose → POST /slack/outbound/post. */
async function submitSlackOutbound(event) {
  event?.preventDefault();
  const channel = String(slackOutboundChannel?.value || '#general').trim() || '#general';
  const text = String(slackOutboundText?.value || '').trim();
  if (!text || slackOutboundInFlight) return;

  slackOutboundInFlight = true;
  if (slackOutboundSend) slackOutboundSend.disabled = true;
  if (slackOutboundStatus) {
    slackOutboundStatus.hidden = false;
    slackOutboundStatus.textContent = `Posting to ${channel}…`;
    slackOutboundStatus.className = 'muted small slack-outbound-status';
  }

  try {
    const result = await window.virtualAgentOffice.postSlackOutbound(channel, text);
    if (!result.ok) {
      if (slackOutboundStatus) {
        const hint =
          result.status === 409 || result.slackStatus === 'not_installed'
            ? 'Connect Slack first'
            : result.error || 'Post failed';
        slackOutboundStatus.textContent = hint;
        slackOutboundStatus.className = 'muted small slack-outbound-status slack-outbound-status--error';
      }
      return;
    }
    if (slackOutboundText) slackOutboundText.value = '';
    if (slackOutboundStatus) {
      const ts = result.slack_ts ? ` · ts ${result.slack_ts}` : '';
      slackOutboundStatus.textContent = `Posted to ${result.channel || channel}${ts}`;
      slackOutboundStatus.className = 'muted small slack-outbound-status slack-outbound-status--ok';
    }
  } finally {
    slackOutboundInFlight = false;
    if (slackOutboundSend) slackOutboundSend.disabled = false;
  }
}

if (slackOutboundForm) {
  slackOutboundForm.addEventListener('submit', submitSlackOutbound);
}

/** Pass 34: preview connector action args without leaking secrets. */
function formatConnectorArgsPreview(args) {
  if (!args || typeof args !== 'object') return '—';
  const channel = args.channel ? String(args.channel) : '';
  const text = args.text ? String(args.text).slice(0, 80) : '';
  if (channel && text) return `${channel}: ${text}`;
  return JSON.stringify(args).slice(0, 80);
}

function renderConnectorApprovals(result) {
  const pending = result?.ok && Array.isArray(result.approvals)
    ? result.approvals.filter((entry) => entry.status === 'pending')
    : [];

  if (connectorApprovalSection) {
    connectorApprovalSection.hidden = pending.length === 0;
  }

  if (connectorApprovalStatus) {
    if (!result?.ok) {
      connectorApprovalStatus.textContent = result?.error
        ? `Offline · ${result.error}`
        : 'Connector approvals offline';
    } else if (!pending.length) {
      connectorApprovalStatus.textContent = 'No pending approvals';
    } else {
      connectorApprovalStatus.textContent = `${pending.length} pending approval${pending.length === 1 ? '' : 's'}`;
    }
  }

  if (!connectorApprovalList) return;
  connectorApprovalList.innerHTML = '';

  pending.forEach((approval) => {
    const li = document.createElement('li');
    li.className = 'connector-approval-card';
    const id = String(approval.id || '');
    const busy = connectorApprovalBusy.has(id);
    const argsPreview = formatConnectorArgsPreview(approval.args);
    li.innerHTML = `
      <dl class="connector-approval-details">
        <dt>Agent</dt><dd>@${approval.agent_id || '—'}</dd>
        <dt>Connector</dt><dd>${approval.connector || '—'}</dd>
        <dt>Action</dt><dd>${approval.action || '—'}</dd>
        <dt>Risk</dt><dd>${approval.risk || 'write'}</dd>
        <dt>Args</dt><dd>${argsPreview}</dd>
        <dt>Task</dt><dd>${approval.task_id || '—'}</dd>
      </dl>
      <div class="connector-approval-actions">
        <button type="button" class="primary small connector-approve-btn" data-approval-id="${id}" ${busy ? 'disabled' : ''}>Approve</button>
        <button type="button" class="danger small connector-deny-btn" data-approval-id="${id}" ${busy ? 'disabled' : ''}>Deny</button>
      </div>
    `;
    li.querySelector('.connector-approve-btn')?.addEventListener('click', () => approveConnectorApproval(id));
    li.querySelector('.connector-deny-btn')?.addEventListener('click', () => denyConnectorApproval(id));
    connectorApprovalList.appendChild(li);
  });
}

async function refreshConnectorApprovals() {
  const result = await window.virtualAgentOffice.getConnectorApprovals();
  renderConnectorApprovals(result);
  return result;
}

async function approveConnectorApproval(approvalId) {
  const id = String(approvalId || '').trim();
  if (!id || connectorApprovalBusy.has(id)) return;
  connectorApprovalBusy.add(id);
  await refreshConnectorApprovals();

  try {
    const result = await window.virtualAgentOffice.approveConnectorApproval(id);
    if (!result.ok && connectorApprovalStatus) {
      connectorApprovalStatus.textContent = result.error || 'Approve failed';
    }
  } finally {
    connectorApprovalBusy.delete(id);
    await refreshConnectorApprovals();
  }
}

async function denyConnectorApproval(approvalId) {
  const id = String(approvalId || '').trim();
  if (!id || connectorApprovalBusy.has(id)) return;
  connectorApprovalBusy.add(id);
  await refreshConnectorApprovals();

  try {
    const result = await window.virtualAgentOffice.denyConnectorApproval(id);
    if (!result.ok && connectorApprovalStatus) {
      connectorApprovalStatus.textContent = result.error || 'Deny failed';
    }
  } finally {
    connectorApprovalBusy.delete(id);
    await refreshConnectorApprovals();
  }
}

/** Pass 34: Comms desk dispatch + perform → awaiting_approval on Director desk. */
async function submitConnectorStage(event) {
  event?.preventDefault();
  const intent = String(connectorStageIntent?.value || '').trim();
  const channel = String(connectorStageChannel?.value || '#general').trim() || '#general';
  const text = String(connectorStageText?.value || '').trim();
  if (!intent || !text || connectorStageInFlight) return;

  connectorStageInFlight = true;
  if (connectorStageSend) connectorStageSend.disabled = true;
  if (connectorStageStatus) {
    connectorStageStatus.hidden = false;
    connectorStageStatus.textContent = 'Staging agent write for approval…';
    connectorStageStatus.className = 'muted small connector-stage-status';
  }

  try {
    const result = await window.virtualAgentOffice.dispatchConnectorTask('comms', intent, channel, text);
    if (!result.ok) {
      if (connectorStageStatus) {
        connectorStageStatus.textContent = result.error || 'Stage failed';
        connectorStageStatus.className = 'muted small connector-stage-status connector-stage-status--error';
      }
      return;
    }
    if (connectorStageText) connectorStageText.value = '';
    if (connectorStageStatus) {
      connectorStageStatus.textContent = result.staged
        ? 'Staged — approve at Director desk'
        : 'Task completed without approval gate';
      connectorStageStatus.className = 'muted small connector-stage-status connector-stage-status--ok';
    }
    await refreshConnectorApprovals();
  } finally {
    connectorStageInFlight = false;
    if (connectorStageSend) connectorStageSend.disabled = false;
  }
}

if (connectorStageForm) {
  connectorStageForm.addEventListener('submit', submitConnectorStage);
}

function renderChannels(config, slackChannels) {
  if (!channelList) return;
  channelList.innerHTML = '';
  const channels = slackChannels?.length ? slackChannels : (config?.channels || []);
  const workspaceLabel = config?.workspace?.location_label || 'Select a workspace';
  if (channelWorkspaceLabel) {
    channelWorkspaceLabel.textContent = workspaceLabel;
  }

  if (!channels.length) {
    channelList.innerHTML = '<li class="muted small">Sign in and pick a workspace to load channels.</li>';
    return;
  }

  channels.forEach((ch) => {
    const li = document.createElement('li');
    const unread = ch.unread_count_display ?? ch.unread ?? 0;
    const hasUnread = unread > 0;
    li.className = `channel-item${hasUnread ? ' channel-item--unread' : ''}`;
    const space = ch.purpose?.value ?? ch.space ?? '';
    const badge = hasUnread ? `<span class="channel-unread">${unread}</span>` : '';
    li.innerHTML = `
      <span class="channel-name">${ch.name || ch.id}</span>
      ${badge}
      <span class="channel-space">${space}</span>
    `;
    if (hasUnread && ch.id) {
      li.title = 'Click to mark as read';
      li.addEventListener('click', async () => {
        const result = await window.virtualAgentOffice.markChannelRead(ch.id);
        if (result.ok) {
          await refreshSlackChannels(config);
        } else if (channelSyncStatus) {
          channelSyncStatus.textContent = result.error || 'Mark read failed';
        }
      });
    }
    channelList.appendChild(li);
  });
}

async function refreshSlackChannels(config) {
  let localConfig = config;
  if (!localConfig) {
    const saved = await window.virtualAgentOffice.getWorkspaceConfig();
    localConfig = saved.ok ? saved.config : null;
  }

  const slack = await window.virtualAgentOffice.getSlackChannels();
  if (slack.ok && slack.channels?.length) {
    renderChannels(localConfig, slack.channels);
    if (channelSyncStatus) {
      const summary = slack.general_summary ? ` · ${slack.general_summary}` : '';
      channelSyncStatus.textContent = `Live · Office Service${summary}`;
    }
    await refreshDmThreads();
    return;
  }

  renderChannels(localConfig, null);
  if (channelSyncStatus) {
    const offline = slack.error ? ` · Service offline (${slack.error})` : '';
    channelSyncStatus.textContent = localConfig
      ? `Local config${offline}`
      : 'Not signed in';
  }
  renderDmThreads(null);
}

/** Pass 9: currently selected DM thread for detail pane. */
let selectedDmAgentId = null;

/** Pass 16: Web Speech TTS for agent DM replies (Security lower pitch). */
let dmTtsEnabled = localStorage.getItem('vao_dm_tts') !== '0';
let dmTtsVoicesReady = false;

function primeDmTtsVoices() {
  if (!window.speechSynthesis || dmTtsVoicesReady) return;
  const voices = window.speechSynthesis.getVoices();
  if (voices.length) dmTtsVoicesReady = true;
}

if (window.speechSynthesis) {
  window.speechSynthesis.onvoiceschanged = primeDmTtsVoices;
  primeDmTtsVoices();
}

function pickVoiceForSlug(voiceSlug) {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  if (!voices.length) return null;
  const slug = String(voiceSlug || '').toLowerCase();
  const english = voices.filter((v) => /^en(-|$)/i.test(v.lang || ''));
  const pool = english.length ? english : voices;
  if (slug === 'security') {
    const maleish = pool.find((v) => /male|daniel|fred|tom|alex|bruce/i.test(v.name));
    if (maleish) return maleish;
  }
  const hinted = pool.find((v) => v.name.toLowerCase().includes(slug));
  return hinted || pool[0];
}

function maybeSpeakAgentDmLine(payload) {
  if (!dmTtsEnabled || !window.speechSynthesis) return;
  const tts = payload?.tts_speak;
  if (!tts || tts.status !== 'ready' || !tts.text) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(tts.text);
  utterance.rate = Number(tts.rate) || 1.0;
  utterance.pitch = Number(tts.pitch) || 1.0;
  const voice = pickVoiceForSlug(tts.voice_slug);
  if (voice) utterance.voice = voice;
  window.speechSynthesis.speak(utterance);
}

function hideDmDetail() {
  selectedDmAgentId = null;
  if (dmDetail) dmDetail.hidden = true;
  if (dmMessageList) dmMessageList.innerHTML = '';
  if (dmDetailStatus) dmDetailStatus.textContent = '';
  if (dmComposeForm) dmComposeForm.hidden = true;
  if (dmComposeInput) dmComposeInput.value = '';
}

function renderDmDetail(threadPayload) {
  if (!dmDetail || !dmMessageList) return;
  const thread = threadPayload?.thread;
  const agentId = thread?.agent_id || threadPayload?.agent_id;
  if (!thread || !agentId) {
    hideDmDetail();
    return;
  }
  selectedDmAgentId = agentId;
  dmDetail.hidden = false;
  if (dmComposeForm) dmComposeForm.hidden = false;
  if (dmDetailTitle) dmDetailTitle.textContent = `@${agentId}`;
  const messages = thread.messages || [];
  if (dmDetailStatus) {
    dmDetailStatus.textContent = messages.length
      ? `${messages.length} message${messages.length === 1 ? '' : 's'}`
      : 'No messages yet';
  }
  dmMessageList.innerHTML = '';
  if (!messages.length) {
    dmMessageList.innerHTML = '<li class="muted small">Walk up or Z-target this agent in-game.</li>';
    return;
  }
  messages.slice(-20).forEach((msg) => {
    const li = document.createElement('li');
    const role = msg.from === 'agent' ? 'agent' : 'human';
    li.className = `dm-message dm-message--${role}`;
    const label = role === 'agent' ? agentId : 'You';
    li.innerHTML = `
      <span class="dm-message-meta">${label}</span>
      <span class="dm-message-text">${String(msg.text || '').slice(0, 500)}</span>
    `;
    dmMessageList.appendChild(li);
  });
}

async function openDmThread(agentId) {
  if (!agentId) return;
  selectedDmAgentId = agentId;
  if (dmDetail) dmDetail.hidden = false;
  if (dmComposeForm) dmComposeForm.hidden = false;
  if (dmDetailTitle) dmDetailTitle.textContent = `@${agentId}`;
  if (dmDetailStatus) dmDetailStatus.textContent = 'Loading…';
  if (dmMessageList) dmMessageList.innerHTML = '';
  const result = await window.virtualAgentOffice.getDmThread(agentId);
  if (!result.ok) {
    if (dmDetailStatus) dmDetailStatus.textContent = result.error || 'Failed to load thread';
    return;
  }
  renderDmDetail(result);
  const unread = result.thread?.unread_count_display ?? result.unread_count_display ?? 0;
  if (unread > 0) {
    maybeSpeakAgentDmLine(result);
    await window.virtualAgentOffice.markDmRead(agentId);
    await refreshDmThreads();
  }
}

/** Pass 10: compose human line from Electron launcher (stub agent reply). */
async function submitDmCompose(event) {
  event?.preventDefault();
  const agentId = selectedDmAgentId;
  const text = String(dmComposeInput?.value || '').trim();
  if (!agentId || !text) return;
  if (dmComposeSend) dmComposeSend.disabled = true;
  if (dmDetailStatus) dmDetailStatus.textContent = 'Sending…';
  const result = await window.virtualAgentOffice.appendDmMessage(agentId, text);
  if (dmComposeSend) dmComposeSend.disabled = false;
  if (!result.ok) {
    if (dmDetailStatus) dmDetailStatus.textContent = result.error || 'Send failed';
    return;
  }
  if (dmComposeInput) dmComposeInput.value = '';
  await openDmThread(agentId);
  await refreshDmThreads();
}

if (dmComposeForm) {
  dmComposeForm.addEventListener('submit', submitDmCompose);
}

/** Pass 8/9: persisted walk-up DMs with unread badges + detail pane on select. */
function renderDmThreads(payload) {
  if (!dmList) return;
  dmList.innerHTML = '';
  const threads = payload?.threads || [];
  if (!threads.length) {
    dmList.innerHTML = '<li class="muted small">No walk-up DMs yet — Z-target any agent in-game.</li>';
    if (dmSyncStatus) dmSyncStatus.textContent = payload?.error ? `Offline (${payload.error})` : 'No threads yet';
    hideDmDetail();
    return;
  }
  let totalUnread = 0;
  threads.forEach((thread) => {
    const li = document.createElement('li');
    const last = thread.messages?.[thread.messages.length - 1];
    const preview = last?.text ? String(last.text).slice(0, 64) : '';
    const unread = thread.unread_count_display ?? thread.unread_count ?? 0;
    const hasUnread = unread > 0;
    if (hasUnread) totalUnread += unread;
    const isSelected = selectedDmAgentId && thread.agent_id === selectedDmAgentId;
    li.className = `channel-item channel-item--selectable${hasUnread ? ' channel-item--unread' : ''}${isSelected ? ' channel-item--selected' : ''}`;
    const badge = hasUnread ? `<span class="channel-unread">${unread}</span>` : '';
    li.innerHTML = `
      <span class="channel-name">@${thread.agent_id}</span>
      ${badge}
      <span class="channel-space">${preview}</span>
    `;
    if (thread.agent_id) {
      li.title = hasUnread ? 'Open thread and mark read' : 'Open thread';
      li.addEventListener('click', () => openDmThread(thread.agent_id));
    }
    dmList.appendChild(li);
  });
  if (dmSyncStatus) {
    const unreadNote = totalUnread > 0 ? ` · ${totalUnread} unread` : '';
    dmSyncStatus.textContent = `${threads.length} active thread${threads.length === 1 ? '' : 's'}${unreadNote}`;
  }
}

async function refreshDmThreads() {
  if (!hasAgentProfile()) {
    renderDmThreads(null);
    return;
  }
  const dms = await window.virtualAgentOffice.getDmThreads();
  renderDmThreads(dms.ok ? dms : { error: dms.error });
}

async function syncWorkspaceConfig() {
  const profile = loadAgentProfile();
  if (!profile?.displayName) {
    renderChannels(null, null);
    if (channelSyncStatus) channelSyncStatus.textContent = 'Not signed in';
    return;
  }

  if (channelSyncStatus) channelSyncStatus.textContent = 'Syncing…';
  const result = await window.virtualAgentOffice.saveWorkspaceConfig({
    locationKey: currentLocation,
    displayName: profile.displayName,
    codename: profile.codename,
  });

  if (!result.ok) {
    if (channelSyncStatus) channelSyncStatus.textContent = result.error || 'Sync failed';
    return;
  }

  await refreshSlackChannels(result.config);
}

async function loadWorkspaceChannels() {
  const saved = await window.virtualAgentOffice.getWorkspaceConfig();
  if (saved.ok && saved.config) {
    await refreshSlackChannels(saved.config);
    return;
  }
  await syncWorkspaceConfig();
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

async function refreshDirectorStatus() {
  const director = await window.virtualAgentOffice.getDirectorStatus();
  renderDirectorStatus(director);
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
    if (currentLocation === 'lab') {
      agentsBlurb.textContent =
        'Team agents in the Matrix sandbox — desk props, sit/operate anims, console, and test doors.';
    } else if (currentLocation === 'ci' || currentLocation === 'ci_lobby') {
      agentsBlurb.textContent =
        'Eight team agents at CI desks in this workspace — Z-target for role status; you walk as your agent profile.';
    } else {
      agentsBlurb.textContent =
        'Eight team agents in the G5 meeting room — Z-target for role status; you walk as your agent profile.';
    }
  }
  renderAgents(info.layout);
  renderGameStatus(info.game);
  renderDirectorStatus(info.director);
  await refreshSlackOAuth();
  await refreshSecurityApproval();
  await refreshConnectorApprovals();
  await loadWorkspaceChannels();
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
    const fastRunCheckbox = document.getElementById('fastRunCheckbox');
    const fastRun = fastRunCheckbox ? fastRunCheckbox.checked : false;
    const disableTexturesCheckbox = document.getElementById('disableTexturesCheckbox');
    const disableTextures = disableTexturesCheckbox ? disableTexturesCheckbox.checked : false;
    result = await window.virtualAgentOffice.launch(mode, currentLocation, { fastRun, disableTextures });
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

startDirectorBtn.addEventListener('click', async () => {
  if (directorLaunchInFlight) {
    setStatus('Director launch already in progress…', 'warn');
    return;
  }
  directorLaunchInFlight = true;
  startDirectorBtn.disabled = true;
  setStatus('Starting live LLM director…', '');
  try {
    const result = await window.virtualAgentOffice.startDirector();
    if (!result.ok) {
      setStatus(result.error || 'Director launch failed', 'error');
      return;
    }
    renderDirectorStatus(result.status);
    if (result.alreadyRunning) {
      setStatus('Live director already running', 'warn');
    } else {
      setStatus('Live director started — walk up to an agent in-game', 'ok');
    }
    if (result.logTail?.ok) {
      logOutput.textContent = result.logTail.lines || '';
    }
  } finally {
    directorLaunchInFlight = false;
    await refreshDirectorStatus();
  }
});

stopDirectorBtn.addEventListener('click', async () => {
  setStatus('Stopping live director…', '');
  const result = await window.virtualAgentOffice.stopDirector();
  renderDirectorStatus(result.status);
  if (result.killed?.length) {
    setStatus(`Stopped director PID(s): ${result.killed.join(', ')}`, 'ok');
  } else {
    setStatus('No live director process found', 'warn');
  }
});

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

revealDirectorLogBtn.addEventListener('click', async () => {
  if (!repoRoot) return;
  await window.virtualAgentOffice.revealPath(`${repoRoot}/${directorLogPath}`);
});

locationSelect?.addEventListener('change', async () => {
  currentLocation = locationSelect.value || 'g5';
  await refresh();
  await syncWorkspaceConfig();
});

agentDisplayName?.addEventListener('input', saveAgentProfile);
agentCodename?.addEventListener('input', saveAgentProfile);
agentDisplayName?.addEventListener('change', saveAgentProfile);
agentCodename?.addEventListener('change', saveAgentProfile);

renderAgentProfile();
refresh().catch((err) => setStatus(String(err), 'error'));

pollTimer = setInterval(async () => {
  await refreshGameStatus();
  await refreshDirectorStatus();
  await refreshLog();
  await refreshSlackOAuth();
  await refreshSecurityApproval();
  await refreshConnectorApprovals();
  await refreshSlackChannels();
}, 4000);

window.addEventListener('beforeunload', () => {
  if (pollTimer) clearInterval(pollTimer);
});
