let compareSlots = [];
let compareTurns = [];
let compareBusy = false;
let compareTimers = {};
let compareAboutCache = {};
let compareClock = null;
let compareGeneration = 0;
let compareAgentsRendering = false;
const compareFolded = new Set();

function compareModelCatalog() {
  const live = (window.openrouterModelsList || []).filter(model => model && model.id && model.id !== 'local-almojtahed-8b');
  if (live.length) return live;
  return [
    { id: 'google/gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
    { id: 'google/gemini-2.5-pro', name: 'Gemini 2.5 Pro' },
    { id: 'anthropic/claude-3.7-sonnet', name: 'Claude 3.7 Sonnet' },
    { id: 'deepseek/deepseek-r1', name: 'DeepSeek R1' },
    { id: 'openai/gpt-4o', name: 'GPT-4o' },
    { id: 'openai/gpt-4o-mini', name: 'GPT-4o Mini' }
  ];
}

function compareModelName(modelId) {
  const found = compareModelCatalog().find(model => model.id === modelId);
  return found ? (found.name || found.id) : (modelId || 'اختر نموذجاً');
}

function initCompareTab() {
  if (!compareSlots.length) {
    const saved = localStorage.getItem('almojtahed_active_chat_model');
    const catalog = compareModelCatalog();
    const savedModel = catalog.find(model => model.id === saved);
    const savedIsImage = savedModel && /image|vision/i.test(`${savedModel.id} ${savedModel.name || ''}`);
    const preferred = catalog.find(model => /gemini-2\.5-flash/.test(model.id) && !/image/i.test(model.id));
    const first = (savedModel && !savedIsImage) ? savedModel.id : (preferred || catalog[0]).id;
    compareSlots = [{ id: first, query: '', open: false }];
  }
  if (typeof loadOpenRouterModelsList === 'function' && !(window.openrouterModelsList || []).length) {
    loadOpenRouterModelsList();
  }
  renderCompareTab();
  renderCompareAgents();
}

function refreshCompareModelLists() {
  if (!document.getElementById('paneCompare')?.classList.contains('active')) return;
  renderCompareTab();
}

function addCompareSlot() {
  if (compareSlots.length >= 2) return;
  const used = new Set(compareSlots.map(slot => slot.id));
  const next = compareModelCatalog().find(model => !used.has(model.id)) || compareModelCatalog()[0];
  compareSlots.push({ id: next.id, query: '', open: false });
  renderCompareTab();
}

function removeCompareSlot(index) {
  if (compareSlots.length < 2) return;
  compareSlots.splice(index, 1);
  renderCompareTab();
}

function toggleCompareMenu(index) {
  compareSlots.forEach((slot, slotIndex) => {
    slot.open = slotIndex === index ? !slot.open : false;
  });
  renderCompareTab();
  const input = document.querySelector(`#comparePickers [data-slot="${index}"] .compare-slot-search`);
  if (input) input.focus();
}

function filterCompareSlot(index, value) {
  compareSlots[index].query = value || '';
  const menu = document.querySelector(`#comparePickers [data-slot="${index}"] .compare-slot-items`);
  if (!menu) return;
  const query = compareSlots[index].query.trim().toLowerCase();
  menu.innerHTML = compareSlotItems(compareSlots[index], query);
}

function chooseCompareModel(index, modelId) {
  compareSlots[index].id = modelId;
  compareSlots[index].open = false;
  compareSlots[index].query = '';
  renderCompareTab();
}

function compareSlotItems(slot, query) {
  return compareModelCatalog()
    .filter(model => {
      const haystack = `${model.name || ''} ${model.id}`.toLowerCase();
      return !query || haystack.includes(query);
    })
    .slice(0, 80)
    .map(model => `
      <div class="compare-slot-item ${model.id === slot.id ? 'active' : ''}" data-id="${model.id}">
        ${escapeHtml(model.name || model.id)}
      </div>
    `).join('') || '<div class="compare-slot-item">لا توجد نتائج</div>';
}

function renderCompareTab() {
  const pickers = document.getElementById('comparePickers');
  const columns = document.getElementById('compareColumns');
  if (!pickers || !columns) return;

  pickers.innerHTML = compareSlots.map((slot, index) => `
    <div class="compare-slot ${slot.open ? 'open' : ''}" data-slot="${index}">
      <button type="button" class="compare-slot-trigger" data-toggle="${index}">
        <span>${escapeHtml(compareModelName(slot.id))}</span>
        ${index > 0 ? '<span class="compare-remove-slot" data-remove="' + index + '" title="إزالة النموذج">×</span>' : '<span>▾</span>'}
      </button>
      <div class="compare-slot-menu">
        <input class="compare-slot-search" placeholder="ابحث عن النموذج" value="${escapeHtml(slot.query || '')}">
        <div class="compare-slot-items">${compareSlotItems(slot, (slot.query || '').toLowerCase())}</div>
      </div>
    </div>
  `).join('') + (compareSlots.length < 2 ? '<button type="button" class="compare-add-btn" id="compareAddModel" title="إضافة النموذج الآخر">+</button>' : '');

  columns.classList.toggle('split', compareSlots.length > 1);
  columns.innerHTML = compareSlots.map(slot => {
    const folded = compareFolded.has(slot.id);
    return `
    <section class="compare-column ${folded ? 'is-folded' : ''}" data-column="${escapeHtml(slot.id)}">
      <div class="compare-column-head">
        <span class="compare-column-title">${escapeHtml(compareModelName(slot.id))}</span>
        <span class="compare-column-tools">
          <span class="compare-timer" data-timer="${escapeHtml(slot.id)}">${formatCompareElapsed(slot.id)}</span>
          <button type="button" class="compare-fold-btn" data-fold="${escapeHtml(slot.id)}" title="${folded ? 'عرض وصف النموذج والسعر والسياق' : 'طي وصف النموذج والسعر والسياق'}">${folded ? 'عرض' : 'طي'}</button>
        </span>
      </div>
      <div class="compare-model-meta">
        <div class="compare-about" data-about="${escapeHtml(slot.id)}">${compareAboutHtml(slot.id)}</div>
        ${compareSpecsHtml(slot.id)}
      </div>
      <div class="compare-column-body">${renderCompareMessages(slot.id)}</div>
    </section>
  `;
  }).join('');
  compareSlots.forEach(slot => loadCompareAbout(slot.id));
  if (typeof window.enhanceProjectCitationsWithBookReader === 'function') {
    try { window.enhanceProjectCitationsWithBookReader(columns); } catch (e) {}
  }
  if (typeof window.renderForce3dBlocks === 'function') {
    try { window.renderForce3dBlocks(columns); } catch (e) {}
  }

  columns.querySelectorAll('.compare-column-body').forEach(body => {
    body.scrollTop = body.scrollHeight;
  });
}

function renderCompareMessages(modelId) {
  if (!compareTurns.length) {
    return '<div class="compare-msg">سيظهر جواب هذا النموذج هنا.</div>';
  }
  return compareTurns.map(turn => {
    if (turn.role === 'user') {
      return `<div class="compare-msg user">${escapeHtml(turn.content)}</div>`;
    }
    const answer = turn.answers?.[modelId];
    if (!answer) {
      if (!compareBusy) return '';
      const pending = turn.searching ? 'جارٍ بحث الوكلاء في الشاملة ثم الإجابة...' : 'جارٍ الإجابة...';
      return `<div class="compare-msg">${pending}</div>`;
    }
    if (answer.error) return `<div class="compare-msg error">${escapeHtml(answer.error)}</div>`;
    if (answer.streaming) {
      const live = answer.reply ? escapeHtml(answer.reply) : 'يكتب الآن...';
      return `<div class="compare-msg assistant compare-streaming">${live}</div>`;
    }
    const reply = answer.reply || '';
    const html = (typeof formatMarkdown === 'function') ? formatMarkdown(reply) : ((typeof marked !== 'undefined' && marked.parse) ? marked.parse(reply) : escapeHtml(reply));
    return `<div class="compare-msg assistant">${html}</div>`;
  }).join('');
}

function historyForCompareModel(modelId) {
  const messages = [];
  compareTurns.forEach(turn => {
    if (turn.role === 'user') messages.push({ role: 'user', content: turn.content });
    const reply = turn.answers?.[modelId]?.reply;
    if (reply) messages.push({ role: 'assistant', content: reply });
  });
  return messages;
}

function formatCompareElapsed(modelId) {
  const timer = compareTimers[modelId];
  if (!timer) return '—';
  const ms = timer.running ? Date.now() - timer.startedAt : timer.elapsedMs;
  if (ms == null || ms < 0) return '—';
  if (ms < 1000) return `${Math.max(0, Math.round(ms / 100) / 10)} ث`;
  return `${(ms / 1000).toFixed(1)} ث`;
}

function paintCompareColumn(modelId, finalized) {
  const body = document.querySelector(`.compare-column[data-column="${CSS.escape(modelId)}"] .compare-column-body`);
  if (!body) {
    renderCompareTab();
    return;
  }
  body.innerHTML = renderCompareMessages(modelId);
  if (finalized && typeof window.enhanceProjectCitationsWithBookReader === 'function') {
    try { window.enhanceProjectCitationsWithBookReader(body); } catch (e) {}
  }
  if (finalized && typeof window.renderForce3dBlocks === 'function') {
    try { window.renderForce3dBlocks(body); } catch (e) {}
  }
  body.scrollTop = body.scrollHeight;
}

function refreshCompareTimers() {
  document.querySelectorAll('.compare-timer').forEach(node => {
    node.textContent = formatCompareElapsed(node.dataset.timer);
  });
}

function ensureCompareClock() {
  if (compareClock) return;
  compareClock = setInterval(() => {
    if (!Object.values(compareTimers).some(timer => timer.running)) {
      clearInterval(compareClock);
      compareClock = null;
      return;
    }
    refreshCompareTimers();
  }, 100);
}

function compareModelRecord(modelId) {
  return (window.openrouterModelsList || []).find(model => model && model.id === modelId) || null;
}

function compareSpecsHtml(modelId) {
  const model = compareModelRecord(modelId);
  if (!model || !model.pricing) {
    return '<div class="compare-specs"><span class="compare-about-muted">جارٍ جلب السعر وطول السياق...</span></div>';
  }
  const prompt1m = Number(model.pricing.prompt_per_1m || 0);
  const comp1m = Number(model.pricing.completion_per_1m || 0);
  const promptPerToken = model.pricing.prompt_per_token ? `$${Number(model.pricing.prompt_per_token).toFixed(8)}` : '$0.00';
  const compPerToken = model.pricing.completion_per_token ? `$${Number(model.pricing.completion_per_token).toFixed(8)}` : '$0.00';
  const ctx = model.context_length ? Number(model.context_length).toLocaleString() : 'غير محدد';
  return `
    <div class="compare-specs specs-stats-grid">
      <div class="spec-stat-item">
        <span class="spec-stat-label">سعر الإدخال (Prompt)</span>
        <div class="spec-stat-val"><strong>$${prompt1m.toFixed(3)}</strong> / 1M توكن<span class="compare-spec-sub">(${promptPerToken} للتوكن)</span></div>
      </div>
      <div class="spec-stat-item">
        <span class="spec-stat-label">سعر الإخراج (Completion)</span>
        <div class="spec-stat-val"><strong>$${comp1m.toFixed(3)}</strong> / 1M توكن<span class="compare-spec-sub">(${compPerToken} للتوكن)</span></div>
      </div>
      <div class="spec-stat-item">
        <span class="spec-stat-label">سياق النموذج (Context)</span>
        <div class="spec-stat-val">${escapeHtml(ctx)} توكن</div>
      </div>
    </div>
  `;
}

function compareAboutHtml(modelId) {
  const cached = compareAboutCache[modelId];
  if (!cached || cached.loading) return '<span class="compare-about-muted">جارٍ جلب تعريف النموذج...</span>';
  if (cached.error) return `<span class="compare-about-muted">${escapeHtml(cached.error)}</span>`;
  return escapeHtml(cached.text);
}

function loadCompareAbout(modelId) {
  if (!modelId || Object.prototype.hasOwnProperty.call(compareAboutCache, modelId)) return;
  compareAboutCache[modelId] = { loading: true };
  fetch('/api/openrouter/model-about?model_id=' + encodeURIComponent(modelId))
    .then(res => res.ok ? res.json() : Promise.reject())
    .then(data => {
      compareAboutCache[modelId] = { text: data.description || '' };
      const node = document.querySelector(`.compare-about[data-about="${CSS.escape(modelId)}"]`);
      if (node) node.textContent = data.description || 'لا يوجد تعريف لهذا النموذج.';
    })
    .catch(() => {
      compareAboutCache[modelId] = { error: 'تعذر جلب تعريف هذا النموذج.' };
      const node = document.querySelector(`.compare-about[data-about="${CSS.escape(modelId)}"]`);
      if (node) node.textContent = 'تعذر جلب تعريف هذا النموذج.';
    });
}

async function submitCompareQuestion(event) {
  event.preventDefault();
  if (compareBusy) return;
  const input = document.getElementById('compareInput');
  const question = (input?.value || '').trim();
  if (!question) return;
  if (!compareSlots.length || compareSlots.some(slot => !slot.id)) return;

  const generation = ++compareGeneration;
  const agentPayload = buildCompareAgentPayload();
  compareTurns.push({ role: 'user', content: question });
  const answerTurn = { role: 'assistant', answers: {}, searching: !!agentPayload };
  compareTurns.push(answerTurn);
  input.value = '';
  compareBusy = true;
  const button = document.getElementById('compareSendBtn');
  const clearButton = document.getElementById('compareClearBtn');
  if (button) button.disabled = true;
  if (clearButton) clearButton.disabled = false;
  compareSlots.forEach(slot => {
    compareTimers[slot.id] = { startedAt: Date.now(), elapsedMs: 0, running: true };
  });
  ensureCompareClock();
  renderCompareTab();

  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) { }

  let sharedSystem = '';
  if (agentPayload) {
    const prep = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: compareSlots[0].id,
        provider: 'openrouter',
        api_key: savedKeys.openrouter || '',
        messages: historyForCompareModel(compareSlots[0].id),
        use_hybrid: true,
        context_only: true,
        agent_group: agentPayload,
        agent_dispatch_mode: window.chatAgentDispatchMode || 'parallel'
      })
    });
    const prepData = await prep.json().catch(() => ({}));
    if (generation !== compareGeneration) return;
    if (!prep.ok || !prepData.system) {
      const message = prepData.detail || 'تعذر بحث الوكلاء في الشاملة';
      compareSlots.forEach(slot => {
        answerTurn.answers[slot.id] = { error: message };
        compareTimers[slot.id] = {
          startedAt: compareTimers[slot.id]?.startedAt || Date.now(),
          elapsedMs: Date.now() - (compareTimers[slot.id]?.startedAt || Date.now()),
          running: false
        };
      });
      renderCompareTab();
      compareBusy = false;
      if (button) button.disabled = false;
      return;
    }
    sharedSystem = prepData.system;
    compareSlots.forEach(slot => {
      answerTurn.answers[slot.id] = { reply: '', streaming: true };
    });
    answerTurn.searching = false;
    renderCompareTab();
  }

  await Promise.all(compareSlots.map(async slot => {
    const messages = historyForCompareModel(slot.id);
    const finish = (elapsedMs) => {
      compareTimers[slot.id] = {
        startedAt: compareTimers[slot.id]?.startedAt || Date.now(),
        elapsedMs,
        running: false
      };
      refreshCompareTimers();
    };
    try {
      const response = await fetch('/api/compare/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: savedKeys.openrouter || '',
          model: slot.id,
          messages,
          system: sharedSystem || undefined
        })
      });
      if (!response.ok || !response.body) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'تعذر الاتصال بالنموذج');
      }
      answerTurn.answers[slot.id] = { reply: '', streaming: true };
      paintCompareColumn(slot.id, false);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let reply = '';
      let reasoning = '';
      let paintQueued = false;
      const queuePaint = () => {
        if (paintQueued) return;
        paintQueued = true;
        requestAnimationFrame(() => {
          paintQueued = false;
          if (generation !== compareGeneration) return;
          answerTurn.answers[slot.id] = { reply, streaming: true };
          paintCompareColumn(slot.id, false);
        });
      };
      while (true) {
        const step = await reader.read();
        if (step.done || generation !== compareGeneration) break;
        buffer += decoder.decode(step.value, { stream: true });
        const pieces = buffer.split('\n\n');
        buffer = pieces.pop() || '';
        for (const piece of pieces) {
          const line = piece.split('\n').map(item => item.trim()).find(item => item.startsWith('data:'));
          if (!line) continue;
          let payload = null;
          try { payload = JSON.parse(line.slice(5).trim()); } catch (e) { continue; }
          if (payload.error) throw new Error(payload.error);
          if (payload.kind === 'reasoning') reasoning += payload.delta || '';
          if (payload.kind === 'content' && payload.delta) {
            reply += payload.delta;
            queuePaint();
          }
        }
      }
      if (generation !== compareGeneration) return;
      answerTurn.answers[slot.id] = { reply: reply || reasoning };
      finish(Date.now() - (compareTimers[slot.id]?.startedAt || Date.now()));
      paintCompareColumn(slot.id, true);
    } catch (error) {
      if (generation !== compareGeneration) return;
      answerTurn.answers[slot.id] = { error: error.message || 'تعذر الجواب' };
      finish(Date.now() - (compareTimers[slot.id]?.startedAt || Date.now()));
      paintCompareColumn(slot.id, true);
    }
  }));

  if (generation !== compareGeneration) return;
  compareBusy = false;
  if (button) button.disabled = false;
  if (clearButton) clearButton.disabled = false;
  refreshCompareTimers();
}

