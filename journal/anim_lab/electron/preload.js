'use strict';

/** Preload — Electron bridge for Animation Lab server lifecycle. */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('animLabAPI', {
  platform: process.platform,
  getServerPort: () => ipcRenderer.invoke('anim-lab:get-port'),
  ensureServer: () => ipcRenderer.invoke('anim-lab:ensure-server'),
});
