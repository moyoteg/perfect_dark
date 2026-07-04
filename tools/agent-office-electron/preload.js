'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('virtualAgentOffice', {
  getInfo: (location) => ipcRenderer.invoke('office:get-info', location),
  launch: (mode, location) => ipcRenderer.invoke('office:launch', mode, location),
  killGame: (location) => ipcRenderer.invoke('office:kill-game', location),
  getGameStatus: (location) => ipcRenderer.invoke('office:game-status', location),
  startDirector: () => ipcRenderer.invoke('office:start-director'),
  stopDirector: () => ipcRenderer.invoke('office:stop-director'),
  getDirectorStatus: () => ipcRenderer.invoke('office:director-status'),
  tailDirectorLog: (lines) => ipcRenderer.invoke('office:tail-director-log', lines),
  tailLog: (lines, location) => ipcRenderer.invoke('office:tail-log', lines, location),
  revealPath: (targetPath) => ipcRenderer.invoke('office:reveal-path', targetPath),
});