function clearCompareAnswers() {
  compareGeneration += 1;
  compareTurns = [];
  compareTimers = {};
  compareBusy = false;
  const button = document.getElementById('compareSendBtn');
  const clearButton = document.getElementById('compareClearBtn');
  if (button) button.disabled = false;
  if (clearButton) clearButton.disabled = false;
  renderCompareTab();
}

function compareAgentGroups() {
  let groups = [];
  try {
    const raw = localStorage.getItem('almojtahed_agent_groups');
    if (raw) groups = JSON.parse(raw);
  } catch (e) {}
  if ((!groups || !groups.length) && window.agentGroups) groups = window.agentGroups;
  return groups || [];
}

function renderCompareAgents() {
  const select = document.getElementById('compareAgentGroupSelect');
  const checkbox = document.getElementById('compareUseAgentGroupCheckbox');
  const picker = document.getElementById('compareAgentGroupPicker');
  if (!select || compareAgentsRendering) return;
  compareAgentsRendering = true;
  const groups = compareAgentGroups();
  const savedGroupId = localStorage.getItem('almojtahed_chat_selected_group_id') || (groups[0] ? groups[0].id : '');
  const savedEnabled = localStorage.getItem('almojtahed_chat_use_agent_group');
  const isEnabled = savedEnabled === null ? true : (savedEnabled === 'true');
  select.innerHTML = groups.length
    ? groups.map(group => `<option value="${escapeHtml(group.id)}" ${group.id === savedGroupId ? 'selected' : ''}>${escapeHtml(group.name)} (${(group.agents || []).length} وكلاء)</option>`).join('')
    : '<option value="">لا توجد مجموعات وكلاء</option>';
  if (checkbox) checkbox.checked = isEnabled && !!groups.length;
  if (picker) picker.classList.toggle('active', !!(checkbox && checkbox.checked));
  renderCompareSubAgents(select.value);
  updateCompareDispatchModeUI();
  compareAgentsRendering = false;
}

