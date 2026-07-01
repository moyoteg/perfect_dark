'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('pdKit', {
  getInfo: () => ipcRenderer.invoke('kit:get-info'),
  launchApp: (appKey) => ipcRenderer.invoke('kit:launch-app', appKey),
  launchGame: (options) => ipcRenderer.invoke('kit:launch-game', options),
  revealPath: (targetPath) => ipcRenderer.invoke('kit:reveal-path', targetPath),
  buildKit: () => ipcRenderer.invoke('kit:build-kit'),
});
