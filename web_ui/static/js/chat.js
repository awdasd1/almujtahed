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
      showToast('الشات الذكي: تم تفعيل استرجاع النصوص بالبحث الهجين (Dense + BM25) ⚡');
    } else {
      showToast('الشات الذكي: تم تفعيل استرجاع النصوص بالبحث الدلالي الصرف (Dense Only) 🧠');
    }
  }
}

function updateChatHybridToggleUI() {
  const btn = document.getElementById('btnToggleChatHybridSearch');
  const label = document.getElementById('labelChatHybridToggle');
  const icon = document.getElementById('iconChatHybridToggle');
  if (!btn || !label) return;

  if (isChatHybridSearchEnabled) {
    btn.classList.add('is-active');
    btn.classList.remove('is-disabled');
    btn.setAttribute('aria-pressed', 'true');
    btn.title = 'البحث الهجين في الشات مفعّل: استرجاع الشواهد التراثية بالدمج بين التضمين الدلالي والتطابق اللفظي BM25. انقر للتعطيل.';
    label.textContent = 'بحث هجين مفعّل (Dense + BM25)';
    if (icon) icon.setAttribute('data-lucide', 'layers');
  } else {
    btn.classList.remove('is-active');
    btn.classList.add('is-disabled');
    btn.setAttribute('aria-pressed', 'false');
    btn.title = 'البحث الدلالي الصرف في الشات مفعّل: استرجاع الشواهد التراثية بنموذج المتجهات 8B فقط. انقر لتفعيل البحث الهجين.';
    label.textContent = 'بحث دلالي صرف (Dense Only)';
    if (icon) icon.setAttribute('data-lucide', 'cpu');
  }

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initChatHistory();
  initChatHybridToggleState();
  populateChatAgentGroupsDropdown();
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

// تهيئة سجل المحادثات من التخزين المحلي
function initChatHistory() {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (raw) {
      chatSessions = JSON.parse(raw);
      // تنظيف أي بقايا من الجلسات الوهمية التجريبية القديمة
      chatSessions = chatSessions.filter(s => {
        return !s.messages.some(m => m.content && m.content.includes("أجوبة التسولي عن مسائل الأمير عبد القادر") && !m.content.includes("ذخيرة العقبى"));
      });
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chatSessions));
    }
  } catch (e) {
    console.error('Error loading chat history:', e);
  }

  if (chatSessions.length === 0) {
    createNewChatSession(false);
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
    messages: [
      {
        role: 'assistant',
        content: `مرحباً بك في منظومة **المجتهد** الذكية.\n\nأنا متصل مباشرة بمخزن الشاملة التراثي الضخم (أكثر من 8 ملايين مقطع) ومزود بوكلاء مساعدين في الفقه، والتفسير، والحديث، والتاريخ. كيف يمكنني إعانتك في بحثك أو استنباطك اليوم؟`
      }
    ]
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

  const names = { low: 'منخفض (سريع)', medium: 'متوسط (متزن)', high: 'عالي (استدلال عميق)' };
  showToast(`تم ضبط التفكير على: ${names[level] || level}`);
}

// عرض قائمة المحادثات في الشريط الجانبي
function renderChatHistorySidebar() {
  const container = document.getElementById('chatHistoryList');
  if (!container) return;

  container.innerHTML = chatSessions.map(sess => {
    const isActive = sess.id === activeSessionId;
    return `
      <div class="history-item ${isActive ? 'active' : ''}" onclick="selectChatSession('${sess.id}')" title="${escapeHtml(sess.title)}">
        <span style="overflow: hidden; text-overflow: ellipsis;">${escapeHtml(sess.title)}</span>
        <button onclick="deleteChatSession(event, '${sess.id}')" style="background: transparent; border: none; color: var(--text-light); cursor: pointer; padding: 2px 4px;" title="حذف">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </div>
    `;
  }).join('');
}

// اختيار جلسة من الشريط الجانبي
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

// حفظ المحادثات في LocalStorage
function saveChatSessions() {
  try {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chatSessions));
  } catch (e) {
    console.error('Failed to save chats to storage:', e);
  }
}

