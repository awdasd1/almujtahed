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
  restoreDocOcrUI();
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

// ---------- محرك قراءة الصفحات المصوّرة: محلي أو نموذج OpenRouter ----------
function docOcrSelection() {
  const engine = document.querySelector('input[name="docOcrEngine"]:checked')?.value
    || localStorage.getItem('almojtahed_ocr_engine') || 'local';
  return { engine, model: localStorage.getItem('almojtahed_ocr_model') || '' };
}

function docOcrEngineChanged() {
  const { engine, model } = docOcrSelection();
  localStorage.setItem('almojtahed_ocr_engine', engine);
  const btn = document.getElementById('btnDocOcrPick');
  if (btn) btn.disabled = engine !== 'openrouter';
  const label = document.getElementById('docOcrModelLabel');
  if (label) {
    const rec = (window.openrouterModelsList || []).find(m => m.id === model);
    label.textContent = engine === 'openrouter' ? (rec ? (rec.name || model) : (model || 'لم يُختر نموذج')) : '';
  }
}

function restoreDocOcrUI() {
  const engine = localStorage.getItem('almojtahed_ocr_engine') || 'local';
  const radio = document.querySelector(`input[name="docOcrEngine"][value="${engine}"]`);
  if (radio) radio.checked = true;
  docOcrEngineChanged();
}

let docOcrModelsCache = null;

async function loadDocOcrModels(force) {
  const box = document.getElementById('docOcrList');
  if (!force && docOcrModelsCache) { renderDocOcrList(); return; }
  if (box) box.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">تُجلب نماذج OpenRouter…</div>';
  try {
    const res = await fetch('/api/openrouter/models');
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'تعذر جلب النماذج');
    docOcrModelsCache = data.models || [];
    window.openrouterModelsList = docOcrModelsCache;
    renderDocOcrList();
  } catch (e) {
    if (box) box.innerHTML = `<div style="color: var(--text-muted); font-size: 13px;">تعذر جلب النماذج: ${escapeHtml(e.message || String(e))}. تأكد من مفتاح OpenRouter في تبويب الخدمات.</div>`;
  }
}

function renderDocOcrList() {
  const box = document.getElementById('docOcrList');
  if (!box) return;
  const q = (document.getElementById('docOcrSearch')?.value || '').toLowerCase().trim();
  const visionOnly = !!document.getElementById('docOcrVisionOnly')?.checked;
  const { model } = docOcrSelection();
  let list = docOcrModelsCache || [];
  if (visionOnly) list = list.filter(m => (m.input_modalities || []).includes('image'));
  if (q) list = list.filter(m => (m.id || '').toLowerCase().includes(q) || (m.name || '').toLowerCase().includes(q));
  if (!list.length) {
    box.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">لا نماذج مطابقة للفلترة.</div>';
    return;
  }
  const price = m => {
    const p = m.pricing || {};
    return `$${(p.prompt_per_1m ?? 0).toFixed(2)}/$${(p.completion_per_1m ?? 0).toFixed(2)} لكل مليون`;
  };
  box.innerHTML = list.slice(0, 300).map(m => `
    <div style="display:flex; align-items:center; gap:8px; padding:7px 9px; border:1px solid ${m.id === model ? 'var(--accent-clay)' : 'var(--border-subtle)'}; border-radius:8px; margin-bottom:6px; flex-wrap:wrap;">
      <span style="flex:1; min-width:200px;">
        <span style="display:block; font-weight:600;">${escapeHtml(m.name || m.id)}</span>
        <span style="font-size:11px; color: var(--text-muted); direction:ltr; display:block; text-align:right;">${escapeHtml(m.id)}</span>
        <span style="font-size:11.5px; color: var(--text-muted);">سياق ${m.context_length ? Number(m.context_length).toLocaleString('ar-EG') : '—'} • ${price(m)}${(m.input_modalities || []).includes('image') ? ' • 📷 يقبل الصور' : ''}</span>
      </span>
      <button type="button" class="btn-flat-secondary reader-mini-btn" onclick="showDocOcrInfo('${m.id}')">تعريف</button>
      <button type="button" class="btn-flat-primary reader-mini-btn" onclick="pickDocOcrModel('${m.id}')">اختيار</button>
    </div>`).join('');
}

