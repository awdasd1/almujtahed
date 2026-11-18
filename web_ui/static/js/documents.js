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
  // استجابة لضغطة المفتاح نفسها أيضًا: لوحات مفاتيح لا يصل منها الحرف
  // إلى حدث الإدخال بصيغته اللاتينية دائمًا
  input.addEventListener('keydown', (e) => {
    if (e.code !== 'Backslash') return;
    setTimeout(() => {
      const menu = document.getElementById('docSlashMenu');
      if (menu) menu.style.display = 'block';
    }, 30);
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
  window._docAppendId = null;
  const note = document.getElementById('docAppendNote');
  if (note) note.style.display = 'none';
  const btn = document.getElementById('btnDocStart');
  if (btn) btn.textContent = 'رفع وتحويل إلى نص';
  const modal = document.getElementById('docUploadModal');
  if (modal) modal.style.display = 'flex';
  loadDocumentsList();
}

function openDocAppend(docId, docName) {
  window._docAppendId = docId;
  const modal = document.getElementById('docUploadModal');
  if (modal) modal.style.display = 'flex';
  const note = document.getElementById('docAppendNote');
  if (note) {
    note.style.display = 'block';
    note.textContent = `تُضاف الملفات المختارة أجزاءً جديدة إلى وثيقة «${docName || ''}» بعد أجزائها الحالية.`;
  }
  const btn = document.getElementById('btnDocStart');
  if (btn) btn.textContent = 'إضافة الأجزاء وتحويلها';
  loadDocumentsList();
}

function closeDocUpload() {
  const modal = document.getElementById('docUploadModal');
  if (modal) modal.style.display = 'none';
  if (docUploadTimer) { clearInterval(docUploadTimer); docUploadTimer = null; }
}

function docScopeChanged() {
  const mode = document.querySelector('input[name="docScopeMode"]:checked')?.value || 'all';
  const set = (id, on) => { const el = document.getElementById(id); if (el) el.disabled = !on; };
  set('docScopePage', mode === 'page');
  set('docScopeVolume1', mode === 'page');
  set('docScopeFrom', mode === 'range');
  set('docScopeTo', mode === 'range');
  set('docScopeVolume2', mode === 'range');
}

function readDocScope() {
  const mode = document.querySelector('input[name="docScopeMode"]:checked')?.value || 'all';
  const num = id => {
    const v = parseInt(document.getElementById(id)?.value || '', 10);
    return Number.isFinite(v) && v >= 1 ? v : null;
  };
  if (mode === 'page') {
    const p = num('docScopePage');
    return p ? { mode, volume: num('docScopeVolume1'), from: p, to: p } : null;
  }
  if (mode === 'range') {
    const f = num('docScopeFrom'), t = num('docScopeTo');
    return f && t ? { mode, volume: num('docScopeVolume2'), from: f, to: t } : null;
  }
  return null;
}

function docScopeLabel(s) {
  if (!s) return '';
  const v = s.volume ? ` من الجزء ${Number(s.volume).toLocaleString('ar-EG')}` : '';
  const n = x => Number(x).toLocaleString('ar-EG');
  return s.mode === 'page'
    ? ` • حُوّلت صفحة ${n(s.from)}${v} فقط`
    : ` • حُوّلت الصفحات ${n(s.from)}–${n(s.to)}${v}`;
}

function docFileChosen() {
  const file = document.getElementById('docFileInput')?.files?.[0];
  const nameInput = document.getElementById('docNameInput');
  if (file && nameInput && !nameInput.value.trim()) {
    nameInput.value = file.name.replace(/\.[^.]+$/, '');
  }
}

async function startDocUpload() {
  const picked = document.getElementById('docFileInput')?.files;
  const files = picked ? [...picked] : [];
  if (!files.length) { showToast('اختر ملف الوثيقة أو ملفات أجزائها أولاً (PDF أو صورة)'); return; }
  const appendId = window._docAppendId || null;
  const modeSel = document.querySelector('input[name="docScopeMode"]:checked')?.value || 'all';
  if (modeSel !== 'all' && !readDocScope()) { showToast('أدخل أرقام الصفحات للنطاق المختار أولاً'); return; }
  const name = document.getElementById('docNameInput')?.value.trim() || files[0].name.replace(/\.[^.]+$/, '');
  const btn = document.getElementById('btnDocStart');
  const wrap = document.getElementById('docProgressWrap');
  const bar = document.getElementById('docProgressBar');
  const label = document.getElementById('docProgressLabel');
  const done = document.getElementById('docDoneArea');
  if (btn) btn.disabled = true;
  if (wrap) wrap.style.display = 'block';
  if (done) done.style.display = 'none';
  if (bar) bar.style.width = '2%';
  if (label) label.textContent = files.length > 1 ? `تُرفع ${files.length} ملفات أجزاء…` : 'يُرفع الملف…';
  try {
    const form = new FormData();
    files.forEach(f => form.append('files', f));
    form.append('name', name);
    form.append('dpi', document.getElementById('docDpiInput')?.value || '300');
    const sc = readDocScope();
    form.append('scope_mode', sc ? sc.mode : 'all');
    if (sc && sc.volume) form.append('scope_volume', sc.volume);
    if (sc) { form.append('scope_from', sc.from); form.append('scope_to', sc.to); }
    const url = appendId ? `/api/documents/${appendId}/volumes` : '/api/documents/upload';
    const res = await fetch(url, { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'تعذر الرفع');
    window._docAppendId = null;
    pollDocProgress(data.id, data.name);
  } catch (e) {
    if (label) label.textContent = `تعذر الرفع: ${e.message || e}`;
    if (btn) btn.disabled = false;
  }
}

function fmtDocDur(sec) {
  sec = Math.max(0, parseInt(sec || 0, 10));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const n = x => Number(x).toLocaleString('ar-EG');
  const p2 = x => String(Number(x)).padStart(2, '0').replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d]);
  return h > 0 ? `${n(h)}:${p2(m)}:${p2(s)}` : `${n(m)}:${p2(s)}`;
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
        if (label) label.textContent = (p.pages ? `تُحوَّل الوثيقة نصًا… صفحة ${p.page} من ${p.pages}` : 'تُجهَّز الوثيقة…') + (p.elapsed ? ` • الوقت المنقضي ${fmtDocDur(p.elapsed)}` : '');
      } else if (p.status === 'done') {
        clearInterval(docUploadTimer); docUploadTimer = null;
        if (bar) bar.style.width = '100%';
        if (label) label.textContent = `اكتمل التحويل${p.elapsed ? ` في ${fmtDocDur(p.elapsed)}` : ''}: ${p.pages} صفحة${p.volumes > 1 ? ` في ${p.volumes} أجزاء` : ''}، ${Number(p.chars || 0).toLocaleString('ar-EG')} حرفًا.${p.note ? ' ' + p.note : ''}`;
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
    const showArchived = !!document.getElementById('docShowArchived')?.checked;
    const docs = (data.documents || []).filter(d => showArchived || !d.archived);
    if (!docs.length) {
      box.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">لا وثائق محفوظة بعد.</div>';
      return;
    }
    box.innerHTML = docs.map(d => {
      const nm = escapeHtml(d.name || '').replace(/'/g, '');
      const done = d.status === 'done';
      return `
      <div style="display:flex; align-items:center; gap:8px; padding:7px 9px; border:1px solid var(--border-subtle); border-radius:8px; margin-bottom:6px; flex-wrap:wrap; ${d.archived ? 'opacity:0.65;' : ''}">
        <span style="font-size:15px;">📄</span>
        <span style="flex:1; min-width:140px;">
          <span style="display:block; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(d.name || '')}${d.archived ? ' <span style="font-size:10.5px; color:var(--accent-clay);">(مؤرشفة)</span>' : ''}</span>
          <span style="font-size:11.5px; color: var(--text-muted);">${done ? `${d.volume_count > 1 ? `${d.volume_count} أجزاء • ` : ''}${d.pages} صفحة • ${Number(d.chars || 0).toLocaleString('ar-EG')} حرفًا${d.dpi ? ` • القراءة عند ${Number(d.dpi).toLocaleString('ar-EG')} نقطة` : ''}${docScopeLabel(d.scope)}${d.started && d.finished ? ` • حُوّلت في ${fmtDocDur(d.finished - d.started)}` : ''}` : d.status === 'error' ? 'تعذر تحويلها' : 'جارٍ تحويلها…'}</span>
        </span>
        ${done && !d.archived ? `<button class="btn-flat-primary reader-mini-btn" onclick="discussDocument('${d.id}')">مناقشة الوثيقة</button>` : ''}
        ${done ? `<button class="btn-flat-secondary reader-mini-btn" onclick="openDocBrowse('${d.id}', '${nm}')">تصفح</button>` : ''}
        ${done ? `<button class="btn-flat-secondary reader-mini-btn" onclick="exportDocument('${d.id}', 'txt')" title="تصدير النص المحوَّل ملفًا نصيًا">تصدير TXT</button>` : ''}
        ${done ? `<button class="btn-flat-secondary reader-mini-btn" onclick="exportDocument('${d.id}', 'docx')" title="تصدير ملف Word بصفحات الوثيقة وحواشيها">تصدير Word</button>` : ''}
        ${done && !d.archived ? `<button class="btn-flat-secondary reader-mini-btn" onclick="openDocAppend('${d.id}', '${nm}')" title="إضافة أجزاء جديدة إلى هذه الوثيقة">إضافة جزء</button>` : ''}
        ${(done || d.status === 'error') && !d.archived ? `<button class="btn-flat-secondary reader-mini-btn" onclick="reconvertDocument('${d.id}', '${nm}')" title="إعادة التحويل من الملفات الأصلية بالدقة والنطاق المختارين">إعادة تحويل</button>` : ''}
        ${!d.archived
          ? `<button class="btn-flat-secondary reader-mini-btn" onclick="archiveDocument('${d.id}', true)" title="أرشفة الوثيقة: تُخفى من القائمة وتبقى محفوظة">أرشفة</button>`
          : `<button class="btn-flat-secondary reader-mini-btn" onclick="archiveDocument('${d.id}', false)" title="استرجاع الوثيقة من الأرشيف">استرجاع</button>`}
        <button class="btn-flat-secondary reader-mini-btn" onclick="deleteDocument('${d.id}')" title="حذف الوثيقة">حذف</button>
      </div>`;
    }).join('');
  } catch (e) {
    box.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">تعذر جلب الوثائق.</div>';
  }
}