// عرض رسائل الجلسة الحالية
function renderSessionMessages(sessionId) {
  const session = chatSessions.find(s => s.id === sessionId);
  const container = document.getElementById('chatMessagesContainer');
  if (!session || !container) return;

  container.innerHTML = session.messages.map((msg, idx) => {
    const isUser = msg.role === 'user';
    const avatar = isUser ? 'أنت' : 'مج';
    const parsedText = formatMarkdown(msg.content);
    
    const modelTag = (!isUser && msg.model) ? `
      <div class="message-model-tag" title="النموذج الذي قام بالتحليل والإجابة">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
        <span>النموذج: ${escapeHtml(cleanModelDisplayName(msg.model))}</span>
      </div>
    ` : '';

    const agentGroupTag = (!isUser && msg.agent_group) ? `
      <div class="message-agent-group-tag" title="تم توجيه الاستفسار واستخراج البيانات عبر هذه المجموعة">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        <span>المجموعة: ${escapeHtml(msg.agent_group)}</span>
      </div>
    ` : '';

    const tagsHtml = (modelTag || agentGroupTag) ? `
      <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px;">
        ${modelTag}
        ${agentGroupTag}
      </div>
    ` : '';

    const actionsBar = !isUser ? `
      <div class="chat-msg-actions-bar" style="display: flex; gap: 8px; margin-top: 10px; border-top: 1px dashed var(--border-subtle); padding-top: 8px; flex-wrap: wrap;">
        <button type="button" class="btn-msg-export" onclick="exportChatMessageHtml(${idx})" title="تصدير هذه النتيجة كملف HTML تفاعلي متكامل">
          🌐 تصدير HTML
        </button>
        <button type="button" class="btn-msg-export" onclick="exportChatMessagePdf(${idx})" title="تصدير هذه النتيجة كملف PDF أكاديمي منسق">
          📄 تصدير PDF
        </button>
        <button type="button" class="btn-msg-export" onclick="copyChatMessageText(${idx})" title="نسخ نص الإجابة كاملاً">
          📋 نسخ
        </button>
      </div>
    ` : '';

    return `
      <div class="message-bubble ${isUser ? 'user' : 'assistant'}">
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
          ${parsedText}
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

  scrollToBottom();
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
      name: 'النتيجة والدراسة التحريرية المعتمدة',
      output: msg.content,
      executedAt: new Date().toLocaleString('ar-SA')
    }]
  };

  const htmlContent = (typeof window.buildStandaloneProjectHtml === 'function')
    ? window.buildStandaloneProjectHtml(runData)
    : msg.content;

  const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.setAttribute('href', url);
  a.setAttribute('download', `research_result_${Date.now()}.html`);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('🎉 تم تصدير النتيجة البحثية كـ HTML تفاعلي بنجاح!');
}

async function exportChatMessagePdf(idx) {
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
      name: 'النتيجة والدراسة التحريرية المعتمدة',
      output: msg.content,
      executedAt: new Date().toLocaleString('ar-SA')
    }]
  };

  const htmlContent = (typeof window.buildStandaloneProjectHtml === 'function')
    ? window.buildStandaloneProjectHtml(runData)
    : msg.content;

  showToast('جارٍ إعداد وتوليد ملف PDF الأكاديمي عالي الدقة... ⏳');
  try {
    const res = await fetch('/api/projects/export-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html: htmlContent, title: title })
    });
    if (!res.ok) throw new Error('فشل التوليد');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('href', url);
    a.setAttribute('download', `research_result_${Date.now()}.pdf`);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('🎉 تم تحميل ملف PDF الأكاديمي بنجاح!');
  } catch (err) {
    console.warn('PDF export server fallback to print:', err);
    const printWin = window.open('', '_blank');
    if (printWin) {
      printWin.document.open();
      printWin.document.write(htmlContent);
      printWin.document.close();
      setTimeout(() => { printWin.focus(); printWin.print(); }, 500);
    }
  }
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
function handleChatInputKey(e) {
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
      const data = await resp.json();

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
        item.error = data.error || 'فشل الرفع';
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

  if (currentAttachments.some(a => a.uploading)) {
    if (typeof showToast === 'function') {
      showToast('يرجى الانتظار ثوانٍ حتى يكتمل حفظ الملف في المجلد واستخراج محتواه...', 2500);
    }
    return;
  }

  // تصفية المرفقات الصالحة الجاهزة
  const validAttachments = currentAttachments.filter(a => !a.error && !a.uploading);

  if (!text && validAttachments.length === 0) return;

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
  // حفظ نسخة من المرفقات لتمريرها في الطلب البرمجي ثم تفريغ الواجهة
  const outgoingAttachments = validAttachments.slice();
  currentAttachments = [];
  renderAttachmentsPreview();
  renderSessionMessages(activeSessionId);

  const selectedModel = document.getElementById('chatModelSelect')?.value || 
                        localStorage.getItem('almojtahed_active_chat_model') || 
                        'anthropic/claude-3.7-sonnet';

  const activeProvider = localStorage.getItem('almojtahed_active_provider') || 'openrouter';
  let savedKeys = {};
  try {
    savedKeys = JSON.parse(localStorage.getItem('almojtahed_provider_keys') || '{}');
  } catch (e) {}
  const apiKey = savedKeys[activeProvider] || '';

  const modelDisplayName = document.getElementById('chatModelSelect')?.selectedOptions[0]?.text || cleanModelDisplayName(selectedModel);

  // فحص ما إذا كان المستخدم قد فعّل إسناد الطلب لمجموعة الوكلاء المساعدين
  const useAgentGroup = document.getElementById('chatUseAgentGroupCheckbox')?.checked;
  const selectedGroupId = document.getElementById('chatAgentGroupSelect')?.value;
  let assignedGroupPayload = null;
  let activeAgent = null;

  if (useAgentGroup && selectedGroupId) {
    let groups = [];
    try {
      const raw = localStorage.getItem('almojtahed_agent_groups');
      if (raw) groups = JSON.parse(raw);
    } catch (e) {}
    if (!groups.length && window.agentGroups) groups = window.agentGroups;

    const grp = groups.find(g => g.id === selectedGroupId);
    if (grp && grp.agents && grp.agents.length > 0) {
      // فحص الوكلاء المحددين بالمربعات (محددة 1 أو 2 أو 3 أو الجميع)
      let selectedSubAgentIds = [];
      try {
        const rawSel = localStorage.getItem('almojtahed_chat_selected_agents_' + selectedGroupId)
                    || localStorage.getItem('almojtahed_selected_chat_subagents');
        if (rawSel) selectedSubAgentIds = JSON.parse(rawSel);
      } catch (e) {}

      let candidateAgents = grp.agents;
      if (Array.isArray(selectedSubAgentIds) && selectedSubAgentIds.length > 0) {
        const filtered = grp.agents.filter(a => selectedSubAgentIds.includes(a.id));
        if (filtered.length > 0) candidateAgents = filtered;
      }

      // إذا اختار المستخدم وكيلاً واحداً صراحة أو فريقاً محدداً
      const isMultiAgents = candidateAgents.length > 1;
      const agentsNames = candidateAgents.map(a => a.name).join(' + ');
      let activeAgent = candidateAgents[0];

      // تجميع نطاق كتب الوكلاء المختارين (دمج نطاق جميع الوكلاء المحددين دون تكرار)
      const booksSet = new Set();
      candidateAgents.forEach(a => {
        const bList = (a.booksScope && Array.isArray(a.booksScope)) ? a.booksScope : (a.scopeBooks || a.books || []);
        bList.forEach(b => {
          if (b && String(b).trim()) booksSet.add(String(b).trim());
        });
      });
      const agentBooks = Array.from(booksSet);

      const poolVal = parseInt(activeAgent.poolSize) || 250;
      const topVal = parseInt(activeAgent.topK || activeAgent.top_k || activeAgent.topRerank) || 40;

      // تجميع اختصاصات وتوجيهات الوكلاء المحددين
      let unifiedSystemPrompt = activeAgent.systemPrompt || '';
      if (isMultiAgents) {
        unifiedSystemPrompt = candidateAgents.map(a => `### اختصاص وتوجيه الوكيل المساعد «${a.name}»:\n${a.systemPrompt || a.desc || ''}`).join('\n\n');
      }

      assignedGroupPayload = {
        id: grp.id,
        name: grp.name,
        desc: grp.desc || '',
        active_agent: {
          id: activeAgent.id,
          name: isMultiAgents ? `فريق الوكلاء المختارين (${candidateAgents.length}): ${agentsNames}` : activeAgent.name,
          desc: isMultiAgents ? candidateAgents.map(a => `[${a.name}]: ${a.desc || ''}`).join(' | ') : (activeAgent.desc || ''),
          model: activeAgent.model || 'google/gemini-2.5-flash',
          thinking: activeAgent.thinking || 'medium',
          system_prompt: unifiedSystemPrompt,
          books: agentBooks,
          pool_size: poolVal,
          top_k: topVal,
          temp: activeAgent.temp !== undefined ? activeAgent.temp : 0.2
        },
        agents: candidateAgents.map(a => {
          let booksList = (a.booksScope && Array.isArray(a.booksScope)) ? a.booksScope : (a.scopeBooks || a.books || []);
          return {
            id: a.id,
            name: a.name,
            desc: a.desc || '',
            system_prompt: a.systemPrompt || '',
            model: a.model || 'google/gemini-2.5-flash',
            thinking: a.thinking || 'medium',
            books: booksList,
            pool_size: parseInt(a.poolSize) || 250,
            top_k: parseInt(a.topK || a.top_k || a.topRerank) || 40,
            temp: a.temp !== undefined ? a.temp : 0.2,
            scope_summary: booksList.length > 0 ? `${booksList.length} كتاب محدد` : 'شامل المخزن التراثي'
          };
        })
      };
    }
  }

  // اعتماد النموذج المختار صراحة من قبل المستخدم في ترويسة الشات الذكي
  let executionModel = selectedModel;
  let executionThinking = currentThinkingLevel;
  let executionPrompt = currentSettings.modelParams?.systemPrompt;
  let executionTemp = currentSettings.modelParams?.temperature;
  let executionTopK = currentSettings.modelParams?.topK;

  if (activeAgent) {
    // إسناد الوكيل يوفر توجيه استخراج الشاملة وتخصيص التفكير دون مصادرة النموذج المختار
    if (activeAgent.thinking && !executionThinking) executionThinking = activeAgent.thinking;
    if (activeAgent.systemPrompt) executionPrompt = activeAgent.systemPrompt;
    if (activeAgent.temp !== undefined && executionTemp === undefined) executionTemp = activeAgent.temp;
    if (activeAgent.topK !== undefined && executionTopK === undefined) executionTopK = activeAgent.topK;
  }

  // إظهار فقاعة مؤشر الكتابة للنموذج
  const container = document.getElementById('chatMessagesContainer');
  const typingBubble = document.createElement('div');
  typingBubble.className = 'message-bubble assistant';
  typingBubble.id = 'typingBubbleIndicator';

  const hybridModeName = isChatHybridSearchEnabled ? 'بحث هجين' : 'دلالي صرف';
  let typingMessage = `جارٍ الاستدلال واستدعاء نصوص الشاملة عبر «<strong>${escapeHtml(modelDisplayName)}</strong>» (${executionThinking === 'high' ? 'استدلال عميق' : 'تفكير سريع'} · ${hybridModeName})...`;
  if (assignedGroupPayload && activeAgent) {
    typingMessage = `جارٍ تشغيل وكيل «<strong>${escapeHtml(activeAgent.name)}</strong>» عبر نموذج «<strong>${escapeHtml(cleanModelDisplayName(executionModel))}</strong>» والبحث في نطاق كتبه المحدد (${hybridModeName})...`;
  } else if (assignedGroupPayload) {
    typingMessage = `جارٍ إرسال وتوجيه الطلب حصراً إلى وكلاء «<strong>${escapeHtml(assignedGroupPayload.name)}</strong>» لاستخراج البيانات التراثية ومعالجتها (${hybridModeName})...`;
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

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: executionModel,
        provider: activeProvider,
        api_key: apiKey,
        thinking_level: executionThinking,
        use_hybrid: isChatHybridSearchEnabled,
        messages: session.messages,
        system_prompt: executionPrompt,
        temperature: executionTemp,
        top_k: executionTopK,
        max_tokens: currentSettings.modelParams?.maxTokens,
        providers: currentSettings.providers,
        agent_group: assignedGroupPayload,
        agent_dispatch_mode: window.chatAgentDispatchMode || 'parallel',
        attachments: outgoingAttachments.map(a => ({
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
    typingBubble.remove();

    session.messages.push({
      role: 'assistant',
      content: data.reply || 'عذراً، لم أتلقَّ استجابة واضحة من الخادم.',
      model: data.model || selectedModel,
      provider: data.provider || activeProvider,
      agent_group: data.agent_group || (assignedGroupPayload ? assignedGroupPayload.name : null)
    });

    saveChatSessions();
    renderSessionMessages(activeSessionId);

  } catch (err) {
    typingBubble.remove();
    session.messages.push({
      role: 'assistant',
      content: `⚠️ تعذر استكمال المحادثة: ${err.message}`
    });
    saveChatSessions();
    renderSessionMessages(activeSessionId);
  }
}

// =============================================================================
// إدارة ربط الشات بمجموعات الوكلاء المساعدين
// =============================================================================

// تعبئة القائمة المنسدلة لمجموعات الوكلاء في الشات
function populateChatAgentGroupsDropdown() {
  const select = document.getElementById('chatAgentGroupSelect');
  const checkbox = document.getElementById('chatUseAgentGroupCheckbox');
  const container = document.getElementById('chatAgentGroupPicker');
  if (!select) return;

  let groups = [];
  try {
    const raw = localStorage.getItem('almojtahed_agent_groups');
    if (raw) groups = JSON.parse(raw);
  } catch (e) {}

  if ((!groups || !groups.length) && window.agentGroups && window.agentGroups.length) {
    groups = window.agentGroups;
  }

  // إذا لم تكن هناك مجموعات بعد، ننشئ المجموعة الأساسية الافتراضية التراثية المليئة بالوكلاء
  if (!groups || !groups.length) {
    groups = [
      {
        id: 'group_heritage_default',
        name: 'مجموعة العلوم التراثية الأساسية',
        desc: 'وكلاء الفقه وأصوله، والحديث ورجاله، والتفسير والتاريخ لتحضير مسائل المخزن والربط مع الشاملة',
        agents: [
          { id: 'agent_fiqh', name: 'وكيل الفقه وأصوله', desc: 'تحرير الفروع الفقهية على المذاهب الأربعة وتخريج المسائل', model: 'google/gemini-2.5-flash', thinking: 'high' },
          { id: 'agent_hadith', name: 'وكيل الحديث والرجال', desc: 'تخريج الأحاديث وبيان علل الرواة وتوثيق الأسانيد', model: 'anthropic/claude-3.7-sonnet', thinking: 'medium' },
          { id: 'agent_tafsir', name: 'وكيل التفسير وعلوم القرآن', desc: 'أقوال المفسرين بالمأثور والدراية وأسباب النزول', model: 'google/gemini-2.5-flash', thinking: 'medium' }
        ]
      }
    ];
    try {
      localStorage.setItem('almojtahed_agent_groups', JSON.stringify(groups));
    } catch (e) {}
  }

  const savedGroupId = localStorage.getItem('almojtahed_chat_selected_group_id') || (groups[0] ? groups[0].id : '');
  const savedEnabled = localStorage.getItem('almojtahed_chat_use_agent_group');
  const isEnabled = savedEnabled === null ? true : (savedEnabled === 'true');

  select.innerHTML = groups.map(g => {
    const agentCount = g.agents ? g.agents.length : 0;
    const isSelected = g.id === savedGroupId;
    return `<option value="${escapeHtml(g.id)}" ${isSelected ? 'selected' : ''}>${escapeHtml(g.name)} (${agentCount} وكلاء)</option>`;
  }).join('');

  if (checkbox) {
    checkbox.checked = isEnabled;
  }

  // القائمة المنسدلة تظل مفعلة دائماً ليتمكن المستخدم من النقر عليها واستعراض المجموعات بحرية
  select.disabled = false;
  select.removeAttribute('disabled');

  if (container) {
    container.classList.toggle('active', isEnabled);
  }

  // تعبئة القائمة الفرعية لوكلاء المجموعة المحددة
  populateSubAgentsDropdown(savedGroupId);
}

// تعبئة وإدارة القائمة المنسدلة للوكلاء مع دعم التشيك ليست وتحديد أكثر من وكيل
function populateSubAgentsDropdown(groupId) {
  const subWrap = document.getElementById('chatSubAgentSelectWrap');
  const btnLabel = document.getElementById('chatSubAgentBtnLabel');
  const itemsContainer = document.getElementById('chatSubAgentChecklistItems');
  const subSelect = document.getElementById('chatSubAgentSelect');
  if (!subWrap) return;

  let groups = [];
  try {
    const raw = localStorage.getItem('almojtahed_agent_groups');
    if (raw) groups = JSON.parse(raw);
  } catch (e) {}
  if (!groups.length && window.agentGroups) groups = window.agentGroups;

  const currentGroup = groups.find(g => g.id === groupId);
  if (!currentGroup || !currentGroup.agents || currentGroup.agents.length === 0) {
    subWrap.style.display = 'none';
    if (subSelect) subSelect.innerHTML = '<option value="">لا يوجد وكلاء</option>';
    return;
  }

  subWrap.style.display = 'inline-flex';

  // قراءة الوكلاء المحددين سابقاً لهذه المجموعة من التخزين المحلي
  let selectedIds = [];
  try {
    const rawSel = localStorage.getItem('almojtahed_chat_selected_agents_' + groupId);
    if (rawSel) selectedIds = JSON.parse(rawSel);
  } catch (e) {}

  // إذا لم يسبق تخصيص، أو كانت القائمة فارغة، نجعل الافتراضي هو تحديد جميع وكلاء المجموعة
  if (!Array.isArray(selectedIds) || selectedIds.length === 0) {
    selectedIds = currentGroup.agents.map(a => a.id);
  }

  // بناء عناصر التشيك ليست داخل القائمة المنسدلة
  let itemsHtml = '';
  currentGroup.agents.forEach(a => {
    const isChecked = selectedIds.includes(a.id);
    const scopeCount = (a.booksScope && a.booksScope.length) ? a.booksScope.length : ((a.books && a.books.length) ? a.books.length : 0);
    const scopeText = scopeCount > 0 ? `${scopeCount} كتب` : 'شامل التراث';

    itemsHtml += `
      <div class="chat-checklist-item ${isChecked ? 'is-selected' : ''}" onclick="handleSubAgentCheckItemClick(event, '${escapeHtml(a.id)}')">
        <input type="checkbox" class="chat-agent-item-checkbox" data-agent-id="${escapeHtml(a.id)}" ${isChecked ? 'checked' : ''} onclick="event.stopPropagation()" onchange="toggleSingleSubAgent('${escapeHtml(a.id)}', this.checked)">
        <div class="chat-agent-item-info">
          <div class="chat-agent-item-name">
            <span>${escapeHtml(a.name)}</span>
            <span class="chat-agent-scope-badge">${escapeHtml(scopeText)}</span>
          </div>
          <div class="chat-agent-item-desc" title="${escapeHtml(a.desc || '')}">${escapeHtml(a.desc || 'وكيل مساعد متخصص')}</div>
        </div>
      </div>
    `;
  });

  if (itemsContainer) itemsContainer.innerHTML = itemsHtml;

  // تحديث الزر والشارات والـ Select الخفي
  updateSubAgentsSelectionUI(currentGroup, selectedIds);
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
function handleSubAgentCheckItemClick(event, agentId) {
  const itemsContainer = document.getElementById('chatSubAgentChecklistItems');
  if (!itemsContainer) return;
  const cb = itemsContainer.querySelector(`input[data-agent-id="${agentId}"]`);
  if (!cb) return;

  const newChecked = !cb.checked;
  cb.checked = newChecked;
  toggleSingleSubAgent(agentId, newChecked);
}

// تبديل اختيار وكيل واحد
function toggleSingleSubAgent(agentId, isChecked) {
  const groupId = document.getElementById('chatAgentGroupSelect')?.value;
  if (!groupId) return;

  let groups = [];
  try {
    const raw = localStorage.getItem('almojtahed_agent_groups');
    if (raw) groups = JSON.parse(raw);
  } catch (e) {}
  if (!groups.length && window.agentGroups) groups = window.agentGroups;
  const currentGroup = groups.find(g => g.id === groupId);
  if (!currentGroup) return;

  let selectedIds = [];
  try {
    const rawSel = localStorage.getItem('almojtahed_chat_selected_agents_' + groupId);
    if (rawSel) selectedIds = JSON.parse(rawSel);
  } catch (e) {}
  if (!Array.isArray(selectedIds)) selectedIds = [];

  if (isChecked) {
    if (!selectedIds.includes(agentId)) selectedIds.push(agentId);
  } else {
    selectedIds = selectedIds.filter(id => id !== agentId);
  }

  // تحديث تمييز الصف بصرياً
  const itemsContainer = document.getElementById('chatSubAgentChecklistItems');
  if (itemsContainer) {
    const cb = itemsContainer.querySelector(`input[data-agent-id="${agentId}"]`);
    if (cb) {
      cb.checked = isChecked;
      const row = cb.closest('.chat-checklist-item');
      if (row) row.classList.toggle('is-selected', isChecked);
    }
  }

  updateSubAgentsSelectionUI(currentGroup, selectedIds);
}

// تحديد أو إلغاء تحديد الكل
function selectAllChatSubAgents(selectAll) {
  const groupId = document.getElementById('chatAgentGroupSelect')?.value;
  if (!groupId) return;

  let groups = [];
  try {
    const raw = localStorage.getItem('almojtahed_agent_groups');
    if (raw) groups = JSON.parse(raw);
  } catch (e) {}
  if (!groups.length && window.agentGroups) groups = window.agentGroups;
  const currentGroup = groups.find(g => g.id === groupId);
  if (!currentGroup) return;

  const selectedIds = selectAll ? currentGroup.agents.map(a => a.id) : [];

  const itemsContainer = document.getElementById('chatSubAgentChecklistItems');
  if (itemsContainer) {
    itemsContainer.querySelectorAll('.chat-agent-item-checkbox').forEach(cb => {
      cb.checked = selectAll;
      const row = cb.closest('.chat-checklist-item');
      if (row) row.classList.toggle('is-selected', selectAll);
    });
  }

  updateSubAgentsSelectionUI(currentGroup, selectedIds);
}

// فتح وإغلاق القائمة المنسدلة للوكلاء
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
    menu.style.display = 'none';
    if (btn) btn.classList.remove('is-open');
  } else {
    menu.style.display = 'flex';
    if (btn) btn.classList.add('is-open');
  }
}

function closeSubAgentsDropdown() {
  const menu = document.getElementById('chatSubAgentChecklistMenu');
  const btn = document.getElementById('chatSubAgentDropdownBtn');
  if (menu) menu.style.display = 'none';
  if (btn) btn.classList.remove('is-open');
}

// إغلاق القائمة عند النقر في أي مكان خارجها
document.addEventListener('click', (e) => {
  const wrap = document.getElementById('chatSubAgentSelectWrap');
  const menu = document.getElementById('chatSubAgentChecklistMenu');
  if (menu && menu.style.display !== 'none') {
    if (!wrap || !wrap.contains(e.target)) {
      closeSubAgentsDropdown();
    }
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
  }

  localStorage.setItem('almojtahed_chat_use_agent_group', isChecked ? 'true' : 'false');

  if (isChecked) {
    if (!select.value && select.options.length > 0) {
      select.selectedIndex = 0;
    }
    localStorage.setItem('almojtahed_chat_selected_group_id', select.value);
    populateSubAgentsDropdown(select.value);
    const selectedText = select.options[select.selectedIndex]?.text || '';
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
  if (!select) return;

  select.disabled = false;
  select.removeAttribute('disabled');
  localStorage.setItem('almojtahed_chat_selected_group_id', select.value);

  // تحديث قائمة الوكلاء التابعة للمجموعة المختارة فوراً
  populateSubAgentsDropdown(select.value);

  // بمجرد اختيار مجموعة من القائمة، نقوم بتفعيل مربع الاختيار تلقائياً وتنشيط ربط البحث بها
  if (checkbox) {
    checkbox.checked = true;
    if (container) container.classList.add('active');
    localStorage.setItem('almojtahed_chat_use_agent_group', 'true');
  }

  const selectedText = select.options[select.selectedIndex]?.text || '';
  if (typeof showToast === 'function') {
    showToast(`تم ربط وتوجيه البحث عبر: ${selectedText}`, 3000);
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

function scrollToBottom() {
  const container = document.getElementById('chatMessagesContainer');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

// تحويل نصوص الماركداون القياسية إلى HTML مع دعم كامل للجداول والاقتباسات النبوية والقرآنية
function formatMarkdown(text) {
  if (!text) return '';

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
    res = res.replace(/^### (.*$)/gim, '<h4 style="font-family: var(--font-amiri); font-size: 19px; margin: 12px 0 6px; color: var(--text-main);">$1</h4>');
    res = res.replace(/^## (.*$)/gim, '<h3 style="font-family: var(--font-amiri); font-size: 21px; margin: 14px 0 8px; color: var(--accent-clay);">$1</h3>');
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
    URL.revokeObjectURL(url);

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
window.exportChatMessageHtml = exportChatMessageHtml;
window.exportChatMessagePdf = exportChatMessagePdf;
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
إذا نقلت نصًا حرفيًا: اذكر (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: اجعل رقم الإحالة في المتن بين قوسين، أصغر من الخط الأساسي بمقاسين ومرتفعة (superscript) هكذا: <sup><small>(١)</small></sup>. ويشمل ذلك: الآيات، تخريج الأحاديث، ونسبة الأقوال.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (القول الأول: / الدليل الأول:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
## [3] سرد المصادر والمراجع ##
اجعل في نهاية البحث قائمة بالمصادر والمراجع على الطريقة الأكاديمية، مرتبة هجائيًا، بذكر: اسم المصدر، مؤلفه، محققه، رقم الطبعة، الناشر، مدينة النشر، سنة الطبع.`,

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
إذا نقلت نصًا حرفيًا: اذكر (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: اجعل رقم الإحالة في المتن بين قوسين، أصغر من الخط الأساسي بمقاسين ومرتفعة (superscript) هكذا: <sup><small>(١)</small></sup>. ويشمل ذلك: الآيات، تخريج الأحاديث، ونسبة الأقوال.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (الوجه الأول: / القول الثاني:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
## [3] سرد المصادر والمراجع ##
اجعل في نهاية البحث قائمة بالمصادر والمراجع على الطريقة الأكاديمية، مرتبة هجائيًا، بذكر: اسم المصدر، مؤلفه، محققه، رقم الطبعة، الناشر، مدينة النشر، سنة الطبع.`,

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
إذا نقلت نصًا حرفيًا: اذكر (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: اجعل رقم الإحالة في المتن بين قوسين، أصغر من الخط الأساسي بمقاسين ومرتفعة (superscript) هكذا: <sup><small>(١)</small></sup>. ويشمل ذلك: الآيات، تخريج الأحاديث، ونسبة الأقوال.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (الطريق الأول: / علة الحديث:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
## [3] سرد المصادر والمراجع ##
اجعل في نهاية البحث قائمة بالمصادر والمراجع على الطريقة الأكاديمية، مرتبة هجائيًا، بذكر: اسم المصدر، مؤلفه، محققه، رقم الطبعة، الناشر، مدينة النشر، سنة الطبع.`,

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

## [5] الحكم النهائي والعلل الخفية ##
بيان العلة القادحة إن وجدت، والحكم الجازم على ثبوت الحديث أو إعلاله، مع توثيق تراجم الرواة وأقوال النقاد في الحاشية.
## [6] منهجية الحاشية ##
اذكر مصادر تراجم الرواة (تهذيب الكمال، سير أعلام النبلاء، التقريب) وكتب العلل في الحاشية بذكر: اسم الكتاب، المؤلف، الجزء، الصفحة.`,

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

## [2] التحليل والتأصيل العلمي في المتن ##
1. تحرير صورة المسألة والتحرير الأصولي الدقيق.
2. تفصيل أدلة كل فريق مع مناقشة الاعتراضات والردود من كتب الفقه المقارن المعتمدة.
3. الترجيح المعتمد على القواعد الفقهية ومقاصد الشريعة.

## [3] منهجية الحاشية والمصادر ##
توثيق كل قول ودليل في الحاشية بذكر: اسم الكتاب، المؤلف، الجزء، الصفحة وفق القواعد الأكاديمية المعتمدة.`,

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
رابعًا: استخدم الإحالة الصحيحة (الكتاب، صاحبه، الجزء، الصفحة).
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

window.P2C_OUTPUT_TEMPLATES = window.P2C_OUTPUT_TEMPLATES || CHAT_OUTPUT_TEMPLATES;

function applyChatOutputTemplate(type) {
  const input = document.getElementById('chatInputText');
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
window._chatIsnads = window._chatIsnads || {};

function autoRenderChatInteractiveWidgets(container) {
  if (!container) return;

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
          <div style="display: flex; gap: 6px; align-items: center;">
            <button type="button" class="btn-msg-export" style="font-size:11px; padding:3px 8px;" onclick="zoomChatMarkmap('${mapId}', 1.25)" title="تكبير الخريطة">🔍+ تكبير</button>
            <button type="button" class="btn-msg-export" style="font-size:11px; padding:3px 8px;" onclick="zoomChatMarkmap('${mapId}', 0.8)" title="تصغير الخريطة">🔍- تصغير</button>
            <button type="button" class="btn-msg-export" style="font-size:11px; padding:3px 8px;" onclick="fitChatMarkmap('${mapId}')" title="ملاءمة الشاشة">⛶ ملاءمة</button>
            <button type="button" class="btn-msg-export" style="font-size:11px; padding:3px 8px;" onclick="toggleChatCodeBlock('${mapId}_code')" title="عرض الكود المصدر">📝 الكود</button>
          </div>
        </div>
        <div style="height: 380px; width: 100%; border: 1px solid var(--border-subtle); border-radius: 6px; background: var(--bg-muted); overflow: hidden; position: relative;">
          <svg id="${mapId}" style="width: 100%; height: 100%; display: block;"></svg>
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
}

function zoomChatMarkmap(mapId, factor) {
  const mm = window._chatMarkmaps && window._chatMarkmaps[mapId];
  if (mm && typeof mm.rescale === 'function') {
    mm.rescale(factor);
  }
}

function fitChatMarkmap(mapId) {
  const mm = window._chatMarkmaps && window._chatMarkmaps[mapId];
  if (mm && typeof mm.fit === 'function') {
    mm.fit();
  }
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

window.applyChatOutputTemplate = applyChatOutputTemplate;
window.autoRenderChatInteractiveWidgets = autoRenderChatInteractiveWidgets;
window.zoomChatMarkmap = zoomChatMarkmap;
window.fitChatMarkmap = fitChatMarkmap;
window.fitChatIsnad = fitChatIsnad;
window.toggleChatCodeBlock = toggleChatCodeBlock;

// نمط توزيع واستدعاء الوكلاء المساعدين في الشات الذكي (متوازي vs مباشر - حفظ خط الرجعة)
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

// تهيئة نمط الشات عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    updateChatDispatchModeUI();
    updateChatHybridToggleUI();
  }, 100);
});

window.toggleChatHybridSearchMode = toggleChatHybridSearchMode;
window.updateChatHybridToggleUI = updateChatHybridToggleUI;
window.initChatHybridToggleState = initChatHybridToggleState;
window.createNewChatSession = createNewChatSession;
window.openOrReuseChatSession = openOrReuseChatSession;
window.startNewChatWithPrompt = startNewChatWithPrompt;
