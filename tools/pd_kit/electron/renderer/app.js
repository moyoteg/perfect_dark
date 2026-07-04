'use strict';

const toolGrid = document.getElementById('toolGrid');
const moreToolsSection = document.getElementById('moreToolsSection');
const moreToolsDetails = document.getElementById('moreToolsDetails');
const moreToolGrid = document.getElementById('moreToolGrid');
const moreToolsSectionNote = document.getElementById('moreToolsSectionNote');
const actionSections = document.getElementById('actionSections');
const docGrid = document.getElementById('docGrid');
const toolsSection = document.getElementById('toolsSection');
const docsSection = document.getElementById('docsSection');
const toolsSectionNote = document.getElementById('toolsSectionNote');
const docsSectionNote = document.getElementById('docsSectionNote');
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
const kitSearchInput = document.getElementById('kitSearchInput');
const kitSearchClear = document.getElementById('kitSearchClear');
const kitSearchMeta = document.getElementById('kitSearchMeta');
const kitSearchEmpty = document.getElementById('kitSearchEmpty');

/** @type {ReturnType<typeof window.pdKit.getInfo> extends Promise<infer T> ? T : never} | null */
let latestInfo = null;
/** @type {Set<string>} */
const launchInFlight = new Set();
/** @type {string} */
let searchQuery = '';

/** Visual glyphs for quick scanning (static — safe for innerHTML). */
const KIT_ICONS = {
  apps: {
    mapEditor: { glyph: '🗺️', tone: 'authoring', label: 'Map authoring' },
    mapLauncher: { glyph: '🚀', tone: 'companion', label: 'Curriculum launcher' },
    animLab: { glyph: '🎭', tone: 'authoring', label: 'Animation research' },
    objectCatalog: { glyph: '📦', tone: 'authoring', label: 'Asset browser' },
    agentOffice: { glyph: '🏢', tone: 'companion', label: 'Agent simulation' },
    assetUpgrader: { glyph: '✨', tone: 'authoring', label: 'Texture upgrade' },
    playLastTestMap: { glyph: '▶️', tone: 'companion', label: 'Replay last test' },
    llmPlay: { glyph: '🤖', tone: 'companion', label: 'LLM orchestration' },
  },
  actionGroups: {
    build: '🔨',
    validate: '✅',
    scenarios: '🎮',
    setup: '⚙️',
  },
  actions: {
    buildApps: '📱',
    buildGame: '🎮',
    buildFullKit: '📦',
    validateMaps: '📋',
    validateNext: '⏭️',
    validateStatus: '📊',
    playLearnStep: '🎓',
    launchAioMod: '🌐',
    matrixBattle: '⚔️',
    playAgentOffice: '🏙️',
    playAgentOfficeCi: '🏛️',
    startAgentOfficeDirector: '🎙️',
    stopAgentOfficeDirector: '⏹️',
    resetUffTestMap: '🔄',
    rebuildMapEditor: '🗺️',
    rebuildLlmPlay: '🤖',
    linkRom: '💿',
    setupAssetUpgrader: '🐍',
    runAssetUpgrader: '✨',
    setupOllama: '🦙',
  },
  docs: {
    spec: '📜',
    stories: '📝',
    architecture: '🏗️',
    environments: '🌍',
    apiContracts: '🔌',
    kitReadme: '📘',
    mapWiki: '📖',
    mapSpec: '🧮',
    animations: '🕺',
    assetUpgraderReadme: '🖼️',
    learnCurriculum: '🎓',
  },
  categories: {
    authoring: '🛠️',
    companion: '🧩',
  },
};

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function appIcon(appKey, category) {
  const entry = KIT_ICONS.apps[appKey];
  if (entry) return entry;
  const tone = category === 'companion' ? 'companion' : 'authoring';
  return { glyph: KIT_ICONS.categories[tone] || '📱', tone, label: 'Kit app' };
}

function actionIcon(actionKey) {
  return KIT_ICONS.actions[actionKey] || '▶️';
}

function docIcon(docKey) {
  return KIT_ICONS.docs[docKey] || '📄';
}

function iconBadgeHtml(glyph, tone, sizeClass) {
  const cls = ['icon-badge', tone ? `icon-badge--${tone}` : '', sizeClass || '']
    .filter(Boolean)
    .join(' ');
  return `<span class="${cls}" aria-hidden="true">${glyph}</span>`;
}

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

function normalizeQuery(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ');
}

function queryTokens(query) {
  return normalizeQuery(query).split(' ').filter(Boolean);
}

function haystack(...parts) {
  return parts
    .flat()
    .filter((part) => part != null && part !== '')
    .map((part) => String(part).toLowerCase())
    .join(' ');
}

function matchesQuery(text, query) {
  const tokens = queryTokens(query);
  if (!tokens.length) return true;
  const hay = String(text || '');
  return tokens.every((token) => hay.includes(token));
}

