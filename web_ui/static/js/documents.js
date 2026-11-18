// =============================================================================
// رفع وثيقة كاملة: باكسلاش (\) في حقل المحادثة يُظهر «رفع وثيقة»، فتُرفع
// الوثيقة (كتاب PDF أو صورة) وتُحوَّل نصًا مع شريط تقدم وتُحفظ، ثم
// تُربط بالمحادثة فيستحضر النموذج أقرب مقاطعها إلى كل سؤال
// =============================================================================
let docUploadTimer = null;

function initDocSlash() {
  const input = document.getElementById('chatInputText');
  if (!input || input.dataset.docSlashBound) return;
  input.dataset.docSlashBound = '1';
  input.addEventListener('input', () => {
    const menu = document.getElementById('docSlashMenu');
    if (!menu) return;
    menu.style.display = /\\$/.test(input.value) ? 'block' : 'none';
  });
  input.addEventListener('blur', () => {
    setTimeout(() => {
      const menu = document.getElementById('docSlashMenu');
      if (menu) menu.style.display = 'none';
    }, 250);
  });
}

function docSlashPick() {
  const input = document.getElementById('chatInputText');
  if (input) input.value = input.value.replace(/\\$/, '');
  const menu = document.getElementById('docSlashMenu');
  if (menu) menu.style.display = 'none';
  openDocUpload();
}

function openDocUpload() {
  const modal = document.getElementById('docUploadModal');
  if (modal) modal.style.display = 'flex';
  loadDocumentsList();
}

function closeDocUpload() {
  const modal = document.getElementById('docUploadModal');
  if (modal) modal.style.display = 'none';
  if (docUploadTimer) { clearInterval(docUploadTimer); docUploadTimer = null; }
}

function docFileChosen() {
  const file = document.getElementById('docFileInput')?.files?.[0];
  const nameInput = document.getElementById('docNameInput');
  if (file && nameInput && !nameInput.value.trim()) {
    nameInput.value = file.name.replace(/\.[^.]+$/, '');
  }
}

async function startDocUpload() {
  const file = document.getElementById('docFileInput')?.files?.[0];
  if (!file) { showToast('اختر ملف الوثيقة أولاً (PDF أو صورة)'); return; }
  const name = document.getElementById('docNameInput')?.value.trim() || file.name.replace(/\.[^.]+$/, '');
  const btn = document.getElementById('btnDocStart');
  const wrap = document.getElementById('docProgressWrap');
  const bar = document.getElementById('docProgressBar');
  const label = document.getElementById('docProgressLabel');
  const done = document.getElementById('docDoneArea');
  if (btn) btn.disabled = true;
  if (wrap) wrap.style.display = 'block';
  if (done) done.style.display = 'none';
  if (bar) bar.style.width = '2%';
  if (label) label.textContent = 'يُرفع الملف…';
  try {
    const form = new FormData();
    form.append('file', file);
    form.append('name', name);
    const res = await fetch('/api/documents/upload', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'تعذر الرفع');
    pollDocProgress(data.id, data.name);
  } catch (e) {
    if (label) label.textContent = `تعذر الرفع: ${e.message || e}`;
    if (btn) btn.disabled = false;
  }
}

