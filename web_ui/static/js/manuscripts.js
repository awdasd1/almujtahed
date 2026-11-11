// =============================================================================
// تحقيق المخطوطات — المرحلة ١: مشاريع ونسخ ولوحات، ونسخ اللوحة بنموذجين
// (أساسي سريع + مدقق متحفظ) مع جدول مواضع اختلافهما ليحسمها المحقق،
// فلا يُعتمد نص إلا بقراره. الحفظ خادمي فوري في كل خطوة.
// =============================================================================
let msProjects = [];
let msModels = { primary: '', checker: '' };
// قياس م٠ الموسع (اللوحة السودانية): Gemini 2.5 Pro أقدر الخطوط الصعبة،
// وQwen3-VL ثانيه بجزء يسير من كلفته؛ والقياسي أسرع وأرخص للخطوط المعتادة.
const MS_MODEL_CHOICES = [
  ['google/gemini-2.5-flash', 'Gemini 2.5 Flash — سريع اقتصادي'],
  ['google/gemini-2.5-pro', 'Gemini 2.5 Pro — الأقدر على الخطوط الصعبة'],
  ['qwen/qwen3-vl-235b-a22b-instruct', 'Qwen3-VL — قوي ورخيص'],
  ['qwen/qwen2.5-vl-72b-instruct', 'Qwen2.5-VL — متوسط'],
  ['~openai/gpt-luna-latest', 'GPT Luna — مدقق متحفظ'],
  ['anthropic/claude-sonnet-5', 'Claude Sonnet 5 — غالٍ'],
];
const MS_MODEL_PRESETS = {
  standard: { primary: 'google/gemini-2.5-flash', checker: '~openai/gpt-luna-latest' },
  hard: { primary: 'google/gemini-2.5-pro', checker: 'qwen/qwen3-vl-235b-a22b-instruct' },
};

function msModelChoice() {
  try {
    const saved = JSON.parse(localStorage.getItem('almujtahed_ms_models') || 'null');
    if (saved && saved.primary && saved.checker) return saved;
  } catch (e) { /* الافتراضي */ }
  return { ...MS_MODEL_PRESETS.standard };
}

function msFillModelSelects() {
  const choice = msModelChoice();
  [['msPrimaryModel', choice.primary], ['msCheckerModel', choice.checker]].forEach(([id, val]) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = MS_MODEL_CHOICES.map(([v, label]) =>
      `<option value="${v}"${v === val ? ' selected' : ''}>${label}</option>`).join('');
  });
}

function msSaveModelChoice() {
  const primary = document.getElementById('msPrimaryModel')?.value;
  const checker = document.getElementById('msCheckerModel')?.value;
  if (primary && checker) {
    localStorage.setItem('almujtahed_ms_models', JSON.stringify({ primary, checker }));
    msToast('حُفظ اختيار نموذجي النسخ');
  }
}

function msPresetModels(name) {
  const preset = MS_MODEL_PRESETS[name];
  if (!preset) return;
  localStorage.setItem('almujtahed_ms_models', JSON.stringify(preset));
  msFillModelSelects();
  msToast(name === 'hard' ? 'وضع الخطوط الصعبة: Gemini Pro + Qwen3-VL' : 'الوضع القياسي: Gemini Flash + Luna');
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
    return `<div class="ms-copy-card">
      <div class="ms-copy-head">
        <strong>نسخة (${msEsc(c.siglum)})</strong>
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
  msSave(); renderMsCopies();
}

function msDeleteCopy(pid, cid) {
  const p = msProject(pid);
  const c = msCopy(p, cid);
  if (!c || !confirm(`حذف نسخة (${c.siglum}) بكل لوحاتها ونصوصها؟`)) return;
  p.copies = p.copies.filter(x => x.id !== cid);
  msSave(); renderMsCopies();
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
  const ta = document.getElementById('msWbText');
  ta.value = f.text || f.primary_text || '';
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
  if (f.model_primary) meta.push(`الأساسي: ${f.model_primary}${f.primary_seconds != null ? ` (${f.primary_seconds}ث)` : ''}`);
  if (f.model_checker) meta.push(`المدقق: ${f.model_checker}${f.checker_seconds != null ? ` (${f.checker_seconds}ث)` : ''}`);
  if (f.agreement != null) meta.push(`اتفاق النموذجين حرفيًا: ${f.agreement}٪`);
  if (f.cost != null) meta.push(`كلفة النسخ: $${Number(f.cost).toFixed(4)}`);
  document.getElementById('msWbMeta').textContent = meta.join(' · ');
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
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر النسخ');
    const primary = data.primary || {};
    const checker = data.checker || {};
    if (primary.error && checker.error) throw new Error(primary.error);
    if (!primary.text && !checker.text) throw new Error((primary.error || checker.error || 'لم يرجع النموذجان نصًا'));
    f.primary_text = primary.text || '';
    f.checker_text = checker.text || '';
    f.model_primary = primary.model || msModels.primary;
    f.model_checker = checker.model || msModels.checker;
    f.primary_seconds = primary.seconds;
    f.checker_seconds = checker.seconds;
    f.cost = (Number(primary.cost) || 0) + (Number(checker.cost) || 0);
    f.disputes = data.disputes || [];
    f.agreement = data.agreement;
    f.text = f.primary_text;
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
    msSave(); renderMsCopies();
  }
  document.getElementById('msWorkbench').hidden = true;
  msWb = null;
}

document.addEventListener('input', (e) => {
  if (e.target && e.target.id === 'msWbText' && msWb) {
    const ctx = msWbFolio();
    if (ctx && ctx.folio) {
      ctx.folio.text = e.target.value;
      msSave();
    }
  }
});
