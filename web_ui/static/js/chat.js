// =============================================================================
// منظومة المجتهد - واجهة الشات الذكي (chat.js)
// إدارة المحادثات، عمق التفكير، رفع المرفقات، والتواصل مع النماذج
// =============================================================================

const CHAT_STORAGE_KEY = 'almojtahed_chat_sessions';

let chatSessions = [];
let activeSessionId = null;
let currentThinkingLevel = 'medium'; // 'low' | 'medium' | 'high'
let currentAttachments = [];
let isChatHybridSearchEnabled = true;
let isSemanticEnhancedEnabled = false;

// =============================================================================
// خيار معزّز: قناة البحث الدلالي في مخزن المتجهات — قرار الباحث، تُعلن حالته
// في تقرير كل بحث (مفعّلة وباحثة / معطّلة بقراره / مفعّلة وغير متوفرة)
// =============================================================================
function initSemanticEnhancedState() {
  const saved = localStorage.getItem('almojtahed_semantic_enhanced_v2');
  if (saved !== null) isSemanticEnhancedEnabled = saved === 'true';
  updateSemanticEnhancedUI();
  // مؤشر التوفر الحي: مخزن متصل ونموذج تضمين محمّل؟
  fetch('/api/system/resources').then(r => r.ok ? r.json() : null).then(d => {
    if (!d) return;
    const avail = !!(d.qdrant && d.qdrant.connected && d.model && d.model.loaded);
    const btn = document.getElementById('btnToggleSemanticEnhanced');
    if (btn) btn.title = avail
      ? `الخيار المعزّز متاح الآن: مخزن «${(d.qdrant && d.qdrant.collection_name) || ''}» متصل ونموذج التضمين محمّل. سياسة معتمدة: يُفعَّل للمسائل النحيلة لفظيًا التي تعجز عنها المراسي، ويُترك مغلقًا في المسائل غنية اللفظ. انقر للتبديل.`
      : 'تنبيه: مخزن المتجهات أو نموذج التضمين غير متوفر حاليًا على هذا الجهاز؛ تفعيل الخيار لن يضيف قناة دلالية وسيُعلن ذلك في تقرير البحث. انقر للتبديل.';
    const lbl = document.getElementById('labelSemanticEnhanced');
    if (lbl && isSemanticEnhancedEnabled) lbl.textContent = avail ? '🧠 دلالي معزّز' : '🧠 دلالي (غير متوفر)';
  }).catch(() => {});
}

function toggleSemanticEnhanced() {
  isSemanticEnhancedEnabled = !isSemanticEnhancedEnabled;
  localStorage.setItem('almojtahed_semantic_enhanced_v2', isSemanticEnhancedEnabled);
  updateSemanticEnhancedUI();
  if (typeof showToast === 'function') {
    showToast(isSemanticEnhancedEnabled
      ? 'تم تفعيل الخيار المعزّز: قناة البحث الدلالي في مخزن المتجهات (إن توفرت) 🧠'
      : 'تم تعطيل القناة الدلالية بقرارك: بحث لفظي فقط في فهرس المكتبة');
  }
}

function updateSemanticEnhancedUI() {
  const btn = document.getElementById('btnToggleSemanticEnhanced');
  if (!btn) return;
  btn.classList.toggle('is-active', isSemanticEnhancedEnabled);
  btn.classList.toggle('is-disabled', !isSemanticEnhancedEnabled);
  btn.setAttribute('aria-pressed', isSemanticEnhancedEnabled ? 'true' : 'false');
}

// =============================================================================
// إدارة وتفعيل / تعطيل نمط استرجاع نصوص الشات (البحث الهجين: Dense + BM25)
// =============================================================================
function initChatHybridToggleState() {
  const saved = localStorage.getItem('almojtahed_chat_hybrid_search');
  if (saved !== null) {
    isChatHybridSearchEnabled = saved === 'true';
  } else {
    const globalHybrid = localStorage.getItem('almojtahed_hybrid_search');
    if (globalHybrid !== null) {
      isChatHybridSearchEnabled = globalHybrid === 'true';
    }
  }
  updateChatHybridToggleUI();
}

function toggleChatHybridSearchMode() {
  isChatHybridSearchEnabled = !isChatHybridSearchEnabled;
  localStorage.setItem('almojtahed_chat_hybrid_search', isChatHybridSearchEnabled);
  updateChatHybridToggleUI();
  if (typeof showToast === 'function') {
    if (isChatHybridSearchEnabled) {
      showToast('الشات الذكي: تم تفعيل استرجاع النصوص بالبحث الهجين (دلالي + لفظي) ⚡');
    } else {
      showToast('الشات الذكي: تم تفعيل استرجاع النصوص بالبحث الدلالي الصرف (Dense Only) 🧠');
    }
  }
}

function updateChatHybridToggleUI() {
  const btn = document.getElementById('btnToggleChatHybridSearch');
  const label = document.getElementById('labelChatHybridToggle');
  if (!btn || !label) return;

  if (isChatHybridSearchEnabled) {
    btn.classList.add('is-active');
    btn.classList.remove('is-disabled');
    btn.setAttribute('aria-pressed', 'true');
    btn.title = 'البحث الهجين في الشات مفعّل: استرجاع الشواهد التراثية بالدمج بين التضمين الدلالي والتطابق اللفظي BM25. انقر للتعطيل.';
    label.textContent = 'بحث هجين';
  } else {
    btn.classList.remove('is-active');
    btn.classList.add('is-disabled');
    btn.setAttribute('aria-pressed', 'false');
    btn.title = 'البحث الدلالي في الشات مفعّل. انقر لتفعيل البحث الهجين.';
    label.textContent = 'بحث دلالي';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initChatHistory();
  initChatHybridToggleState();
  initSemanticEnhancedState();
  populateChatAgentGroupsDropdown();
  renderChatMcpList();
  setTimeout(() => {
    if (typeof syncChatModelDropdown === 'function') {
      syncChatModelDropdown();
    }
    populateChatAgentGroupsDropdown();
    updateChatHybridToggleUI();
  }, 80);
  setTimeout(() => {
    populateChatAgentGroupsDropdown();
    updateChatHybridToggleUI();
  }, 400);
});

let chatSaveTimer = null;

function normalizeChatSessions(list) {
  return (Array.isArray(list) ? list : []).filter(s => {
    if (!s || !s.id) return false;
    return !s.messages?.some(m => m.content && m.content.includes("أجوبة التسولي عن مسائل الأمير عبد القادر") && !m.content.includes("ذخيرة العقبى"));
  });
}

// تهيئة سجل المحادثات من قاعدة الخادم، مع نقل ما تبقى في المتصفح مرة واحدة
async function initChatHistory() {
  await (window.almujtahedIdentity || Promise.resolve());
  const chatStorageKey = ownerStorageKey(CHAT_STORAGE_KEY);
  let localSessions = [];
  try {
    localSessions = normalizeChatSessions(JSON.parse(localStorage.getItem(chatStorageKey) || '[]'));
  } catch (e) {
    localSessions = [];
  }

  let remoteSessions = [];
  try {
    const res = await fetch('/api/chats');
    if (res.ok) {
      const data = await res.json();
      remoteSessions = normalizeChatSessions(data.sessions);
    }
  } catch (e) {
    console.error('Error loading chats from server:', e);
  }

  const known = new Set(remoteSessions.map(s => s.id));
  let imported = 0;
  localSessions.forEach(session => {
    if (!known.has(session.id)) {
      remoteSessions.push(session);
      known.add(session.id);
      imported += 1;
    }
  });

  chatSessions = remoteSessions;
  if (imported > 0) {
    await persistChatSessionsNow();
  }
  if (localSessions.length > 0) {
    localStorage.removeItem(chatStorageKey);
  }

  if (chatSessions.length === 0) {
    createNewChatSession(true);
  } else {
    activeSessionId = chatSessions[0].id;
    renderChatHistorySidebar();
    renderSessionMessages(activeSessionId);
  }
}

// إنشاء جلسة محادثة جديدة
function createNewChatSession(save = true, customTitle = null) {
  const newSession = {
    id: 'chat_' + Date.now(),
    title: customTitle || 'محادثة تراثية جديدة',
    createdAt: new Date().toISOString(),
    messages: []
  };

  chatSessions.unshift(newSession);
  activeSessionId = newSession.id;

  if (save) saveChatSessions();
  renderChatHistorySidebar();
  renderSessionMessages(activeSessionId);

  const input = document.getElementById('chatInputText');
  if (input) {
    input.value = '';
    input.focus();
  }
  return newSession;
}

// فتح جلسة محادثة جديدة مخصصة، أو استغلال الجلسة الحالية فقط إذا كانت عذراء وفارغة تماماً
function openOrReuseChatSession(customTitle = null) {
  const currentSession = chatSessions.find(s => s.id === activeSessionId);
  const isCompletelyEmpty = currentSession && 
    (!currentSession.messages || currentSession.messages.filter(m => m.role === 'user').length === 0) &&
    (!currentSession.title || currentSession.title === 'محادثة تراثية جديدة' || currentSession.title === 'محادثة جديدة');

  if (isCompletelyEmpty) {
    if (customTitle) {
      currentSession.title = customTitle;
      saveChatSessions();
      renderChatHistorySidebar();
    }
    renderSessionMessages(currentSession.id);
    return currentSession;
  }

  return createNewChatSession(true, customTitle);
}

// بدء محادثة جديدة في الشات مع نص وعنوان مخصص (تمنع تراكم وتداخل النقاشات السابقة)
function startNewChatWithPrompt(promptText, customTitle = null) {
  if (typeof switchMainTab === 'function') {
    switchMainTab('chat');
  }
  const sess = openOrReuseChatSession(customTitle);
  const input = document.getElementById('chatInputText');
  if (input) {
    input.value = promptText;
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 220)}px`;
    input.focus();
    input.scrollTop = input.scrollHeight;
  }
  return sess;
}

// تبديل عمق التفكير
function setThinkingLevel(level) {
  currentThinkingLevel = level;
  
  // تحديث القائمة المنسدلة لعمق التفكير
  const selectEl = document.getElementById('chatThinkingSelect');
  if (selectEl && selectEl.value !== level) {
    selectEl.value = level;
  }

  // التوافق في حال وجود أزرار قديمة
  ['thinkLow', 'thinkMed', 'thinkHigh'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });

  if (level === 'low') document.getElementById('thinkLow')?.classList.add('active');
  if (level === 'medium') document.getElementById('thinkMed')?.classList.add('active');
  if (level === 'high') document.getElementById('thinkHigh')?.classList.add('active');

  const names = {
    low: 'منخفض · سريع · أقل تكلفة',
    medium: 'متوسط · متزن · متوسط التكلفة',
    high: 'عالي · أعمق · أعلى تكلفة',
    max: 'أقصى · أبطأ · التكلفة القصوى',
    none: 'بدون تفكير · بلا تكلفة إضافية'
  };
  showToast(`تم ضبط التفكير على: ${names[level] || level}`);
  if (typeof syncThinkingControls === 'function') syncThinkingControls();
}

const THINKING_EFFORT_LABELS = {
  none: 'بدون تفكير · بلا تكلفة إضافية',
  minimal: 'أدنى · سريع · أقل تكلفة',
  low: 'منخفض · سريع · أقل تكلفة',
  medium: 'متوسط · متزن · متوسط التكلفة',
  high: 'عالي · أعمق · أعلى تكلفة',
  xhigh: 'أقصى · أبطأ · التكلفة القصوى',
  max: 'أقصى · أبطأ · التكلفة القصوى'
};
const THINKING_LADDER = ['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'];

function thinkingEffortLabel(effort) {
  return THINKING_EFFORT_LABELS[effort] || '';
}

function modelReasoningRecord(modelId) {
  if (!modelId || String(modelId).startsWith('local:') || String(modelId).startsWith('local-')) return { local: true };
  const lists = [];
  if (typeof openrouterModelsList !== 'undefined') lists.push(openrouterModelsList);
  if (window.openrouterModelsList) lists.push(window.openrouterModelsList);
  for (const list of lists) {
    const found = (list || []).find(model => model && (model.id === modelId || model.canonical_slug === modelId));
    if (found) return found;
  }
  return null;
}

function resolveThinkingEffort(modelId, level) {
  const record = modelReasoningRecord(modelId);
  if (!record || record.local) return record && record.local ? '' : '';
  const spec = record.reasoning;
  if (!spec) return '';
  let wanted = level === 'max' ? 'max' : (level || 'medium');
  const supported = spec.supported_efforts;
  if (wanted === 'none') {
    if (spec.mandatory) wanted = spec.default_effort && spec.default_effort !== 'none' ? spec.default_effort : 'low';
    else return 'none';
  }
  if (wanted === 'max') {
    const ceiling = ['max', 'xhigh', 'high'].find(item => !supported || supported.includes(item));
    return ceiling || 'high';
  }
  if (!supported) return wanted;
  if (supported.includes(wanted)) return wanted;
  const index = THINKING_LADDER.indexOf(wanted);
  if (index < 0) return supported.includes('medium') ? 'medium' : supported[0];
  for (let step = 1; step < THINKING_LADDER.length; step++) {
    const lower = THINKING_LADDER[index - step];
    const higher = THINKING_LADDER[index + step];
    if (lower && supported.includes(lower) && !(lower === 'none' && spec.mandatory)) return lower;
    if (higher && supported.includes(higher)) return higher;
  }
  return '';
}

function describeThinking(modelId, level) {
  const record = modelReasoningRecord(modelId);
  if (record && record.local) return 'بلا تفكير داخلي';
  if (record && !record.reasoning) return 'بلا تفكير داخلي';
  const effort = resolveThinkingEffort(modelId, level);
  return thinkingEffortLabel(effort) || thinkingEffortLabel(level) || 'متوسط · متزن · متوسط التكلفة';
}

function syncOneThinking(selectId, modelId) {
  const select = document.getElementById(selectId);
  if (!select) return;
  const record = modelReasoningRecord(modelId);
  const unsupported = record && (record.local || record.reasoning === null);
  select.disabled = !!unsupported;
  select.title = unsupported ? 'هذا النموذج بلا تفكير داخلي' : 'جهد التفكير الداخلي وسرعته وتكلفته';
  Array.from(select.options).forEach(option => {
    if (option.value === 'none') {
      option.disabled = false;
      return;
    }
    if (!record || record.local || !record.reasoning || !record.reasoning.supported_efforts) {
      option.disabled = false;
      return;
    }
    const supported = record.reasoning.supported_efforts;
    option.disabled = option.value === 'max'
      ? !supported.some(item => item === 'max' || item === 'xhigh' || item === 'high')
      : !supported.includes(option.value);
  });
  if (select.selectedOptions[0] && select.selectedOptions[0].disabled) {
    const fallback = Array.from(select.options).find(option => !option.disabled);
    if (fallback) select.value = fallback.value;
  }
}

function syncThinkingControls() {
  syncOneThinking('chatThinkingSelect', document.getElementById('chatModelSelect')?.value);
  syncOneThinking('agentThinkingSelect', document.getElementById('agentSelectedModelId')?.value);
  syncOneThinking('pDirectorThinking', document.getElementById('pDirectorModel')?.value);
  syncOneThinking('p2cThinkingSelect', document.getElementById('p2cModelSelect')?.value);
  syncOneThinking('architectThinkingSelect', document.getElementById('architectModelSelect')?.value);
}
window.syncThinkingControls = syncThinkingControls;
window.describeThinking = describeThinking;
window.thinkingEffortLabel = thinkingEffortLabel;

document.addEventListener('change', (event) => {
  const id = event.target && event.target.id;
  if (['pDirectorModel', 'p2cModelSelect', 'pDirectorThinking', 'p2cThinkingSelect', 'agentThinkingSelect', 'architectModelSelect', 'architectThinkingSelect'].includes(id)) {
    syncThinkingControls();
  }
});

// عرض قائمة المحادثات في الشريط الجانبي
function renderChatHistorySidebar() {
  const container = document.getElementById('chatHistoryList');
  const countBadge = document.getElementById('chatSessionsCountBadge');
  if (countBadge) countBadge.textContent = chatSessions.length;

  if (!container) return;

  container.innerHTML = chatSessions.map(sess => {
    const isActive = sess.id === activeSessionId;
    return `
      <div class="history-item ${isActive ? 'active' : ''}" onclick="selectChatSession('${sess.id}')" title="${escapeHtml(sess.title)}">
        <span style="overflow: hidden; text-overflow: ellipsis;">${escapeHtml(sess.title)}</span>
        <span class="history-item-actions">
          <button type="button" class="history-share-btn" data-share-kind="chat" data-share-id="${escapeHtml(sess.id)}" data-share-label="${escapeHtml(sess.title)}" title="مشاركة">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/></svg>
          </button>
          <button onclick="deleteChatSession(event, '${sess.id}')" style="background: transparent; border: none; color: var(--text-light); cursor: pointer; padding: 2px 4px;" title="حذف">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </span>
      </div>
    `;
  }).join('');
}

// اختيار جلسة من الشريط الجانبي
async function revealSharedChat(itemId) {
  switchMainTab('chat');
  try {
    const res = await fetch('/api/chats');
    if (res.ok) {
      const data = await res.json();
      chatSessions = normalizeChatSessions(data.sessions);
    }
  } catch (err) {
    console.error(err);
  }
  if (!chatSessions.some(item => item.id === itemId)) return;
  selectChatSession(itemId);
}

function exportChatSessionFile(sessionId, messageIndex) {
  const session = chatSessions.find(item => item.id === sessionId);
  if (!session) {
    showToast('المحادثة غير موجودة لحفظها', true);
    return false;
  }
  let chat = session;
  if (Number.isInteger(messageIndex) && session.messages[messageIndex]) {
    const message = session.messages[messageIndex];
    chat = {
      id: session.id,
      title: chatMessagePaperTitle(message, session),
      createdAt: new Date().toISOString(),
      messages: [message],
      shared_answer: true
    };
  }
  const payload = {
    export_version: '1.0',
    exported_at: new Date().toISOString(),
    type: 'almojtahed_chat',
    chat: chat
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const link = document.createElement('a');
  const safeId = String(session.id || 'chat').replace(/[^a-zA-Z0-9_-]/g, '_');
  link.href = URL.createObjectURL(blob);
  link.download = `${chat.shared_answer ? 'answer' : 'chat'}_${safeId}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 120000);
  showToast(chat.shared_answer ? 'تم حفظ الإجابة في جهازك' : 'تم حفظ المحادثة في جهازك');
  return true;
}

function importedChatSessions(data) {
  if (!data || typeof data !== 'object') return [];
  if (data.type === 'almojtahed_chat' && data.chat) return [data.chat];
  if (Array.isArray(data.sessions)) return data.sessions;
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.messages)) return [data];
  return [];
}

function importChatSessionFile(input) {
  const file = input && input.files && input.files[0];
  if (input) input.value = '';
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    let data;
    try {
      data = JSON.parse(String(reader.result || ''));
    } catch (err) {
      showToast('الملف ليس محادثة صالحة');
      return;
    }
    const found = importedChatSessions(data).map(session => {
      const messages = Array.isArray(session.messages)
        ? session.messages.filter(message => message && (message.role === 'user' || message.role === 'assistant') && typeof message.content === 'string')
        : [];
      return {
        title: String(session.title || '').trim(),
        createdAt: session.createdAt || new Date().toISOString(),
        messages
      };
    }).filter(session => session.messages.length);
    if (!found.length) {
      showToast('لم يُعثر على محادثة في الملف');
      return;
    }
    found.forEach(session => {
      const imported = {
        id: 'chat_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
        title: session.title || 'محادثة مستوردة',
        createdAt: session.createdAt,
        messages: session.messages
      };
      chatSessions.unshift(imported);
      activeSessionId = imported.id;
    });
    saveChatSessions();
    renderChatHistorySidebar();
    renderSessionMessages(activeSessionId);
    if (typeof switchMainTab === 'function') switchMainTab('chat');
    showToast(found.length > 1 ? `تم استيراد ${found.length} محادثات` : 'تم استيراد المحادثة');
  };
  reader.readAsText(file);
}

function shareActiveChat() {
  const session = chatSessions.find(item => item.id === activeSessionId);
  if (!session) {
    showToast('اختر محادثة أولاً');
    return;
  }
  openSharePicker('chat', session.id, session.title || 'المحادثة');
}

function selectChatSession(id) {
  activeSessionId = id;
  renderChatHistorySidebar();
  renderSessionMessages(id);
}

// حذف جلسة محادثة
async function deleteChatSession(e, id) {
  if (e) e.stopPropagation();
  const session = chatSessions.find(s => s.id === id);
  const title = session ? session.title : 'هذه الجلسة';

  const confirmed = await showConfirmDialog({
    title: 'حذف جلسة المحادثة',
    message: `هل تود حذف محادثة «${title}» نهائياً؟`,
    confirmText: 'نعم، احذف',
    cancelText: 'إلغاء',
    danger: true,
    icon: 'trash-2'
  });
  if (!confirmed) return;

  chatSessions = chatSessions.filter(s => s.id !== id);
  if (chatSessions.length === 0) {
    createNewChatSession();
  } else {
    if (activeSessionId === id) {
      activeSessionId = chatSessions[0].id;
    }
    saveChatSessions();
    renderChatHistorySidebar();
    renderSessionMessages(activeSessionId);
  }
}

function persistChatSessionsNow() {
  return fetch('/api/chats', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessions: chatSessions })
  }).then(res => {
    if (!res.ok) throw new Error('تعذر حفظ المحادثات');
  }).catch(err => {
    console.error('Failed to save chats:', err);
  });
}

function saveChatSessions() {
  clearTimeout(chatSaveTimer);
  chatSaveTimer = setTimeout(persistChatSessionsNow, 250);
}

window.addEventListener('pagehide', () => {
  if (chatSaveTimer) {
    clearTimeout(chatSaveTimer);
    chatSaveTimer = null;
    try {
      fetch('/api/chats', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessions: chatSessions }),
        keepalive: true
      });
    } catch (e) {}
  }
});

function arabicDuration(ms) {
  const digits = '٠١٢٣٤٥٦٧٨٩';
  const toArabic = (value) => String(value).replace(/\d/g, (digit) => digits[digit]);
  const total = Math.max(1, Math.round((ms || 0) / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  if (minutes > 0) return `${toArabic(minutes)} د ${toArabic(seconds)} ث`;
  return `${toArabic(seconds)} ث`;
}

function startChatAnswerClock(bubble) {
  const started = Date.now();
  let stopped = false;
  const slot = document.createElement('div');
  slot.className = 'chat-answer-clock';
  slot.textContent = arabicDuration(0);
  const host = bubble && bubble.querySelector('.message-content');
  if (host) host.appendChild(slot);
  const timer = setInterval(() => {
    slot.textContent = arabicDuration(Date.now() - started);
  }, 1000);
  return () => {
    if (stopped) return Date.now() - started;
    stopped = true;
    clearInterval(timer);
    return Date.now() - started;
  };
}

function chatMessagePaperTitle(msg, session) {
  const heading = String(msg && msg.content || '').match(/^#{1,3}\s+([^\n]+)/);
  const made = heading && heading[1].replace(/[*_`]/g, '').trim();
  if (msg && msg.selection_research) return made || 'تعليق وشرح مختصر';
  return (session && session.title) || 'دراسة وتحقيق بحثي - منظومة المجتهد';
}

function scrollChatMessageTop(idx) {
  const message = document.getElementById(`chatMsg${idx}`);
  const scroller = document.getElementById('chatMessagesContainer');
  if (!message || !scroller) return;
  scroller.scrollTo({ top: message.offsetTop, behavior: 'smooth' });
}

// =============================================================================
// 🧵 خط زمني لإجابات الشات على يمين منطقة الرسائل: خط طولي عليه نقطة
// عند رأس كل إجابة، وبجوار كل نقطة مستطيل صغير وسطه اسم مرحلة الإجابة
// (أول إجابة: مسودة، إجابات جلسة المناقشة: مناقشة ١، ٢...، وإقفال
// المناقشة واعتماد البحث: نسخة نهائية)، والضغط عليها يقفز إلى رأسها.
// المرحلة مختومة على الرسالة عند توليدها (stage)، وللجلسات القديمة
// تُستنتج: الجواب التالي لرسالة الإقفال 🔒 نسخة نهائية حتمًا.
// =============================================================================
function chatAnswerStages(session) {
  const out = [];
  if (!session || !Array.isArray(session.messages)) return out;
  const num = (n) => (typeof toArabicDigits === 'function' ? toArabicDigits(n) : String(n));
  let mainCount = 0;
  let discCount = 0;
  let briefCount = 0;
  let prevFinalize = false;
  session.messages.forEach((msg, idx) => {
    if (!msg) return;
    if (msg.role === 'user') {
      if (String(msg.content || '').startsWith('🔒 أقفل جلسة المناقشة')) prevFinalize = true;
      return;
    }
    if (msg.role !== 'assistant') return;
    if (idx === 0 && typeof isStoredOpening === 'function' && isStoredOpening(msg)) return;
    const text = String(msg.content || '');
    if (!text.trim() || text.startsWith('⚠️ تعذر')) { prevFinalize = false; return; }
    if (msg.stage === 'final' || prevFinalize) {
      out.push({ idx, kind: 'final', label: 'نسخة نهائية' });
    } else if (msg.stage === 'discussion') {
      discCount += 1;
      out.push({ idx, kind: 'discussion', label: `مناقشة ${num(discCount)}` });
    } else if (msg.selection_research) {
      briefCount += 1;
      out.push({ idx, kind: 'brief', label: `تعليق مختصر ${num(briefCount)}` });
    } else {
      mainCount += 1;
      out.push({ idx, kind: mainCount === 1 ? 'draft' : 'answer', label: mainCount === 1 ? 'مسودة' : `إجابة ${num(mainCount)}` });
    }
    prevFinalize = false;
  });
  return out;
}

function scrollToChatAnswer(idx) {
  const scroller = document.getElementById('chatMessagesContainer');
  const msg = document.getElementById(`chatMsg${idx}`);
  if (!scroller || !msg) return;
  scroller.scrollTo({ top: Math.max(0, msg.offsetTop - scroller.offsetTop - 8), behavior: 'smooth' });
  msg.classList.remove('chat-timeline-flash');
  void msg.offsetWidth;
  msg.classList.add('chat-timeline-flash');
  setTimeout(() => msg.classList.remove('chat-timeline-flash'), 1700);
}

let _chatTlRaf = 0;
function scheduleChatTimeline() {
  if (_chatTlRaf) return;
  _chatTlRaf = requestAnimationFrame(() => { _chatTlRaf = 0; positionChatTimeline(); });
}

function buildChatTimeline(sessionArg) {
  const container = document.getElementById('chatMessagesContainer');
  const main = container && container.closest('.chat-main');
  if (!container || !main) return;
  let rail = document.getElementById('chatTimeline');
  if (!rail) {
    rail = document.createElement('div');
    rail.id = 'chatTimeline';
    rail.className = 'chat-timeline';
    rail.innerHTML = '<div class="chat-timeline-hotzone" title="مراحل الإجابات"></div>'
      + '<div class="chat-timeline-hint"></div>'
      + '<div class="chat-timeline-panel"><div class="chat-timeline-line"></div></div>';
    main.appendChild(rail);
    container.addEventListener('scroll', scheduleChatTimeline, { passive: true });
    window.addEventListener('resize', scheduleChatTimeline);
    // منطقة التمرير اليمنى لا تحجب عجلة الفأرة عن الرسائل، ولمسها
    // ينقر فيفتح اللوحة (للأجهزة اللمسية بلا تمرير فأرة)
    const hot = rail.querySelector('.chat-timeline-hotzone');
    hot.addEventListener('wheel', (e) => { container.scrollTop += e.deltaY; }, { passive: true });
    hot.addEventListener('click', () => rail.classList.toggle('is-open'));
  }
  const panel = rail.querySelector('.chat-timeline-panel');
  const session = sessionArg
    || ((typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null);
  const stages = chatAnswerStages(session);
  // تلميح خافت دائم: نقاط صغيرة بألوان المراحل تنبّه لوجود اللوحة
  const hint = rail.querySelector('.chat-timeline-hint');
  if (hint) {
    hint.innerHTML = '';
    stages.forEach((st) => {
      const i = document.createElement('i');
      i.className = `is-${st.kind}`;
      hint.appendChild(i);
    });
  }
  rail.querySelectorAll('.chat-timeline-item').forEach((n) => n.remove());
  if (!stages.length) { rail.style.display = 'none'; return; }
  rail.style.display = '';
  stages.forEach((st) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `chat-timeline-item is-${st.kind}`;
    btn.dataset.msgIdx = String(st.idx);
    btn.title = `الانتقال إلى رأس الإجابة: ${st.label}`;
    const dot = document.createElement('span');
    dot.className = 'chat-timeline-dot';
    const chip = document.createElement('span');
    chip.className = 'chat-timeline-chip';
    chip.textContent = st.label;
    btn.appendChild(dot);
    btn.appendChild(chip);
    btn.addEventListener('click', () => scrollToChatAnswer(st.idx));
    (panel || rail).appendChild(btn);
  });
  rail.dataset.activeIdx = '';
  positionChatTimeline();
}

function positionChatTimeline() {
  const container = document.getElementById('chatMessagesContainer');
  const rail = document.getElementById('chatTimeline');
  if (!container || !rail || rail.style.display === 'none') return;
  // اللوحة عائمة متمركزة عموديًا في منتصف منطقة الرسائل دائمًا
  rail.style.top = `${container.offsetTop}px`;
  rail.style.height = `${container.clientHeight}px`;
  const cRect = container.getBoundingClientRect();
  let activeItem = null;
  rail.querySelectorAll('.chat-timeline-item').forEach((item) => {
    const msg = document.getElementById(`chatMsg${item.dataset.msgIdx}`);
    if (!msg) { item.style.display = 'none'; return; }
    item.style.display = '';
    if (msg.getBoundingClientRect().top - cRect.top <= 110) activeItem = item;
  });
  rail.querySelectorAll('.chat-timeline-item').forEach((item) => {
    item.classList.toggle('is-active', item === activeItem);
  });
  // عند كثرة المراحل تمرّر اللوحة داخليًا حتى يبقى الفعّال في وسطها
  const activeKey = activeItem ? activeItem.dataset.msgIdx : '';
  if (activeItem && rail.dataset.activeIdx !== activeKey) {
    rail.dataset.activeIdx = activeKey;
    const panel = rail.querySelector('.chat-timeline-panel');
    if (panel && panel.scrollHeight > panel.clientHeight) {
      const target = activeItem.offsetTop - panel.clientHeight / 2 + activeItem.clientHeight / 2;
      panel.scrollTop = Math.max(0, target);
    }
  }
}

function deleteChatMessage(idx) {
  const session = chatSessions.find(item => item.id === activeSessionId);
  if (!session || !session.messages[idx]) return;
  let overlay = document.getElementById('chatDeleteOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'chatDeleteOverlay';
    overlay.className = 'chat-delete-overlay';
    overlay.hidden = true;
    overlay.innerHTML = `
      <div class="chat-delete-panel" role="dialog" aria-modal="true" aria-labelledby="chatDeleteTitle">
        <div class="chat-delete-icon" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>
        </div>
        <h3 id="chatDeleteTitle">حذف الإجابة</h3>
        <p>هل تريد حذف هذه الإجابة؟ لن تبقى في المحادثة بعد التأكيد.</p>
        <div class="chat-delete-actions">
          <button type="button" class="chat-delete-cancel" id="chatDeleteCancel">إلغاء</button>
          <button type="button" class="chat-delete-confirm" id="chatDeleteConfirm">حذف</button>
        </div>
      </div>
    `;
    overlay.addEventListener('click', (event) => {
      if (event.target.id === 'chatDeleteOverlay' || event.target.id === 'chatDeleteCancel') {
        overlay.hidden = true;
        return;
      }
      if (event.target.id !== 'chatDeleteConfirm') return;
      const target = Number(overlay.dataset.idx);
      overlay.hidden = true;
      const current = chatSessions.find(item => item.id === activeSessionId);
      if (!current || !current.messages[target]) return;
      current.messages.splice(target, 1);
      saveChatSessions();
      renderSessionMessages(activeSessionId, { keepPosition: true });
    });
    document.body.appendChild(overlay);
  }
  overlay.dataset.idx = String(idx);
  overlay.hidden = false;
}

function shareChatMessage(idx) {
  const session = chatSessions.find(item => item.id === activeSessionId);
  if (!session || !session.messages[idx]) return;
  if (typeof openSharePicker !== 'function') return;
  openSharePicker('chat', session.id, chatMessagePaperTitle(session.messages[idx], session), { messageIndex: idx });
}

function toggleChatMessageTashkeel(idx) {
  const session = chatSessions.find(item => item.id === activeSessionId);
  const msg = session && session.messages[idx];
  if (!msg) return;
  const marks = /[\u064B-\u065F\u0670\u06D6-\u06ED]/;
  if (msg.tashkeel_hidden && msg.vocalized_content) {
    msg.content = msg.vocalized_content;
    msg.tashkeel_hidden = false;
  } else {
    if (!marks.test(msg.content || '')) {
      if (typeof showToast === 'function') showToast('لا تشكيل في هذه الإجابة');
      return;
    }
    msg.vocalized_content = msg.content;
    msg.content = msg.content.replace(/[\u064B-\u065F\u0670\u06D6-\u06ED]/g, '');
    msg.tashkeel_hidden = true;
  }
  saveChatSessions();
  renderSessionMessages(activeSessionId, { keepPosition: true });
}

window.scrollChatMessageTop = scrollChatMessageTop;
window.deleteChatMessage = deleteChatMessage;
window.shareChatMessage = shareChatMessage;

const CHAT_REWRITE_LANGUAGES = [
  ['الإنجليزية', 'english'],
  ['الفرنسية', 'french'],
  ['الألمانية', 'german'],
  ['الإسبانية', 'spanish'],
  ['الإيطالية', 'italian'],
  ['البرتغالية', 'portuguese'],
  ['الروسية', 'russian'],
  ['التركية', 'turkish'],
  ['الفارسية', 'persian'],
  ['الأردية', 'urdu'],
  ['الهندية', 'hindi'],
  ['البنغالية', 'bengali'],
  ['الصينية', 'chinese'],
  ['اليابانية', 'japanese'],
  ['الكورية', 'korean'],
  ['الإندونيسية', 'indonesian'],
  ['الملايو', 'malay'],
  ['الهولندية', 'dutch'],
  ['السويدية', 'swedish'],
  ['النرويجية', 'norwegian'],
  ['الدنماركية', 'danish'],
  ['الفنلندية', 'finnish'],
  ['البولندية', 'polish'],
  ['التشيكية', 'czech'],
  ['المجرية', 'hungarian'],
  ['الرومانية', 'romanian'],
  ['اليونانية', 'greek'],
  ['اللاتينية', 'latin'],
  ['العبرية', 'hebrew'],
  ['الكردية', 'kurdish'],
  ['الأذربيجانية', 'azerbaijani'],
  ['الأوزبكية', 'uzbek'],
  ['البشتوية', 'pashto'],
  ['السواحيلية', 'swahili'],
  ['الهوسا', 'hausa'],
  ['الأمازيغية', 'tamazight'],
  ['التاميلية', 'tamil'],
  ['التايلندية', 'thai'],
  ['الفيتنامية', 'vietnamese'],
  ['الأوكرانية', 'ukrainian'],
  ['الصربية', 'serbian'],
  ['البوسنية', 'bosnian'],
  ['الألبانية', 'albanian']
];

let chatRewriteBusy = false;

function chatAnswerSourceText(msg) {
  if (!msg) return '';
  if (msg.tashkeel_hidden && msg.vocalized_content) return msg.vocalized_content;
  return msg.content || '';
}

async function rewriteChatAnswer(idx, mode, language) {
  if (chatRewriteBusy) {
    showToast('جارٍ معالجة إجابة حالياً');
    return;
  }
  const session = chatSessions.find(item => item.id === activeSessionId);
  const msg = session && session.messages[idx];
  if (!msg || msg.role === 'user') return;
  const source = chatAnswerSourceText(msg).trim();
  if (!source) {
    showToast('لا يوجد نص لاختصاره');
    return;
  }
  let keys = {};
  try { keys = readProviderKeys(); } catch (e) {}
  chatRewriteBusy = true;
  msg.rewriting = mode === 'translate' ? 'الترجمة' : 'الاختصار';
  renderSessionMessages(activeSessionId, { keepPosition: true });
  try {
    const res = await fetch('/api/chat/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: source,
        mode,
        language: language || '',
        api_key: keys.openrouter || ''
      })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'تعذر الاختصار');
    msg.content = data.content;
    msg.vocalized_content = '';
    msg.tashkeel_hidden = false;
    if (data.model) msg.model = data.model;
    delete msg.rewriting;
    saveChatSessions();
    showToast(mode === 'translate' ? 'تمت الترجمة' : 'تم الاختصار');
  } catch (err) {
    showToast(err.message || 'تعذر الاختصار');
  } finally {
    chatRewriteBusy = false;
    delete msg.rewriting;
    renderSessionMessages(activeSessionId, { keepPosition: true });
  }
}

function abbreviateChatMessage(idx) {
  rewriteChatAnswer(idx, 'abbreviate', '');
}

function fillChatTranslateLanguages(query) {
  const select = document.getElementById('chatTranslateLanguage');
  if (!select) return;
  const q = String(query || '').trim().toLowerCase();
  const current = select.value;
  const rows = CHAT_REWRITE_LANGUAGES.filter(([ar, en]) => !q || ar.includes(q) || en.includes(q));
  select.innerHTML = rows.map(([ar]) => `<option value="${ar}">${ar}</option>`).join('');
  if (rows.some(([ar]) => ar === current)) select.value = current;
  else if (rows.length) select.selectedIndex = 0;
}

function openChatTranslatePicker(idx) {
  const session = chatSessions.find(item => item.id === activeSessionId);
  if (!session || !session.messages[idx] || session.messages[idx].role === 'user') return;
  let overlay = document.getElementById('chatTranslateOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'chatTranslateOverlay';
    overlay.className = 'chat-delete-overlay';
    overlay.hidden = true;
    overlay.innerHTML = `
      <div class="chat-delete-panel chat-translate-panel" role="dialog" aria-modal="true" aria-labelledby="chatTranslateTitle">
        <h3 id="chatTranslateTitle">ترجمة الإجابة</h3>
        <p>يُختصر النص ثم يُترجم إلى اللغة التي تختارها، من النص ومراجعه فقط.</p>
        <label class="chat-translate-label" for="chatTranslateFilter">تصفية اللغات</label>
        <input id="chatTranslateFilter" class="chat-translate-filter" type="text" placeholder="اكتب اسم اللغة" autocomplete="off">
        <label class="chat-translate-label" for="chatTranslateLanguage">اللغة</label>
        <select id="chatTranslateLanguage" class="chat-translate-select"></select>
        <div class="chat-delete-actions">
          <button type="button" class="chat-delete-cancel" id="chatTranslateCancel">إلغاء</button>
          <button type="button" class="chat-translate-confirm" id="chatTranslateConfirm">ترجمة</button>
        </div>
      </div>`;
    overlay.addEventListener('click', (event) => {
      if (event.target.id === 'chatTranslateOverlay' || event.target.id === 'chatTranslateCancel') {
        overlay.hidden = true;
      }
    });
    overlay.querySelector('#chatTranslateFilter').addEventListener('input', (event) => {
      fillChatTranslateLanguages(event.target.value);
    });
    overlay.querySelector('#chatTranslateConfirm').addEventListener('click', () => {
      const target = Number(overlay.dataset.idx);
      const language = overlay.querySelector('#chatTranslateLanguage').value;
      overlay.hidden = true;
      if (!language) {
        showToast('اختر لغة الترجمة');
        return;
      }
      rewriteChatAnswer(target, 'translate', language);
    });
    document.body.appendChild(overlay);
  }
  overlay.dataset.idx = String(idx);
  const filter = overlay.querySelector('#chatTranslateFilter');
  if (filter) filter.value = '';
  fillChatTranslateLanguages('');
  const select = overlay.querySelector('#chatTranslateLanguage');
  if (select && select.options.length) select.value = 'الإنجليزية';
  overlay.hidden = false;
  if (filter) filter.focus();
}

window.abbreviateChatMessage = abbreviateChatMessage;
window.openChatTranslatePicker = openChatTranslatePicker;
window.toggleChatMessageTashkeel = toggleChatMessageTashkeel;

// عرض رسائل الجلسة الحالية
function chatSourceBibliography(row, places) {
  const bits = [];
  if (row.title) bits.push(row.title);
  if (row.author) bits.push(row.death_year ? `${row.author} (ت: ${row.death_year} هـ)` : row.author);
  if (row.editor) bits.push(`المحقق: ${row.editor}`);
  if (row.edition) bits.push(`الطبعة: ${row.edition}`);
  if (row.publisher) bits.push(`الناشر: ${row.publisher}`);
  if (row.city) bits.push(`مدينة النشر: ${row.city}`);
  if (row.print_year) bits.push(`سنة الطبع: ${row.print_year}`);
  if (places && places.length) bits.push(places.join('؛ '));
  return bits.join('، ');
}

/* مفتاح الفرز الأبجدي العربي لعناوين المراجع: بلا تشكيل، وبتوحيد
   الهمزات والألف المقصورة والتاء المربوطة، وبتجاهل «ال» التعريف */
function biblioTitleSortKey(title) {
  return String(title || '').trim()
    .replace(/[ً-ٰٟ]/g, '')
    .replace(/[أإآ]/g, 'ا')
    .replace(/ى/g, 'ي')
    .replace(/ة/g, 'ه')
    .replace(/^[^ء-يA-Za-z0-9]+/, '')
    .replace(/^ال/, '')
    .trim();
}
function compareBiblioTitles(a, b) {
  return biblioTitleSortKey(a).localeCompare(biblioTitleSortKey(b), 'ar')
    || String(a || '').localeCompare(String(b || ''), 'ar');
}

function chatWitnessesHtml(msg, idx) {
  const rows = Array.isArray(msg.witnesses) ? msg.witnesses : [];
  if (!rows.length || msg.role === 'user') return '';
  // «تعليق وشرح مختصر»: لا قائمة مراجع تحت النتيجة — أرقام وبطاقة شاهد فقط
  if (msg.selection_research) return '';
  const groups = [];
  const index = new Map();
  rows.forEach((row, n) => {
    const key = String(row.book_id || row.rel_path || row.title || n);
    if (!index.has(key)) {
      index.set(key, groups.length);
      groups.push({ row, n, places: [] });
    }
    const place = [row.part ? `جـ ${row.part}` : '', row.page ? `ص ${row.page}` : ''].filter(Boolean).join(' ');
    const group = groups[index.get(key)];
    if (place && !group.places.includes(place)) group.places.push(place);
  });
  // ترتيب القائمة على الحروف الأبجدية بعناوين الكتب
  groups.sort((a, b) => compareBiblioTitles(a.row.title || a.row.author, b.row.title || b.row.author));
  const items = groups.map(({ row, n, places }) => `
      <li class="chat-source-item">
        <div class="chat-source-row">
          <span class="chat-source-text">${escapeHtml(chatSourceBibliography(row, places))}</span>
        </div>
      </li>`).join('');
  return `
    <section class="chat-source-list">
      <h3 class="chat-source-heading">قائمة المصادر والمراجع</h3>
      <ol>${items}</ol>
    </section>`;
}

function openChatWitness(msgIdx, rowIdx) {
  const session = chatSessions.find(s => s.id === activeSessionId);
  const row = session && session.messages[msgIdx] && session.messages[msgIdx].witnesses
    ? session.messages[msgIdx].witnesses[rowIdx]
    : null;
  if (!row || typeof openBookReader !== 'function') return;
  openBookReader({
    rel_path: row.rel_path || '',
    book_id: row.book_id || '',
    book_title: row.title || '',
    part: row.part || '',
    page_num: parseInt(row.page, 10) || null,
    highlight: row.text || ''
  });
}

function verifyChatWitness(msgIdx, rowIdx) {
  const session = chatSessions.find(s => s.id === activeSessionId);
  const row = session && session.messages[msgIdx] && session.messages[msgIdx].witnesses
    ? session.messages[msgIdx].witnesses[rowIdx]
    : null;
  if (!row || typeof openMcpLiteralVerify !== 'function') return;
  openMcpLiteralVerify({
    book: row.book_id ? `#${row.book_id}` : (row.title || ''),
    rel_path: row.rel_path || '',
    part: row.part || '',
    page: row.page || '',
    quote: row.text || ''
  });
}
window.verifyChatWitness = verifyChatWitness;

function citationNameWords(value) {
  return String(value || '')
    .replace(/[\u064B-\u065F\u0670\u0640]/g, '')
    .replace(/[أإآ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه')
    .split(/[^\u0600-\u06FF]+/)
    .filter(word => word.length >= 4 && !['ينظر', 'انظر', 'راجع', 'كتاب', 'المصدر', 'المرجع'].includes(word));
}

function attachStoredWitnesses(container) {
  const session = chatSessions.find(s => s.id === activeSessionId);
  if (!session || !container) return;
  const western = (value) => String(value || '')
    .replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))
    .replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
  const bindButton = (button, rows) => {
    // ختم خادمي موثّق (وسم cit-src قبل الزر يحمل رقم كتابه وموضعه):
    // مرجع التصفح هو الخادم وبوابة توثيقه لا قائمة الشواهد المستخرجة،
    // فلا يُحذف زرّه لغيابه عنها — بهذا الحذف كانت تُصمَت أختام الإغناءة
    // من الكتالوج (أغلب حواشي البحوث) وتبقى الحاشية بلا أيقونة تحقق.
    const prevSpan = button.previousElementSibling;
    if (prevSpan && (prevSpan.classList.contains('cit-src') || prevSpan.classList.contains('cit-unresolved'))
        && (prevSpan.getAttribute('data-book-id') || prevSpan.getAttribute('data-rel-path'))) return;
    const page = parseInt(western(button.getAttribute('data-page')), 10);
    const part = western(button.getAttribute('data-part') || '');
    const stampedId = button.getAttribute('data-book-id') || '';
    const stampedRel = button.getAttribute('data-rel-path') || '';
    if (stampedId || stampedRel) {
      // ختم قديم لا يطابق قائمة التوثيق الموثوقة يُلغى ويُعاد ربطه من نص الحاشية نفسه.
      const trusted = rows.some((item) => {
        const sameBook = (stampedId && String(item.book_id || '') === stampedId)
          || (stampedRel && String(item.rel_path || '') === stampedRel);
        if (!sameBook) return false;
        if (page && parseInt(item.page, 10) !== page) return false;
        if (part && item.part && String(parseInt(part, 10) || part) !== String(item.part)) return false;
        return true;
      });
      if (trusted) return;
      button.removeAttribute('data-book-id');
      button.removeAttribute('data-rel-path');
    }
    const stampedSpan = button.previousElementSibling && button.previousElementSibling.classList.contains('cit-src')
      ? button.previousElementSibling.textContent
      : '';
    // ربط يقيني فقط: العنوان كاملاً، أو بدايته المميزة. كلمة واحدة مشتركة
    // مثل «الرسالة» لا تربط، وما لم يُربط يقيناً يُزال زرّه فلا يفتح كتاباً مخمّناً.
    const generic = new Set(['التفسير', 'الحديث', 'الفقه', 'الشرح', 'الكتاب', 'الصحيح', 'السنن', 'التاريخ', 'الرساله', 'رساله', 'طبعه', 'الطبعه', 'ط', 'ت', 'تحقيق']);
    const buttonKey = citationNameWords(stampedSpan || button.getAttribute('data-book')).join(' ');
    const contentWords = buttonKey.split(' ').filter(word => word.length >= 3 && !generic.has(word));
    let best = null;
    let bestScore = 0;
    let tied = false;
    rows.forEach((item) => {
      if (page && parseInt(item.page, 10) !== page) return;
      if (part && item.part && String(parseInt(part, 10) || part) !== String(item.part)) return;
      const rowKey = citationNameWords(item.title).join(' ');
      if (!buttonKey || !rowKey) return;
      let score = 0;
      if (buttonKey === rowKey) score = 1000 + rowKey.length;
      else if (` ${buttonKey} `.includes(` ${rowKey} `)) score = 900 + rowKey.length;
      else if (rowKey.startsWith(buttonKey + ' ') && contentWords.length >= 2) score = 700 + buttonKey.length;
      else if (buttonKey.startsWith(rowKey + ' ')) score = 650 + rowKey.length;
      if (!score) return;
      if (score > bestScore) {
        best = item;
        bestScore = score;
        tied = false;
      } else if (score === bestScore && best && best !== item) {
        tied = true;
      }
    });
    if (tied || !best || !best.rel_path) {
      button.remove();
      return;
    }
    button.setAttribute('data-rel-path', best.rel_path);
    button.setAttribute('data-book-id', best.book_id || '');
    if (best.title) button.setAttribute('data-book', best.title);
    if (best.text && !button.getAttribute('data-quote')) {
      button.setAttribute('data-quote', String(best.text).slice(0, 180));
    }
  };
  container.querySelectorAll('.message-bubble.assistant').forEach((bubble) => {
    const idx = parseInt(String(bubble.id || '').replace('chatMsg', ''), 10);
    const rows = session.messages[idx] && session.messages[idx].witnesses;
    if (!Array.isArray(rows) || !rows.length) return;
    bubble.querySelectorAll('.btn-verify-citation, .btn-mcp-verify').forEach((button) => bindButton(button, rows));
  });
}
window.openChatWitness = openChatWitness;

// بطاقة الشاهد المنبثقة: تمرير الفأرة على رقم الحاشية في المتن يُظهر
// شاهدها المنقول (اسم الكتاب وجزؤه وصفحته وأول نص الصفحة) من ختم
// الحاشية نفسه، مع زر فتح الموضع في الكتاب — تحقق بلا نزول إلى آخر
// البحث ولا فتح للكتاب إلا عند القصد.
function attachFootnoteHover(container) {
  if (!container) return;
  // في نتائج «تعليق وشرح مختصر» قد يأتي رقم الإحالة نصًا عاديًا (١)
  // لا عنصر إحالة: يُغلَّف بعنصر مرتفع ليمرَّر عليه وتنبثق بطاقة
  // شاهده كما في سائر الإجابات
  container.querySelectorAll('.message-bubble.brief-comment .message-content').forEach((content) => {
    if (content.dataset.fnPlainWrapped === '1') return;
    content.dataset.fnPlainWrapped = '1';
    // حذف أي قسم مراجع/حواشٍ ختامي صاغه النموذج بنفسه مهما كانت
    // وسومه: العنوان وكل ما يليه حتى آخر النتيجة
    const refHeads = [];
    content.querySelectorAll('h1, h2, h3, h4, h5, h6, p, strong, b').forEach((h) => {
      const t = (h.textContent || '').trim();
      if (/^(?:📚\s*)?(?:قائمة\s+)?(?:المصادر والمراجع|المصادر|المراجع|الحواشي|ثبت المصادر والمراجع)\s*[:：]?$/.test(t)
        || /^(?:📚\s*)?(?:قائمة\s+)?(?:المصادر والمراجع|المصادر|المراجع|الحواشي)\s*[:：]\s*\S/.test(t)) {
        refHeads.push(h.closest('h1, h2, h3, h4, h5, h6, p') || h);
      }
    });
    refHeads.forEach((head) => {
      let node = head;
      while (node.parentElement && node.parentElement !== content
        && !(node.parentElement.classList && node.parentElement.classList.contains('chat-academic'))) {
        node = node.parentElement;
      }
      if (!node.parentElement) return;
      let n = node;
      while (n) {
        const nx = n.nextSibling;
        // توقف عند شريط أزرار الرسالة أو أي أداة مركّبة فلا يُبتلع
        if (n.nodeType === 1 && (n.classList.contains('applied-tool-mount')
          || n.querySelector('.btn-msg-export, .btn-user-msg-action, .applied-tool-mount'))) break;
        n.remove();
        n = nx;
      }
    });
    // وقائمة ختامية بلا عنوان إن كانت بنودها إحالات كتب صريحة —
    // أما قوائم تعريف الحواشي المختومة فتبقى مخفية لتعمل بطاقتها
    const tail = [...content.querySelectorAll('.chat-academic > ol, .chat-academic > ul, :scope > ol, :scope > ul')]
      .filter((list) => !list.classList.contains('chat-fn-list'));
    tail.forEach((list) => {
      const items = [...list.querySelectorAll(':scope > li')];
      if (items.length < 2) return;
      if (list.querySelector('.cit-src, .cit-unresolved, [id*="fn"]')) return;
      const cites = items.filter((li) => /\(\s*[\d٠-٩]+\s*[-/]\s*[\d٠-٩]+\s*\)|#\d{2,}/.test(li.textContent || '')).length;
      if (cites >= Math.ceil(items.length * 0.7)) list.remove();
    });
    // وكل أشكال تعريفات الحواشي الأخرى تُخفى ولا تُحذف — منها سطور
    // «(ن) انظر: …» العادية في آخر الجواب — فتبقى في البنية مصدرًا
    // لبطاقة الشاهد عند تمرير المؤشر على رقمها في المتن
    content.querySelectorAll('.chat-fn-list, .footnote-list, .footnote-line, .footnotes').forEach((el) => {
      el.style.display = 'none';
      el.dataset.fnHidden = '1';
    });
    content.querySelectorAll('p, li').forEach((el) => {
      if (el.closest('.chat-fn-list, .footnote-list')) return;
      const t = (el.textContent || '').trim();
      if (/^\(\s*[\d٠-٩]+\s*\)/.test(t)
        && /(انظر|ينظر|يُنظر|راجع|#\d|\(\s*[\d٠-٩]+\s*[-/]\s*[\d٠-٩]+\s*\)|ص\s*\(?\s*[\d٠-٩]+)/.test(t)) {
        el.style.display = 'none';
        el.dataset.fnHidden = '1';
      }
    });
    // وفواصل أفقية لم يبقَ بعدها إلا مخفيّ فلا معنى لبقائها ظاهرة
    content.querySelectorAll('hr').forEach((hr) => {
      let n = hr.nextElementSibling;
      let onlyHidden = true;
      while (n) {
        if (n.dataset.fnHidden !== '1' && n.style.display !== 'none') { onlyHidden = false; break; }
        n = n.nextElementSibling;
      }
      if (onlyHidden) hr.style.display = 'none';
    });
    const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => {
        if (!node.nodeValue || !/\(\s*[٠-٩\d]+\s*\)/.test(node.nodeValue)) return NodeFilter.FILTER_REJECT;
        if (node.parentElement.closest('.chat-fn-list, .footnote-list, .footnote-line, a, sup, button')) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    textNodes.forEach((node) => {
      const frag = document.createDocumentFragment();
      node.nodeValue.split(/(\(\s*[٠-٩\d]+\s*\))/g).forEach((part) => {
        if (/^\(\s*[٠-٩\d]+\s*\)$/.test(part)) {
          const sup = document.createElement('sup');
          sup.className = 'fn-plain-ref';
          sup.textContent = part;
          frag.appendChild(sup);
        } else {
          frag.appendChild(document.createTextNode(part));
        }
      });
      node.replaceWith(frag);
    });
  });
  if (container.dataset.fnHoverBound === '1') return;
  container.dataset.fnHoverBound = '1';
  let card = document.getElementById('fnHoverCard');
  if (!card) {
    card = document.createElement('div');
    card.id = 'fnHoverCard';
    card.className = 'fn-hover-card';
    card.hidden = true;
    document.body.appendChild(card);
  }
  const western = (v) => String(v || '')
    .replace(/[٠-٩]/g, (d) => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))
    .replace(/[۰-۹]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/\D/g, '');
  const arabic = (v) => String(v || '').replace(/\d/g, (d) => '٠١٢٣٤٥٦٧٨٩'[+d]);
  let hideTimer = 0;
  let currentMarker = null;

  const hide = () => { card.hidden = true; currentMarker = null; };
  const scheduleHide = () => { clearTimeout(hideTimer); hideTimer = setTimeout(hide, 260); };

  function markerOf(node) {
    const el = node && node.closest ? node.closest('sup, a.chat-fn-ref') : null;
    if (!el || el.classList.contains('chat-fn-back')) return null;
    if (!/^\(\s*[\d٠-٩۰-۹]+\s*\)$/.test((el.textContent || '').trim())) return null;
    // رقم تعريف الحاشية في ذيل البحث ليس علامة متن: أول عنصر في سطر تعريفها
    const host = el.closest('li, p');
    if (host && (host.querySelector('.cit-src') || host.querySelector('.cit-unresolved'))
        && (host.textContent || '').trim().startsWith((el.textContent || '').trim())) return null;
    return el;
  }

  function findDef(bubble, n) {
    const byId = bubble.querySelector(`[id="fn${n}"], [id="paper-fn${n}"]`);
    if (byId) return byId;
    const ar = arabic(n);
    const candidates = bubble.querySelectorAll('.footnote-item, .footnote-line, li, p');
    for (const c of candidates) {
      const t = (c.textContent || '').trim();
      if (t.startsWith(`(${n})`) || t.startsWith(`(${ar})`)) return c;
    }
    return null;
  }

  function showCard(marker) {
    const bubble = marker.closest('.message-bubble') || container;
    const n = western(marker.textContent);
    if (!n) return;
    const def = findDef(bubble, n);
    let html = `<div class="fn-hover-head">حاشية (${arabic(n)}) — الشاهد المنقول</div>`;
    const entries = [];
    if (def) {
      def.querySelectorAll('.cit-src').forEach((span) => {
        if (entries.length >= 3) return;
        entries.push({
          book: span.getAttribute('data-book') || span.textContent || '',
          part: span.getAttribute('data-part') || '',
          page: span.getAttribute('data-page') || '',
          quote: span.getAttribute('data-quote') || '',
          bookId: span.getAttribute('data-book-id') || '',
          rel: span.getAttribute('data-rel-path') || '',
        });
      });
      if (!entries.length) {
        const un = def.querySelector('.cit-unresolved');
        if (un) {
          entries.push({
            book: (un.textContent || '').replace('⚠', '').trim().slice(0, 90),
            part: un.getAttribute('data-part') || '', page: un.getAttribute('data-page') || '',
            quote: '', bookId: un.getAttribute('data-book-id') || '',
            rel: un.getAttribute('data-rel-path') || '', unverified: true,
          });
        }
      }
    }
    if (!entries.length) {
      // بلا تعريف حاشية في النص (كتعليقات «شرح مختصر»): الشاهد برقم
      // إحالته من شواهد الرسالة نفسها بترتيب ورودها
      const idxm = (bubble.id || '').match(/chatMsg(\d+)/);
      const sess = (typeof chatSessions !== 'undefined' && typeof activeSessionId !== 'undefined')
        ? chatSessions.find((s) => s.id === activeSessionId) : null;
      const msgw = (idxm && sess && sess.messages[+idxm[1]]) ? sess.messages[+idxm[1]].witnesses : null;
      const w = Array.isArray(msgw) ? msgw[parseInt(n, 10) - 1] : null;
      if (w) {
        entries.push({
          book: w.title || '', part: w.part || '', page: w.page || '',
          quote: String(w.text || '').slice(0, 320),
          bookId: w.book_id || '', rel: w.rel_path || '',
        });
      }
    }
    if (entries.length) {
      html += entries.map((e) => {
        const loc = [e.part ? `ج ${arabic(e.part)}` : '', e.page ? `ص ${arabic(e.page)}` : ''].filter(Boolean).join('، ');
        return `<div class="fn-hover-entry">
          <div class="fn-hover-book">📖 ${escapeHtml(e.book)}${loc ? ` <span class="fn-hover-loc">(${loc})</span>` : ''}</div>
          ${e.quote ? `<blockquote class="fn-hover-quote">${escapeHtml(e.quote)}…</blockquote>` : ''}
          ${e.unverified ? '<div class="fn-hover-warn">⚠ موضع لم يتحقق منه النظام آليًا — على ذمة النموذج</div>' : ''}
          ${e.bookId ? `<button type="button" class="fn-hover-open" data-book-id="${escapeHtml(e.bookId)}" data-rel-path="${escapeHtml(e.rel)}" data-book="${escapeHtml(e.book)}" data-part="${escapeHtml(e.part)}" data-page="${escapeHtml(e.page)}" data-quote="${escapeHtml(e.quote)}">تصفح الموضع في الكتاب</button>` : ''}
        </div>`;
      }).join('');
    } else if (def) {
      html += `<div class="fn-hover-entry"><div class="fn-hover-quote">${escapeHtml((def.textContent || '').trim().slice(0, 420))}</div></div>`;
    } else {
      html += '<div class="fn-hover-warn">لم يُعثر على نص هذه الحاشية في الجواب</div>';
    }
    card.innerHTML = html;
    card.querySelectorAll('.fn-hover-open').forEach((btn) => {
      btn.addEventListener('click', () => {
        hide();
        if (typeof openBookReader === 'function') {
          openBookReader({
            rel_path: btn.getAttribute('data-rel-path') || '',
            book_id: btn.getAttribute('data-book-id') || '',
            book_title: btn.getAttribute('data-book') || '',
            part: btn.getAttribute('data-part') || '',
            page_num: parseInt(btn.getAttribute('data-page'), 10) || null,
            highlight: btn.getAttribute('data-quote') || '',
          });
        }
      });
    });
    card.hidden = false;
    const rect = marker.getBoundingClientRect();
    const cardW = card.offsetWidth;
    const cardH = card.offsetHeight;
    let left = Math.min(Math.max(8, rect.left + rect.width / 2 - cardW / 2), window.innerWidth - cardW - 8);
    let top = rect.bottom + 8;
    if (top + cardH > window.innerHeight - 6) top = Math.max(6, rect.top - cardH - 8);
    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
  }

  container.addEventListener('mouseover', (e) => {
    const m = markerOf(e.target);
    if (m) {
      clearTimeout(hideTimer);
      if (m !== currentMarker) { currentMarker = m; showCard(m); }
    } else if (!e.target.closest || !e.target.closest('#fnHoverCard')) {
      scheduleHide();
    }
  });
  container.addEventListener('mouseout', (e) => {
    if (markerOf(e.target)) scheduleHide();
  });
  card.addEventListener('mouseenter', () => clearTimeout(hideTimer));
  card.addEventListener('mouseleave', scheduleHide);
  container.addEventListener('scroll', hide, { passive: true });
}

function chatOpeningHtml() {
  return '<div class="chat-opening"><p>مرحبا بك ...</p><p>كيف يمكنني خدمتك؟</p></div>';
}

function sessionIsOpening(session) {
  return !session.messages || !session.messages.some(m => m.role === 'user');
}

function isStoredOpening(msg) {
  if (!msg || msg.role !== 'assistant') return false;
  if (msg.model || msg.tool_html || msg.tool_figure || msg.tool_web) return false;
  const text = String(msg.content || '');
  return text.includes('مرحباً بك في منظومة') || text.startsWith('مرحبا بك ...');
}

function renderSessionMessages(sessionId, options) {
  const session = chatSessions.find(s => s.id === sessionId);
  const container = document.getElementById('chatMessagesContainer');
  if (!session || !container) return;
  if (typeof refreshDiscussionBar === 'function') refreshDiscussionBar();
  const keepPosition = options && options.keepPosition;
  const previousScroll = keepPosition ? container.scrollTop : 0;

  if (sessionIsOpening(session)) {
    const placeholderOnly = !(session.messages || []).some(m => m.role !== 'assistant' || m.model || m.tool_html || m.tool_figure || m.tool_web);
    if (placeholderOnly && session.messages && session.messages.length) {
      session.messages = [];
      saveChatSessions();
    }
    if (placeholderOnly) {
      container.innerHTML = chatOpeningHtml();
      buildChatTimeline(session);
      return;
    }
  }

  let briefTitleCount = 0;
  container.innerHTML = session.messages.map((msg, idx) => {
    if (idx === 0 && isStoredOpening(msg)) return '';
    const isUser = msg.role === 'user';
    const avatar = isUser ? 'أنت' : 'مج';
    const parsedText = formatMarkdown(msg.content, `c${idx}`);
    // عنوان نتيجة «تعليق وشرح مختصر» مرقّمًا بترتيب التعليقات في
    // الجلسة، موافقًا لترقيمه في الخط الزمني (تعليق مختصر ١، ٢، ٣)
    let briefTitleHtml = '';
    if (!isUser && msg.selection_research) {
      briefTitleCount += 1;
      const kind = SELECTION_RESEARCH_KINDS.find((k) => k.id === msg.selection_research);
      const num = (typeof toArabicDigits === 'function') ? toArabicDigits(briefTitleCount) : String(briefTitleCount);
      briefTitleHtml = `<div class="brief-comment-title"><span>${kind ? kind.icon : '✒️'}</span><span>تعليق وشرح مختصر ${num}${kind ? ` — ${escapeHtml(kind.label)}` : ''}</span></div>`;
    }
    
    const modelTag = (!isUser && msg.model) ? `
      <div class="message-model-tag" title="النموذج الذي قام بالتحليل والإجابة">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
        <span>النموذج: ${escapeHtml(cleanModelDisplayName(msg.model))}${msg.thinking_label ? ` · ${escapeHtml(msg.thinking_label)}` : ''}</span>
      </div>
    ` : '';

    const agentGroupTag = (!isUser && msg.agent_group) ? `
      <div class="message-agent-group-tag" title="تم توجيه الاستفسار واستخراج البيانات عبر هذه المجموعة">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        <span>المجموعة: ${escapeHtml(msg.agent_group)}</span>
      </div>
    ` : '';

    const durationTag = (!isUser && msg.duration_ms) ? `
      <div class="message-model-tag chat-answer-clock" title="زمن الإجابة">
        <span>زمن الإجابة: ${arabicDuration(msg.duration_ms)}</span>
      </div>
    ` : '';

    const tagsHtml = (modelTag || agentGroupTag || durationTag) ? `
      <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px;">
        ${modelTag}
        ${agentGroupTag}
        ${durationTag}
      </div>
    ` : '';

    const actionsBar = !isUser ? `
      <div class="chat-msg-actions-bar" style="display: flex; gap: 8px; margin-top: 10px; border-top: 1px dashed var(--border-subtle); padding-top: 8px; flex-wrap: wrap;">
        ${msg.rewriting ? `<span class="chat-rewrite-status">جارٍ ${escapeHtml(msg.rewriting)}...</span>` : ''}
        <button type="button" class="btn-msg-export" onclick="exportChatMessageHtml(${idx})" title="قراءة هذه النتيجة في صفحة قراءة">
          📄 قراءة
        </button>
        <button type="button" class="btn-msg-export" onclick="exportChatMessagePdf(${idx})" title="طباعة هذه النتيجة بحواشٍ لكل صفحة أو حفظها PDF">
          🖨️ طباعة
        </button>
        <button type="button" class="btn-msg-export" onclick="copyChatMessageText(${idx})" title="نسخ نص الإجابة كاملاً">
          📋 نسخ
        </button>
        <button type="button" class="btn-msg-export" onclick="shareChatMessage(${idx})" title="مشاركة هذه الإجابة">
          مشاركة
        </button>
        <button type="button" class="btn-msg-export" onclick="scrollChatMessageTop(${idx})" title="الانتقال إلى أعلى هذه الإجابة">
          أعلى الإجابة
        </button>
        <button type="button" class="btn-msg-export" onclick="toggleChatMessageTashkeel(${idx})" title="إزالة التشكيل أو إعادته">
          ${msg.tashkeel_hidden ? 'إعادة التشكيل' : 'إزالة التشكيل'}
        </button>
        <button type="button" class="btn-msg-export" onclick="abbreviateChatMessage(${idx})" title="اختصار هذه الإجابة بنموذج Gemini 3.8 Flash" ${msg.rewriting ? 'disabled' : ''}>
          اختصار
        </button>
        <button type="button" class="btn-msg-export" onclick="openChatTranslatePicker(${idx})" title="ترجمة هذه الإجابة بعد اختصارها" ${msg.rewriting ? 'disabled' : ''}>
          ترجمة
        </button>
        <button type="button" class="btn-msg-export" onclick="openDiscussion(${idx})" title="فتح جلسة مناقشة مع مدير المشروع حول هذا البحث: حوار واستكمال للنواقص بلا بحث جديد، وله أن يطلب وكيلًا بعينه للتحقق، ثم يقفل الجلسة ويعيد الصياغة النهائية">
          🗣️ مناقشة المدير
        </button>
        <button type="button" class="btn-msg-export" onclick="openAnswerSearch(${idx})" title="بحث مفلتر داخل نص هذه الإجابة نفسها: عدّادات وتظليل تلقائي للمواضع وتنقل بينها">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -2px;"><circle cx="7" cy="15" r="4"/><circle cx="17" cy="15" r="4"/><path d="M7 11V5h3v6M17 11V5h-3v6M11 8h2"/></svg>
          بحث في الإجابة
        </button>
        <button type="button" class="btn-msg-export" onclick="downloadChatResearchReport(${idx})" title="تقرير هذا البحث كاملًا في ملف منفصل: مؤشراته وملحوظاته وبدائله وسجل تدقيقه الآلي">
          📏 تقرير البحث
        </button>
        <button type="button" class="btn-msg-export btn-msg-delete" onclick="deleteChatMessage(${idx})" title="حذف هذه الإجابة" aria-label="حذف هذه الإجابة">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>
        </button>
      </div>
    ` : `
      <div class="chat-user-msg-actions-bar" style="display: flex; gap: 8px; margin-top: 8px; padding-top: 6px; border-top: 1px dashed rgba(204, 120, 92, 0.25); justify-content: flex-start; flex-wrap: wrap;">
        <button type="button" class="btn-user-msg-action" onclick="regenerateAnswerForUserMessage(${idx})" title="مسح الإجابة الحالية ثم توليد إجابة جديدة">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
          <span>مسح وإعادة توليد</span>
        </button>
        <button type="button" class="btn-user-msg-action" onclick="regenerateAnswerKeepingCurrent(${idx})" title="توليد إجابة إضافية مع الإبقاء على الإجابة الحالية">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
          <span>إعادة توليد</span>
        </button>
        <button type="button" class="btn-user-msg-action" onclick="copyUserMessageText(${idx})" title="نسخ نص السؤال">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          <span>نسخ السؤال</span>
        </button>
      </div>
    `;

    return `
      <div class="message-bubble ${isUser ? 'user' : 'assistant'}${msg.selection_research ? ' brief-comment' : ''}" id="chatMsg${idx}">
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
          ${(!isUser && msg.regenerated) ? `
            <div class="chat-regenerated-badge" title="إجابة أُعيد توليدها مع الإبقاء على الإجابة السابقة">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
              <span>إجابة معاد توليدها</span>
            </div>
          ` : ''}
          ${briefTitleHtml}
          ${parsedText}
          ${msg.tool_figure ? `<div class="applied-tool-mount" data-tool-figure="1" data-tool-index="${idx}" style="min-height:780px;"></div>` : ''}
          ${msg.tool_html && !msg.tool_figure ? `<div class="applied-tool-mount" data-tool-html="1" data-tool-index="${idx}"></div>` : ''}
          ${msg.tool_web ? `<div class="applied-tool-mount" data-tool-web="1" data-tool-index="${idx}"></div>` : ''}
          ${chatWitnessesHtml(msg, idx)}
          ${tagsHtml}
          ${actionsBar}
        </div>
      </div>
    `;
  }).join('');

  // تشغيل الأدوات التفاعلية الحية (شجرة الأسانيد وخرائط Markmap) في رسائل الشات
  if (typeof autoRenderChatInteractiveWidgets === 'function') {
    try {
      autoRenderChatInteractiveWidgets(container);
    } catch (e) {
      console.warn('Interactive widgets render error:', e);
    }
  }
  mountChatAppliedWebTools(container, session);
  mountChatToolFigures(container, session);

  // تفعيل التحقق من صحة المنقول وتصفح الكتاب الأصلي للإحالات
  if (typeof window.enhanceProjectCitationsWithBookReader === 'function') {
    try {
      window.enhanceProjectCitationsWithBookReader(container);
      attachStoredWitnesses(container);
      attachFootnoteHover(container);
    } catch (e) {
      console.warn('Citation reader enhance error:', e);
    }
  }

  if (keepPosition) container.scrollTop = previousScroll;
  else scrollToBottom();
  buildChatTimeline(session);
}

if (!window._chatFnJumpBound) {
  window._chatFnJumpBound = true;
  let clearChatNoteMark = () => {
    document.querySelectorAll('.chat-fn-target').forEach((node) => node.classList.remove('chat-fn-target'));
    document.removeEventListener('mousemove', clearChatNoteMark);
  };
  document.addEventListener('click', (event) => {
    const link = event.target.closest && event.target.closest('a.chat-fn-ref, a.chat-fn-back');
    if (!link) return;
    const id = decodeURIComponent((link.getAttribute('href') || '').replace(/^#/, ''));
    const target = id && document.getElementById(id);
    if (!target) return;
    event.preventDefault();
    if (link.classList.contains('chat-fn-ref') && link.id) {
      const note = document.getElementById(id);
      const back = note && note.querySelector('a.chat-fn-back');
      if (back) back.setAttribute('href', `#${link.id}`);
    }
    document.removeEventListener('mousemove', clearChatNoteMark);
    document.querySelectorAll('.chat-fn-target').forEach((node) => node.classList.remove('chat-fn-target'));
    target.classList.add('chat-fn-target');
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const originX = event.clientX;
    const originY = event.clientY;
    clearChatNoteMark = (move) => {
      if (Math.abs(move.clientX - originX) < 4 && Math.abs(move.clientY - originY) < 4) return;
      document.querySelectorAll('.chat-fn-target').forEach((node) => node.classList.remove('chat-fn-target'));
      document.removeEventListener('mousemove', clearChatNoteMark);
    };
    document.addEventListener('mousemove', clearChatNoteMark);
  });
}

// =============================================================================
// دوال تصدير نتائج الشات البحثية إلى HTML و PDF
// =============================================================================
function exportChatMessageHtml(idx) {
  const session = chatSessions.find(s => s.id === activeSessionId);
  if (!session || !session.messages[idx]) return;
  const msg = session.messages[idx];
  const title = session.title || 'دراسة وتحقيق بحثي - منظومة المجتهد';
  const runData = {
    projectTitle: title,
    executedAt: new Date().toLocaleString('ar-SA'),
    directorModel: cleanModelDisplayName(msg.model || 'الذكاء الاصطناعي الأكاديمي'),
    rounds: [{
      round: 1,
      name: '',
      output: msg.content,
      executedAt: new Date().toLocaleString('ar-SA')
    }]
  };

  const filename = readingHtmlFilename(title);
  const htmlContent = (typeof window.buildStandaloneProjectHtml === 'function')
    ? window.buildStandaloneProjectHtml(runData, { portrait: true, downloadName: filename })
    : msg.content;

  openChatReadingWindow(htmlContent);
}

function readingHtmlFilename(title) {
  const base = String(title || 'قراءة')
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80) || 'قراءة';
  return `${base}.html`;
}

function openChatReadingWindow(htmlContent) {
  const width = Math.min(860, Math.max(680, (window.screen.availWidth || 1200) - 80));
  const height = Math.max(720, (window.screen.availHeight || 900) - 40);
  const left = Math.max(0, Math.round(((window.screen.availWidth || width) - width) / 2));
  const win = window.open('', '_blank', `popup=yes,width=${width},height=${height},left=${left},top=16,resizable=yes,scrollbars=yes`);
  if (win && win !== window) {
    writeChatReadingDocument(win, htmlContent);
    showToast('تم فتح نافذة القراءة');
    setTimeout(() => { try { win.focus(); } catch (e) {} }, 200);
    return;
  }
  openChatReadingOverlay(htmlContent);
  showToast('تم فتح نافذة القراءة');
}

function writeChatReadingDocument(win, htmlContent) {
  win.document.open();
  win.document.write(htmlContent);
  win.document.close();
  win.__readingSource = htmlContent;
}

/* طباعة محتوى تراكب القراءة/الطباعة من رأسه مباشرة: على الماك تُسلَّم
   الصفحة (مقسّمةً إن كانت ورقة طباعة) إلى غلاف التطبيق ليفتح لوحة
   طباعة النظام، وفي غيره تُطبع طباعة الإطار نفسه */
/* طباعة خام: فك روابط أرقام الحواشي من نسخة الطباعة وحدها */
function stripChatFootnoteLinks(html) {
  // الرقم يبقى داخل وسم بصنفه نفسه (مرتفعًا وأصغر كما كان) لكن بلا رابط
  const rawCss = '<style id="raw-print-css">span.pg-fn-call,span.pg-fn-marker,span.chat-fn-ref,span.chat-fn-back{color:inherit !important;font-weight:inherit !important;text-decoration:none !important;background:transparent !important;cursor:default}span.pg-fn-call,span.chat-fn-ref{vertical-align:super;line-height:0}span.chat-fn-ref{font-size:0.72em}</style>';
  const out = String(html || '')
    .replace(/<a\b[^>]*class="[^"]*pg-fn-call[^"]*"[^>]*>([\s\S]*?)<\/a>/gi, '<span class="pg-fn-call">$1</span>')
    .replace(/<a\b[^>]*class="[^"]*pg-fn-marker[^"]*"[^>]*>([\s\S]*?)<\/a>/gi, '<span class="pg-fn-marker">$1</span>')
    .replace(/<a\b[^>]*class="[^"]*chat-fn-ref[^"]*"[^>]*>([\s\S]*?)<\/a>/gi, '<span class="chat-fn-ref">$1</span>')
    .replace(/<a\b[^>]*class="[^"]*chat-fn-back[^"]*"[^>]*>([\s\S]*?)<\/a>/gi, '<span class="chat-fn-back">$1</span>')
    .replace(/<a\b[^>]*href="#(?:pgfn|pgcall|paper-fn)-[^"]*"[^>]*>([\s\S]*?)<\/a>/gi, '<span class="pg-fn-call">$1</span>');
  return out.includes('</head>') ? out.replace('</head>', rawCss + '\n</head>') : rawCss + out;
}

function printHtmlViaTempFrame(html) {
  const tmp = document.createElement('iframe');
  tmp.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden;';
  tmp.srcdoc = html;
  document.body.appendChild(tmp);
  tmp.addEventListener('load', () => {
    setTimeout(() => {
      try { tmp.contentWindow.focus(); tmp.contentWindow.print(); } catch (e) {}
      setTimeout(() => tmp.remove(), 1500);
    }, 400);
  });
}

/* ===== تصدير وورد: جمع بنية الورقة (فقرات وحواشٍ وأنماط مقاسة) ===== */
function wordRgbToHex(rgb) {
  const s = String(rgb || '');
  if (s.startsWith('rgba(0, 0, 0, 0')) return '';
  const m = s.match(/(\d+)[,\s]+(\d+)[,\s]+(\d+)/);
  if (!m) return '';
  return ((1 << 24) + (+m[1] << 16) + (+m[2] << 8) + +m[3]).toString(16).slice(1);
}

function wordMeasureStyle(el) {
  if (!el) return null;
  try {
    const cs = getComputedStyle(el);
    const font = (cs.fontFamily || '').split(',')[0].replace(/["']/g, '').trim();
    if (!font) return null;
    return {
      font,
      size: Math.round(parseFloat(cs.fontSize || '16') * 0.75 * 2) / 2,
      weight: parseInt(cs.fontWeight, 10) || 400,
      color: wordRgbToHex(cs.color),
    };
  } catch (e) { return null; }
}

function wordCleanRuns(runs) {
  const out = [];
  (runs || []).forEach((r) => {
    if (r.fn !== undefined) { out.push(r); return; }
    const t = String(r.t || '');
    if (!t) return;
    const prev = out[out.length - 1];
    if (prev && prev.fn === undefined && !!prev.b === !!r.b && !!prev.i === !!r.i && (prev.cls || '') === (r.cls || '')) {
      prev.t += t;
    } else {
      const nr = { t };
      if (r.b) nr.b = 1;
      if (r.i) nr.i = 1;
      if (r.cls) nr.cls = r.cls;
      out.push(nr);
    }
  });
  while (out.length && out[0].fn === undefined && !out[0].t.trim()) out.shift();
  while (out.length && out[out.length - 1].fn === undefined && !out[out.length - 1].t.trim()) out.pop();
  if (out.length && out[0].fn === undefined) out[0].t = out[0].t.replace(/^\s+/, '');
  if (out.length && out[out.length - 1].fn === undefined) out[out.length - 1].t = out[out.length - 1].t.replace(/\s+$/, '');
  return out;
}

function wordRunsFromNode(node, ctx, out) {
  node.childNodes.forEach((ch) => {
    if (ch.nodeType === 3) {
      if (ch.nodeValue) out.push({ t: ch.nodeValue });
      return;
    }
    if (ch.nodeType !== 1) return;
    const el = ch;
    if (el.hasAttribute('data-footnote-call')) {
      const fnIdx = ctx.callMap ? ctx.callMap.get(el) : undefined;
      if (fnIdx !== undefined && fnIdx >= 0) out.push({ fn: fnIdx });
      return;
    }
    const cls = typeof el.className === 'string' ? el.className : '';
    if (el.tagName === 'A') {
      const href = el.getAttribute('href') || '';
      const m = href.match(/paper-fn(\d+)/);
      if (m && ctx.defMap) {
        if (ctx.defMap.has(m[1])) out.push({ fn: ctx.defMap.get(m[1]) });
        return;
      }
      if (/pg-fn-call|pg-fn-marker|chat-fn-back/.test(cls)) return;
    }
    if (/(btn-verify-citation|btn-mcp-verify|chat-source-book|pg-fn-call|pg-fn-marker|chat-fn-back|no-print)/.test(cls)) return;
    if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.tagName === 'BUTTON') return;
    if (el.tagName === 'BR') { out.push({ t: '\n' }); return; }
    const sub = [];
    wordRunsFromNode(el, ctx, sub);
    const isB = el.tagName === 'B' || el.tagName === 'STRONG';
    const isI = el.tagName === 'I' || el.tagName === 'EM';
    let runCls = '';
    if (el.classList.contains('quran-verse')) runCls = 'quran';
    else if (el.classList.contains('hadith-text')) runCls = 'hadith';
    else if (el.classList.contains('quoted-text')) runCls = 'quote';
    sub.forEach((r) => {
      if (r.fn !== undefined) { out.push(r); return; }
      if (isB) r.b = 1;
      if (isI) r.i = 1;
      if (runCls && !r.cls) r.cls = runCls;
      out.push(r);
    });
  });
}

function wordBodyMeasureEl(doc) {
  const ps = Array.from(doc.querySelectorAll('.academic-text-content p'));
  let best = null;
  let bestLen = 0;
  ps.slice(0, 40).forEach((p) => {
    const len = (p.textContent || '').length;
    if (len > bestLen) { bestLen = len; best = p; }
  });
  return best || doc.querySelector('.paper-sheet p');
}

function buildWordPayload(doc) {
  const payload = { title: '', styles: {}, blocks: [], footnotes: [] };
  const titleEl = doc.querySelector('.paper-main-title');
  payload.title = titleEl ? titleEl.textContent.trim() : (doc.title || 'بحث');
  payload.styles = {
    title: wordMeasureStyle(titleEl),
    body: wordMeasureStyle(wordBodyMeasureEl(doc)),
    h: wordMeasureStyle(doc.querySelector('.academic-round-title') || doc.querySelector('.academic-subheading') || doc.querySelector('h2')),
    fn: wordMeasureStyle(doc.querySelector('[data-footnote-marker]') || doc.querySelector('.footnote-item')),
    biblio: wordMeasureStyle(doc.querySelector('.biblio-list li')),
    meta: wordMeasureStyle(doc.querySelector('.paper-sub-meta')),
    quran: wordMeasureStyle(doc.querySelector('.quran-verse')),
    hadith: wordMeasureStyle(doc.querySelector('.hadith-text')),
    quote: wordMeasureStyle(doc.querySelector('.quoted-text')),
  };
  const ctx = { callMap: new Map(), defMap: new Map() };
  const pages = Array.from(doc.querySelectorAll('.pagedjs_page'));
  if (pages.length) {
    pages.forEach((page) => {
      const calls = Array.from(page.querySelectorAll('[data-footnote-call]'));
      const markers = Array.from(page.querySelectorAll('.pagedjs_footnote_area [data-footnote-marker]'));
      calls.forEach((call, i) => {
        const mk = markers[i];
        if (!mk) { ctx.callMap.set(call, -1); return; }
        const clone = mk.cloneNode(true);
        clone.querySelectorAll('.pg-fn-marker, .btn-verify-citation, .btn-mcp-verify, script, style').forEach((n) => n.remove());
        const runs = [];
        wordRunsFromNode(clone, { callMap: new Map(), defMap: new Map() }, runs);
        ctx.callMap.set(call, payload.footnotes.length);
        payload.footnotes.push({ runs: wordCleanRuns(runs), n: i + 1 });
      });
    });
  } else {
    Array.from(doc.querySelectorAll('.footnote-list .footnote-item, p.footnote-line')).forEach((defEl) => {
      let num = '';
      const idm = (defEl.getAttribute('id') || '').match(/(\d+)/);
      const tm = (defEl.textContent || '').trim().match(/^\((\d+|[٠-٩]+)\)/);
      if (idm) num = idm[1];
      if (tm) num = String(tm[1]).replace(/[٠-٩]/g, (d) => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
      if (!num) return;
      const clone = defEl.cloneNode(true);
      clone.querySelectorAll('a.chat-fn-back, .btn-verify-citation, .btn-mcp-verify, script, style').forEach((n) => n.remove());
      const runs = [];
      wordRunsFromNode(clone, { callMap: new Map(), defMap: new Map() }, runs);
      const cleaned = wordCleanRuns(runs);
      if (cleaned.length && cleaned[0].t) cleaned[0].t = cleaned[0].t.replace(/^\s*\((?:\d+|[٠-٩]+)\)\s*/, '');
      ctx.defMap.set(num, payload.footnotes.length);
      payload.footnotes.push({ runs: cleaned, n: payload.footnotes.length + 1 });
    });
  }
  const roots = pages.length
    ? pages.map((p) => p.querySelector('.pagedjs_area') || p)
    : [doc.querySelector('.paper-sheet') || doc.body];
  const blockSel = '.paper-main-title, .paper-bismillah, .paper-sub-meta, h1, h2, h3, h4, h5, h6, p, li';
  roots.forEach((root) => {
    if (!root) return;
    root.querySelectorAll(blockSel).forEach((el) => {
      if (el.closest('.pagedjs_footnote_area')) return;
      if (el.closest('.footnote-list') || el.classList.contains('footnote-line') || el.classList.contains('footnote-item')) return;
      let kind = 'p';
      if (el.classList.contains('paper-main-title')) kind = 'title';
      else if (el.classList.contains('paper-sub-meta')) kind = 'meta';
      else if (el.classList.contains('paper-bismillah')) kind = 'bismillah';
      else if (el.classList.contains('biblio-title')) kind = 'biblioTitle';
      else if (el.closest('.biblio-list')) kind = 'biblioItem';
      else if (/^H[1-6]$/.test(el.tagName) || el.classList.contains('academic-round-title') || el.classList.contains('academic-subheading')) kind = 'h';
      const runs = [];
      wordRunsFromNode(el, ctx, runs);
      const cleaned = wordCleanRuns(runs);
      if (!cleaned.length) return;
      payload.blocks.push({ kind, runs: cleaned });
    });
  });
  // لا فواصل صفحات قسرية: يصفّح وورد بتدفق طبيعي فيملأ الصفحات
  // ويقسّم الحواشي الطويلة، وترقيمه التلقائي متجدد كل صفحة في
  // المتن والحاشية معًا فلا ينفصل الرقمان أبدًا
  return payload;
}

async function exportWordFromDoc(doc) {
  const payload = buildWordPayload(doc);
  if (!payload.blocks.length) throw new Error('empty');
  const res = await fetch('/api/projects/export-docx', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('docx');
  const blob = await res.blob();
  const name = `${String(payload.title || 'بحث').replace(/[\s/\\:*?"<>|]+/g, '_').slice(0, 80) || 'بحث'}.docx`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function printChatReadingFrame(raw) {
  const frame = document.getElementById('chatReadingFrame');
  if (!frame || !frame.contentWindow) return;
  const bridge = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.almujtahed;
  let out = '';
  try {
    out = '<!DOCTYPE html>\n' + frame.contentDocument.documentElement.outerHTML;
    out = out.replace(/<script[^>]*paged\.polyfill[^>]*><\/script>/i, '');
    if (raw) out = stripChatFootnoteLinks(out);
  } catch (e) { out = ''; }
  if (bridge && out) {
    try {
      bridge.postMessage({ action: 'printHtml', html: out, base: location.origin + '/' });
      showToast(raw ? 'جارٍ فتح نافذة الطباعة الخام…' : 'جارٍ فتح نافذة طباعة النظام…');
      return;
    } catch (e) {}
  }
  if (raw && out) {
    printHtmlViaTempFrame(out);
    return;
  }
  try { frame.contentWindow.focus(); } catch (e) {}
  try { frame.contentWindow.print(); } catch (e) {}
}

function openChatReadingOverlay(htmlContent) {
  let overlay = document.getElementById('chatReadingOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'chatReadingOverlay';
    overlay.className = 'chat-reading-overlay';
    overlay.innerHTML = `
      <div class="chat-reading-window" role="dialog" aria-label="قراءة">
        <div class="chat-reading-head">
          <button type="button" class="chat-reading-print">🖨️ طباعة / حفظ PDF</button>
          <button type="button" class="chat-reading-print chat-reading-print-raw" title="نفس الطباعة لكن بأرقام حواشٍ غير مرتبطة: نص خام بلا روابط بين المتن والحاشية">🖨️ طباعة خام</button>
          <button type="button" class="chat-reading-print chat-reading-word" title="تصدير البحث ملف وورد DOCX بنفس التنسيق وبحواشٍ سفلية حقيقية">📝 تصدير وورد</button>
          <button type="button" class="chat-reading-close" aria-label="إغلاق">إغلاق</button>
        </div>
        <iframe id="chatReadingFrame" title="قراءة"></iframe>
      </div>`;
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) overlay.hidden = true;
    });
    overlay.querySelector('.chat-reading-close').addEventListener('click', () => {
      overlay.hidden = true;
    });
    overlay.querySelector('.chat-reading-print').addEventListener('click', () => {
      printChatReadingFrame(false);
    });
    overlay.querySelector('.chat-reading-print-raw').addEventListener('click', () => {
      printChatReadingFrame(true);
    });
    overlay.querySelector('.chat-reading-word').addEventListener('click', async () => {
      const fr = document.getElementById('chatReadingFrame');
      const fw = fr && fr.contentWindow;
      if (fw && typeof fw.exportPaperWord === 'function') { fw.exportPaperWord(); return; }
      if (!fr || !fr.contentDocument) return;
      try {
        await exportWordFromDoc(fr.contentDocument);
        showToast('تم تصدير ملف وورد');
      } catch (e) {
        showToast('تعذر تصدير ملف وورد');
      }
    });
    document.body.appendChild(overlay);
  }
  const frame = overlay.querySelector('#chatReadingFrame');
  overlay.hidden = false;
  frame.onload = () => {
    try { frame.contentWindow.__readingSource = htmlContent; } catch (e) {}
  };
  frame.srcdoc = htmlContent;
}

function chatAnswerPaper(idx) {
  const session = chatSessions.find(s => s.id === activeSessionId);
  if (!session || !session.messages[idx]) return null;
  const msg = session.messages[idx];
  const title = chatMessagePaperTitle(msg, session);
  const output = msg.selection_research
    ? String(msg.content || '').replace(/^#{1,3}\s+[^\n]+\n+/, '')
    : msg.content;
  return {
    title,
    runData: {
      projectTitle: title,
      executedAt: new Date().toLocaleString('ar-SA'),
      directorModel: cleanModelDisplayName(msg.model || 'الذكاء الاصطناعي الأكاديمي'),
      bibliography: Array.isArray(msg.witnesses) ? msg.witnesses : [],
      rounds: [{
        round: 1,
        name: msg.selection_research ? title : '',
        output,
        executedAt: new Date().toLocaleString('ar-SA')
      }]
    }
  };
}

async function prepareChatAnswerShareFile(idx) {
  const paper = chatAnswerPaper(idx);
  if (!paper || typeof buildAcademicPaperHtml !== 'function') throw new Error('paper');
  const html = buildAcademicPaperHtml(paper.runData, { toolbar: false, forPdf: true });
  const res = await fetch('/api/projects/export-pdf', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ html, title: paper.title || 'قراءة' })
  });
  if (!res.ok) throw new Error('pdf');
  const blob = await res.blob();
  if (!blob || blob.size < 800) throw new Error('pdf-empty');
  const name = readingHtmlFilename(paper.title).replace(/\.html$/i, '') + '.pdf';
  return new File([blob], name, { type: 'application/pdf' });
}

async function exportChatMessagePdf(idx) {
  const paper = chatAnswerPaper(idx);
  if (!paper) return;
  if (typeof window.openAcademicPaperWindow === 'function') {
    window.openAcademicPaperWindow(paper.runData);
    return;
  }
  showToast('تعذر تجهيز صفحة البحث للطباعة');
}

function copyChatMessageText(idx) {
  const session = chatSessions.find(s => s.id === activeSessionId);
  if (!session || !session.messages[idx]) return;
  navigator.clipboard.writeText(session.messages[idx].content);
  showToast('تم نسخ نص النتيجة البحثية إلى الحافظة 📋');
}

function cleanModelDisplayName(modelId) {
  if (!modelId) return 'المجتهد الذكي';
  if (modelId === 'local-almojtahed-8b') return 'المجتهد 8B (محلي)';
  const parts = modelId.split('/');
  return parts.length > 1 ? parts[1] : modelId;
}

// معالجة الضغط على Enter في مربع الكتابة
// ================= أوامر البحث الجاهزة (قائمة السلاش) =================
const RESEARCH_COMMANDS = [
  { id: 'plan', label: 'خطة بحث', desc: 'يبني معك تقسيم البحث وجولاته قبل التنفيذ', soon: true },
  { id: 'general', label: 'بحث عام', desc: 'توزيع متوازن بين الفنون بلا طغيان فن' },
  { id: 'fiqh-long', label: 'بحث فقهي مطول', desc: 'تصوير وسبب خلاف وتخريج وأقوال ومناقشة وترجيح' },
  { id: 'fiqh-mid', label: 'بحث فقهي متوسط', desc: 'هيكل فقهي كامل بإطالة متوسطة' },
  { id: 'fiqh-short', label: 'بحث فقهي مختصر', desc: 'الأقوال معينة والراجح ودليله' },
  { id: 'hadith-long', label: 'بحث حديثي مطول', desc: 'طرق وتخريج وعلل وحكم وشرح' },
  { id: 'hadith-mid', label: 'بحث حديثي متوسط', desc: 'تخريج وحكم بهيكل متوسط' },
  { id: 'hadith-short', label: 'بحث حديثي مختصر', desc: 'المصادر الأصلية وخلاصة الحكم' },
  { id: 'tafsir-long', label: 'بحث تفسيري مطول', desc: 'أقوال السلف والمفسرون طبقة طبقة' },
  { id: 'tafsir-mid', label: 'بحث تفسيري متوسط', desc: 'أقوال المفسرين والترجيح متوسطاً' },
  { id: 'tafsir-short', label: 'بحث تفسيري مختصر', desc: 'المعنى وأمهات الأقوال والراجح' },
  { id: 'aqidah-long', label: 'بحث عقدي مطول', desc: 'مقالات المدارس من كتبها ومناقشة محايدة' },
  { id: 'aqidah-mid', label: 'بحث عقدي متوسط', desc: 'المقالات والأدلة باختصار متوسط' },
  { id: 'aqidah-short', label: 'بحث عقدي مختصر', desc: 'تحرير النزاع والراجح ودليله' },
  { id: 'lugha-long', label: 'بحث لغوي مطول', desc: 'المعاجم طبقة طبقة والشواهد والفروق' },
  { id: 'lugha-mid', label: 'بحث لغوي متوسط', desc: 'المعنى والاشتقاق والشواهد متوسطاً' },
  { id: 'lugha-short', label: 'بحث لغوي مختصر', desc: 'المعنى عند أمهات المعاجم وشاهد' },
  { id: 'tarikh-long', label: 'بحث تاريخي مطول', desc: 'الروايات بطبقات المصادر ونقدها' },
  { id: 'tarikh-mid', label: 'بحث تاريخي متوسط', desc: 'الروايات واختلافها والترجيح' },
  { id: 'tarikh-short', label: 'بحث تاريخي مختصر', desc: 'أرجح الروايات وسببه' },
  { id: 'fiqh-hadith-long', label: 'بحث فقهي حديثي مطول', desc: 'أحاديث الباب أولاً ثم الأقوال والترجيح' },
  { id: 'fiqh-hadith-mid', label: 'بحث فقهي حديثي متوسط', desc: 'تخريج ثم أقوال معينة وترجيح' },
  { id: 'fiqh-hadith-short', label: 'بحث فقهي حديثي مختصر', desc: 'حكم الأحاديث والأقوال والراجح' },
];
window.selectedResearchCommand = null;
let _slashItems = [], _slashIdx = 0;

function _slashMenuEl() {
  let el = document.getElementById('slashCommandMenu');
  if (!el) {
    el = document.createElement('div');
    el.id = 'slashCommandMenu';
    el.className = 'slash-menu';
    el.hidden = true;
    const area = document.querySelector('.chat-input-area');
    if (area) area.insertBefore(el, area.firstChild);
  }
  return el;
}
function closeSlashMenu() { const el = document.getElementById('slashCommandMenu'); if (el) el.hidden = true; _slashItems = []; }
function renderSlashMenu(filter) {
  const el = _slashMenuEl();
  const f = (filter || '').trim();
  _slashItems = RESEARCH_COMMANDS.filter(c => !f || c.label.includes(f) || c.desc.includes(f));
  _slashIdx = Math.min(_slashIdx, Math.max(0, _slashItems.length - 1));
  if (!_slashItems.length) { el.hidden = true; return; }
  el.innerHTML = _slashItems.map((c, i) =>
    `<button type="button" class="slash-item${i === _slashIdx ? ' active' : ''}${c.soon ? ' soon' : ''}" data-i="${i}">
       <span class="slash-item-label">/${c.label}</span>
       <span class="slash-item-desc">${c.desc}${c.soon ? ' — قريباً' : ''}</span>
     </button>`).join('');
  el.querySelectorAll('.slash-item').forEach(btn => {
    btn.addEventListener('mousedown', (ev) => { ev.preventDefault(); pickSlashCommand(_slashItems[parseInt(btn.dataset.i, 10)]); });
  });
  el.hidden = false;
}
function pickSlashCommand(cmd) {
  const input = document.getElementById('chatInputText');
  if (!cmd || cmd.soon) { closeSlashMenu(); if (input) input.focus(); return; }
  window.selectedResearchCommand = cmd.id;
  if (input) {
    input.value = input.value.replace(/^\s*\/\S*\s*/, '');
    input.focus();
  }
  showResearchCmdChip(cmd);
  closeSlashMenu();
}
function showResearchCmdChip(cmd) {
  const old = document.getElementById('researchCmdChip');
  if (old) old.remove();  // إزالة الشريحة القديمة فقط — دون تصفير الاختيار الحالي
  const area = document.querySelector('.chat-input-area');
  if (!area) return;
  const chip = document.createElement('div');
  chip.id = 'researchCmdChip';
  chip.className = 'research-cmd-chip';
  chip.innerHTML = `<span>الأمر البحثي: <b>${cmd.label}</b></span>
    <button type="button" title="إلغاء الأمر" onclick="clearResearchCmdChip(true)">✕</button>`;
  const box = area.querySelector('.chat-input-box');
  area.insertBefore(chip, box || null);
}
function clearResearchCmdChip(focusBack) {
  const chip = document.getElementById('researchCmdChip');
  if (chip) chip.remove();
  window.selectedResearchCommand = null;
  if (focusBack) { const i = document.getElementById('chatInputText'); if (i) i.focus(); }
}
window.clearResearchCmdChip = clearResearchCmdChip;
function initSlashCommands() {
  const input = document.getElementById('chatInputText');
  if (!input || input._slashReady) return;
  input._slashReady = true;
  input.addEventListener('input', () => {
    const v = input.value;
    const m = v.match(/^\s*\/(\S*)$/);
    if (m) renderSlashMenu(m[1]); else closeSlashMenu();
  });
  input.addEventListener('blur', () => setTimeout(closeSlashMenu, 180));
}
document.addEventListener('DOMContentLoaded', initSlashCommands);

function handleChatInputKey(e) {
  const menu = document.getElementById('slashCommandMenu');
  if (menu && !menu.hidden && _slashItems.length) {
    if (e.key === 'ArrowDown') { e.preventDefault(); _slashIdx = (_slashIdx + 1) % _slashItems.length; renderSlashMenu(document.getElementById('chatInputText').value.replace(/^\s*\//, '')); return; }
    if (e.key === 'ArrowUp') { e.preventDefault(); _slashIdx = (_slashIdx - 1 + _slashItems.length) % _slashItems.length; renderSlashMenu(document.getElementById('chatInputText').value.replace(/^\s*\//, '')); return; }
    if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); pickSlashCommand(_slashItems[_slashIdx]); return; }
    if (e.key === 'Escape') { closeSlashMenu(); return; }
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChatMessage();
  }
}

// معالجة اختيار المرفقات (صور، مستندات، ملفات نصية وبي دي إف) وحفظها في المجلد (Bucket)
async function handleFileSelected(e) {
  const files = Array.from(e.target.files);
  if (!files.length) return;

  const preview = document.getElementById('attachmentsPreview');
  if (preview) preview.style.display = 'flex';

  for (const file of files) {
    const tempId = 'upload_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
    const item = {
      id: tempId,
      name: file.name,
      uploading: true,
      error: null
    };
    currentAttachments.push(item);
    renderAttachmentsPreview();

    try {
      const formData = new FormData();
      formData.append('file', file);

      const resp = await fetch('/api/chat/upload', {
        method: 'POST',
        body: formData
      });
      const data = await resp.json().catch(() => ({}));

      if (resp.status === 401) {
        item.uploading = false;
        item.error = 'انتهت الجلسة';
        renderAttachmentsPreview();
        if (typeof showToast === 'function') showToast('انتهت الجلسة. سجّل الدخول ثم أعد رفع الملف');
        setTimeout(() => { window.location.href = '/login'; }, 700);
        return;
      }

      if (data.success) {
        item.uploading = false;
        item.safeName = data.safe_filename;
        item.url = data.file_url;
        item.path = data.file_path;
        item.size = data.file_size;
        item.type = data.file_type;
        item.extractedText = data.extracted_text;
        item.hasImage = data.has_image;
        item.base64Data = data.base64_data;
        renderAttachmentsPreview();
        if (typeof showToast === 'function') {
          showToast(`📁 تم حفظ «${data.filename}» في المجلد واستخراج نصوصه بنجاح!`, 2500);
        }
      } else {
        item.uploading = false;
        item.error = data.detail || data.error || 'فشل الرفع';
        renderAttachmentsPreview();
        if (typeof showToast === 'function') {
          showToast(`❌ فشل حفظ «${file.name}»: ${item.error}`, 3500);
        }
      }
    } catch (err) {
      item.uploading = false;
      item.error = err.message || 'خطأ في الشبكة';
      renderAttachmentsPreview();
    }
  }

  e.target.value = '';
}

function renderAttachmentsPreview() {
  const preview = document.getElementById('attachmentsPreview');
  if (!preview) return;

  preview.innerHTML = currentAttachments.map((att, i) => {
    if (att.uploading) {
      return `
        <span style="font-size: 11.5px; background: rgba(184, 115, 51, 0.08); border: 1px dashed var(--accent-clay); color: var(--accent-clay); padding: 4px 10px; border-radius: var(--radius-sm); display: inline-flex; align-items: center; gap: 6px;">
          <span style="display: inline-block; animation: spin 1s linear infinite;">⏳</span>
          جارٍ حفظ <strong>${escapeHtml(att.name)}</strong> في المجلد واستخراج محتواه...
        </span>
      `;
    }
    if (att.error) {
      return `
        <span style="font-size: 11.5px; background: rgba(220, 53, 69, 0.1); border: 1px solid #dc3545; color: #dc3545; padding: 4px 10px; border-radius: var(--radius-sm); display: inline-flex; align-items: center; gap: 6px;">
          ❌ ${escapeHtml(att.name)} (${escapeHtml(att.error)})
          <button onclick="removeAttachment(${i})" style="background: none; border: none; cursor: pointer; color: #dc3545; font-size: 14px;">&times;</button>
        </span>
      `;
    }
    const icon = att.hasImage ? '🖼️' : (att.name.endsWith('.pdf') ? '📕' : (att.name.endsWith('.docx') ? '📝' : '📄'));
    return `
      <span style="font-size: 11.5px; background: var(--bg-surface); border: 1px solid var(--border-subtle); padding: 4px 10px; border-radius: var(--radius-sm); display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);" title="مسار الملف على القرص: ${escapeHtml(att.path || '')}">
        <span>${icon}</span>
        <span style="font-weight: 600; color: var(--text-main);">${escapeHtml(att.name)}</span>
        <span style="color: var(--accent-clay); font-size: 10px; font-weight: 700;">(محفوظ بالبوكت)</span>
        <button onclick="removeAttachment(${i})" style="background: none; border: none; cursor: pointer; color: var(--text-light); font-size: 15px; line-height: 1;" title="حذف المرفق">&times;</button>
      </span>
    `;
  }).join('');
  preview.style.display = currentAttachments.length ? 'flex' : 'none';
}

function removeAttachment(idx) {
  currentAttachments.splice(idx, 1);
  renderAttachmentsPreview();
}

// إرسال رسالة الشات
async function sendChatMessage() {
  const input = document.getElementById('chatInputText');
  const text = input.value.trim();
  const outgoingResearchCommand = window.selectedResearchCommand || null;

  if (currentAttachments.some(a => a.uploading)) {
    if (typeof showToast === 'function') {
      showToast('يرجى الانتظار ثوانٍ حتى يكتمل حفظ الملف في المجلد واستخراج محتواه...', 2500);
    }
    return;
  }

  // تصفية المرفقات الصالحة الجاهزة
  const validAttachments = currentAttachments.filter(a => !a.error && !a.uploading);

  if (!text && validAttachments.length === 0) return;
  if (chatGraphBusy) return;

  const session = chatSessions.find(s => s.id === activeSessionId);
  if (!session) return;

  // إذا كانت هذه أول رسالة للمستخدم، قم بتحديث عنوان المحادثة إن لم يكن محدداً مسبقاً بعنوان مخصص
  if (session.messages.length <= 1) {
    if (!session.title || session.title === 'محادثة تراثية جديدة' || session.title === 'محادثة جديدة') {
      session.title = (text || (validAttachments[0] ? validAttachments[0].name : 'محادثة جديدة')).slice(0, 35);
    }
    renderChatHistorySidebar();
  }

  // إضافة رسالة المستخدم مع توثيق اسم ومسار الملف المحفوظ بالبوكت
  let userMessageContent = text;
  if (validAttachments.length > 0) {
    const fileNotices = validAttachments.map(a => 
      `📁 [ملف مرفق محفوظ في المجلد: ${a.name} | مساره: ${a.path || a.url}]`
    ).join('\n');
    userMessageContent += (userMessageContent ? '\n\n' : '') + fileNotices;
  }

  session.messages.push({
    role: 'user',
    content: userMessageContent
  });

  input.value = '';
  if (typeof clearResearchCmdChip === 'function') clearResearchCmdChip(false);
  // حفظ نسخة من المرفقات لتمريرها في الطلب البرمجي ثم تفريغ الواجهة
  const outgoingAttachments = validAttachments.slice();
  currentAttachments = [];
  renderAttachmentsPreview();
  renderSessionMessages(activeSessionId);


  // إرسال الطلب للنموذج واستقبال الرد
  await triggerChatCompletion(session, outgoingAttachments, { researchCommand: outgoingResearchCommand });
}

// =============================================================================
// دورة توليد الإجابة وإرسال الطلب للنموذج أو الوكلاء (مشتركة مع إعادة التوليد)
// =============================================================================
function placeChatReply(session, message, options) {
  if (options && Number.isInteger(options.insertAt)) {
    const at = Math.max(0, Math.min(options.insertAt, session.messages.length));
    session.messages.splice(at, 0, message);
  } else {
    session.messages.push(message);
  }
}

async function triggerChatCompletion(session, attachments = [], options = {}) {
  if (!session) return;
  const promptMessages = (options && options.contextMessages) || session.messages;

  const selectedModel = document.getElementById('chatModelSelect')?.value || 
                        localStorage.getItem('almojtahed_active_chat_model') || 
                        'anthropic/claude-3.7-sonnet';

  const activeProvider = localStorage.getItem(ownerStorageKey('almojtahed_active_provider')) || 'openrouter';
  let savedKeys = {};
  try {
    savedKeys = readProviderKeys();
  } catch (e) {}
  const apiKey = savedKeys[activeProvider] || '';

  const modelDisplayName = document.getElementById('chatModelSelect')?.selectedOptions[0]?.text || cleanModelDisplayName(selectedModel);

  // فحص ما إذا كان المستخدم قد فعّل إسناد الطلب لمجموعة الوكلاء المساعدين
  const builtGroup = buildChatAgentGroupPayload();
  const assignedGroupPayload = builtGroup ? builtGroup.payload : null;
  const activeAgent = builtGroup ? builtGroup.activeAgent : null;
  const mcpPayload = buildChatMcpPayload();

  // اعتماد النموذج المختار صراحة من قبل المستخدم في ترويسة الشات الذكي
  const customOn = !!currentSettings.modelParams?.customGeneration;
  const savedParams = currentSettings.modelParams || {};
  let executionModel = selectedModel;
  let executionThinking = currentThinkingLevel;
  let executionPrompt = customOn ? (document.getElementById('systemPromptInput')?.value.trim() || savedParams.systemPrompt || '') : '';
  let executionTemp = parseFloat(document.getElementById('paramTemperature')?.value ?? savedParams.temperature ?? 0.2);
  let executionTopK = parseInt(document.getElementById('paramTopK')?.value ?? savedParams.topK ?? 40, 10);
  let executionMaxTokens = customOn ? parseInt(document.getElementById('paramMaxTokens')?.value ?? savedParams.maxTokens ?? 65536, 10) : undefined;
  let executionRepPenalty = customOn ? parseFloat(document.getElementById('paramRepPenalty')?.value ?? savedParams.repPenalty ?? 1.1) : undefined;

  if (activeAgent && activeAgent.thinking && !executionThinking) executionThinking = activeAgent.thinking;
  if (!customOn && activeAgent && activeAgent.systemPrompt) executionPrompt = activeAgent.systemPrompt;

  // إظهار فقاعة مؤشر الكتابة للنموذج
  const container = document.getElementById('chatMessagesContainer');
  const typingBubble = document.createElement('div');
  typingBubble.className = 'message-bubble assistant';
  typingBubble.id = 'typingBubbleIndicator';

  const hybridModeName = isChatHybridSearchEnabled ? 'بحث هجين' : 'دلالي صرف';
  const thinkingPhrase = (typeof describeThinking === 'function')
    ? describeThinking(executionModel, executionThinking)
    : (executionThinking === 'high' ? 'عالي · أعمق · أعلى تكلفة' : 'متوسط · متزن · متوسط التكلفة');
  let typingMessage = `جارٍ الاستدلال واستدعاء نصوص الشاملة عبر «<strong>${escapeHtml(modelDisplayName)}</strong>» (${escapeHtml(thinkingPhrase)} · ${hybridModeName})...`;
  if (assignedGroupPayload && activeAgent) {
    typingMessage = `جارٍ تشغيل وكيل «<strong>${escapeHtml(activeAgent.name)}</strong>» عبر نموذج «<strong>${escapeHtml(cleanModelDisplayName(executionModel))}</strong>» والبحث في نطاق كتبه المحدد (${hybridModeName})...`;
  } else if (assignedGroupPayload) {
    typingMessage = `جارٍ إرسال وتوجيه الطلب حصراً إلى وكلاء «<strong>${escapeHtml(assignedGroupPayload.name)}</strong>» لاستخراج البيانات التراثية ومعالجتها (${hybridModeName})...`;
  } else if (mcpPayload.length) {
    typingMessage = `جارٍ ربط خوادم MCP: «<strong>${escapeHtml(mcpPayload.map(item => item.name).join('، '))}</strong>» مع «<strong>${escapeHtml(modelDisplayName)}</strong>»...`;
  }

  typingBubble.innerHTML = `
    <div class="message-avatar">مج</div>
    <div class="message-content">
      <span style="display: inline-block; animation: pulse 1.2s infinite; font-size: 13.5px; color: var(--text-muted);">
        ${typingMessage}
      </span>
    </div>
  `;
  container.appendChild(typingBubble);
  scrollToBottom();
  const stopAnswerClock = startChatAnswerClock(typingBubble);

  const control = startChatRun();
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: control.signal,
      body: JSON.stringify({
        chat_id: (typeof activeSessionId !== 'undefined' ? activeSessionId : null),
        model: executionModel,
        provider: activeProvider,
        api_key: apiKey,
        thinking_level: executionThinking,
        use_hybrid: isChatHybridSearchEnabled,
        semantic_enhanced: isSemanticEnhancedEnabled,
        messages: promptMessages,
        system_prompt: executionPrompt || null,
        temperature: executionTemp,
        top_k: executionTopK,
        max_tokens: executionMaxTokens,
        repetition_penalty: executionRepPenalty,
        custom_generation: customOn,
        context_tokens: (typeof currentContextTokens === 'function') ? currentContextTokens() : 1048576,
        witness_limit: (typeof currentWitnessCount === 'function') ? currentWitnessCount() : 50,
        death_max: (typeof currentDeathMax === 'function') ? currentDeathMax() : null,
        intent_genres: (typeof currentIntentGenres === 'function') ? currentIntentGenres() : null,
        research_command: (options && options.researchCommand) || null,
        discussion_mode: (options && options.discussionMode) || (discussionState(session.id) === 'open' ? 'open' : null),
        risk_control: (options && options.riskControl && options.riskControl.length) ? { items: options.riskControl } : null,
        semantic_enhanced: isSemanticEnhancedEnabled,
        providers: readProviderKeys(),
        agent_group: window.chatRawMcp ? null : assignedGroupPayload,
        mcp_servers: window.chatRawMcp ? [] : mcpPayload,
        raw_mcp: !!window.chatRawMcp,
        mcp_for_agents: localStorage.getItem('almojtahed_mcp_for_agents') === '1',
        agent_dispatch_mode: window.chatAgentDispatchMode || 'parallel',
        attachments: (attachments || []).map(a => ({
          filename: a.name,
          safe_filename: a.safeName,
          file_url: a.url,
          file_path: a.path,
          file_type: a.type,
          file_size: a.size,
          extracted_text: a.extractedText,
          has_image: a.hasImage,
          base64_data: a.base64Data
        }))
      })
    });

    const data = await response.json();
    const durationMs = stopAnswerClock();
    typingBubble.remove();

    placeChatReply(session, {
      role: 'assistant',
      content: data.reply || 'عذراً، لم أتلقَّ استجابة واضحة من الخادم.',
      model: data.model || selectedModel,
      provider: data.provider || activeProvider,
      agent_group: data.raw_mcp ? 'MCP خام مباشر' : (data.agent_group || [assignedGroupPayload ? assignedGroupPayload.name : '', mcpPayload.map(item => item.name).join(' + ')].filter(Boolean).join(' + ') || null),
      duration_ms: durationMs,
      thinking_effort: data.thinking_effort || '',
      thinking_label: (typeof thinkingEffortLabel === 'function') ? thinkingEffortLabel(data.thinking_effort) : '',
      witnesses: Array.isArray(data.witnesses) ? data.witnesses : [],
      regenerated: !!options.regenerated,
      stage: (options && options.discussionMode === 'finalize') ? 'final'
        : (((options && options.discussionMode === 'open') || discussionState(session.id) === 'open') ? 'discussion' : undefined)
    }, options);

    saveChatSessions();
    renderSessionMessages(activeSessionId);

  } catch (err) {
    const durationMs = stopAnswerClock();
    typingBubble.remove();
    if (chatStopped(err)) {
      if (typeof showToast === 'function') showToast('تم الإيقاف');
      return;
    }
    placeChatReply(session, {
      role: 'assistant',
      content: `⚠️ تعذر استكمال المحادثة: ${err.message}`,
      duration_ms: durationMs,
      regenerated: !!options.regenerated
    }, options);
    saveChatSessions();
    renderSessionMessages(activeSessionId);
  } finally {
    endChatRun();
  }
}

// إعادة توليد الإجابة مرة أخرى بناءً على سؤال المستخدم المحدد
async function regenerateAnswerForUserMessage(idx) {
  const session = chatSessions.find(s => s.id === activeSessionId);
  if (!session || !session.messages || !session.messages[idx]) return;

  // التأكد من أن الرسالة هي سؤال المستخدم
  if (session.messages[idx].role !== 'user') return;

  // إذا كان هناك توليد جارٍ حالياً نمنع التكرار
  if (document.getElementById('typingBubbleIndicator')) {
    showToast('جارٍ معالجة إجابة حالياً، يرجى الانتظار...');
    return;
  }

  // اقتطاع المحادثة حتى هذا السؤال لبدء توليد جديد من عنده
  session.messages = session.messages.slice(0, idx + 1);
  saveChatSessions();
  renderSessionMessages(activeSessionId);

  showToast('جارٍ مسح الإجابة وإعادة توليدها... 🔄');
  await triggerChatCompletion(session, []);
}
window.regenerateAnswerForUserMessage = regenerateAnswerForUserMessage;

async function regenerateAnswerKeepingCurrent(idx) {
  const session = chatSessions.find(s => s.id === activeSessionId);
  if (!session || !session.messages || !session.messages[idx]) return;
  if (session.messages[idx].role !== 'user') return;
  if (document.getElementById('typingBubbleIndicator')) {
    showToast('جارٍ معالجة إجابة حالياً، يرجى الانتظار...');
    return;
  }

  let insertAt = idx + 1;
  while (insertAt < session.messages.length && session.messages[insertAt].role !== 'user') {
    insertAt += 1;
  }
  showToast('جارٍ توليد إجابة إضافية مع الإبقاء على الحالية... 🔄');
  await triggerChatCompletion(session, [], {
    contextMessages: session.messages.slice(0, idx + 1),
    insertAt,
    regenerated: true
  });
}
window.regenerateAnswerKeepingCurrent = regenerateAnswerKeepingCurrent;

// نسخ نص سؤال المستخدم إلى الحافظة
function copyUserMessageText(idx) {
  const session = chatSessions.find(s => s.id === activeSessionId);
  if (!session || !session.messages || !session.messages[idx]) return;
  const content = session.messages[idx].content || '';
  navigator.clipboard.writeText(content);
  showToast('تم نسخ نص السؤال إلى الحافظة 📋');
}
window.copyUserMessageText = copyUserMessageText;

// =============================================================================
// إدارة ربط الشات بمجموعات الوكلاء المساعدين
// =============================================================================

function readChatAgentGroups() {
  let groups = [];
  try {
    const raw = localStorage.getItem(ownerStorageKey('almojtahed_agent_groups'));
    if (raw) groups = JSON.parse(raw);
  } catch (e) {}
  if ((!groups || !groups.length) && window.agentGroups && window.agentGroups.length) {
    groups = window.agentGroups;
  }
  return Array.isArray(groups) ? groups.filter(g => g && g.id && g.name) : [];
}

function readSelectedChatGroupIds(groups) {
  const valid = new Set((groups || []).map(g => g.id));
  const raw = localStorage.getItem('almojtahed_chat_selected_group_ids');
  if (raw !== null) {
    try {
      const ids = JSON.parse(raw);
      // اختيار محفوظ فارغ أو باطل = لا اختيار: يسقط للافتراضي القياسي
      if (Array.isArray(ids)) {
        const kept = ids.filter(id => valid.has(id));
        if (kept.length) return kept;
      }
    } catch (e) {}
  }
  const one = localStorage.getItem('almojtahed_chat_selected_group_id');
  if (one && valid.has(one)) return [one];
  if (!groups || !groups.length) return [];
  const def = groups.find(g => g && g.is_default) || groups[0];
  return def ? [def.id] : [];
}

function agentsChosenInGroup(group) {
  const agents = (Array.isArray(group?.agents) ? group.agents : []).filter(agent => agent.kind !== 'mcp');
  const raw = localStorage.getItem('almojtahed_chat_selected_agents_' + group.id);
  if (raw === null) return agents.slice();
  let selectedIds = [];
  try { selectedIds = JSON.parse(raw); } catch (e) { return agents.slice(); }
  if (!Array.isArray(selectedIds)) return agents.slice();
  return agents.filter(a => selectedIds.includes(a.id));
}

function groupSelectionLabel(groups, ids) {
  if (!groups.length) return 'لا توجد مجموعات';
  if (!ids.length) return 'لم تُحدد أي مجموعة';
  if (ids.length === groups.length) return `كل المجموعات (${groups.length})`;
  const names = groups.filter(g => ids.includes(g.id)).map(g => g.name);
  if (names.length === 1) return names[0];
  return `${names.length} مجموعات: ${names.slice(0, 2).join('، ')}${names.length > 2 ? '...' : ''}`;
}

function writeSelectedChatGroupIds(ids) {
  const groups = readChatAgentGroups();
  const valid = new Set(groups.map(g => g.id));
  ids = (Array.isArray(ids) ? ids : []).filter(id => valid.has(id));
  localStorage.setItem('almojtahed_chat_selected_group_ids', JSON.stringify(ids));
  localStorage.setItem('almojtahed_chat_selected_group_id', ids[0] || '');
  const select = document.getElementById('chatAgentGroupSelect');
  if (select) {
    select.innerHTML = groups.map(g => `<option value="${escapeHtml(g.id)}" ${g.id === ids[0] ? 'selected' : ''}>${escapeHtml(g.name)}</option>`).join('')
      || '<option value="">لا توجد مجموعات</option>';
    select.value = ids[0] || '';
  }
  const label = document.getElementById('chatGroupBtnLabel');
  if (label) updateChatSourceLabels();
  const badge = document.getElementById('chatGroupCountBadge');
  if (badge) updateChatSourceLabels();
  const items = document.getElementById('chatGroupChecklistItems');
  if (items) {
    items.querySelectorAll('input[data-group-id]').forEach(cb => {
      const on = ids.includes(cb.getAttribute('data-group-id'));
      cb.checked = on;
      const row = cb.closest('.chat-checklist-item');
      if (row) row.classList.toggle('is-selected', on);
    });
  }
  return ids;
}

function chatGroupDirector() {
  if (!document.getElementById('chatUseAgentGroupCheckbox')?.checked) return null;
  const groups = readChatAgentGroups();
  const chosen = groups.filter(g => readSelectedChatGroupIds(groups).includes(g.id));
  for (const g of chosen) {
    const dir = (g.agents || []).find(a => a && (a.is_director || a.role === 'director' || a.kind === 'director'));
    if (dir && agentsChosenInGroup(g).some(a => a.id === dir.id)) return { group: g, director: dir };
  }
  return null;
}

// سلطة واحدة معلنة: ما دام للمجموعة مدير قائد معيّن فيها، تتعطل أدوات
// نموذج المحادثة (نموذجه وتفكيره وسياقه وشواهده وسقف وفاته ونوع بحثه)
// لئلا تتنازع قيادتان؛ وتعطيل المدير من قائمة الوكلاء يعيدها فورًا.
function refreshDirectorAuthorityUI() {
  const found = chatGroupDirector();
  ['chatModelSelect', 'chatThinkingSelect', 'chatContextSelect', 'intentSelect', 'deathMaxSelect', 'witnessDdBtn', 'btnToggleChatHybridSearch', 'chatCustomModelTrigger'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.disabled = !!found;
    el.style.opacity = found ? '0.45' : '';
    if (found) el.title = 'معطّل: القيادة لمدير المشروع داخل المجموعة';
  });
  const badge = document.getElementById('directorAuthorityBadge');
  if (badge) {
    badge.style.display = found ? 'block' : 'none';
    if (found) badge.textContent = `👑 القيادة لمدير المشروع «${found.director.name}» داخل المجموعة — عُطّلت أدوات نموذج المحادثة حتى لا تتنازع السلطة، والمدير يقود بنموذجه وتفكيره وتوجيهه. إن عطّلت المدير من قائمة الوكلاء عادت القيادة لنموذج المحادثة وتوجيهك.`;
  }
}

function editAgentFromChat(groupId, agentId) {
  // نافذة واحدة مضبوطة لتعديل الوكيل أينما ضُغط «تعديل»: نافذة تبويب
  // الوكلاء الأساسية بمنتقي نماذجها ونطاق كتبها، لا نافذة موازية للمحادثة.
  if (typeof window.openAgentEditorForGroup === 'function') {
    window.openAgentEditorForGroup(groupId, agentId);
  } else if (typeof showToast === 'function') {
    showToast('تعذر فتح محرر الوكيل');
  }
}

// =============================================================================
// 🗣️ جلسة مناقشة الباحث مع مدير المشروع حول بحث مغلق: حوار واستكمال للنواقص
// بلا بحث جديد من الصفر؛ المدير يطلب وكلاء بعينهم عند الحاجة، وعند الإقفال
// يعيد الصياغة النهائية من المحادثة المحفوظة، وتُستأنف الجلسة متى شاء الباحث.
// =============================================================================
function discussionState(sid) {
  try { return localStorage.getItem('almojtahed_discussion_' + sid) || ''; } catch (e) { return ''; }
}
function setDiscussionState(sid, v) {
  try {
    if (v) localStorage.setItem('almojtahed_discussion_' + sid, v);
    else localStorage.removeItem('almojtahed_discussion_' + sid);
  } catch (e) { }
  refreshDiscussionBar();
}
function refreshDiscussionBar() {
  const bar = document.getElementById('discussionBar');
  if (!bar) return;
  const open = (typeof activeSessionId !== 'undefined') && discussionState(activeSessionId) === 'open';
  bar.style.display = open ? 'block' : 'none';
}
function openDiscussion(idx) {
  if (typeof activeSessionId === 'undefined' || !activeSessionId) return;
  setDiscussionState(activeSessionId, 'open');
  if (typeof notifyDownload === 'function') { /* لا تنبيه تنزيل هنا */ }
  if (typeof showToast === 'function') showToast('🗣️ فُتحت جلسة المناقشة مع مدير المشروع: اكتب سؤالك أو النقص المطلوب استكماله في صندوق الرسائل', 3500);
  const input = document.getElementById('chatInputText');
  if (input) { input.focus(); input.placeholder = 'ناقش مدير المشروع: ما النقص؟ ما الذي تريد التحقق منه أو استكماله؟'; }
  if (typeof scrollToBottom === 'function') scrollToBottom();
}
function closeDiscussion() {
  if (typeof activeSessionId === 'undefined' || !activeSessionId) return;
  setDiscussionState(activeSessionId, '');
  const input = document.getElementById('chatInputText');
  if (input) input.placeholder = 'اسأل المجتهد في الفقه، الأصول، الحديث، أو ناقش نصوص المسائل...';
  if (typeof showToast === 'function') showToast('أُنهيت المناقشة مؤقتًا؛ محادثتها محفوظة وتستطيع استئنافها بزر «مناقشة المدير» متى شئت', 3000);
}
// 📋 زر الباحث المختصر: يجلب ثغرات تقرير البحث وفجواته من سجل القياس
// مرقمةً واحدة تلو الأخرى، ويرفعها إلى مدير المشروع دفعة واحدة في رسالة
// واحدة ليعالجها معه في جلسة المناقشة بندًا بندًا.
async function sendAuditGapsToDirector() {
  const session = (typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null;
  if (!session) return;
  let entry = null;
  try {
    const res = await fetch('/api/research-metrics');
    if (res.ok) {
      const data = await res.json();
      const mine = (data.items || []).filter(it => it.chat_id === activeSessionId);
      entry = mine.length ? mine[mine.length - 1] : null;
    }
  } catch (e) { }
  if (!entry) {
    if (typeof showToast === 'function') showToast('لا يوجد تقرير بحث آلي محفوظ لهذه المحادثة بعد — الثغرات تُجلب من تقارير البحوث المنفذة بالوكلاء', 3500);
    return;
  }
  if (discussionState(activeSessionId) !== 'open') setDiscussionState(activeSessionId, 'open');
  const a = entry.audit || {};
  const items = [];
  (entry.agents_failed || []).forEach(n => items.push(`وكيل سقط في البحث الأصلي: «${n}» — ما أثر سقوطه في مادته وكيف يُستكمل؟`));
  (entry.audit_failures || []).forEach(f => items.push(`نقل لم يثبت آليًا في كتاب إحالته: «${(f.quote || '').slice(0, 140)}» — تحقق منه بتقليب صفحته أو استبدل به ثابتًا موثقًا.`));
  if (a.ijma_unattributed) items.push(`دعاوى اتفاق/إجماع مطلقة بلا نسبة: ${a.ijma_unattributed} — انسبها إلى قائلها أو كتاب إجماعها أو خففها إلى «الجمهور».`);
  if (a.unverified) items.push(`نقول فُحصت ولم تثبت آليًا: ${a.unverified} من ${a.checked || 0} مفحوصًا — راجع مواضعها قبل الاعتماد.`);
  if (a.relocated) items.push(`نقول ثابتة في غير موضع إحالتها: ${a.relocated} — صحح إحالاتها إلى مواضعها الصحيحة.`);
  if (a.tier_warnings) items.push(`تنبيهات طبقة اعتماد (وسيط أو ناقل وحيد): ${a.tier_warnings} — لا يبقى متن حديث أو قول مذهب أو إجماع معلقًا بوسيط أو شرح معاصر أو شرح ناقل (كمغلطاي عن أبي داود وسعيد بن منصور) وحده؛ ائتِ بأصله التراثي مباشرة أو صرّح بالواسطة.`);
  if ((a.missing_terms || []).length) items.push(`ألفاظ متقدمين موثقة في المكتبة غابت عن متن الإجابة: ${a.missing_terms.map(t => '«' + t + '»').join('، ')} — ابحث عما وراءها من نصوص صريحة في كتب الطبقات (فقد يكون وراء اللفظ نص في عين المسألة كنص المرداوي في تقبيل الفرج) وائتِ بها أو صرّح بخلوّها بعد الفحص.`);
  const zeroLines = (entry.audit_record || '').split('\n').filter(l => l.includes('صفرية'));
  zeroLines.forEach(l => items.push(`خلية صفرية موثقة في تغطية الطبقات: ${l.replace(/^.*?—/, '').trim().slice(0, 220)}`));
  if (!items.length) items.push('لا ثغرات مسجلة في التقرير الآلي؛ راجع معي مع ذلك مواضع العزو بالواسطة من الشروح المعاصرة والموسوعات، وأي نقل تشك في طبقة سنده.');
  items.push('قاعدة طبقات صارمة لهذه الجلسة: لا تعتمد عزوًا بالواسطة من شرح معاصر أو موسوعة أو تفريغ دروس (كالعباد والهرري والهيميد والبسام) سندًا لمتن حديث أو حكم مذهب أو دعوى إجماع؛ ائتِ بالنص من أصله التراثي مباشرة بتقليب صفحته أو بطلب وكيله، وإلا صرّح بخلوّه.');
  const body = 'هذه ملحوظات تقرير البحث الآلي وثغراته، أرفعها إليك دفعة واحدة. عالجها معي واحدة تلو الأخرى بالترتيب، ولكل بند: ما ستفعله، وهل تحتاج طلب وكيل أو تقليب صفحة، وما سيتغير في الصياغة النهائية بسببه:\n\n'
    + items.map((t, i) => `${i + 1}- ${t}`).join('\n');
  session.messages.push({ role: 'user', content: body });
  renderSessionMessages(activeSessionId);
  if (typeof saveChatSessions === 'function') saveChatSessions();
  await triggerChatCompletion(session, [], { discussionMode: 'open' });
}

// 🏛 زر الضبط في المناقشة: سجل مخاطر هذا البحث من حزمته المحفوظة مقطعًا
// تشيك ليست (عالية 🔴 في الأعلى، متوسطة 🟡، منخفضة ⚪)؛ يعلّم الباحث ما
// يشاء فيصل مديرَ المشروع بتوجيه محاسبة رقابي يُبنى خادميًا ولا يرى
// الباحث صياغته، ثم يتحقق مسؤول المخاطر من إغلاق البنود في السجل.
async function toggleRiskControlPanel() {
  const panel = document.getElementById('riskControlPanel');
  if (!panel) return;
  if (panel.style.display !== 'none') { panel.style.display = 'none'; return; }
  panel.style.display = 'block';
  panel.innerHTML = '<div style="padding:4px;">جارٍ جلب سجل المخاطر من حزمة البحث المحفوظة…</div>';
  let pkg = null;
  try {
    const res = await fetch('/api/research-package/' + encodeURIComponent(activeSessionId));
    if (res.ok) pkg = await res.json();
  } catch (e) { }
  if (!pkg || !pkg.found) {
    panel.innerHTML = '<div style="padding:4px;">لا حزمة مخاطر محفوظة لهذه المحادثة — سجلات المخاطر تُحفظ للبحوث المنفذة من إصدار 1.10.284 فصاعدًا.</div>';
    return;
  }
  const esc = s => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const events = pkg.risk_events || [];
  const dots = { 'عالية': '#dc2626', 'متوسطة': '#d9a400', 'منخفضة': '#9ca3af' };
  let h = '<div style="font-weight:700;">🏛 سجل مخاطر هذا البحث — علّم ما تريد معالجته فورًا'
    + (pkg.risk_verdict ? ' · الحكم العام: ' + esc(pkg.risk_verdict) : '')
    + (pkg.risk_officer ? ' · مسؤول المخاطر: ' + esc(pkg.risk_officer) : '') + '</div>';
  h += '<div style="font-size:11.5px; opacity:.85;">المذكرة الكاملة في زر «📏 تقرير البحث» أسفل الجواب. البنود المعلّمة تصل مدير المشروع بتوجيه إدارة المخاطر: يعالجها من حزمة البحث المحفوظة أو يطلب الوكيل المعني بسدّها مع إشعاره أن الخطر لُوحظ عليه، ويُحاسَب المتسبب، ثم يتحقق مسؤول المخاطر من الإغلاق في هذا السجل.</div>';
  if (!events.length) h += '<div style="padding:4px;">لا أحداث مخاطر مسجلة في هذا البحث ضمن الحدود المعتمدة.</div>';
  ['عالية', 'متوسطة', 'منخفضة'].forEach(cls => {
    const rows = events.map((e, i) => [e, i]).filter(([e]) => e.cls === cls);
    if (!rows.length) return;
    h += `<div style="margin:9px 0 4px; font-weight:700;"><span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${dots[cls]}; margin-left:5px;"></span>${cls === 'عالية' ? '⚠️ ' : ''}مخاطر ${cls} (${rows.length})</div>`;
    rows.forEach(([e, i]) => {
      const st = e.status || '';
      const done = st.startsWith('مُغلق') || st.startsWith('عولج آليًا') || st.startsWith('موثق بقرار');
      h += `<label style="display:flex; gap:8px; align-items:flex-start; padding:6px 8px; border:1px solid rgba(150,130,90,.3); border-radius:8px; margin-bottom:5px; ${done ? 'opacity:.6;' : ''}">
        <input type="checkbox" class="risk-item-check" value="${i}" ${done ? 'disabled' : ''} style="margin-top:5px;">
        <span style="flex:1;"><b>${esc(e.title)}</b><br><small>${esc(e.evidence)}</small><br><small>الحالة: ${esc(st || 'مفتوح')}${done ? ' — لا معالجة مطلوبة' : ''}</small></span></label>`;
    });
  });
  if (events.length) h += '<div style="margin-top:8px;"><button type="button" class="btn-msg-export" onclick="sendRiskControlItems()">📨 إرسال البنود المعلّمة إلى مدير المشروع للمعالجة الفورية</button></div>';
  panel.innerHTML = h;
}

async function sendRiskControlItems() {
  const checks = Array.from(document.querySelectorAll('.risk-item-check:checked')).map(c => parseInt(c.value, 10));
  if (!checks.length) { if (typeof showToast === 'function') showToast('علّم بندًا واحدًا على الأقل من سجل المخاطر أولًا', 3000); return; }
  const session = (typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null;
  if (!session) return;
  if (discussionState(activeSessionId) !== 'open') setDiscussionState(activeSessionId, 'open');
  session.messages.push({ role: 'user', content: '🏛 أرسلتُ ' + checks.length + ' بندًا من بنود سجل مخاطر هذا البحث إلى مدير المشروع للمعالجة الفورية ومحاسبة المتسبب فيها، على أن يعالجها من حزمة البحث المحفوظة أو يطلب الوكيل المعني بسدّ ما قصّر فيه.' });
  const panel = document.getElementById('riskControlPanel');
  if (panel) panel.style.display = 'none';
  renderSessionMessages(activeSessionId);
  if (typeof saveChatSessions === 'function') saveChatSessions();
  await triggerChatCompletion(session, [], { discussionMode: 'open', riskControl: checks });
  if (typeof showToast === 'function') showToast('أُرسلت بنود الضبط؛ بعد رد المدير يتحقق مسؤول المخاطر من إغلاقها — أعد فتح «الضبط» لترى حالتها', 4500);
}

async function finalizeDiscussion() {
  const session = (typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null;
  if (!session) return;
  if (discussionState(activeSessionId) !== 'open') return;
  session.messages.push({
    role: 'user',
    content: '🔒 أقفل جلسة المناقشة باتفاقنا: أعد صياغة البحث كاملًا صياغة نهائية معتمدة مستوعبًا ما اتفقنا عليه في هذه المناقشة وتقارير الوكلاء المستكملة، ومعالجًا نواقص سجل التدقيق، ورقةً علمية محكمة بلا أي لغة من لغات عملية البحث والمناقشة.'
  });
  setDiscussionState(activeSessionId, 'closed');
  const input = document.getElementById('chatInputText');
  if (input) input.placeholder = 'اسأل المجتهد في الفقه، الأصول، الحديث، أو ناقش نصوص المسائل...';
  renderSessionMessages(activeSessionId);
  if (typeof saveChatSessions === 'function') saveChatSessions();
  await triggerChatCompletion(session, [], { discussionMode: 'finalize' });
  if (typeof showToast === 'function') showToast('🔒 أُقفلت المناقشة وصيغت الصياغة النهائية؛ وتستطيع فتح مناقشة جديدة عليها بزر «مناقشة المدير»', 3500);
}

// =============================================================================
// 🔭 بحث مفلتر داخل نص الإجابة نفسها: عدّادات (مرات الورود، كلمات العبارة،
// الجمل الحاوية)، وتظليل تلقائي لكل موضع، وقائمة جمل مفلترة يقفز منها
// الباحث إلى الموضع بعينه، مع تنقل سابق/تالٍ بين المواضع.
// =============================================================================
let _answerSearch = { idx: null, marks: [], current: -1 };

function _ansNormChar(ch) {
  if (/[\u064B-\u0652\u0670\u0640]/.test(ch)) return '';
  if ('إأآٱ'.includes(ch)) return 'ا';
  if (ch === 'ى') return 'ي';
  if (ch === 'ة') return 'ه';
  if (ch === 'ؤ') return 'و';
  if (ch === 'ئ') return 'ي';
  return ch;
}
function _ansNormalize(s) { return (s || '').split('').map(_ansNormChar).join(''); }

function _ensureAnswerSearchModal() {
  if (document.getElementById('answerSearchModal')) return;
  const st = document.createElement('style');
  st.textContent = 'mark.ans-hit{background:#ffe58a;color:inherit;padding:0 1px;border-radius:3px;} mark.ans-hit.ans-current{background:#ff9d45;outline:2px solid #e07b1f;}';
  document.head.appendChild(st);
  const d = document.createElement('div');
  d.id = 'answerSearchModal';
  d.style.cssText = 'display:none;position:fixed;inset:0;z-index:9999;background:transparent;direction:rtl;pointer-events:none;';
  d.innerHTML = `
    <div id="answerSearchPanel" style="pointer-events:auto;position:absolute;top:7vh;left:50%;transform:translateX(-50%);width:min(640px,94vw);background:var(--bg-surface,#fff);border-radius:14px;box-shadow:0 18px 50px rgba(0,0,0,0.35);padding:16px 18px;max-height:84vh;display:flex;flex-direction:column;">
      <div id="answerSearchDragHandle" title="اسحب من هذا الشريط لتحريك النافذة ومشاهدة التظليل في الإجابة" style="display:flex;justify-content:space-between;align-items:center;gap:10px;cursor:move;touch-action:none;user-select:none;-webkit-user-select:none;">
        <strong style="font-size:15px;">🔭 بحث في نص الإجابة <span style="font-size:11px;opacity:0.65;font-weight:400;">(قابلة للسحب ⠿)</span></strong>
        <button type="button" class="btn-msg-export" onclick="closeAnswerSearch()">إغلاق ✕</button>
      </div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;">
        <input id="answerSearchInput" type="text" placeholder="اكتب حرفًا أو كلمة أو جملة للبحث داخل هذه الإجابة..." style="flex:1;min-width:220px;padding:9px 12px;border:1px solid var(--border-subtle,#ccc);border-radius:9px;font-size:14px;" oninput="runAnswerSearch()" onkeydown="if(event.key==='Enter'){event.preventDefault();stepAnswerSearch(1);}">
        <button type="button" class="btn-msg-export" onclick="stepAnswerSearch(-1)">▲ السابق</button>
        <button type="button" class="btn-msg-export" onclick="stepAnswerSearch(1)">▼ التالي</button>
      </div>
      <label style="margin-top:8px;font-size:12.5px;display:flex;gap:6px;align-items:center;cursor:pointer;">
        <input id="answerSearchFlex" type="checkbox" checked onchange="runAnswerSearch()">
        بحث مرن: تجاهل التشكيل والهمزات والألف المقصورة والتاء المربوطة
      </label>
      <div id="answerSearchStats" style="margin-top:9px;font-size:13px;line-height:1.9;color:var(--accent-gold,#9a6b1f);background:rgba(184,115,51,0.07);border:1px solid var(--border-subtle,#e2d8c3);border-radius:9px;padding:7px 11px;">اكتب عبارة البحث وستُظلَّل مواضعها في الإجابة تلقائيًا مع عدّاداتها هنا.</div>
      <div id="answerSearchResults" style="margin-top:10px;overflow-y:auto;display:flex;flex-direction:column;gap:6px;"></div>
    </div>`;
  document.body.appendChild(d);
  // سحب النافذة من شريط رأسها (ماوس ولمس) لتبقى الإجابة وتظليلاتها مرئية
  const panel = d.querySelector('#answerSearchPanel');
  const handle = d.querySelector('#answerSearchDragHandle');
  if (panel && handle) {
    handle.addEventListener('pointerdown', (e) => {
      if (e.target.closest('button')) return;
      const rect = panel.getBoundingClientRect();
      panel.style.left = rect.left + 'px';
      panel.style.top = rect.top + 'px';
      panel.style.transform = 'none';
      const offX = e.clientX - rect.left, offY = e.clientY - rect.top;
      handle.setPointerCapture(e.pointerId);
      const move = (ev) => {
        const w = panel.offsetWidth, h = panel.offsetHeight;
        let x = ev.clientX - offX, y = ev.clientY - offY;
        x = Math.max(-w + 90, Math.min(x, window.innerWidth - 90));
        y = Math.max(0, Math.min(y, window.innerHeight - 44));
        panel.style.left = x + 'px';
        panel.style.top = y + 'px';
      };
      const up = () => {
        handle.removeEventListener('pointermove', move);
        handle.removeEventListener('pointerup', up);
        handle.removeEventListener('pointercancel', up);
      };
      handle.addEventListener('pointermove', move);
      handle.addEventListener('pointerup', up);
      handle.addEventListener('pointercancel', up);
    });
  }
}

function openAnswerSearch(idx) {
  _ensureAnswerSearchModal();
  _clearAnswerHighlights();
  _answerSearch = { idx: idx, marks: [], current: -1 };
  const m = document.getElementById('answerSearchModal');
  m.style.display = 'block';
  const inp = document.getElementById('answerSearchInput');
  if (inp) { inp.focus(); if (inp.value.trim().length >= 2) runAnswerSearch(); }
}
function closeAnswerSearch() {
  _clearAnswerHighlights();
  const m = document.getElementById('answerSearchModal');
  if (m) m.style.display = 'none';
  _answerSearch = { idx: null, marks: [], current: -1 };
}
function _clearAnswerHighlights() {
  document.querySelectorAll('mark.ans-hit').forEach(mk => {
    const parent = mk.parentNode;
    if (parent) { parent.replaceChild(document.createTextNode(mk.textContent), mk); parent.normalize(); }
  });
  _answerSearch.marks = []; _answerSearch.current = -1;
}
function _answerContentEl() {
  const bubble = document.getElementById('chatMsg' + _answerSearch.idx);
  return bubble ? bubble.querySelector('.message-content') : null;
}
function runAnswerSearch() {
  _clearAnswerHighlights();
  const stats = document.getElementById('answerSearchStats');
  const results = document.getElementById('answerSearchResults');
  const q = (document.getElementById('answerSearchInput')?.value || '').trim();
  const flex = !!document.getElementById('answerSearchFlex')?.checked;
  if (results) results.innerHTML = '';
  if (!q || q.length < 2) { if (stats) stats.textContent = 'اكتب حرفين على الأقل للبحث داخل هذه الإجابة.'; return; }
  const content = _answerContentEl();
  if (!content) { if (stats) stats.textContent = 'تعذر العثور على نص الإجابة.'; return; }

  // جمع العقد النصية (عدا أزرار الإجراءات) ثم تظليل كل مواضع العبارة فيها
  const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      if (node.parentElement && node.parentElement.closest('.chat-msg-actions-bar, .chat-user-msg-actions-bar, button')) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const nq = flex ? _ansNormalize(q) : q;
  let total = 0;
  for (const node of nodes) {
    const text = node.nodeValue;
    let hay = text, map = null;
    if (flex) {
      hay = ''; map = [];
      for (let i = 0; i < text.length; i++) { const nc = _ansNormChar(text[i]); if (nc) { hay += nc; map.push(i); } }
    }
    const spans = [];
    let pos = 0;
    while (true) {
      const hit = hay.indexOf(nq, pos);
      if (hit < 0) break;
      const s = flex ? map[hit] : hit;
      const e = flex ? (map[hit + nq.length - 1] + 1) : (hit + nq.length);
      spans.push([s, e]); total++;
      pos = hit + Math.max(nq.length, 1);
    }
    if (!spans.length) continue;
    const frag = document.createDocumentFragment();
    let last = 0;
    for (const [s, e] of spans) {
      if (s > last) frag.appendChild(document.createTextNode(text.slice(last, s)));
      const mk = document.createElement('mark');
      mk.className = 'ans-hit'; mk.textContent = text.slice(s, e);
      frag.appendChild(mk);
      last = e;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
  }
  _answerSearch.marks = Array.from(content.querySelectorAll('mark.ans-hit'));

  // عدّادات: مرات الورود، حروف العبارة وكلماتها، والجمل الحاوية لها
  const plain = content.textContent || '';
  const np = flex ? _ansNormalize(plain) : plain;
  const sentences = plain.split(/(?<=[.!؟؛:])\s+|\n+/).map(s => s.trim()).filter(Boolean);
  let sentHits = [], markCursor = 0;
  for (const s of sentences) {
    const ns = flex ? _ansNormalize(s) : s;
    let c = 0, p = 0;
    while (true) { const h = ns.indexOf(nq, p); if (h < 0) break; c++; p = h + Math.max(nq.length, 1); }
    if (c) { sentHits.push({ sentence: s, count: c, firstMark: markCursor }); markCursor += c; }
  }
  const wordsCount = q.split(/\s+/).filter(Boolean).length;
  if (stats) {
    stats.innerHTML = total
      ? `وُجدت العبارة <strong>${total}</strong> مرة في هذه الإجابة | عبارة البحث: ${q.length} حرفًا و${wordsCount} ${wordsCount === 1 ? 'كلمة' : 'كلمات'} | وردت في <strong>${sentHits.length}</strong> جملة | تنقّل بالسابق/التالي أو اضغط أي جملة للقفز إلى موضعها.`
      : 'لا مواضع لهذه العبارة في نص الإجابة. جرّب البحث المرن أو عبارة أقصر.';
  }
  if (results && sentHits.length) {
    results.innerHTML = sentHits.slice(0, 40).map((h, i) =>
      `<button type="button" onclick="jumpToAnswerMark(${h.firstMark})" style="text-align:right;padding:8px 11px;border:1px solid var(--border-subtle,#ddd);border-radius:9px;background:transparent;cursor:pointer;font-size:12.5px;line-height:1.8;">
         <span style="color:var(--accent-gold,#9a6b1f);font-weight:700;">${i + 1}.</span> ${escapeHtml(h.sentence.slice(0, 220))}${h.sentence.length > 220 ? '…' : ''} <span style="opacity:0.7;">(${h.count}×)</span>
       </button>`).join('');
  }
  if (_answerSearch.marks.length) jumpToAnswerMark(0);
}
function jumpToAnswerMark(i) {
  const marks = _answerSearch.marks;
  if (!marks.length) return;
  _answerSearch.current = ((i % marks.length) + marks.length) % marks.length;
  marks.forEach((mk, j) => mk.classList.toggle('ans-current', j === _answerSearch.current));
  marks[_answerSearch.current].scrollIntoView({ behavior: 'smooth', block: 'center' });
  const stats = document.getElementById('answerSearchStats');
  if (stats && marks.length) stats.innerHTML = stats.innerHTML.replace(/\| الموضع الحالي:.*$/, '') + ` | الموضع الحالي: ${_answerSearch.current + 1} من ${marks.length}`;
}
function stepAnswerSearch(dir) { jumpToAnswerMark((_answerSearch.current < 0 ? 0 : _answerSearch.current) + dir); }

async function downloadChatResearchReport(idx) {
  const session = (typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null;
  const msg = session && session.messages ? session.messages[idx] : null;
  let entry = null;
  try {
    const res = await fetch('/api/research-metrics');
    if (res.ok) {
      const data = await res.json();
      const mine = (data.items || []).filter(it => it.chat_id === activeSessionId);
      entry = mine.length ? mine[mine.length - 1] : null;
    }
  } catch (e) { }
  const L = [];
  L.push('تقرير بحث — المجتهد');
  L.push('====================');
  L.push('');
  if (entry) {
    const a = entry.audit || {};
    const ratio = a.checked ? Math.round(100 * ((a.verified || 0) + (a.relocated || 0)) / a.checked) : null;
    const failed = entry.agents_failed || [];
    const disabled = entry.agents_disabled || [];
    let verdict = 'قوي';
    if (failed.length >= 3 || (ratio !== null && ratio < 50)) verdict = 'ضعيف — يعاد توليده ولا يعتمد مرجعًا';
    else if (failed.length === 2 || (ratio !== null && ratio < 65) || (a.ijma_unattributed || 0) > 0) verdict = 'مقبول بتنبيه — يعتمد مسودة وتحرر مواضعه المنبهة';
    L.push(`البحث: ${entry.question || '—'}`);
    L.push(`التاريخ: ${entry.ts || '—'} · المجموعة: ${entry.group || '—'} · نموذج المدير: ${entry.manager_model || '—'}`);
    L.push(`المدة: ${entry.duration_s ? Math.round(entry.duration_s / 60 * 10) / 10 + ' دقيقة' : '—'} · حروف الجواب: ${entry.answer_chars ?? '—'} · الشواهد: ${entry.witnesses ?? '—'}`);
    L.push('');
    L.push('الحكم العام: ' + verdict);
    L.push('');
    L.push('أولًا: اكتمال الفريق');
    L.push(`الوكلاء المرسلون: ${entry.agents_total ?? '—'} · الساقطون تقنيًا: ${failed.length}${failed.length ? ' (' + failed.join('، ') + ')' : ''} · المعطّلون بقرار المستخدم: ${disabled.length}${disabled.length ? ' (' + disabled.join('، ') + ')' : ''}`);
    if (failed.length) L.push('الساقطون بُنيت أقسامهم على بطاقات شواهدهم وبطاقات الخلاف والمقارنة، والبديل العملي لكل منهم في تقرير هذا البحث من سجل القياس بإحصائيات المجتهد.');
    if (disabled.length) L.push('المعطّلون قرارك أنت: لم يُطلب منهم شيء ولم يُعوّض دورهم، والبحث مبني على النطاق المقلّص بقرارك.');
    L.push('');
    L.push('ثانيًا: مؤشرات التدقيق التوثيقي');
    L.push(`مفحوص: ${a.checked ?? '—'} · مربوط بحواشيه: ${a.linked ?? '—'} · ثابت: ${a.verified ?? '—'} · في غير موضعه: ${a.relocated ?? '—'} · غير ثابت آليًا: ${a.unverified ?? '—'} · نسبة الثبوت: ${ratio !== null ? ratio + '٪' : '—'} (عتبة الاعتماد ٦٥٪) · تنبيهات وسيط وحيد: ${a.tier_warnings ?? 0} · دعاوى إجماع: ${a.ijma_flags ?? 0} · اتفاق مطلق بلا نسبة: ${a.ijma_unattributed ?? 0}`);
    if ((entry.audit_failures || []).length) {
      L.push('');
      L.push('مواضع منبّهة من التدقيق (للمراجعة البشرية):');
      entry.audit_failures.slice(0, 12).forEach(f => L.push(`- «${(f.quote || '').slice(0, 90)}» — ${f.reason || ''}`));
    }
    if (entry.risk_memo) {
      L.push('');
      L.push('ثالثًا: 🏛 مذكرة إدارة المخاطر إلى صاحب البحث (مسؤول المخاطر: ' + (entry.risk_officer || '—') + (entry.risk_verdict ? ' · الحكم: ' + entry.risk_verdict : '') + ')');
      L.push('--------------------------------------------------');
      L.push(entry.risk_memo.replace(/\*\*/g, ''));
      if ((entry.excluded_items || []).length) {
        L.push('');
        L.push('النقول المستبعدة لخارجها عن المكتبة (قاعدة: لا نقل من خارجها):');
        entry.excluded_items.slice(0, 26).forEach(x => L.push('- «' + (x.quote || '').slice(0, 110) + '»'));
      }
    }
    if (entry.audit_record) {
      L.push('');
      L.push((entry.risk_memo ? 'رابعًا' : 'ثالثًا') + ': سجل التدقيق الآلي الكامل (كما خرج من المنظومة)');
      L.push('--------------------------------------------------');
      L.push(entry.audit_record.replace(/\*\*/g, ''));
    }
  } else {
    L.push('لا سجل قياس محفوظ لهذه الإجابة: إما أنها أُنجزت قبل نظام التقرير المنفصل، أو أنها ليست بحث وكلاء موثقًا.');
    if (msg) {
      L.push(`النموذج: ${msg.model || '—'} · المجموعة: ${msg.agent_group || '—'} · زمن الإجابة: ${msg.duration_ms ? Math.round(msg.duration_ms / 1000) + ' ثانية' : '—'} · الشواهد: ${(msg.witnesses || []).length}`);
    }
    L.push('لبحوثك القادمة: يخرج هذا الزر تقريرًا كاملًا بمؤشرات التدقيق وتنبيهات الفريق والنطاق.');
  }
  L.push('');
  L.push('تنبيه: التقرير بوصلة تنبيه من مؤشرات آلية، لا بديل عن قراءة متن البحث.');
  const blob = new Blob(['\ufeff' + L.join('\n')], { type: 'text/plain;charset=utf-8' });
  const dl = document.createElement('a');
  dl.href = URL.createObjectURL(blob);
  dl.download = 'تقرير-بحث-' + (activeSessionId || 'chat') + '.txt';
  dl.click();
  URL.revokeObjectURL(dl.href);
}

function buildChatAgentGroupPayload() {
  const useAgentGroup = document.getElementById('chatUseAgentGroupCheckbox')?.checked;
  if (!useAgentGroup) return null;
  const groups = readChatAgentGroups();
  const chosen = groups.filter(g => readSelectedChatGroupIds(groups).includes(g.id));
  const bundles = [];
  chosen.forEach(grp => {
    agentsChosenInGroup(grp).forEach(agent => bundles.push({ group: grp, agent }));
  });
  if (!bundles.length) return null;
  const activeAgent = bundles[0].agent;
  const isMulti = bundles.length > 1;
  const names = bundles.map(b => b.agent.name).join(' + ');
  const booksSet = new Set();
  bundles.forEach(({ agent }) => {
    const bList = (agent.booksScope && Array.isArray(agent.booksScope)) ? agent.booksScope : (agent.scopeBooks || agent.books || []);
    bList.forEach(b => { if (b && String(b).trim()) booksSet.add(String(b).trim()); });
  });
  const agentBooks = Array.from(booksSet);
  const groupName = chosen.length === 1 ? chosen[0].name : chosen.map(g => g.name).join(' + ');
  const unifiedSystemPrompt = isMulti
    ? bundles.map(b => `### اختصاص وتوجيه الوكيل «${b.agent.name}» من مجموعة «${b.group.name}»:\n${b.agent.systemPrompt || b.agent.desc || ''}`).join('\n\n')
    : (activeAgent.systemPrompt || '');
  return {
    activeAgent,
    payload: {
      id: chosen.map(g => g.id).join(','),
      name: groupName,
      desc: chosen.map(g => g.desc || '').filter(Boolean).join(' \n'),
      active_agent: {
        id: activeAgent.id,
        name: isMulti ? `فريق الوكلاء المختارين (${bundles.length}): ${names}` : activeAgent.name,
        desc: isMulti ? bundles.map(b => `[${b.group.name} / ${b.agent.name}]: ${b.agent.desc || ''}`).join(' | ') : (activeAgent.desc || ''),
        model: activeAgent.model || 'google/gemini-2.5-flash',
        thinking: activeAgent.thinking || 'medium',
        system_prompt: unifiedSystemPrompt,
        books: agentBooks,
        pool_size: parseInt(activeAgent.poolSize) || 250,
        top_k: parseInt(activeAgent.topK || activeAgent.top_k || activeAgent.topRerank) || 40,
        temp: activeAgent.temp !== undefined ? activeAgent.temp : 0.2
      },
      disabled_agents: chosen.flatMap(grp => {
        const chosenIds = new Set(agentsChosenInGroup(grp).map(a => a.id));
        return (grp.agents || [])
          .filter(a => a && a.kind !== 'mcp' && !chosenIds.has(a.id))
          .map(a => ({ name: a.name, desc: a.desc || '' }));
      }),
      agents: bundles.map(({ group, agent }) => {
        const booksList = (agent.booksScope && Array.isArray(agent.booksScope)) ? agent.booksScope : (agent.scopeBooks || agent.books || []);
        return {
          id: agent.id,
          name: agent.name,
          desc: chosen.length > 1 ? `[${group.name}] ${agent.desc || ''}` : (agent.desc || ''),
          system_prompt: agent.systemPrompt || agent.system_prompt || '',
          systemPrompt: agent.systemPrompt || agent.system_prompt || '',
          model: agent.model || 'google/gemini-2.5-flash',
          thinking: agent.thinking || 'medium',
          books: booksList,
          booksScope: booksList,
          is_director: !!(agent.is_director || agent.role === 'director' || agent.kind === 'director'),
          role: agent.role || '',
          kind: agent.kind || '',
          search_mode: agent.search_mode || ((agent.use_hybrid === false) ? 'semantic' : 'hybrid'),
          use_hybrid: agent.use_hybrid !== false,
          context_tokens: agent.context_tokens || agent.contextTokens || 1048576,
          extract_count: agent.extract_count || agent.topK || agent.top_k || 80,
          pool_size: parseInt(agent.poolSize) || 250,
          top_k: parseInt(agent.topK || agent.top_k || agent.topRerank) || 40,
          temp: agent.temp !== undefined ? agent.temp : 0.2,
          scope_summary: booksList.length > 0 ? `${booksList.length} كتاب محدد` : 'شامل المخزن التراثي'
        };
      })
    }
  };
}

function readChatMcps() {
  try {
    const raw = localStorage.getItem(ownerStorageKey('almojtahed_chat_mcps'));
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter(item => item && item.id && item.url) : [];
  } catch (e) {
    return [];
  }
}

function writeChatMcps(list) {
  localStorage.setItem(ownerStorageKey('almojtahed_chat_mcps'), JSON.stringify(list || []));
  renderChatMcpList();
  populateChatAgentGroupsDropdown();
}

function readSelectedChatMcpIds() {
  const valid = new Set(readChatMcps().map(item => item.id));
  try {
    const raw = localStorage.getItem('almojtahed_chat_selected_mcp_ids');
    const ids = raw ? JSON.parse(raw) : [];
    return Array.isArray(ids) ? ids.filter(id => valid.has(id)) : [];
  } catch (e) {
    return [];
  }
}

function writeSelectedChatMcpIds(ids) {
  const valid = new Set(readChatMcps().map(item => item.id));
  ids = (Array.isArray(ids) ? ids : []).filter(id => valid.has(id));
  localStorage.setItem('almojtahed_chat_selected_mcp_ids', JSON.stringify(ids));
  return ids;
}

function toolsChosenInMcp(mcp) {
  const tools = Array.isArray(mcp?.tools) ? mcp.tools : [];
  const raw = localStorage.getItem('almojtahed_chat_selected_mcp_tools_' + mcp.id);
  if (raw === null) return tools.slice();
  let names = [];
  try { names = JSON.parse(raw); } catch (e) { return tools.slice(); }
  if (!Array.isArray(names)) return tools.slice();
  return tools.filter(tool => names.includes(tool.name));
}

function updateChatSourceLabels() {
  const groups = readChatAgentGroups();
  const ids = readSelectedChatGroupIds(groups);
  const label = document.getElementById('chatGroupBtnLabel');
  if (label) {
    if (!groups.length) label.textContent = 'لا توجد مجموعات';
    else if (!ids.length) label.textContent = 'لم تُحدد أي مجموعة';
    else if (ids.length === 1) label.textContent = groups.find(group => group.id === ids[0])?.name || 'مجموعة';
    else label.textContent = `${ids.length} مجموعات`;
  }
  const badge = document.getElementById('chatGroupCountBadge');
  if (badge) badge.textContent = `تم تحديد ${ids.length} من أصل ${groups.length} مجموعات`;
}

function renderChatMcpList() {
  const box = document.getElementById('chatMcpList');
  if (!box) return;
  const list = readChatMcps();
  box.innerHTML = list.map(mcp => `
    <div class="chat-mcp-row">
      <span class="chat-mcp-row-name" title="${escapeHtml(mcp.url)}">${escapeHtml(mcp.name)} · ${(mcp.tools || []).length} فرع</span>
      <span class="chat-mcp-row-actions">
        <button type="button" data-mcp-refresh="${escapeHtml(mcp.id)}">تحديث</button>
        <button type="button" data-mcp-delete="${escapeHtml(mcp.id)}">حذف</button>
      </span>
    </div>`).join('');
}

async function addChatMcp(event) {
  event.preventDefault();
  const nameInput = document.getElementById('chatMcpNameInput');
  const urlInput = document.getElementById('chatMcpUrlInput');
  const button = document.getElementById('chatMcpAddBtn');
  const name = (nameInput?.value || '').trim();
  const url = (urlInput?.value || '').trim();
  if (!name || !url) {
    if (typeof showToast === 'function') showToast('اكتب اسم الخادم ورابطه', 2200);
    return;
  }
  if (button) button.disabled = true;
  try {
    const response = await fetch('/api/mcp/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await response.json();
    if (!response.ok || data.status === 'error') {
      if (typeof showToast === 'function') showToast(data.error || 'تعذر قراءة الخادم', 3500);
      return;
    }
    const list = readChatMcps().filter(item => item.url !== url);
    list.push({ id: 'mcp_' + Date.now(), name, url, tools: data.tools || [] });
    writeChatMcps(list);
    if (nameInput) nameInput.value = '';
    if (urlInput) urlInput.value = '';
    if (typeof showToast === 'function') showToast(`أضيف «${name}» وفيه ${(data.tools || []).length} فرع`, 2500);
  } catch (e) {
    if (typeof showToast === 'function') showToast('تعذر الاتصال بالخادم', 2500);
  } finally {
    if (button) button.disabled = false;
  }
}

async function refreshChatMcp(id) {
  const list = readChatMcps();
  const mcp = list.find(item => item.id === id);
  if (!mcp) return;
  try {
    const response = await fetch('/api/mcp/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: mcp.url })
    });
    const data = await response.json();
    if (data.status === 'error') {
      if (typeof showToast === 'function') showToast(data.error || 'تعذر التحديث', 3000);
      return;
    }
    mcp.tools = data.tools || [];
    writeChatMcps(list);
  } catch (e) {
    if (typeof showToast === 'function') showToast('تعذر تحديث الفروع', 2500);
  }
}

function deleteChatMcp(id) {
  const list = readChatMcps().filter(item => item.id !== id);
  localStorage.setItem(ownerStorageKey('almojtahed_chat_mcps'), JSON.stringify(list));
  writeSelectedChatMcpIds(readSelectedChatMcpIds().filter(item => item !== id));
  renderChatMcpList();
  populateChatAgentGroupsDropdown();
}

function toggleSingleChatMcp(mcpId, isChecked) {
  let ids = readSelectedChatMcpIds();
  if (isChecked) {
    if (!ids.includes(mcpId)) ids.push(mcpId);
  } else {
    ids = ids.filter(id => id !== mcpId);
  }
  writeSelectedChatMcpIds(ids);
  if (ids.length) {
    const checkbox = document.getElementById('chatUseAgentGroupCheckbox');
    const container = document.getElementById('chatAgentGroupPicker');
    if (checkbox) checkbox.checked = true;
    if (container) container.classList.add('active');
    localStorage.setItem('almojtahed_chat_use_agent_group', 'true');
  }
  document.querySelectorAll('#chatGroupChecklistItems input[data-mcp-id]').forEach(box => {
    const on = ids.includes(box.getAttribute('data-mcp-id'));
    box.checked = on;
    box.closest('.chat-checklist-item')?.classList.toggle('is-selected', on);
  });
  updateChatSourceLabels();
  populateSubAgentsDropdown();
}

function setMcpForAgents(checked) {
  localStorage.setItem('almojtahed_mcp_for_agents', checked ? '1' : '0');
}
window.setMcpForAgents = setMcpForAgents;

function syncMcpForAgentsCheckbox() {
  const box = document.getElementById('chatMcpForAgentsCheckbox');
  if (box) box.checked = localStorage.getItem('almojtahed_mcp_for_agents') === '1';
}
window.syncMcpForAgentsCheckbox = syncMcpForAgentsCheckbox;

function toggleChatMcpTool(el) {
  const mcpId = el.getAttribute('data-mcp-id');
  const toolName = el.getAttribute('data-tool-name');
  const mcp = readChatMcps().find(item => item.id === mcpId);
  if (!mcp) return;
  let names = toolsChosenInMcp(mcp).map(tool => tool.name);
  if (el.checked) {
    if (!names.includes(toolName)) names.push(toolName);
  } else {
    names = names.filter(name => name !== toolName);
  }
  localStorage.setItem('almojtahed_chat_selected_mcp_tools_' + mcpId, JSON.stringify(names));
  el.closest('.chat-checklist-item')?.classList.toggle('is-selected', el.checked);
  updateCombinedSubAgentsUI();
}

function buildChatMcpPayload() {
  const useSources = document.getElementById('chatUseAgentGroupCheckbox')?.checked;
  if (!useSources) return [];
  const groups = readChatAgentGroups();
  const selected = new Set(readSelectedChatGroupIds(groups));
  const servers = [];
  groups.filter(group => selected.has(group.id)).forEach(group => {
    (group.agents || []).filter(agent => agent.kind === 'mcp' && agent.enabled !== false && agent.url).forEach(agent => {
      const tools = toolsChosenInMcp(agent).map(tool => tool.name);
      if (tools.length) servers.push({ name: agent.name, url: agent.url, tools });
    });
  });
  return servers;
}

// تعبئة قائمة مجموعات الوكلاء في الشات، مع اختيار أكثر من مجموعة
function populateChatAgentGroupsDropdown() {
  const select = document.getElementById('chatAgentGroupSelect');
  const checkbox = document.getElementById('chatUseAgentGroupCheckbox');
  const container = document.getElementById('chatAgentGroupPicker');
  const items = document.getElementById('chatGroupChecklistItems');
  const groupBtn = document.getElementById('chatGroupDropdownBtn');
  if (!select) return;

  const groups = readChatAgentGroups();
  const wrap = document.getElementById('chatGroupSelectWrap');
  if (!groups.length) {
    select.innerHTML = '<option value="">لا توجد مجموعات</option>';
    if (checkbox) checkbox.checked = false;
    if (container) container.classList.remove('active');
    if (wrap) wrap.dataset.empty = '1';
    if (groupBtn) groupBtn.disabled = true;
    const label = document.getElementById('chatGroupBtnLabel');
    if (label) label.textContent = 'لا توجد مجموعات';
    if (items) items.innerHTML = '';
    populateSubAgentsDropdown();
    if (typeof renderCompareAgents === 'function') renderCompareAgents();
    return;
  }

  if (wrap) wrap.dataset.empty = '0';
  if (groupBtn) groupBtn.disabled = false;
  const savedEnabled = localStorage.getItem('almojtahed_chat_use_agent_group');
  const isEnabled = savedEnabled === null ? true : (savedEnabled === 'true');
  const ids = writeSelectedChatGroupIds(readSelectedChatGroupIds(groups));

  if (items) {
    items.innerHTML = groups.map(g => {
      const on = ids.includes(g.id);
      const agentCount = g.agents ? g.agents.length : 0;
      return `
        <div class="chat-checklist-item ${on ? 'is-selected' : ''}" onclick="handleChatGroupCheckItemClick(event, '${escapeHtml(g.id)}')">
          <input type="checkbox" class="chat-agent-item-checkbox" data-group-id="${escapeHtml(g.id)}" ${on ? 'checked' : ''} onclick="event.stopPropagation()" onchange="toggleSingleChatGroup('${escapeHtml(g.id)}', this.checked)">
          <div class="chat-agent-item-info">
            <div class="chat-agent-item-name">
              <span>${escapeHtml(g.name)}</span>
              <span class="chat-agent-scope-badge">${agentCount} وكلاء</span>
            </div>
            <div class="chat-agent-item-desc" title="${escapeHtml(g.desc || '')}">${escapeHtml(g.desc || 'مجموعة وكلاء مساعدين')}</div>
          </div>
        </div>`;
    }).join('');
  }

  if (checkbox) checkbox.checked = isEnabled && ids.length > 0;
  if (container) container.classList.toggle('active', !!(checkbox && checkbox.checked));
  populateSubAgentsDropdown();
  if (typeof renderCompareAgents === 'function') renderCompareAgents();
}

function handleChatGroupCheckItemClick(event, groupId) {
  const items = document.getElementById('chatGroupChecklistItems');
  const cb = items?.querySelector(`input[data-group-id="${groupId}"]`);
  if (!cb) return;
  toggleSingleChatGroup(groupId, !cb.checked);
}

function handleChatMcpCheckItemClick(event, mcpId) {
  const box = document.querySelector(`#chatGroupChecklistItems input[data-mcp-id="${mcpId}"]`);
  if (!box) return;
  toggleSingleChatMcp(mcpId, !box.checked);
}

function toggleSingleChatGroup(groupId, isChecked) {
  const groups = readChatAgentGroups();
  let ids = readSelectedChatGroupIds(groups);
  if (isChecked) {
    if (!ids.includes(groupId)) ids.push(groupId);
  } else {
    ids = ids.filter(id => id !== groupId);
  }
  ids = writeSelectedChatGroupIds(ids);
  const checkbox = document.getElementById('chatUseAgentGroupCheckbox');
  const container = document.getElementById('chatAgentGroupPicker');
  if (ids.length && checkbox) {
    checkbox.checked = true;
    if (container) container.classList.add('active');
    localStorage.setItem('almojtahed_chat_use_agent_group', 'true');
  }
  populateSubAgentsDropdown();
}

function selectAllChatGroups(selectAll) {
  const groups = readChatAgentGroups();
  const ids = writeSelectedChatGroupIds(selectAll ? groups.map(g => g.id) : []);
  const checkbox = document.getElementById('chatUseAgentGroupCheckbox');
  const container = document.getElementById('chatAgentGroupPicker');
  if (checkbox) {
    checkbox.checked = ids.length > 0;
    if (container) container.classList.toggle('active', checkbox.checked);
    if (checkbox.checked) localStorage.setItem('almojtahed_chat_use_agent_group', 'true');
  }
  populateChatAgentGroupsDropdown();
}

// تعبئة وإدارة القائمة المنسدلة للوكلاء مع دعم التشيك ليست وتحديد أكثر من وكيل
function populateSubAgentsDropdown(groupId) {
  const subWrap = document.getElementById('chatSubAgentSelectWrap');
  const itemsContainer = document.getElementById('chatSubAgentChecklistItems');
  const subSelect = document.getElementById('chatSubAgentSelect');
  if (!subWrap) return;
  syncMcpForAgentsCheckbox();

  const groups = readChatAgentGroups();
  if (groupId && groups.some(g => g.id === groupId)) {
    writeSelectedChatGroupIds([groupId]);
  }
  const chosen = groups.filter(g => readSelectedChatGroupIds(groups).includes(g.id) && g.agents && g.agents.length);
  const mcpChosen = [];
  chosen.forEach(group => {
    (group.agents || []).filter(agent => agent.kind === 'mcp' && agent.enabled !== false && (agent.tools || []).length)
      .forEach(agent => mcpChosen.push(agent));
  });
  if (!chosen.length && !mcpChosen.length) {
    subWrap.style.display = 'none';
    if (subSelect) subSelect.innerHTML = '<option value="">لا يوجد وكلاء</option>';
    return;
  }

  subWrap.style.display = 'inline-flex';
  let itemsHtml = '';
  chosen.forEach(group => {
    const selectedIds = agentsChosenInGroup(group).map(a => a.id);
    if (chosen.length > 1 || mcpChosen.length) {
      itemsHtml += `<div class="chat-checklist-group-label">${escapeHtml(group.name)}</div>`;
    }
    group.agents.forEach(a => {
      if (a.kind === 'mcp') return;
      const isChecked = selectedIds.includes(a.id);
      const scopeCount = (a.booksScope && a.booksScope.length) ? a.booksScope.length : ((a.books && a.books.length) ? a.books.length : 0);
      const scopeText = scopeCount > 0 ? `${scopeCount} كتب` : 'شامل التراث';
      itemsHtml += `
        <div class="chat-checklist-item ${isChecked ? 'is-selected' : ''}" onclick="handleSubAgentCheckItemClick(event, '${escapeHtml(a.id)}', '${escapeHtml(group.id)}')">
          <input type="checkbox" class="chat-agent-item-checkbox" data-agent-id="${escapeHtml(a.id)}" data-group-id="${escapeHtml(group.id)}" ${isChecked ? 'checked' : ''} onclick="event.stopPropagation()" onchange="toggleSingleSubAgent('${escapeHtml(a.id)}', this.checked, '${escapeHtml(group.id)}')">
          <div class="chat-agent-item-info">
            <div class="chat-agent-item-name">
              <span>${escapeHtml(a.name)}</span>
              <span class="chat-agent-scope-badge">${escapeHtml(scopeText)}</span>
            </div>
            <div class="chat-agent-item-desc" title="${escapeHtml(a.desc || '')}">${escapeHtml(a.desc || 'وكيل مساعد متخصص')}</div>
          </div>
          <button type="button" class="btn-secondary-action" style="font-size: 11px; padding: 4px 10px; white-space: nowrap;" onclick="event.stopPropagation(); editAgentFromChat('${escapeHtml(group.id)}', '${escapeHtml(a.id)}')" title="تعديل بطاقة هذا الوكيل في نافذة الوكلاء الأساسية: النموذج والتفكير والشواهد والكتب والتوجيه والقيادة">تعديل</button>
        </div>`;
    });
  });
  mcpChosen.forEach(mcp => {
    const selectedNames = toolsChosenInMcp(mcp).map(tool => tool.name);
    itemsHtml += `<div class="chat-checklist-group-label">${escapeHtml(mcp.name)}</div>`;
    (mcp.tools || []).forEach(tool => {
      const isChecked = selectedNames.includes(tool.name);
      itemsHtml += `
        <div class="chat-checklist-item ${isChecked ? 'is-selected' : ''}">
          <input type="checkbox" class="chat-agent-item-checkbox" data-mcp-id="${escapeHtml(mcp.id)}" data-tool-name="${escapeHtml(tool.name)}" ${isChecked ? 'checked' : ''} onchange="toggleChatMcpTool(this)">
          <div class="chat-agent-item-info">
            <div class="chat-agent-item-name"><span>${escapeHtml(tool.name)}</span></div>
            <div class="chat-agent-item-desc" title="${escapeHtml(tool.description || '')}">${escapeHtml(tool.description || 'فرع من خادم MCP')}</div>
          </div>
        </div>`;
    });
  });
  if (itemsContainer) itemsContainer.innerHTML = itemsHtml;
  updateCombinedSubAgentsUI(chosen);
}

function updateCombinedSubAgentsUI(chosen) {
  const groups = chosen || [];
  let total = 0;
  let count = 0;
  groups.forEach(group => {
    const agents = group.agents || [];
    total += agents.length;
    count += agentsChosenInGroup(group).length;
  });
  const mcpChosen = [];
  groups.forEach(group => {
    (group.agents || []).filter(agent => agent.kind === 'mcp' && agent.enabled !== false).forEach(agent => mcpChosen.push(agent));
  });
  let toolTotal = 0;
  let toolCount = 0;
  mcpChosen.forEach(mcp => {
    const tools = mcp.tools || [];
    toolTotal += tools.length;
    toolCount += toolsChosenInMcp(mcp).length;
  });
  const btnLabel = document.getElementById('chatSubAgentBtnLabel');
  const countBadge = document.getElementById('chatChecklistCountBadge');
  const subSelect = document.getElementById('chatSubAgentSelect');
  const parts = [];
  if (total) {
    if (count === 0) parts.push('لم يُحدد وكيل');
    else if (count === total) parts.push(groups.length > 1 ? `كل الوكلاء (${total})` : `كل وكلاء المجموعة (${total})`);
    else parts.push(`${count} وكلاء من ${total}`);
  }
  if (toolTotal) {
    if (toolCount === toolTotal) parts.push(`كل فروع MCP (${toolTotal})`);
    else parts.push(`${toolCount} فروع MCP من ${toolTotal}`);
  }
  const labelText = parts.length ? parts.join(' + ') : 'لا توجد فروع';
  if (btnLabel) btnLabel.textContent = labelText;
  if (countBadge) countBadge.textContent = `تم تحديد ${count} وكلاء و ${toolCount} فروع`;
  if (subSelect) {
    subSelect.innerHTML = `<option value="all" selected>${escapeHtml(labelText)}</option>`;
    subSelect.value = 'all';
  }
  if (typeof refreshDirectorAuthorityUI === 'function') refreshDirectorAuthorityUI();
}

// تحديث الواجهة التفاعلية لاختيار الوكلاء (نص الزر، العداد، والحفظ)
function updateSubAgentsSelectionUI(currentGroup, selectedIds) {
  const total = currentGroup.agents.length;
  const count = selectedIds.length;
  const btnLabel = document.getElementById('chatSubAgentBtnLabel');
  const countBadge = document.getElementById('chatChecklistCountBadge');
  const subSelect = document.getElementById('chatSubAgentSelect');

  let labelText = '';
  if (count === 0) {
    labelText = '⚠️ لم يُحدد أي وكيل (اختر)';
  } else if (count === total) {
    labelText = `كل وكلاء المجموعة (${total})`;
  } else if (count === 1) {
    const single = currentGroup.agents.find(a => a.id === selectedIds[0]);
    labelText = `الوكيل: ${single ? single.name : 'واحد'}`;
  } else {
    const names = currentGroup.agents.filter(a => selectedIds.includes(a.id)).map(a => a.name);
    labelText = `${count} وكلاء: ${names.slice(0, 2).join('، ')}${count > 2 ? '...' : ''}`;
  }

  if (btnLabel) btnLabel.textContent = labelText;
  if (countBadge) countBadge.textContent = `تم تحديد ${count} من أصل ${total} وكلاء`;

  // حفظ في التخزين المحلي
  localStorage.setItem('almojtahed_chat_selected_agents_' + currentGroup.id, JSON.stringify(selectedIds));
  localStorage.setItem('almojtahed_selected_chat_subagents', JSON.stringify(selectedIds));

  // تحديث الـ Select الخفي لضمان التوافقية العكسية
  if (subSelect) {
    if (count === 1) {
      subSelect.innerHTML = `<option value="${escapeHtml(selectedIds[0])}" selected>${escapeHtml(labelText)}</option>`;
      subSelect.value = selectedIds[0];
    } else {
      subSelect.innerHTML = `<option value="all" selected>${escapeHtml(labelText)}</option>`;
      subSelect.value = 'all';
    }
  }
}

// النقر على صف كامل داخل التشيك ليست لعكس حالة التحديد
function handleSubAgentCheckItemClick(event, agentId, groupId) {
  const itemsContainer = document.getElementById('chatSubAgentChecklistItems');
  if (!itemsContainer) return;
  const cb = groupId
    ? itemsContainer.querySelector(`input[data-agent-id="${agentId}"][data-group-id="${groupId}"]`)
    : itemsContainer.querySelector(`input[data-agent-id="${agentId}"]`);
  if (!cb) return;
  const ownerGroup = groupId || cb.getAttribute('data-group-id');
  toggleSingleSubAgent(agentId, !cb.checked, ownerGroup);
}

// تبديل اختيار وكيل واحد
function toggleSingleSubAgent(agentId, isChecked, groupId) {
  groupId = groupId || document.getElementById('chatAgentGroupSelect')?.value;
  if (!groupId) return;

  let groups = [];
  try {
    const raw = localStorage.getItem(ownerStorageKey('almojtahed_agent_groups'));
    if (raw) groups = JSON.parse(raw);
  } catch (e) {}
  if (!groups.length && window.agentGroups) groups = window.agentGroups;
  const currentGroup = groups.find(g => g.id === groupId);
  if (!currentGroup) return;

  let selectedIds = [];
  const rawSel = localStorage.getItem('almojtahed_chat_selected_agents_' + groupId);
  if (rawSel === null) {
    selectedIds = (currentGroup.agents || []).map(a => a.id);
  } else {
    try { selectedIds = JSON.parse(rawSel); } catch (e) { selectedIds = []; }
    if (!Array.isArray(selectedIds)) selectedIds = [];
  }

  if (isChecked) {
    if (!selectedIds.includes(agentId)) selectedIds.push(agentId);
  } else {
    selectedIds = selectedIds.filter(id => id !== agentId);
  }

  // تحديث تمييز الصف بصرياً
  const itemsContainer = document.getElementById('chatSubAgentChecklistItems');
  if (itemsContainer) {
    const cb = itemsContainer.querySelector(`input[data-agent-id="${agentId}"][data-group-id="${groupId}"]`)
      || itemsContainer.querySelector(`input[data-agent-id="${agentId}"]`);
    if (cb) {
      cb.checked = isChecked;
      const row = cb.closest('.chat-checklist-item');
      if (row) row.classList.toggle('is-selected', isChecked);
    }
  }

  updateSubAgentsSelectionUI(currentGroup, selectedIds);
  const chosen = readChatAgentGroups().filter(g => readSelectedChatGroupIds(readChatAgentGroups()).includes(g.id));
  updateCombinedSubAgentsUI(chosen);
}

// تحديد أو إلغاء تحديد الكل
function selectAllChatSubAgents(selectAll) {
  const groups = readChatAgentGroups();
  const chosen = groups.filter(g => readSelectedChatGroupIds(groups).includes(g.id));
  chosen.forEach(group => {
    const selectedIds = selectAll ? (group.agents || []).map(a => a.id) : [];
    localStorage.setItem('almojtahed_chat_selected_agents_' + group.id, JSON.stringify(selectedIds));
  });
  readChatAgentGroups().filter(group => readSelectedChatGroupIds(readChatAgentGroups()).includes(group.id)).forEach(group => {
    (group.agents || []).filter(agent => agent.kind === 'mcp').forEach(agent => {
      const names = selectAll ? (agent.tools || []).map(tool => tool.name) : [];
      localStorage.setItem('almojtahed_chat_selected_mcp_tools_' + agent.id, JSON.stringify(names));
    });
  });
  const itemsContainer = document.getElementById('chatSubAgentChecklistItems');
  if (itemsContainer) {
    itemsContainer.querySelectorAll('.chat-agent-item-checkbox').forEach(cb => {
      cb.checked = selectAll;
      const row = cb.closest('.chat-checklist-item');
      if (row) row.classList.toggle('is-selected', selectAll);
    });
  }
  updateCombinedSubAgentsUI(chosen);
}

function placeChatSubAgentsMenu() {
  const menu = document.getElementById('chatSubAgentChecklistMenu');
  const btn = document.getElementById('chatSubAgentDropdownBtn');
  if (!menu || !btn || menu.style.display === 'none') return;
  const rect = btn.getBoundingClientRect();
  const width = Math.min(420, window.innerWidth - 16);
  let left = rect.right - width;
  if (left < 8) left = 8;
  if (left + width > window.innerWidth - 8) left = Math.max(8, window.innerWidth - width - 8);
  const spaceAbove = Math.max(160, rect.top - 12);
  menu.style.position = 'fixed';
  menu.style.left = `${Math.round(left)}px`;
  menu.style.right = 'auto';
  menu.style.top = 'auto';
  menu.style.bottom = `${Math.round(window.innerHeight - rect.top + 8)}px`;
  menu.style.width = `${Math.round(width)}px`;
  menu.style.maxHeight = `${Math.round(spaceAbove)}px`;
  menu.style.zIndex = '100050';
}

function placeChatGroupsMenu() {
  const menu = document.getElementById('chatGroupChecklistMenu');
  const btn = document.getElementById('chatGroupDropdownBtn');
  if (!menu || !btn || menu.style.display === 'none') return;
  const rect = btn.getBoundingClientRect();
  const width = Math.min(420, window.innerWidth - 16);
  let left = rect.right - width;
  if (left < 8) left = 8;
  if (left + width > window.innerWidth - 8) left = Math.max(8, window.innerWidth - width - 8);
  const spaceAbove = Math.max(160, rect.top - 12);
  menu.style.position = 'fixed';
  menu.style.left = `${Math.round(left)}px`;
  menu.style.right = 'auto';
  menu.style.top = 'auto';
  menu.style.bottom = `${Math.round(window.innerHeight - rect.top + 8)}px`;
  menu.style.width = `${Math.round(width)}px`;
  menu.style.maxHeight = `${Math.round(spaceAbove)}px`;
  menu.style.zIndex = '100050';
}

function toggleChatGroupsDropdown(event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const menu = document.getElementById('chatGroupChecklistMenu');
  const btn = document.getElementById('chatGroupDropdownBtn');
  if (!menu || btn?.disabled) return;
  const isOpen = menu.style.display !== 'none';
  if (isOpen) {
    closeChatGroupsDropdown();
    return;
  }
  closeSubAgentsDropdown();
  if (menu.parentElement !== document.body) document.body.appendChild(menu);
  menu.style.display = 'flex';
  menu.classList.add('is-portaled');
  if (btn) btn.classList.add('is-open');
  placeChatGroupsMenu();
}

function closeChatGroupsDropdown() {
  const menu = document.getElementById('chatGroupChecklistMenu');
  const btn = document.getElementById('chatGroupDropdownBtn');
  const wrap = document.getElementById('chatGroupSelectWrap');
  if (menu) {
    menu.style.display = 'none';
    menu.classList.remove('is-portaled');
    if (wrap && menu.parentElement !== wrap) wrap.appendChild(menu);
  }
  if (btn) btn.classList.remove('is-open');
}

function toggleSubAgentsDropdown(event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const menu = document.getElementById('chatSubAgentChecklistMenu');
  const btn = document.getElementById('chatSubAgentDropdownBtn');
  if (!menu) return;

  const isOpen = menu.style.display !== 'none';
  if (isOpen) {
    closeSubAgentsDropdown();
  } else {
    closeChatGroupsDropdown();
    if (menu.parentElement !== document.body) document.body.appendChild(menu);
    menu.style.display = 'flex';
    menu.classList.add('is-portaled');
    if (btn) btn.classList.add('is-open');
    placeChatSubAgentsMenu();
  }
}

function closeSubAgentsDropdown() {
  const menu = document.getElementById('chatSubAgentChecklistMenu');
  const btn = document.getElementById('chatSubAgentDropdownBtn');
  const wrap = document.getElementById('chatSubAgentSelectWrap');
  if (menu) {
    menu.style.display = 'none';
    menu.classList.remove('is-portaled');
    if (wrap && menu.parentElement !== wrap) wrap.appendChild(menu);
  }
  if (btn) btn.classList.remove('is-open');
}

if (!window._chatSubAgentMenuBound) {
  window._chatSubAgentMenuBound = true;
  window.addEventListener('resize', placeChatSubAgentsMenu);
  window.addEventListener('resize', placeChatGroupsMenu);
  document.addEventListener('scroll', placeChatSubAgentsMenu, true);
  document.addEventListener('scroll', placeChatGroupsMenu, true);
}

// إغلاق القائمة عند النقر في أي مكان خارجها
document.addEventListener('click', (e) => {
  const wrap = document.getElementById('chatSubAgentSelectWrap');
  const menu = document.getElementById('chatSubAgentChecklistMenu');
  if (menu && menu.style.display !== 'none') {
    const inside = (wrap && wrap.contains(e.target)) || menu.contains(e.target);
    if (!inside) closeSubAgentsDropdown();
  }
  const groupWrap = document.getElementById('chatGroupSelectWrap');
  const groupMenu = document.getElementById('chatGroupChecklistMenu');
  if (groupMenu && groupMenu.style.display !== 'none') {
    const insideGroup = (groupWrap && groupWrap.contains(e.target)) || groupMenu.contains(e.target);
    if (!insideGroup) closeChatGroupsDropdown();
  }
});

// معالجة تغيير اختيار الوكيل الفرعي (للتوافق)
function handleSubAgentDropdownChange() {
  const select = document.getElementById('chatAgentGroupSelect');
  const subSelect = document.getElementById('chatSubAgentSelect');
  if (!select || !subSelect) return;
  const groupId = select.value;
  localStorage.setItem('almojtahed_chat_selected_agent_id_' + groupId, subSelect.value);
  const text = subSelect.options[subSelect.selectedIndex]?.text || '';
  if (typeof showToast === 'function') {
    showToast(`تم تعيين الوكيل المنفذ: ${text}`, 2000);
  }
}

// معالجة تغيير مربع الاختيار لتوجيه الطلب للمجموعة
function handleAgentGroupCheckboxToggle() {
  const checkbox = document.getElementById('chatUseAgentGroupCheckbox');
  const select = document.getElementById('chatAgentGroupSelect');
  const container = document.getElementById('chatAgentGroupPicker');
  if (!checkbox || !select) return;

  const isChecked = checkbox.checked;
  if (isChecked && !select.value && !readSelectedChatMcpIds().length) {
    checkbox.checked = false;
    if (container) container.classList.remove('active');
    const empty = document.getElementById('chatGroupSelectWrap')?.dataset.empty === '1';
    if (typeof showToast === 'function') {
      showToast(empty ? 'لا توجد مجموعات أو خوادم MCP' : 'حدد مجموعة أو خادم MCP', 2500);
    }
    return;
  }
  select.disabled = false;
  select.removeAttribute('disabled');

  if (container) {
    container.classList.toggle('active', isChecked);
  }

  const subBtn = document.getElementById('chatSubAgentDropdownBtn');
  if (subBtn) {
    subBtn.disabled = !isChecked;
    subBtn.style.opacity = isChecked ? '1' : '0.45';
    subBtn.style.pointerEvents = isChecked ? 'auto' : 'none';
  }
  if (!isChecked) {
    closeSubAgentsDropdown();
    closeChatGroupsDropdown();
  }

  localStorage.setItem('almojtahed_chat_use_agent_group', isChecked ? 'true' : 'false');

  if (isChecked) {
    populateSubAgentsDropdown();
    const selectedText = document.getElementById('chatGroupBtnLabel')?.textContent || '';
    if (typeof showToast === 'function') {
      showToast(`تم تفعيل إسناد ومعالجة البحث عبر «${selectedText}»`, 3000);
    }
  } else {
    if (typeof showToast === 'function') {
      showToast('تم إلغاء التوجيه للمجموعة (الاستعلام المباشر عبر النموذج)', 2500);
    }
  }
}

// معالجة تغيير اختيار المجموعة من القائمة المنسدلة
function handleAgentGroupDropdownChange() {
  const select = document.getElementById('chatAgentGroupSelect');
  const checkbox = document.getElementById('chatUseAgentGroupCheckbox');
  const container = document.getElementById('chatAgentGroupPicker');
  if (!select || !select.value) return;
  writeSelectedChatGroupIds([select.value]);
  populateChatAgentGroupsDropdown();
  if (checkbox) {
    checkbox.checked = true;
    if (container) container.classList.add('active');
    localStorage.setItem('almojtahed_chat_use_agent_group', 'true');
  }
}

window.populateChatAgentGroupsDropdown = populateChatAgentGroupsDropdown;
window.populateSubAgentsDropdown = populateSubAgentsDropdown;
window.handleSubAgentDropdownChange = handleSubAgentDropdownChange;
window.handleAgentGroupCheckboxToggle = handleAgentGroupCheckboxToggle;
window.handleAgentGroupDropdownChange = handleAgentGroupDropdownChange;
window.toggleSubAgentsDropdown = toggleSubAgentsDropdown;
window.closeSubAgentsDropdown = closeSubAgentsDropdown;
window.selectAllChatSubAgents = selectAllChatSubAgents;
window.handleSubAgentCheckItemClick = handleSubAgentCheckItemClick;
window.toggleSingleSubAgent = toggleSingleSubAgent;
window.toggleChatGroupsDropdown = toggleChatGroupsDropdown;
window.closeChatGroupsDropdown = closeChatGroupsDropdown;
window.selectAllChatGroups = selectAllChatGroups;
window.handleChatGroupCheckItemClick = handleChatGroupCheckItemClick;
window.toggleSingleChatGroup = toggleSingleChatGroup;
if (!window._chatMcpListBound) {
  window._chatMcpListBound = true;
  document.addEventListener('click', (event) => {
    const refresh = event.target?.closest?.('[data-mcp-refresh]');
    const remove = event.target?.closest?.('[data-mcp-delete]');
    if (refresh) refreshChatMcp(refresh.getAttribute('data-mcp-refresh'));
    if (remove) deleteChatMcp(remove.getAttribute('data-mcp-delete'));
  });
}

window.buildChatAgentGroupPayload = buildChatAgentGroupPayload;
window.buildChatMcpPayload = buildChatMcpPayload;
window.addChatMcp = addChatMcp;

function scrollToBottom() {
  const container = document.getElementById('chatMessagesContainer');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

// تحويل نصوص الماركداون القياسية إلى HTML مع دعم كامل للجداول والاقتباسات النبوية والقرآنية
function chatIndicToWestern(value) {
  return String(value || '')
    .replace(/[٠-٩]/g, (digit) => '٠١٢٣٤٥٦٧٨٩'.indexOf(digit))
    .replace(/[۰-۹]/g, (digit) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(digit));
}

function chatDisplayText(text, scope) {
  const source = String(text || '');
  if (!/<p[\s>]|<sup[\s>]/i.test(source)) return source;
  const prefix = scope ? `${scope}-` : '';
  let next = source.replace(/\bid=(["'])fn(\d+)\1/gi, (match, quote, number) => `id=${quote}${prefix}fn${number}${quote}`);
  next = next.replace(/<ol>([\s\S]*?)<\/ol>/gi, (full, inner) => {
    if (!/fn\d+/.test(inner)) return full;
    return `<ol class="chat-fn-list">${inner}</ol>`;
  });
  next = next.replace(/(<li\s+id="[^"]*fn(\d+)"[^>]*>)\s*<sup>\s*<small>\s*(\([^<]{1,12}\))\s*<\/small>\s*<\/sup>/gi, (match, open, number, label) => {
    return `${open}<a class="chat-fn-back" href="#${prefix}ref${number}-1">${label}</a>`;
  });
  const seen = {};
  next = next.replace(/<sup>\s*<small>\s*\(([^)<]{1,8})\)\s*<\/small>\s*<\/sup>/gi, (match, number) => {
    const western = chatIndicToWestern(number).replace(/\D/g, '');
    if (!western) return `(${number})`;
    seen[western] = (seen[western] || 0) + 1;
    const refId = `${prefix}ref${western}-${seen[western]}`;
    return `<a class="chat-fn-ref" id="${refId}" href="#${prefix}fn${western}">(${number})</a>`;
  });
  return next
    .replace(/<p[^>]*>/gi, '')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<br\s*\/?>/gi, '\n');
}

function enforceStandardCitations(text) {
  const source = String(text || '');
  if (!source) return source;
  const eastern = '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹';
  const western = '01234567890123456789';
  const toInt = (token) => parseInt(String(token).replace(/[٠-٩۰-۹]/g, (d) => western[eastern.indexOf(d)]), 10);
  const lead = /^(?:و?(?:انظر|راجع|ينظر|يُنظر|قال|في|من|جاء|كتاب|المصدر|المرجع|هذا|ذلك|كما|نص|عند|إلى|الى|عن|على|وهو|هي|هو|وقد|قد|ثم|أو|او|بعد|قبل))\s+/;
  const reject = new Set(['الآية', 'آية', 'الآيات', 'السورة', 'سورة', 'عام', 'سنة', 'العام', 'القرن', 'الباب', 'الفصل', 'المسألة', 'القول', 'المذهب', 'جزء', 'الجزء', 'صفحة', 'الصفحة']);
  const titleOf = (raw) => {
    let title = String(raw || '').trim();
    if (title.startsWith('«') && title.includes('»')) title = title.slice(1, title.lastIndexOf('»')).trim();
    let next = title.replace(lead, '');
    while (next !== title) {
      title = next;
      next = title.replace(lead, '');
    }
    title = title.replace(/\s+/g, ' ').replace(/^[«»"\s]+|[«»"\s]+$/g, '');
    const letters = (title.match(/[\u0600-\u06FF]/g) || []).length;
    if (!title || reject.has(title) || letters < 3 || title.length > 80) return '';
    return title;
  };
  const locator = (first, second) => {
    const left = toInt(first);
    const right = toInt(second);
    if (!Number.isFinite(left) || !Number.isFinite(right)) return '';
    if (left >= 1300 && right >= 1300) return '';
    let volume = left;
    let page = right;
    if (left > right && left >= 60 && right <= 40 && left >= right * 3) {
      volume = right;
      page = left;
    }
    if (volume < 1 || volume > 200 || page < 1 || page > 3000) return '';
    return `(${volume}-${page})`;
  };
  const rewrite = (chunk) => chunk
    .replace(/\(\s*(«[^»\n]{3,80}»|[\u0600-\u06FF][\u0600-\u06FF\s]{2,70}?)\s+([0-9٠-٩۰-۹]{1,4})\s*[-–—/／]\s*([0-9٠-٩۰-۹]{1,4})\s*\)/g, (all, book, first, second) => {
      const title = titleOf(book);
      const loc = locator(first, second);
      return title && loc ? `${title} ${loc}` : all;
    })
    .replace(/(«[^»\n]{3,80}»|[\u0600-\u06FF]+(?:\s+[\u0600-\u06FF]+){0,8})\s*\(\s*([0-9٠-٩۰-۹]{1,4})\s*[-–—/／]\s*([0-9٠-٩۰-۹]{1,4})\s*\)/g, (all, book, first, second) => {
      const title = titleOf(book);
      const loc = locator(first, second);
      if (!title || !loc) return all;
      const kept = book.slice(0, book.lastIndexOf(title));
      return `${kept}${title} ${loc}`;
    })
    .replace(/ص\s*\(\s*([0-9٠-٩۰-۹]{1,4})\s*\)/g, (_, page) => `ص(${toInt(page)})`);
  return source.split(/(```[\s\S]*?```)/).map((part) => (part.startsWith('```') ? part : rewrite(part))).join('');
}
window.enforceStandardCitations = enforceStandardCitations;

function stripMatnCitations(html) {
  return String(html || '')
    .replace(/(«[^»\n]{3,80}»|(?:(?!سورة\s|الآية\s|آية\s)[\u0600-\u06FF]{3,}(?:\s+[\u0600-\u06FF]+){0,8}))\s*\(\s*[0-9٠-٩۰-۹]{1,4}\s*[-–—/／]\s*[0-9٠-٩۰-۹]{1,4}\s*\)/g, '')
    .replace(/(«[^»\n]{3,80}»|[\u0600-\u06FF]{3,}(?:\s+[\u0600-\u06FF]+){0,8})\s*ص\s*\(\s*[0-9٠-٩۰-۹]{1,4}\s*\)/g, '')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\s+([،.])/g, '$1');
}
window.stripMatnCitations = stripMatnCitations;

function renderScholarlyAnswer(text, scope) {
  const prefix = scope ? `${scope}-` : '';
  let next = String(text || '');
  const footnoteAt = next.search(/<ol>[\s\S]*?\bfn\d+/i);
  if (footnoteAt >= 0) next = stripMatnCitations(next.slice(0, footnoteAt)) + next.slice(footnoteAt);
  next = next.replace(/\bid=(["'])fn(\d+)\1/gi, (match, quote, number) => `id=${quote}${prefix}fn${number}${quote}`);
  next = next.replace(/<ol>([\s\S]*?)<\/ol>/gi, (full, inner) => {
    if (!/fn\d+/.test(inner)) return full;
    return `<ol class="chat-fn-list">${inner}</ol>`;
  });
  next = next.replace(/(<li\s+id="[^"]*fn(\d+)"[^>]*>)\s*<sup>\s*<small>\s*(\([^<]{1,12}\))\s*<\/small>\s*<\/sup>/gi, (match, open, number, label) => {
    return `${open}<a class="chat-fn-back" href="#${prefix}ref${number}-1">${label}</a>`;
  });
  const seen = {};
  next = next.replace(/<sup>\s*<small>\s*\(([^)<]{1,8})\)\s*<\/small>\s*<\/sup>/gi, (match, number) => {
    const western = chatIndicToWestern(number).replace(/\D/g, '');
    if (!western) return `(${number})`;
    seen[western] = (seen[western] || 0) + 1;
    const refId = `${prefix}ref${western}-${seen[western]}`;
    return `<a class="chat-fn-ref" id="${refId}" href="#${prefix}fn${western}">(${number})</a>`;
  });
  next = next.replace(/(?:<br\s*\/?>\s*)*<hr\b[^>]*>(?:\s*<br\s*\/?>)*(?=\s*<ol class="chat-fn-list">)/gi, '');
  next = next.replace(/(^|[>\s])#(\d{2,6})(?=\s)/g, '$1');
  return `<div class="chat-academic">${next}</div>`;
}

function formatMarkdown(text, scope) {
  if (!text) return '';
  text = enforceStandardCitations(text);
  if (/<p[\s>]|<sup[\s>]|<ol[\s>]/i.test(text)) {
    return attachTableToolbar(renderScholarlyAnswer(text, scope));
  }
  text = chatDisplayText(text, scope);

  let html = '';
  if (typeof marked !== 'undefined' && (marked.parse || typeof marked === 'function')) {
    try {
      if (typeof marked.setOptions === 'function') {
        marked.setOptions({
          gfm: true,
          breaks: true
        });
      }
      const parseFn = marked.parse || marked;
      html = parseFn(text);
    } catch (e) {
      console.warn('Marked parsing error:', e);
    }
  }

  // معالجة احتياطية في حال عدم توفر مكتبة marked
  if (!html) {
    let res = escapeHtml(text);
    res = res.replace(/^### (.*$)/gim, '<h4 style="font-family: var(--font-reading); font-size: 19px; margin: 12px 0 6px; color: var(--text-main);">$1</h4>');
    res = res.replace(/^## (.*$)/gim, '<h3 style="font-family: var(--font-reading); font-size: 21px; margin: 14px 0 8px; color: var(--accent-clay);">$1</h3>');
    res = res.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    res = res.replace(/\*(.*?)\*/g, '<em>$1</em>');
    res = res.replace(/^\- (.*$)/gim, '<li style="margin-right: 18px; margin-bottom: 4px;">$1</li>');
    res = res.replace(/\n\n+/g, '</p><p>');
    html = `<p>${res}</p>`;
  }

  return attachTableToolbar(html);
}

// تغليف أي جدول يتم إنشاؤه بشريط أدوات يتضمن زر تحميل CSV
function attachTableToolbar(html) {
  if (!html || !html.includes('<table')) return html;

  const tableRegex = /<table[\s\S]*?<\/table>/gi;
  return html.replace(tableRegex, (match) => {
    // حساب عدد السجلات (الصفوف باستثناء صف العناوين)
    const rowMatches = match.match(/<tr[\s\S]*?<\/tr>/gi);
    const rowCount = rowMatches ? Math.max(0, rowMatches.length - 1) : 0;
    const countBadge = rowCount > 0 ? ` (${rowCount} سجل)` : '';

    return `
      <div class="chat-table-wrapper">
        <div class="chat-table-header">
          <span class="chat-table-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3h18v18H3zM3 9h18M3 15h18M9 3v18M15 3v18"/></svg>
            <span>جدول البيانات المستخرجة${countBadge}</span>
          </span>
          <button type="button" class="chat-table-csv-btn" onclick="downloadTableAsCSV(this)" title="تحميل الجدول بصيغة CSV لفتحه في Microsoft Excel">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            <span>تحميل CSV</span>
          </button>
        </div>
        <div class="chat-table-scroll">
          ${match}
        </div>
      </div>
    `;
  });
}

// دالة تصدير الجدول إلى ملف CSV متوافق مع اللغة العربية في Excel
function downloadTableAsCSV(btn) {
  try {
    const wrapper = btn.closest('.chat-table-wrapper') || btn.closest('.message-content');
    if (!wrapper) return;
    const table = wrapper.querySelector('table');
    if (!table) return;

    const rows = Array.from(table.querySelectorAll('tr'));
    if (!rows.length) return;

    const csvLines = [];
    rows.forEach(tr => {
      const cells = Array.from(tr.querySelectorAll('th, td'));
      if (!cells.length) return;
      const rowData = cells.map(cell => {
        let text = cell.innerText || cell.textContent || '';
        text = text.trim();
        // إزالة فواصل الأسطر الداخلية داخل الخلية لتجنب كسر الصفوف في CSV
        text = text.replace(/[\r\n]+/g, ' ');
        // معالجة علامات التنصيص المزدوجة داخل النص
        text = text.replace(/"/g, '""');
        return `"${text}"`;
      });
      csvLines.push(rowData.join(','));
    });

    if (csvLines.length === 0) return;

    // إضافة علامة الترتيب البايتي \uFEFF (UTF-8 BOM) لضمان ظهور الأحرف العربية بشكل قياسي في Excel دون تشويه
    const csvContent = '\uFEFF' + csvLines.join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;

    const now = new Date();
    const dateStr = now.toISOString().slice(0, 10);
    const timeStr = `${String(now.getHours()).padStart(2, '0')}-${String(now.getMinutes()).padStart(2, '0')}`;
    link.download = `جدول_المجتهد_${dateStr}_${timeStr}.csv`;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 120000);

    if (typeof showToast === 'function') {
      showToast('تم تحميل الجدول بصيغة CSV بنجاح');
    }
  } catch (err) {
    console.error('Error downloading CSV:', err);
    if (typeof showAlertDialog === 'function') {
      showAlertDialog({
        title: 'خطأ في التصدير',
        message: 'حدث خطأ أثناء إعداد وتحميل ملف الجدول CSV.',
        type: 'danger'
      });
    } else if (typeof showToast === 'function') {
      showToast('حدث خطأ أثناء تحميل الجدول', 4000);
    }
  }
}

window.downloadTableAsCSV = downloadTableAsCSV;
window.formatMarkdown = formatMarkdown;
window.exportChatSessionFile = exportChatSessionFile;
window.importChatSessionFile = importChatSessionFile;
window.exportChatMessageHtml = exportChatMessageHtml;
window.exportChatMessagePdf = exportChatMessagePdf;
window.prepareChatAnswerShareFile = prepareChatAnswerShareFile;
window.copyChatMessageText = copyChatMessageText;

// =============================================================================
// قوالب إخراج البحوث التخصصية الجاهزة في الشات (فوق زر الإرسال)
// =============================================================================
const CHAT_OUTPUT_TEMPLATES = {
  fiqh: `اذا طلب منك المستخدم إخراج البحث وترتيبه قم بالتالي:
صورة المسألة: بيان واقع المسألة المطروحة.
تحرير محل النزاع: ضبط نقطة الاتفاق والاختلاف بدقة.
الأدلة النقلية: استعراض الآيات والأحاديث المتعلقة بالمسألة.
بيان أسباب الخلاف: ذكر الجذور التي تفرع عنها الخلاف (من كتب أسباب الخلاف).
سرد الأقوال الفقهية بأدلتها: ذكر كل قول بأدلته، مع نسبة كل قول إلى قائليه من المذاهب (من كتب الفقه).
القواعد والأصول الداخلة في المسألة: ربط المسألة بالقواعد الفقهية والأصولية (من كتب القواعد والأصول).
مناقشة الأدلة: استعراض المناقشات والاعتراضات المذكورة في المصادر.
الترجيح: رجّح ما تراه راجحاً مع بيان سبب الترجيح الأصولي والفقهي.
## [1] منهجية الحاشية والإحالات ##

أولًا: خرّج الأحاديث تخريجًا كاملاً وفق قواعد التخريج المذكورة أعلاه، وضعها في الحاشية.
ثانيًا: اذكر مصدر كل قول في الحاشية بذكر: اسم الكتاب، مؤلفه، الجزء، الصفحة.
ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.
رابعًا: استخدم الإحالة الصحيحة:
إذا نقلت نصًا حرفيًا: اكتب "انظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: الرقم المرتفع وحده هكذا: <sup><small>(١)</small></sup>. يُمنع ذكر اسم الكتاب أو الجزء أو الصفحة في المتن، والمرجع كامل في الحاشية فقط.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (القول الأول: / الدليل الأول:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
الحاشية هي التوثيق الوحيد لما نُقل في المتن. لا تُنشئ بعد الحواشي قائمة مصادر ومراجع.`,

  tafsir: `اذا طلب منك المستخدم إخراج البحث وترتيبه قم بالتالي:
نص الآية الكريمة وسياقها: إيراد الآيات محل التفسير والبيان وضبط ألفاظها.
سبب النزول وتحقيقه: ذكر الروايات الواردة في سبب النزول والتمييز بين الصحيح والضعيف منها (من كتب أسباب النزول ومصنفات الحديث).
المعنى الإجمالي وغريب الألفاظ: بيان المعنى العام والمدلول اللغوي للألفاظ الغريبة (من كتب معاني القرآن وغريب القرآن والمعاجم).
أقوال السلف من الصحابة والتابعين: سرد المأثور عن ابن عباس، ومجاهد، وقتادة، وسائر أئمة التفسير المتقدمين بأسانيدها المحررة (من تفسير الطبري وابن أبي حاتم وعبد الرزاق).
أقوال المفسرين وتوجيهها: استعراض وجوه التفسير لدى المحققين (القرطبي، وابن كثير، والرازي، والشوكاني) مع المقارنة بين المأثور والرأي.
الوجوه البلاغية والإعرابية: إبراز النكت البلاغية واللطائف البيانية والإعراب المؤثر في المعنى.
الهدايات والأحكام والفوائد: استنباط المقاصد والأحكام والدروس المستفادة من الآية.
الترجيح والاختيار: ترجيح المعنى الأظهر مع بيان القرائن التفسيرية واللغوية والسياقية المعتمدة.
## [1] منهجية الحاشية والإحالات ##

أولًا: خرّج الأحاديث والآثار المروية عن السلف تخريجًا كاملاً مع بيان درجتها في الحاشية.
ثانيًا: اذكر مصدر كل قول وتفسير في الحاشية بذكر: اسم الكتاب، مؤلفه، الجزء، الصفحة.
ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.
رابعًا: استخدم الإحالة الصحيحة:
إذا نقلت نصًا حرفيًا: اكتب "انظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: الرقم المرتفع وحده هكذا: <sup><small>(١)</small></sup>. يُمنع ذكر اسم الكتاب أو الجزء أو الصفحة في المتن، والمرجع كامل في الحاشية فقط.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (الوجه الأول: / القول الثاني:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
الحاشية هي التوثيق الوحيد لما نُقل في المتن. لا تُنشئ بعد الحواشي قائمة مصادر ومراجع.`,

  hadith: `اذا طلب منك المستخدم إخراج البحث وترتيبه قم بالتالي:
نص الحديث وألفاظه ورواياته: إيراد متن الحديث مع رصد الفروق اللفظية والزيادات في الروايات.
التخريج الموسع من الدواوين المسندة: عزو الحديث إلى الكتب التسعة والمصنفات والمسانيد والمعاجم مع بيان الكتاب والباب ورقم الحديث.
جمع الطرق ورصد المدار: حصر طرق الحديث وبيان الراوي المدار الذي تلتقي عنده الأسانيد (من كتب الجوامع والأطراف والعلل).
المتابعات والشواهد: استقصاء المتابعات التامة والقاصرة وشواهد الحديث من رواية صحابة آخرين لبيان القوة والاعتبار.
دراسة الإسناد ونقد رجاله: ترجمة موجزة لرجال السند وتحرير مراتبهم من كتب الجرح والتعديل المعتمدة (التهذيب والميزان).
تحرير الاتصال والعلل: بحث اتصال السماع وكشف الإرسال الخفي أو الانقطاع أو التدليس، وبيان الاختلاف رفعاً ووقفاً ووصلاً وإرسالاً.
الحكم النهائي على الحديث: صياغة الحكم النقدي المعلل بعبارات المحدثين المنضبطة (صحيح، حسن، ضعيف، منكر...).
فقه الحديث ودلالته: بيان المسائل الفقهية والأصولية والتربوية المستنبطة من المتن.
## [1] منهجية الحاشية والإحالات ##

أولًا: خرّج الحديث تخريجًا كاملاً بذكر: اسم المصنف، اسم الكتاب، الباب، رقم الحديث، الجزء والصفحة.
ثانيًا: اذكر نقول أئمة الجرح والتعديل في الحاشية معزوّة إلى مصادرها الأصيلة.
ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.
رابعًا: استخدم الإحالة الصحيحة:
إذا نقلت نصًا حرفيًا: اكتب "انظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: الرقم المرتفع وحده هكذا: <sup><small>(١)</small></sup>. يُمنع ذكر اسم الكتاب أو الجزء أو الصفحة في المتن، والمرجع كامل في الحاشية فقط.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (الطريق الأول: / علة الحديث:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
الحاشية هي التوثيق الوحيد لما نُقل في المتن. لا تُنشئ بعد الحواشي قائمة مصادر ومراجع.`,

  isnad_tree: `اذا طلب منك المستخدم دراسة الإسناد أو رسم شجرة الأسانيد وشبكات الرواة قم بالتالي:
## [1] التخريج الموسع وجمع الطرق ##
أولاً: أورد نص الحديث المسند مع توثيق مخرجه في كتب السنة الأصلية (الكتب الستة، المسانيد، والمعاجم).
ثانياً: اذكر كافة الطرق المروية عن الصحابي أو التابعي مع بيان مواضع الالتقاء والافتراق بين الرواة.

## [2] تحرير المدار والاختلاف عليه ##
حدد بوضوح "راوي المدار" المشترك بين أسانيد الحديث (كالزهري أو قتادة أو الأعمش)، وبيّن أوجه الاختلاف عليه تفصيلاً:
(الرفع مقابل الوقف، الوصل مقابل الإرسال، وتسمية الرواة وإبدالهم)، مع ترجيح الوجه المحفوظ بالأدلة الحديثية وقواعد التعليل.

## [3] جدول شبكة الرواة وتراجم الإسناد ##
قم بصياغة جدول ماركداون محكم يوضح طبقات السند وحال كل راوٍ:
| الطبقة | اسم الراوي | حاله وضبطه | صيغة الأداء والاتصال | صفته في السند (مدار / متابع / تفرد) |
(واحرص على تصنيف الراوي المدار بدقة كـ: "مدار الحديث"، والصحابي كـ: "صحابي رضي الله عنه").

## [4] الهيكل الشجري لشبكة الأسانيد (Markmap / Vis.js) ##
قم برسم وتفريغ مسارات الإسناد في كتلة كود markmap توضح تفريع الطرق والمدار بصرياً:
\`\`\`markmap
# [الصحابي رضي الله عنه]
## [التابعي]
### [راوي المدار المشترك: كالزهري أو قتادة]
- طريق (١): [التلميذ الأول]
  - [راوي الطبقة التالية]
    - صحيح البخاري
- طريق (٢): [التلميذ الثاني]
  - [راوي الطبقة التالية]
    - صحيح مسلم
- طريق (٣): [التلميذ الثالث]
  - سنن أبي داود
\`\`\`

ثم أخرج كتلة force3d واحدة يرسمها مشجر الإسناد. كل راوٍ عقدة بمعرّف ثابت، وراوي المدار معرّف واحد تشترك فيه كل الطرق. الاتجاه من الأعلى إلى الأسفل: source الشيخ و target التلميذ. role يكون: صحابي أو تابعي أو مدار أو طريق أو ضعيف أو كتاب.
\`\`\`force3d
{
  "title": "مدار الحديث",
  "nodes": [
    {"id": "sahabi", "name": "عمر بن الخطاب", "role": "صحابي", "detail": "رضي الله عنه"},
    {"id": "madar", "name": "يحيى بن سعيد الأنصاري", "role": "مدار", "detail": "مدار الحديث"},
    {"id": "malik", "name": "مالك بن أنس", "role": "طريق", "detail": "الموطأ"},
    {"id": "sufyan", "name": "سفيان بن عيينة", "role": "طريق", "detail": "الطريق الثاني"}
  ],
  "links": [
    {"source": "sahabi", "target": "madar", "label": "عن"},
    {"source": "madar", "target": "malik", "label": "حدثنا"},
    {"source": "madar", "target": "sufyan", "label": "حدثنا"}
  ]
}
\`\`\`
لا تكرر راوي المدار في كل طريق. أبقِ الأسماء العربية كاملة، ولا تجعل JSON داخل جدول.

## [5] الحكم النهائي والعلل الخفية ##
بيان العلة القادحة إن وجدت، والحكم الجازم على ثبوت الحديث أو إعلاله، مع توثيق تراجم الرواة وأقوال النقاد في الحاشية.
## [6] منهجية الحاشية ##
اذكر مصادر تراجم الرواة (تهذيب الكمال، سير أعلام النبلاء، التقريب) وكتب العلل في الحاشية بذكر: اسم الكتاب، مؤلفه، الجزء، الصفحة.`,

  markmap: `اذا طلب منك المستخدم تشجير المسألة أو عرض الأقوال والاختلافات في خريطة ذهنية (Markmap) قم بالتالي:
## [1] الخريطة الذهنية والشجرة التفاعلية (Markmap) ##
ابدأ إجابتك مباشرة أو صدّرها بكتلة كود markmap محكمة ترسم الشجرة الكاملة للمسألة والأقوال وتفريعاتها وأدلتها، هكذا:
\`\`\`markmap
# [عنوان المسألة الشرعية أو الفكرية بدقة]
## تحرير محل النزاع
- ما اتفق عليه أئمة المذاهب
- نقطة الافتراق والخلاف الجوهري
## القول الأول: [المذهب الأول أو الجمهور]
- القائلون به: الحنفية / المالكية / الشافعية / الحنابلة
- الأدلة النقلية: الآيات والأحاديث
- الأدلة القياسية والتعليل ومأخذ الاستنباط
## القول الثاني: [المذهب المخالف أو الرواية الأخرى]
- القائلون به
- الأدلة والاعتراضات
## القول الثالث (إن وجد)
- القائلون وتفصيل المذهب
## أسباب الخلاف وجذوره الفقهية والأصولية
- التردد بين أصلين أو الاشتراك اللغوي
## الترجيح ومآل الفتوى
- القول الراجح مع وجه الترجيح
\`\`\`

ثم أخرج كتلة force3d لشبكة الأقوال والأدلة إن اشترك دليل بين أكثر من قول. role يكون: قول أو مذهب أو دليل.
\`\`\`force3d
{
  "title": "شبكة الأقوال والأدلة",
  "nodes": [
    {"id": "q1", "name": "الجواز", "role": "قول"},
    {"id": "q2", "name": "المنع", "role": "قول"},
    {"id": "d1", "name": "حديث الأعمال بالنيات", "role": "دليل"}
  ],
  "links": [
    {"source": "d1", "target": "q1", "label": "استدل به"},
    {"source": "d1", "target": "q2", "label": "استدل به"}
  ]
}
\`\`\`

## [2] التحليل والتأصيل العلمي في المتن ##
1. تحرير صورة المسألة والتحرير الأصولي الدقيق.
2. تفصيل أدلة كل فريق مع مناقشة الاعتراضات والردود من كتب الفقه المقارن المعتمدة.
3. الترجيح المعتمد على القواعد الفقهية ومقاصد الشريعة.

## [3] منهجية الحاشية والمصادر ##
توثيق كل قول ودليل في الحاشية بذكر: اسم الكتاب، مؤلفه، الجزء، الصفحة، وفق قواعد الإخراج القياسي.`,

  isnad: `اذا طلب منك المستخدم إخراج البحث وترتيبه قم بالتالي:
توصيف الحديث ومصدره: إيراد الحديث المسند موضوع الدراسة مع ذكر مخرجه وصحابيه.
رسم شبكة الطرق وشجرة الإسناد: تفريغ أسانيد الحديث في هيكل شجري مرئي يوضح طبقات الرواة والمدار ونقاط الافتراق والالتقاء.
تحرير المدار والاختلاف عليه: تحديد الراوي المدار، وفصل وجوه الاختلاف عليه (الرفع مقابل الوقف، الوصل مقابل الإرسال، وتسمية الرواة وإبدالهم).
تراجم رجال الإسناد طبقة طبقة: دراسة كل راوٍ في السلسلة، بذكر: اسمه، طبقته، سنة وفاته، مرتبته التوثيقية، وأهم ما قيل فيه جرحاً وتعديلاً.
تحقيق صيغ الأداء والاتصال: التحقق من اتصال السماع بين كل راوٍ وشيخه، وتدقيق صيغ التحديث، وتفتيش عن مظان التدليس وعنعنة المدلسين.
الموازنة والترجيح بين الوجوه المتعارضة: الموازنة بين الرواة المختلفين وفق قواعد تقديم الأحفظ والأكثر عدداً وملازمة للشيخ.
النتيجة والعلة النهائية: بيان العلة الخفية القادحة في السند إن وجدت، والحكم الجازم على صحة الطريق أو إعلاله.
## [1] منهجية الحاشية والإحالات ##
أولًا: اذكر مصادر تراجم الرواة في الحاشية من كتب الرجال المعتمدة (الجرح والتعديل لابن أبي حاتم، تهذيب الكمال للمزي، ميزان الاعتدال للذهبي، التقريب لابن حجر).
ثانيًا: اذكر نصوص أقوال النقاد ومواضع الاختلاف من كتب العلل (علل الدارقطني، علل ابن أبي حاتم، العلل للترمذي وأحمد).
ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا.
رابعًا: إذا نقلت نصًا حرفيًا: اكتب "انظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة). وإذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
## [2] التنسيق الطباعي ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML بدقة.`,

  aqeedah: `اذا طلب منك المستخدم إخراج البحث وترتيبه قم بالتالي:
تحرير المسألة العقدية: ضبط عنوان المسألة وبيان محل النزاع العقدي وحقيقة المعتقد فيها.
الأدلة من القرآن الكريم والسنة النبوية: استعراض النصوص النقلية الدالة على الباب وضبط وجه الدلالة منها.
مذهب السلف الصالح وأهل السنة والجماعة: سرد أقوال الصحابة والتابعين والأئمة الأربعة وأعلام السنة بنصوصها الحرفية من المصنفات المسندة وكتب الاعتقاد.
استعراض مقالات الفرق المخالفة: بيان أقوال المخالفين (الجهمية، المعتزلة، الأشاعرة، الماتريدية، وغيرهم) ونسبتها إليهم من كتب المقالات الأصيلة.
شبهات المخالفين ومناقشتها: تفكيك شبهات الفرق واستعراض الردود النقلية والعقلية عليها وفق قواعد السلف ومنهج أهل السنة.
الأصول والقواعد العقدية المتصلة بالمسألة: ربط المسألة بالقواعد الكلية في الأسماء والصفات، أو الإيمان، أو القدر، أو الصحابة والنبوات.
الآثار المترتبة على المعتقد: بيان الأثر الإيماني والعملي والتربوي لتقرير هذا المعتقد وخطورة الانحراف عنه.
الخلاصة والتقرير: صياغة التقرير العقدي الصافي المحرر في المسألة.
## [1] منهجية الحاشية والإحالات ##
أولًا: خرّج الأحاديث والآثار العقدية تخريجًا دقيقًا مع بيان حكم أئمة الشأن عليها في الحاشية.
ثانيًا: اذكر مصدر كل قول ونقل في الحاشية من أمهات كتب السنة والاعتقاد (الرد على الجهمية، شرح أصول اعتقاد أهل السنة للالكائي، الإبانة، الحجة في بيان المحجة، مجموع الفتاوى) بذكر: اسم الكتاب، مؤلفه، الجزء، الصفحة.
ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا.`
};

// الاسم المترادف لأداة Markmap
CHAT_OUTPUT_TEMPLATES.markmap_mindmap = CHAT_OUTPUT_TEMPLATES.markmap;
CHAT_OUTPUT_TEMPLATES.graph_isnad = `نوع الشجرة: تشجير إسناد فقط.
لكل حديث أو أثر ورد في النتيجة عقدة مستقلة role حديث أو role أثر، وفي name نص مختصر من ألفاظ النتيجة يميّز ذلك الحديث أو الأثر.
إن ذُكر النبي صلى الله عليه وسلم فاجعله role نبي.
كل راوٍ عقدة بمعرّف ثابت لا يتكرر، والمدار عقدة واحدة تلتقي عندها الطرق.
role: حديث أو أثر أو نبي أو صحابي أو تابعي أو تابع التابعين أو مدار أو طريق أو ضعيف أو كتاب.
الطبقات من الأعلى إلى الأدنى: الحديث أو الأثر، ثم النبي، ثم الصحابة، ثم التابعون، ثم تابعو التابعين، ثم الكتاب.
السهم يصعد من الأدنى إلى الأعلى: source هو المتأخر (الكتاب أو التلميذ) و target هو المتقدم (الشيخ أو الصحابي أو النبي).
label صيغة الأداء كما في النتيجة.
لا تكرر المدار في كل طريق، ولا تترك حديثاً أو أثراً مذكوراً في النتيجة بلا عقدة.`;

CHAT_OUTPUT_TEMPLATES.graph_ilmi = `نوع الشجرة: تشجير خلاف علمي فقط، من أي علم ورد في النتيجة، بلا حصر في الفقه أو العقيدة.
الجذر role مسألة. تحته role قول لكل وجه. إن ذُكر قائل أو مذهب فاربطه role قائل. ثم role دليل على القول.
source الأعلى و target الفرع. الدليل المشترك عقدة واحدة.
لا تدرج رواة إلا إذا كان الراوي جزءاً من الدليل المذكور في النتيجة.`;

CHAT_OUTPUT_TEMPLATES.graph_istidlal = `نوع الشجرة: تشجير استدلال فقط، من الحكم إلى دليله ووجه دلالته وما ورد عليه.
role: مسألة أو دليل أو وجه الدلالة أو مناقشة أو جواب.
لا تدرج رواة إلا إذا كان الراوي نفسه مذكوراً في النتيجة كجزء من الدليل.`;

CHAT_OUTPUT_TEMPLATES.graph_munaqasha = `نوع الشجرة: تشجير مناقشة فقط بين طرفي الخلاف المذكورين في النتيجة.
الجذر role محل النزاع، ثم role دعوى لكل طرف، ثم دليله role دليل، ثم role مناقشة، ثم role جواب.
source الأعلى و target الفرع.`;

CHAT_OUTPUT_TEMPLATES.graph_aam = `نوع الشجرة: تشجير خلاف عام. يجمع الخلاف العلمي والأدلة والمناقشات والردود والإشكالات والأجوبة، من أي علم ورد في النتيجة، بلا حصر في الفقه أو العقيدة.
الجذر role مسألة.
ثم role قول لكل طرف.
ثم role دليل.
ثم role مناقشة على الدليل.
ثم role إشكال إن ورد إشكال.
ثم role جواب أو role رد.
ثم role ترجيح إن رُجّح قول في النتيجة.
source الأعلى و target الفرع. خذ الألفاظ من النتيجة فقط، ولا تُسقط دليلاً أو مناقشة أو رداً أو إشكالاً أو جواباً ذُكر فيها.`;

CHAT_OUTPUT_TEMPLATES.graph_fiqh = CHAT_OUTPUT_TEMPLATES.graph_ilmi;
CHAT_OUTPUT_TEMPLATES.graph_aqeedah = CHAT_OUTPUT_TEMPLATES.graph_ilmi;
CHAT_OUTPUT_TEMPLATES.force3d = CHAT_OUTPUT_TEMPLATES.graph_aam;

window.P2C_OUTPUT_TEMPLATES = window.P2C_OUTPUT_TEMPLATES || CHAT_OUTPUT_TEMPLATES;

function applyChatOutputTemplate(type, inputId) {
  const input = document.getElementById(inputId || 'chatInputText');
  if (!input) return;

  const templates = window.P2C_OUTPUT_TEMPLATES || CHAT_OUTPUT_TEMPLATES;
  const template = templates[type] || templates[type.replace('_mindmap', '')];
  if (!template) return;

  const currentVal = input.value.trim();
  if (currentVal.length > 0) {
    input.value = currentVal + '\n\n---\n\n' + template;
  } else {
    input.value = template;
  }

  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 260) + 'px';
  input.focus();
  input.scrollTop = input.scrollHeight;

  const labels = {
    fiqh: 'قالب الفقه والمقارنة المذهبية',
    tafsir: 'قالب التفسير وعلوم القرآن',
    hadith: 'قالب الحديث والتخريج الموسع',
    isnad: 'قالب دراسة الأسانيد ونقد الرجال',
    isnad_tree: 'أداة شجرة الأسانيد وشبكات الرواة (رسم المدارات)',
    markmap: 'أداة التشجير والخرائط الذهنية (Markmap)',
    markmap_mindmap: 'أداة التشجير والخرائط الذهنية (Markmap)',
    force3d: 'مشجر الأقوال',
    graph_isnad: 'تشجير إسناد',
    graph_ilmi: 'تشجير خلاف علمي',
    graph_fiqh: 'تشجير خلاف علمي',
    graph_aqeedah: 'تشجير خلاف علمي',
    graph_istidlal: 'تشجير استدلال',
    graph_munaqasha: 'تشجير مناقشة',
    graph_aam: 'تشجير خلاف عام',
    aqeedah: 'قالب العقيدة ومقالات الفرق'
  };

  if (typeof showToast === 'function') {
    showToast(`⚡ تم إدراج «${labels[type] || type}» في رسالة الشات بنجاح!`, 2500);
  }
}

// =============================================================================
// دوال تشغيل الأدوات التفاعلية (Markmap + Vis.js Network) داخل فقاعات الشات
// =============================================================================
window._chatMarkmaps = window._chatMarkmaps || {};
window._chatMarkmapRoots = window._chatMarkmapRoots || {};
window._chatG6 = window._chatG6 || {};
window._chatIsnads = window._chatIsnads || {};

const ECHART_FONTS = [
  ['Amiri', 'أميري'],
  ['Noto Naskh Arabic', 'نسخ نوتو'],
  ['Noto Kufi Arabic', 'كوفي نوتو'],
  ['Noto Sans Arabic', 'نوتو'],
  ['Cairo', 'القاهرة'],
  ['Tajawal', 'تجوال'],
  ['IBM Plex Sans Arabic', 'بلكس عربي'],
  ['Readex Pro', 'ريدكس'],
  ['Scheherazade New', 'شهرزاد'],
  ['Lateef', 'لطيف'],
  ['Aref Ruqaa', 'عارف رقعة'],
  ['El Messiri', 'المسيري'],
  ['Almarai', 'المراعي'],
  ['Markazi Text', 'مركزي'],
  ['Reem Kufi', 'ريم كوفي'],
  ['Changa', 'تشانغا'],
  ['Lemonada', 'ليمونادة'],
  ['Mirza', 'ميرزا'],
  ['Harmattan', 'هرمتان']
];

const ISLAMAP_SEA_COLOR = '#1d4e89';

const ECHART_BACKGROUNDS = [
  ['#f7f3ec', 'رملي'],
  ['#ffffff', 'أبيض'],
  ['#fbf6ea', 'كريمي'],
  ['#f3e6c8', 'عاجي'],
  ['#efe2c9', 'ورقي'],
  ['#f8efe9', 'زهري'],
  ['#e7f0f6', 'سماوي'],
  ['#2563eb', 'أزرق'],
  [ISLAMAP_SEA_COLOR, 'أزرق بحري'],
  ['#e7f3ec', 'نعناعي'],
  ['#f3eef8', 'لافندر'],
  ['#1c1917', 'ليلي'],
  ['#292524', 'فحمي'],
  ['#1e293b', 'كحلي'],
  ['#1c2b24', 'زيتي'],
  ['#3f2e22', 'بني']
];

const ECHART_KIND_LABELS = {
  multi: 'عدة رسوم مناسبة',
  bar: 'أعمدة',
  line: 'خطي',
  pie: 'دائري',
  scatter: 'نقطي',
  radar: 'رادار',
  heatmap: 'حراري',
  tree: 'شجرة',
  treemap: 'تريماب',
  sunburst: 'طبقات دائرية',
  sankey: 'سانكي',
  funnel: 'قمع',
  gauge: 'مقياس',
  graph: 'شبكة علاقات'
};

const ECHART_EXAMPLES = [
  { id: 'original', group: 'هذا الرسم', label: 'الأصلي', note: 'الألوان كما رسمها النموذج، بلا استبدال.' },
  { id: 'sand', group: 'ألوان الرسم', label: 'رملي', note: 'ألوان ترابية دافئة على الرسم نفسه.', colors: ['#8c6a43', '#c4a574', '#5c7a6e', '#a65d4e', '#6b7c93', '#b08968'] },
  { id: 'ink', group: 'ألوان الرسم', label: 'حبري', note: 'درجات الحبر والرماد على الرسم نفسه.', colors: ['#1c1917', '#57534e', '#a8a29e', '#44403c', '#78716c', '#d6d3d1'] },
  { id: 'sea', group: 'ألوان الرسم', label: 'بحري', note: 'أزرق وأخضر بحري على الرسم نفسه.', colors: ['#0f4c5c', '#1b6b7a', '#2a9d8f', '#5fa8d3', '#1d3557', '#457b9d'] },
  { id: 'earth', group: 'ألوان الرسم', label: 'ترابي', note: 'بني وأخضر وذهبي على الرسم نفسه.', colors: ['#6b3e26', '#a65d3f', '#c4a35a', '#3f6b4a', '#8c5a3c', '#d4b483'] },
  { id: 'night', group: 'ألوان الرسم', label: 'ليلي', note: 'ألوان فاتحة تُقرأ على الخلفية الداكنة.', colors: ['#f5d0a9', '#7eb6d6', '#e07a5f', '#81b29a', '#f2cc8f', '#e6e1d8'] }
];

function echartEscape(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function echartExampleOptions() {
  const groups = [];
  ECHART_EXAMPLES.forEach((item) => {
    let group = groups.find((entry) => entry.label === item.group);
    if (!group) {
      group = { label: item.group, items: [] };
      groups.push(group);
    }
    group.items.push(item);
  });
  return groups.map((group) => `
    <optgroup label="${echartEscape(group.label)}">
      ${group.items.map((item) => `<option value="${item.id}"${item.id === 'original' ? ' selected' : ''}>${echartEscape(item.label)}</option>`).join('')}
    </optgroup>
  `).join('');
}

function echartExample(id) {
  return ECHART_EXAMPLES.find((item) => item.id === id) || ECHART_EXAMPLES[0];
}

function echartInk(color) {
  const hex = String(color || '').replace('#', '');
  if (hex.length < 6) return '#44403c';
  const red = parseInt(hex.slice(0, 2), 16);
  const green = parseInt(hex.slice(2, 4), 16);
  const blue = parseInt(hex.slice(4, 6), 16);
  const light = (0.299 * red + 0.587 * green + 0.114 * blue) / 255;
  return light > 0.62 ? '#44403c' : '#f5f5f4';
}

function ensureEchartFont(name) {
  const id = `echart-font-${String(name).replace(/\s+/g, '-')}`;
  if (!document.getElementById(id)) {
    const link = document.createElement('link');
    link.id = id;
    link.rel = 'stylesheet';
    link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(name)}:wght@300;400;500;700;800&display=swap`;
    document.head.appendChild(link);
  }
  const spec = `400 16px "${name}"`;
  return (document.fonts && document.fonts.load) ? document.fonts.load(spec).catch(() => {}) : Promise.resolve();
}

function echartTextStyle(wrapper) {
  const font = wrapper.querySelector('[data-echart-font]');
  const sizeEl = wrapper.querySelector('[data-echart-size]');
  const weightEl = wrapper.querySelector('[data-echart-weight]');
  const family = font ? font.value : 'Amiri';
  const size = Number(sizeEl && sizeEl.value) || 16;
  const weight = (weightEl && weightEl.value) || '700';
  return {
    fontFamily: `"${family}", Amiri, Tajawal, sans-serif`,
    fontSize: size,
    fontWeight: weight
  };
}

function applyEchartBackground(wrapper) {
  const chart = wrapper && wrapper._echart;
  if (!wrapper) return;
  const select = wrapper.querySelector('[data-echart-bg]');
  const color = (select && select.value) || '#f7f3ec';
  const ink = echartInk(color);
  wrapper._bg = color;
  const host = wrapper.querySelector('.echart-host');
  if (host) host.style.background = color;
  if (select) {
    select.style.background = color;
    select.style.color = ink;
    const trigger = select.closest('.theme-select') && select.closest('.theme-select').querySelector('.theme-select-trigger');
    if (trigger) {
      trigger.style.background = color;
      trigger.style.color = ink;
    }
  }
  if (chart) chart.setOption({ backgroundColor: color });
}

function applyEchartType(wrapper) {
  const chart = wrapper && wrapper._echart;
  if (!chart) return Promise.resolve();
  const font = wrapper.querySelector('[data-echart-font]');
  const family = font ? font.value : 'Amiri';
  const text = echartTextStyle(wrapper);
  const small = Object.assign({}, text, { fontSize: Math.max(11, text.fontSize - 2) });
  return ensureEchartFont(family).then(() => {
    if (!wrapper.isConnected || wrapper._echart !== chart) return;
    const current = chart.getOption() || {};
    const patch = { textStyle: text, tooltip: { textStyle: text } };
    ['xAxis', 'yAxis', 'radiusAxis', 'angleAxis'].forEach((key) => {
      if (!Array.isArray(current[key])) return;
      patch[key] = current[key].map(() => ({ axisLabel: small, nameTextStyle: text }));
    });
    if (Array.isArray(current.title)) {
      patch.title = current.title.map(() => ({
        textStyle: Object.assign({}, text, { fontSize: text.fontSize + 2 }),
        subtextStyle: small
      }));
    }
    if (Array.isArray(current.legend)) patch.legend = current.legend.map(() => ({ textStyle: text }));
    if (Array.isArray(current.radar)) patch.radar = current.radar.map(() => ({ axisName: small, name: small }));
    if (Array.isArray(current.series)) patch.series = current.series.map(() => ({ label: small }));
    chart.setOption(patch);
    chart.resize();
  });
}

function paintEchartSeries(series, palette, index) {
  const color = palette[index % palette.length];
  const next = { itemStyle: { color }, lineStyle: { color } };
  if (series && series.areaStyle) next.areaStyle = { color };
  const kind = series && series.type;
  if (Array.isArray(series.data) && /pie|funnel/.test(kind || '')) {
    next.data = series.data.map((item, itemIndex) => {
      const slice = palette[itemIndex % palette.length];
      if (item && typeof item === 'object' && !Array.isArray(item)) return { itemStyle: { color: slice } };
      return item;
    });
    delete next.itemStyle;
  }
  return next;
}

function applyEchartExample(wrapper) {
  const chart = wrapper && wrapper._echart;
  if (!chart || !wrapper._option) return;
  const select = wrapper.querySelector('[data-echart-example]');
  const example = echartExample(select && select.value);
  echartWriteDetail(wrapper);
  if (!example.colors) {
    chart.setOption(JSON.parse(JSON.stringify(wrapper._option)), { notMerge: true });
    applyEchartBackground(wrapper);
    applyEchartType(wrapper);
    return;
  }
  const current = chart.getOption() || {};
  const series = (current.series || []).map((item, index) => paintEchartSeries(item, example.colors, index));
  chart.setOption({ color: example.colors, series });
  chart.resize();
}

function resetEchartView(wrapper) {
  const chart = wrapper && wrapper._echart;
  if (!chart || !wrapper._option) return;
  chart.setOption(JSON.parse(JSON.stringify(wrapper._option)), { notMerge: true });
  applyEchartExample(wrapper);
}

function fitEchart(wrapper) {
  const chart = wrapper && wrapper._echart;
  if (!chart) return;
  chart.resize();
  const zoom = (chart.getOption() || {}).dataZoom || [];
  zoom.forEach((_, index) => {
    chart.dispatchAction({ type: 'dataZoom', dataZoomIndex: index, start: 0, end: 100 });
  });
}

function echartVisualTitle(wrapper, fallback) {
  const titleNode = wrapper && wrapper.querySelector('.chart-render-title span:last-child');
  return ((titleNode && titleNode.textContent) || fallback).trim() || fallback;
}

async function shareEchartImage(wrapper) {
  const chart = wrapper && wrapper._echart;
  if (!chart || typeof window.shareCapturedImage !== 'function') return;
  const url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: wrapper._bg || '#f7f3ec' });
  let blob = null;
  try { blob = await (await fetch(url)).blob(); } catch (err) { blob = null; }
  await window.shareCapturedImage(blob, echartVisualTitle(wrapper, 'رسم'), 'تعذر تجهيز صورة الرسم للمشاركة');
}

function downloadEchartShot(wrapper) {
  const chart = wrapper && wrapper._echart;
  if (!chart) return;
  const title = echartVisualTitle(wrapper, 'رسم');
  const url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: wrapper._bg || '#f7f3ec' });
  const link = document.createElement('a');
  link.href = url;
  link.download = `${title}.png`;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function echartWriteDetail(wrapper) {
  const detail = wrapper && wrapper.querySelector('.echart-detail');
  if (!detail) return;
  const example = echartExample((wrapper.querySelector('[data-echart-example]') || {}).value);
  const kind = ECHART_KIND_LABELS[wrapper._kind] || '';
  detail.textContent = kind ? `النوع: ${kind}. ${example.note}` : example.note;
}

function echartCurrentKind(option) {
  const series = [].concat((option && option.series) || []);
  const kind = series[0] && series[0].type;
  return ECHART_KIND_LABELS[kind] ? kind : 'bar';
}

function echartKindOptions(selected) {
  return Object.keys(ECHART_KIND_LABELS)
    .filter((id) => id !== 'multi')
    .map((id) => `<option value="${id}"${id === selected ? ' selected' : ''}>${echartEscape(ECHART_KIND_LABELS[id])}</option>`)
    .join('');
}

function echartTitleText(option) {
  const title = option && option.title;
  const item = Array.isArray(title) ? title[0] : title;
  return (item && item.text) || 'رسم';
}

function echartRows(option) {
  const opt = option || {};
  const seriesList = [].concat(opt.series || []);
  const xAxis = [].concat(opt.xAxis || [])[0] || {};
  const yAxis = [].concat(opt.yAxis || [])[0] || {};
  const categories = Array.isArray(xAxis.data) ? xAxis.data.map(String)
    : (Array.isArray(yAxis.data) ? yAxis.data.map(String) : []);
  const rows = [];
  const push = (name, value, series) => {
    const label = String(name || '').trim();
    if (!label) return;
    rows.push({ name: label, value: Number(value) || 0, series: series || '' });
  };
  seriesList.forEach((series) => {
    const name = series.name || '';
    const data = Array.isArray(series.data) ? series.data : [];
    if (series.type === 'radar') {
      const indicators = [].concat((opt.radar && opt.radar.indicator) || []);
      data.forEach((item) => {
        const values = (item && item.value) || [];
        indicators.forEach((ind, index) => push((ind && ind.name) || ind, values[index], (item && item.name) || name));
      });
      return;
    }
    if (series.type === 'heatmap') {
      data.forEach((item) => {
        if (!Array.isArray(item)) return;
        const x = categories[item[0]] || item[0];
        push(`${x} / ${item[1]}`, item[2], name);
      });
      return;
    }
    if (series.type === 'tree' || series.type === 'treemap' || series.type === 'sunburst') {
      const walk = (node) => {
        if (!node || typeof node !== 'object') return;
        if (node.name != null && node.value != null) push(node.name, node.value, name);
        (node.children || []).forEach(walk);
      };
      data.forEach(walk);
      return;
    }
    if (series.type === 'sankey') {
      (series.links || []).forEach((link) => push(`${link.source} ← ${link.target}`, link.value, name));
      return;
    }
    if (series.type === 'graph') {
      const links = series.links || series.edges || [];
      if (links.length) links.forEach((link) => push(`${link.source} — ${link.target}`, link.value || 1, name));
      else data.forEach((node) => push(node.name || node.id, node.value || 1, name));
      return;
    }
    data.forEach((item, index) => {
      if (typeof item === 'number') push(categories[index] || name || index + 1, item, name);
      else if (Array.isArray(item)) push(categories[index] || item[0], item[1], name);
      else if (item && typeof item === 'object') push(item.name || categories[index] || index + 1, item.value, name);
    });
  });
  return rows;
}

function buildEchartOption(source, type) {
  const rows = echartRows(source);
  if (!rows.length) return null;
  const title = echartTitleText(source);
  const names = [];
  rows.forEach((row) => { if (!names.includes(row.name)) names.push(row.name); });
  const groups = [];
  rows.forEach((row) => {
    let group = groups.find((item) => item.name === row.series);
    if (!group) {
      group = { name: row.series, rows: [] };
      groups.push(group);
    }
    group.rows.push(row);
  });
  const split = groups.length > 1 && groups.every((group) => group.name);
  const base = {
    backgroundColor: source.backgroundColor || '#f7f3ec',
    title: { text: title, right: 0 },
    textStyle: { fontFamily: 'Amiri, Tajawal, sans-serif', fontSize: 16, fontWeight: '700' }
  };
  const valueOf = (group, name) => {
    const found = group.rows.find((row) => row.name === name);
    return found ? found.value : 0;
  };
  if (type === 'bar' || type === 'line' || type === 'scatter') {
    const categories = split ? names : rows.map((row) => row.name);
    const unique = [];
    categories.forEach((name) => { if (!unique.includes(name)) unique.push(name); });
    const packs = split ? groups : [{ name: '', rows }];
    return Object.assign(base, {
      tooltip: { trigger: 'axis' },
      legend: split ? { bottom: 0 } : undefined,
      xAxis: { type: 'category', data: unique },
      yAxis: { type: 'value' },
      series: packs.map((group) => ({
        name: group.name || undefined,
        type,
        data: unique.map((name, index) => (type === 'scatter' ? [index, valueOf(group, name)] : valueOf(group, name)))
      }))
    });
  }
  if (type === 'pie' || type === 'funnel') {
    const data = split
      ? groups.map((group) => ({ name: group.name, value: group.rows.reduce((sum, row) => sum + row.value, 0) }))
      : rows.map((row) => ({ name: row.name, value: row.value }));
    return Object.assign(base, {
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type,
        data,
        radius: type === 'pie' ? '62%' : undefined,
        left: type === 'funnel' ? '12%' : undefined,
        width: type === 'funnel' ? '76%' : undefined
      }]
    });
  }
  if (type === 'radar') {
    const packs = split ? groups : [{ name: title, rows }];
    const indicators = names.map((name) => ({
      name,
      max: Math.max(1, ...rows.filter((row) => row.name === name).map((row) => row.value)) * 1.15
    }));
    return Object.assign(base, {
      tooltip: {},
      legend: { bottom: 0 },
      radar: { indicator: indicators },
      series: [{
        type: 'radar',
        data: packs.map((group) => ({ name: group.name || title, value: names.map((name) => valueOf(group, name)) }))
      }]
    });
  }
  if (type === 'gauge') {
    const top = rows.slice().sort((a, b) => b.value - a.value)[0];
    return Object.assign(base, {
      series: [{ type: 'gauge', min: 0, max: Math.max(top.value, 1), detail: { formatter: '{value}' }, data: [{ name: top.name, value: top.value }] }]
    });
  }
  if (type === 'heatmap') {
    const max = Math.max(1, ...rows.map((row) => row.value));
    return Object.assign(base, {
      tooltip: { position: 'top' },
      xAxis: { type: 'category', data: names },
      yAxis: { type: 'category', data: ['القيمة'] },
      visualMap: { min: 0, max, calculable: true, orient: 'horizontal', left: 'center', bottom: 0 },
      series: [{ type: 'heatmap', data: names.map((name, index) => [index, 0, valueOf({ rows }, name)]), label: { show: true } }]
    });
  }
  if (type === 'tree') {
    return Object.assign(base, {
      series: [{
        type: 'tree',
        data: [{ name: title, children: rows.map((row) => ({ name: `${row.name}: ${row.value}` })) }],
        top: '12%', bottom: '12%', left: '18%', right: '22%',
        symbolSize: 9,
        label: { position: 'right' }
      }]
    });
  }
  if (type === 'treemap' || type === 'sunburst') {
    return Object.assign(base, {
      series: [{
        type,
        data: rows.map((row) => ({ name: row.name, value: Math.abs(row.value) })),
        radius: type === 'sunburst' ? ['12%', '78%'] : undefined
      }]
    });
  }
  if (type === 'sankey') {
    const sink = names.includes(title) ? `${title} · المجموع` : title;
    return Object.assign(base, {
      series: [{
        type: 'sankey',
        data: [{ name: sink }].concat(names.map((name) => ({ name }))),
        links: rows.map((row) => ({ source: row.name, target: sink, value: Math.max(Math.abs(row.value) || 0, 0.01) })),
        emphasis: { focus: 'adjacency' },
        lineStyle: { curveness: 0.5 }
      }]
    });
  }
  if (type === 'graph') {
    return Object.assign(base, {
      series: [{
        type: 'graph',
        layout: 'force',
        roam: true,
        label: { show: true },
        force: { repulsion: 220 },
        data: [{ name: title, id: 'center', symbolSize: 46 }].concat(rows.map((row, index) => ({
          name: row.name, id: `n${index}`, value: row.value, symbolSize: 26
        }))),
        links: rows.map((row, index) => ({ source: 'center', target: `n${index}` }))
      }]
    });
  }
  return null;
}

function applyEchartKind(wrapper) {
  const chart = wrapper && wrapper._echart;
  const select = wrapper && wrapper.querySelector('[data-echart-kind]');
  const type = select && select.value;
  if (!chart || !wrapper._sourceOption || !type || type === wrapper._kind) return;
  const sourceKind = echartCurrentKind(wrapper._sourceOption);
  const next = type === sourceKind
    ? JSON.parse(JSON.stringify(wrapper._sourceOption))
    : buildEchartOption(wrapper._sourceOption, type);
  if (!next) {
    if (select) {
      select.value = wrapper._kind || sourceKind;
      select.dispatchEvent(new CustomEvent('theme-select-sync'));
    }
    if (typeof showToast === 'function') showToast('تعذر تحويل هذا الرسم إلى النوع المختار');
    return;
  }
  wrapper._kind = type;
  wrapper._option = JSON.parse(JSON.stringify(next));
  chart.setOption(next, { notMerge: true });
  const code = wrapper.querySelector('.echart-code code');
  if (code) code.textContent = JSON.stringify(next, null, 2);
  applyEchartBackground(wrapper);
  const example = wrapper.querySelector('[data-echart-example]');
  if (example && example.value !== 'original') applyEchartExample(wrapper);
  else applyEchartType(wrapper);
  echartWriteDetail(wrapper);
  requestAnimationFrame(() => { if (wrapper._echart) wrapper._echart.resize(); });
}

function renderEchartsBlocks(container) {
  if (!container || !window.echarts) return;
  container.querySelectorAll('pre code').forEach((codeEl, idx) => {
    const cls = codeEl.className || '';
    if (!/echarts/i.test(cls)) return;
    const pre = codeEl.closest('pre');
    if (!pre || pre.dataset.renderedEcharts === '1') return;
    let option;
    try {
      option = JSON.parse(codeEl.innerText.trim().replace(/,\s*([}\]])/g, '$1'));
    } catch (e) {
      return;
    }
    if (!option || typeof option !== 'object') return;
    if (option.option && typeof option.option === 'object') option = option.option;
    pre.dataset.renderedEcharts = '1';
    const hostId = `echart_${Date.now()}_${idx}`;
    const title = (option.title && (option.title.text || option.title.subtext)) || 'رسم ECharts';
    const box = document.createElement('div');
    box.className = 'chart-render-wrapper echart-render-wrapper';
    box.innerHTML = `
      <div class="chart-render-header">
        <div class="chart-render-title"><span>📈</span><span>${escapeHtml(String(title))}</span></div>
        <div class="force3d-tools">
          <label class="force3d-example-label">
            <span>النوع</span>
            <select data-echart-kind dir="rtl">${echartKindOptions(echartCurrentKind(option))}</select>
          </label>
          <label class="force3d-example-label">
            <span>المثال</span>
            <select data-echart-example dir="rtl">${echartExampleOptions()}</select>
          </label>
          <label class="force3d-example-label">
            <span>الخط</span>
            <select data-echart-font dir="rtl">
              ${ECHART_FONTS.map(([name, label]) => `<option value="${echartEscape(name)}"${name === 'Amiri' ? ' selected' : ''}>${echartEscape(label)}</option>`).join('')}
            </select>
          </label>
          <label class="force3d-example-label">
            <span>الحجم</span>
            <select data-echart-size dir="rtl">
              ${[12, 14, 16, 18, 20, 24, 28, 32].map((size) => `<option value="${size}"${size === 16 ? ' selected' : ''}>${size}</option>`).join('')}
            </select>
          </label>
          <label class="force3d-example-label">
            <span>المقاس</span>
            <select data-echart-weight dir="rtl">
              <option value="300">نحيف</option>
              <option value="400">عادي</option>
              <option value="500">متوسط</option>
              <option value="700" selected>عريض</option>
              <option value="800">ثقيل</option>
            </select>
          </label>
          <label class="force3d-example-label">
            <span>الخلفية</span>
            <select data-echart-bg dir="rtl">
              ${ECHART_BACKGROUNDS.map(([color, label]) => `<option value="${color}"${color === '#f7f3ec' ? ' selected' : ''}>${echartEscape(label)}</option>`).join('')}
            </select>
          </label>
          <button type="button" class="btn-chart-type" data-echart-share="1" title="مشاركة">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4"/></svg>
            <span>مشاركة</span>
          </button>
          <button type="button" class="btn-chart-type" data-echart-fit="1">ملاءمة</button>
          <button type="button" class="btn-chart-type" data-echart-reset="1">إعادة</button>
          <button type="button" class="btn-chart-type force3d-shot" data-echart-shot="1" title="لقطة للرسم">
            <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M9.2 4.5 10.6 6h2.8l1.4-1.5H17a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-11a2 2 0 0 1 2-2h2.2ZM12 8.2A3.8 3.8 0 1 0 15.8 12 3.8 3.8 0 0 0 12 8.2Zm0 1.6A2.2 2.2 0 1 1 9.8 12 2.2 2.2 0 0 1 12 9.8Z"/></svg>
            <span>لقطة</span>
          </button>
          <button type="button" class="btn-chart-type" data-echart-expand="1">تكبير</button>
          <button type="button" class="btn-chart-type echart-close" data-echart-close="1">إغلاق</button>
          <button type="button" class="btn-chart-type" data-echart-code="1">الكود</button>
        </div>
      </div>
      <div id="${hostId}" class="echart-host"></div>
      <div class="echart-detail">${echartEscape(ECHART_EXAMPLES[0].note)}</div>
      <div class="echart-code" hidden></div>
    `;
    pre.parentNode.insertBefore(box, pre);
    pre.hidden = false;
    box.querySelector('.echart-code').appendChild(pre);
    try {
      const chart = window.echarts.init(document.getElementById(hostId));
      option.backgroundColor = option.backgroundColor || '#f7f3ec';
      option.textStyle = Object.assign({ fontFamily: 'Amiri, Tajawal, sans-serif', fontSize: 16, fontWeight: '700' }, option.textStyle || {});
      box._option = JSON.parse(JSON.stringify(option));
      box._sourceOption = JSON.parse(JSON.stringify(option));
      box._kind = echartCurrentKind(option);
      chart.setOption(option);
      box._echart = chart;
      window._chatEcharts = window._chatEcharts || {};
      window._chatEcharts[hostId] = chart;
      applyEchartBackground(box);
      applyEchartType(box);
      echartWriteDetail(box);
      setTimeout(() => chart.resize(), 80);
    } catch (err) {
      console.warn('ECharts render error:', err);
    }
  });
}

function setEchartExpanded(wrapper, expanded) {
  const chart = wrapper && wrapper._echart;
  if (!wrapper) return;
  if (expanded) {
    if (!wrapper.classList.contains('is-expanded')) {
      wrapper._homeParent = wrapper.parentNode;
      wrapper._homeNext = wrapper.nextSibling;
      document.body.appendChild(wrapper);
    }
    wrapper.classList.add('is-expanded');
  } else {
    wrapper.classList.remove('is-expanded');
    if (wrapper._homeParent) wrapper._homeParent.insertBefore(wrapper, wrapper._homeNext);
  }
  requestAnimationFrame(() => { if (chart) chart.resize(); });
}

if (!window._echartClicksBound) {
  window._echartClicksBound = true;
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-echart-share], [data-echart-fit], [data-echart-reset], [data-echart-shot], [data-echart-expand], [data-echart-close], [data-echart-code]');
    if (!button) return;
    const wrapper = button.closest('.echart-render-wrapper');
    if (!wrapper) return;
    event.preventDefault();
    if (button.dataset.echartFit) {
      fitEchart(wrapper);
      return;
    }
    if (button.dataset.echartReset) {
      resetEchartView(wrapper);
      return;
    }
    if (button.dataset.echartShare) {
      shareEchartImage(wrapper);
      return;
    }
    if (button.dataset.echartShot) {
      downloadEchartShot(wrapper);
      return;
    }
    if (button.dataset.echartCode) {
      const code = wrapper.querySelector('.echart-code');
      if (code) code.hidden = !code.hidden;
      return;
    }
    setEchartExpanded(wrapper, button.dataset.echartClose ? false : !wrapper.classList.contains('is-expanded'));
  });
  document.addEventListener('change', (event) => {
    const control = event.target.closest('[data-echart-kind], [data-echart-example], [data-echart-font], [data-echart-size], [data-echart-weight], [data-echart-bg]');
    if (!control) return;
    const wrapper = control.closest('.echart-render-wrapper');
    if (!wrapper) return;
    if (control.matches('[data-echart-kind]')) {
      applyEchartKind(wrapper);
      return;
    }
    if (control.matches('[data-echart-bg]')) {
      applyEchartBackground(wrapper);
      return;
    }
    if (control.matches('[data-echart-example]')) {
      applyEchartExample(wrapper);
      return;
    }
    applyEchartType(wrapper);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const open = document.querySelector('.echart-render-wrapper.is-expanded');
    if (open) setEchartExpanded(open, false);
  });
}

function autoRenderChatInteractiveWidgets(container) {
  if (!container) return;
  renderEchartsBlocks(container);
  renderIslamapBlocks(container);

  // 1. توليد وتشغيل خرائط التشجير والخرائط الذهنية Markmap التفاعلية
  if (window.markmap && window.markmap.Markmap) {
    container.querySelectorAll('.message-bubble.assistant pre code').forEach((codeEl, idx) => {
      const cls = codeEl.className || '';
      const rawText = codeEl.innerText.trim();
      const isMarkmap = cls.includes('markmap') || cls.includes('mindmap') || (rawText.startsWith('# ') && rawText.includes('## '));
      if (!isMarkmap) return;

      const pre = codeEl.closest('pre');
      if (!pre || pre.dataset.renderedMarkmap === '1') return;
      pre.dataset.renderedMarkmap = '1';

      const mapId = 'chat_markmap_' + Date.now() + '_' + idx;
      const widget = document.createElement('div');
      widget.className = 'isnad-render-wrapper chat-markmap-wrapper';
      widget.innerHTML = `
        <div class="isnad-render-header">
          <div class="isnad-render-title">
            <span>🧠</span>
            <span>أداة التشجير والخرائط الذهنية (Markmap) — عرض الأقوال والاختلافات</span>
          </div>
          <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
            <button type="button" class="btn-msg-export" data-tree-switch="${mapId}" data-engine="markmap" style="font-size:11px; padding:3px 8px; background: var(--accent-clay); color: #fff;" onclick="showChatTreeEngine('${mapId}', 'markmap')">تشجير</button>
            <button type="button" class="btn-msg-export" data-tree-switch="${mapId}" data-engine="g6" style="font-size:11px; padding:3px 8px;" onclick="showChatTreeEngine('${mapId}', 'g6')">تشجير مفرغ</button>
            <button type="button" class="btn-msg-export" style="font-size:11px; padding:3px 8px;" onclick="zoomChatMarkmap('${mapId}', 1.25)" title="تكبير الخريطة">🔍+ تكبير</button>
            <button type="button" class="btn-msg-export" style="font-size:11px; padding:3px 8px;" onclick="zoomChatMarkmap('${mapId}', 0.8)" title="تصغير الخريطة">🔍- تصغير</button>
            <button type="button" class="btn-msg-export" style="font-size:11px; padding:3px 8px;" onclick="fitChatMarkmap('${mapId}')" title="ملاءمة الشاشة">⛶ ملاءمة</button>
            <button type="button" class="btn-msg-export" style="font-size:11px; padding:3px 8px;" onclick="toggleChatCodeBlock('${mapId}_code')" title="عرض الكود المصدر">📝 الكود</button>
          </div>
        </div>
        <div style="height: 380px; width: 100%; border: 1px solid var(--border-subtle); border-radius: 6px; background: var(--bg-muted); overflow: hidden; position: relative;">
          <svg id="${mapId}" style="width: 100%; height: 100%; display: block;"></svg>
          <div id="${mapId}_g6" style="display: none; width: 100%; height: 100%;"></div>
        </div>
        <div id="${mapId}_code" style="display: none; margin-top: 8px;"></div>
      `;

      pre.parentNode.insertBefore(widget, pre);
      const codeHolder = document.getElementById(`${mapId}_code`);
      if (codeHolder) {
        codeHolder.appendChild(pre);
      }

      try {
        const { Transformer, Markmap } = window.markmap;
        const transformer = new Transformer();
        const { root } = transformer.transform(rawText);
        const svgEl = document.getElementById(mapId);
        if (svgEl) {
          const mm = Markmap.create(svgEl, { autoFit: true, duration: 300 }, root);
          window._chatMarkmaps[mapId] = mm;
          window._chatMarkmapRoots[mapId] = root;
        }
      } catch (err) {
        console.warn('Markmap render error in chat:', err);
        pre.style.display = 'block';
      }
    });
  }

  // 2. توليد وتشغيل شجرة الأسانيد وشبكات الرواة Vis.js Network في رسائل الشات
  if (window.vis && window.vis.Network) {
    container.querySelectorAll('.message-bubble.assistant table').forEach((table, idx) => {
      if (table.dataset.renderedIsnad === '1') return;
      const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
      const isHadithTable = headers.some(h => /راوي|الراوي|الشيخ|السند|طريق|المدار|الصحابي|التابعي|الإسناد/i.test(h));
      if (!isHadithTable) return;

      const rows = Array.from(table.querySelectorAll('tbody tr'));
      if (rows.length < 2) return;

      table.dataset.renderedIsnad = '1';

      const nodes = [];
      const edges = [];
      let prevId = null;

      rows.forEach((r, rIdx) => {
        const cells = Array.from(r.querySelectorAll('td')).map(td => td.innerText.trim());
        const name = cells[1] || cells[0];
        const status = cells[2] || '';
        const reception = cells[3] || 'عن';
        if (name && name.length >= 2 && !/^\d+$/.test(name)) {
          const id = rIdx + 1;
          const isMadar = /مدار|أصل/i.test(name) || /مدار/i.test(status);
          const isSahabi = /رضي الله عنه|صحابي/i.test(name) || /صحابي/i.test(status);
          const isWeak = /ضعيف|متروك|منكر|مجهول|كذاب|وضاع/i.test(status);

          let nodeColor = '#059669'; // ثقة/عدل
          if (isMadar) nodeColor = '#D97706'; // مدار (ذهبي/كهرماني)
          else if (isSahabi) nodeColor = '#2563EB'; // صحابي (أزرق)
          else if (isWeak) nodeColor = '#DC2626'; // ضعيف (أحمر)

          nodes.push({
            id: id,
            label: name.length > 25 ? name.substring(0, 23) + '..' : name,
            shape: isMadar ? 'box' : 'ellipse',
            color: nodeColor,
            title: `الراوي: ${name}\nالحال: ${status || 'عدل ضابط'}`
          });

          if (prevId !== null) {
            edges.push({
              from: prevId,
              to: id,
              label: reception.length < 15 ? reception : 'عن',
              arrows: 'to'
            });
          }
          prevId = id;
        }
      });

      if (nodes.length >= 2) {
        const treeId = 'chat_isnad_' + Date.now() + '_' + idx;
        const wrapper = document.createElement('div');
        wrapper.className = 'isnad-render-wrapper chat-isnad-wrapper';
        wrapper.innerHTML = `
          <div class="isnad-render-header">
            <div class="isnad-render-title">
              <span>🌳</span>
              <span>أداة شجرة الأسانيد وشبكات الرواة (رسم المدارات والاتصال)</span>
            </div>
            <div style="display: flex; gap: 6px; align-items: center;">
              <span style="font-size: 11px; color: var(--text-muted);">عُقد الرواة: ${nodes.length}</span>
              <button type="button" class="btn-msg-export" style="font-size:11px; padding:3px 8px;" onclick="fitChatIsnad('${treeId}')" title="إعادة التمركز">⛶ ضبط</button>
            </div>
          </div>
          <div id="${treeId}" class="isnad-canvas-container" style="height: 300px; width: 100%;"></div>
        `;
        table.parentNode.insertBefore(wrapper, table.nextSibling);

        const treeContainer = document.getElementById(treeId);
        if (treeContainer) {
          const network = new vis.Network(treeContainer, {
            nodes: new vis.DataSet(nodes),
            edges: new vis.DataSet(edges)
          }, {
            layout: { hierarchical: { direction: 'UD', sortMethod: 'directed', levelSeparation: 70, nodeSpacing: 120 } },
            nodes: { font: { face: 'Amiri, Tajawal, sans-serif', size: 13, color: '#FFFFFF' }, borderWidth: 2, margin: 8 },
            edges: { arrows: 'to', font: { face: 'Tajawal, sans-serif', size: 10, align: 'middle' }, color: '#B45309', smooth: true },
            physics: { enabled: false }
          });
          window._chatIsnads[treeId] = network;
        }
      }
    });
  }

  if (typeof window.renderForce3dBlocks === 'function') {
    window.renderForce3dBlocks(container);
  }
}

function g6TreeLabel(value) {
  const clean = String(value || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  if (!clean) return '—';
  return clean.length > 42 ? clean.slice(0, 40) + '…' : clean;
}

function markmapToG6(node, path) {
  const label = g6TreeLabel(node && (node.content || (node.payload && node.payload.content)));
  const children = Array.isArray(node && node.children) ? node.children : [];
  const row = { id: path, label };
  if (children.length) row.children = children.map((child, index) => markmapToG6(child, path + '-' + index));
  return row;
}

function chatTreeEngine(mapId) {
  const host = document.getElementById(mapId + '_g6');
  return host && host.style.display !== 'none' ? 'g6' : 'markmap';
}

function renderChatG6(mapId) {
  const existing = window._chatG6 && window._chatG6[mapId];
  if (existing) {
    const box = existing.getContainer();
    existing.changeSize(box.clientWidth, box.clientHeight);
    existing.fitView(24);
    return;
  }
  const root = window._chatMarkmapRoots && window._chatMarkmapRoots[mapId];
  const host = document.getElementById(mapId + '_g6');
  if (!root || !host || !window.G6 || typeof window.G6.TreeGraph !== 'function') return;
  const data = markmapToG6(root, 'root');
  const graph = new window.G6.TreeGraph({
    container: host,
    width: host.clientWidth || 640,
    height: host.clientHeight || 380,
    fitView: true,
    fitViewPadding: 24,
    animate: true,
    modes: { default: ['drag-canvas', 'zoom-canvas', 'collapse-expand'] },
    defaultNode: {
      type: 'rect',
      style: { fill: '#f4efe6', stroke: '#b7aa96', radius: 8, lineWidth: 1 },
      labelCfg: {
        position: 'center',
        style: { fill: '#1c1917', fontSize: 13, fontFamily: 'Almarai, Amiri, sans-serif', textAlign: 'center' }
      }
    },
    defaultEdge: { type: 'cubic-horizontal', style: { stroke: '#a8a29e' } },
    layout: {
      type: 'compactBox',
      direction: 'RL',
      getId: (node) => node.id,
      getHeight: () => 32,
      getWidth: (node) => Math.min(380, Math.max(104, String(node.label || '').length * 13 + 28)),
      getVGap: () => 14,
      getHGap: () => 48
    }
  });
  graph.data(data);
  graph.render();
  graph.fitView(24);
  window._chatG6[mapId] = graph;
}

function showChatTreeEngine(mapId, engine) {
  const svg = document.getElementById(mapId);
  const host = document.getElementById(mapId + '_g6');
  if (svg) svg.style.display = engine === 'g6' ? 'none' : 'block';
  if (host) host.style.display = engine === 'g6' ? 'block' : 'none';
  document.querySelectorAll('[data-tree-switch="' + mapId + '"]').forEach((button) => {
    const active = button.dataset.engine === engine;
    button.style.background = active ? 'var(--accent-clay)' : '';
    button.style.color = active ? '#fff' : '';
  });
  if (engine === 'g6') renderChatG6(mapId);
  else fitChatMarkmap(mapId);
}

function zoomChatMarkmap(mapId, factor) {
  if (chatTreeEngine(mapId) === 'g6') {
    const graph = window._chatG6 && window._chatG6[mapId];
    if (!graph) return;
    const box = graph.getContainer().getBoundingClientRect();
    graph.zoom(factor, { x: box.width / 2, y: box.height / 2 });
    return;
  }
  const mm = window._chatMarkmaps && window._chatMarkmaps[mapId];
  if (mm && typeof mm.rescale === 'function') mm.rescale(factor);
}

function fitChatMarkmap(mapId) {
  if (chatTreeEngine(mapId) === 'g6') {
    const graph = window._chatG6 && window._chatG6[mapId];
    if (graph) graph.fitView(24);
    return;
  }
  const mm = window._chatMarkmaps && window._chatMarkmaps[mapId];
  if (mm && typeof mm.fit === 'function') mm.fit();
}

function fitChatIsnad(treeId) {
  const net = window._chatIsnads && window._chatIsnads[treeId];
  if (net && typeof net.fit === 'function') {
    net.fit();
  }
}

function toggleChatCodeBlock(codeId) {
  const el = document.getElementById(codeId);
  if (el) {
    el.style.display = (el.style.display === 'none') ? 'block' : 'none';
  }
}

let chatGraphBusy = false;
let chatAbortController = null;

function setChatSendLocked(locked) {
  const button = document.getElementById('btnSendChat');
  const stop = document.getElementById('btnStopChat');
  const select = document.querySelector('select.chat-graph-kind-fixed');
  const chartSelect = document.querySelector('select.chat-echart-kind-fixed');
  const mapSelect = document.querySelector('select.chat-islamap-kind-fixed');
  const tableButton = document.getElementById('btnChatTable');
  if (button) button.disabled = !!locked;
  if (stop) stop.disabled = !locked;
  if (tableButton) tableButton.disabled = !!locked;
  if (select) select.disabled = !!locked;
  if (chartSelect) chartSelect.disabled = !!locked;
  if (mapSelect) mapSelect.disabled = !!locked;
  [select, chartSelect, mapSelect].forEach((node) => {
    const trigger = node && node.closest('.theme-select') && node.closest('.theme-select').querySelector('.theme-select-trigger');
    if (trigger) trigger.disabled = !!locked;
  });
}

function startChatRun() {
  chatAbortController = new AbortController();
  chatGraphBusy = true;
  setChatSendLocked(true);
  return chatAbortController;
}

function endChatRun() {
  chatAbortController = null;
  chatGraphBusy = false;
  setChatSendLocked(false);
}

function stopChatGeneration() {
  if (!chatAbortController) return;
  chatAbortController.abort();
}

function chatStopped(err) {
  return !!(err && err.name === 'AbortError');
}

window.stopChatGeneration = stopChatGeneration;

function graphKindInstruction(type) {
  const labels = {
    graph_isnad: 'تشجير إسناد',
    graph_ilmi: 'تشجير خلاف علمي',
    graph_fiqh: 'تشجير خلاف علمي',
    graph_aqeedah: 'تشجير خلاف علمي',
    graph_istidlal: 'تشجير استدلال',
    graph_munaqasha: 'تشجير مناقشة',
    graph_aam: 'تشجير خلاف عام'
  };
  const templates = window.P2C_OUTPUT_TEMPLATES || CHAT_OUTPUT_TEMPLATES;
  const shape = String(templates[type] || '').replace(/```[\s\S]*?```/g, '').trim();
  const label = labels[type] || 'التشجير المطلوب';
  return `شجّر النتيجة السابقة تشجيراً من نوع «${label}» فقط.
لا تبحث من جديد، ولا تستدعِ الشاملة ولا الوكلاء، ولا تضف شاهداً ليس في النتيجة.
لا تنسخ شجرة مثال، ولا تستخدم اسماً لم يرد في النتيجة.
لا تكتب الشرح قبل الشجرة.
أخرج كتلة force3d واحدة فقط، وأغلق السياج قبل أي كلام آخر.
بعد إغلاق السياج اكتب سطراً واحداً باسم نوع الشجرة، خارج الكتلة.
الصيغة داخل السياج إلزامية وفيها الوصلات، لا تكتفِ بقائمة عقد:
{"title":"عنوان من النتيجة","nodes":[{"id":"1","name":"الاسم كما في النتيجة","role":"الدور"}],"links":[{"source":"1","target":"2","label":""}]}
كل أب وفرع وصلة في links من الأعلى إلى الأسفل. لا تكتب اسم النوع داخل السياج.
${shape}`;
}

function stripGraphFences(text) {
  return String(text || '')
    .replace(/```(?:force3d|markmap)[\s\S]*?```/g, '')
    .replace(/^(تشجير إسناد|تشجير خلاف علمي|تشجير استدلال|تشجير مناقشة|تشجير خلاف عام|شجرة إسناد|شجرة خلاف فقهي|شجرة خلاف عقدي|شجرة استدلال|شجرة مناقشة)\s*$/gm, '')
    .trim();
}

async function requestChatGraph(type) {
  if (chatGraphBusy) return;
  const session = chatSessions.find(item => item.id === activeSessionId);
  const source = session && [...session.messages].reverse().find(item => item.role === 'assistant' && stripGraphFences(item.content).length > 40);
  if (!source) {
    if (typeof showToast === 'function') showToast('لا توجد نتيجة سابقة لتشجيرها');
    return;
  }

  const control = startChatRun();
  const container = document.getElementById('chatMessagesContainer');
  const typingBubble = document.createElement('div');
  typingBubble.className = 'message-bubble assistant';
  typingBubble.id = 'graphTypingIndicator';
  typingBubble.innerHTML = `
    <div class="message-avatar">مج</div>
    <div class="message-content">
      <span class="graph-wait-note">النموذج يقوم بالتشجير، فضلاً انتظر</span>
    </div>
  `;
  if (container) {
    container.appendChild(typingBubble);
    if (typeof scrollToBottom === 'function') scrollToBottom();
  }

  const instruction = graphKindInstruction(type);
  const material = stripGraphFences(source.content).slice(0, 24000);
  const selectedModel = document.getElementById('chatModelSelect')?.value
    || localStorage.getItem('almojtahed_active_chat_model')
    || 'anthropic/claude-3.7-sonnet';
  const activeProvider = localStorage.getItem(ownerStorageKey('almojtahed_active_provider')) || 'openrouter';
  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) {}

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: control.signal,
      body: JSON.stringify({
        model: selectedModel,
        provider: activeProvider,
        api_key: savedKeys[activeProvider] || '',
        thinking_level: currentThinkingLevel,
        use_hybrid: false,
        graph_only: true,
        messages: [{ role: 'user', content: `النتيجة المراد تشجيرها:\n${material}` }],
        system_prompt: instruction,
        temperature: 0.2,
        providers: savedKeys,
        agent_group: null
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'تعذر التشجير');
    if (typingBubble.parentNode) typingBubble.remove();
    session.messages.push({
      role: 'assistant',
      content: data.reply || 'تعذر إظهار التشجير.',
      model: data.model || selectedModel,
      provider: data.provider || activeProvider,
      graph_kind: type
    });
    saveChatSessions();
    renderSessionMessages(activeSessionId);
  } catch (err) {
    if (typingBubble.parentNode) typingBubble.remove();
    if (chatStopped(err)) {
      if (typeof showToast === 'function') showToast('تم الإيقاف');
    } else if (typeof showToast === 'function') showToast(err.message || 'تعذر التشجير');
  } finally {
    endChatRun();
  }
}

function tableInstruction() {
  return `جدول النتيجة السابقة فقط.
لا تبحث من جديد، ولا تستدعِ الشاملة ولا الوكلاء، ولا تضف شاهداً ليس في النتيجة.
لا تكتب شرحاً قبل الجدول ولا شجرة.
أخرج جداول ماركداون فقط، بأعمدة تناسب أبواب النتيجة: القول، والدليل، والمصدر إن ذُكر.
لا تضع علامة اقتباس داخل الخلايا، وأغلق كل جدول كاملاً.`;
}

async function requestChatTable() {
  if (chatGraphBusy) return;
  const session = chatSessions.find(item => item.id === activeSessionId);
  const source = session && [...session.messages].reverse().find(item => item.role === 'assistant' && stripGraphFences(item.content).length > 40);
  if (!source) {
    if (typeof showToast === 'function') showToast('لا توجد نتيجة سابقة لجدولتها');
    return;
  }

  const control = startChatRun();
  const container = document.getElementById('chatMessagesContainer');
  const typingBubble = document.createElement('div');
  typingBubble.className = 'message-bubble assistant';
  typingBubble.id = 'tableTypingIndicator';
  typingBubble.innerHTML = `
    <div class="message-avatar">مج</div>
    <div class="message-content">
      <span class="graph-wait-note">النموذج يقوم بالجدولة، فضلاً انتظر</span>
    </div>
  `;
  if (container) {
    container.appendChild(typingBubble);
    if (typeof scrollToBottom === 'function') scrollToBottom();
  }

  const material = stripGraphFences(source.content).slice(0, 24000);
  const selectedModel = document.getElementById('chatModelSelect')?.value
    || localStorage.getItem('almojtahed_active_chat_model')
    || 'anthropic/claude-3.7-sonnet';
  const activeProvider = localStorage.getItem(ownerStorageKey('almojtahed_active_provider')) || 'openrouter';
  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) {}

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: control.signal,
      body: JSON.stringify({
        chat_id: (typeof activeSessionId !== 'undefined' ? activeSessionId : null),
        model: selectedModel,
        provider: activeProvider,
        api_key: savedKeys[activeProvider] || '',
        thinking_level: currentThinkingLevel,
        use_hybrid: false,
        graph_only: false,
        table_only: true,
        messages: [{ role: 'user', content: `النتيجة المراد جدولتها:\n${material}` }],
        system_prompt: tableInstruction(),
        temperature: 0.2,
        providers: savedKeys,
        agent_group: null
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'تعذر الجدولة');
    if (typingBubble.parentNode) typingBubble.remove();
    session.messages.push({
      role: 'assistant',
      content: data.reply || 'تعذر إظهار الجدول.',
      model: data.model || selectedModel,
      provider: data.provider || activeProvider,
      table_request: true
    });
    saveChatSessions();
    renderSessionMessages(activeSessionId);
  } catch (err) {
    if (typingBubble.parentNode) typingBubble.remove();
    if (chatStopped(err)) {
      if (typeof showToast === 'function') showToast('تم الإيقاف');
    } else if (typeof showToast === 'function') showToast(err.message || 'تعذر الجدولة');
  } finally {
    endChatRun();
  }
}

window.requestChatTable = requestChatTable;

function stripChartFences(text) {
  return String(text || '').replace(/```(?:echarts|islamap)[\s\S]*?```/gi, '').trim();
}

function echartInstruction(type) {
  const label = ECHART_KIND_LABELS[type] || 'الرسم';
  const fence = '```echarts';
  const kindRule = type === 'multi'
    ? 'أخرج من رسمين إلى ثلاثة إذا احتملت النتيجة أكثر من زاوية، كل رسم في كتلة ' + fence + ' مستقلة، وseries.type مختلف في كل كتلة من: bar, line, pie, scatter, radar, heatmap, tree, treemap, sunburst, sankey, funnel, gauge, graph.'
    : 'أخرج رسماً واحداً فقط عنوانه «' + label + '» في كتلة ' + fence + ' واحدة، وseries.type يساوي ' + type + '.';
  return `${kindRule}
لا تبحث من جديد، ولا تستدعِ الشاملة ولا الوكلاء.
لا تضف رقماً ولا اسماً ليس في النتيجة، ولا تنسخ مثالاً جاهزاً.
لا تكتب أي كلمة خارج كتل echarts.
كل كتلة خيار Apache ECharts صالح فيه title.text بالعربية وseries.`;
}

async function requestChatEcharts(type) {
  if (chatGraphBusy) return;
  const session = chatSessions.find(item => item.id === activeSessionId);
  const source = session && [...session.messages].reverse().find(item => item.role === 'assistant' && !item.chart_kind && !item.map_kind && stripChartFences(item.content).length > 40);
  if (!source) {
    if (typeof showToast === 'function') showToast('لا توجد نتيجة سابقة لرسمها');
    return;
  }
  const control = startChatRun();
  const container = document.getElementById('chatMessagesContainer');
  const typingBubble = document.createElement('div');
  typingBubble.className = 'message-bubble assistant';
  typingBubble.innerHTML = `
    <div class="message-avatar">مج</div>
    <div class="message-content">
      <span class="graph-wait-note">جارٍ الرسم، فضلاً انتظر</span>
    </div>
  `;
  if (container) {
    container.appendChild(typingBubble);
    if (typeof scrollToBottom === 'function') scrollToBottom();
  }
  const material = stripChartFences(source.content).slice(0, 24000);
  const selectedModel = document.getElementById('chatModelSelect')?.value
    || localStorage.getItem('almojtahed_active_chat_model')
    || 'anthropic/claude-3.7-sonnet';
  const activeProvider = localStorage.getItem(ownerStorageKey('almojtahed_active_provider')) || 'openrouter';
  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) {}
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: control.signal,
      body: JSON.stringify({
        model: selectedModel,
        provider: activeProvider,
        api_key: savedKeys[activeProvider] || '',
        thinking_level: currentThinkingLevel,
        use_hybrid: false,
        graph_only: true,
        messages: [{ role: 'user', content: `النتيجة المراد رسمها:\n${material}` }],
        system_prompt: echartInstruction(type),
        temperature: 0.2,
        providers: savedKeys,
        agent_group: null
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'تعذر الرسم');
    if (typingBubble.parentNode) typingBubble.remove();
    session.messages.push({
      role: 'assistant',
      content: data.reply || 'تعذر إظهار الرسم.',
      model: data.model || selectedModel,
      provider: data.provider || activeProvider,
      chart_kind: type
    });
    saveChatSessions();
    renderSessionMessages(activeSessionId);
  } catch (err) {
    if (typingBubble.parentNode) typingBubble.remove();
    if (chatStopped(err)) {
      if (typeof showToast === 'function') showToast('تم الإيقاف');
    } else if (typeof showToast === 'function') showToast(err.message || 'تعذر الرسم');
  } finally {
    endChatRun();
  }
}

function insertEchartKind(select) {
  const type = select.value;
  select.value = '';
  select.dispatchEvent(new CustomEvent('theme-select-sync'));
  if (!type) return;
  requestChatEcharts(type);
}

window.insertEchartKind = insertEchartKind;
window.requestChatEcharts = requestChatEcharts;

const ISLAMAP_KIND_LABELS = {
  distribution: 'توزيع جغرافي',
  madhhab: 'توزيع جغرافي',
  cities: 'مدن ومراكز',
  routes: 'غزوات وفتوحات ورحلات',
  futuh: 'غزوات وفتوحات ورحلات',
  ghazawat: 'غزوات وفتوحات ورحلات'
};

const ISLAMAP_CATEGORY_COLORS = ['#dc2626', '#16a34a', '#2563eb', '#f97316', '#eab308', '#7c3aed', '#0891b2', '#db2777'];

const ISLAMAP_REGIONS = [
  ['andalus', 'الأندلس', 'M40,190 L130,165 L155,210 L140,270 L50,255 Z', 90, 220],
  ['maghreb', 'المغرب', 'M150,175 L250,160 L270,230 L240,285 L145,270 L155,215 Z', 200, 225],
  ['ifriqiya', 'إفريقية', 'M250,165 L340,160 L355,240 L300,290 L245,270 L255,210 Z', 295, 225],
  ['egypt', 'مصر', 'M340,175 L430,160 L455,230 L430,310 L350,300 L330,240 Z', 390, 240],
  ['sham', 'الشام', 'M400,105 L510,90 L530,160 L455,185 L395,155 Z', 460, 140],
  ['jazira', 'الجزيرة', 'M500,100 L590,90 L610,155 L530,170 L495,140 Z', 550, 130],
  ['iraq', 'العراق', 'M520,175 L640,160 L660,245 L560,270 L500,220 Z', 590, 215],
  ['hijaz', 'الحجاز', 'M430,250 L520,235 L545,320 L490,390 L430,360 L415,290 Z', 475, 310],
  ['yemen', 'اليمن', 'M470,380 L575,365 L590,455 L490,470 L455,420 Z', 520, 420],
  ['fars', 'فارس', 'M650,165 L770,150 L790,245 L670,265 L640,210 Z', 710, 205],
  ['khurasan', 'خراسان', 'M740,115 L870,100 L890,190 L760,210 L730,160 Z', 810, 155],
  ['transoxiana', 'ما وراء النهر', 'M800,45 L960,35 L970,120 L830,140 L790,90 Z', 880, 85],
  ['sind', 'السند', 'M840,200 L970,185 L980,290 L860,305 L830,240 Z', 900, 245],
  ['anatolia', 'آسيا الصغرى', '', 0, 0],
  ['kurdistan', 'كردستان', '', 0, 0],
  ['azerbaijan', 'أذربيجان', '', 0, 0],
  ['khwarizm', 'خوارزم', '', 0, 0],
  ['daylam', 'الديلم', '', 0, 0],
  ['jibal', 'الجبال', '', 0, 0],
  ['kirman', 'كرمان', '', 0, 0],
  ['khuzistan', 'خوزستان', '', 0, 0],
  ['oman', 'عمان', '', 0, 0],
  ['hadramawt', 'حضرموت', '', 0, 0],
  ['bahrayn', 'البحرين', '', 0, 0],
  ['filastin', 'فلسطين', '', 0, 0],
  ['urdunn', 'الأردن', '', 0, 0]
];

const ISLAMAP_CITIES = [
  ['qurtuba', 'قرطبة', -4.78, 37.88],
  ['fas', 'فاس', -5.0, 34.03],
  ['qayrawan', 'القيروان', 10.1, 35.68],
  ['fustat', 'الفسطاط', 31.23, 30.0],
  ['cairo', 'القاهرة', 31.24, 30.05],
  ['dimashq', 'دمشق', 36.29, 33.51],
  ['quds', 'القدس', 35.23, 31.78],
  ['makka', 'مكة', 39.83, 21.42],
  ['madina', 'المدينة', 39.61, 24.47],
  ['sanaa', 'صنعاء', 44.21, 15.35],
  ['kufa', 'الكوفة', 44.4, 32.03],
  ['basra', 'البصرة', 47.78, 30.51],
  ['baghdad', 'بغداد', 44.37, 33.31],
  ['mawsil', 'الموصل', 43.14, 36.34],
  ['rayy', 'الري', 51.43, 35.59],
  ['naysabur', 'نيسابور', 58.8, 36.21],
  ['bukhara', 'بخارى', 64.42, 39.77],
  ['samarqand', 'سمرقند', 66.97, 39.65],
  ['mansura', 'المنصورة', 68.42, 25.92],
  ['tarsus', 'طرسوس', 34.895, 36.917],
  ['cilicia', 'درب كليكيا', 34.761, 37.268],
  ['heraclea', 'هرقلة', 34.046, 37.513],
  ['amorium', 'عمورية', 31.302, 39.025],
  ['edirne', 'أدرنة', 26.556, 41.677],
  ['constantinople', 'القسطنطينية', 28.979, 41.008],
  ['landwalls', 'الأسوار البرية', 28.923, 41.029],
  ['rumeli', 'روملي حصاري', 29.056, 41.085],
  ['anadolu', 'أناضولو حصاري', 29.067, 41.082],
  ['bosphorus', 'البوسفور', 29.062, 41.084],
  ['tophane', 'طوب خانه', 28.988, 41.031],
  ['galata', 'غلطة', 28.974, 41.026],
  ['goldenhorn', 'الخليج الذهبي', 28.96, 41.032],
  ['hornmouth', 'فم الخليج', 28.978, 41.023],
  ['levantsea', 'بحر الشام', 34.6, 35.4, true],
  ['aegean', 'بحر إيجه', 25.6, 37.8, true],
  ['dardanelles', 'الدردنيل', 26.39, 40.2, true],
  ['marmara', 'بحر مرمرة', 28.35, 40.88, true],
  ['redsea', 'البحر الأحمر', 38.5, 20.2, true],
  ['persian', 'بحر فارس', 51.8, 27.2, true],
  ['indian', 'المحيط الهندي', 65.0, 15.0, true],
  ['westmed', 'غرب المتوسط', 12.5, 36.5, true],
  ['blacksea', 'البحر الأسود', 34.0, 43.0, true],
  ['caspian', 'بحر الخزر', 50.5, 42.0, true],
  ['atlantic', 'المحيط الأطلسي', -12.0, 33.0, true],
  ['aden', 'خليج عدن', 46.5, 12.4, true],
  ['wasit', 'واسط', 45.75, 32.51],
  ['isfahan', 'أصفهان', 51.68, 32.65],
  ['shiraz', 'شيراز', 52.54, 29.59],
  ['hamadan', 'همذان', 48.51, 34.80],
  ['tabriz', 'تبريز', 46.29, 38.08],
  ['aleppo', 'حلب', 37.15, 36.20],
  ['hama', 'حماة', 36.75, 35.13],
  ['homs', 'حمص', 36.72, 34.73],
  ['tripoli', 'طرابلس الشام', 35.85, 33.90],
  ['baalbek', 'بعلبك', 36.20, 34.00],
  ['sidon', 'صيدا', 35.37, 33.56],
  ['acre', 'عكا', 35.08, 32.93],
  ['tiberias', 'طبريا', 35.53, 32.79],
  ['nablus', 'نابلس', 35.26, 32.22],
  ['hebron', 'الخليل', 35.10, 31.53],
  ['gaza', 'غزة', 34.45, 31.50],
  ['ascalon', 'عسقلان', 34.55, 31.67],
  ['ramla', 'الرملة', 34.87, 31.93],
  ['alexandria', 'الإسكندرية', 29.92, 31.20],
  ['damietta', 'دمياط', 31.42, 31.42],
  ['asyut', 'أسيوط', 31.18, 27.18],
  ['zabid', 'زبيد', 43.32, 14.20],
  ['taiz', 'تعز', 44.02, 13.58],
  ['aden', 'عدن', 45.04, 12.78],
  ['herat', 'هراة', 62.20, 34.35],
  ['merv', 'مرو', 62.18, 37.66],
  ['balkh', 'بلخ', 66.90, 36.76],
  ['tus', 'طوس', 59.48, 36.45],
  ['sabzevar', 'بيهق', 57.68, 36.21],
  ['jurjan', 'جرجان', 54.44, 36.84],
  ['amol', 'آمل', 52.35, 36.47],
  ['qazvin', 'قزوين', 50.00, 36.28],
  ['ardabil', 'أردبيل', 48.29, 38.25],
  ['maragha', 'مراغة', 46.24, 37.39],
  ['irbil', 'أربيل', 44.01, 36.19],
  ['tikrit', 'تكريت', 43.68, 34.60],
  ['hilla', 'الحلة', 44.43, 32.47],
  ['khiva', 'خيوة', 60.36, 41.38],
  ['termez', 'ترمذ', 67.27, 37.22],
  ['nasaf', 'نسف', 65.79, 38.86],
  ['tashkent', 'الشاش', 69.24, 41.30],
  ['fergana', 'فرغانة', 71.78, 40.39],
  ['khujand', 'خجند', 69.62, 40.28],
  ['multan', 'ملتان', 71.47, 30.16],
  ['daybul', 'الديبل', 67.65, 24.57],
  ['kerman', 'كرمان', 57.07, 30.29],
  ['taif', 'الطائف', 40.42, 21.27],
  ['jeddah', 'جدة', 39.17, 21.49],
  ['sohar', 'صحار', 56.34, 24.34],
  ['nizwa', 'نزوى', 57.53, 22.93],
  ['seville', 'إشبيلية', -5.99, 37.39],
  ['granada', 'غرناطة', -3.59, 37.18],
  ['malaga', 'مالقة', -4.42, 36.72],
  ['valencia', 'بلنسية', -0.38, 39.47],
  ['murcia', 'مرسية', -1.13, 37.99],
  ['mahdia', 'المهدية', 11.06, 35.50],
  ['tunis', 'تونس', 10.18, 36.80],
  ['bejaia', 'بجاية', 5.08, 36.75],
  ['tlemcen', 'تلمسان', -1.31, 34.88],
  ['marrakesh', 'مراكش', -7.99, 31.63]
];

const ISLAMAP_COUNTRIES = {
  andalus: ['Spain', 'Portugal'],
  maghreb: ['Morocco', 'Algeria', 'Mauritania'],
  ifriqiya: ['Tunisia', 'Libya'],
  egypt: ['Egypt'],
  sham: ['Syria', 'Lebanon', 'Jordan', 'Palestine', 'Israel'],
  iraq: ['Iraq'],
  yemen: ['Yemen'],
  fars: ['Iran'],
  khurasan: ['Afghanistan', 'Turkmenistan'],
  transoxiana: ['Uzbekistan', 'Tajikistan', 'Kyrgyzstan'],
  sind: ['Pakistan'],
  anatolia: ['Turkey'],
  azerbaijan: ['Azerbaijan'],
  khwarizm: ['Uzbekistan', 'Turkmenistan'],
  daylam: ['Iran'],
  jibal: ['Iran'],
  kirman: ['Iran'],
  khuzistan: ['Iran'],
  oman: ['Oman'],
  bahrayn: ['Bahrain'],
  filastin: ['Palestine', 'Israel'],
  urdunn: ['Jordan']
};

const ISLAMAP_MODERN_COUNTRY = {
  Spain: 'إسبانيا', Portugal: 'البرتغال', Morocco: 'المغرب', Algeria: 'الجزائر', Mauritania: 'موريتانيا',
  Tunisia: 'تونس', Libya: 'ليبيا', Egypt: 'مصر', Syria: 'سوريا', Lebanon: 'لبنان', Jordan: 'الأردن',
  Palestine: 'فلسطين', Israel: 'إسرائيل', Iraq: 'العراق', Yemen: 'اليمن', Iran: 'إيران',
  Afghanistan: 'أفغانستان', Turkmenistan: 'تركمانستان', Uzbekistan: 'أوزبكستان', Tajikistan: 'طاجيكستان',
  Kyrgyzstan: 'قيرغيزستان', Pakistan: 'باكستان', Turkey: 'تركيا', Azerbaijan: 'أذربيجان',
  Oman: 'عُمان', Bahrain: 'البحرين'
};

const ISLAMAP_VIEW = { center: [43, 28], zoom: 3.6 };

const ISLAMAP_ALIAS = {
  'الأندلس': 'andalus', 'الاندلس': 'andalus', 'المغرب': 'maghreb', 'إفريقية': 'ifriqiya', 'افريقية': 'ifriqiya',
  'مصر': 'egypt', 'الشام': 'sham', 'الجزيرة': 'jazira', 'العراق': 'iraq', 'الحجاز': 'hijaz', 'اليمن': 'yemen',
  'فارس': 'fars', 'خراسان': 'khurasan', 'ما وراء النهر': 'transoxiana', 'السند': 'sind',
  'قرطبة': 'qurtuba', 'فاس': 'fas', 'القيروان': 'qayrawan', 'الفسطاط': 'fustat', 'القاهرة': 'cairo',
  'دمشق': 'dimashq', 'القدس': 'quds', 'مكة': 'makka', 'المدينة': 'madina', 'المدينة المنورة': 'madina',
  'صنعاء': 'sanaa', 'الكوفة': 'kufa', 'البصرة': 'basra', 'بغداد': 'baghdad', 'الموصل': 'mawsil',
  'الري': 'rayy', 'نيسابور': 'naysabur', 'بخارى': 'bukhara', 'سمرقند': 'samarqand', 'المنصورة': 'mansura',
  'طرسوس': 'tarsus', 'درب كليكيا': 'cilicia', 'كليكيا': 'cilicia', 'هرقلة': 'heraclea', 'عمورية': 'amorium',
  'أدرنة': 'edirne', 'أدرنه': 'edirne', 'القسطنطينية': 'constantinople', 'إسطنبول': 'constantinople',
  'الأسوار البرية': 'landwalls', 'روملي حصاري': 'rumeli', 'قلعة الروم': 'rumeli',
  'أناضولو حصاري': 'anadolu', 'قلعة الأناضول': 'anadolu', 'غلطة': 'galata',
  'الخليج الذهبي': 'goldenhorn', 'فم الخليج': 'hornmouth', 'طوب خانه': 'tophane',
  'البوسفور': 'bosphorus', 'بحر إيجه': 'aegean', 'الدردنيل': 'dardanelles', 'بحر مرمرة': 'marmara',
  'بحر الشام': 'levantsea', 'البحر المتوسط': 'levantsea', 'بحر الروم': 'levantsea',
  'البحر الأحمر': 'redsea', 'الخليج الفارسي': 'persian', 'بحر فارس': 'persian',
  'المحيط الهندي': 'indian', 'البحر الأسود': 'blacksea', 'بحر الخزر': 'caspian',
  'بحر قزوين': 'caspian', 'المحيط الأطلسي': 'atlantic', 'خليج عدن': 'aden',
  'آسيا الصغرى': 'anatolia', 'الأناضول': 'anatolia',
  'constantinople': 'constantinople', 'edirne': 'edirne', 'tarsus': 'tarsus',
  'amorium': 'amorium', 'heraclea': 'heraclea', 'galata': 'galata',
  'golden horn': 'goldenhorn', 'bosphorus': 'bosphorus',
  'كردستان': 'kurdistan', 'أذربيجان': 'azerbaijan', 'خوارزم': 'khwarizm', 'الديلم': 'daylam',
  'الجبال': 'jibal', 'كرمان': 'kirman', 'خوزستان': 'khuzistan', 'عمان': 'oman',
  'حضرموت': 'hadramawt', 'البحرين': 'bahrayn', 'فلسطين': 'filastin', 'الأردن': 'urdunn',
  'واسط': 'wasit', 'أصفهان': 'isfahan', 'شيراز': 'shiraz', 'همذان': 'hamadan', 'تبريز': 'tabriz',
  'حلب': 'aleppo', 'حماة': 'hama', 'حمص': 'homs', 'طرابلس الشام': 'tripoli', 'بعلبك': 'baalbek',
  'صيدا': 'sidon', 'عكا': 'acre', 'طبريا': 'tiberias', 'نابلس': 'nablus', 'الخليل': 'hebron',
  'غزة': 'gaza', 'عسقلان': 'ascalon', 'الرملة': 'ramla', 'الإسكندرية': 'alexandria',
  'دمياط': 'damietta', 'أسيوط': 'asyut', 'زبيد': 'zabid', 'تعز': 'taiz', 'عدن': 'aden',
  'هراة': 'herat', 'مرو': 'merv', 'بلخ': 'balkh', 'طوس': 'tus', 'بيهق': 'sabzevar',
  'جرجان': 'jurjan', 'آمل': 'amol', 'قزوين': 'qazvin', 'أردبيل': 'ardabil', 'مراغة': 'maragha',
  'أربيل': 'irbil', 'تكريت': 'tikrit', 'الحلة': 'hilla', 'خيوة': 'khiva', 'ترمذ': 'termez',
  'نسف': 'nasaf', 'الشاش': 'tashkent', 'فرغانة': 'fergana', 'خجند': 'khujand', 'ملتان': 'multan',
  'الديبل': 'daybul', 'الطائف': 'taif', 'جدة': 'jeddah', 'صحار': 'sohar', 'نزوى': 'nizwa',
  'إشبيلية': 'seville', 'غرناطة': 'granada', 'مالقة': 'malaga', 'بلنسية': 'valencia',
  'مرسية': 'murcia', 'المهدية': 'mahdia', 'تونس': 'tunis', 'بجاية': 'bejaia',
  'تلمسان': 'tlemcen', 'مراكش': 'marrakesh'
};

const ISLAMAP_COLORS = [
  ['حنفي', '#eab308'],
  ['مالكي', '#16a34a'],
  ['شافعي', '#2563eb'],
  ['حنبلي', '#dc2626'],
  ['ظاهري', '#f97316'],
  ['إباضي', '#0891b2'],
  ['زيدي', '#ca8a04'],
  ['إمامي', '#7c3aed']
];

function islamapResolve(token) {
  const text = String(token || '').trim();
  if (!text) return '';
  if (ISLAMAP_REGIONS.some((item) => item[0] === text) || ISLAMAP_CITIES.some((item) => item[0] === text)) return text;
  return ISLAMAP_ALIAS[text] || ISLAMAP_ALIAS[text.toLowerCase()] || '';
}

function islamapColor(value) {
  const text = String(value || '');
  const found = ISLAMAP_COLORS.find(([name]) => text.includes(name));
  return found ? found[1] : (text ? '#8d7355' : '#f3e6c8');
}

const ISLAMAP_CENTURY_COLORS = {
  1: '#dc2626', 2: '#16a34a', 3: '#2563eb', 4: '#f97316', 5: '#eab308',
  6: '#7c3aed', 7: '#0891b2', 8: '#db2777', 9: '#65a30d', 10: '#1d4ed8',
  11: '#b91c1c', 12: '#15803d', 13: '#c2410c', 14: '#a16207', 15: '#6d28d9'
};

function islamapCenturyColor(century) {
  return ISLAMAP_CENTURY_COLORS[Number(century)] || '#8d7355';
}

function islamapShade(hex, ratio) {
  const raw = String(hex || '#2f6f8f').replace('#', '');
  if (raw.length !== 6) return hex;
  const mix = (part) => Math.round(parseInt(part, 16) + (255 - parseInt(part, 16)) * ratio);
  return `rgb(${mix(raw.slice(0, 2))},${mix(raw.slice(2, 4))},${mix(raw.slice(4, 6))})`;
}

function islamapCountShade(base, count) {
  if (!count) return '#f4efe6';
  if (count <= 1) return islamapShade(base, 0.18);
  if (count <= 3) return islamapShade(base, 0.08);
  return base;
}

function islamapList(value) {
  if (Array.isArray(value)) return value.map((item) => String(item || '').trim()).filter(Boolean);
  if (!value) return [];
  return String(value).split(/[،,؛;|\n]+/).map((item) => item.trim()).filter(Boolean);
}

function islamapPlaces(data) {
  const places = [];
  const add = (item, fromPlaces) => {
    if (!item || typeof item !== 'object') return;
    const located = islamapLocate(item.id || item.city || item.name || item.place, data);
    if (!located || located.water) return;
    const scholars = islamapList(item.scholars || item.names);
    const books = islamapList(item.books || item.works);
    const century = Number(item.century || item.era || item.period) || null;
    places.push({
      id: located.id,
      name: located.name,
      lng: located.lng,
      lat: located.lat,
      region: islamapResolve(item.region) || '',
      century,
      scholars,
      books,
      count: Number(item.count) || scholars.length,
      value: String(item.value || '').trim(),
      note: String(item.note || '').trim(),
      fromPlaces: !!fromPlaces
    });
  };
  (data.places || []).forEach((item) => add(item, true));
  if (!places.length) (data.cities || []).forEach((item) => add(item, false));
  return places;
}

function islamapRegionName(id) {
  const found = ISLAMAP_REGIONS.find((region) => region[0] === id);
  return found ? found[1] : '';
}

const ISLAMAP_CITY_REGION = {
  qurtuba: 'andalus', seville: 'andalus', granada: 'andalus', malaga: 'andalus', valencia: 'andalus', murcia: 'andalus',
  fas: 'maghreb', marrakesh: 'maghreb', tlemcen: 'maghreb', qayrawan: 'ifriqiya', mahdia: 'ifriqiya', tunis: 'ifriqiya', bejaia: 'ifriqiya',
  fustat: 'egypt', cairo: 'egypt', alexandria: 'egypt', damietta: 'egypt', asyut: 'egypt',
  dimashq: 'sham', aleppo: 'sham', hama: 'sham', homs: 'sham', tripoli: 'sham', baalbek: 'sham', sidon: 'sham',
  acre: 'filastin', tiberias: 'filastin', nablus: 'filastin', hebron: 'filastin', gaza: 'filastin', ascalon: 'filastin', ramla: 'filastin', quds: 'filastin',
  kufa: 'iraq', basra: 'iraq', baghdad: 'iraq', wasit: 'iraq', hilla: 'iraq', tikrit: 'iraq', mawsil: 'jazira', irbil: 'kurdistan',
  makka: 'hijaz', madina: 'hijaz', taif: 'hijaz', jeddah: 'hijaz',
  sanaa: 'yemen', zabid: 'yemen', taiz: 'yemen', aden: 'yemen',
  rayy: 'jibal', isfahan: 'jibal', hamadan: 'jibal', qazvin: 'jibal', shiraz: 'fars', kerman: 'kirman',
  naysabur: 'khurasan', herat: 'khurasan', merv: 'khurasan', balkh: 'khurasan', tus: 'khurasan', sabzevar: 'khurasan', jurjan: 'khurasan', amol: 'daylam',
  tabriz: 'azerbaijan', ardabil: 'azerbaijan', maragha: 'azerbaijan',
  bukhara: 'transoxiana', samarqand: 'transoxiana', termez: 'transoxiana', nasaf: 'transoxiana', tashkent: 'transoxiana', fergana: 'transoxiana', khujand: 'transoxiana',
  khiva: 'khwarizm', mansura: 'sind', multan: 'sind', daybul: 'sind', sohar: 'oman', nizwa: 'oman'
};

function islamapLocate(token, data) {
  const text = String(token || '').trim();
  const resolved = islamapResolve(text);
  const points = (data && data.points) || [];
  const point = points.find((item) => item && (item.id === resolved || item.id === text || item.name === text));
  const city = islamapCity(resolved || (point && point.id) || '');
  let lng = point ? Number(point.lng) : NaN;
  let lat = point ? Number(point.lat) : NaN;
  const tavilyOk = Number.isFinite(lng) && Number.isFinite(lat);
  if (tavilyOk && city) {
    const far = Math.hypot(lng - city[2], lat - city[3]) > 3;
    if (far) {
      lng = city[2];
      lat = city[3];
    }
  } else if (!tavilyOk && city) {
    lng = city[2];
    lat = city[3];
  } else if (!tavilyOk) {
    return null;
  }
  const historical = (point && point.name) || (city && city[1]) || text;
  const modern = point && point.modern && point.modern !== historical ? String(point.modern) : '';
  return {
    id: (point && point.id) || resolved || text,
    lng,
    lat,
    historical,
    modern,
    name: modern ? `${historical} (${modern})` : historical,
    water: !!(point && point.water) || !!(city && city[4] === true)
  };
}

function islamapCoordTip(lng, lat) {
  if (!Number.isFinite(Number(lng)) || !Number.isFinite(Number(lat))) return '';
  return `خط العرض ${Number(lat).toFixed(2)}° · خط الطول ${Number(lng).toFixed(2)}°`;
}

function islamapGraticule(points) {
  const pool = points && points.length ? points : [[-12, 18], [62, 42]];
  const lngs = pool.map((point) => point[0]);
  const lats = pool.map((point) => point[1]);
  const minLng = Math.min(...lngs) - 4;
  const maxLng = Math.max(...lngs) + 4;
  const minLat = Math.max(-55, Math.min(...lats) - 3);
  const maxLat = Math.min(70, Math.max(...lats) + 3);
  const step = (maxLng - minLng) > 36 ? 10 : 5;
  const lines = [];
  const labels = [];
  for (let lng = Math.ceil(minLng / step) * step; lng <= maxLng; lng += step) {
    lines.push({ coords: [[lng, minLat], [lng, maxLat]] });
    labels.push({ value: [lng, minLat], labelText: `${lng}°ط` });
  }
  for (let lat = Math.ceil(minLat / step) * step; lat <= maxLat; lat += step) {
    lines.push({ coords: [[minLng, lat], [maxLng, lat]] });
    labels.push({ value: [minLng, lat], labelText: `${lat}°ع` });
  }
  return [
    {
      type: 'lines',
      coordinateSystem: 'geo',
      polyline: true,
      silent: true,
      data: lines,
      lineStyle: { color: 'rgba(70, 90, 110, 0.28)', width: 0.7 },
      z: 1
    },
    {
      type: 'scatter',
      coordinateSystem: 'geo',
      silent: true,
      symbolSize: 1,
      data: labels,
      label: {
        show: true,
        formatter: (params) => params.data.labelText,
        color: '#5c6b7a',
        fontSize: 10,
        position: 'right'
      },
      z: 2
    }
  ];
}

function islamapCity(id) {
  return ISLAMAP_CITIES.find((item) => item[0] === id);
}

function islamapRouteCoords(route, data) {
  const stops = [route.from].concat(Array.isArray(route.via) ? route.via : [], route.to);
  const located = [];
  stops.forEach((token) => {
    const place = islamapLocate(token, data);
    if (!place) return;
    const point = [place.lng, place.lat];
    const last = located[located.length - 1];
    if (last && last.lng === point[0] && last.lat === point[1]) return;
    located.push({ lng: point[0], lat: point[1], water: place.water });
  });
  const kind = route.kind || route.type || 'land';
  const usable = kind === 'land' ? located.filter((place) => !place.water) : located;
  const shortSea = kind === 'sea' && usable.length >= 2 && usable.every((place, index) => {
    if (!index) return true;
    const previous = usable[index - 1];
    const rad = Math.PI / 180;
    const dLat = (place.lat - previous.lat) * rad;
    const dLng = (place.lng - previous.lng) * rad;
    const lat1 = previous.lat * rad;
    const lat2 = place.lat * rad;
    const hav = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
    return 6371 * 2 * Math.atan2(Math.sqrt(hav), Math.sqrt(1 - hav)) <= 150;
  });
  if (kind === 'sea' && !usable.some((place) => place.water) && !shortSea) return null;
  if (usable.length < 2) return null;
  return usable.map((place) => [place.lng, place.lat]);
}

function islamapFrame(points) {
  if (!points.length) return ISLAMAP_VIEW;
  const lngs = points.map((point) => point[0]);
  const lats = points.map((point) => point[1]);
  const midLat = (Math.min(...lats) + Math.max(...lats)) / 2;
  const span = Math.max(
    Math.max(...lngs) - Math.min(...lngs),
    (Math.max(...lats) - Math.min(...lats)) / Math.max(0.35, Math.cos(midLat * Math.PI / 180)),
    1.1
  );
  return {
    center: [(Math.min(...lngs) + Math.max(...lngs)) / 2, midLat],
    zoom: Math.max(1.5, Math.min(11, 128 / span))
  };
}

function islamapInstruction(type) {
  const fence = '```islamap';
  const focus = {
    madhhab: 'ركّز على طبقات المذهب: عنصر places لكل مدينة في قرن، مع scholars وbooks وcount. لا تكتف بتلوين إقليم.',
    futuh: 'ركّز على الفتوحات. كل مسار طريق متتابع في via، لا خطاً مستقيماً يقطع الجبال أو البحر. kind: land للبر، sea للبحر، portage لجر السفن على البر.',
    ghazawat: 'ركّز على الغزوات والسرايا. كل مسار طريق متتابع في via. kind: land للبر، sea للبحر، portage لجر السفن على البر.',
    cities: 'ركّز على المدن والمراكز، بلا طرق إلا إذا ورد انتقال صريح.',
    full: 'اجمع من النتيجة ما يصح من مناطق ومدن وطرق، بلا حشو.'
  }[type] || 'اجمع ما يصح من النتيجة.';
  return `${focus}
لا تبحث من جديد، ولا تستدعِ الشاملة ولا الوكلاء.
لا تضف مذهباً ولا فتحاً ولا غزوة ولا مدينة ليست في النتيجة، ولا تنسخ مثالاً جاهزاً.
لا تخترع إحداثيات. المعرفات المسموحة فقط:
المناطق: andalus maghreb ifriqiya egypt sham jazira iraq hijaz yemen fars khurasan transoxiana sind anatolia.
المدن: qurtuba fas qayrawan fustat cairo dimashq quds makka madina sanaa kufa basra baghdad mawsil rayy naysabur bukhara samarqand mansura tarsus cilicia heraclea amorium edirne constantinople landwalls rumeli anadolu bosphorus tophane galata goldenhorn hornmouth levantsea aegean dardanelles marmara.
رتّب via على الطريق نفسه: البر على المحطات البرية، والبحر على محطات البحر حتى لا يقطع الخط اليابسة، ونقل السفن kind=portage.
أخرج كتلة ${fence} واحدة فقط، بلا أي كلمة خارجها:
{"title":"","subject":"","places":[{"id":"","region":"","century":3,"scholars":[],"books":[],"count":0}],"regions":[{"id":"","value":"","note":""}],"cities":[],"routes":[{"from":"","to":"","via":[],"kind":"land","label":"","year":""}]}
احذف الحقول الفارغة. value وصف قصير من النتيجة.`;
}

function parseIslamapBlock(raw) {
  const text = String(raw || '').trim().replace(/,\s*([}\]])/g, '$1');
  const data = JSON.parse(text);
  const body = data && data.islamap && typeof data.islamap === 'object' ? data.islamap : data;
  if (!body || typeof body !== 'object') return null;
  return {
    title: String(body.title || 'خارطة العالم الإسلامي').trim(),
    mode: String(body.mode || body.kind || '').trim(),
    subject: String(body.subject || body.madhhab || '').trim(),
    eras: Array.isArray(body.eras) ? body.eras : [],
    places: Array.isArray(body.places) ? body.places : [],
    regions: Array.isArray(body.regions) ? body.regions : [],
    cities: Array.isArray(body.cities) ? body.cities : [],
    routes: Array.isArray(body.routes) ? body.routes : [],
    points: Array.isArray(body.points) ? body.points : [],
    option: body.option && typeof body.option === 'object' ? body.option : null,
    example: String(body.example || '').trim(),
    example_label: String(body.example_label || '').trim(),
    example_url: String(body.example_url || '').trim()
  };
}

function islamapLookup(list, id) {
  return (list || []).find((item) => islamapResolve(item.id || item.name || item.region) === id);
}

function renderIslamapBlocks(container) {
  if (!container) return;
  container.querySelectorAll('pre code').forEach((codeEl, idx) => {
    const pre = codeEl.closest('pre');
    if (!pre || pre.dataset.renderedIslamap === '1') return;
    const raw = codeEl.innerText.trim();
    const tagged = /islamap/i.test(codeEl.className || '');
    const looks = raw.startsWith('{') && /"(regions|routes|cities)"/.test(raw) && !/"nodes"/.test(raw);
    if (!tagged && !looks) return;
    let data = null;
    try { data = parseIslamapBlock(raw); } catch (e) { data = null; }
    if (!data) return;
    pre.dataset.renderedIslamap = '1';
    const eraCenturies = [...new Set(islamapPlaces(data).map((place) => place.century).filter(Boolean))].sort((a, b) => a - b);
    const eraOptions = eraCenturies.length
      ? `<label class="force3d-example-label"><span>الطبقة</span><select data-islamap-era dir="rtl"><option value="all" selected>كل القرون</option>${eraCenturies.map((century) => `<option value="${century}">ق${century}هـ</option>`).join('')}</select></label>`
      : '';
    const box = document.createElement('div');
    box.className = 'chart-render-wrapper islamap-render-wrapper';
    box._map = data;
    box._scale = 1;
    box._tx = 0;
    box._ty = 0;
    box.innerHTML = `
      <div class="chart-render-header">
        <div class="chart-render-title"><span>🗺️</span><span>${escapeHtml(data.title)}</span></div>
        <div class="force3d-tools">
          <label class="force3d-example-label">
            <span>العرض</span>
            <select data-islamap-layer dir="rtl">
              <option value="all" selected>الكل</option>
              <option value="regions">المذاهب والمناطق</option>
              <option value="routes">الفتوحات والغزوات</option>
              <option value="cities">المدن</option>
            </select>
          </label>
          ${eraOptions}
          <label class="force3d-example-label">
            <span>الخط</span>
            <select data-islamap-font dir="rtl">
              ${ECHART_FONTS.map(([name, label]) => `<option value="${echartEscape(name)}"${name === 'Amiri' ? ' selected' : ''}>${echartEscape(label)}</option>`).join('')}
            </select>
          </label>
          <label class="force3d-example-label">
            <span>الحجم</span>
            <select data-islamap-size dir="rtl">
              ${[12, 14, 16, 18, 20, 24].map((size) => `<option value="${size}"${size === 14 ? ' selected' : ''}>${size}</option>`).join('')}
            </select>
          </label>
          <label class="force3d-example-label">
            <span>الخلفية</span>
            <select data-islamap-bg dir="rtl">
              ${ECHART_BACKGROUNDS.map(([color, label]) => `<option value="${color}"${color === '#e7f0f6' ? ' selected' : ''}>${echartEscape(label)}</option>`).join('')}
            </select>
          </label>
          <button type="button" class="btn-chart-type" data-islamap-share="1" title="مشاركة">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4"/></svg>
            <span>مشاركة</span>
          </button>
          <button type="button" class="btn-chart-type" data-islamap-fit="1">ملاءمة</button>
          <button type="button" class="btn-chart-type" data-islamap-reset="1">إعادة</button>
          <button type="button" class="btn-chart-type force3d-shot" data-islamap-shot="1" title="لقطة للخارطة"><span>لقطة</span></button>
          <button type="button" class="btn-chart-type" data-islamap-expand="1">تكبير</button>
          <button type="button" class="btn-chart-type islamap-close" data-islamap-close="1">إغلاق</button>
          <button type="button" class="btn-chart-type" data-islamap-code="1">الكود</button>
        </div>
      </div>
      <div class="islamap-stage"></div>
      <div class="islamap-legend"></div>
      <div class="islamap-details"></div>
      <div class="echart-detail">${escapeHtml(data.example_label ? `الخريطة المختارة: ${data.example} — ${data.example_label}. ` : '')}خارطة جغرافية بحدود الدول، والمدن في مواضعها من خطوط الطول والعرض. الألوان والطرق من النتيجة فقط، والتجوال بالفأرة.</div>
      <div class="echart-code" hidden></div>
    `;
    pre.parentNode.insertBefore(box, pre);
    pre.hidden = false;
    box.querySelector('.echart-code').appendChild(pre);
    paintIslamap(box);
  });
}

let islamapWorldPromise = null;

function ensureIslamapWorld() {
  if (window._islamapWorld) return Promise.resolve(window._islamapWorld);
  if (!islamapWorldPromise) {
    islamapWorldPromise = fetch('/static/geo/world.json')
      .then((response) => {
        if (!response.ok) throw new Error('world map');
        return response.json();
      })
      .then((geo) => {
        window._islamapWorld = geo;
        if (window.echarts) window.echarts.registerMap('islamap-world', geo);
        return geo;
      })
      .catch((err) => {
        islamapWorldPromise = null;
        throw err;
      });
  }
  return islamapWorldPromise;
}

function islamapUsedIds(data) {
  const used = new Set();
  (data.places || []).forEach((item) => used.add(islamapResolve(item.id || item.city || item.name)));
  (data.cities || []).forEach((item) => used.add(islamapResolve(item.id || item.name)));
  (data.routes || []).forEach((route) => {
    used.add(islamapResolve(route.from));
    used.add(islamapResolve(route.to));
    (Array.isArray(route.via) ? route.via : []).forEach((token) => used.add(islamapResolve(token)));
  });
  used.delete('');
  return used;
}

function paintIslamap(wrapper) {
  if (!window.echarts) return;
  ensureIslamapWorld().then(() => {
    if (!wrapper.isConnected) return;
    drawIslamap(wrapper);
  }).catch((err) => {
    console.warn('islamap world map:', err);
    const stage = wrapper.querySelector('.islamap-stage');
    if (stage) stage.textContent = 'تعذر تحميل خارطة العالم.';
  });
}

function islamapMovingArrows(option) {
  const series = option.series || [];
  const graph = series.find((item) => item && item.type === 'graph' && Array.isArray(item.edges) && item.edges.length);
  if (!graph) return;
  const places = new Map();
  (graph.data || []).forEach((node) => {
    const value = node && node.value;
    if (!node || !node.name || !Array.isArray(value)) return;
    const lng = Number(value[0]);
    const lat = Number(value[1]);
    if (Number.isFinite(lng) && Number.isFinite(lat)) places.set(node.name, [lng, lat]);
  });
  const data = [];
  graph.edges.forEach((edge) => {
    const from = places.get(edge.source);
    const to = places.get(edge.target);
    if (!from || !to) return;
    const color = (edge.lineStyle && edge.lineStyle.color) || '#6b3e26';
    edge.lineStyle = Object.assign({}, edge.lineStyle, { opacity: 0, width: 0 });
    data.push({ coords: [from, to], lineStyle: { color, width: 2.2 } });
  });
  if (!data.length) return;
  graph.edgeSymbol = ['none', 'none'];
  graph.lineStyle = Object.assign({}, graph.lineStyle, { opacity: 0, width: 0 });
  series.push({
    type: 'lines',
    coordinateSystem: 'geo',
    polyline: false,
    data,
    z: 4,
    effect: { show: true, symbol: 'arrow', symbolSize: 10, constantSpeed: 70, trailLength: 0 },
    lineStyle: { width: 2.2, opacity: 0.95 }
  });
}

function drawIslamapOption(wrapper, chart, option, family, sea) {
  const next = JSON.parse(JSON.stringify(option));
  const walk = (node) => {
    if (!node || typeof node !== 'object') return;
    if (Object.prototype.hasOwnProperty.call(node, 'map') && node.map && node.map !== 'islamap-world') node.map = 'islamap-world';
    Object.values(node).forEach(walk);
  };
  walk(next);
  if (next.geo && !Array.isArray(next.geo)) {
    next.geo.map = 'islamap-world';
    next.geo.roam = true;
    next.geo.label = Object.assign({}, next.geo.label, { show: false });
  }
  next.backgroundColor = sea;
  const points = [];
  (next.series || []).forEach((series) => {
    (series.data || []).forEach((row) => {
      const value = row && row.value ? row.value : row;
      if (Array.isArray(value) && Number.isFinite(Number(value[0])) && Number.isFinite(Number(value[1]))) {
        points.push([Number(value[0]), Number(value[1])]);
      }
    });
    if (series.label) series.label.fontFamily = `"${family}", Amiri, serif`;
  });
  const frame = islamapFrame(points);
  wrapper._frame = frame;
  if (next.geo && !Array.isArray(next.geo)) {
    next.geo.center = frame.center;
    next.geo.zoom = frame.zoom;
  }
  (next.series || []).forEach((series) => {
    if (series.type === 'map') {
      series.center = frame.center;
      series.zoom = frame.zoom;
      series.roam = true;
    }
  });
  islamapMovingArrows(next);
  chart.setOption(next, { notMerge: true });
  const legendHost = wrapper.querySelector('.islamap-legend');
  if (legendHost) legendHost.innerHTML = '';
  const detailsHost = wrapper.querySelector('.islamap-details');
  if (detailsHost) detailsHost.innerHTML = '';
  requestAnimationFrame(() => chart.resize());
}

function islamapMode(data) {
  const exampleMode = {
    'map-HK': 'distribution',
    'geo-choropleth-scatter': 'cities',
    'geo-graph': 'routes',
    'geo-svg-map': 'routes'
  }[data && data.example];
  if (exampleMode) return exampleMode;
  const mode = String((data && (data.mode || data.kind)) || '');
  if (mode === 'distribution' || mode === 'madhhab') return 'distribution';
  if (mode === 'cities') return 'cities';
  if (mode === 'routes' || mode === 'futuh' || mode === 'ghazawat') return 'routes';
  if (data && (data.routes || []).length) return 'routes';
  if (data && ((data.cities || []).length || (data.places || []).length)) return 'cities';
  return 'distribution';
}

function islamapCategoryColors(labels) {
  const assigned = new Map();
  labels.forEach((label) => {
    const text = String(label || '').trim();
    if (!text || assigned.has(text)) return;
    assigned.set(text, ISLAMAP_CATEGORY_COLORS[assigned.size % ISLAMAP_CATEGORY_COLORS.length]);
  });
  return assigned;
}

function drawIslamapDistribution(wrapper, chart, family, size, sea) {
  const data = wrapper._map;
  const labels = (data.regions || []).map((item) => item.value || item.madhhab || '').filter(Boolean);
  const colors = islamapCategoryColors(labels);
  const merged = new Map();
  (data.regions || []).forEach((item) => {
    const id = islamapResolve(item.id || item.name || item.region);
    const value = String(item.value || item.madhhab || '').trim();
    if (!id || !value) return;
    const arabic = islamapRegionName(id) || id;
    (ISLAMAP_COUNTRIES[id] || []).forEach((name) => {
      const row = merged.get(name) || { name, values: [], arabic, regionId: id };
      if (!row.values.includes(value)) row.values.push(value);
      merged.set(name, row);
    });
  });
  const legend = new Map();
  const regions = [];
  const anchor = [];
  [...merged.values()].forEach((row) => {
    const label = row.values.join(' · ');
    const color = colors.get(row.values[0]) || ISLAMAP_CATEGORY_COLORS[0];
    legend.set(label, color);
    const modern = ISLAMAP_MODERN_COUNTRY[row.name] || row.name;
    const located = (data.points || []).find((point) => point && (point.name === row.arabic || islamapResolve(point.id) === row.regionId));
    if (located && Number.isFinite(Number(located.lng))) anchor.push([Number(located.lng), Number(located.lat)]);
    regions.push({
      name: row.name,
      itemStyle: { areaColor: color },
      label: { show: false },
      tooltip: { formatter: `${modern}<br>${row.arabic}<br>${label}${located ? '<br>' + islamapCoordTip(located.lng, located.lat) : ''}` }
    });
  });
  const loose = [];
  const labeled = new Set();
  (data.regions || []).forEach((item) => {
    const id = islamapResolve(item.id || item.name || item.region);
    const value = String(item.value || item.madhhab || '').trim();
    if (!id || !value || labeled.has(id)) return;
    const spots = ISLAMAP_CITIES.filter((city) => city[4] !== true && ISLAMAP_CITY_REGION[city[0]] === id);
    if (!spots.length) return;
    labeled.add(id);
    const lng = spots.reduce((sum, city) => sum + city[2], 0) / spots.length;
    const lat = spots.reduce((sum, city) => sum + city[3], 0) / spots.length;
    const color = colors.get(value) || ISLAMAP_CATEGORY_COLORS[0];
    legend.set(value, color);
    anchor.push([lng, lat]);
    loose.push({
      name: id,
      value: [lng, lat],
      symbolSize: 12,
      itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
      labelText: `${islamapRegionName(id) || id}\n${value}`,
      tip: `${islamapRegionName(id) || id}<br>${value}`,
      label: {
        show: true,
        formatter: (params) => params.data.labelText,
        position: 'top',
        color: '#1c1917',
        fontFamily: `"${family}", Amiri, serif`,
        fontSize: Math.max(12, size - 1),
        textBorderColor: '#fff',
        textBorderWidth: 2
      }
    });
  });
  const regionIds = (data.regions || []).map((item) => islamapResolve(item.id || item.name || item.region)).filter(Boolean);
  const framePoints = ISLAMAP_CITIES.filter((city) => city[4] !== true && regionIds.includes(ISLAMAP_CITY_REGION[city[0]])).map((city) => [city[2], city[3]]);
  anchor.forEach((point) => framePoints.push(point));
  const framed = islamapFrame(framePoints);
  wrapper._frame = framed;
  const tips = {};
  regions.forEach((region) => { tips[region.name] = region.tooltip.formatter; });
  chart.setOption({
    backgroundColor: sea,
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.componentType === 'geo') return tips[params.name] || '';
        return (params.data && params.data.tip) || '';
      }
    },
    geo: {
      map: 'islamap-world',
      roam: true,
      aspectScale: Math.cos((28 * Math.PI) / 180),
      center: framed.center,
      zoom: framed.zoom,
      scaleLimit: { min: 1, max: 16 },
      itemStyle: { areaColor: '#f4efe6', borderColor: '#b7aa96', borderWidth: 0.6 },
      emphasis: { label: { show: true }, itemStyle: { areaColor: '#e7dcc8' } },
      label: { show: false },
      tooltip: { show: false },
      regions
    },
    series: islamapGraticule(anchor.length ? anchor : ISLAMAP_CITIES.filter((city) => regionIds.includes(ISLAMAP_CITY_REGION[city[0]])).map((city) => [city[2], city[3]])).concat(loose.length ? [{
      type: 'scatter',
      coordinateSystem: 'geo',
      data: loose,
      z: 5,
      labelLayout: { hideOverlap: true }
    }] : [])
  }, { notMerge: true });
  const legendHost = wrapper.querySelector('.islamap-legend');
  if (legendHost) {
    legendHost.innerHTML = [...legend.entries()].map(([name, color]) => `<span><i style="background:${color}"></i>${escapeHtml(name)}</span>`).join('');
  }
  const detailsHost = wrapper.querySelector('.islamap-details');
  if (detailsHost) detailsHost.innerHTML = '';
  requestAnimationFrame(() => chart.resize());
}

function islamapRegionFrame(regionIds) {
  const points = ISLAMAP_CITIES.filter((city) => city[4] !== true && regionIds.includes(ISLAMAP_CITY_REGION[city[0]])).map((city) => [city[2], city[3]]);
  return islamapFrame(points);
}

function drawIslamapCities(wrapper, chart, family, size, sea) {
  const data = wrapper._map;
  const places = islamapPlaces(data);
  const colors = islamapCategoryColors(places.map((place) => place.value || data.subject || 'مدينة'));
  const legend = new Map();
  const byRegion = new Map();
  places.forEach((place) => {
    const regionId = place.region || ISLAMAP_CITY_REGION[place.id] || '';
    if (!regionId) return;
    const list = byRegion.get(regionId) || [];
    list.push(place.value || data.subject || '');
    byRegion.set(regionId, list);
  });
  const regions = [];
  byRegion.forEach((values, regionId) => {
    const unique = [...new Set(values.filter(Boolean))];
    if (unique.length !== 1) return;
    const color = islamapShade(colors.get(unique[0]) || '#2563eb', 0.55);
    (ISLAMAP_COUNTRIES[regionId] || []).forEach((name) => {
      regions.push({
        name,
        itemStyle: { areaColor: color },
        label: { show: false },
        tooltip: { formatter: `${islamapRegionName(regionId) || name} — ${unique[0]}` }
      });
    });
  });
  const nodes = [];
  const seen = new Set();
  places.forEach((place) => {
    if (seen.has(place.id)) return;
    seen.add(place.id);
    const located = islamapLocate(place.id, data);
    if (!located) return;
    const category = place.value || data.subject || 'مدينة';
    const color = colors.get(category) || '#2563eb';
    legend.set(category, color);
    nodes.push({
      name: place.id,
      value: [located.lng, located.lat],
      symbolSize: 16,
      itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
      labelText: located.name,
      tip: `<strong>${escapeHtml(located.name)}</strong>${category ? '<br>' + escapeHtml(category) : ''}<br>${islamapCoordTip(located.lng, located.lat)}${place.note ? '<br>' + escapeHtml(place.note) : ''}`,
      label: {
        show: true,
        formatter: (params) => params.data.labelText,
        position: 'right',
        color: '#1c1917',
        fontFamily: `"${family}", Amiri, serif`,
        fontSize: size,
        textBorderColor: '#fff',
        textBorderWidth: 2
      }
    });
  });
  const frame = islamapFrame(nodes.map((node) => node.value));
  wrapper._frame = frame;
  chart.setOption({
    backgroundColor: sea,
    tooltip: {
      trigger: 'item',
      formatter: (params) => (params.data && params.data.tip) || (params.data && params.data.tooltip && params.data.tooltip.formatter) || ''
    },
    geo: {
      map: 'islamap-world',
      roam: true,
      aspectScale: Math.cos((28 * Math.PI) / 180),
      center: frame.center,
      zoom: frame.zoom,
      scaleLimit: { min: 1, max: 16 },
      itemStyle: { areaColor: '#f4efe6', borderColor: '#b7aa96', borderWidth: 0.6 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: '#e7dcc8' } },
      label: { show: false },
      tooltip: { show: false },
      regions
    },
    series: islamapGraticule(nodes.map((node) => node.value)).concat([{
      type: 'scatter',
      coordinateSystem: 'geo',
      data: nodes,
      z: 5,
      labelLayout: { hideOverlap: true }
    }])
  }, { notMerge: true });
  const legendHost = wrapper.querySelector('.islamap-legend');
  if (legendHost) {
    legendHost.innerHTML = [...legend.entries()].map(([name, color]) => `<span><i style="background:${color}"></i>${escapeHtml(name)}</span>`).join('');
  }
  const detailsHost = wrapper.querySelector('.islamap-details');
  if (detailsHost) {
    detailsHost.innerHTML = places.length ? places.map((place) => `<div class="islamap-era"><strong>${escapeHtml(place.name)}</strong>${place.value ? ' — ' + escapeHtml(place.value) : ''}<br>${islamapCoordTip(place.lng, place.lat)}${place.note ? '<br>' + escapeHtml(place.note) : ''}</div>`).join('') : '';
  }
  requestAnimationFrame(() => chart.resize());
}

function drawIslamap(wrapper) {
  const data = wrapper._map;
  const stage = wrapper.querySelector('.islamap-stage');
  if (!data || !stage || !window.echarts) return;
  if (!wrapper._echart) wrapper._echart = window.echarts.init(stage);
  const chart = wrapper._echart;
  const layer = (wrapper.querySelector('[data-islamap-layer]') || {}).value || 'all';
  const showRegions = layer === 'all' || layer === 'regions';
  const showRoutes = layer === 'all' || layer === 'routes';
  const showCities = layer !== 'regions';
  const font = wrapper.querySelector('[data-islamap-font]');
  const sizeEl = wrapper.querySelector('[data-islamap-size]');
  const bg = wrapper.querySelector('[data-islamap-bg]');
  const family = font ? font.value : 'Amiri';
  const size = Number(sizeEl && sizeEl.value) || 14;
  const sea = (bg && bg.value) || '#e7f0f6';
  wrapper._bg = sea;
  if (bg) {
    bg.style.background = sea;
    bg.style.color = echartInk(sea);
  }
  ensureEchartFont(family);
  if (data.option) {
    drawIslamapOption(wrapper, chart, data.option, family, sea);
    return;
  }
  const mode = islamapMode(data);
  if (mode === 'distribution') {
    drawIslamapDistribution(wrapper, chart, family, size, sea);
    return;
  }
  if (mode === 'cities') {
    drawIslamapCities(wrapper, chart, family, size, sea);
    return;
  }
  const legend = new Map();
  const remember = (value) => {
    const text = String(value || '').trim();
    if (text && !legend.has(text)) legend.set(text, islamapColor(text));
  };
  const eraEl = wrapper.querySelector('[data-islamap-era]');
  const selectedEra = eraEl && eraEl.value !== 'all' ? Number(eraEl.value) : null;
  const allPlaces = islamapPlaces(data);
  const visiblePlaces = selectedEra ? allPlaces.filter((place) => place.century === selectedEra) : allPlaces;
  const subjectText = data.subject || (visiblePlaces.find((place) => place.value) || {}).value || '';
  const baseColor = islamapColor(subjectText || 'مذهب');
  const showPlaces = layer !== 'routes';
  const regionStats = new Map();
  visiblePlaces.forEach((place) => {
    const regionId = place.region || ISLAMAP_CITY_REGION[place.id] || '';
    if (!regionId) return;
    const stat = regionStats.get(regionId) || { weight: 0, scholars: 0, books: 0, cities: new Set(), byCentury: new Map() };
    const weight = place.count || 1;
    stat.weight += weight;
    stat.scholars += place.count || 0;
    stat.books += place.books.length;
    stat.cities.add(place.id);
    if (place.century) stat.byCentury.set(place.century, (stat.byCentury.get(place.century) || 0) + weight);
    regionStats.set(regionId, stat);
  });
  const centurySet = new Set(visiblePlaces.map((place) => place.century).filter(Boolean));
  const countryStyles = new Map();
  if (centurySet.size === 1 && showRegions) {
    const onlyCentury = [...centurySet][0];
    const hue = islamapCenturyColor(onlyCentury);
    regionStats.forEach((stat, regionId) => {
      const regionName = islamapRegionName(regionId) || regionId;
      const tip = `${escapeHtml(regionName)}${subjectText ? ' — ' + escapeHtml(subjectText) : ''} — ق${onlyCentury}هـ<br>${stat.scholars} عالماً، ${stat.books} كتاباً، ${stat.cities.size} مدينة`;
      (ISLAMAP_COUNTRIES[regionId] || []).forEach((name) => {
        countryStyles.set(name, { color: hue, tip });
      });
    });
  }
  const regions = [...countryStyles.entries()].map(([name, style]) => ({
    name,
    itemStyle: { areaColor: style.color },
    label: { show: false },
    tooltip: { formatter: style.tip }
  }));
  const grouped = new Map();
  visiblePlaces.forEach((place) => {
    const group = grouped.get(place.id) || { ...place, parts: [], total: 0, centuries: new Set() };
    group.parts.push(place);
    group.total += place.count || 0;
    if (place.century) group.centuries.add(place.century);
    grouped.set(place.id, group);
  });
  const used = islamapUsedIds(data);
  const placeIds = new Set(allPlaces.map((place) => place.id));
  const nodes = [];
  grouped.forEach((group) => {
    const located = islamapLocate(group.id, data);
    if (!located || located.water) return;
    const parts = group.parts.slice().sort((a, b) => (a.century || 0) - (b.century || 0));
    parts.forEach((part) => {
      if (part.century) legend.set(`ق${part.century}هـ`, islamapCenturyColor(part.century));
    });
    const regionName = islamapRegionName(group.region || ISLAMAP_CITY_REGION[group.id]);
    parts.forEach((part, index) => {
      const color = part.century ? islamapCenturyColor(part.century) : baseColor;
      const angle = parts.length <= 1 ? 0 : (index / parts.length) * Math.PI * 2;
      const radius = parts.length <= 1 ? 0 : 0.55;
      const scholars = part.scholars.length ? `<br>العلماء: ${part.scholars.map(escapeHtml).join('، ')}` : '';
      const books = part.books.length ? `<br>الكتب: ${part.books.map(escapeHtml).join('، ')}` : '';
      const note = part.note ? `<br>${escapeHtml(part.note)}` : '';
      const head = `${part.century ? 'ق' + part.century + 'هـ' : 'بلا قرن'}${part.count ? ' — ' + part.count + ' علماء' : ''}`;
      nodes.push({
        name: `${group.id}-${part.century || 'x'}-${index}`,
        value: [located.lng + Math.cos(angle) * radius, located.lat + Math.sin(angle) * radius, part.count || 0],
        symbolSize: showPlaces ? 16 : 0,
        itemStyle: { color, borderColor: color === '#eab308' ? '#713f12' : '#fff', borderWidth: 2 },
        labelText: located.name,
        tip: `<strong>${escapeHtml(located.name)}</strong>${regionName ? ' — ' + escapeHtml(regionName) : ''}<br>${islamapCoordTip(located.lng, located.lat)}<br>${head}${scholars}${books}${note}`,
        label: {
          show: showPlaces && index === 0,
          formatter: (params) => params.data.labelText,
          position: 'right',
          color: '#292524',
          fontFamily: `"${family}", Amiri, serif`,
          fontSize: size,
          textBorderColor: '#fff',
          textBorderWidth: 2
        }
      });
    });
  });
  ISLAMAP_CITIES.filter((city) => used.has(city[0]) && !placeIds.has(city[0])).forEach((city) => {
    const located = islamapLocate(city[0], data) || { lng: city[2], lat: city[3], name: city[1], water: city[4] === true };
    const item = islamapLookup(data.cities, city[0]);
    const value = item && (item.value || '') || '';
    remember(value);
    const label = [located.name, value, item && item.note, islamapCoordTip(located.lng, located.lat)].filter(Boolean).join(' — ');
    const waypoint = located.water;
    nodes.push({
      name: city[0],
      value: [located.lng, located.lat, 0],
      symbolSize: showCities ? (waypoint ? 7 : 11) : 0,
      itemStyle: { color: value ? islamapColor(value) : (waypoint ? ISLAMAP_SEA_COLOR : '#44403c'), borderColor: '#fff', borderWidth: 1 },
      labelText: located.name,
      tip: escapeHtml(label || city[1]),
      label: {
        show: showCities,
        formatter: (params) => params.data.labelText,
        position: 'right',
        color: '#292524',
        fontFamily: `"${family}", Amiri, serif`,
        fontSize: waypoint ? Math.max(11, size - 2) : size,
        textBorderColor: '#fff',
        textBorderWidth: 2
      }
    });
  });
  const lines = [];
  const framePoints = nodes.map((node) => node.value.slice(0, 2));
  (data.routes || []).forEach((route) => {
    const coords = islamapRouteCoords(route, data);
    if (!coords) return;
    coords.forEach((point) => framePoints.push(point));
    const kind = route.kind || route.type || 'land';
    const color = kind === 'sea' ? ISLAMAP_SEA_COLOR : (kind === 'portage' ? '#8c6a43' : '#6b3e26');
    const label = [route.label, route.year].filter(Boolean).join(' ');
    if (showRoutes) legend.set(kind === 'sea' ? 'مسار بحري' : (kind === 'portage' ? 'نقل على البر' : 'مسار بري'), color);
    lines.push({
      coords,
      lineStyle: { color, width: 2.2, type: kind === 'portage' ? 'dashed' : 'solid', opacity: showRoutes ? 1 : 0 },
      label: {
        show: showRoutes && !!label,
        formatter: label,
        position: 'middle',
        color: '#292524',
        fontFamily: `"${family}", Amiri, serif`,
        fontSize: Math.max(11, size - 1)
      },
      tooltip: { formatter: label }
    });
  });
  const frame = islamapFrame(framePoints);
  wrapper._frame = frame;
  const tips = {};
  regions.forEach((region) => { tips[region.name] = region.tooltip.formatter; });
  chart.setOption({
    backgroundColor: sea,
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.componentType === 'geo') return tips[params.name] || '';
        const tip = params.data && (params.data.tip || (params.data.tooltip && params.data.tooltip.formatter));
        return tip || '';
      }
    },
    geo: {
      map: 'islamap-world',
      roam: true,
      aspectScale: Math.cos((28 * Math.PI) / 180),
      center: frame.center,
      zoom: frame.zoom,
      scaleLimit: { min: 1, max: 16 },
      itemStyle: { areaColor: '#f4efe6', borderColor: '#b7aa96', borderWidth: 0.6 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: '#e7dcc8' } },
      label: { show: false },
      tooltip: { show: false },
      regions
    },
    series: islamapGraticule(framePoints).concat([{
      type: 'scatter',
      coordinateSystem: 'geo',
      data: nodes,
      z: 5,
      labelLayout: { hideOverlap: true },
      emphasis: { scale: 1.18 }
    }, {
      type: 'lines',
      coordinateSystem: 'geo',
      polyline: true,
      data: lines,
      effect: { show: showRoutes, symbol: 'arrow', symbolSize: 8, period: 7, trailLength: 0 },
      lineStyle: { width: 2, opacity: showRoutes ? 1 : 0 }
    }])
  }, { notMerge: true });
  const legendHost = wrapper.querySelector('.islamap-legend');
  if (legendHost) {
    legendHost.innerHTML = [...legend.entries()].map(([name, color]) => `<span><i style="background:${color}"></i>${escapeHtml(name)}</span>`).join('');
  }
  const detailsHost = wrapper.querySelector('.islamap-details');
  if (detailsHost) {
    if (!visiblePlaces.length) {
      detailsHost.innerHTML = '';
    } else {
      const byCentury = new Map();
      visiblePlaces.forEach((place) => {
        const key = place.century || 0;
        if (!byCentury.has(key)) byCentury.set(key, []);
        byCentury.get(key).push(place);
      });
      detailsHost.innerHTML = [...byCentury.entries()].sort((a, b) => a[0] - b[0]).map(([century, places]) => {
        const scholars = places.reduce((sum, place) => sum + (place.count || 0), 0);
        const books = places.reduce((sum, place) => sum + place.books.length, 0);
        const rows = places.map((place) => {
          const names = place.scholars.length ? place.scholars.map(escapeHtml).join('، ') : 'لا أسماء في النص';
          const works = place.books.length ? ` — الكتب: ${place.books.map(escapeHtml).join('، ')}` : '';
          return `<span><strong>${escapeHtml(place.name)}</strong>${place.count ? ' ' + place.count : ''}: ${names}${works}</span>`;
        }).join('<br>');
        return `<div class="islamap-era"><strong>${century ? 'ق' + century + 'هـ' : 'بلا قرن'} — ${places.length} مدينة، ${scholars} عالماً، ${books} كتاباً</strong><br>${rows}</div>`;
      }).join('');
    }
  }
  requestAnimationFrame(() => chart.resize());
}

function fitIslamap(wrapper) {
  const chart = wrapper && wrapper._echart;
  if (!chart) return;
  const frame = wrapper._frame || ISLAMAP_VIEW;
  const series = (chart.getOption().series || [])[0];
  if (series && series.type === 'map') {
    chart.setOption({ series: [{ center: frame.center, zoom: frame.zoom }] });
    return;
  }
  chart.setOption({ geo: { center: frame.center, zoom: frame.zoom } });
}

async function shareIslamapImage(wrapper) {
  const chart = wrapper && wrapper._echart;
  if (!chart || typeof window.shareCapturedImage !== 'function') return;
  const url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: wrapper._bg || '#e7f0f6' });
  let blob = null;
  try { blob = await (await fetch(url)).blob(); } catch (err) { blob = null; }
  await window.shareCapturedImage(blob, echartVisualTitle(wrapper, 'خارطة'), 'تعذر تجهيز صورة الخارطة للمشاركة');
}

function downloadIslamapShot(wrapper) {
  const chart = wrapper && wrapper._echart;
  if (!chart) return;
  const title = echartVisualTitle(wrapper, 'خارطة');
  const link = document.createElement('a');
  link.href = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: wrapper._bg || '#e7f0f6' });
  link.download = `${title}.png`;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function setIslamapExpanded(wrapper, expanded) {
  if (!wrapper) return;
  if (expanded) {
    if (!wrapper.classList.contains('is-expanded')) {
      wrapper._homeParent = wrapper.parentNode;
      wrapper._homeNext = wrapper.nextSibling;
      document.body.appendChild(wrapper);
    }
    wrapper.classList.add('is-expanded');
  } else {
    wrapper.classList.remove('is-expanded');
    if (wrapper._homeParent) wrapper._homeParent.insertBefore(wrapper, wrapper._homeNext);
  }
  requestAnimationFrame(() => { if (wrapper._echart) wrapper._echart.resize(); });
}

if (!window._islamapClicksBound) {
  window._islamapClicksBound = true;
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-islamap-share], [data-islamap-fit], [data-islamap-reset], [data-islamap-shot], [data-islamap-expand], [data-islamap-close], [data-islamap-code]');
    if (!button) return;
    const wrapper = button.closest('.islamap-render-wrapper');
    if (!wrapper) return;
    event.preventDefault();
    if (button.dataset.islamapFit) { fitIslamap(wrapper); return; }
    if (button.dataset.islamapReset) { fitIslamap(wrapper); paintIslamap(wrapper); return; }
    if (button.dataset.islamapShare) { shareIslamapImage(wrapper); return; }
    if (button.dataset.islamapShot) { downloadIslamapShot(wrapper); return; }
    if (button.dataset.islamapCode) {
      const code = wrapper.querySelector('.echart-code');
      if (code) code.hidden = !code.hidden;
      return;
    }
    setIslamapExpanded(wrapper, button.dataset.islamapClose ? false : !wrapper.classList.contains('is-expanded'));
  });
  document.addEventListener('change', (event) => {
    const control = event.target.closest('[data-islamap-layer], [data-islamap-era], [data-islamap-font], [data-islamap-size], [data-islamap-bg]');
    if (!control) return;
    const wrapper = control.closest('.islamap-render-wrapper');
    if (!wrapper) return;
    drawIslamap(wrapper);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const open = document.querySelector('.islamap-render-wrapper.is-expanded');
    if (open) setIslamapExpanded(open, false);
  });
}

async function requestChatIslamap(type) {
  if (chatGraphBusy) return;
  const session = chatSessions.find(item => item.id === activeSessionId);
  const source = session && [...session.messages].reverse().find(item => item.role === 'assistant' && !item.chart_kind && !item.map_kind && stripChartFences(item.content).length > 40);
  if (!source) {
    if (typeof showToast === 'function') showToast('لا توجد نتيجة سابقة لرسم خارطتها');
    return;
  }
  const control = startChatRun();
  const container = document.getElementById('chatMessagesContainer');
  const typingBubble = document.createElement('div');
  typingBubble.className = 'message-bubble assistant';
  typingBubble.innerHTML = `<div class="message-avatar">مج</div><div class="message-content"><span class="graph-wait-note">جارٍ استخلاص البيانات ثم اختيار الخارطة والإحداثيات، فضلاً انتظر</span></div>`;
  if (container) {
    container.appendChild(typingBubble);
    if (typeof scrollToBottom === 'function') scrollToBottom();
  }
  const material = stripChartFences(source.content).slice(0, 36000);
  const selectedModel = document.getElementById('chatModelSelect')?.value
    || localStorage.getItem('almojtahed_active_chat_model')
    || '';
  if (!selectedModel) {
    if (typingBubble.parentNode) typingBubble.remove();
    endChatRun();
    if (typeof showToast === 'function') showToast('اختر النموذج من القائمة المنسدلة قبل الرسم');
    return;
  }
  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) {}
  try {
    const response = await fetch('/api/islamap/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: control.signal,
      body: JSON.stringify({
        text: material,
        kind: type,
        model: selectedModel,
        api_key: savedKeys.openrouter || '',
        tavily_key: (typeof readTavilyKey === 'function' ? readTavilyKey() : '') || savedKeys.tavily || ''
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'تعذر رسم الخارطة');
    if (typingBubble.parentNode) typingBubble.remove();
    session.messages.push({
      role: 'assistant',
      content: data.reply || 'تعذر إظهار الخارطة.',
      model: data.model || selectedModel,
      map_kind: type
    });
    saveChatSessions();
    renderSessionMessages(activeSessionId);
  } catch (err) {
    if (typingBubble.parentNode) typingBubble.remove();
    if (chatStopped(err)) {
      if (typeof showToast === 'function') showToast('تم الإيقاف');
    } else if (typeof showToast === 'function') showToast(err.message || 'تعذر رسم الخارطة');
  } finally {
    endChatRun();
  }
}

function insertIslamapKind(select) {
  const type = select.value;
  select.value = '';
  select.dispatchEvent(new CustomEvent('theme-select-sync'));
  if (!type) return;
  requestChatIslamap(type);
}

window.insertIslamapKind = insertIslamapKind;
window.requestChatIslamap = requestChatIslamap;
window.renderIslamapBlocks = renderIslamapBlocks;

function insertGraphKind(select) {
  const type = select.value;
  const inputId = select.dataset.graphTarget || 'chatInputText';
  select.value = '';
  select.dispatchEvent(new CustomEvent('theme-select-sync'));
  if (!type) return;
  if (inputId === 'chatInputText') {
    requestChatGraph(type);
    return;
  }
  applyChatOutputTemplate(type, inputId);
}

window.insertGraphKind = insertGraphKind;
window.applyChatOutputTemplate = applyChatOutputTemplate;
window.autoRenderChatInteractiveWidgets = autoRenderChatInteractiveWidgets;
window.renderEchartsBlocks = renderEchartsBlocks;
window.zoomChatMarkmap = zoomChatMarkmap;
window.fitChatMarkmap = fitChatMarkmap;
window.fitChatIsnad = fitChatIsnad;
window.toggleChatCodeBlock = toggleChatCodeBlock;

// نمط توزيع واستدعاء الوكلاء المساعدين في الشات الذكي (متوازي vs مباشر - حفظ خط الرجعة)
window.chatRawMcp = localStorage.getItem('almojtahed_chat_raw_mcp') === '1';

window.toggleChatRawMcp = function() {
  window.chatRawMcp = !window.chatRawMcp;
  localStorage.setItem('almojtahed_chat_raw_mcp', window.chatRawMcp ? '1' : '0');
  updateChatRawMcpUI();
  if (typeof showToast === 'function') {
    showToast(window.chatRawMcp
      ? '🔌 وضع MCP الخام مفعّل: النموذج يقود أدوات المجتهد مباشرة، بلا وكلاء، مع ضبط إحالات فقط'
      : '↩️ عودة إلى الوضع المعتاد (وكلاء وتوجيه واسترجاع)', 3000);
  }
};

window.updateChatRawMcpUI = function() {
  const btn = document.getElementById('chatRawMcpToggleBtn');
  if (!btn) return;
  btn.classList.toggle('mode-raw', !!window.chatRawMcp);
  btn.title = window.chatRawMcp
    ? 'وضع MCP الخام مفعّل الآن: النموذج مع أدوات المجتهد فقط وقاعدة إحالة واحدة تضبط النقل والعزو، بلا وكلاء ولا استرجاع مسبق (انقر للإيقاف)'
    : 'MCP خام مباشر: النموذج المختار يقود أدوات خادم المجتهد بنفسه كما يفعل أي عميل MCP خارجي — بلا وكلاء ولا خط استرجاع، مع قاعدة إحالة واحدة تضبط النقل والعزو فقط (انقر للتفعيل)';
};

window.chatAgentDispatchMode = localStorage.getItem('almojtahed_chat_dispatch_mode') || 'parallel';

window.toggleChatDispatchMode = function() {
  window.chatAgentDispatchMode = (window.chatAgentDispatchMode === 'direct') ? 'parallel' : 'direct';
  localStorage.setItem('almojtahed_chat_dispatch_mode', window.chatAgentDispatchMode);
  updateChatDispatchModeUI();
  if (typeof showToast === 'function') {
    const isDirect = window.chatAgentDispatchMode === 'direct';
    showToast(isDirect 
      ? '🎯 تم تفعيل النمط المباشر الموحد (استدعاء النموذج الرئيسي فقط - خط الرجعة)'
      : '⚡ تم تفعيل النمط التوكيلي الموزع (استدعاء نماذج الوكلاء المحددين بالتوازي)', 3000);
  }
};

window.updateChatDispatchModeUI = function() {
  const btn = document.getElementById('chatDispatchModeToggleBtn');
  const icon = document.getElementById('chatDispatchModeIcon');
  const txt = document.getElementById('chatDispatchModeText');
  if (typeof updateCompareDispatchModeUI === 'function') updateCompareDispatchModeUI();
  if (!btn) return;
  const isDirect = window.chatAgentDispatchMode === 'direct';
  if (isDirect) {
    btn.classList.add('mode-direct');
    if (icon) icon.textContent = '🎯';
    if (txt) txt.textContent = 'موحد مباشر';
    btn.title = 'النمط المباشر الموحد: دمج الشواهد وتمريرها دفعة واحدة لنموذج الشات (خط الرجعة) - انقر للتبديل للتوزيع المتوازي ⚡';
  } else {
    btn.classList.remove('mode-direct');
    if (icon) icon.textContent = '⚡';
    if (txt) txt.textContent = 'توزيع متوازي';
    btn.title = 'النمط التوكيلي الموزع: استدعاء نماذج الوكلاء المخصصة بالتوازي وضخ الخلاصات للنموذج المختار - انقر للتبديل للمباشر 🎯';
  }
};

// =============================================================================
// إدارة واستدعاء الأدوات المساعدة داخل الشات (التشجير، الشارتات، الأسانيد، الحساب)
// =============================================================================
const CHAT_ENABLED_TOOLS_KEY = 'almojtahed_chat_enabled_tools';
let _cachedToolsForChat = [];

function getChatEnabledToolIds() {
  let ids = ['markmap_mindmap', 'charts_metrics', 'echarts_charts'];
  try {
    const saved = localStorage.getItem(CHAT_ENABLED_TOOLS_KEY);
    if (saved) ids = JSON.parse(saved);
  } catch (e) {
    console.error('Error reading chat enabled tools:', e);
  }
  if (!Array.isArray(ids)) ids = ['markmap_mindmap', 'charts_metrics', 'echarts_charts'];
  if (localStorage.getItem('almojtahed_echarts_chat_added') !== '1') {
    if (!ids.includes('echarts_charts')) ids.push('echarts_charts');
    try {
      localStorage.setItem(CHAT_ENABLED_TOOLS_KEY, JSON.stringify(ids));
      localStorage.setItem('almojtahed_echarts_chat_added', '1');
    } catch (e) {}
  }
  if (localStorage.getItem('almojtahed_islamap_chat_added') !== '1') {
    if (!ids.includes('islamap_map')) ids.push('islamap_map');
    try {
      localStorage.setItem(CHAT_ENABLED_TOOLS_KEY, JSON.stringify(ids));
      localStorage.setItem('almojtahed_islamap_chat_added', '1');
    } catch (e) {}
  }
  return ids;
}

async function fetchAllToolsForChat() {
  if (window.toolsState && Array.isArray(window.toolsState.tools) && window.toolsState.tools.length > 0) {
    _cachedToolsForChat = window.toolsState.tools;
    return _cachedToolsForChat;
  }
  try {
    const res = await fetch('/api/tools');
    if (res.ok) {
      const data = await res.json();
      _cachedToolsForChat = (data.tools || (Array.isArray(data) ? data : [])).map(t => ({
        ...t,
        tool_type: t.tool_type || (t.type === 'python_script' ? 'python_code' : 'ready_web_lib'),
        description: t.description || t.desc || '',
        name: t.name || t.id
      }));
      return _cachedToolsForChat;
    }
  } catch (e) {
    console.warn('Could not fetch tools for chat:', e);
  }
  return _cachedToolsForChat;
}

// بناء القالب التوجيهي والمثال المطلوب عند استدعاء الأداة في الشات
function buildToolPromptTemplate(tool) {
  const toolName = tool.name || 'الأداة المساعدة';
  if (tool.architect_spec || tool.application_instruction || tool.example_input) {
    const spec = tool.architect_spec || {};
    const exampleInput = tool.example_input || spec.example_input || tool.mock_data || tool.mock_test_data || {};
    const exampleOutput = tool.example_output || spec.example_output || {};
    return `طبق أداة «${toolName}» على ناتج البحث الجاهز السابق في هذه المحادثة.

[عقد تطبيق الأداة]:
- البيانات هي ناتج البحث الجاهز الذي أنتجته من مخزن الشاملة في هذه المحادثة أو المشروع؛ لا تسأل الباحث عن مصدرها ولا تطلب منه إدخالها.
- استخرج الحقول من ناتج البحث وفق المثال، ثم أخرج النتيجة بالشكل الذي صممت له الأداة تلقائياً: ${spec.output_kind || spec.display || tool.description || tool.desc || ''}
- تعليمات التطبيق: ${tool.application_instruction || spec.application_instruction || tool.description || tool.desc || ''}
- مثال لمدخل من ناتج بحث جاهز:
${typeof exampleInput === 'string' ? exampleInput : JSON.stringify(exampleInput, null, 2)}
- مثال للمخرج المطلوب:
${typeof exampleOutput === 'string' ? exampleOutput : JSON.stringify(exampleOutput, null, 2)}

ما أريده من هذه الأداة تحديداً: (فضلا حدد هنا ما تريده من هذه الأداة)`;
  }
  let exampleStr = '';

  // استخراج المثال من mock_data أو mock_test_data
  let mock = tool.mock_data || tool.mock_test_data;
  if (typeof mock === 'string') {
    try {
      mock = JSON.parse(mock);
    } catch (e) {
      exampleStr = mock.trim();
    }
  }

  if (!exampleStr && mock && typeof mock === 'object') {
    if (mock.markdown) {
      exampleStr = String(mock.markdown).trim();
    } else {
      exampleStr = JSON.stringify(mock, null, 2);
    }
  }

  if (!exampleStr && tool.test_input) {
    exampleStr = typeof tool.test_input === 'string' ? tool.test_input.trim() : JSON.stringify(tool.test_input, null, 2);
  }

  if (!exampleStr) {
    exampleStr = (tool.description || tool.desc || 'لا يوجد مثال مدون للأداة').trim();
  }

  return `استخدم هذه الاداة (فضلا حدد هنا ما تريده من هذه الأداة)\n\n[تنبيه للنموذج بكيفية الإخراج واستخدام الأداة: ${toolName}]:\n${exampleStr}`;
}

const CHAT_PROMPT_ONLY_TOOLS = new Set(['markmap_mindmap', 'charts_metrics', 'echarts_charts', 'islamap_map', 'astronomy_hijri_sync', 'hadith_isnad_tree', 'web_nasa_catalog', 'coc_markmap']);

function toolRunsInBackground(tool) {
  if (!tool || CHAT_PROMPT_ONLY_TOOLS.has(tool.id)) return false;
  return true;
}

// عند الضغط على زر الأداة في الشريط الجانبي للشات
async function useToolInChatPrompt(toolId) {
  let tools = await fetchAllToolsForChat();
  try {
    const res = await fetch('/api/tools');
    if (res.ok) {
      const data = await res.json();
      const list = data.tools || (Array.isArray(data) ? data : []);
      if (list.length) {
        tools = list.map(t => ({
          ...t,
          tool_type: t.tool_type || (t.type === 'python_script' ? 'python_code' : 'ready_web_lib'),
          description: t.description || t.desc || '',
          name: t.name || t.id
        }));
        _cachedToolsForChat = tools;
        if (window.toolsState) window.toolsState.tools = tools;
      }
    }
  } catch (e) {}
  const tool = (tools || []).find(t => t.id === toolId);
  if (!tool) {
    showToast('تعذر العثور على بيانات الأداة', true);
    return;
  }

  if (tool.id === 'echarts_charts') {
    requestChatEcharts('multi');
    return;
  }
  if (tool.id === 'islamap_map') {
    requestChatIslamap('full');
    return;
  }

  if (toolRunsInBackground(tool)) {
    await applyAdoptedToolInChat(tool);
    return;
  }

  const promptText = buildToolPromptTemplate(tool);
  const input = document.getElementById('chatInputText');
  if (input) {
    input.value = promptText;
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 260)}px`;

    // وضع التحديد التلقائي على عبارة (فضلا حدد هنا ما تريده من هذه الأداة)
    const targetPhrase = '(فضلا حدد هنا ما تريده من هذه الأداة)';
    const startIdx = promptText.indexOf(targetPhrase);
    input.focus();
    if (startIdx !== -1) {
      input.setSelectionRange(startIdx, startIdx + targetPhrase.length);
    } else {
      input.scrollTop = 0;
    }
  }

  // نسخ إلى الحافظة
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(promptText).catch(() => {});
  }

  showToast(`تم إدراج قالب «${tool.name}» في مربع المحادثة 🛠️`);
}

// عرض قائمة أزرار الأدوات المساعدة المفعلة في الشريط الجانبي للشات
async function renderChatAssistantTools() {
  const container = document.getElementById('chatAssistantToolsList');
  if (!container) return;

  const enabledIds = getChatEnabledToolIds();
  const tools = await fetchAllToolsForChat();

  const activeTools = tools.filter(t => enabledIds.includes(t.id) && t.enabled !== false && t.id !== 'echarts_charts' && t.id !== 'islamap_map');

  if (activeTools.length === 0) {
    container.innerHTML = `
      <div class="chat-tools-empty-hint">
        لا توجد أدوات مفعلة في الشات حالياً.
        <br>
        <button type="button" class="btn-flat-secondary" onclick="switchMainTab('tools')" style="margin-top: 6px; padding: 2px 8px; font-size: 11px; color: var(--accent-clay);">
          تفعيل أدوات من المستودع ⚙️
        </button>
      </div>
    `;
    return;
  }

  container.innerHTML = activeTools.map(t => {
    const isWeb = t.tool_type === 'ready_web_lib' || t.type === 'web_library';
    const executable = toolRunsInBackground(t);
    const icon = t.id === 'markmap_mindmap' ? '🌳' : (t.id === 'echarts_charts' ? '📈' : (isWeb ? '📊' : '⚙️'));
    const badge = executable ? 'تطبيق ⚡' : 'إدراج ✍️';
    const title = executable ? `تطبيق «${t.name}» بمكتباتها على ناتج البحث` : `إدراج قالب واستدعاء «${t.name}» في الشات`;
    return `
      <button type="button" class="btn-chat-tool-action" onclick="useToolInChatPrompt('${escapeHtml(t.id)}')" title="${escapeHtml(title)}">
        <span class="tool-btn-icon">${icon}</span>
        <span class="tool-btn-name">${escapeHtml(t.name)}</span>
        <span class="tool-btn-badge">${badge}</span>
      </button>
    `;
  }).join('');
}

function summarizeToolOutput(name, output) {
  const title = `نتيجة تطبيق أداة «${name}» على ناتج البحث:`;
  if (!output || typeof output !== 'object') return title;
  const lines = [title];
  if (output.issue) lines.push('', `**المسألة:** ${output.issue}`);
  if (output.range && (output.range.from || output.range.to)) {
    lines.push(`**المدى:** ${output.range.from ?? ''}–${output.range.to ?? ''} هـ`);
  }
  if (output.counts && typeof output.counts === 'object') {
    lines.push('', '**عدد القائلين:**');
    Object.entries(output.counts).forEach(([label, count]) => lines.push(`- ${label}: ${count}`));
  }
  if (Array.isArray(output.entries) && output.entries.length) {
    lines.push('', '| الفقيه | السنة | القول |', '| --- | --- | --- |');
    output.entries.forEach((entry) => {
      lines.push(`| ${entry.name || ''} | ${entry.year ?? ''} | ${entry.position || entry.القول || ''} |`);
    });
  }
  if (output.status === 'error' || output.message) {
    lines.push('', String(output.message || 'لم تُنتج الأداة رسماً من هذا النص.'));
  }
  if (lines.length === 1) {
    const preview = { ...output };
    delete preview.html;
    delete preview.figure_json;
    delete preview.html_path;
    lines.push('', '```json', JSON.stringify(preview, null, 2), '```');
  }
  return lines.join('\n');
}

function plotlyFigureFromOutput(output) {
  const figure = output && output.figure_json;
  if (!figure || !Array.isArray(figure.data) || !figure.data.length) return null;
  return { data: figure.data, layout: figure.layout || {} };
}

function formatAppliedToolOutput(name, output) {
  const title = `نتيجة تطبيق أداة «${name}» على ناتج البحث:`;
  if (output == null) return { markdown: `${title}\n\nلم تُرجع الأداة نتيجة.`, html: '', figure: null };
  if (typeof output === 'string') {
    const trimmed = output.trim();
    if (trimmed.startsWith('<')) return { markdown: title, html: trimmed, figure: null };
    return { markdown: `${title}\n\n${trimmed}`, html: '', figure: null };
  }
  if (typeof output === 'object') {
    const figure = plotlyFigureFromOutput(output);
    const html = figure ? '' : (typeof output.html === 'string' ? output.html : '');
    return { markdown: summarizeToolOutput(name, output), html, figure };
  }
  return { markdown: `${title}\n\n${String(output)}`, html: '', figure: null };
}

function placeToolResultHtml(node, html) {
  if (!node || !html) return;
  const frame = document.createElement('iframe');
  frame.title = 'رسم الأداة';
  frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-popups');
  frame.style.width = '100%';
  frame.style.height = '800px';
  frame.style.border = '1px solid var(--border-subtle)';
  frame.style.borderRadius = '8px';
  frame.style.background = '#fff';
  frame.srcdoc = html;
  node.replaceChildren(frame);
}

async function mountChatToolFigures(container, session) {
  if (!container || !session) return;
  const figures = [...container.querySelectorAll('[data-tool-figure="1"]')];
  const htmlNodes = [...container.querySelectorAll('[data-tool-html="1"]')];
  if (figures.length) {
    try {
      await loadAdoptedToolScript('https://cdn.plot.ly/plotly-2.35.2.min.js');
    } catch (e) {}
  }
  figures.forEach((node) => {
    if (node.dataset.mounted === '1') return;
    node.dataset.mounted = '1';
    const index = Number(node.getAttribute('data-tool-index'));
    const figure = session.messages[index] && session.messages[index].tool_figure;
    if (window.Plotly && figure) {
      window.Plotly.newPlot(node, figure.data || [], figure.layout || {}, { responsive: true, displaylogo: false });
    } else {
      node.textContent = 'تعذر تحميل مكتبة الرسم، والجدول أعلاه هو نتيجة الأداة.';
    }
  });
  htmlNodes.forEach((node) => {
    if (node.dataset.mounted === '1') return;
    node.dataset.mounted = '1';
    const index = Number(node.getAttribute('data-tool-index'));
    const html = session.messages[index] && session.messages[index].tool_html;
    placeToolResultHtml(node, html);
  });
}

async function loadAdoptedToolScript(url) {
  if (!url || document.querySelector(`script[data-tool-src="${CSS.escape(url)}"]`)) return;
  await new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = url;
    script.async = false;
    script.dataset.toolSrc = url;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`تعذر تحميل المكتبة: ${url}`));
    document.head.appendChild(script);
  });
}

async function mountAdoptedWebTool(mount, spec, researchText) {
  if (!mount || !spec) return;
  const urls = Array.isArray(spec.cdn_urls) ? spec.cdn_urls.slice() : [];
  if (spec.library_url && /^https:\/\/.+\.js(?:\?|$)/.test(spec.library_url) && !urls.includes(spec.library_url)) {
    urls.push(spec.library_url);
  }
  mount.innerHTML = '<span class="tool-coder-spinner" aria-hidden="true"></span> جارٍ تحميل مكتبات الأداة في الصفحة. فضلاً الانتظار.';
  try {
    for (const url of urls) await loadAdoptedToolScript(url);
    mount.innerHTML = '';
    const data = { research_text: researchText, text: researchText, content: researchText, answer: researchText };
    if (spec.init_script) {
      const runner = new Function('input', 'mount', 'data', 'researchText', spec.init_script);
      runner(researchText, mount, data, researchText);
    }
    if (!mount.childNodes.length) {
      mount.textContent = urls.length
        ? 'حُمّلت مكتبات الأداة، ولم ترسم نتيجة داخل اللوحة.'
        : 'الأداة بلا سكربت عرض يمكن تشغيله في الصفحة.';
    }
  } catch (err) {
    mount.textContent = `تعذر تشغيل مكتبة الأداة في الصفحة: ${err.message}`;
  }
}

function mountChatAppliedWebTools(container, session) {
  if (!container || !session) return;
  container.querySelectorAll('[data-tool-web="1"]').forEach((mount) => {
    if (mount.dataset.mounted === '1') return;
    mount.dataset.mounted = '1';
    const index = Number(mount.getAttribute('data-tool-index'));
    const spec = session.messages[index] && session.messages[index].tool_web;
    let researchText = '';
    for (let i = index - 1; i >= 0; i -= 1) {
      const message = session.messages[i];
      if (message && message.role === 'assistant' && message.content && !message.tool_applied) {
        researchText = message.content;
        break;
      }
    }
    mountAdoptedWebTool(mount, spec, researchText);
  });
}

async function applyStoredResearchTool(tool, researchText) {
  const res = await fetch('/api/tools/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool_id: tool.id, research_text: researchText || '' })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.success === false) {
    return { ok: false, error: data.detail || data.error || data.message || 'تعذر تطبيق الأداة' };
  }
  if (data.kind === 'web') {
    return {
      ok: true,
      kind: 'web',
      markdown: `نتيجة تطبيق أداة «${tool.name}» تُعرض بلوحتها بعد تحميل مكتباتها.`,
      web: {
        init_script: data.init_script || '',
        cdn_urls: data.cdn_urls || [],
        library_url: data.library_url || ''
      }
    };
  }
  const rendered = formatAppliedToolOutput(tool.name, data.output);
  return { ok: true, kind: 'python', markdown: rendered.markdown, html: rendered.html || '', figure: rendered.figure || null };
}

let chatToolApplyBusy = false;

async function applyAdoptedToolInChat(tool) {
  if (chatToolApplyBusy) return;
  const session = (typeof chatSessions !== 'undefined' ? chatSessions : []).find(s => s.id === activeSessionId);
  if (!session) {
    if (typeof showToast === 'function') showToast('افتح محادثة فيها نتيجة بحث أولاً', true);
    return;
  }
  const source = [...session.messages].reverse().find(m => m.role === 'assistant' && m.content && !m.tool_applied);
  if (!source || !String(source.content).trim()) {
    if (typeof showToast === 'function') showToast('طبّق الأداة بعد ظهور نتيجة البحث في المحادثة', true);
    return;
  }
  chatToolApplyBusy = true;
  const container = document.getElementById('chatMessagesContainer');
  const wait = document.createElement('div');
  wait.className = 'message-bubble assistant';
  wait.innerHTML = `
    <div class="message-avatar">مج</div>
    <div class="message-content">
      <span class="tool-coder-spinner" aria-hidden="true"></span>
      جارٍ تطبيق «${escapeHtml(tool.name || 'الأداة')}» بمكتباتها المنصّبة. فضلاً الانتظار.
    </div>
  `;
  if (container) {
    container.appendChild(wait);
    if (typeof scrollToBottom === 'function') scrollToBottom();
  }
  try {
    const applied = await applyStoredResearchTool(tool, source.content);
    if (!applied.ok) throw new Error(applied.error || 'تعذر تطبيق الأداة');
    session.messages.push({
      role: 'assistant',
      content: applied.markdown,
      tool_html: applied.html || '',
      tool_figure: applied.figure || null,
      tool_web: applied.web || null,
      tool_applied: true
    });
    if (typeof saveChatSessions === 'function') saveChatSessions();
    renderSessionMessages(activeSessionId);
  } catch (err) {
    session.messages.push({
      role: 'assistant',
      content: `تعذر تطبيق أداة «${tool.name || 'الأداة'}»: ${err.message}`,
      tool_applied: true
    });
    if (typeof saveChatSessions === 'function') saveChatSessions();
    renderSessionMessages(activeSessionId);
  } finally {
    chatToolApplyBusy = false;
    if (wait.parentNode) wait.remove();
  }
}

window.formatAppliedToolOutput = formatAppliedToolOutput;
window.applyStoredResearchTool = applyStoredResearchTool;
window.mountAdoptedWebTool = mountAdoptedWebTool;
window.placeToolResultHtml = placeToolResultHtml;
window.mountChatToolFigures = mountChatToolFigures;

/* «تعليق وشرح مختصر»: تخصصات بأيقونات وكتب ثابتة معتمدة لكل فن،
   يبحث النقر على أيقونة في كتب ذلك الفن وحده (١٠ شواهد، وسياق
   لا يتجاوز ٦٤٠٠٠) ويخرج شرحًا مختصرًا للنص المحدد */
const SELECTION_RESEARCH_KINDS = [
  { id: 'tafsir', label: 'تفسير', icon: '📖', angle: 'من جهة التفسير: المعنى الإجمالي وبيان غريب الألفاظ وخلاصة أقوال المفسرين',
    books: ['جامع البيان عن تأويل آي القرآن', 'الجامع لأحكام القرآن', 'التحرير والتنوير', 'تيسير الكريم الرحمن'] },
  { id: 'fiqh', label: 'فقه', icon: '⚖️', angle: 'من الجهة الفقهية: صورة المسألة وأبرز الأقوال والأدلة',
    books: ['الاستذكار', 'بداية المجتهد ونهاية المقتصد', 'المغني لابن قدامة', 'الموسوعة الفقهية الكويتية'] },
  { id: 'aqeeda', label: 'عقيدة', icon: '🕌', angle: 'من الناحية العقدية: تقرير عقيدة أهل السنة والجماعة وأدلتها',
    books: ['فتح المجيد شرح كتاب التوحيد', 'العقيدة الواسطية', 'شرح العقيدة الطحاوية', 'العقيدة التدمرية', 'الاعتصام', 'الملل والنحل', 'العواصم من القواصم'] },
  { id: 'hadith', label: 'حديث', icon: '📜', angle: 'من جهة شرح الحديث: المعنى الإجمالي وفقه الحديث وأبرز فوائده',
    books: ['فتح الباري شرح صحيح البخاري', 'نيل الأوطار', 'طرح التثريب', 'شرح صحيح مسلم'] },
  { id: 'takhrij', label: 'تخريج', icon: '🔍', angle: 'من جهة التخريج: مصادر الحديث ودرجته وخلاصة أقوال المحدثين فيه',
    books: ['تحفة الأشراف بمعرفة الأطراف', 'التلخيص الحبير', 'نصب الراية', 'إرواء الغليل', 'سلسلة الأحاديث الصحيحة', 'سلسلة الأحاديث الضعيفة'] },
  { id: 'usul', label: 'أصول وقواعد ومقاصد', icon: '🧭', angle: 'من جهة أصول الفقه والقواعد والمقاصد: الأصل أو القاعدة المؤثرة في النص وخلاصتها',
    books: ['الموافقات', 'روضة الناظر', 'تقرير القواعد وتحرير الفوائد', 'المنثور في القواعد', 'الفروق للقرافي', 'الأشباه والنظائر للسيوطي'] },
  { id: 'language', label: 'لغة', icon: '✒️', angle: 'من الجهة اللغوية: معاني الألفاظ وغريبها وشواهدها',
    books: ['لسان العرب', 'تاج العروس', 'المصباح المنير', 'غريب الحديث'] },
  { id: 'tarikh', label: 'تاريخ', icon: '🏺', angle: 'من الجهة التاريخية: سياق الخبر أو الحدث وخلاصة ما ذكره المؤرخون',
    books: ['تاريخ الرسل والملوك', 'الكامل في التاريخ', 'البيان المغرب', 'البداية والنهاية', 'كتاب العبر', 'تاريخ ابن حجي', 'شذرات الذهب', 'تاريخ اليمن', 'نزهة النظار', 'مرآة الحرمين', 'تاريخ الدولة العلية العثمانية'] },
  { id: 'sira', label: 'سيرة وتراجم', icon: '👥', angle: 'من جهة السيرة والتراجم: تعريف موجز بصاحب الترجمة أو خبر السيرة المتعلق بالنص',
    books: ['السيرة النبوية لابن هشام', 'السيرة النبوية لابن إسحاق', 'الروض الأنف', 'تقريب التهذيب', 'ميزان الاعتدال', 'سير أعلام النبلاء', 'تاريخ بغداد', 'تاريخ دمشق', 'سمط اللآلي', 'النجوم الزاهرة', 'الإصابة في تمييز الصحابة'] },
  { id: 'mudun', label: 'مدن وأماكن', icon: '🗺️', angle: 'من جهة البلدان والأماكن: تحديد الموضع المذكور ووصفه',
    books: ['فتوح البلدان', 'معجم البلدان', 'الاعتبار'] },
  { id: 'fatawa', label: 'فتاوى', icon: '🧾', angle: 'من جهة الفتاوى: خلاصة ما أفتى به العلماء في مسألة النص',
    books: ['مجموع الفتاوى', 'فتاوى الرملي', 'الفتاوى الهندية', 'مجموع فتاوى ابن باز', 'مجموع فتاوى ابن عثيمين'] }
];

const selectionResearch = {
  text: '',
  kindId: '',
  running: false
};

function ensureChatSelectPanel() {
  let overlay = document.getElementById('chatSelectOverlay');
  if (overlay) return overlay;
  overlay = document.createElement('div');
  overlay.id = 'chatSelectOverlay';
  overlay.className = 'chat-select-overlay';
  overlay.hidden = true;
  overlay.innerHTML = `
    <div id="chatSelectPanel" class="chat-select-panel" role="dialog" aria-modal="true">
      <div class="chat-select-top">
        <h3 class="chat-select-head" id="chatSelectTitle">تعليق وشرح مختصر</h3>
        <button type="button" class="chat-select-close" id="chatSelectClose" aria-label="إغلاق">×</button>
      </div>
      <div class="chat-select-body">
        <div class="chat-select-quote" id="chatSelectQuote"></div>
        <div class="chat-select-kinds" id="chatSelectKinds"></div>
        <div class="chat-select-note">انقر فنًّا فيبحث في كتبه المعتمدة وحدها — ١٠ شواهد وشرح مختصر</div>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.querySelector('#chatSelectKinds').innerHTML = SELECTION_RESEARCH_KINDS.map(kind =>
    `<button type="button" data-kind="${kind.id}"><span class="chat-select-kind-icon">${kind.icon}</span>${kind.label}</button>`
  ).join('');
  overlay.addEventListener('click', onChatSelectPanelClick);
  return overlay;
}

function openChatSelectionPanel() {
  if (chatGraphBusy) return;
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || !selection.rangeCount) return;
  const text = selection.toString().replace(/\s+/g, ' ').trim();
  if (text.length < 2) return;
  const node = selection.anchorNode;
  const host = node && node.parentElement && node.parentElement.closest('#chatMessagesContainer .message-bubble.assistant .message-content');
  if (!host) return;
  const overlay = ensureChatSelectPanel();
  if (!overlay.hidden) return;
  selectionResearch.text = text.slice(0, 2500);
  selectionResearch.kindId = '';
  overlay.querySelector('#chatSelectQuote').textContent = selectionResearch.text;
  overlay.hidden = false;
  selection.removeAllRanges();
}

function onChatSelectPanelClick(event) {
  const kindButton = event.target.closest('[data-kind]');
  if (kindButton) {
    selectionResearch.kindId = kindButton.getAttribute('data-kind');
    runSelectionResearch();
    return;
  }
  if (event.target.id === 'chatSelectClose' || event.target.id === 'chatSelectOverlay') {
    document.getElementById('chatSelectOverlay').hidden = true;
  }
}

function selectionResearchInstruction(kind) {
  return `علّق على النص التالي واشرحه شرحًا مختصرًا ${kind.angle}، معتمدًا على الشواهد المرفقة من كتب هذا الفن فقط:\n«${selectionResearch.text}»\nاجعل الجواب مختصرًا مركزًا في فقرات قصيرة بلا إطالة.\nضع رقم إحالة كل نقل بين قوسين في موضعه من المتن هكذا (١) (٢) متسلسلًا بحسب ترتيب الشواهد، ولا تكتب في آخر الجواب قائمة حواشٍ ولا قائمة مصادر ومراجع — الأرقام وحدها.`;
}

async function runSelectionResearch() {
  if (chatGraphBusy || selectionResearch.running) return;
  const session = chatSessions.find(item => item.id === activeSessionId);
  const kind = SELECTION_RESEARCH_KINDS.find(item => item.id === selectionResearch.kindId);
  if (!session || !kind || !selectionResearch.text) return;
  selectionResearch.running = true;

  document.getElementById('chatSelectOverlay').hidden = true;
  window.getSelection()?.removeAllRanges();
  const control = startChatRun();
  const container = document.getElementById('chatMessagesContainer');
  const typingBubble = document.createElement('div');
  typingBubble.className = 'message-bubble assistant';
  typingBubble.id = 'selectionTypingIndicator';
  typingBubble.innerHTML = `
    <div class="message-avatar">مج</div>
    <div class="message-content"><span class="graph-wait-note">جار البحث .. فضلا انتظر</span></div>
  `;
  if (container) {
    container.appendChild(typingBubble);
    if (typeof scrollToBottom === 'function') scrollToBottom();
  }
  const stopAnswerClock = startChatAnswerClock(typingBubble);

  const instruction = selectionResearchInstruction(kind);
  const selectedModel = document.getElementById('chatModelSelect')?.value
    || localStorage.getItem('almojtahed_active_chat_model')
    || 'anthropic/claude-3.7-sonnet';
  const activeProvider = localStorage.getItem(ownerStorageKey('almojtahed_active_provider')) || 'openrouter';
  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) {}
  const hybrid = typeof isChatHybridSearchEnabled === 'boolean' ? isChatHybridSearchEnabled : true;

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: control.signal,
      body: JSON.stringify({
        model: selectedModel,
        provider: activeProvider,
        api_key: savedKeys[activeProvider] || '',
        thinking_level: currentThinkingLevel,
        use_hybrid: hybrid,
        library_only: true,
        library_query: selectionResearch.text.slice(0, 800),
        selected_books: [...kind.books],
        extraction_capacity: 10,
        witness_limit: 10,
        context_tokens: 64000,
        messages: [{ role: 'user', content: instruction }],
        system_prompt: `أنت تعلّق تعليقًا مختصرًا على نص محدد اعتمادًا على شواهد الشاملة المرفقة، بلا وكلاء.\nالسطر الأول عنوان علمي تنشئه أنت لهذا التعليق وحده، بهذا الشكل: ### عنوان التعليق\nلا تستخدم عنوان السؤال الأصلي ولا عنوان المحادثة.\nاشرح شرحًا مختصرًا مركزًا، ولا تنشئ جدولاً، ولا تخترع إحالة ليست في الشواهد.\n${instruction}`,
        temperature: 0.2,
        providers: savedKeys,
        agent_group: null
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'تعذر البحث');
    let reply = String(data.reply || '').trim();
    if (!/^#{1,3}\s+/m.test(reply)) reply = `### ${kind.label}\n\n${reply}`;
    const durationMs = stopAnswerClock();
    session.messages.push({
      role: 'assistant',
      content: reply || 'لم تُستخرج نتيجة.',
      model: data.model || selectedModel,
      provider: data.provider || activeProvider,
      selection_research: kind.id,
      duration_ms: durationMs,
      thinking_effort: data.thinking_effort || '',
      thinking_label: (typeof thinkingEffortLabel === 'function') ? thinkingEffortLabel(data.thinking_effort) : '',
      witnesses: Array.isArray(data.witnesses) ? data.witnesses : []
    });
    saveChatSessions();
    renderSessionMessages(activeSessionId);
  } catch (err) {
    stopAnswerClock();
    if (chatStopped(err)) {
      if (typeof showToast === 'function') showToast('تم الإيقاف');
    } else if (typeof showToast === 'function') showToast(err.message || 'تعذر البحث');
  } finally {
    const note = document.getElementById('selectionTypingIndicator');
    if (note) note.remove();
    selectionResearch.running = false;
    endChatRun();
  }
}

document.addEventListener('mouseup', () => {
  const overlay = document.getElementById('chatSelectOverlay');
  if (overlay && !overlay.hidden) return;
  setTimeout(openChatSelectionPanel, 0);
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  const deleteOverlay = document.getElementById('chatDeleteOverlay');
  if (deleteOverlay && !deleteOverlay.hidden) {
    deleteOverlay.hidden = true;
    return;
  }
  const overlay = document.getElementById('chatSelectOverlay');
  const books = document.getElementById('searchScopeModal');
  if (books && books.classList.contains('open')) return;
  if (overlay) overlay.hidden = true;
});

// تهيئة نمط الشات عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    updateChatDispatchModeUI();
    if (typeof updateChatRawMcpUI === 'function') updateChatRawMcpUI();
    updateChatHybridToggleUI();
    renderChatAssistantTools();
  }, 100);
});

window.toggleChatHybridSearchMode = toggleChatHybridSearchMode;
window.updateChatHybridToggleUI = updateChatHybridToggleUI;
window.initChatHybridToggleState = initChatHybridToggleState;
window.createNewChatSession = createNewChatSession;
window.openOrReuseChatSession = openOrReuseChatSession;
window.startNewChatWithPrompt = startNewChatWithPrompt;
window.renderChatAssistantTools = renderChatAssistantTools;
window.useToolInChatPrompt = useToolInChatPrompt;
window.buildToolPromptTemplate = buildToolPromptTemplate;
