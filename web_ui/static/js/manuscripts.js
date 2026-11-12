// =============================================================================
// تحقيق المخطوطات — المرحلة ١: مشاريع ونسخ ولوحات، ونسخ اللوحة بنموذجين
// (أساسي سريع + مدقق متحفظ) مع جدول مواضع اختلافهما ليحسمها المحقق،
// فلا يُعتمد نص إلا بقراره. الحفظ خادمي فوري في كل خطوة.
// =============================================================================
let msProjects = [];
let msModels = { primary: '', checker: '' };
// قياسات م٠ الموسعة (مغربية وسودانية): Gemini 3.1 Pro الأقوى قراءة للخطوط
// الصعبة، وSonnet 5.5 دقيق وصادق حيث يشك فيصلح مدققًا وثانيًا، وMuse Wonder
// رُفض (الأغلى والأخلط حرفيًا)، و2.5 Pro انهار في تشغيل (تسرّب تفكير) فلا يعتمد وحده.
const MS_MODEL_CHOICES = [
  ['~google/gemini-pro-latest', 'Gemini Pro Latest — القارئ الأول المعتمد (دقة)'],
  ['~google/gemini-flash-latest', 'Gemini Flash Latest — القارئ الثاني المعتمد (سرعة ورخص)'],
  ['google/gemini-4-argon', 'Gemini 4 Argon — المدقق المعتمد'],
  ['google/gemini-3.1-pro-preview', 'Gemini 3.1 Pro — قوي قراءة للخطوط الصعبة (غالٍ بطيء)'],
  ['anthropic/claude-sonnet-5.5', 'Claude Sonnet 5.5 — دقيق وصادق في مواضع الشك'],
  ['google/gemini-2.5-flash', 'Gemini 2.5 Flash — سريع اقتصادي'],
  ['google/gemini-2.5-pro', 'Gemini 2.5 Pro — قوي (تذبذب مرة)'],
  ['qwen/qwen3-vl-235b-a22b-instruct', 'Qwen3-VL — قوي ورخيص'],
  ['qwen/qwen2.5-vl-72b-instruct', 'Qwen2.5-VL — متوسط'],
  ['~openai/gpt-luna-latest', 'GPT Luna — مدقق متحفظ'],
  ['anthropic/claude-sonnet-5', 'Claude Sonnet 5 — غالٍ'],
];
const MS_MODEL_PRESETS = {
  standard: { primary: '~google/gemini-pro-latest', checker: '~google/gemini-flash-latest', auditor: 'google/gemini-4-argon' },
  hard: { primary: 'google/gemini-3.1-pro-preview', checker: 'anthropic/claude-sonnet-5.5', auditor: 'google/gemini-3.1-pro-preview' },
};

function msModelChoice() {
  try {
    const saved = JSON.parse(localStorage.getItem('almujtahed_ms_models_v2') || 'null');
    if (saved && saved.primary && saved.checker) {
      return { primary: saved.primary, checker: saved.checker, auditor: saved.auditor || MS_MODEL_PRESETS.standard.auditor };
    }
  } catch (e) { /* الافتراضي */ }
  return { ...MS_MODEL_PRESETS.standard };
}

function msFillModelSelects() {
  const choice = msModelChoice();
  [['msPrimaryModel', choice.primary], ['msCheckerModel', choice.checker], ['msAuditorModel', choice.auditor]].forEach(([id, val]) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = MS_MODEL_CHOICES.map(([v, label]) =>
      `<option value="${v}"${v === val ? ' selected' : ''}>${label}</option>`).join('');
  });
}

function msSaveModelChoice() {
  const primary = document.getElementById('msPrimaryModel')?.value;
  const checker = document.getElementById('msCheckerModel')?.value;
  const auditor = document.getElementById('msAuditorModel')?.value;
  if (primary && checker && auditor) {
    localStorage.setItem('almujtahed_ms_models_v2', JSON.stringify({ primary, checker, auditor }));
    msToast('حُفظ اختيار نماذج النسخ والتدقيق');
  }
}

function msPresetModels(name) {
  const preset = MS_MODEL_PRESETS[name];
  if (!preset) return;
  localStorage.setItem('almujtahed_ms_models_v2', JSON.stringify(preset));
  msFillModelSelects();
  msToast(name === 'hard' ? 'وضع الخطوط الصعبة: Gemini 3.1 Pro أولًا، Sonnet 5.5 ثانيًا، يدققه Gemini 3.1 Pro' : 'الوضع الموحّد المعتمد: Gemini Pro Latest أولًا، Gemini Flash Latest ثانيًا، يدققهما Gemini 4 Argon');
}
let msWb = null; // {projectId, copyId, folioId}
let msSaveTimer = null;
let msLoaded = false;

function msEsc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function msToast(msg, ms) {
  if (typeof showToast === 'function') showToast(msg, ms || 3500);
}
function msUid() { return 'ms' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
function msProject(id) { return msProjects.find(p => p.id === id) || null; }
function msCopy(project, copyId) { return project ? (project.copies || []).find(c => c.id === copyId) || null : null; }
function msFolio(copy, folioId) { return copy ? (copy.folios || []).find(f => f.id === folioId) || null : null; }

async function initManuscriptsTab() {
  if (msLoaded) { renderMsProjects(); return; }
  try {
    const res = await fetch('/api/manuscripts');
    const data = await res.json();
    msProjects = Array.isArray(data.projects) ? data.projects : [];
    if (data.models) msModels = data.models;
  } catch (e) { msProjects = []; }
  msLoaded = true;
  msFillModelSelects();
  renderMsProjects();
}

function msSave() {
  clearTimeout(msSaveTimer);
  msSaveTimer = setTimeout(async () => {
    try {
      await fetch('/api/manuscripts', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projects: msProjects }),
      });
    } catch (e) { /* يُعاد الحفظ عند أي تغيير لاحق */ }
  }, 350);
}

function msFolioProgress(copy) {
  const folios = copy.folios || [];
  const approved = folios.filter(f => f.status === 'approved').length;
  return { total: folios.length, approved };
}

// ---------- قائمة المشاريع ----------
function renderMsProjects() {
  const wrap = document.getElementById('msProjectsList');
  if (!wrap) return;
  if (!msProjects.length) {
    wrap.innerHTML = '<div class="ms-empty">لا مشاريع تحقيق بعد. أنشئ أول مشروع، ثم أضف نسخة وارفع لوحاتها لبدء النسخ.</div>';
    return;
  }
  wrap.innerHTML = msProjects.map(p => {
    const copies = p.copies || [];
    const stats = copies.reduce((acc, c) => {
      const pr = msFolioProgress(c);
      acc.total += pr.total; acc.approved += pr.approved;
      return acc;
    }, { total: 0, approved: 0 });
    return `<div class="ms-project-card">
      <div class="ms-project-card-title">📜 ${msEsc(p.title)}</div>
      ${p.author ? `<div class="ms-project-card-author">${msEsc(p.author)}</div>` : ''}
      ${p.desc ? `<div class="ms-project-card-desc">${msEsc(p.desc)}</div>` : ''}
      <div class="ms-project-card-stats">${copies.length} نسخة · ${stats.total} لوحة · ✔ ${stats.approved} معتمدة</div>
      <div class="ms-card-actions">
        <button type="button" class="ms-btn ms-btn-primary" onclick="msOpenProject('${p.id}')">فتح المشروع</button>
        <button type="button" class="ms-btn ms-btn-danger" onclick="msDeleteProject('${p.id}')">حذف</button>
      </div>
    </div>`;
  }).join('');
}

function msCreateProject() {
  const title = document.getElementById('msNewTitle').value.trim();
  if (!title) { msToast('اكتب عنوان الكتاب المخطوط أولًا'); return; }
  const p = {
    id: msUid(), title,
    author: document.getElementById('msNewAuthor').value.trim(),
    desc: document.getElementById('msNewDesc').value.trim(),
    createdAt: new Date().toISOString(), copies: [],
  };
  msProjects.unshift(p);
  document.getElementById('msNewTitle').value = '';
  document.getElementById('msNewAuthor').value = '';
  document.getElementById('msNewDesc').value = '';
  msSave(); renderMsProjects(); msOpenProject(p.id);
}

function msDeleteProject(id) {
  const p = msProject(id);
  if (!p || !confirm(`حذف مشروع «${p.title}» بكل نسخه ولوحاته ونصوصه؟`)) return;
  msProjects = msProjects.filter(x => x.id !== id);
  msSave(); renderMsProjects();
}

function msBackToProjects() {
  document.getElementById('msProjectView').hidden = true;
  document.getElementById('msProjectsView').hidden = false;
  msWb = null;
  renderMsProjects();
}

// ---------- عرض المشروع والنسخ ----------
function msOpenProject(id) {
  const p = msProject(id);
  if (!p) return;
  document.getElementById('msProjectsView').hidden = true;
  const view = document.getElementById('msProjectView');
  view.hidden = false;
  view.dataset.projectId = id;
  document.getElementById('msProjectHead').innerHTML = `
    <h3 class="ms-proj-title">📜 ${msEsc(p.title)}</h3>
    ${p.author ? `<div class="ms-proj-author">${msEsc(p.author)}</div>` : ''}
    ${p.desc ? `<p class="ms-proj-desc">${msEsc(p.desc)}</p>` : ''}`;
  renderMsCopies();
  renderMsCollation();
  renderMsAgents();
  renderMsAuthor();
  renderMsMonitor();
  msRenderIndexes();
  const introEl = document.getElementById('msIntroText');
  if (introEl) introEl.value = p.intro || '';
}

function renderMsCopies() {
  const view = document.getElementById('msProjectView');
  const p = msProject(view.dataset.projectId);
  const wrap = document.getElementById('msCopiesList');
  if (!p || !wrap) return;
  const copies = p.copies || [];
  if (!copies.length) {
    wrap.innerHTML = '<div class="ms-empty">لا نسخ بعد. أضف النسخة الأولى (النسخة الأم إن وجدت) وارفع صور لوحاتها.</div>';
    return;
  }
  wrap.innerHTML = copies.map(c => {
    const pr = msFolioProgress(c);
    const meta = [c.library, c.shelfmark ? `رقم ${c.shelfmark}` : '', c.scribe, c.date, c.script].filter(Boolean).join(' · ');
    const base = msBaseCopy(p);
    const isBase = base && base.id === c.id;
    return `<div class="ms-copy-card">
      <div class="ms-copy-head">
        <strong>نسخة (${msEsc(c.siglum)})</strong>
        ${isBase ? '<span class="ms-badge">الأم</span>' : `<button type="button" class="ms-btn" onclick="msSetBaseCopy('${c.id}')">اجعلها الأم</button>`}
        ${meta ? `<span class="ms-copy-meta">${msEsc(meta)}</span>` : ''}
        <span class="ms-copy-progress">${pr.total} لوحة · ✔ ${pr.approved} معتمدة</span>
        <span class="ms-copy-actions">
          <label class="ms-btn ms-btn-primary ms-upload-label">⬆ رفع لوحات
            <input type="file" accept="image/*" multiple hidden onchange="msUploadFolios('${p.id}','${c.id}',this)">
          </label>
          <button type="button" class="ms-btn ms-btn-danger" onclick="msDeleteCopy('${p.id}','${c.id}')">حذف النسخة</button>
        </span>
      </div>
      ${c.notes ? `<div class="ms-copy-notes">${msEsc(c.notes)}</div>` : ''}
      <div class="ms-folios-grid">
        ${(c.folios || []).map(f => `
          <div class="ms-folio ${f.status === 'approved' ? 'is-approved' : (f.status === 'draft' ? 'is-draft' : '')}" onclick="msOpenFolio('${p.id}','${c.id}','${f.id}')">
            <img src="${msEsc(f.file_url)}" alt="${msEsc(f.label)}" loading="lazy">
            <div class="ms-folio-label">${msEsc(f.label)} ${f.status === 'approved' ? '✔' : (f.status === 'draft' ? '✎' : '')}</div>
          </div>`).join('') || '<div class="ms-empty">لا لوحات بعد في هذه النسخة.</div>'}
      </div>
    </div>`;
  }).join('');
}