function renderCompareSubAgents(groupId) {
  const wrap = document.getElementById('compareSubAgentSelectWrap');
  const items = document.getElementById('compareSubAgentChecklistItems');
  const label = document.getElementById('compareSubAgentBtnLabel');
  const badge = document.getElementById('compareChecklistCountBadge');
  if (!wrap || !items) return;
  const group = compareAgentGroups().find(item => item.id === groupId);
  const agents = group?.agents || [];
  if (!agents.length) {
    wrap.style.display = 'none';
    return;
  }
  wrap.style.display = 'inline-flex';
  let selectedIds = [];
  try {
    const raw = localStorage.getItem('almojtahed_chat_selected_agents_' + groupId);
    if (raw) selectedIds = JSON.parse(raw);
  } catch (e) {}
  const selected = new Set(selectedIds);
  const useAll = !selectedIds.length;
  items.innerHTML = agents.map(agent => `
    <label class="chat-checklist-item">
      <input type="checkbox" value="${escapeHtml(agent.id)}" ${useAll || selected.has(agent.id) ? 'checked' : ''} onchange="saveCompareSubAgents()">
      <span>${escapeHtml(agent.name || 'وكيل')}</span>
    </label>
  `).join('');
  const count = useAll ? agents.length : agents.filter(agent => selected.has(agent.id)).length;
  if (label) label.textContent = (useAll || count === agents.length) ? 'كل وكلاء المجموعة' : `${count} من الوكلاء`;
  if (badge) badge.textContent = `تم تحديد ${count} وكيل`;
}