function badgeForTool(tool) {
  if (tool.built) {
    if (tool.wrapped) return ['Wrapped in kit', 'ok'];
    if (tool.devMode) return ['Dev mode', 'ok'];
    return ['Available', 'ok'];
  }
  return tool.optional ? ['Optional — not built', 'warn'] : ['Not built', 'warn'];
}

function filteredTools(tools) {
  return (tools || []).filter((tool) =>
    matchesQuery(
      haystack(
        tool.shortTitle,
        tool.title,
        tool.description,
        tool.key,
        tool.category,
        tool.buildScript,
        tool.path,
        appIcon(tool.key, tool.category).label,
        appIcon(tool.key, tool.category).glyph
      ),
      searchQuery
    )
  );
}

function filteredActionGroups(groups) {
  return (groups || [])
    .map((group) => {
      const groupMatches = matchesQuery(haystack(group.title, group.id), searchQuery);
      const actions = (group.actions || []).filter(
        (action) =>
          groupMatches ||
          matchesQuery(
            haystack(action.shortTitle, action.description, action.key, group.title, group.id),
            searchQuery
          )
      );
      return { ...group, actions };
    })
    .filter((group) => group.actions.length > 0);
}

function filteredDocs(docs) {
  return (docs || []).filter((doc) =>
    matchesQuery(haystack(doc.title, doc.key, doc.path), searchQuery)
  );
}

function renderToolCards(gridEl, tools) {
  if (!gridEl) return;
  gridEl.innerHTML = '';
  tools.forEach((tool) => {
    const [badgeText, badgeKind] = badgeForTool(tool);
    const icon = appIcon(tool.key, tool.category);
    const categoryLabel = tool.category === 'companion' ? 'Companion' : 'Authoring';
    const card = document.createElement('article');
    card.className = 'card';
    card.innerHTML = `
      <div class="card-top">
        ${iconBadgeHtml(icon.glyph, icon.tone, 'icon-badge--lg')}
        <div class="card-heading">
          <h3>${escapeHtml(tool.shortTitle)}</h3>
          <span class="category-chip category-chip--${icon.tone}">${icon.glyph} ${categoryLabel}</span>
        </div>
      </div>
      <p>${escapeHtml(tool.description)}</p>
      <div class="card-footer">
        <span class="badge ${badgeKind}">${escapeHtml(badgeText)}</span>
      </div>
      <button type="button" data-app-key="${escapeHtml(tool.key)}" ${tool.built ? '' : 'disabled'}>
        ${icon.glyph} Open ${escapeHtml(tool.shortTitle)}
      </button>
    `;
    card.querySelector('button')?.setAttribute('aria-label', `Open ${tool.title || tool.shortTitle}`);
    gridEl.appendChild(card);
  });

  gridEl.querySelectorAll('button[data-app-key]').forEach((button) => {
    button.addEventListener('click', async () => {
      const appKey = button.getAttribute('data-app-key');
      if (!appKey || launchInFlight.has(appKey)) return;
      launchInFlight.add(appKey);
      button.disabled = true;
      setStatus(`Opening ${appKey}…`, '');
      showOutput('');
      try {
        const result = await window.pdKit.launchApp(appKey);
        if (!result.ok) {
          setStatus(result.error || 'Launch failed', 'error');
          return;
        }
        setStatus(result.skipped ? `Already opening ${appKey}` : `Launched ${appKey}`, 'ok');
      } catch (err) {
        setStatus(String(err?.message || err), 'error');
      } finally {
        launchInFlight.delete(appKey);
        button.disabled = false;
      }
    });
  });
}

function renderTools(tools) {
  renderToolCards(toolGrid, tools);
}

function renderMoreTools(tools) {
  renderToolCards(moreToolGrid, tools);
  if (moreToolsSection) {
    moreToolsSection.classList.toggle('hidden', tools.length === 0);
  }
  if (moreToolsDetails && tools.length > 0 && queryTokens(searchQuery).length > 0) {
    moreToolsDetails.open = true;
  }
}

