'use strict';

/**
 * Enforce one running instance per kit app (unique dock icon + focus on re-open).
 */

/**
 * @param {import('electron').App} app
 * @param {() => void} focusWindow
 * @returns {boolean} false when this process should exit immediately
 */
function bindSingleInstance(app, focusWindow) {
  const gotLock = app.requestSingleInstanceLock();
  if (!gotLock) {
    app.quit();
    return false;
  }
  app.on('second-instance', () => {
    try {
      focusWindow();
    } catch (err) {
      console.error('[single-instance] focus failed:', err);
    }
  });
  return true;
}

module.exports = { bindSingleInstance };