function msAddCopy() {
  const view = document.getElementById('msProjectView');
  const p = msProject(view.dataset.projectId);
  if (!p) return;
  const siglum = document.getElementById('msCopySiglum').value.trim();
  if (!siglum) { msToast('اكتب رمز النسخة أولًا (أ، ب...)'); return; }
  p.copies = p.copies || [];
  if (p.copies.some(c => c.siglum === siglum)) { msToast(`الرمز (${siglum}) مستعمل لنسخة أخرى — الترميز يقتضي رمزًا واحدًا لكل نسخة`); return; }
  p.copies.push({
    id: msUid(), siglum,
    library: document.getElementById('msCopyLibrary').value.trim(),
    shelfmark: document.getElementById('msCopyShelf').value.trim(),
    scribe: document.getElementById('msCopyScribe').value.trim(),
    date: document.getElementById('msCopyDate').value.trim(),
    script: document.getElementById('msCopyScript').value.trim(),
    notes: document.getElementById('msCopyNotes').value.trim(),
    folios: [],
  });
  ['msCopySiglum', 'msCopyLibrary', 'msCopyShelf', 'msCopyScribe', 'msCopyDate', 'msCopyScript', 'msCopyNotes']
    .forEach(i => { document.getElementById(i).value = ''; });
  msSave(); renderMsCopies(); renderMsCollation();
}

function msDeleteCopy(pid, cid) {
  const p = msProject(pid);
  const c = msCopy(p, cid);
  if (!c || !confirm(`حذف نسخة (${c.siglum}) بكل لوحاتها ونصوصها؟`)) return;
  p.copies = p.copies.filter(x => x.id !== cid);
  if (p.baseCopyId === cid) p.baseCopyId = '';
  msSave(); renderMsCopies(); renderMsCollation();
  document.getElementById('msWorkbench').hidden = true;
  msWb = null;
}

async function msUploadFolios(pid, cid, input) {
  const p = msProject(pid);
  const c = msCopy(p, cid);
  const files = Array.from(input.files || []);
  input.value = '';
  if (!c || !files.length) return;
  msToast(`جارٍ رفع ${files.length} لوحة إلى البوكت...`);
  for (const file of files) {
    try {
      const form = new FormData();
      form.append('file', file);
      const resp = await fetch('/api/chat/upload', { method: 'POST', body: form });
      const data = await resp.json().catch(() => ({}));
      if (!data.success) throw new Error(data.detail || data.error || 'فشل الرفع');
      const pos = (c.folios || []).length;
      const num = Math.floor(pos / 2) + 1;
      const side = pos % 2 === 0 ? 'و' : 'ظ';
      c.folios = c.folios || [];
      c.folios.push({
        id: msUid(), label: `${num}${side}`, name: data.filename,
        file_url: data.file_url, file_path: data.file_path,
        status: 'pending', text: '', primary_text: '', checker_text: '',
        disputes: [], agreement: null,
      });
    } catch (e) {
      msToast(`❌ فشل رفع «${file.name}»: ${e.message}`, 5000);
    }
  }
  msSave(); renderMsCopies();
  msToast('اكتمل رفع اللوحات. اضغط أي لوحة لبدء نسخها.');
}

// ---------- المرحلة ٢: المقابلة بين النسخ بهامش مستقل ----------
function msBaseCopy(p) {
  const copies = (p && p.copies) || [];
  if (!copies.length) return null;
  return copies.find(c => c.id === p.baseCopyId) || copies[0];
}

function msCurrentProject() {
  const view = document.getElementById('msProjectView');
  return view ? msProject(view.dataset.projectId) : null;
}

function msSetBaseCopy(cid) {
  const p = msCurrentProject();
  if (!p) return;
  p.baseCopyId = cid;
  msSave(); renderMsCopies(); renderMsCollation();
  const c = msCopy(p, cid);
  msToast(`صارت نسخة (${c ? c.siglum : ''}) هي النسخة الأم للمقابلة`);
}

function msApparatusText(e) {
  if (e.custom_apparatus) return e.custom_apparatus;
  const s = `(${e.siglum})`;
  const ctx = e.context ? ` بعد «${e.context}»` : '';
  switch (e.type) {
    case 'سقط': return `سقط من ${s}: «${e.base}»${ctx}`;
    case 'زيادة': return `في ${s} زيادة: «${e.other}»${ctx}`;
    case 'تبديل': return `في ${s}: «${e.other}» بدل «${e.base}»`;
    case 'ضبط/رسم': return `في ${s} ضبطًا/رسمًا: «${e.other}» بدل «${e.base}»`;
    case 'متعذر في النسخة': return `في ${s} موضع متعذر القراءة مقابل «${e.base}»`;
    case 'الأم متعذرة هنا': return `الأم متعذرة هنا، وفي ${s}: «${e.other}»`;
    case 'بياض/مفقود': return `اللوحة غير موجودة في ${s} (بياض/مفقودة)`;
    default: return `${e.type} ${s}: «${e.other || e.base}»`;
  }
}

function renderMsCollation() {
  const p = msCurrentProject();
  const sel = document.getElementById('msBaseCopy');
  if (!p || !sel) return;
  const copies = p.copies || [];
  const base = msBaseCopy(p);
  sel.innerHTML = copies.map(c =>
    `<option value="${c.id}"${base && c.id === base.id ? ' selected' : ''}>(${msEsc(c.siglum)})${c.library ? ' — ' + msEsc(c.library) : ''}</option>`).join('');
  const sigla = document.getElementById('msSiglaList');
  sigla.innerHTML = copies.length
    ? '<strong>رموز النسخ:</strong> ' + copies.map(c =>
        `(${msEsc(c.siglum)}) = ${msEsc([c.library, c.shelfmark ? 'رقم ' + c.shelfmark : '', c.date].filter(Boolean).join('، ') || 'بدون بيانات')}${base && c.id === base.id ? ' — الأم' : ''}`).join(' · ')
    : '';
  const col = p.collation || { entries: [] };
  const entries = col.entries || [];
  const pending = entries.filter(e => e.status === 'pending');
  const accepted = entries.filter(e => e.status === 'accepted');
  document.getElementById('msCollateInfo').textContent =
    entries.length ? `آخر مقابلة: ${col.at ? new Date(col.at).toLocaleString('ar') : ''} · ${entries.length} فرقًا (${accepted.length} معتمد في الهامش، ${pending.length} بانتظار الحسم)` : 'لم تُجرَ مقابلة بعد';
  const res = document.getElementById('msCollateResults');
  if (!pending.length) {
    res.innerHTML = entries.length ? '<div class="ms-disputes-none">لا فروق بانتظار الحسم.</div>' : '';
  } else {
    const byFolio = {};
    pending.forEach(e => { (byFolio[e.folio] = byFolio[e.folio] || []).push(e); });
    res.innerHTML = `<div class="ms-disputes-title">فروق بانتظار حسم المحقق (${pending.length}) — «اعتماد» يدخلها هامش المقابلة:</div>` +
      Object.keys(byFolio).map(folio => `
        <div class="ms-collate-folio">
          <div class="ms-collate-folio-title">لوحة (${msEsc(folio)})</div>
          ${byFolio[folio].map(e => `
            <div class="ms-dispute">
              <span class="ms-dispute-a">${msEsc(msApparatusText(e))}</span>
              <span>
                <button type="button" class="ms-dispute-btn" onclick="msCollEntry('${e.id}','accepted')">اعتماد في الهامش</button>
                <button type="button" class="ms-dispute-btn ms-rec-btn" onclick="msOpenRecommend('${e.id}')">🧠 توصية Wonder</button>
                <button type="button" class="ms-dispute-dismiss" onclick="msCollEntry('${e.id}','dismissed')">تجاهل</button>
              </span>
            </div>`).join('')}
        </div>`).join('');
  }
  const mc = document.getElementById('msMarginCollation');
  mc.innerHTML = accepted.length
    ? accepted.map(e => `<div class="ms-margin-entry"><strong>(${msEsc(e.folio)})</strong> ${msEsc(msApparatusText(e))}
        <button type="button" class="ms-dispute-dismiss ms-rec-btn" onclick="msOpenRecommend('${e.id}')" title="طلب توصية Muse Wonder لهذا الموضع">🧠</button>
        <button type="button" class="ms-dispute-dismiss" onclick="msCollEntry('${e.id}','pending')" title="إخراج من الهامش">↩</button></div>`).join('')
    : '<div class="ms-disputes-none">فارغ — اعتمد فروقًا من قائمة المقابلة فتظهر هنا.</div>';
  const me = document.getElementById('msMarginEd');
  const edNotes = [];
  if (base) (base.folios || []).forEach(f => { if ((f.ed_note || '').trim()) edNotes.push({ folio: f.label, text: f.ed_note.trim() }); });
  me.innerHTML = edNotes.length
    ? edNotes.map(n => `<div class="ms-margin-entry"><strong>(${msEsc(n.folio)})</strong> ${msEsc(n.text)}</div>`).join('')
    : '<div class="ms-disputes-none">فارغ — اكتب تعليق التحقيق من منضدة اللوحة (أسفل نصها).</div>';
}

