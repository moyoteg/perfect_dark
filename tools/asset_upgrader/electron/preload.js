'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('upgraderAPI', {
  getConfig: () => ipcRenderer.invoke('upgrader:get-config'),
  saveConfig: (config) => ipcRenderer.invoke('upgrader:save-config', config),
  getSnapshot: () => ipcRenderer.invoke('upgrader:get-snapshot'),
  startRun: (options) => ipcRenderer.invoke('upgrader:start-run', options),
  stopRun: () => ipcRenderer.invoke('upgrader:stop-run'),
  refreshSnapshot: () => ipcRenderer.invoke('upgrader:refresh-snapshot'),
  pickDirectory: () => ipcRenderer.invoke('upgrader:pick-directory'),
  onLogLine: (callback) => {
    ipcRenderer.on('upgrader:log', (_event, line) => callback(line));
  },
  onSnapshotUpdated: (callback) => {
    ipcRenderer.on('upgrader:snapshot', (_event, snapshot) => callback(snapshot));
  },
  onRunState: (callback) => {
    ipcRenderer.on('upgrader:run-state', (_event, state) => callback(state));
  },
});