function pollDocProgress(docId, docName) {
  const bar = document.getElementById('docProgressBar');
  const label = document.getElementById('docProgressLabel');
  const done = document.getElementById('docDoneArea');
  const btn = document.getElementById('btnDocStart');
  if (docUploadTimer) clearInterval(docUploadTimer);
  docUploadTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/documents/${docId}/progress`);
      const p = await res.json();
      if (p.status === 'converting' || p.status === 'queued') {
        const pct = p.pages ? Math.max(3, Math.round((p.page / p.pages) * 100)) : 4;
        if (bar) bar.style.width = `${pct}%`;
        if (label) label.textContent = p.pages ? `تُحوَّل الوثيقة نصًا… صفحة ${p.page} من ${p.pages}` : 'تُجهَّز الوثيقة…';
      } else if (p.status === 'done') {
        clearInterval(docUploadTimer); docUploadTimer = null;
        if (bar) bar.style.width = '100%';
        if (label) label.textContent = `اكتمل التحويل: ${p.pages} صفحة، ${Number(p.chars || 0).toLocaleString('ar-EG')} حرفًا.${p.note ? ' ' + p.note : ''}`;
        if (done) {
          done.style.display = 'flex';
          const discuss = document.getElementById('btnDocDiscuss');
          if (discuss) discuss.onclick = () => discussDocument(docId, docName || p.name);
        }
        if (btn) btn.disabled = false;
        loadDocumentsList();
      } else if (p.status === 'error') {
        clearInterval(docUploadTimer); docUploadTimer = null;
        if (label) label.textContent = `تعذر التحويل: ${p.error || 'خطأ غير معروف'}`;
        if (btn) btn.disabled = false;
      }
    } catch (e) { /* نبضة تقدم فائتة: أكمل الاستطلاع */ }
  }, 900);
}

async function loadDocumentsList() {
  const box = document.getElementById('docList');
  if (!box) return;
  try {
    const res = await fetch('/api/documents');
    const data = await res.json();
    const docs = data.documents || [];
    if (!docs.length) {
      box.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">لا وثائق محفوظة بعد.</div>';
      return;
    }
    box.innerHTML = docs.map(d => `
      <div style="display:flex; align-items:center; gap:8px; padding:7px 9px; border:1px solid var(--border-subtle); border-radius:8px; margin-bottom:6px;">
        <span style="font-size:15px;">📄</span>
        <span style="flex:1; min-width:0;">
          <span style="display:block; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(d.name || '')}</span>
          <span style="font-size:11.5px; color: var(--text-muted);">${d.status === 'done' ? `${d.pages} صفحة • ${Number(d.chars || 0).toLocaleString('ar-EG')} حرفًا` : d.status === 'error' ? 'تعذر تحويلها' : 'جارٍ تحويلها…'}</span>
        </span>
        ${d.status === 'done' ? `<button class="btn-flat-primary reader-mini-btn" onclick="discussDocument('${d.id}')">مناقشة الوثيقة</button>` : ''}
        <button class="btn-flat-secondary reader-mini-btn" onclick="deleteDocument('${d.id}')" title="حذف الوثيقة">حذف</button>
      </div>`).join('');
  } catch (e) {
    box.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">تعذر جلب الوثائق.</div>';
  }
}

async function deleteDocument(docId) {
  try {
    await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
    loadDocumentsList();
    showToast('حُذفت الوثيقة');
  } catch (e) { showToast('تعذر حذف الوثيقة'); }
}

function discussDocument(docId, docName) {
  closeDocUpload();
  if (typeof switchMainTab === 'function') switchMainTab('chat');
  const name = docName || 'وثيقة مرفوعة';
  if (typeof createNewChatSession === 'function') createNewChatSession(true, `مناقشة: ${name}`.slice(0, 40));
  const session = (typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null;
  if (session) {
    session.docId = docId;
    session.docName = name;
    if (typeof saveChatSessions === 'function') saveChatSessions();
  }
  updateDocChip();
  showToast('ارتبطت المحادثة بالوثيقة — اسأل عنها وسيستحضر النموذج مقاطعها 📄');
  const input = document.getElementById('chatInputText');
  if (input) input.focus();
}

function detachDocument() {
  const session = (typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null;
  if (session) {
    delete session.docId;
    delete session.docName;
    if (typeof saveChatSessions === 'function') saveChatSessions();
  }
  updateDocChip();
}

function updateDocChip() {
  const chip = document.getElementById('docChatChip');
  if (!chip) return;
  const session = (typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null;
  if (session && session.docId) {
    chip.style.display = 'flex';
    const label = document.getElementById('docChatChipName');
    if (label) label.textContent = session.docName || 'وثيقة مرفوعة';
  } else {
    chip.style.display = 'none';
  }
}

// سياق الوثيقة المرتبطة بالمحادثة: أقرب مقاطعها إلى سؤال الباحث
async function buildDocContextForSession(session, question) {
  if (!session || !session.docId) return '';
  const res = await fetch(`/api/documents/${session.docId}/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: String(question || '').slice(0, 2000) }),
  });
  const data = await res.json();
  const chunks = data.chunks || [];
  if (!chunks.length) return '';
  return `أنت تناقش الباحث في وثيقة مرفوعة بعنوان «${session.docName || data.name || 'وثيقة'}». فيما يلي أقرب مقاطع نص الوثيقة إلى سؤاله الأخير؛ اعتمد عليها في إجابتك، واذكر أرقام الصفحات كما ترد في [صفحة N]، وإن لم يكن الجواب فيها فقل صراحة إن الوثيقة لا تتضمنه:\n\n${chunks.join('\n\n')}`;
}

// إظهار شارة الوثيقة عند تبديل المحادثات
if (typeof renderSessionMessages === 'function') {
  const _origRenderSessionMessages = renderSessionMessages;
  renderSessionMessages = function (...args) {
    const out = _origRenderSessionMessages.apply(this, args);
    updateDocChip();
    return out;
  };
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDocSlash);
} else {
  initDocSlash();
}