function handleCompareAgentToggle() {
  const checkbox = document.getElementById('compareUseAgentGroupCheckbox');
  localStorage.setItem('almojtahed_chat_use_agent_group', checkbox?.checked ? 'true' : 'false');
  if (!compareAgentsRendering && typeof populateChatAgentGroupsDropdown === 'function') populateChatAgentGroupsDropdown();
  renderCompareAgents();
}

function handleCompareAgentGroupChange() {
  const select = document.getElementById('compareAgentGroupSelect');
  if (select?.value) localStorage.setItem('almojtahed_chat_selected_group_id', select.value);
  if (!compareAgentsRendering && typeof populateChatAgentGroupsDropdown === 'function') populateChatAgentGroupsDropdown();
  renderCompareSubAgents(select?.value || '');
}

function saveCompareSubAgents() {
  const select = document.getElementById('compareAgentGroupSelect');
  const group = compareAgentGroups().find(item => item.id === select?.value);
  const boxes = [...document.querySelectorAll('#compareSubAgentChecklistItems input[type="checkbox"]')];
  const chosen = boxes.filter(box => box.checked).map(box => box.value);
  const all = !boxes.length || chosen.length === boxes.length;
  localStorage.setItem('almojtahed_chat_selected_agents_' + (select?.value || ''), JSON.stringify(all ? [] : chosen));
  const label = document.getElementById('compareSubAgentBtnLabel');
  const badge = document.getElementById('compareChecklistCountBadge');
  if (label) label.textContent = all ? 'كل وكلاء المجموعة' : `${chosen.length} من الوكلاء`;
  if (badge) badge.textContent = `تم تحديد ${chosen.length} وكيل`;
  if (typeof populateSubAgentsDropdown === 'function') populateSubAgentsDropdown(select?.value || '');
}