async function msRunCollation() {
  const p = msCurrentProject();
  if (!p) return;
  const base = msBaseCopy(p);
  if (!base) { msToast('أضف نسخة أولًا'); return; }
  const others = (p.copies || []).filter(c => c.id !== base.id);
  if (!others.length) { msToast('المقابلة تحتاج نسخة أخرى على الأقل غير الأم'); return; }
  const baseFolios = (base.folios || []).filter(f => (f.text || '').trim());
  if (!baseFolios.length) { msToast('لا نص منسوخ في لوحات الأم بعد — انسخها واعتمدها أولًا'); return; }
  const items = [];
  baseFolios.forEach(bf => {
    others.forEach(oc => {
      const of = (oc.folios || []).find(x => x.label === bf.label);
      items.push({ folio: bf.label, siglum: oc.siglum, base_text: bf.text || '',
                   other_text: of ? (of.text || '') : null });
    });
  });
  const btn = document.getElementById('msCollateBtn');
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = '⏳ جارٍ مقابلة النسخ...';
  try {
    const res = await fetch('/api/manuscripts/collate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذرت المقابلة');
    p.collation = {
      at: new Date().toISOString(), baseCopyId: base.id,
      entries: (data.entries || []).map(e => ({ ...e, id: msUid(), status: 'pending' })),
    };
    msSave(); renderMsCollation();
    const missing = (data.entries || []).filter(e => e.type === 'بياض/مفقود').length;
    msToast(`تمت المقابلة: ${data.count} فرقًا بانتظار حسمك${missing ? ` (منها ${missing} لوحة مفقودة في نسخ أخرى)` : ''}. الفروق وحدها لا تدخل الهامش حتى تعتمدها.`, 6000);
  } catch (e) {
    msToast('❌ ' + e.message, 7000);
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

function msCollEntry(id, status) {
  const p = msCurrentProject();
  if (!p || !p.collation) return;
  const e = (p.collation.entries || []).find(x => x.id === id);
  if (!e) return;
  e.status = status;
  msSave(); renderMsCollation();
  if (msWb) msRenderWbState();
}

// ---------- مسح أسلوب المؤلف: الأكثر استخدامًا في كتبه ----------
function msOpenStyleBook(bookId, part, page, highlight) {
  if (typeof openBookReader !== 'function') { msToast('قارئ الكتب غير متاح في هذه الصفحة'); return; }
  openBookReader({ book_id: bookId || '', part: part || '', page_num: page ? parseInt(page, 10) : null, highlight: highlight || '' });
}

function msRenderStyle(data) {
  const results = data.results || [];
  if (!results.length) return '<div class="ms-disputes-none">لا عبارات للمسح.</div>';
  const maxTotal = Math.max(...results.map(r => r.total || 0));
  return `<div class="ms-disputes-title">مسح أسلوب المؤلف عبر ${(data.books || []).length} كتابًا — الأكثر استخدامًا عنده يُعلَّم ⭐:</div>` +
    results.map(r => `
      <div class="ms-style-row ${r.total && r.total === maxTotal ? 'ms-style-dom' : ''}">
        <span class="ms-style-phrase">«${msEsc(r.phrase)}»</span>
        — <span class="ms-style-total">${r.total || 0} موضعًا متصلًا</span> في ${(r.occurrences || []).length} كتابًا
        ${r.total && r.total === maxTotal ? '<span class="ms-style-dom-badge">⭐ الأكثر استخدامًا لدى المؤلف</span>' : ''}
        <div>${(r.occurrences || []).map(o => `
          <span class="ms-occ-chip">${msEsc(o.book)} (${o.count} متصل · ج ${msEsc(o.part || '—')} ص ${msEsc(o.page || '—')})
            <button type="button" class="ms-occ-open" title="تصفح الشاهد مظلَّلًا في الكتاب" onclick="msOpenStyleBook(${Number(o.book_id) || 0}, '${msEsc(o.part || '')}', ${Number(o.page) || 0}, '${msEsc(r.phrase)}')">📖</button>
          </span>${o.snippet ? `<div class="ms-occ-snippet">الشاهد: …${msEsc(o.snippet)}…</div>` : ''}`).join('')}</div>
      </div>`).join('');
}

async function msRunStyleScan(phrases, containerId, infoId) {
  const p = msCurrentProject();
  if (!p) return null;
  const box = document.getElementById(containerId);
  if (infoId) document.getElementById(infoId).textContent = '⏳ جارٍ إحصاء العبارات في كل كتب المؤلف...';
  if (box) box.innerHTML = '<div class="ms-rec-loading">⏳ نمسح كتب المؤلف كلها ونعدّ المواضع...</div>';
  try {
    const res = await fetch('/api/manuscripts/author-style', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ author: p.author, title: p.title, phrases }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر مسح الأسلوب');
    if (box) box.innerHTML = msRenderStyle(data);
    if (infoId) document.getElementById(infoId).textContent =
      data.dominant ? `الأكثر استخدامًا عند المؤلف: «${data.dominant}»` : 'لم تظهر العبارات في كتبه الأخرى';
    return data;
  } catch (e) {
    if (box) box.innerHTML = `<div class="ms-rec-loading">❌ ${msEsc(e.message)}</div>`;
    if (infoId) document.getElementById(infoId).textContent = '';
    return null;
  }
}

async function msAuthorStyleScan() {
  const p = msCurrentProject();
  if (!p || !MS_REC) return;
  const e = (p.collation.entries || []).find(x => x.id === MS_REC.entryId);
  if (!e || !e.base || !e.other) { msToast('هذا الموضع بلا قراءتين متنافستين للمسح'); return; }
  const base = msBaseCopy(p);
  const bf = base ? (base.folios || []).find(x => x.label === e.folio) : null;
  const phrases = [];
  const add = s => { s = (s || '').replace(/\s+/g, ' ').trim(); if (s && s.split(' ').length >= 2 && !phrases.includes(s) && phrases.length < 6) phrases.push(s); };
  if (bf && bf.text && bf.text.includes(e.base)) {
    const words = bf.text.split(/\s+/).filter(Boolean);
    const bw = e.base.split(/\s+/).filter(Boolean);
    const ow = e.other.split(/\s+/).filter(Boolean);
    let si = -1;
    for (let i = 0; i + bw.length <= words.length; i++) {
      if (words.slice(i, i + bw.length).join(' ') === e.base) { si = i; break; }
    }
    if (si >= 0) {
      const ei = si + bw.length - 1;
      const win = (from, to, repl) => {
        const seg = words.slice(from, to + 1);
        if (repl) seg.splice(si - from, bw.length, ...ow);
        return seg.join(' ');
      };
      add(win(si - 1, ei, false)); add(win(si - 1, ei, true));
      add(win(si, ei + 1, false)); add(win(si, ei + 1, true));
      add(win(si - 1, ei + 1, false)); add(win(si - 1, ei + 1, true));
    }
  }
  const btn = document.getElementById('msRecStyleBtn');
  btn.disabled = true;
  const data = await msRunStyleScan(phrases, 'msRecStyle', null);
  btn.disabled = false;
  if (data) MS_REC.style = data;
}

async function msAuthorStyleManual() {
  const phrases = document.getElementById('msStylePhrases').value.split('\n').map(s => s.trim()).filter(Boolean).slice(0, 6);
  if (phrases.length < 1) { msToast('ضع عبارة واحدة على الأقل (كل عبارة في سطر)'); return; }
  await msRunStyleScan(phrases, 'msStyleResult', 'msStyleInfo');
}

// ---------- نافذة توصية Muse Wonder لكل موضع ----------
let MS_REC = null; // {entryId, data}
const MS_REC_ACTIONS = {
  keep_base_note: ['keep_note', 'إثبات الأم + إثبات الفرق في الهامش'],
  keep_base_drop: ['keep_drop', 'إثبات الأم + تجاهل الفرق'],
  adopt_other: ['adopt_other', 'اعتماد قراءة الأخرى في المتن + الهامش'],
  needs_image: ['comment_only', 'تعليق الموضع لعين المحقق على الصورة'],
};

async function msOpenRecommend(id) {
  const p = msCurrentProject();
  if (!p || !p.collation) return;
  const e = (p.collation.entries || []).find(x => x.id === id);
  if (!e) return;
  MS_REC = { entryId: id, data: null };
  const modal = document.getElementById('msRecModal');
  modal.hidden = false;
  document.getElementById('msRecActions').hidden = true;
  document.getElementById('msRecComment').value = '';
  document.getElementById('msRecPos').innerHTML =
    `<strong>لوحة (${msEsc(e.folio)}) — ${msEsc(e.type)} مع نسخة (${msEsc(e.siglum)})</strong><br>` +
    `في الأم: «${msEsc(e.base || '—')}» · في الأخرى: «${msEsc(e.other || '—')}»` +
    (e.rec && e.rec.decision ? `<br><em>حسم سابق: ${msEsc(e.rec.decision)}${e.rec.option ? ' — ' + msEsc(e.rec.option) : ''}</em>` : '');
  const body = document.getElementById('msRecBody');
  body.innerHTML = '<div class="ms-rec-loading">⏳ Muse Wonder يدرس الموضع وقراءتيه وسياقه...</div>';
  // مقطع اللوحة حول الموضع من نص الأم
  const base = msBaseCopy(p);
  const bf = base ? (base.folios || []).find(x => x.label === e.folio) : null;
  let excerpt = '';
  if (bf && bf.text) {
    const anchor = (e.context && bf.text.includes(e.context)) ? e.context : (e.base || '');
    const idx = anchor ? bf.text.indexOf(anchor) : -1;
    excerpt = idx >= 0 ? bf.text.slice(Math.max(0, idx - 700), idx + 900) : bf.text.slice(0, 1500);
  }
  try {
    const res = await fetch('/api/manuscripts/recommend', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: p.title, author: p.author, folio: e.folio, type: e.type,
        base: e.base, other: e.other, siglum: e.siglum, context: e.context, excerpt,
        api_key: msApiKey() }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذرت التوصية');
    MS_REC.data = data;
    const [opt, label] = MS_REC_ACTIONS[data.action] || MS_REC_ACTIONS.needs_image;
    body.innerHTML = `
      <div class="ms-rec-title">التوصية: ${msEsc(data.recommendation || '')}<span class="ms-rec-action">${msEsc(label)}</span></div>
      ${(data.reasons || []).length ? `<ul class="ms-rec-reasons">${data.reasons.map(r => `<li>${msEsc(r)}</li>`).join('')}</ul>` : ''}
      ${data.margin_note ? `<div class="ms-rec-margin"><strong>صياغة الهامش المقترحة:</strong> ${msEsc(data.margin_note)}</div>` : ''}`;
    const radio = document.querySelector(`input[name="msRecOption"][value="${opt}"]`);
    if (radio) radio.checked = true;
    document.getElementById('msRecMeta').textContent =
      `${(data.model || 'meta/muse-wonder')} · ثقة ${data.confidence ?? '—'}٪ · ${data.seconds ?? '—'}ث · $${Number(data.cost || 0).toFixed(4)} — التوصية استشارة، والقرار لك.`;
    document.getElementById('msRecActions').hidden = false;
  } catch (err) {
    body.innerHTML = `<div class="ms-rec-loading">❌ ${msEsc(err.message)}</div>`;
  }
}

function msRecClose() {
  document.getElementById('msRecModal').hidden = true;
  MS_REC = null;
}

function msRecSelectedOption() {
  const r = document.querySelector('input[name="msRecOption"]:checked');
  return r ? r.value : 'keep_note';
}

function msRecIgnore() {
  const p = msCurrentProject();
  if (p && MS_REC) {
    const e = (p.collation.entries || []).find(x => x.id === MS_REC.entryId);
    if (e) {
      e.rec = { decision: 'ignored', at: new Date().toISOString(),
                action: MS_REC.data ? MS_REC.data.action : '', model: MS_REC.data ? MS_REC.data.model : '' };
      msSave();
    }
  }
  msRecClose();
  msToast('تجاهلتَ التوصية — بقي الموضع على حاله');
}

function msRecApply(kind) {
  const p = msCurrentProject();
  if (!p || !MS_REC || !MS_REC.data) return;
  const e = (p.collation.entries || []).find(x => x.id === MS_REC.entryId);
  if (!e) return;
  const data = MS_REC.data;
  const [recOpt] = MS_REC_ACTIONS[data.action] || MS_REC_ACTIONS.needs_image;
  const option = kind === 'recommended' ? recOpt : msRecSelectedOption();
  const comment = document.getElementById('msRecComment').value.trim();
  const useNote = document.getElementById('msRecUseNote').checked;
  const base = msBaseCopy(p);
  const bf = base ? (base.folios || []).find(x => x.label === e.folio) : null;
  let corrected = false;
  if (option === 'keep_note' || option === 'adopt_other') {
    e.status = 'accepted';
    if (useNote && data.margin_note) e.custom_apparatus = data.margin_note;
  } else if (option === 'keep_drop') {
    e.status = 'dismissed';
  }
  if (option === 'adopt_other' && bf && e.base && e.other && (bf.text || '').includes(e.base)) {
    bf.text = bf.text.replace(e.base, e.other);
    if (bf._view === 'audited' || !bf._view) bf.audited_text = bf.text;
    corrected = true;
  }
  if (comment && bf) {
    const line = `[تعليق المحقق على موضع ({e.folio}) — {${e.type}} مع (${e.siglum})] ${comment}`;
    bf.ed_note = ((bf.ed_note || '').trim() ? bf.ed_note.trim() + '\n' : '') + line;
  }
  e.rec = { decision: kind === 'recommended' ? 'اعتمد توصية Wonder' : 'طبق خياره مع/دون تعليق',
            option, at: new Date().toISOString(), action: data.action,
            model: data.model, confidence: data.confidence,
            style: MS_REC.style ? { dominant: MS_REC.style.dominant,
              totals: (MS_REC.style.results || []).map(r => ({ phrase: r.phrase, total: r.total })) } : undefined };
  msSave(); renderMsCollation();
  if (msWb) { msRenderWbState(); const ta = document.getElementById('msWbText'); const ctx = msWbFolio(); if (ta && ctx && ctx.folio && ctx.folio.id === (bf && bf.id)) ta.value = ctx.folio.text || ta.value; }
  msRecClose();
  msToast(option === 'adopt_other'
    ? (corrected ? '✔ اعتمدت قراءة الأخرى في المتن وأُثبت الفرق في الهامش' : '⚠️ أُثبت الفرق في الهامش، لكن عبارة الأم لم توجد حرفيًا في النص — صحّح المتن يدويًا من منضدة اللوحة')
    : option === 'keep_drop' ? '✔ أُثبتت الأم وتجاهلنا الفرق'
    : option === 'comment_only' ? '✔ حُفظ تعليقك في هامش التحقيق وبقي الفرق معلقًا'
    : '✔ اعتمدت التوصية وأُثبت الفرق في هامش المقابلة', 6000);
}

function msToggleCollatedText() {
  const box = document.getElementById('msCollatedText');
  if (!box) return;
  if (!box.hidden) { box.hidden = true; return; }
  const p = msCurrentProject();
  const base = p ? msBaseCopy(p) : null;
  if (!p || !base) { msToast('لا نسخة أم بعد'); return; }
  const accepted = ((p.collation || {}).entries || []).filter(e => e.status === 'accepted');
  const folios = (base.folios || []).filter(f => (f.text || '').trim());
  if (!folios.length) { msToast('لا نص في لوحات الأم بعد'); return; }
  box.innerHTML = folios.map(f => {
    const app = accepted.filter(e => e.folio === f.label);
    return `<div class="ms-collated-folio">
      <div class="ms-collate-folio-title">لوحة (${msEsc(f.label)}) — (${msEsc(base.siglum)})</div>
      <div class="ms-collated-text">${msEsc(f.text)}</div>
      ${app.length ? `<div class="ms-collated-app"><strong>هامش المقابلة:</strong>${app.map((e, i) => `<div>${i + 1}. ${msEsc(msApparatusText(e))}</div>`).join('')}</div>` : ''}
      ${(f.ed_note || '').trim() ? `<div class="ms-collated-app"><strong>هامش التحقيق:</strong><div>${msEsc(f.ed_note)}</div></div>` : ''}
    </div>`;
  }).join('');
  box.hidden = false;
  box.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ---------- منضدة اللوحة ----------
function msOpenFolio(pid, cid, fid) {
  const p = msProject(pid);
  const c = msCopy(p, cid);
  const f = msFolio(c, fid);
  if (!f) return;
  msWb = { projectId: pid, copyId: cid, folioId: fid };
  const wb = document.getElementById('msWorkbench');
  wb.hidden = false;
  document.getElementById('msWbTitle').textContent = `لوحة (${f.label}) — نسخة (${c.siglum}) من «${p.title}»`;
  document.getElementById('msWbImg').src = f.file_url;
  if (typeof msImgReset === 'function') msImgReset();
  const ta = document.getElementById('msWbText');
  ta.value = f.text || f.audited_text || f.primary_text || '';
  const ed = document.getElementById('msWbEdNote');
  if (ed) ed.value = f.ed_note || '';
  msRenderWbState();
  wb.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function msWbFolio() {
  if (!msWb) return null;
  const p = msProject(msWb.projectId);
  const c = msCopy(p, msWb.copyId);
  return { project: p, copy: c, folio: msFolio(c, msWb.folioId) };
}

function msRenderWbState() {
  const ctx = msWbFolio();
  if (!ctx || !ctx.folio) return;
  const f = ctx.folio;
  const statusEl = document.getElementById('msWbStatus');
  statusEl.textContent = f.status === 'approved' ? '✔ معتمدة' : (f.status === 'draft' ? '✎ مسودة نسخ' : 'لم تُنسخ بعد');
  const meta = [];
  if (f.model_primary) meta.push(`القارئ الأول: ${f.model_primary}${f.primary_seconds != null ? ` (${f.primary_seconds}ث)` : ''}`);
  if (f.model_checker) meta.push(`القارئ الثاني: ${f.model_checker}${f.checker_seconds != null ? ` (${f.checker_seconds}ث)` : ''}`);
  if (f.model_auditor) meta.push(`المدقق: ${f.model_auditor}${f.auditor_seconds != null ? ` (${f.auditor_seconds}ث)` : ''}`);
  if (f.agreement != null) meta.push(`اتفاق القارئين حرفيًا: ${f.agreement}٪`);
  if (f.cost != null) meta.push(`كلفة النسخ والتدقيق: $${Number(f.cost).toFixed(4)}`);
  document.getElementById('msWbMeta').textContent = meta.join(' · ');
  const notesEl = document.getElementById('msWbAuditNotes');
  if (notesEl) {
    if (f.audit_notes) {
      notesEl.hidden = false;
      notesEl.innerHTML = `<strong>تنبيهات المدقق:</strong> ${msEsc(f.audit_notes)}`;
    } else {
      notesEl.hidden = true;
      notesEl.innerHTML = '';
    }
  }
  document.querySelectorAll('.ms-view-btn').forEach(b => {
    b.classList.toggle('ms-view-active', b.dataset.msView === (f._view || 'audited'));
  });
  // هامش المقابلة المعتمد لهذه اللوحة (من قسم المقابلة بالمشروع)
  const margin = document.getElementById('msWbFolioMargin');
  if (margin && ctx.project) {
    const p = ctx.project;
    const base = msBaseCopy(p);
    const isBase = base && ctx.copy && base.id === ctx.copy.id;
    const accepted = (((p.collation || {}).entries) || [])
      .filter(e => e.status === 'accepted' && e.folio === f.label && (isBase || e.siglum === (ctx.copy || {}).siglum));
    if (accepted.length) {
      margin.hidden = false;
      margin.innerHTML = `<strong>هامش المقابلة — لوحة (${msEsc(f.label)}):</strong>` +
        accepted.map(e => `<div>${msEsc(msApparatusText(e))}</div>`).join('');
    } else {
      margin.hidden = true;
      margin.innerHTML = '';
    }
  }
  msRenderDisputes();
}

function msRenderDisputes() {
  const ctx = msWbFolio();
  const wrap = document.getElementById('msWbDisputes');
  if (!ctx || !ctx.folio || !wrap) return;
  const disputes = ctx.folio.disputes || [];
  if (!disputes.length) {
    wrap.innerHTML = ctx.folio.checker_text
      ? '<div class="ms-disputes-none">لا مواضع اختلاف متبقية بين النموذجين في هذه اللوحة.</div>'
      : '';
    return;
  }
  wrap.innerHTML = `<div class="ms-disputes-title">مواضع اختلاف النموذجين (${disputes.length}) — اضغط قراءة المدقق لاعتمادها في النص، أو عدّل النص يدويًا:</div>` +
    disputes.map((d, i) => {
      // عجز المدقق عن موضع ([غير مقروء] وحدها) ليس قراءة بديلة: تنبيه شك
      // يُراجع على الصورة، ولا يُعرض زر يستبدل به النص المقروء خطأً.
      const checkerBlank = !d.b || !d.b.replace(/\[غير مقروء\]/g, '').trim();
      if (checkerBlank) {
        return `<div class="ms-dispute ms-dispute-warn">
          <span class="ms-dispute-a">الأساسي: ${msEsc(d.a) || '∅'}</span>
          <span class="ms-dispute-flag">⚠️ المدقق عجز عن قراءة هذا الموضع — راجعه على الصورة</span>
          <button type="button" class="ms-dispute-dismiss" onclick="msDismissDispute(${i})" title="أبقِ قراءة الأساسي وأزل التنبيه">إبقاء الأساسي ✔</button>
        </div>`;
      }
      return `<div class="ms-dispute">
        <span class="ms-dispute-a">الأساسي: ${msEsc(d.a) || '∅'}</span>
        <button type="button" class="ms-dispute-btn" onclick="msPickDispute(${i})" title="اعتماد قراءة المدقق">المدقق: ${msEsc(d.b) || '∅'}</button>
      </div>`;
    }).join('');
}

function msDismissDispute(i) {
  const ctx = msWbFolio();
  if (!ctx || !ctx.folio) return;
  ctx.folio.disputes.splice(i, 1);
  msSave(); msRenderDisputes();
}

function msPickDispute(i) {
  const ctx = msWbFolio();
  if (!ctx || !ctx.folio) return;
  const f = ctx.folio;
  const d = (f.disputes || [])[i];
  if (!d) return;
  const ta = document.getElementById('msWbText');
  if (d.a && ta.value.includes(d.a)) {
    ta.value = ta.value.replace(d.a, d.b);
  } else if (!d.a && d.b) {
    ta.value = (ta.value + ' ' + d.b).trim();
  } else {
    msToast('لم يُعثر على عبارة الأساسي في النص الحالي (ربما عدّلتها) — صحّح يدويًا');
    return;
  }
  f.text = ta.value;
  f.disputes.splice(i, 1);
  msSave(); msRenderDisputes();
}

function msShowText(view) {
  const ctx = msWbFolio();
  if (!ctx || !ctx.folio) return;
  const f = ctx.folio;
  const ta = document.getElementById('msWbText');
  // احفظ تحرير المحقق الحالي قبل التنقل بين النسخ حتى لا يضيع
  if (f._view === 'audited' || !f._view) f.text = ta.value;
  f._view = view;
  ta.value = view === 'audited' ? (f.text || f.audited_text || '')
    : (view === 'primary' ? (f.primary_text || '') : (f.checker_text || ''));
  document.querySelectorAll('.ms-view-btn').forEach(b => {
    b.classList.toggle('ms-view-active', b.dataset.msView === view);
  });
}

async function msTranscribeFolio() {
  const ctx = msWbFolio();
  if (!ctx || !ctx.folio) return;
  const f = ctx.folio;
  const btn = document.getElementById('msWbTranscribeBtn');
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = '⏳ جارٍ نسخ اللوحة بالنموذجين...';
  try {
    let apiKey = '';
    try {
      const keys = (typeof readProviderKeys === 'function') ? readProviderKeys() : {};
      apiKey = keys.openrouter || '';
    } catch (e) { /* مفتاح الخادم */ }
    const choice = msModelChoice();
    const res = await fetch('/api/manuscripts/transcribe', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_path: f.file_path, api_key: apiKey,
        primary_model: choice.primary, checker_model: choice.checker,
        auditor_model: choice.auditor,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر النسخ');
    const primary = data.primary || {};
    const checker = data.checker || {};
    const auditor = data.auditor || {};
    if (primary.error && checker.error) throw new Error(primary.error);
    if (!primary.text && !checker.text) throw new Error((primary.error || checker.error || 'لم يرجع القارئان نصًا'));
    f.primary_text = primary.text || '';
    f.checker_text = checker.text || '';
    f.audited_text = auditor.text || '';
    f.audit_notes = auditor.notes || '';
    f.model_primary = primary.model || msModels.primary;
    f.model_checker = checker.model || msModels.checker;
    f.model_auditor = auditor.model || choice.auditor;
    f.primary_seconds = primary.seconds;
    f.checker_seconds = checker.seconds;
    f.auditor_seconds = auditor.seconds;
    f.cost = (Number(primary.cost) || 0) + (Number(checker.cost) || 0) + (Number(auditor.cost) || 0);
    f.disputes = data.disputes || [];
    f.agreement = data.agreement;
    f._view = 'audited';
    f.text = f.audited_text || f.primary_text;
    f.status = 'draft';
    document.getElementById('msWbText').value = f.text;
    msSave(); msRenderWbState(); renderMsCopies();
    if (primary.truncated || checker.truncated) {
      msToast('⚠️ خط هذه اللوحة صعب: قُصّت مخرجات أحد النموذجين (حلقة تكرار). راجع النص على الصورة سطرًا سطرًا قبل الاعتماد.', 8000);
    } else {
      msToast(`تم النسخ. اتفاق النموذجين ${f.agreement}٪ — حسم مواضع الاختلاف ثم اعتمد اللوحة.`, 5000);
    }
  } catch (e) {
    msToast('❌ ' + e.message, 7000);
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

function msApproveFolio() {
  const ctx = msWbFolio();
  if (!ctx || !ctx.folio) return;
  const f = ctx.folio;
  f.text = document.getElementById('msWbText').value;
  if (!f.text.trim()) { msToast('النص فارغ — انسخ اللوحة أو اكتب نصها أولًا'); return; }
  f.status = 'approved';
  msSave(); msRenderWbState(); renderMsCopies();
  msToast(`✔ اعتُمدت لوحة (${f.label})`);
}

function msCloseWorkbench() {
  const ctx = msWbFolio();
  if (ctx && ctx.folio) {
    ctx.folio.text = document.getElementById('msWbText').value;
    if (ctx.folio.status !== 'approved' && ctx.folio.text.trim()) ctx.folio.status = 'draft';
    msSave(); renderMsCopies(); renderMsCollation();
  }
  document.getElementById('msWorkbench').hidden = true;
  msWb = null;
}

// ---------- المرحلة ٣: فريق وكلاء التحقيق ----------
const MS_AGENT_KINDS = { takhrij: 'تخريج', tarjama: 'ترجمة علم', lugha: 'لغة', dabt: 'ضبط/تصحيف', author: 'وكيل المؤلف' };

function msVerifyBadge(v) {
  if (!v) return '';
  const map = { verified: ['✔ موثّق', '#2e7d5b'], found: ['◐ وُجد بلا مطابقة تامة', '#8a6414'],
                not_found: ['✘ لم يُعثر عليه', '#b03a2e'], unchecked: ['؟ يحتاج توثيقًا', '#777'] };
  const [label, color] = map[v.status] || map.unchecked;
  return `<span style="color:${color};font-weight:700">${label}</span>${v.detail ? ` — ${msEsc(v.detail)}` : ''}`;
}

function renderMsAgents() {
  const p = msCurrentProject();
  const list = document.getElementById('msAgentsList');
  if (!p || !list) return;
  const sugs = p.agent_suggestions || [];
  const pending = sugs.filter(s => s.status === 'pending' && s.kind !== 'author');
  const accepted = sugs.filter(s => s.status === 'accepted');
  document.getElementById('msAgentsInfo').textContent =
    sugs.length ? `${sugs.length} اقتراحًا (${accepted.length} في هامش التحقيق، ${pending.length} بانتظار الحسم)` : 'لم تُشغَّل الوكلاء بعد';
  if (!pending.length) {
    list.innerHTML = sugs.length ? '<div class="ms-disputes-none">لا اقتراحات بانتظار الحسم.</div>' : '';
    return;
  }
  const byFolio = {};
  pending.forEach(s => { (byFolio[s.folio] = byFolio[s.folio] || []).push(s); });
  list.innerHTML = `<div class="ms-disputes-title">اقتراحات بانتظار حسم المحقق (${pending.length}) — الاعتماد يُلحقها بهامش تحقيق اللوحة:</div>` +
    Object.keys(byFolio).map(folio => `
      <div class="ms-collate-folio">
        <div class="ms-collate-folio-title">لوحة (${msEsc(folio)})</div>
        ${byFolio[folio].map(s => `
          <div class="ms-dispute">
            <span class="ms-dispute-a"><strong>[${msEsc(MS_AGENT_KINDS[s.kind] || s.kind)}]</strong> «${msEsc(s.anchor)}» — ${msEsc(s.body)}${s.source ? `<br>المصدر المقترح: ${msEsc(s.source)}` : ''}<br>${msVerifyBadge(s.verify)}</span>
            <span>
              <button type="button" class="ms-dispute-btn" onclick="msAgentDecision('${s.id}','accepted')">اعتماد في الهامش</button>
              <button type="button" class="ms-dispute-dismiss" onclick="msAgentDecision('${s.id}','dismissed')">رفض</button>
            </span>
          </div>`).join('')}
      </div>`).join('');
}

async function msRunAgents() {
  const p = msCurrentProject();
  if (!p) return;
  const base = msBaseCopy(p);
  if (!base) { msToast('لا نسخة أم بعد'); return; }
  const folios = (base.folios || []).filter(f => (f.text || '').trim());
  if (!folios.length) { msToast('لا نص في لوحات الأم — انسخها أولًا'); return; }
  const model = document.getElementById('msAgentModel').value;
  let apiKey = '';
  try { const keys = (typeof readProviderKeys === 'function') ? readProviderKeys() : {}; apiKey = keys.openrouter || ''; } catch (e) {}
  const btn = document.getElementById('msAgentsBtn');
  btn.disabled = true;
  const old = btn.textContent;
  p.agent_suggestions = p.agent_suggestions || [];
  let totalCost = 0, totalNew = 0;
  try {
    for (const f of folios) {
      btn.textContent = `⏳ الوكلاء على لوحة (${f.label})...`;
      const res = await fetch('/api/manuscripts/agents', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: f.text, title: p.title, author: p.author, model, api_key: apiKey }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'تعذر تشغيل الوكلاء');
      totalCost += Number(data.cost) || 0;
      (data.suggestions || []).forEach(s => {
        p.agent_suggestions.push({ ...s, id: msUid(), folio: f.label, status: 'pending' });
        totalNew++;
      });
      msSave(); renderMsAgents();
    }
    msToast(`أنهى الوكلاء: ${totalNew} اقتراحًا جديدًا على ${folios.length} لوحة (كلفة $${totalCost.toFixed(4)}). راجِع التوثيق قبل الاعتماد.`, 7000);
  } catch (e) {
    msToast('❌ ' + e.message, 7000);
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

function msAgentDecision(id, status) {
  const p = msCurrentProject();
  if (!p) return;
  const s = (p.agent_suggestions || []).find(x => x.id === id);
  if (!s) return;
  s.status = status;
  if (status === 'accepted') {
    const base = msBaseCopy(p);
    const f = base ? (base.folios || []).find(x => x.label === s.folio) : null;
    if (f) {
      const line = `[${MS_AGENT_KINDS[s.kind] || s.kind}] «${s.anchor}» — ${s.body}${s.source ? ` (${s.source})` : ''}${s.verify && s.verify.detail ? ` [توثيق: ${s.verify.detail}]` : ''}`;
      f.ed_note = ((f.ed_note || '').trim() ? f.ed_note.trim() + '\n' : '') + line;
    }
  }
  msSave(); renderMsAgents(); renderMsAuthor(); renderMsCollation();
}

// ---------- وكيل المؤلف المتخصص ----------
function msApiKey() {
  try { const keys = (typeof readProviderKeys === 'function') ? readProviderKeys() : {}; return keys.openrouter || ''; } catch (e) { return ''; }
}

async function msShowAuthorBooks() {
  const p = msCurrentProject();
  if (!p) return;
  const box = document.getElementById('msAuthorBooks');
  box.textContent = '⏳ جارٍ جمع كتب المؤلف من المكتبة...';
  try {
    const res = await fetch('/api/manuscripts/author-books?author=' + encodeURIComponent(p.author || ''));
    const data = await res.json().catch(() => ({}));
    const books = data.books || [];
    box.innerHTML = books.length
      ? `<strong>كتب «${msEsc(p.author || '')}» عندنا (${books.length}):</strong> ` + books.map(b => `<span class="ms-book-chip">${msEsc(b.title)}</span>`).join('')
      : 'لم يُعثر على كتب لهذا المؤلف في الفهرس — تأكد من اسم المؤلف في بيانات المشروع.';
  } catch (e) { box.textContent = 'تعذر جلب الكتب'; }
}

function renderMsAuthor() {
  const p = msCurrentProject();
  const list = document.getElementById('msAuthorList');
  const info = document.getElementById('msAuthorInfo');
  if (!p || !list) return;
  const sugs = (p.agent_suggestions || []).filter(s => s.kind === 'author');
  const pending = sugs.filter(s => s.status === 'pending');
  const accepted = sugs.filter(s => s.status === 'accepted');
  if (info) info.textContent = sugs.length ? `${accepted.length} موازاة في الهامش، ${pending.length} بانتظار الحسم` : 'لم يُعرَض النص على كتب المؤلف بعد';
  if (!pending.length) { list.innerHTML = sugs.length ? '<div class="ms-disputes-none">لا موازيات بانتظار الحسم.</div>' : ''; return; }
  const byFolio = {};
  pending.forEach(s => { (byFolio[s.folio] = byFolio[s.folio] || []).push(s); });
  list.innerHTML = `<div class="ms-disputes-title">موازيات وجدها وكيل المؤلف في سائر كتبه (${pending.length}):</div>` +
    Object.keys(byFolio).map(folio => `
      <div class="ms-collate-folio">
        <div class="ms-collate-folio-title">لوحة (${msEsc(folio)})</div>
        ${byFolio[folio].map(s => `
          <div class="ms-dispute">
            <span class="ms-dispute-a"><strong>[وكيل المؤلف]</strong> «${msEsc(s.anchor)}» — ${msEsc(s.body)}${s.source ? `<br>المواضع: ${msEsc(s.source)}` : ''}${(s.parallels || []).length ? `<br>تصفح المواضع: ${s.parallels.map(x => `<span class="ms-occ-chip">${msEsc(x.book)} ص ${msEsc(x.page || '—')}<button type="button" class="ms-occ-open" title="تصفح الموضع في الكتاب" onclick="msOpenStyleBook(${Number(x.book_id) || 0}, '${msEsc(x.part || '')}', ${Number(x.page) || 0}, '${msEsc(s.anchor)}')">📖</button></span>`).join('')}` : ''}<br>${msVerifyBadge(s.verify)}</span>
            <span>
              <button type="button" class="ms-dispute-btn" onclick="msAgentDecision('${s.id}','accepted')">اعتماد في الهامش</button>
              <button type="button" class="ms-dispute-dismiss" onclick="msAgentDecision('${s.id}','dismissed')">رفض</button>
            </span>
          </div>`).join('')}
      </div>`).join('');
}

async function msRunAuthor() {
  const p = msCurrentProject();
  if (!p) return;
  const base = msBaseCopy(p);
  if (!base) { msToast('لا نسخة أم بعد'); return; }
  if (!(p.author || '').trim()) { msToast('أضف اسم المؤلف في بيانات المشروع أولًا'); return; }
  const folios = (base.folios || []).filter(f => (f.text || '').trim());
  if (!folios.length) { msToast('لا نص في لوحات الأم — انسخها أولًا'); return; }
  const model = document.getElementById('msAuthorModel').value;
  const btn = document.getElementById('msAuthorBtn');
  btn.disabled = true;
  const old = btn.textContent;
  p.agent_suggestions = p.agent_suggestions || [];
  let totalCost = 0, totalNew = 0, booksSeen = 0;
  try {
    for (const f of folios) {
      btn.textContent = `⏳ وكيل المؤلف على لوحة (${f.label})...`;
      const res = await fetch('/api/manuscripts/author-agent', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: f.text, title: p.title, author: p.author, model, api_key: msApiKey() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'تعذر وكيل المؤلف');
      booksSeen = (data.books || []).length;
      totalCost += Number(data.cost) || 0;
      (data.suggestions || []).forEach(s => {
        p.agent_suggestions.push({ ...s, id: msUid(), folio: f.label, status: 'pending' });
        totalNew++;
      });
      msSave(); renderMsAuthor();
    }
    msToast(`وكيل المؤلف: فحص ${booksSeen} كتابًا للمؤلف فوجد ${totalNew} موازاة موثّقة (كلفة المقارنة $${totalCost.toFixed(4)}). حسمها في بطاقته.`, 8000);
  } catch (e) {
    msToast('❌ ' + e.message, 7000);
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

// ---------- وكيل المراقبة والتدقيق ----------
function msMonitorContext(p, phase) {
  const lines = [`المشروع: ${p.title} — المؤلف: ${p.author || '—'}`];
  const want = (...names) => phase === 'شاملة' || names.includes(phase);
  if (want('النسخ')) {
    lines.push('\n== نصوص اللوحات وحالة النسخ ==');
    (p.copies || []).forEach(c => (c.folios || []).forEach(f => {
      if ((f.text || '').trim()) lines.push(`[${c.siglum} ${f.label}] حالة:${f.status} اتفاق قارئين:${f.agreement ?? '—'}٪ مواضع اختلاف محفوظة:${(f.disputes || []).length}\n${(f.text || '').slice(0, 800)}`);
    }));
  }
  if (want('المقابلة')) {
    const es = (p.collation || {}).entries || [];
    lines.push(`\n== المقابلة: ${es.length} فرقًا ==`);
    es.slice(0, 70).forEach(e => lines.push(`[${e.folio}/${e.siglum}/${e.type}/${e.status}] الأم:«${e.base}» الأخرى:«${e.other}» سياق:«${(e.context || '').slice(0, 100)}»`));
  }
  if (want('وكلاء التحقيق')) {
    const ss = p.agent_suggestions || [];
    lines.push(`\n== اقتراحات الوكلاء: ${ss.length} ==`);
    ss.slice(0, 70).forEach(s => lines.push(`[${s.kind}/${s.folio}/${s.status}/توثيق:${(s.verify || {}).status || '—'}] «${s.anchor}» — ${s.title || ''}: ${s.body || ''}`));
  }
  return lines.join('\n').slice(0, 55000);
}

async function msRunMonitor() {
  const p = msCurrentProject();
  if (!p) return;
  const phase = document.getElementById('msMonitorPhase').value;
  const model = document.getElementById('msMonitorModel').value;
  const btn = document.getElementById('msMonitorBtn');
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = '⏳ وكيل المراقبة يراجع... قد يستغرق دقيقة';
  try {
    const res = await fetch('/api/manuscripts/monitor', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase, context: msMonitorContext(p, phase), model, api_key: msApiKey() }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر وكيل المراقبة');
    p.monitor_log = p.monitor_log || [];
    p.monitor_log.unshift({ id: msUid(), phase, at: new Date().toISOString(), model: data.model || model,
      findings: data.findings || [], status: 'open', cost: data.cost || 0, seconds: data.seconds || 0 });
    msSave(); renderMsMonitor();
    msToast(`دوّن وكيل المراقبة ${(data.findings || []).length} ملاحظة في سجل المشروع (كلفة $${Number(data.cost || 0).toFixed(4)}، ${data.seconds || '—'}ث). راجعها وعالج ما يلزم.`, 8000);
  } catch (e) {
    msToast('❌ ' + e.message, 8000);
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

function renderMsMonitor() {
  const p = msCurrentProject();
  const box = document.getElementById('msMonitorLog');
  const info = document.getElementById('msMonitorInfo');
  if (!p || !box) return;
  const log = p.monitor_log || [];
  if (info) info.textContent = log.length ? `${log.length} جلسة تدقيق في السجل` : 'لا تدقيق بعد';
  if (!log.length) { box.innerHTML = ''; return; }
  const sevLabel = { high: 'عالية', med: 'متوسطة', low: 'خفيفة' };
  box.innerHTML = log.map(e => `
    <div class="ms-monitor-entry ${e.status === 'done' ? 'ms-mon-done' : ''}">
      <div class="ms-monitor-head">
        <strong>تدقيق مرحلة: ${msEsc(e.phase)}</strong>
        <span>${msEsc((e.model || '').split('/').pop() || '')}</span>
        <span>${msEsc((e.at || '').slice(0, 16).replace('T', ' '))}</span>
        <span>${(e.findings || []).length} ملاحظة — $${Number(e.cost || 0).toFixed(4)}</span>
        <button type="button" class="ms-dispute-dismiss" onclick="msMonitorToggle('${e.id}')">${e.status === 'done' ? '↩ إعادة فتح' : '✔ عولجت/اطّلعت'}</button>
      </div>
      ${(e.findings || []).map(f => `
        <div class="ms-finding"><span class="ms-sev-${msEsc(f.severity || 'low')}">${sevLabel[f.severity] || 'خفيفة'}</span>
        <strong>${msEsc(f.area || '')}</strong> — ${msEsc(f.note || '')}${f.evidence ? `<div class="ms-finding-ev">الدليل: ${msEsc(f.evidence)}</div>` : ''}</div>`).join('')}
    </div>`).join('');
}

function msMonitorToggle(id) {
  const p = msCurrentProject();
  if (!p) return;
  const e = (p.monitor_log || []).find(x => x.id === id);
  if (!e) return;
  e.status = e.status === 'done' ? 'open' : 'done';
  msSave(); renderMsMonitor();
}

// ---------- أدوات رسم اللوحة ومعالجتها ----------
const MS_IMG = { zoom: 100, mode: null, cropBlob: null, drawing: false, startPt: null, lastPt: null };

function msImgEl() { return document.getElementById('msWbImg'); }
function msOvEl() { return document.getElementById('msWbOverlay'); }
function msImgFilterCss() {
  const c = document.getElementById('msImgContrast').value;
  const s = document.getElementById('msImgSat').value;
  const b = document.getElementById('msImgBright').value;
  let f = `contrast(${c}%) saturate(${s}%) brightness(${b}%)`;
  if (document.getElementById('msImgSharpen').checked) f += ' url(#msSharpenFilter)';
  return f;
}
function msSyncOverlay() {
  const img = msImgEl(), ov = msOvEl();
  if (!img || !ov || !img.clientWidth) return;
  ov.style.left = img.offsetLeft + 'px';
  ov.style.top = img.offsetTop + 'px';
  ov.style.width = img.clientWidth + 'px';
  ov.style.height = img.clientHeight + 'px';
  if (ov.width !== img.clientWidth || ov.height !== img.clientHeight) {
    ov.width = img.clientWidth; ov.height = img.clientHeight;
  }
}
function msApplyImgFilters() {
  const img = msImgEl();
  if (!img) return;
  img.style.filter = msImgFilterCss();
  img.style.width = MS_IMG.zoom + '%';
  document.getElementById('msZoomVal').textContent = MS_IMG.zoom + '%';
  requestAnimationFrame(msSyncOverlay);
}
function msImgZoom(d) {
  MS_IMG.zoom = Math.min(400, Math.max(50, MS_IMG.zoom + d));
  msApplyImgFilters();
}
function msImgSetMode(mode) {
  MS_IMG.mode = MS_IMG.mode === mode ? null : mode;
  document.getElementById('msWbStage').classList.toggle('ms-mode-active', !!MS_IMG.mode);
  document.getElementById('msImgCropBtn').classList.toggle('ms-mode-on', MS_IMG.mode === 'crop');
  document.getElementById('msImgPenBtn').classList.toggle('ms-mode-on', MS_IMG.mode === 'pen');
  if (MS_IMG.mode) msToast(MS_IMG.mode === 'crop' ? 'اسحب على الصورة لتحديد الجزء الصعب' : 'ارسم بالقلم على الصورة لتعليم المواضع الصعبة', 4000);
}
function msImgClearDraw() {
  const ov = msOvEl();
  if (ov) ov.getContext('2d').clearRect(0, 0, ov.width, ov.height);
}
function msImgReset() {
  MS_IMG.zoom = 100; MS_IMG.mode = null; MS_IMG.cropBlob = null;
  ['msImgContrast', 'msImgSat', 'msImgBright'].forEach(id => { const el = document.getElementById(id); if (el) el.value = 100; });
  const sh = document.getElementById('msImgSharpen'); if (sh) sh.checked = false;
  const box = document.getElementById('msCropBox'); if (box) box.hidden = true;
  const res = document.getElementById('msCropResult'); if (res) res.value = '';
  const stage = document.getElementById('msWbStage'); if (stage) stage.classList.remove('ms-mode-active');
  msImgClearDraw();
  msApplyImgFilters();
}
function msOvPos(e) {
  const ov = msOvEl();
  const r = ov.getBoundingClientRect();
  return { x: (e.clientX - r.left) * (ov.width / r.width), y: (e.clientY - r.top) * (ov.height / r.height) };
}
function msSharpenCanvas(cv) {
  const ctx = cv.getContext('2d');
  const w = cv.width, h = cv.height;
  if (!w || !h || w * h > 9000000) return;
  const src = ctx.getImageData(0, 0, w, h);
  const out = ctx.createImageData(w, h);
  const d = src.data, o = out.data;
  const k = [0, -1, 0, -1, 5, -1, 0, -1, 0];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = (y * w + x) * 4;
    if (x === 0 || y === 0 || x === w - 1 || y === h - 1) { o[i] = d[i]; o[i + 1] = d[i + 1]; o[i + 2] = d[i + 2]; o[i + 3] = d[i + 3]; continue; }
    for (let ch = 0; ch < 3; ch++) {
      let v = 0, ki = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) v += d[((y + dy) * w + (x + dx)) * 4 + ch] * k[ki++];
      o[i + ch] = Math.max(0, Math.min(255, v));
    }
    o[i + 3] = d[i + 3];
  }
  ctx.putImageData(out, 0, 0);
}
function msDoCrop(rect) {
  const img = msImgEl();
  if (!img || !img.naturalWidth) return;
  const sx = img.naturalWidth / img.clientWidth, sy = img.naturalHeight / img.clientHeight;
  // تُحفظ القصاصة مكبّرة بحسب تكبير الباحث الحالي حتى يرى النموذج
  // الحروف أكبر وأوضح مما في أصل الصورة الصغيرة.
  const scale = Math.min(5, Math.max(2, Math.round(MS_IMG.zoom / 50)));
  MS_IMG.cropScale = scale;
  const cv = document.createElement('canvas');
  cv.width = Math.max(2, Math.round(rect.w * sx * scale));
  cv.height = Math.max(2, Math.round(rect.h * sy * scale));
  const ctx = cv.getContext('2d');
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  const c = document.getElementById('msImgContrast').value / 100;
  const s = document.getElementById('msImgSat').value / 100;
  const b = document.getElementById('msImgBright').value / 100;
  try { ctx.filter = `contrast(${c}) saturate(${s}) brightness(${b})`; } catch (e) { /* متصفح قديم */ }
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.drawImage(img, rect.x * sx, rect.y * sy, rect.w * sx, rect.h * sy, 0, 0, cv.width, cv.height);
  try { ctx.filter = 'none'; } catch (e) {}
  if (document.getElementById('msImgSharpen').checked) msSharpenCanvas(cv);
  cv.toBlob(blob => {
    MS_IMG.cropBlob = blob;
    document.getElementById('msCropPreview').src = URL.createObjectURL(blob);
    document.getElementById('msCropBox').hidden = false;
    document.getElementById('msCropResult').value = '';
    document.getElementById('msCropReadMeta').textContent = '';
    const si = document.getElementById('msCropScaleInfo');
    if (si) si.textContent = `أُبقيت القصاصة مكبرة ×${scale} (تكبيرك الحالي ${MS_IMG.zoom}٪) ليراها النموذج أوضح`;
    msLoadCropModels();
    msImgSetMode(MS_IMG.mode);
    msImgClearDraw();
    msToast('قُصّ الجزء بالمعالجة الحالية ومكبرًا — اختر نموذج القراءة ثم أعد نسخه');
  }, 'image/png');
}
function msOvInit() {
  const ov = msOvEl();
  if (!ov || ov.dataset.msInit) return;
  ov.dataset.msInit = '1';
  ov.addEventListener('pointerdown', e => {
    if (!MS_IMG.mode) return;
    MS_IMG.drawing = true;
    MS_IMG.startPt = msOvPos(e);
    MS_IMG.lastPt = MS_IMG.startPt;
    ov.setPointerCapture(e.pointerId);
  });
  ov.addEventListener('pointermove', e => {
    if (!MS_IMG.drawing || !MS_IMG.mode) return;
    const ctx = ov.getContext('2d');
    const pt = msOvPos(e);
    if (MS_IMG.mode === 'pen') {
      ctx.strokeStyle = 'rgba(200,30,30,.85)';
      ctx.lineWidth = Math.max(2, ov.width / 260);
      ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(MS_IMG.lastPt.x, MS_IMG.lastPt.y); ctx.lineTo(pt.x, pt.y); ctx.stroke();
    } else if (MS_IMG.mode === 'crop') {
      ctx.clearRect(0, 0, ov.width, ov.height);
      ctx.strokeStyle = '#b4552d'; ctx.lineWidth = 2; ctx.setLineDash([8, 5]);
      ctx.strokeRect(MS_IMG.startPt.x, MS_IMG.startPt.y, pt.x - MS_IMG.startPt.x, pt.y - MS_IMG.startPt.y);
      ctx.setLineDash([]);
    }
    MS_IMG.lastPt = pt;
  });
  ov.addEventListener('pointerup', e => {
    if (!MS_IMG.drawing) return;
    MS_IMG.drawing = false;
    if (MS_IMG.mode === 'crop' && MS_IMG.startPt) {
      const pt = msOvPos(e);
      const rect = { x: Math.min(MS_IMG.startPt.x, pt.x), y: Math.min(MS_IMG.startPt.y, pt.y),
                     w: Math.abs(pt.x - MS_IMG.startPt.x), h: Math.abs(pt.y - MS_IMG.startPt.y) };
      if (rect.w > 12 && rect.h > 12) msDoCrop(rect); else msImgClearDraw();
    }
    MS_IMG.startPt = null;
  });
}
let MS_CROP_MODELS_LOADED = false;
async function msLoadCropModels() {
  const sel = document.getElementById('msCropModel');
  if (!sel || MS_CROP_MODELS_LOADED) return;
  MS_CROP_MODELS_LOADED = true;
  try {
    const res = await fetch('/api/manuscripts/models');
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر جلب النماذج');
    const vision = (data.models || []).filter(m => m.vision);
    const textOnly = (data.models || []).filter(m => !m.vision);
    const mk = m => `<option value="${msEsc(m.id)}">${msEsc(m.name)} — ${msEsc(m.id)}</option>`;
    sel.innerHTML = '<option value="">الثلاثي الحالي (قارئان + مدقق)</option>' +
      `<optgroup label="نماذج ترى الصور (${vision.length})">${vision.map(mk).join('')}</optgroup>` +
      `<optgroup label="نماذج نصية — غالبًا لا تقرأ الصور (${textOnly.length})">${textOnly.map(mk).join('')}</optgroup>`;
  } catch (e) {
    MS_CROP_MODELS_LOADED = false;
  }
}
function msCropModelInfo() {
  const sel = document.getElementById('msCropModel');
  const meta = document.getElementById('msCropReadMeta');
  if (meta && sel) meta.textContent = sel.value ? `سيقرأ الجزء: ${sel.value}` : 'سيقرأ بالثلاثي الحالي';
}

async function msRetranscribeCrop() {
  if (!MS_IMG.cropBlob) { msToast('اصنع قصًا أولًا بوضع القصّ'); return; }
  const btn = document.getElementById('msCropTranscribeBtn');
  btn.disabled = true;
  const old = btn.textContent;
  const model = document.getElementById('msCropModel').value;
  btn.textContent = model ? `⏳ جارٍ رفع الجزء وقراءته بـ ${model}...` : '⏳ جارٍ رفع الجزء ونسخه بالثلاثي...';
  try {
    const fd = new FormData();
    fd.append('file', MS_IMG.cropBlob, 'ms-crop.png');
    const up = await fetch('/api/chat/upload', { method: 'POST', body: fd });
    const upData = await up.json().catch(() => ({}));
    if (!up.ok || !upData.file_path) throw new Error(upData.detail || 'تعذر رفع الجزء');
    let txt = '', meta = '';
    if (model) {
      const res = await fetch('/api/manuscripts/transcribe-one', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: upData.file_path, model, api_key: msApiKey() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'تعذر قراءة النموذج');
      txt = data.text || '';
      meta = `قرأها: ${data.model || model} · ${data.seconds ?? '—'}ث · $${Number(data.cost || 0).toFixed(4)} · قصاصة مكبرة ×${MS_IMG.cropScale || 1}`;
    } else {
      const choice = msModelChoice();
      const res = await fetch('/api/manuscripts/transcribe', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: upData.file_path, api_key: msApiKey(),
          primary_model: choice.primary, checker_model: choice.checker, auditor_model: choice.auditor }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'تعذر نسخ الجزء');
      const aud = data.auditor || {};
      const pri = data.primary || {};
      txt = aud.text || pri.text || '';
      meta = `قرأها الثلاثي: أول ${pri.model || ''} · ثانٍ ${(data.checker || {}).model || ''} · مدقق ${aud.model || ''} · قصاصة مكبرة ×${MS_IMG.cropScale || 1}`;
    }
    if (!txt) throw new Error('لم يرجع النموذج قراءة للجزء');
    document.getElementById('msCropResult').value = txt;
    document.getElementById('msCropReadMeta').textContent = meta;
    msToast('قُرئ الجزء المعالج — قارنه بعينك على الصورة قبل إلحاقه', 6000);
  } catch (e) {
    msToast('❌ ' + e.message, 7000);
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}
function msAppendCropResult() {
  const txt = document.getElementById('msCropResult').value.trim();
  if (!txt) { msToast('لا قراءة في صندوق الجزء بعد'); return; }
  const ta = document.getElementById('msWbText');
  ta.value = (ta.value.trim() ? ta.value.trim() + '\n' : '') + txt;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  msToast('أُلحقت قراءة الجزء بنص اللوحة — راجع موضع الإلحاق وحرّره');
}
function msDownloadBlob(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
function msDownloadCrop() {
  if (!MS_IMG.cropBlob) { msToast('لا جزء مقصوص بعد'); return; }
  msDownloadBlob(MS_IMG.cropBlob, 'جزء-معالج.png');
}
function msDownloadAnnotated() {
  const img = msImgEl(), ov = msOvEl();
  if (!img || !img.clientWidth) return;
  const cv = document.createElement('canvas');
  cv.width = img.clientWidth; cv.height = img.clientHeight;
  const ctx = cv.getContext('2d');
  const c = document.getElementById('msImgContrast').value / 100;
  const s = document.getElementById('msImgSat').value / 100;
  const b = document.getElementById('msImgBright').value / 100;
  try { ctx.filter = `contrast(${c}) saturate(${s}) brightness(${b})`; } catch (e) {}
  ctx.drawImage(img, 0, 0, cv.width, cv.height);
  try { ctx.filter = 'none'; } catch (e) {}
  ctx.drawImage(ov, 0, 0);
  cv.toBlob(blob => msDownloadBlob(blob, 'لقطة-مشروحة.png'), 'image/png');
}
document.addEventListener('DOMContentLoaded', () => {
  const img = msImgEl();
  if (img) img.addEventListener('load', () => { msSyncOverlay(); msOvInit(); });
  window.addEventListener('resize', msSyncOverlay);
});

// ---------- المرحلة ٤: الفهارس والمقدمة والإخراج ----------
function msIndexGroups(p) {
  const accepted = (p.agent_suggestions || []).filter(s => s.status === 'accepted');
  const groups = { 'الآيات القرآنية': [], 'الأحاديث والأقوال': [], 'الأعلام': [], 'اللغة والضبط': [], 'موازيات المؤلف': [], 'مصادر التحقيق': [] };
  const sources = new Set();
  accepted.forEach(s => {
    const item = `«${s.anchor}» — لوحة (${s.folio})`;
    if (s.kind === 'takhrij' && s.surah) groups['الآيات القرآنية'].push(item);
    else if (s.kind === 'takhrij') groups['الأحاديث والأقوال'].push(item);
    else if (s.kind === 'tarjama') groups['الأعلام'].push(item);
    else if (s.kind === 'author') groups['موازيات المؤلف'].push(`${item} — ${s.body}`);
    else groups['اللغة والضبط'].push(item);
    if (s.source) sources.add(s.source);
    if (s.verify && s.verify.status === 'verified') sources.add(s.verify.detail);
  });
  groups['مصادر التحقيق'] = [...sources];
  return groups;
}

function msBuildIndexes() {
  const p = msCurrentProject();
  if (!p) return;
  const accepted = (p.agent_suggestions || []).filter(s => s.status === 'accepted');
  if (!accepted.length) { msToast('لا اقتراحات معتمدة بعد — شغّل الوكلاء واعتمد اقتراحات أولًا'); return; }
  p.indexes = { at: new Date().toISOString(), groups: msIndexGroups(p) };
  msSave(); msRenderIndexes();
  msToast('وُلّدت الفهارس من الاقتراحات المعتمدة');
}

function msRenderIndexes() {
  const p = msCurrentProject();
  const box = document.getElementById('msIndexesBox');
  if (!p || !box) return;
  const groups = (p.indexes || {}).groups;
  if (!groups) { box.innerHTML = ''; return; }
  box.innerHTML = Object.keys(groups).map(name => `
    <div class="ms-collate-folio">
      <div class="ms-collate-folio-title">فهرس ${msEsc(name)} (${groups[name].length})</div>
      ${groups[name].length ? groups[name].map(i => `<div class="ms-margin-entry">${msEsc(i)}</div>`).join('') : '<div class="ms-disputes-none">—</div>'}
    </div>`).join('');
}

function msGenIntro() {
  const p = msCurrentProject();
  if (!p) return;
  const base = msBaseCopy(p);
  const copies = p.copies || [];
  const acceptedCount = ((base || {}).folios || []).filter(f => f.status === 'approved').length;
  const colAcc = ((p.collation || {}).entries || []).filter(e => e.status === 'accepted').length;
  const sigla = copies.map(c => `(${c.siglum}): ${[c.library, c.shelfmark ? 'رقم الحفظ ' + c.shelfmark : '', c.scribe ? 'ناسخها ' + c.scribe : '', c.date ? 'تاريخها ' + c.date : '', c.script ? 'خطها ' + c.script : ''].filter(Boolean).join('، ')}${base && c.id === base.id ? ' — وهي النسخة الأم المعتمدة أصلًا للنص' : ''}`).join('\n');
  p.intro = `مقدمة المحقق
الحمد لله رب العالمين، والصلاة والسلام على سيدنا محمد وعلى آله وصحبه أجمعين، أما بعد:

أولًا: موضوع الكتاب وأهميته
هذا تحقيق لكتاب «${p.title}»${p.author ? ` من تأليف ${p.author}` : ''}. [يُستكمل: فن الكتاب وموضوعه ومنزلته ومصنفاته وشروحه وطبعاته السابقة وما امتاز به هذا التحقيق.]

ثانيًا: ترجمة المؤلف
[تُستكمل من كتب التراجم: اسمه ونسبه ومولده وشيوخه وتلاميذه ومصنفاته ووفاته، موثّقة بمصادرها.]

ثالثًا: وصف النسخ المعتمدة ورموزها
اعتمدت في هذا التحقيق ${copies.length} نسخ:
${sigla}

رابعًا: منهج التحقيق
نُسخت اللوحات بنماذج رؤية متعددة (قارئان مستقلان ومدقق يقابلهما على الصورة) واعتمد المحقق نص كل لوحة بعينه، ثم قوبلت النسخ على النسخة الأم ولوحاتها المرقمة، وصُنّفت الفروق (سقط/زيادة/تبديل/ضبط/رسم/بياض) في «هامش مقابلة» مستقل لا يدخله فرق إلا باعتماد المحقق. وخُرّجت الآيات والأحاديث والأشعار وتراجم الأعلام في «هامش تحقيق» مستقل، مع توثيق آلي من مكتبة الشاملة وتمييز ما ثبت بما لم يثبت. وحالة اللوحات المعتمدة حتى توليد هذه المسودة: ${acceptedCount} معتمدة من أصل ${((base || {}).folios || []).length} في الأم، وفروق مقابلة معتمدة: ${colAcc}. [يُستكمل: رموز الأقواس والاصطلاحات وطريقة ضبط النص.]`;
  const ta = document.getElementById('msIntroText');
  if (ta) ta.value = p.intro;
  msSave();
  msToast('وُلّدت مسودة مقدمة المحقق — راجعها وحرّر مواضع [الاستكمال]');
}

function msDocStructure(p) {
  const base = msBaseCopy(p);
  const sections = [];
  sections.push({ h: `تحقيق «${p.title}»`, level: 'title' });
  if (p.author) sections.push({ h: p.author, level: 'meta' });
  if ((p.intro || '').trim()) {
    sections.push({ h: 'مقدمة المحقق', level: 'h' });
    p.intro.split('\n').forEach(l => sections.push({ h: l, level: 'p' }));
  }
  const accepted = ((p.collation || {}).entries || []).filter(e => e.status === 'accepted');
  ((base || {}).folios || []).filter(f => (f.text || '').trim()).forEach(f => {
    sections.push({ h: `لوحة (${f.label}) — نسخة (${base.siglum})`, level: 'h' });
    f.text.split('\n').forEach(l => { if (l.trim()) sections.push({ h: l, level: 'p' }); });
    const app = accepted.filter(e => e.folio === f.label);
    if (app.length) {
      sections.push({ h: 'هامش المقابلة', level: 'h' });
      app.forEach((e, i) => sections.push({ h: `${i + 1}. ${msApparatusText(e)}`, level: 'p' }));
    }
    if ((f.ed_note || '').trim()) {
      sections.push({ h: 'هامش التحقيق', level: 'h' });
      f.ed_note.split('\n').forEach(l => { if (l.trim()) sections.push({ h: l, level: 'p' }); });
    }
  });
  const groups = (p.indexes || {}).groups;
  if (groups) {
    sections.push({ h: 'الفهارس', level: 'h' });
    Object.keys(groups).forEach(name => {
      sections.push({ h: `فهرس ${name}`, level: 'h' });
      groups[name].forEach(i => sections.push({ h: i, level: 'p' }));
    });
  }
  return sections;
}

function msDownloadBlob(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 800);
}

async function msExportDocx() {
  const p = msCurrentProject();
  if (!p) return;
  const sections = msDocStructure(p);
  const blocks = sections.map(s => ({
    kind: s.level === 'title' ? 'title' : (s.level === 'meta' ? 'meta' : (s.level === 'h' ? 'h' : 'p')),
    runs: [{ t: s.h }],
  }));
  document.getElementById('msExportInfo').textContent = 'جارٍ توليد Word...';
  try {
    const res = await fetch('/api/projects/export-docx', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: p.title, styles: {}, blocks, footnotes: [] }),
    });
    if (!res.ok) throw new Error('فشل توليد الملف');
    msDownloadBlob(await res.blob(), `${p.title}.docx`);
    document.getElementById('msExportInfo').textContent = 'نُزّل ملف Word بالنص والهامشين والفهارس';
  } catch (e) {
    document.getElementById('msExportInfo').textContent = '❌ ' + e.message;
  }
}

async function msExportPdf() {
  const p = msCurrentProject();
  if (!p) return;
  const sections = msDocStructure(p);
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const html = `<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><style>
    body{font-family:'Amiri',serif;font-size:15px;line-height:2;margin:36px;color:#222}
    h1{text-align:center;font-size:24px} .meta{text-align:center;color:#555} h2{font-size:18px;margin-top:26px;border-bottom:1px solid #ccc;padding-bottom:4px}
    p{margin:4px 0;text-align:justify}</style></head><body>` +
    sections.map(s => s.level === 'title' ? `<h1>${esc(s.h)}</h1>`
      : s.level === 'meta' ? `<div class="meta">${esc(s.h)}</div>`
      : s.level === 'h' ? `<h2>${esc(s.h)}</h2>` : `<p>${esc(s.h)}</p>`).join('') +
    '</body></html>';
  document.getElementById('msExportInfo').textContent = 'جارٍ توليد PDF...';
  try {
    const res = await fetch('/api/projects/export-pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: p.title, html }),
    });
    if (!res.ok) throw new Error('فشل توليد PDF');
    msDownloadBlob(await res.blob(), `${p.title}.pdf`);
    document.getElementById('msExportInfo').textContent = 'نُزّل ملف PDF بالنص والهامشين والفهارس';
  } catch (e) {
    document.getElementById('msExportInfo').textContent = '❌ ' + e.message;
  }
}

document.addEventListener('input', (e) => {
  if (e.target && e.target.id === 'msIntroText') {
    const p = msCurrentProject();
    if (p) { p.intro = e.target.value; msSave(); }
    return;
  }
  if (e.target && e.target.id === 'msWbEdNote' && msWb) {
    const ctx = msWbFolio();
    if (ctx && ctx.folio) { ctx.folio.ed_note = e.target.value; msSave(); }
    return;
  }
  if (e.target && e.target.id === 'msWbText' && msWb) {
    const ctx = msWbFolio();
    if (ctx && ctx.folio) {
      const f = ctx.folio;
      if (f._view === 'primary') f.primary_text = e.target.value;
      else if (f._view === 'checker') f.checker_text = e.target.value;
      else f.text = e.target.value;
      msSave();
    }
  }
});
