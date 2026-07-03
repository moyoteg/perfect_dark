'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('pdMapLauncher', {
  getInfo: () => ipcRenderer.invoke('launcher:get-info'),
  launchMap: (mapId, options) => ipcRenderer.invoke('launcher:launch-map', mapId, options),
  killGame: () => ipcRenderer.invoke('launcher:kill-game'),
  getGameStatus: () => ipcRenderer.invoke('launcher:game-status'),
  tailLog: (logPath, lines) => ipcRenderer.invoke('launcher:tail-log', logPath, lines),
  startLearnLoop: () => ipcRenderer.invoke('launcher:start-learn-loop'),
  stopLearnLoop: () => ipcRenderer.invoke('launcher:stop-learn-loop'),
  getLearnStatus: () => ipcRenderer.invoke('launcher:learn-status'),
  runLearnAction: (action, args) => ipcRenderer.invoke('launcher:run-learn-action', action, args),
  revealPath: (targetPath) => ipcRenderer.invoke('launcher:reveal-path', targetPath),
  openDoc: (relativePath) => ipcRenderer.invoke('launcher:open-doc', relativePath),
});