async function showDocOcrInfo(modelId) {
  const panel = document.getElementById('docOcrInfo');
  if (!panel) return;
  const m = (docOcrModelsCache || []).find(x => x.id === modelId);
  if (!m) return;
  const plain = (typeof plainModelDescription === 'function') ? plainModelDescription : (t => String(t || ''));
  panel.style.display = 'block';
  panel.innerHTML = `<strong>${escapeHtml(m.name || m.id)}</strong>
    <span style="direction:ltr; display:inline-block;">(${escapeHtml(m.id)})</span><br>
    سياق: ${m.context_length ? Number(m.context_length).toLocaleString('ar-EG') : '—'} توكن • إدخال: ${escapeHtml((m.input_modalities || ['text']).join('، '))} • إخراج: ${escapeHtml((m.output_modalities || ['text']).join('، '))}<br>
    أسعار (لكل مليون توكن): إدخال $${(m.pricing?.prompt_per_1m ?? 0).toFixed(3)} • إخراج $${(m.pricing?.completion_per_1m ?? 0).toFixed(3)}
    <div id="docOcrAbout" style="margin-top:6px;">${escapeHtml(plain(m.description || '')) || 'يُجلب التعريف…'}</div>`;
  try {
    const res = await fetch('/api/openrouter/model-about?model_id=' + encodeURIComponent(modelId));
    if (res.ok) {
      const data = await res.json();
      const el = document.getElementById('docOcrAbout');
      if (el && data && data.description) el.textContent = plain(data.description);
    }
  } catch (e) { /* يبقى وصف الكتالوج */ }
}

function pickDocOcrModel(modelId) {
  localStorage.setItem('almojtahed_ocr_model', modelId);
  localStorage.setItem('almojtahed_ocr_engine', 'openrouter');
  const radio = document.querySelector('input[name="docOcrEngine"][value="openrouter"]');
  if (radio) radio.checked = true;
  docOcrEngineChanged();
  closeDocOcrPicker();
  showToast('صار نموذج القراءة: ' + modelId);
}

function openDocOcrPicker() {
  const modal = document.getElementById('docOcrModal');
  if (modal) modal.style.display = 'flex';
  loadDocOcrModels(false);
}

function closeDocOcrPicker() {
  const modal = document.getElementById('docOcrModal');
  if (modal) modal.style.display = 'none';
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
    form.append('dpi', document.getElementById('docDpiInput')?.value || '150');
    const sc = readDocScope();
    form.append('scope_mode', sc ? sc.mode : 'all');
    if (sc && sc.volume) form.append('scope_volume', sc.volume);
    if (sc) { form.append('scope_from', sc.from); form.append('scope_to', sc.to); }
    const ocr = docOcrSelection();
    if (ocr.engine === 'openrouter' && !ocr.model) { showToast('اختر نموذج القراءة من OpenRouter أولاً'); if (btn) btn.disabled = false; return; }
    form.append('ocr_engine', ocr.engine);
    if (ocr.model) form.append('ocr_model', ocr.model);
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

let docPollingId = null;

async function stopDocConversion() {
  if (docPollingId) await stopDocConversionById(docPollingId);
}

async function stopDocConversionById(docId) {
  try {
    const res = await fetch(`/api/documents/${docId}/cancel`, { method: 'POST' });
    if (!res.ok) throw new Error('تعذر');
    showToast('أُوقف التحويل فورًا — يُحفظ ما تمّ من صفحات');
    const stopBtn = document.getElementById('btnDocStop');
    if (stopBtn) stopBtn.disabled = true;
    setTimeout(loadDocumentsList, 1500);
  } catch (e) { showToast('تعذر إيقاف التحويل'); }
}

let docFallbackDocId = null;

function showDocFallback(prompt, docId) {
  const modal = document.getElementById('docFallbackModal');
  const text = document.getElementById('docFallbackText');
  if (!modal || !text) return;
  const model = prompt?.model ? `«${prompt.model}» ` : '';
  const reason = prompt?.reason ? ` (${prompt.reason})` : '';
  text.textContent = `النموذج ${model}لا يستطيع قراءة الصفحات${reason}. سيتم التحويل إلى النموذج الافتراضي لأنظمة ماك (القراءة المحلية على هذا الجهاز). «قبول» يكمل التحويل محليًا، و«إلغاء» يوقف التحويل ويحفظ ما تمّ.`;
  modal.style.display = 'flex';
  docFallbackDocId = docId;
}

function hideDocFallback() {
  const modal = document.getElementById('docFallbackModal');
  if (modal) modal.style.display = 'none';
  docFallbackDocId = null;
}

async function resolveDocFallback(decision) {
  const docId = docFallbackDocId;
  hideDocFallback();
  if (!docId) return;
  try {
    await fetch(`/api/documents/${docId}/fallback`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({decision}),
    });
    showToast(decision === 'accept' ? 'سيُكمل التحويل بالمحرك المحلي الافتراضي للماك' : 'أُلغي التحويل وحُفظ ما تمّ');
  } catch (e) { showToast('تعذر إيصال القرار'); }
}