function selectAllCompareSubAgents(selectAll) {
  document.querySelectorAll('#compareSubAgentChecklistItems input[type="checkbox"]').forEach(box => { box.checked = !!selectAll; });
  saveCompareSubAgents();
}

function toggleCompareSubAgentsDropdown(event) {
  event.preventDefault();
  event.stopPropagation();
  const menu = document.getElementById('compareSubAgentChecklistMenu');
  if (!menu) return;
  menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
}

function closeCompareSubAgentsDropdown() {
  const menu = document.getElementById('compareSubAgentChecklistMenu');
  if (menu) menu.style.display = 'none';
}

function toggleCompareDispatchMode() {
  if (typeof window.toggleChatDispatchMode === 'function') window.toggleChatDispatchMode();
  updateCompareDispatchModeUI();
}

function updateCompareDispatchModeUI() {
  const icon = document.getElementById('compareDispatchModeIcon');
  const text = document.getElementById('compareDispatchModeText');
  const direct = (window.chatAgentDispatchMode || localStorage.getItem('almojtahed_chat_dispatch_mode')) === 'direct';
  if (icon) icon.textContent = direct ? '🎯' : '⚡';
  if (text) text.textContent = direct ? 'موحد مباشر' : 'توزيع متوازي';
}

function buildCompareAgentPayload() {
  const checkbox = document.getElementById('compareUseAgentGroupCheckbox');
  const select = document.getElementById('compareAgentGroupSelect');
  if (!checkbox?.checked || !select?.value) return null;
  const group = compareAgentGroups().find(item => item.id === select.value);
  if (!group?.agents?.length) return null;
  let selectedIds = [];
  try {
    const raw = localStorage.getItem('almojtahed_chat_selected_agents_' + group.id);
    if (raw) selectedIds = JSON.parse(raw);
  } catch (e) {}
  let agents = group.agents;
  if (selectedIds.length) {
    const filtered = group.agents.filter(agent => selectedIds.includes(agent.id));
    if (filtered.length) agents = filtered;
  }
  const first = agents[0];
  const books = [];
  agents.forEach(agent => {
    const list = (agent.booksScope && Array.isArray(agent.booksScope)) ? agent.booksScope : (agent.scopeBooks || agent.books || []);
    list.forEach(book => {
      const name = String(book || '').trim();
      if (name && !books.includes(name)) books.push(name);
    });
  });
  const many = agents.length > 1;
  return {
    id: group.id,
    name: group.name,
    desc: group.desc || '',
    active_agent: {
      id: first.id,
      name: many ? `فريق الوكلاء المختارين (${agents.length})` : first.name,
      desc: many ? agents.map(agent => `[${agent.name}]: ${agent.desc || ''}`).join(' | ') : (first.desc || ''),
      model: first.model || 'google/gemini-2.5-flash',
      thinking: first.thinking || 'medium',
      system_prompt: many ? agents.map(agent => `### اختصاص وتوجيه الوكيل المساعد «${agent.name}»:\n${agent.systemPrompt || agent.desc || ''}`).join('\n\n') : (first.systemPrompt || ''),
      books,
      pool_size: parseInt(first.poolSize) || 250,
      top_k: parseInt(first.topK || first.top_k || first.topRerank) || 40,
      temp: first.temp !== undefined ? first.temp : 0.2
    },
    agents: agents.map(agent => {
      const list = (agent.booksScope && Array.isArray(agent.booksScope)) ? agent.booksScope : (agent.scopeBooks || agent.books || []);
      return {
        id: agent.id,
        name: agent.name,
        desc: agent.desc || '',
        system_prompt: agent.systemPrompt || '',
        model: agent.model || 'google/gemini-2.5-flash',
        thinking: agent.thinking || 'medium',
        books: list,
        pool_size: parseInt(agent.poolSize) || 250,
        top_k: parseInt(agent.topK || agent.top_k || agent.topRerank) || 40,
        temp: agent.temp !== undefined ? agent.temp : 0.2,
        scope_summary: list.length ? `${list.length} كتاب محدد` : 'شامل المخزن التراثي'
      };
    })
  };
}

