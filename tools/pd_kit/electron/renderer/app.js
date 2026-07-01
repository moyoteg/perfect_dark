'use strict';

const toolGrid = document.getElementById('toolGrid');
const kitTitle = document.getElementById('kitTitle');
const kitSubtitle = document.getElementById('kitSubtitle');
const kitVersionPill = document.getElementById('kitVersionPill');
const portVersionPill = document.getElementById('portVersionPill');
const repoLine = document.getElementById('repoLine');
const statusLine = document.getElementById('statusLine');
const playBtn = document.getElementById('playBtn');
const testMapBtn = document.getElementById('testMapBtn');
const revealReleaseBtn = document.getElementById('revealReleaseBtn');

function setStatus(message, kind) {
  statusLine.textContent = message;
  statusLine.className = `status ${kind || ''}`.trim();
}

function renderTools(tools) {
  toolGrid.innerHTML = '';
  tools.forEach((tool) => {
    const card = document.createElement('article');
    card.className = 'card';
    const badgeClass = tool.built ? 'badge ok' : 'badge warn';
    const badgeText = tool.built
      ? tool.wrapped
        ? 'Wrapped in kit'
        : 'Available'
      : 'Not built';
    card.innerHTML = `
      <h2>${tool.shortTitle}</h2>
      <p>${tool.description}</p>
      <div class="card-footer">
        <span class="${badgeClass}">${badgeText}</span>
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
      const result = await window.pdKit.launchApp(appKey);
      if (!result.ok) {
        setStatus(result.error || 'Launch failed', 'error');
        return;
      }
      setStatus(`Launched ${appKey}`, 'ok');
    });
  });
}

async function refresh() {
  const info = await window.pdKit.getInfo();
  kitTitle.textContent = info.name;
  kitSubtitle.textContent = info.gameBinary.built
    ? 'All kit tools launch from this hub. Game binary is ready.'
    : 'Build the kit to wrap tools and enable Play.';
  kitVersionPill.textContent = `Kit v${info.kitVersion}`;
  portVersionPill.textContent = `Port v${info.portVersion}`;
  repoLine.textContent = info.repoRoot || 'Repo root not resolved';
  playBtn.disabled = !info.gameBinary.built;
  testMapBtn.disabled = !info.gameBinary.built;
  renderTools(info.tools);
}

playBtn.addEventListener('click', async () => {
  setStatus('Launching game…', '');
  const result = await window.pdKit.launchGame({ mod: 'mod_allinone' });
  if (!result.ok) {
    setStatus(result.error || 'Launch failed', 'error');
    return;
  }
  setStatus('Game launched', 'ok');
});

testMapBtn.addEventListener('click', async () => {
  setStatus('Launching test map…', '');
  const result = await window.pdKit.launchGame({ mod: 'mod_allinone', testMap: true });
  if (!result.ok) {
    setStatus(result.error || 'Launch failed', 'error');
    return;
  }
  setStatus('Test map launched', 'ok');
});

revealReleaseBtn.addEventListener('click', async () => {
  const info = await window.pdKit.getInfo();
  const target = info.releaseDir || info.repoRoot;
  const result = await window.pdKit.revealPath(target);
  if (!result.ok) {
    setStatus(result.error || 'Could not reveal folder', 'error');
  }
});

refresh().catch((error) => {
  setStatus(String(error), 'error');
});
