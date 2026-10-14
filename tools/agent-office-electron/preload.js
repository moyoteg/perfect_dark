'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('virtualAgentOffice', {
  getInfo: (location) => ipcRenderer.invoke('office:get-info', location),
  getTenants: () => ipcRenderer.invoke('office:get-tenants'),
  setTenant: (tenantId) => ipcRenderer.invoke('office:set-tenant', tenantId),
  launch: (mode, location, options) => ipcRenderer.invoke('office:launch', mode, location, options),
  killGame: (location) => ipcRenderer.invoke('office:kill-game', location),
  getGameStatus: (location) => ipcRenderer.invoke('office:game-status', location),
  startDirector: () => ipcRenderer.invoke('office:start-director'),
  stopDirector: () => ipcRenderer.invoke('office:stop-director'),
  getDirectorStatus: () => ipcRenderer.invoke('office:director-status'),
  tailDirectorLog: (lines) => ipcRenderer.invoke('office:tail-director-log', lines),
  tailLog: (lines, location) => ipcRenderer.invoke('office:tail-log', lines, location),
  revealPath: (targetPath) => ipcRenderer.invoke('office:reveal-path', targetPath),
  getWorkspaceConfig: () => ipcRenderer.invoke('office:get-workspace-config'),
  saveWorkspaceConfig: (payload) => ipcRenderer.invoke('office:save-workspace-config', payload),
  getSlackChannels: () => ipcRenderer.invoke('office:get-slack-channels'),
  markChannelRead: (channelId) => ipcRenderer.invoke('office:mark-channel-read', channelId),
  getDmThreads: () => ipcRenderer.invoke('office:get-dm-threads'),
  getDmThread: (agentId) => ipcRenderer.invoke('office:get-dm-thread', agentId),
  markDmRead: (agentId) => ipcRenderer.invoke('office:mark-dm-read', agentId),
  appendDmMessage: (agentId, text) => ipcRenderer.invoke('office:append-dm-message', agentId, text),
  getSlackOAuthStatus: () => ipcRenderer.invoke('office:get-slack-oauth-status'),
  beginSlackOAuth: () => ipcRenderer.invoke('office:begin-slack-oauth'),
  connectSlackOAuthBrowser: () => ipcRenderer.invoke('office:connect-slack-oauth-browser'),
  completeSlackOAuth: (code, state) => ipcRenderer.invoke('office:complete-slack-oauth', code, state),
  disconnectSlackOAuth: () => ipcRenderer.invoke('office:disconnect-slack-oauth'),
  getSlackOAuthSecurityApproval: () => ipcRenderer.invoke('office:get-slack-oauth-security-approval'),
  approveSlackOAuthSecurity: (approvalId) =>
    ipcRenderer.invoke('office:approve-slack-oauth-security', approvalId),
  denySlackOAuthSecurity: (approvalId) =>
    ipcRenderer.invoke('office:deny-slack-oauth-security', approvalId),
  postSlackOutbound: (channel, text) =>
    ipcRenderer.invoke('office:post-slack-outbound', channel, text),
  getConnectorApprovals: () => ipcRenderer.invoke('office:get-connector-approvals'),
  approveConnectorApproval: (approvalId) =>
    ipcRenderer.invoke('office:approve-connector-approval', approvalId),
  denyConnectorApproval: (approvalId) =>
    ipcRenderer.invoke('office:deny-connector-approval', approvalId),
  dispatchConnectorTask: (agentId, intent, channel, text) =>
    ipcRenderer.invoke('office:dispatch-connector-task', agentId, intent, channel, text),
  getAntigravityLiveAgents: (push) =>
    ipcRenderer.invoke('office:get-antigravity-live-agents', push),
  syncAntigravityLiveAgents: (pushToEngine) =>
    ipcRenderer.invoke('office:sync-antigravity-live-agents', pushToEngine),
});