function toggleCompareFold(modelId) {
  if (!modelId) return;
  if (compareFolded.has(modelId)) compareFolded.delete(modelId);
  else compareFolded.add(modelId);
  const column = document.querySelector(`.compare-column[data-column="${CSS.escape(modelId)}"]`);
  if (!column) return;
  const folded = compareFolded.has(modelId);
  column.classList.toggle('is-folded', folded);
  const button = column.querySelector('[data-fold]');
  if (button) {
    button.textContent = folded ? 'عرض' : 'طي';
    button.title = folded ? 'عرض وصف النموذج والسعر والسياق' : 'طي وصف النموذج والسعر والسياق';
  }
}

document.addEventListener('click', (event) => {
  const fold = event.target.closest('[data-fold]');
  if (fold) {
    event.preventDefault();
    event.stopPropagation();
    toggleCompareFold(fold.dataset.fold);
    return;
  }
  const add = event.target.closest('#compareAddModel');
  if (add) {
    addCompareSlot();
    return;
  }
  const remove = event.target.closest('[data-remove]');
  if (remove) {
    event.stopPropagation();
    removeCompareSlot(Number(remove.dataset.remove));
    return;
  }
  const toggle = event.target.closest('[data-toggle]');
  if (toggle) {
    toggleCompareMenu(Number(toggle.dataset.toggle));
    return;
  }
  const item = event.target.closest('.compare-slot-item[data-id]');
  if (item) {
    const slot = item.closest('[data-slot]');
    chooseCompareModel(Number(slot.dataset.slot), item.dataset.id);
    return;
  }
  if (!event.target.closest('#compareSubAgentSelectWrap')) closeCompareSubAgentsDropdown();
  if (!event.target.closest('.compare-slot')) {
    if (compareSlots.some(slot => slot.open)) {
      compareSlots.forEach(slot => { slot.slotOpen = false; slot.open = false; });
      renderCompareTab();
    }
  }
});

document.addEventListener('input', (event) => {
  if (!event.target.classList?.contains('compare-slot-search')) return;
  const slot = event.target.closest('[data-slot]');
  filterCompareSlot(Number(slot.dataset.slot), event.target.value);
});

window.clearCompareAnswers = clearCompareAnswers;
window.handleCompareAgentToggle = handleCompareAgentToggle;
window.handleCompareAgentGroupChange = handleCompareAgentGroupChange;
window.saveCompareSubAgents = saveCompareSubAgents;
window.selectAllCompareSubAgents = selectAllCompareSubAgents;
window.toggleCompareSubAgentsDropdown = toggleCompareSubAgentsDropdown;
window.closeCompareSubAgentsDropdown = closeCompareSubAgentsDropdown;
window.toggleCompareDispatchMode = toggleCompareDispatchMode;
window.renderCompareAgents = renderCompareAgents;

document.addEventListener('keydown', (event) => {
  const input = document.getElementById('compareInput');
  if (event.key === 'Enter' && document.activeElement === input && !event.shiftKey) {
    event.preventDefault();
    document.getElementById('compareComposer')?.requestSubmit();
  }
});
