'use strict';

const toolGrid = document.getElementById('toolGrid');
const actionSections = document.getElementById('actionSections');
const docGrid = document.getElementById('docGrid');
const kitTitle = document.getElementById('kitTitle');
const kitSubtitle = document.getElementById('kitSubtitle');
const kitVersionPill = document.getElementById('kitVersionPill');
const portVersionPill = document.getElementById('portVersionPill');
const repoLine = document.getElementById('repoLine');
const statusLine = document.getElementById('statusLine');
const outputLine = document.getElementById('outputLine');
const playBtn = document.getElementById('playBtn');
const testMapBtn = document.getElementById('testMapBtn');
const buildAppsBtn = document.getElementById('buildAppsBtn');
const revealReleaseBtn = document.getElementById('revealReleaseBtn');

/** @type {ReturnType<typeof window.pdKit.getInfo> extends Promise<infer T> ? T : never} | null */
let latestInfo = null;

function setStatus(message, kind) {
  statusLine.textContent = message;
  statusLine.className = `status ${kind || ''}`.trim();
}

function showOutput(text) {
  if (!text) {
    outputLine.classList.add('hidden');
    outputLine.textContent = '';
    return;
  }
  outputLine.classList.remove('hidden');
  outputLine.textContent = text;
}

function badgeForTool(tool) {
  if (tool.built) {
    if (tool.wrapped) return ['Wrapped in kit', 'ok'];
    if (tool.devMode) return ['Dev mode', 'ok'];
    return ['Available', 'ok'];
  }
  return tool.optional ? ['Optional — not built', 'warn'] : ['Not built', 'warn'];
}

function renderTools(tools) {
  toolGrid.innerHTML = '';
  tools.forEach((tool) => {
    const [badgeText, badgeKind] = badgeForTool(tool);
    const card = document.createElement('article');
    card.className = 'card';
    card.innerHTML = `
      <h3>${tool.shortTitle}</h3>
      <p>${tool.description}</p>
      <div class="card-footer">
        <span class="badge ${badgeKind}">${badgeText}</span>
      </div>
      <button type="button" data-app-key="${tool.key}" ${tool.built ? '' : 'disabled'}>
        Open ${tool.shortTitle}
      </button>
    `;
    toolGrid.appendChild(card);
  });

  toolGrid.querySelectorAll('button[data-app-key]').forEach((button) => {
    button.addEventListener('click', async () => {
      const appKey = button.getAttribute('data-app-key');
      setStatus(`Opening ${appKey}…`, '');
      showOutput('');
      const result = await window.pdKit.launchApp(appKey);
      if (!result.ok) {
        setStatus(result.error || 'Launch failed', 'error');
        return;
      }
      setStatus(`Launched ${appKey}`, 'ok');
    });
  });
}

function renderActionGroups(groups, gameBuilt) {
  actionSections.innerHTML = '';
  groups.forEach((group) => {
    const section = document.createElement('section');
    section.className = 'section nested';
    section.innerHTML = `
      <div class="section-head">
        <h2>${group.title}</h2>
      </div>
      <div class="grid compact"></div>
    `;
    const grid = section.querySelector('.grid');
    (group.actions || []).forEach((action) => {
      const disabled = action.requiresGame && !gameBuilt;
      const card = document.createElement('article');
      card.className = 'card compact-card';
      card.innerHTML = `
        <h3>${action.shortTitle}</h3>
        <p>${action.description}</p>
        <button type="button" data-action-key="${action.key}" ${disabled ? 'disabled' : ''}>
          Run
        </button>
      `;
      grid.appendChild(card);
    });
    actionSections.appendChild(section);
  });

  actionSections.querySelectorAll('button[data-action-key]').forEach((button) => {
    button.addEventListener('click', async () => {
      const actionKey = button.getAttribute('data-action-key');
      setStatus(`Running ${actionKey}…`, '');
      showOutput('');
      button.disabled = true;
      const result = await window.pdKit.runAction(actionKey);
      button.disabled = false;
      if (!result.ok) {
        setStatus(result.error || `Action failed (${result.code ?? 'error'})`, 'error');
        if (result.output) showOutput(result.output);
        return;
      }
      if (result.detached) {
        setStatus(`${actionKey} started in background`, 'ok');
        return;
      }
      setStatus(`${actionKey} completed`, 'ok');
      if (result.output) showOutput(result.output);
      await refresh();
    });
  });
}

function renderDocs(docs) {
  docGrid.innerHTML = '';
  docs.forEach((doc) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'doc-link';
    button.textContent = doc.title;
    button.disabled = !doc.exists;
    button.title = doc.path;
    button.addEventListener('click', async () => {
      const result = await window.pdKit.openDoc(doc.key);
      if (!result.ok) {
        setStatus(result.error || 'Could not open doc', 'error');
      }
    });
    docGrid.appendChild(button);
  });
}

async function refresh() {
  const info = await window.pdKit.getInfo();
  latestInfo = info;
  kitTitle.textContent = info.name;
  kitSubtitle.textContent = info.gameBinary.built
    ? 'All kit tools, scripts, and docs launch from this hub.'
    : 'Build the game binary to enable Play and scenario launchers.';
  kitVersionPill.textContent = `Kit v${info.kitVersion}`;
  portVersionPill.textContent = `Port v${info.portVersion}`;
  repoLine.textContent = info.repoRoot || 'Repo root not resolved';
  playBtn.disabled = !info.gameBinary.built;
  testMapBtn.disabled = !info.gameBinary.built;
  renderTools(info.tools);
  renderActionGroups(info.actionGroups || [], info.gameBinary.built);
  renderDocs(info.docs || []);
}

playBtn.addEventListener('click', async () => {
  setStatus('Launching game…', '');
  showOutput('');
  const result = await window.pdKit.launchGame({ mod: 'mod_allinone' });
  if (!result.ok) {
    setStatus(result.error || 'Launch failed', 'error');
    return;
  }
  setStatus('Game launched', 'ok');
});

testMapBtn.addEventListener('click', async () => {
  setStatus('Launching test map…', '');
  showOutput('');
  const result = await window.pdKit.launchGame({ mod: 'mod_allinone', testMap: true });
  if (!result.ok) {
    setStatus(result.error || 'Launch failed', 'error');
    return;
  }
  setStatus('Test map launched', 'ok');
});

buildAppsBtn.addEventListener('click', async () => {
  setStatus('Building kit apps…', '');
  showOutput('');
  buildAppsBtn.disabled = true;
  const result = await window.pdKit.runAction('buildApps');
  buildAppsBtn.disabled = false;
  if (!result.ok) {
    setStatus(result.error || `Build failed (${result.code ?? 'error'})`, 'error');
    if (result.output) showOutput(result.output);
    return;
  }
  setStatus('Kit apps rebuilt', 'ok');
  if (result.output) showOutput(result.output);
  await refresh();
});

revealReleaseBtn.addEventListener('click', async () => {
  const info = latestInfo || (await window.pdKit.getInfo());
  const target = info.releaseDir || info.repoRoot;
  const result = await window.pdKit.revealPath(target);
  if (!result.ok) {
    setStatus(result.error || 'Could not reveal folder', 'error');
  }
});

refresh().catch((error) => {
  setStatus(String(error), 'error');
});