async function reconvertDocument(docId, docName) {
  try {
    const res = await fetch(`/api/documents/${docId}/reconvert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dpi: parseInt(document.getElementById('docDpiInput')?.value || '300', 10),
        scope: readDocScope(),
      }),
    });
    if (!res.ok) throw new Error('تعذر بدء إعادة التحويل');
    showToast('بدأت إعادة التحويل بالدقة المختارة — تُستكمل الحواشي هذه المرة');
    pollDocProgress(docId, docName);
  } catch (e) { showToast('تعذرت إعادة التحويل'); }
}

async function archiveDocument(docId, flag) {
  try {
    const res = await fetch(`/api/documents/${docId}/archive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ archived: flag }),
    });
    if (!res.ok) throw new Error('تعذر');
    showToast(flag ? 'أُرشفت الوثيقة — تجدها بتفعيل «إظهار المؤرشفة»' : 'استُرجعت الوثيقة من الأرشيف');
    loadDocumentsList();
  } catch (e) { showToast(flag ? 'تعذرت الأرشفة' : 'تعذر الاسترجاع'); }
}

function exportDocument(docId, kind) {
  const a = document.createElement('a');
  a.href = `/api/documents/${docId}/export.${kind}`;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  a.remove();
  showToast(kind === 'docx' ? 'يُجهَّز ملف Word ويُنزَّل…' : 'يُنزَّل النص…');
}