function pollDocProgress(docId, docName) {
  docPollingId = docId;
  const bar = document.getElementById('docProgressBar');
  const label = document.getElementById('docProgressLabel');
  const done = document.getElementById('docDoneArea');
  const btn = document.getElementById('btnDocStart');
  const stopBtn = document.getElementById('btnDocStop');
  if (stopBtn) { stopBtn.style.display = 'inline-block'; stopBtn.disabled = false; }
  if (docUploadTimer) clearInterval(docUploadTimer);
  docUploadTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/documents/${docId}/progress`);
      const p = await res.json();
      if (p.fallback_prompt && docFallbackDocId !== docId) showDocFallback(p.fallback_prompt, docId);
      if (!p.fallback_prompt && docFallbackDocId === docId) hideDocFallback();
      if (p.status === 'converting' || p.status === 'queued') {
        const pct = p.pages ? Math.max(3, Math.round((p.page / p.pages) * 100)) : 4;
        if (bar) bar.style.width = `${pct}%`;
        if (label) label.textContent = (p.pages ? `تُحوَّل الوثيقة نصًا… صفحة ${p.page} من ${p.pages}` : 'تُجهَّز الوثيقة…') + (p.elapsed ? ` • الوقت المنقضي ${fmtDocDur(p.elapsed)}` : '');
      } else if (p.status === 'cancelled') {
        clearInterval(docUploadTimer); docUploadTimer = null;
        docPollingId = null;
        if (stopBtn) stopBtn.style.display = 'none';
        if (label) label.textContent = `أُوقف التحويل: حُفظت ${p.page} صفحة (${Number(p.chars || 0).toLocaleString('ar-EG')} حرفًا)${p.elapsed ? ` في ${fmtDocDur(p.elapsed)}` : ''}. أعد التحويل من القائمة لاستكمال الباقي.`;
        if (btn) btn.disabled = false;
        loadDocumentsList();
      } else if (p.status === 'done') {
        clearInterval(docUploadTimer); docUploadTimer = null;
        docPollingId = null;
        if (stopBtn) stopBtn.style.display = 'none';
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
        docPollingId = null;
        if (stopBtn) stopBtn.style.display = 'none';
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
    if (docs.some(d => d.rag_status === 'building')) {
      if (!docRagRefreshTimer) docRagRefreshTimer = setTimeout(() => { docRagRefreshTimer = null; loadDocumentsList(); }, 1200);
    }
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
          <span style="font-size:11.5px; color: var(--text-muted);">${done ? `${d.volume_count > 1 ? `${d.volume_count} أجزاء • ` : ''}${d.pages} صفحة • ${Number(d.chars || 0).toLocaleString('ar-EG')} حرفًا${d.dpi ? ` • القراءة عند ${Number(d.dpi).toLocaleString('ar-EG')} نقطة` : ''}${d.ocr_engine === 'openrouter' && d.ocr_model ? ` • قراءة بنموذج <span style="direction:ltr; display:inline-block;">${escapeHtml(d.ocr_model)}</span>` : ''}${d.ocr_fallback ? ' • تعذّر النموذج فحُوّلت بالمحرك المحلي' : ''}${d.rag_status === 'done' ? ` • 🧠 بحث دلالي (${Number(d.rag_chunks || 0).toLocaleString('ar-EG')} مقطعًا)` : d.rag_status === 'building' ? ' • 🧠 تُفهرس دلاليًا الآن…' : d.rag_status === 'stale' ? ' • 🧠 الفهرسة الدلالية قديمة بعد إعادة التحويل' : d.rag_status === 'error' ? ' • 🧠 فشلت الفهرسة الدلالية' : ''}${docScopeLabel(d.scope)}${d.started && d.finished ? ` • حُوّلت في ${fmtDocDur(d.finished - d.started)}` : ''}` : d.status === 'error' ? 'تعذر تحويلها' : d.status === 'cancelled' ? `أُوقف التحويل عند ${Number(d.page || 0).toLocaleString('ar-EG')} صفحة — حُفظ ما تمّ` : `جارٍ تحويلها… صفحة ${Number(d.page || 0).toLocaleString('ar-EG')} من ${Number(d.pages || 0).toLocaleString('ar-EG')}`}</span>
        </span>
        ${d.status === 'converting' || d.status === 'queued' ? `<button class="btn-flat-secondary reader-mini-btn" style="color:#c0392b;" onclick="stopDocConversionById('${d.id}')" title="إيقاف فوري: تُسقط الصفحة الجارية ويُحفظ ما قبلها">⏹ إيقاف التحويل</button>` : ''}
        ${done && !d.archived ? `<button class="btn-flat-primary reader-mini-btn" onclick="discussDocument('${d.id}')">مناقشة الوثيقة</button>` : ''}
        ${done || d.status === 'cancelled' ? `<button class="btn-flat-secondary reader-mini-btn" onclick="openDocBrowse('${d.id}', '${nm}')">تصفح</button>` : ''}
        ${done || d.status === 'cancelled' ? `<button class="btn-flat-secondary reader-mini-btn" onclick="exportDocument('${d.id}', 'txt')" title="تصدير النص المحوَّل ملفًا نصيًا">تصدير TXT</button>` : ''}
        ${done || d.status === 'cancelled' ? `<button class="btn-flat-secondary reader-mini-btn" onclick="exportDocument('${d.id}', 'docx')" title="تصدير ملف Word بصفحات الوثيقة وحواشيها">تصدير Word</button>` : ''}
        ${done && !d.archived ? `<button class="btn-flat-secondary reader-mini-btn" onclick="openDocAppend('${d.id}', '${nm}')" title="إضافة أجزاء جديدة إلى هذه الوثيقة">إضافة جزء</button>` : ''}
        ${done && d.rag_status !== 'building' ? `<button class="btn-flat-secondary reader-mini-btn" onclick="buildRag('${d.id}')" title="فهرسة دلالية (RAG): تضمين مقاطع الوثيقة بنموذج baai/bge-m3 عبر OpenRouter ليُبحث فيها بالمعنى مع اللفظ">${d.rag_status === 'done' ? '↻ إعادة الفهرسة الدلالية' : '🧠 فهرسة دلالية'}</button>` : ''}
        ${d.rag_status === 'building' ? `<div style="flex-basis: 100%; display: flex; align-items: center; gap: 8px; margin-top: 6px;">
          <div style="flex: 1; height: 8px; background: var(--border-subtle); border-radius: 999px; overflow: hidden;"><div style="height: 100%; width: ${d.rag_total ? Math.min(100, Math.max(2, Math.round(100 * (d.rag_done || 0) / d.rag_total))) : 2}%; background: var(--accent-clay); border-radius: 999px; transition: width 0.4s ease;"></div></div>
          <span style="font-size: 11.5px; color: var(--text-muted); white-space: nowrap;">🧠 فهرسة دلالية: ${Number(d.rag_done || 0).toLocaleString('ar-EG')} من ${Number(d.rag_total || 0).toLocaleString('ar-EG')} مقطعًا (${d.rag_total ? Math.round(100 * (d.rag_done || 0) / d.rag_total) : 0}٪)</span>
          <button class="btn-flat-secondary reader-mini-btn" style="color: #c0392b; white-space: nowrap;" onclick="stopRagBuild('${d.id}')" title="إيقاف الفهرسة الدلالية الآن">⏹ إيقاف الفهرسة</button>
        </div>` : ''}
        ${(done || d.status === 'error' || d.status === 'cancelled') && !d.archived ? `<button class="btn-flat-secondary reader-mini-btn" onclick="reconvertDocument('${d.id}', '${nm}')" title="إعادة التحويل من الملفات الأصلية بالدقة والنطاق المختارين">إعادة تحويل</button>` : ''}
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
        dpi: parseInt(document.getElementById('docDpiInput')?.value || '150', 10),
        scope: readDocScope(),
        ocr_engine: docOcrSelection().engine,
        ocr_model: docOcrSelection().model,
      }),
    });
    if (!res.ok) throw new Error('تعذر بدء إعادة التحويل');
    showToast('بدأت إعادة التحويل بالدقة المختارة — تُستكمل الحواشي هذه المرة');
    pollDocProgress(docId, docName);
  } catch (e) { showToast('تعذرت إعادة التحويل'); }
}

let docRagRefreshTimer = null;

async function buildRag(docId) {
  try {
    const res = await fetch(`/api/documents/${docId}/rag/build`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}',
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { showToast(data.detail || 'تعذرت الفهرسة الدلالية'); return; }
    showToast(data.building ? 'بدأت الفهرسة الدلالية… تُبنى في الخلفية وتظهر نتيجتها في القائمة' : 'الفهرسة جارية أصلًا');
    loadDocumentsList();
  } catch (e) { showToast('تعذرت الفهرسة الدلالية'); }
}

async function stopRagBuild(docId) {
  try {
    await fetch(`/api/documents/${docId}/rag/cancel`, {method: 'POST'});
    showToast('أُوقفت الفهرسة الدلالية');
    setTimeout(loadDocumentsList, 1200);
  } catch (e) { showToast('تعذر إيقاف الفهرسة'); }
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

// ── نقد ومقارنة: وثيقة مرفوعة × نطاق شاملة محدد (+ ويب)، بضبط صارم خادمي ──
// مدخلها قائمة السلاش الأصلية في حقل المحادثة (بحث حر/مخصص/موسع/نقد ومقارنة)
function closeCritiqueModal() {
  const modal = document.getElementById('docCritiqueModal');
  if (modal) modal.style.display = 'none';
}

async function openCritiqueModal() {
  const modal = document.getElementById('docCritiqueModal');
  if (modal) modal.style.display = 'flex';
  const list = document.getElementById('critDocList');
  if (list) {
    list.innerHTML = '<div style="font-size: 12.5px; color: var(--text-muted); padding: 8px;">جارٍ التحميل…</div>';
    try {
      const res = await fetch('/api/documents');
      const data = await res.json();
      const docs = (data.documents || []).filter(d => !d.archived);
      if (!docs.length) {
        list.innerHTML = '<div style="font-size: 12.5px; color: var(--text-muted); padding: 8px;">لا وثائق بعد — ارفع وثيقة وحوّلها أولًا من «📄 رفع وثيقة كاملة».</div>';
      } else {
        let firstDone = true;
        list.innerHTML = docs.map(d => {
          const ok = d.status === 'done';
          const checked = ok && firstDone ? ' checked' : '';
          if (ok) firstDone = false;
          const when = d.created ? new Date(d.created * 1000).toLocaleDateString('ar-EG', {day: 'numeric', month: 'long'}) : '';
          const state = ok ? '' : d.status === 'converting' || d.status === 'queued' ? ' — جارٍ تحويلها، أكملها أولًا' : d.status === 'cancelled' ? ' — تحويل موقوف جزئيًا، أعد تحويلها أولًا' : ' — تعذر تحويلها';
          return `<label style="display: flex; align-items: center; gap: 8px; padding: 7px 8px; border-radius: 6px; font-size: 13px; ${ok ? 'cursor: pointer;' : 'opacity: 0.55;'}">
            <input type="radio" name="critDocPick" value="${d.id}" data-name="${escapeHtml(d.name || 'وثيقة')}" ${checked} ${ok ? '' : 'disabled'}>
            <span style="flex: 1;">${escapeHtml(d.name || 'وثيقة')}${d.rag_status === 'done' ? ' 🧠' : ''}<span style="display: block; font-size: 11.5px; color: var(--text-muted);">${Number(d.pages || 0).toLocaleString('ar-EG')} صفحة${when ? ' • ' + when : ''}${state}</span></span>
          </label>`;
        }).join('');
      }
    } catch (e) {
      list.innerHTML = '<div style="font-size: 12.5px; color: #c0392b; padding: 8px;">تعذر جلب الوثائق</div>';
    }
  }
  buildCritCats();
  buildCritModels();
  renderCritBooksChips();
  critScopeChanged();
}

function buildCritModels() {
  const box = document.getElementById('critModelList');
  if (!box) return;
  const src = document.getElementById('chatModelSelect');
  const opts = src ? Array.from(src.options).filter(o => o.value) : [];
  box.innerHTML = `<label class="crit-model-row"><input type="radio" name="critModelPick" value="" checked><span>نموذج المحادثة الحالي</span></label>`
    + (opts.length
      ? opts.map(o => `<label class="crit-model-row"><input type="radio" name="critModelPick" value="${escapeHtml(o.value)}"><span>${escapeHtml(o.textContent)}</span></label>`).join('')
      : '<div style="font-size: 12px; color: var(--text-muted); padding: 4px 8px;">تُحمّل قائمة النماذج من الخدمات؛ يبقى نموذج المحادثة الحالي خيارًا قائمًا.</div>');
}

function buildCritCats() {
  const box = document.getElementById('critCatsBox');
  if (!box || box.dataset.built) return;
  box.dataset.built = '1';
  const src = document.getElementById('filterCategory');
  const opts = src ? Array.from(src.options).filter(o => o.value) : [];
  box.innerHTML = opts.map(o => {
    const name = o.textContent.replace(/^\s*\d+\s*[.．]\s*/, '').trim();
    return `<label style="display: inline-block; font-size: 12.5px; margin: 3px 8px 3px 0;"><input type="checkbox" class="critCatCheck" value="${escapeHtml(name)}"> ${escapeHtml(name)}</label>`;
  }).join('') || '<span style="font-size: 12px; color: var(--text-muted);">لا أقسام متاحة</span>';
}

function critScopeChanged() {
  const mode = document.querySelector('input[name="critScopeMode"]:checked')?.value || 'all';
  const cats = document.getElementById('critCatsBox');
  const books = document.getElementById('critBooksBox');
  if (cats) cats.style.display = mode === 'categories' ? 'block' : 'none';
  if (books) books.style.display = mode === 'books' ? 'block' : 'none';
}

function renderCritBooksChips() {
  const box = document.getElementById('critBooksChips');
  if (!box) return;
  const titles = window._critiqueBookTitles || [];
  box.innerHTML = titles.length
    ? titles.map(t => `<span class="design-book-sel-chip">${escapeHtml(t)}<button type="button" onclick="removeCritBook('${escapeHtml(t).replace(/'/g, "\\'")}')" title="حذف من النطاق">×</button></span>`).join('')
    : '<span style="font-size: 12px; color: var(--text-muted);">لا كتب محددة بعد</span>';
}