function renderActionGroups(groups, gameBuilt) {
  actionSections.innerHTML = '';
  groups.forEach((group) => {
    const groupGlyph = KIT_ICONS.actionGroups[group.id] || '⚡';
    const section = document.createElement('section');
    section.className = 'section nested';
    section.innerHTML = `
      <div class="section-head section-head--icon">
        ${iconBadgeHtml(groupGlyph, group.id, 'icon-badge--md')}
        <h2>${escapeHtml(group.title)}</h2>
      </div>
      <div class="grid compact"></div>
    `;
    const grid = section.querySelector('.grid');
    (group.actions || []).forEach((action) => {
      const disabled = action.requiresGame && !gameBuilt;
      const glyph = actionIcon(action.key);
      const card = document.createElement('article');
      card.className = 'card compact-card';
      card.innerHTML = `
        <div class="card-top card-top--compact">
          ${iconBadgeHtml(glyph, group.id, 'icon-badge--sm')}
          <h3>${escapeHtml(action.shortTitle)}</h3>
        </div>
        <p>${escapeHtml(action.description)}</p>
        <button type="button" data-action-key="${escapeHtml(action.key)}" ${disabled ? 'disabled' : ''}>
          ${glyph} Run
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
    const glyph = docIcon(doc.key);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'doc-link';
    button.innerHTML = `<span class="doc-link-icon" aria-hidden="true">${glyph}</span><span class="doc-link-text">${escapeHtml(doc.title)}</span>`;
    button.disabled = !doc.exists;
    button.title = doc.path;
    button.setAttribute('aria-label', `Open ${doc.title}`);
    button.addEventListener('click', async () => {
      const result = await window.pdKit.openDoc(doc.key);
      if (!result.ok) {
        setStatus(result.error || 'Could not open doc', 'error');
      }
    });
    docGrid.appendChild(button);
  });
}

function updateFilterChrome(toolCount, moreToolCount, actionCount, docCount, totals) {
  const active = queryTokens(searchQuery).length > 0;
  kitSearchClear.hidden = !active;

  if (!active) {
    kitSearchMeta.textContent = '';
    kitSearchEmpty.classList.add('hidden');
    toolsSectionNote.textContent = 'Map Editor, Anim Lab, and Asset Upgrader';
    if (moreToolsSectionNote) {
      moreToolsSectionNote.textContent = 'Optional companions — shown when built';
    }
    docsSectionNote.textContent = 'Workflow guides and reference specs';
    return;
  }

  const totalShown = toolCount + moreToolCount + actionCount + docCount;
  kitSearchMeta.textContent = `${totalShown} match${totalShown === 1 ? '' : 'es'}`;
  kitSearchEmpty.classList.toggle('hidden', totalShown > 0);
  toolsSectionNote.textContent =
    toolCount === totals.tools
      ? 'Map Editor, Anim Lab, and Asset Upgrader'
      : `${toolCount} of ${totals.tools} core apps`;
  if (moreToolsSectionNote) {
    moreToolsSectionNote.textContent =
      moreToolCount === totals.moreTools
        ? 'Optional companions — shown when built'
        : `${moreToolCount} of ${totals.moreTools} optional tools`;
  }
  docsSectionNote.textContent =
    docCount === totals.docs
      ? 'Workflow guides and reference specs'
      : `${docCount} of ${totals.docs} docs`;
}

function renderFiltered() {
  if (!latestInfo) return;

  const tools = filteredTools(latestInfo.tools);
  const moreTools = filteredTools(latestInfo.moreTools || []);
  const groups = filteredActionGroups(latestInfo.actionGroups || []);
  const docs = filteredDocs(latestInfo.docs || []);
  const actionCount = groups.reduce((sum, group) => sum + (group.actions || []).length, 0);

  renderTools(tools);
  renderMoreTools(moreTools);
  renderActionGroups(groups, latestInfo.gameBinary.built);
  renderDocs(docs);

  toolsSection.classList.toggle('hidden', tools.length === 0);
  actionSections.classList.toggle('hidden', groups.length === 0);
  docsSection.classList.toggle('hidden', docs.length === 0);

  updateFilterChrome(tools.length, moreTools.length, actionCount, docs.length, {
    tools: (latestInfo.tools || []).length,
    moreTools: (latestInfo.moreTools || []).length,
    docs: (latestInfo.docs || []).length,
  });
}

async function refresh() {
  const info = await window.pdKit.getInfo();
  latestInfo = info;
  kitTitle.innerHTML = `<span class="hero-icon" aria-hidden="true">🎯</span> ${escapeHtml(info.name)}`;
  kitSubtitle.textContent = info.gameBinary.built
    ? 'Three core authoring apps plus scripts and docs from one hub.'
    : 'Build the game binary to enable Play and scenario launchers.';
  kitVersionPill.textContent = `Kit v${info.kitVersion}`;
  portVersionPill.textContent = `Port v${info.portVersion}`;
  repoLine.textContent = info.repoRoot || 'Repo root not resolved';
  playBtn.disabled = !info.gameBinary.built;
  testMapBtn.disabled = !info.gameBinary.built;
  renderFiltered();
}

let searchTimer = null;
if (kitSearchInput) {
  kitSearchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchQuery = kitSearchInput.value;
      renderFiltered();
    }, 60);
  });

  kitSearchInput.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && kitSearchInput.value) {
      event.preventDefault();
      kitSearchInput.value = '';
      searchQuery = '';
      renderFiltered();
    }
  });
}

if (kitSearchClear && kitSearchInput) {
  kitSearchClear.addEventListener('click', () => {
    kitSearchInput.value = '';
    searchQuery = '';
    renderFiltered();
    kitSearchInput.focus();
  });
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