// ---------- تصفح الوثيقة: الأصل صورة والنص المحوَّل صفحة بصفحة ----------
window._browse = null;

async function openDocBrowse(docId, docName) {
  window._browse = { id: docId, name: docName || '', volume: 1, page: 1, volumes: [] };
  const modal = document.getElementById('docBrowseModal');
  if (modal) modal.style.display = 'flex';
  const title = document.getElementById('docBrowseTitle');
  if (title) title.textContent = `تصفح: ${docName || 'وثيقة'}`;
  await loadBrowsePage();
}

function closeDocBrowse() {
  const modal = document.getElementById('docBrowseModal');
  if (modal) modal.style.display = 'none';
  window._browse = null;
}

async function loadBrowsePage() {
  const b = window._browse;
  if (!b) return;
  const textEl = document.getElementById('docBrowseText');
  const img = document.getElementById('docBrowseImg');
  const noImg = document.getElementById('docBrowseNoImg');
  const info = document.getElementById('docBrowseInfo');
  try {
    const res = await fetch(`/api/documents/${b.id}/page?volume=${b.volume}&page=${b.page}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'تعذر');
    b.volumes = data.volumes || [];
    // قائمة الأجزاء
    const volWrap = document.getElementById('docBrowseVolWrap');
    const volSel = document.getElementById('docBrowseVolume');
    if (volSel && b.volumes.length > 1) {
      volSel.innerHTML = b.volumes.map(v => `<option value="${v.volume}" ${v.volume === b.volume ? 'selected' : ''}>الجزء ${Number(v.volume).toLocaleString('ar-EG')}</option>`).join('');
      if (volWrap) volWrap.style.display = 'flex';
    } else if (volWrap) {
      volWrap.style.display = 'none';
    }
    const volInfo = b.volumes.find(v => v.volume === b.volume) || { pages: 0, has_original: false };
    const pageInput = document.getElementById('docBrowsePage');
    if (pageInput) { pageInput.value = b.page; pageInput.max = volInfo.pages || 1; }
    if (info) info.textContent = volInfo.pages
      ? `صفحة ${Number(b.page).toLocaleString('ar-EG')} من ${Number(volInfo.pages).toLocaleString('ar-EG')}${b.volumes.length > 1 ? ` — الجزء ${Number(b.volume).toLocaleString('ar-EG')}` : ''}${data.converted ? '' : ' — هذه الصفحة خارج نطاق التحويل المحفوظ'}`
      : '';
    if (textEl) textEl.textContent = data.text || (data.converted ? '' : 'لم تُحوَّل هذه الصفحة ضمن نطاق التحويل المختار للوثيقة.');
    if (volInfo.has_original) {
      if (img) {
        img.style.display = 'block';
        img.src = `/api/documents/${b.id}/page-image?volume=${b.volume}&page=${b.page}&t=${Date.now()}`;
      }
      if (noImg) noImg.style.display = 'none';
    } else {
      if (img) img.style.display = 'none';
      if (noImg) { noImg.style.display = 'block'; noImg.textContent = 'الأصل ملف نصي: لا صورة له.'; }
    }
  } catch (e) {
    if (textEl) textEl.textContent = 'تعذر جلب الصفحة.';
  }
}

function browseStep(delta) {
  const b = window._browse;
  if (!b) return;
  const volInfo = (b.volumes || []).find(v => v.volume === b.volume) || { pages: 1 };
  b.page = Math.min(Math.max(1, b.page + delta), volInfo.pages || 1);
  loadBrowsePage();
}

function browsePageJump() {
  const b = window._browse;
  if (!b) return;
  const v = parseInt(document.getElementById('docBrowsePage')?.value || '1', 10);
  const volInfo = (b.volumes || []).find(x => x.volume === b.volume) || { pages: 1 };
  if (Number.isFinite(v)) b.page = Math.min(Math.max(1, v), volInfo.pages || 1);
  loadBrowsePage();
}

function browseVolumeChanged() {
  const b = window._browse;
  if (!b) return;
  b.volume = parseInt(document.getElementById('docBrowseVolume')?.value || '1', 10) || 1;
  b.page = 1;
  loadBrowsePage();
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