function removeCritBook(title) {
  window._critiqueBookTitles = (window._critiqueBookTitles || []).filter(t => t !== title);
  renderCritBooksChips();
}
window.onCritiqueBooks = function () { renderCritBooksChips(); };

async function startCritiqueSession() {
  const pick = document.querySelector('input[name="critDocPick"]:checked');
  const docId = pick?.value || '';
  if (!docId) { showToast('اختر وثيقة محوّلة أولًا (ارفعها من «رفع وثيقة كاملة» إن لم توجد)'); return; }
  const docName = pick?.dataset?.name || 'وثيقة';
  const mode = document.querySelector('input[name="critScopeMode"]:checked')?.value || 'all';
  const scope = { mode };
  if (mode === 'categories') {
    scope.categories = Array.from(document.querySelectorAll('.critCatCheck:checked')).map(c => c.value);
    if (!scope.categories.length) { showToast('حدّد قسمًا واحدًا على الأقل أو اختر «جميع كتب الشاملة»'); return; }
  }
  if (mode === 'books') {
    const titles = window._critiqueBookTitles || [];
    if (!titles.length) { showToast('حدّد كتابًا واحدًا على الأقل من الشاملة'); return; }
    if (typeof catalogBooksCache !== 'undefined' && !catalogBooksCache.length) {
      try { catalogBooksCache = await (await fetch('/api/books')).json(); } catch (e) { /* تُحل الأسماء خادميًا عندها */ }
    }
    scope.books = titles.map(t => {
      const f = (typeof catalogBooksCache !== 'undefined' ? catalogBooksCache : []).find(b => b.title === t);
      return { id: f && f.id != null ? f.id : '', title: t };
    });
  }
  closeCritiqueModal();
  if (typeof switchMainTab === 'function') switchMainTab('chat');
  if (typeof createNewChatSession === 'function') createNewChatSession(true, `نقد ومقارنة: ${docName}`.slice(0, 40));
  const session = (typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null;
  if (session) {
    delete session.docId;
    delete session.docName;
    session.critique = {
      document_id: docId, document_name: docName, scope,
      web: !!document.getElementById('critWebCheck')?.checked,
      model: document.querySelector('input[name="critModelPick"]:checked')?.value || '',
      thinking: document.querySelector('input[name="critThinkingPick"]:checked')?.value || '',
      witnesses: parseInt(document.querySelector('input[name="critWitnessPick"]:checked')?.value || '20', 10),
    };
    if (typeof saveChatSessions === 'function') saveChatSessions();
  }
  updateDocChip();
  updateCritChip();
  showToast('بدأت جلسة النقد والمقارنة ⚖️ اكتب طلبك بالضبط: ما الذي يُنقد أو يُقارَن في الوثيقة؟');
  const input = document.getElementById('chatInputText');
  if (input) input.focus();
}

function detachCritique() {
  const session = (typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null;
  if (session) {
    delete session.critique;
    if (typeof saveChatSessions === 'function') saveChatSessions();
  }
  updateCritChip();
}

function updateCritChip() {
  const chip = document.getElementById('critChatChip');
  if (!chip) return;
  const session = (typeof chatSessions !== 'undefined') ? chatSessions.find(s => s.id === activeSessionId) : null;
  const crit = session?.critique;
  if (crit) {
    chip.style.display = 'flex';
    const name = document.getElementById('critChatChipName');
    if (name) name.textContent = crit.document_name || 'وثيقة';
    const scopeEl = document.getElementById('critChatChipScope');
    if (scopeEl) {
      const s = crit.scope || {};
      scopeEl.textContent = '• النطاق: ' + (
        s.mode === 'books' ? `${(s.books || []).length} كتب محددة`
        : s.mode === 'categories' ? `أقسام: ${(s.categories || []).join('، ')}`
        : 'جميع كتب الشاملة') + (crit.web ? ' + ويب' : '');
    }
  } else {
    chip.style.display = 'none';
  }
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
    updateCritChip();
    return out;
  };
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDocSlash);
} else {
  initDocSlash();
}
