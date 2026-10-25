const LOCAL_MODE_KEY = 'almojtahed_use_local_models';
const LOCAL_MODEL_KEY = 'almojtahed_local_model_id';
const PROVIDER_MODEL_BACKUP = 'almojtahed_provider_model_backup';

function localText(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function localCatalog() {
  return Array.isArray(window.localModelsList) ? window.localModelsList : [];
}

function chosenLocalId() {
  const saved = localStorage.getItem(LOCAL_MODEL_KEY) || '';
  const list = localCatalog();
  if (list.some((model) => model.id === saved)) return saved;
  return list[0] ? list[0].id : '';
}

function fillLocalSelect(selectEl, selected) {
  if (!selectEl) return;
  const list = localCatalog();
  const current = selected && list.some((model) => model.id === selected) ? selected : chosenLocalId();
  if (!list.length) {
    selectEl.innerHTML = '<option value="">لا توجد نماذج محلية</option>';
    return;
  }
  selectEl.innerHTML = list.map((model) => {
    const label = `${model.name || model.filename}${model.size_str ? ' · ' + model.size_str : ''}`;
    return `<option value="${localText(model.id)}" ${model.id === current ? 'selected' : ''}>${localText(label)}</option>`;
  }).join('');
  if (current) selectEl.value = current;
}

function renderLocalChatDropdown() {
  const id = chosenLocalId();
  const model = localCatalog().find((item) => item.id === id);
  const badge = document.getElementById('chatActiveProviderName');
  const listEl = document.getElementById('chatCustomModelOptionsList');
  const trigger = document.getElementById('chatCustomModelTriggerText');
  if (badge) badge.textContent = 'النماذج المحلية';
  fillLocalSelect(document.getElementById('chatModelSelect'), id);
  if (listEl) {
    listEl.innerHTML = localCatalog().map((item) => `
      <div class="custom-model-item ${item.id === id ? 'active' : ''}" data-model-id="${localText(item.id)}" data-model-name="${localText(item.name)}" onclick="selectCustomChatModel('${localText(item.id)}', '${localText(item.name).replace(/'/g, '&#39;')}')">
        <span class="custom-model-item-name">${localText(item.name)}</span>
        <span class="custom-model-item-tag">محلي</span>
      </div>
    `).join('') || '<div class="model-group-title">لا توجد نماذج محلية</div>';
  }
  if (trigger) {
    trigger.textContent = model ? model.name : 'لا توجد نماذج محلية';
    trigger.title = id;
  }
  if (id) localStorage.setItem('almojtahed_active_chat_model', id);
  if (typeof refreshCompareModelLists === 'function') refreshCompareModelLists();
}

function renderLocalAgentDropdown() {
  const hidden = document.getElementById('agentSelectedModelId');
  const id = hidden && localCatalog().some((model) => model.id === hidden.value) ? hidden.value : chosenLocalId();
  const model = localCatalog().find((item) => item.id === id);
  const listEl = document.getElementById('agentCustomModelOptionsList');
  const trigger = document.getElementById('agentCustomModelTriggerText');
  if (hidden && id) hidden.value = id;
  if (trigger) trigger.textContent = model ? model.name : 'لا توجد نماذج محلية';
  if (!listEl) return;
  listEl.innerHTML = localCatalog().map((item) => `
    <div class="custom-model-item ${item.id === id ? 'active' : ''}" data-model-id="${localText(item.id)}" data-model-name="${localText(item.name)}" onclick="selectCustomAgentModel('${localText(item.id)}', '${localText(item.name).replace(/'/g, '&#39;')}')">
      <span class="custom-model-item-name">${localText(item.name)}</span>
      <span class="custom-model-item-tag">محلي</span>
    </div>
  `).join('');
}

function refreshLocalModelSurfaces() {
  const id = chosenLocalId();
  renderLocalChatDropdown();
  renderLocalAgentDropdown();
  ['architectModelSelect', 'manualProjectDirectorModel', 'pDirectorModel', 'pSubagentModelSelect', 'toolAiModelSelect', 'p2cModelSelect'].forEach((elementId) => {
    fillLocalSelect(document.getElementById(elementId), id);
  });
  const subBadge = document.getElementById('pSubagentModelCountBadge');
  const toolBadge = document.getElementById('toolAiModelCountBadge');
  const count = `${localCatalog().length} نموذج محلي`;
  if (subBadge) subBadge.textContent = count;
  if (toolBadge) toolBadge.textContent = count;
}

function installLocalModelHooks() {
  if (window._localModelHooks) return;
  window._localModelHooks = true;
  const wrap = (name, localFn) => {
    const original = window[name];
    if (typeof original !== 'function') return;
    window[name] = function (...args) {
      if (window.localModelsActive) return localFn.apply(this, args);
      return original.apply(this, args);
    };
  };
  wrap('syncChatModelDropdown', () => renderLocalChatDropdown());
  wrap('populateAgentModelDropdown', () => renderLocalAgentDropdown());
  wrap('populateOpenRouterModelDropdown', (selectEl, selected) => fillLocalSelect(selectEl, selected));
  wrap('populateProjectSubagentModelsDropdown', async () => refreshLocalModelSurfaces());
  wrap('initToolAiModels', async () => refreshLocalModelSurfaces());
  wrap('populateP2CModelsDropdown', () => fillLocalSelect(document.getElementById('p2cModelSelect'), chosenLocalId()));
  if (typeof window.compareModelCatalog === 'function') {
    const originalCatalog = window.compareModelCatalog;
    window.compareModelCatalog = function () {
      if (window.localModelsActive) return localCatalog();
      return originalCatalog();
    };
  }
}

function paintLocalMode(active) {
  window.localModelsActive = !!active;
  const card = document.getElementById('providerServiceCard');
  if (card) card.classList.toggle('local-mode-locked', !!active);
  const badge = document.getElementById('localModelsModeBadge');
  const button = document.getElementById('btnToggleLocalModels');
  if (badge) badge.textContent = active ? 'النماذج المحلية فعّالة' : 'المزود السحابي فعّال';
  if (button) button.textContent = active ? 'إيقاف النماذج المحلية' : 'تفعيل النماذج المحلية';
}

function applyLocalMode(active) {
  if (active) {
    const current = localStorage.getItem('almojtahed_active_chat_model') || '';
    if (!current.startsWith('local:')) localStorage.setItem(PROVIDER_MODEL_BACKUP, current);
    const id = chosenLocalId();
    if (id) {
      localStorage.setItem(LOCAL_MODEL_KEY, id);
      localStorage.setItem('almojtahed_active_chat_model', id);
    }
    localStorage.setItem(LOCAL_MODE_KEY, '1');
    paintLocalMode(true);
    refreshLocalModelSurfaces();
    return;
  }
  localStorage.setItem(LOCAL_MODE_KEY, '0');
  paintLocalMode(false);
  const backup = localStorage.getItem(PROVIDER_MODEL_BACKUP) || '';
  if (backup && !backup.startsWith('local:')) localStorage.setItem('almojtahed_active_chat_model', backup);
  if (typeof syncChatModelDropdown === 'function') syncChatModelDropdown();
  if (typeof populateAgentModelDropdown === 'function') populateAgentModelDropdown();
  if (typeof refreshCompareModelLists === 'function') refreshCompareModelLists();
}

function renderLocalSection() {
  const select = document.getElementById('localModelSelect');
  fillLocalSelect(select, chosenLocalId());
  if (!localCatalog().length && select) {
    select.innerHTML = '<option value="">لا توجد نماذج محلية بعد</option>';
  }
}

function selectLocalModel(modelId) {
  if (!modelId) return;
  localStorage.setItem(LOCAL_MODEL_KEY, modelId);
  if (window.localModelsActive) {
    localStorage.setItem('almojtahed_active_chat_model', modelId);
    refreshLocalModelSurfaces();
  }
}

function toggleLocalModelForm() {
  const form = document.getElementById('localModelForm');
  if (!form) return;
  form.hidden = !form.hidden;
  if (!form.hidden) {
    const input = document.getElementById('localModelUrl');
    if (input) input.focus();
  }
}

function paintLocalDownload(download) {
  const wrap = document.getElementById('localDownloadWrap');
  const bar = document.getElementById('localDownloadBar');
  const label = document.getElementById('localDownloadLabel');
  if (!download || (!download.running && !download.message && !download.error)) {
    if (wrap) wrap.hidden = true;
    return;
  }
  if (wrap) wrap.hidden = false;
  const form = document.getElementById('localModelForm');
  if (form && download.running) form.hidden = false;
  const percent = Math.max(0, Math.min(100, Number(download.percent) || 0));
  if (bar) bar.style.width = `${Math.max(percent, download.running ? 4 : 0)}%`;
  if (label) {
    const size = download.expected_gb ? ` · ${download.received_gb || 0} / ${download.expected_gb} GB` : '';
    label.textContent = `${download.error || download.message || 'جارٍ السحب'}${size}`;
  }
}

async function loadLocalModels() {
  try {
    const res = await fetch('/api/local-models');
    if (!res.ok) return;
    const data = await res.json();
    window.localModelsList = data.models || [];
    renderLocalSection();
    paintLocalDownload(data.download || {});
    if (window.localModelsActive) refreshLocalModelSurfaces();
    const running = !!(data.download && data.download.running);
    if (running && !window._localDownloadPoller) {
      window._localDownloadPoller = setInterval(loadLocalModels, 1500);
    }
    if (!running && window._localDownloadPoller) {
      clearInterval(window._localDownloadPoller);
      window._localDownloadPoller = null;
    }
  } catch (err) {
    console.warn('local models', err);
  }
}

async function startLocalModelDownload() {
  const input = document.getElementById('localModelUrl');
  const url = (input?.value || '').trim();
  const label = document.getElementById('localDownloadLabel');
  const wrap = document.getElementById('localDownloadWrap');
  if (!url) {
    if (label) label.textContent = 'ضع رابط النموذج أولاً';
    if (wrap) wrap.hidden = false;
    return;
  }
  if (wrap) wrap.hidden = false;
  if (label) label.textContent = 'جارٍ بدء السحب';
  try {
    const res = await fetch('/api/local-models/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await res.json();
    paintLocalDownload(data.download || { running: false, message: data.message || data.detail || 'تعذر بدء السحب' });
    if (!res.ok && label) label.textContent = data.detail || data.message || 'تعذر بدء السحب';
    await loadLocalModels();
  } catch (err) {
    if (label) label.textContent = 'تعذر بدء السحب';
  }
}

function toggleLocalModelsMode() {
  const next = !window.localModelsActive;
  if (next && !localCatalog().length) {
    const hint = document.getElementById('localModelsHint');
    if (hint) hint.textContent = 'أضف نموذجاً محلياً أولاً، ثم فعّل النماذج المحلية.';
    toggleLocalModelForm();
    return;
  }
  applyLocalMode(next);
}

window.selectLocalModel = selectLocalModel;
window.toggleLocalModelForm = toggleLocalModelForm;
window.startLocalModelDownload = startLocalModelDownload;
window.toggleLocalModelsMode = toggleLocalModelsMode;

installLocalModelHooks();
document.addEventListener('DOMContentLoaded', () => {
  const active = localStorage.getItem(LOCAL_MODE_KEY) === '1';
  paintLocalMode(active);
  loadLocalModels().then(() => {
    if (active && localCatalog().length) applyLocalMode(true);
    else if (active) paintLocalMode(false);
  });
});
