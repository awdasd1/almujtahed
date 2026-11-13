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
  ['google/gemini-4-carbon', 'Gemini Carbon — القارئ الثاني المعتمد (ثبت في اللوحات)'],
  ['~google/gemini-flash-latest', 'Gemini Flash Latest — يرجع فارغًا غالبًا في اللوحات، لا يُعتمد قارئًا'],
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
  standard: { primary: '~google/gemini-pro-latest', checker: 'google/gemini-4-carbon', auditor: 'google/gemini-4-argon' },
  hard: { primary: 'google/gemini-3.1-pro-preview', checker: 'anthropic/claude-sonnet-5.5', auditor: 'google/gemini-3.1-pro-preview' },
};

// نماذج القراءة موحّدة بقرار المحقق (لا اختيار في الواجهة)، فلا يسري اختيار قديم محفوظ في المتصفح
function msModelChoice() {
  try { localStorage.removeItem('almujtahed_ms_models_v2'); } catch (e) { /* لا شيء */ }
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
  if (msLoaded) { renderMsProjects(); renderMsGroup(); return; }
  try {
    const res = await fetch('/api/manuscripts');
    const data = await res.json();
    msProjects = Array.isArray(data.projects) ? data.projects : [];
    if (data.models) msModels = data.models;
  } catch (e) { msProjects = []; }
  msLoaded = true;
  msFillModelSelects();
  renderMsProjects();
  msLoadGroup();
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
      <div class="ms-project-card-title">📜 ${msEsc(p.title)} <span class="ms-mode-badge">${p.mode === 'auto' ? '🤖 تحقيق آلي' : '👤 مراجعة بشرية'}</span></div>
      ${p.author ? `<div class="ms-project-card-author">${msEsc(p.author)}</div>` : ''}
      ${p.desc ? `<div class="ms-project-card-desc">${msEsc(p.desc)}</div>` : ''}
      <div class="ms-project-card-stats">${copies.length} نسخة · ${stats.total} لوحة · ✔ ${stats.approved} معتمدة</div>
      ${(p.mode === 'auto' && p.auto && ['running', 'paused_network', 'interrupted'].includes(p.auto.status)) ? '<div class="ms-project-card-stats" style="color:#8a6414;font-weight:700">⏸ تحقيق آلي متوقف عند نقطة محفوظة — افتح المشروع ليستأنف ذاتيًا</div>' : ''}
      ${(p.mode === 'auto' && p.auto && p.auto.status === 'done') ? '<div class="ms-project-card-stats" style="color:#2e7d5b;font-weight:700">✔ اكتمل التحقيق الآلي وصدرت النسخة النهائية</div>' : ''}
      <div class="ms-card-actions">
        <button type="button" class="ms-btn ms-btn-primary" onclick="msOpenProject('${p.id}')">فتح المشروع</button>
        <button type="button" class="ms-btn ms-btn-danger" onclick="msDeleteProject('${p.id}')">حذف</button>
      </div>
    </div>`;
  }).join('');
}

// نوع التحقيق المختار لمشروع جديد: آلي كامل بقيادة المدقق، أو بخطوات مراجعة بشرية
let MS_NEW_MODE = 'auto';

function msSetNewMode(mode) {
  MS_NEW_MODE = mode === 'manual' ? 'manual' : 'auto';
  document.querySelectorAll('.ms-mode-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.mode === MS_NEW_MODE));
}

function msCreateProject() {
  const title = document.getElementById('msNewTitle').value.trim();
  if (!title) { msToast('اكتب عنوان الكتاب المخطوط أولًا'); return; }
  const p = {
    id: msUid(), title,
    author: document.getElementById('msNewAuthor').value.trim(),
    desc: document.getElementById('msNewDesc').value.trim(),
    mode: MS_NEW_MODE,
    createdAt: new Date().toISOString(), copies: [],
  };
  if (p.mode === 'auto') p.auto = { status: 'idle', steps: {}, log: [], report: null, cost: 0 };
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
    <h3 class="ms-proj-title">📜 ${msEsc(p.title)} <span class="ms-mode-badge">${p.mode === 'auto' ? '🤖 تحقيق آلي كامل — بقيادة المدقق الذكي' : '👤 تحقيق بخطوات مراجعة بشرية'}</span></h3>
    ${p.author ? `<div class="ms-proj-author">${msEsc(p.author)}</div>` : ''}
    ${p.desc ? `<p class="ms-proj-desc">${msEsc(p.desc)}</p>` : ''}`;
  renderMsCopies();
  renderMsAuto();
  renderMsStage2();
  renderMsCompareChips();
  renderMsDiscussion();
  renderMsCollation();
  renderMsAgents();
  renderMsAuthor();
  renderMsMonitor();
  msRenderIndexes();
  const introEl = document.getElementById('msIntroText');
  if (introEl) introEl.value = p.intro || '';
  // استئناف ذاتي عند فتح مشروع تحقيق آلي توقف بانقطاع أو إغلاق
  if (p.mode === 'auto') {
    const a = msAutoInit(p);
    msAutoArmWatchdog();
    if (!MS_AUTO_RUNNING && ['running', 'paused_network', 'interrupted'].includes(a.status)) {
      if (a.status === 'running') {
        a.status = 'interrupted';
        msAutoLog(p, 'رُصد إغلاق أو انقطاع في جولة سابقة — يُستأنف ذاتيًا من نقطة الحفظ بعد لحظات.');
        msSave(); renderMsAuto();
      }
      setTimeout(() => msAutoMaybeResume('فتح المشروع'), 1500);
    }
  }
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
  // أي تغير في النسخ/اللوحات يعيد حساب إتاحة زر التحقيق الآلي فورًا
  renderMsAuto();
  renderMsStage2();
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

const MS_ENH_DEFAULTS = { separation: 55, contrast: 1.30, brightness: 1.04, sharpness: 1.9 };

async function msEnhanceFolioFile(folio, params) {
  const src = folio.orig_file_path || folio.file_path;
  const res = await fetch('/api/manuscripts/enhance', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: src, ...(params || MS_ENH_DEFAULTS) }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.file_path) throw new Error(data.detail || 'تعذر ترميم اللوحة');
  folio.enhanced_file_path = data.file_path;
  folio.enhanced_file_url = data.file_url;
  folio.enhance_params = data.params || params || MS_ENH_DEFAULTS;
  return data;
}

async function msUploadFolios(pid, cid, input) {
  const p = msProject(pid);
  const c = msCopy(p, cid);
  const files = Array.from(input.files || []);
  input.value = '';
  if (!c || !files.length) return;
  msToast(`جارٍ رفع ${files.length} لوحة ومعايرتها وترميمها آليًا...`);
  const uploaded = [];
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
      const folio = {
        id: msUid(), label: `${num}${side}`, name: data.filename,
        file_url: data.file_url, file_path: data.file_path,
        orig_file_url: data.file_url, orig_file_path: data.file_path,
        enhanced_file_url: '', enhanced_file_path: '', enhance_params: null,
        adopted_image: 'original',
        status: 'pending', text: '', primary_text: '', checker_text: '',
        disputes: [], agreement: null,
      };
      c.folios.push(folio);
      uploaded.push(folio);
      try { await msEnhanceFolioFile(folio); }
      catch (e) { msToast(`⚠ رُفعت لوحة (${folio.label}) وتعذر ترميمها آليًا: ${e.message}`, 5000); }
    } catch (e) {
      msToast(`❌ فشل رفع «${file.name}»: ${e.message}`, 5000);
    }
  }
  msSave(); renderMsCopies();
  if (uploaded.length) {
    msToast('اكتمل الرفع والترميم. قارن الأصلية بالمرمّمة واعتمد إحداهما.');
    msOpenEnhance(pid, cid, uploaded[0].id, uploaded.slice(1).map(f => f.id));
  } else {
    msToast('اكتمل رفع اللوحات. اضغط أي لوحة لبدء نسخها.');
  }
}

// ---------- معايرة اللوحة وترميمها: أصلية ومرمّمة جنبًا إلى جنب ----------
let MS_ENH = null; // {projectId, copyId, folioId, queue:[folioId]}

function msEnhCtx() {
  if (!MS_ENH) return null;
  const p = msProject(MS_ENH.projectId);
  const c = msCopy(p, MS_ENH.copyId);
  const f = msFolio(c, MS_ENH.folioId);
  return f ? { project: p, copy: c, folio: f } : null;
}

function msEnhVal(sliderId, labelId, div) {
  const s = document.getElementById(sliderId);
  const l = document.getElementById(labelId);
  if (s && l) l.textContent = div ? (s.value / div).toFixed(2) : s.value;
}

function msEnhReadParams() {
  return {
    separation: Number(document.getElementById('msEnhSep').value),
    contrast: Number(document.getElementById('msEnhCon').value) / 100,
    brightness: Number(document.getElementById('msEnhBri').value) / 100,
    sharpness: Number(document.getElementById('msEnhSha').value) / 100,
  };
}

function msEnhSetSliders(params) {
  const pr = params || MS_ENH_DEFAULTS;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
  set('msEnhSep', pr.separation != null ? pr.separation : 65);
  set('msEnhCon', Math.round((pr.contrast || 1.35) * 100));
  set('msEnhBri', Math.round((pr.brightness || 1.04) * 100));
  set('msEnhSha', Math.round((pr.sharpness || 2.0) * 100));
  msEnhVal('msEnhSep', 'msEnhSepVal'); msEnhVal('msEnhCon', 'msEnhConVal', 100);
  msEnhVal('msEnhBri', 'msEnhBriVal', 100); msEnhVal('msEnhSha', 'msEnhShaVal', 100);
}

async function msOpenEnhance(pid, cid, fid, queue) {
  const p = msProject(pid);
  const c = msCopy(p, cid);
  const f = msFolio(c, fid);
  if (!f) return;
  if (!f.orig_file_path) { f.orig_file_path = f.file_path; f.orig_file_url = f.file_url; }
  MS_ENH = { projectId: pid, copyId: cid, folioId: fid, queue: queue || [] };
  const modal = document.getElementById('msEnhModal');
  modal.hidden = false;
  document.getElementById('msEnhInfo').innerHTML =
    `<strong>لوحة (${msEsc(f.label)}) — نسخة (${msEsc(c.siglum)}) من «${msEsc(p.title)}»</strong><br>` +
    'رُمّمت اللوحة آليًا (فصل الخط عن الخلفية + تباين وحدّة وتكبير). عدّل بقيم الترميم، وجرّب القراءة، ثم اعتمد الأصلية أو المرمّمة فتكون هي لوحة النسخ والمقابلة.';
  document.getElementById('msEnhTrial').hidden = true;
  document.getElementById('msEnhTrial').innerHTML = '';
  msEnhSetSliders(f.enhance_params);
  if (!f.enhanced_file_path) {
    document.getElementById('msEnhRestImg').removeAttribute('src');
    try { await msEnhanceFolioFile(f); msSave(); }
    catch (e) { msToast(`⚠ تعذر الترميم الآلي: ${e.message}`, 5000); }
  }
  msRenderEnhance();
}

function msOpenEnhanceCurrent() {
  if (!msWb) { msToast('افتح لوحة أولًا'); return; }
  msOpenEnhance(msWb.projectId, msWb.copyId, msWb.folioId);
}

function msRenderEnhance() {
  const ctx = msEnhCtx();
  if (!ctx) return;
  const f = ctx.folio;
  const bust = `?v=${Date.now()}`;
  document.getElementById('msEnhOrigImg').src = (f.orig_file_url || f.file_url);
  document.getElementById('msEnhRestImg').src = f.enhanced_file_url ? f.enhanced_file_url + bust : '';
  const adopted = f.adopted_image || 'original';
  document.getElementById('msEnhStateOrig').textContent = adopted === 'original' ? '· المعتمدة الآن ✔' : '';
  document.getElementById('msEnhStateRest').textContent = adopted === 'restored' ? '· المعتمدة الآن ✔' : '';
  document.getElementById('msEnhPanelOrig').classList.toggle('ms-enh-adopted', adopted === 'original');
  document.getElementById('msEnhPanelRest').classList.toggle('ms-enh-adopted', adopted === 'restored');
}

async function msApplyEnhance() {
  const ctx = msEnhCtx();
  if (!ctx) return;
  const btn = document.getElementById('msEnhApplyBtn');
  btn.disabled = true; btn.textContent = '⏳ جارٍ إعادة الترميم...';
  try {
    await msEnhanceFolioFile(ctx.folio, msEnhReadParams());
    msSave(); msRenderEnhance();
    msToast('أُعيد ترميم اللوحة بالقيم الجديدة');
  } catch (e) { msToast(`❌ ${e.message}`, 5000); }
  btn.disabled = false; btn.textContent = '🔄 إعادة الترميم بهذه القيم';
}

async function msTrialReadEnhanced() {
  const ctx = msEnhCtx();
  if (!ctx || !ctx.folio.enhanced_file_path) { msToast('لا لوحة مرمّمة بعد'); return; }
  const btn = document.getElementById('msEnhTrialBtn');
  const box = document.getElementById('msEnhTrial');
  btn.disabled = true; btn.textContent = '⏳ Gemini Pro Latest يقرأ اللوحة المرمّمة...';
  box.hidden = false; box.innerHTML = '<div class="ms-rec-loading">⏳ جارٍ تجربة القراءة...</div>';
  try {
    const res = await fetch('/api/manuscripts/transcribe-one', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: ctx.folio.enhanced_file_path, model: '~google/gemini-pro-latest', api_key: msApiKey() }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذرت تجربة القراءة');
    box.innerHTML = `<div class="ms-margin-title">نتيجة تجربة قراءة اللوحة المرمّمة — ${msEsc(data.model || '')}${data.seconds != null ? ` · ${data.seconds}ث` : ''}${data.cost != null ? ` · $${Number(data.cost).toFixed(4)}` : ''}</div><div class="ms-enh-trial-text">${msEsc(data.text || '(بلا نص)')}</div>`;
  } catch (e) {
    box.innerHTML = `<div class="ms-rec-loading">❌ ${msEsc(e.message)}</div>`;
  }
  btn.disabled = false; btn.textContent = '🧪 تجربة قراءة اللوحة';
}

function msAdoptEnhanced(which) {
  const ctx = msEnhCtx();
  if (!ctx) return;
  const f = ctx.folio;
  if (which === 'restored') {
    if (!f.enhanced_file_path) { msToast('لا لوحة مرمّمة لاعتمادها'); return; }
    f.file_url = f.enhanced_file_url; f.file_path = f.enhanced_file_path;
    f.adopted_image = 'restored';
  } else {
    f.file_url = f.orig_file_url || f.file_url; f.file_path = f.orig_file_path || f.file_path;
    f.adopted_image = 'original';
  }
  msSave(); renderMsCopies(); msRenderEnhance();
  if (msWb && msWb.folioId === f.id) msOpenFolio(MS_ENH.projectId, MS_ENH.copyId, f.id);
  msToast(`✔ اعتُمدت اللوحة ${which === 'restored' ? 'المرمّمة' : 'الأصلية'} للوحة (${f.label}) — هي التي ستُنسخ وتُقابَل`);
  const next = (MS_ENH.queue || []).shift();
  if (next) msOpenEnhance(MS_ENH.projectId, MS_ENH.copyId, next, MS_ENH.queue);
  else msCloseEnhance();
}

function msCloseEnhance() {
  const modal = document.getElementById('msEnhModal');
  if (modal) modal.hidden = true;
  MS_ENH = null;
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
                <button type="button" class="ms-dispute-btn ms-rec-btn" onclick="msOpenRecommend('${e.id}')">🧠 توصية المدقق الذكي</button>
                <button type="button" class="ms-dispute-dismiss" onclick="msCollEntry('${e.id}','dismissed')">تجاهل</button>
              </span>
            </div>`).join('')}
        </div>`).join('');
  }
  const mc = document.getElementById('msMarginCollation');
  mc.innerHTML = accepted.length
    ? accepted.map(e => `<div class="ms-margin-entry">${msEntryMark(e)} <strong>(${msEsc(e.folio)})</strong> ${msEsc(msApparatusText(e))}
        <button type="button" class="ms-dispute-dismiss ms-rec-btn" onclick="msOpenRecommend('${e.id}')" title="طلب توصية المدقق الذكي لهذا الموضع">🧠</button>
        <button type="button" class="ms-dispute-dismiss" onclick="msCollEntry('${e.id}','pending')" title="إخراج من الهامش">↩</button></div>`).join('')
    : '<div class="ms-disputes-none">فارغ — اعتمد فروقًا من قائمة المقابلة فتظهر هنا.</div>';
  const me = document.getElementById('msMarginEd');
  const edNotes = [];
  if (base) (base.folios || []).forEach(f => { if ((f.ed_note || '').trim()) edNotes.push({ folio: f.label, text: f.ed_note.trim() }); });
  me.innerHTML = edNotes.length
    ? edNotes.map(n => `<div class="ms-margin-entry"><strong>(${msEsc(n.folio)})</strong> ${msEsc(msEdNoteDisplay(n.text))}</div>`).join('')
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
    // قاعدة المحقق المعتمدة: فروق الضبط/رسم المحض تُردّ آليًا فلا تدخل قائمة الحسم ولا الهامش
    let autoRuled = 0;
    const entries = (data.entries || []).map(e => {
      if (e.type === 'ضبط/رسم') {
        autoRuled++;
        return { ...e, id: msUid(), status: 'dismissed',
                 rec: { decision: 'قاعدة المحقق: فروق الضبط/رسم المحض تُردّ ولا تدخل الهامش',
                        auto_rule: 'orthography_only', at: new Date().toISOString() } };
      }
      return { ...e, id: msUid(), status: 'pending' };
    });
    p.collation = { at: new Date().toISOString(), baseCopyId: base.id, entries };
    msSave(); renderMsCollation();
    const missing = (data.entries || []).filter(e => e.type === 'بياض/مفقود').length;
    msToast(`تمت المقابلة: ${entries.filter(e => e.status === 'pending').length} فرقًا بانتظار حسمك${missing ? ` (منها ${missing} لوحة مفقودة في نسخ أخرى)` : ''}${autoRuled ? `، ورُدّ آليًا بقاعدة الضبط/رسم ${autoRuled} فرقًا محضًا` : ''}. الفروق وحدها لا تدخل الهامش حتى تعتمدها.`, 6000);
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
  if (status === 'accepted') {
    // الاعتماد بيد المحقق من القائمة حسمٌ موثّق يستحق العلامة الخضراء
    e.rec = Object.assign({}, e.rec || {}, {
      decision: 'اعتمد المحقق الفرق في الهامش بيده', by_editor: true,
      at: new Date().toISOString(),
    });
  }
  msSave(); renderMsCollation();
  if (msWb) msRenderWbState();
}

// وسم مصدر سطر هامش التحقيق: وكلاء التحقيق لما جاء منهم وقبله المحقق، وقرار المحقق لما حسَمه بنفسه
const MS_ED_SOURCE_TAGS = [
  [/^\[(تخريج|توثيق)\]/, '[وكيل التخريج]'],
  [/^\[لغة\]/, '[وكيل اللغة]'],
  [/^\[(ضبط\/تصحيف|ضبط|تصحيف)\]/, '[وكيل الضبط]'],
  [/^\[(تراجم|ترجمة)\]/, '[وكيل التراجم]'],
  [/^\[وكيل المؤلف\]/, '[وكيل المؤلف]'],
  [/^\[تعليق المحقق/, '[قرار المحقق — تعليق'],
  [/^\[(تنبيه المحقق|تصحيح المحقق)\]/, '[قرار المحقق]'],
];
function msEdNoteDisplay(text) {
  return (text || '').split('\n').map(l => {
    let out = l;
    for (const [re, tag] of MS_ED_SOURCE_TAGS) {
      if (re.test(out)) { out = out.replace(re, tag); break; }
    }
    return out;
  }).join('\n');
}

// علامة الفرق: ✔ خضراء للمحسوم بقرار المحقق وحده، و◐ كهرمانية للمعتمد آليًا في التشغيل ولم يُحسم بعد
function msEntryMark(e) {
  return (e.rec && e.rec.decision)
    ? '<span class="ms-ok-check" title="محسوم بقرار المحقق">✔</span>'
    : '<span class="ms-auto-check" title="معتمد آليًا في التشغيل — لم يحسمه المحقق بعد">◐</span>';
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

let MS_STYLE_BOOK_TITLES = [];

function msOpenStyleBookPicker() {
  if (typeof openSearchScopeModal === 'function') openSearchScopeModal('ms_style');
  else msToast('نافذة انتقاء الكتب غير متاحة في هذه الصفحة');
}

window.onMsStyleBooks = function (titles) {
  MS_STYLE_BOOK_TITLES = Array.isArray(titles) ? titles : [];
  const label = document.getElementById('msStyleBooksLabel');
  const cmp = document.getElementById('msStyleCompareBtn');
  if (label) label.textContent = MS_STYLE_BOOK_TITLES.length
    ? `النطاق: ${MS_STYLE_BOOK_TITLES.length} كتابًا محددًا` : 'النطاق: كل كتب المؤلف';
  if (cmp) cmp.hidden = !MS_STYLE_BOOK_TITLES.length;
};

async function msRunStyleScan(phrases, containerId, infoId, bookTitles) {
  const p = msCurrentProject();
  if (!p) return null;
  const box = document.getElementById(containerId);
  if (infoId) document.getElementById(infoId).textContent = '⏳ جارٍ إحصاء العبارات في كل كتب المؤلف...';
  if (box) box.innerHTML = '<div class="ms-rec-loading">⏳ نمسح الكتب ونعدّ المواضع المتصلة...</div>';
  try {
    const res = await fetch('/api/manuscripts/author-style', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ author: msAuthorName(p), title: p.title, phrases, book_titles: (bookTitles && bookTitles.length) ? bookTitles : undefined }),
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
  const data = await msRunStyleScan(phrases, 'msRecStyle', null, MS_STYLE_BOOK_TITLES);
  btn.disabled = false;
  if (data) MS_REC.style = data;
}

async function msAuthorStyleManual() {
  const phrases = document.getElementById('msStylePhrases').value.split('\n').map(s => s.trim()).filter(Boolean).slice(0, 6);
  if (phrases.length < 1) { msToast('ضع عبارة واحدة على الأقل (كل عبارة في سطر)'); return; }
  await msRunStyleScan(phrases, 'msStyleResult', 'msStyleInfo');
}

// ---------- نافذة توصية المدقق الذكي لكل موضع ----------
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
  body.innerHTML = '<div class="ms-rec-loading">⏳ المدقق الذكي يدرس الموضع وقراءتيه وسياقه...</div>';
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

// تطبيق قرار على فرق مقابلة (يدوي من النافذة أو آلي بقيادة المدقق الذكي)
function msApplyRecommendation(p, e, data, option, opts) {
  const o = opts || {};
  const base = msBaseCopy(p);
  const bf = base ? (base.folios || []).find(x => x.label === e.folio) : null;
  let corrected = false;
  if (option === 'keep_note' || option === 'adopt_other') {
    e.status = 'accepted';
    if (o.useNote !== false && data.margin_note) e.custom_apparatus = data.margin_note;
  } else if (option === 'keep_drop') {
    e.status = 'dismissed';
  }
  if (option === 'adopt_other' && bf && e.base && e.other && (bf.text || '').includes(e.base)) {
    bf.text = bf.text.replace(e.base, e.other);
    if (bf._view === 'audited' || !bf._view) bf.audited_text = bf.text;
    corrected = true;
  }
  if (o.comment && bf) {
    const line = `[تعليق المحقق على موضع ({e.folio}) — {${e.type}} مع (${e.siglum})] ${o.comment}`;
    bf.ed_note = ((bf.ed_note || '').trim() ? bf.ed_note.trim() + '\n' : '') + line;
  }
  e.rec = { decision: o.decisionLabel || 'اعتمد توصية المدقق الذكي',
            option, at: new Date().toISOString(), action: data.action,
            model: data.model, confidence: data.confidence,
            auto: !!o.auto,
            style: o.style ? { dominant: o.style.dominant,
              totals: (o.style.results || []).map(r => ({ phrase: r.phrase, total: r.total })) } : undefined };
  return corrected;
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
  const corrected = msApplyRecommendation(p, e, data, option, {
    useNote, comment,
    decisionLabel: kind === 'recommended' ? 'اعتمد توصية المدقق الذكي' : 'طبق خياره مع/دون تعليق',
    style: MS_REC.style || undefined,
  });
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
      ${app.length ? `<div class="ms-collated-app"><strong>هامش المقابلة:</strong>${app.map((e, i) => `<div>${msEntryMark(e)} ${i + 1}. ${msEsc(msApparatusText(e))}</div>`).join('')}</div>` : ''}
      ${(f.ed_note || '').trim() ? `<div class="ms-collated-app"><strong>هامش التحقيق:</strong><div>${msEsc(msEdNoteDisplay(f.ed_note))}</div></div>` : ''}
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
        accepted.map(e => `<div>${msEntryMark(e)} ${msEsc(msApparatusText(e))}</div>`).join('');
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
const MS_AGENT_KINDS = { takhrij: 'تخريج', tarjama: 'ترجمة علم', lugha: 'لغة', dabt: 'ضبط/تصحيف', author: 'وكيل المؤلف', tafsir: 'تفسير', aqeedah: 'عقيدة', golden: 'الوكيل الذهبي' };

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
            <span class="ms-dispute-a"><strong>[${msEsc(MS_AGENT_KINDS[s.kind] || s.kind)}]</strong> «${msEsc(s.anchor)}» — ${msEsc(s.body)}${s.source ? `<br>المصدر المقترح: ${msEsc(s.source)}` : ''}<br>اقترحها: وكيل ${msEsc(MS_AGENT_KINDS[s.kind] || s.kind)}${s.model ? ` · النموذج: ${msEsc(s.model)}` : ' · نموذج وكلاء التشغيل'}<br>${msVerifyBadge(s.verify)}</span>
            <span>
              ${(s.verify && s.verify.locus && s.verify.locus.book_id) ? `<button type="button" class="ms-dispute-btn" title="تصفح الشاهد في مصدره مظلَّلًا" onclick="msOpenStyleBook(${Number(s.verify.locus.book_id) || 0}, '${msEsc(s.verify.locus.part || '')}', ${Number(s.verify.locus.page) || 0}, '${msEsc(s.anchor || '')}')">📖 تصفح الشاهد</button>` : ''}
              <button type="button" class="ms-dispute-btn" onclick="msAgentDecision('${s.id}','accepted')">اعتماد في الهامش</button>
              <button type="button" class="ms-dispute-dismiss" onclick="msAgentDecision('${s.id}','dismissed')">رفض</button>
            </span>
          </div>`).join('')}
      </div>`).join('');
}

let MS_AGENT_BOOK_TITLES = [];

function msOpenAgentBookPicker() {
  if (typeof openSearchScopeModal === 'function') openSearchScopeModal('ms_agents');
  else msToast('نافذة انتقاء الكتب غير متاحة في هذه الصفحة');
}

window.onMsAgentBooks = function (titles) {
  MS_AGENT_BOOK_TITLES = Array.isArray(titles) ? titles : [];
  const txt = MS_AGENT_BOOK_TITLES.length
    ? `المظان: ${MS_AGENT_BOOK_TITLES.length} كتابًا مضافًا للبحث والمسح` : null;
  const a = document.getElementById('msAgentBooksLabel');
  const b = document.getElementById('msAuthorBooksLabel');
  if (a) a.textContent = txt || 'المظان: كتب الأصول الافتراضية';
  if (b) b.textContent = txt || 'المظان: لا شيء مضاف';
};

function msToggleAgentSources() {
  const box = document.getElementById('msAgentSources');
  if (!box) return;
  if (!box.hidden) { box.hidden = true; return; }
  const p = msCurrentProject();
  const sugs = p ? (p.agent_suggestions || []) : [];
  const bySource = {};
  sugs.forEach(s => {
    const src = (s.source || '— بلا مصدر مقترح').trim();
    const g = bySource[src] = bySource[src] || { count: 0, kinds: {}, verified: 0, proposers: {} };
    g.count++;
    g.kinds[MS_AGENT_KINDS[s.kind] || s.kind] = 1;
    if (s.model) g.proposers[s.model] = 1;
    if (s.verify && s.verify.status === 'verified') g.verified++;
  });
  const rows = Object.entries(bySource).sort((a, b) => b[1].count - a[1].count);
  box.innerHTML = `<div class="ms-disputes-title">المصادر المقترحة من الوكلاء في هذا المشروع (${rows.length} مصدرًا من ${sugs.length} اقتراحًا) — «أضِف مظنة» يجعل الكتاب ضمن كتب البحث والمسح عند إعادة التوثيق:</div>` +
    (rows.length ? rows.map(([src, g]) => `
      <div class="ms-dispute">
        <span class="ms-dispute-a"><strong>${msEsc(src)}</strong> — اقتُرح ${g.count} مرة (${Object.keys(g.kinds).join('، ')})${g.verified ? ` · موثّق منها ${g.verified}` : ''}${Object.keys(g.proposers).length ? `<br>اقترحها نموذج: ${msEsc(Object.keys(g.proposers).join('، '))}` : ''}</span>
        <span><button type="button" class="ms-dispute-btn" onclick="msAddSourceAsMazanna('${msEsc(src)}')">أضِف مظنة</button></span>
      </div>`).join('') : '<div class="ms-disputes-none">لا اقتراحات بعد.</div>');
  box.hidden = false;
}

function msAddSourceAsMazanna(title) {
  const t = (title || '').trim();
  if (!t || t.startsWith('—')) { msToast('لا مصدر صالح للإضافة'); return; }
  if (!MS_AGENT_BOOK_TITLES.includes(t)) MS_AGENT_BOOK_TITLES.push(t);
  window._msAgentBookTitles = [...MS_AGENT_BOOK_TITLES];
  if (typeof window.onMsAgentBooks === 'function') window.onMsAgentBooks([...MS_AGENT_BOOK_TITLES]);
  msToast(`أُضيف «${t}» إلى كتب المظان — شغّل «إعادة توثيق الاقتراحات بالمظان» للبحث فيه`);
}

async function msReverifySuggestions() {
  const p = msCurrentProject();
  if (!p || !(p.agent_suggestions || []).length) { msToast('لا اقتراحات بعد'); return; }
  const btn = document.getElementById('msReverifyBtn');
  const info = document.getElementById('msReverifyInfo');
  btn.disabled = true; info.textContent = '⏳ جارٍ إعادة التوثيق في المظان وكتب الأصول...';
  try {
    const res = await fetch('/api/manuscripts/verify-suggestions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        suggestions: p.agent_suggestions.map(s => ({ id: s.id, kind: s.kind, anchor: s.anchor, surah: s.surah, ayah: s.ayah })),
        extra_books: MS_AGENT_BOOK_TITLES.length ? MS_AGENT_BOOK_TITLES : undefined,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذرت إعادة التوثيق');
    let changed = 0, verified = 0;
    p.agent_suggestions.forEach(s => {
      const v = (data.results || {})[s.id];
      if (v) { s.verify = v; changed++; if (v.status === 'verified') verified++; }
    });
    msSave(); renderMsAgents(); renderMsAuthor();
    const box = document.getElementById('msAgentSources');
    if (box && !box.hidden) { box.hidden = true; msToggleAgentSources(); }
    info.textContent = `✔ أُعيد توثيق ${changed} اقتراحًا (${verified} موثّقًا)${(data.searched_books || []).length ? ' — بُحث في: ' + data.searched_books.join('، ') : ''}`;
  } catch (e) {
    info.textContent = '';
    msToast('❌ ' + e.message, 6000);
  }
  btn.disabled = false;
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
        body: JSON.stringify({ text: f.text, title: p.title, author: p.author, model, api_key: apiKey, extra_books: msManualExtraBooks(['ayat', 'hadith', 'tarajim', 'lugha']) }),
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

// إثبات اقتراح وكيل في هامش تحقيق لوحته (يدوي أو آلي)
function msAcceptSuggestion(p, s) {
  s.status = 'accepted';
  const base = msBaseCopy(p);
  const f = base ? (base.folios || []).find(x => x.label === s.folio) : null;
  if (f) {
    const line = `[وكيل ${MS_AGENT_KINDS[s.kind] || s.kind}] «${s.anchor}» — ${s.body}${s.source ? ` (${s.source})` : ''}${s.verify && s.verify.detail ? ` [توثيق: ${s.verify.detail}]` : ''}`;
    f.ed_note = ((f.ed_note || '').trim() ? f.ed_note.trim() + '\n' : '') + line;
  }
}

function msAgentDecision(id, status) {
  const p = msCurrentProject();
  if (!p) return;
  const s = (p.agent_suggestions || []).find(x => x.id === id);
  if (!s) return;
  if (status === 'accepted') msAcceptSuggestion(p, s);
  else s.status = status;
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
    const res = await fetch('/api/manuscripts/author-books?author=' + encodeURIComponent(msAuthorName(p) || ''));
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
        body: JSON.stringify({ text: f.text, title: p.title, author: msAuthorName(p), model, api_key: msApiKey(), extra_books: msManualExtraBooks(['authorworks']) }),
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

// ---------- مجموعة تحقيق المخطوطات المعتمدة ----------
// مرجع واحد مضبوط للتحقيق الآلي والبشري: نماذج وكتب كل وكيل محفوظة في
// نظام مجموعات الوكلاء نفسه، وتقرؤها خطوات التحقيق عند كل تشغيل.
const MS_GROUP_ID = 'ms_tahqeeq_group_v1';
const MS_GROUP_MODELS = [
  ['meta/muse-wonder', 'Muse Wonder — قائد ومدقق'],
  ['google/gemini-4-carbon', 'Gemini Carbon — مساعد مدير التحقيق'],
  ['~openai/gpt-luna-latest', 'GPT Luna'],
  ['google/gemini-4-argon', 'Google Argon — معتمِد الصور والجودة'],
  ['~google/gemini-pro-latest', 'Gemini Pro Latest'],
  ['google/gemini-3.1-pro-preview', 'Gemini 3.1 Pro'],
  ['~anthropic/claude-sonnet-latest', 'Claude Sonnet Latest'],
  ['google/gemini-2.5-flash', 'Gemini 2.5 Flash'],
];
const MS_GROUP_DEFAULT_AGENTS = [
  { key: 'leader', name: 'مدير التحقيق — المحقق القائد والمدقق', desc: 'مدير المرحلة الثانية: يستلم النسخة الجاهزة من مدير المرحلة الأولى، يستشير مجلس المستشارين، ينشئ الوكيل الذهبي، يشغّل المتخصصين، ويعتمد النص المحقق نهائيًا. ويحسم مواضع خلاف المرحلة الأولى ويقود النقاش والتصحيحات', model: 'meta/muse-wonder', books: [], stage: 2 },
  { key: 'assistant', name: 'مساعد مدير التحقيق', desc: 'المساعد التنفيذي لمدير التحقيق (Gemini Carbon): يشغّل جولات المتخصصين والمسح والموازاة والرقابة المساعدة بأمر المدير وتحت مراجعته واعتماده', model: 'google/gemini-4-carbon', books: [], stage: 2 },
  { key: 'approver', name: 'المعتمِد — قارئ الصور وحَكم الجودة', desc: 'يدقق صور اللوحات ويعتمد النسخ، يحسم من الصورة، ويعتمد النسخة نهائيًا قبل الإصدار', model: 'google/gemini-4-argon', books: [], stage: 1 },
  { key: 'advisor_sonnet', name: 'عضو مجلس المستشارين — Sonnet', desc: 'مجلس مستشاري المرحلة الثانية: تصله النسخة الجاهزة كاملة استقلالًا فيحللها وينشئ مراسي التحقيق ويقترح أمهات الكتب — تحليل ومظان ومراسٍ فقط، لا تحقيق ولا أحكام', model: '~anthropic/claude-sonnet-latest', books: [], stage: 2, advisor: true },
  { key: 'advisor_argon', name: 'عضو مجلس المستشارين — Gemini Argon', desc: 'مجلس مستشاري المرحلة الثانية: تصله النسخة الجاهزة كاملة استقلالًا فيحللها وينشئ مراسي التحقيق ويقترح أمهات الكتب — تحليل ومظان ومراسٍ فقط، لا تحقيق ولا أحكام', model: 'google/gemini-4-argon', books: [], stage: 2, advisor: true },
  { key: 'advisor_wonder', name: 'عضو مجلس المستشارين — Muse Wonder', desc: 'مجلس مستشاري المرحلة الثانية: تصله النسخة الجاهزة كاملة استقلالًا فيحللها وينشئ مراسي التحقيق ويقترح أمهات الكتب — تحليل ومظان ومراسٍ فقط، لا تحقيق ولا أحكام', model: 'meta/muse-wonder', books: [], stage: 2, advisor: true },
  { key: 'authorid', name: 'وكيل بطاقة المؤلف وتصنيفه المذهبي والعقدي', desc: 'يبني بطاقة المؤلف عصبَ المرحلة الثانية: اسمه الصحيح والمشهور وصيغ النساخ (كاملًا ومختصرًا وبشهرته)، ومذهبه الفقهي وعقيدته بدقة، وكتبه وتسلسلها، وكتب طبقات مذهبه وتراجمه المرشحة — فعليها تُبنى الترجمة واختيار المظان والموازاة بكتبه بدقة', model: 'meta/muse-wonder', stage: 2,
    books: ['سير أعلام النبلاء', 'وفيات الأعيان', 'الوافي بالوفيات', 'تاريخ الإسلام', 'الأعلام', 'معجم المؤلفين', 'طبقات الشافعية الكبرى', 'طبقات الحنابلة', 'الديباج المذهب', 'الجواهر المضية في طبقات الحنفية', 'حسن المحاضرة', 'الدرر الكامنة', 'كشف الظنون عن أسامي الكتب والفنون', 'إيضاح المكنون', 'هدية العارفين', 'الفهرست لابن النديم', 'مفتاح السعادة ومصباح السيادة', 'أبجد العلوم'] },
  { key: 'bio', name: 'وكيل ترجمة المؤلف', desc: 'يبني ترجمة المؤلف بين المختصرة والمتوسطة من كتب التراجم المعتمدة: مولد ووفاة ومواقف وشيوخ وتلاميذ', model: 'meta/muse-wonder', stage: 2,
    books: ['سير أعلام النبلاء', 'وفيات الأعيان', 'الوافي بالوفيات', 'تاريخ الإسلام', 'شذرات الذهب', 'البداية والنهاية', 'طبقات الشافعية الكبرى', 'الأعلام', 'معجم المؤلفين', 'الدرر الكامنة', 'بغية الوعاة', 'حسن المحاضرة'] },
  { key: 'ayat', name: 'وكيل تخريج الآيات', desc: 'يعزو الآيات إلى سورها وأرقامها ويضبط لفظها على المصحف، ويستعين بكتب التفسير والإعراب', model: 'google/gemini-4-carbon', stage: 2,
    books: ['تفسير الطبري', 'تفسير ابن كثير', 'الدر المنثور', 'فتح القدير للشوكاني', 'إعراب القرآن', 'معاني القرآن'] },
  { key: 'hadith', name: 'وكيل التخريج', desc: 'يخرّج الأحاديث والآثار باختصار المحققين: عزو للمصدر والرقم ودرجة مختصرة من كتب التخريج المعتمدة (التلخيص الحبير، نصب الراية، إرواء الغليل، سلسلتا الألباني) — لا سرد أسانيد، والصحيحان يُكتفى بعزوهما', model: 'google/gemini-4-carbon', stage: 2,
    books: ['صحيح البخاري', 'صحيح مسلم', 'سنن أبي داود', 'سنن الترمذي', 'سنن النسائي', 'سنن ابن ماجه', 'موطأ مالك', 'مسند الإمام أحمد', 'التلخيص الحبير', 'نصب الراية', 'إرواء الغليل', 'سلسلة الأحاديث الصحيحة', 'سلسلة الأحاديث الضعيفة', 'فتح الباري', 'شرح النووي على صحيح مسلم'] },
  { key: 'tarajim', name: 'وكيل السير والتراجم', desc: 'يعرّف بأعلام المتن باختصار شديد لا يتجاوز ٤-٥ أسطر: تعريف بالمترجم له ومذهبه وعقيدته وأهم شيوخه وتلاميذه ومؤلفاته وسنة وفاته — من كتب التراجم والطبقات، وما لم يثبت لا يُذكر أو يُنسب بقيل', model: 'google/gemini-4-carbon', stage: 2,
    books: ['سير أعلام النبلاء', 'تهذيب الكمال', 'تهذيب التهذيب', 'تقريب التهذيب', 'الإصابة في تمييز الصحابة', 'أسد الغابة', 'ميزان الاعتدال', 'لسان الميزان', 'الوافي بالوفيات', 'الأعلام'] },
  { key: 'lugha', name: 'وكيل اللغة والأشعار', desc: 'يستخرج غريب الألفاظ من لسان العرب والقاموس المحيط وتاج العروس، ويضبط المشكل ويكشف التصحيف، ويعزو الأبيات الشعرية الواردة في المتن إلى قائليها من كتب الأدب والدواوين', model: 'google/gemini-4-carbon', stage: 2,
    books: ['لسان العرب', 'القاموس المحيط', 'تاج العروس', 'الصحاح', 'النهاية في غريب الحديث', 'المصباح المنير', 'مختار الصحاح', 'الأغاني', 'خزانة الأدب', 'المفضليات'] },
  { key: 'tafsir', name: 'وكيل التفسير', desc: 'حين يكون المخطوط في التفسير أو يذكر المؤلف آية فيفسرها أو يستدل بها: يبين معناها ووجه الاستدلال باختصار من أمهات كتب التفسير المعتمدة', model: 'google/gemini-4-carbon', stage: 2,
    books: ['تفسير الطبري', 'تفسير ابن كثير', 'الجامع لأحكام القرآن للقرطبي', 'الدر المنثور', 'فتح القدير للشوكاني', 'روح المعاني', 'التحرير والتنوير'] },
  { key: 'aqeedah', name: 'وكيل العقيدة', desc: 'حيث يذكر المؤلف في ثنايا بحثه موضوعًا أو كلامًا في الاعتقاد: يبين باختصار موثّق هل هو مذهب أهل السنة والجماعة أو خلافه، من كتب الاعتقاد المعتمدة — بلا توسع ولا تكفير ولا تبديع لأعيان', model: 'google/gemini-4-carbon', stage: 2,
    books: ['شرح العقيدة الطحاوية لابن أبي العز', 'شرح السنة للبغوي', 'الشريعة للآجري', 'الإبانة لابن بطة', 'شرح أصول اعتقاد أهل السنة والجماعة للالكائي', 'درء تعارض العقل والنقل', 'منهاج السنة النبوية'] },
  { key: 'authorworks', name: 'وكيل مقارنة أقوال المؤلف بكتبه', desc: 'متغير بحسب صاحب كل مخطوط: تُحلّ كتب المؤلف نفسه آليًا من المكتبة عند كل مشروع، وما تضيفه هنا مظان إضافية ثابتة', model: 'google/gemini-4-carbon', books: [], stage: 2 },
];
// كتب تُستكمل في المجموعة الحية القائمة بلا مساس بضبط المحقق القائم
const MS_GROUP_BOOK_UPGRADES = {
  hadith: ['التلخيص الحبير', 'نصب الراية', 'سلسلة الأحاديث الصحيحة', 'سلسلة الأحاديث الضعيفة'],
  lugha: ['الأغاني', 'خزانة الأدب', 'المفضليات'],
  authorid: ['كشف الظنون عن أسامي الكتب والفنون', 'إيضاح المكنون', 'هدية العارفين', 'الفهرست لابن النديم', 'مفتاح السعادة ومصباح السيادة', 'أبجد العلوم', 'معجم المؤلفين'],
};
let MS_GROUP = null;
let MS_GROUP_PICK_KEY = null;

async function msLoadGroup() {
  try {
    const res = await fetch('/api/agent-groups');
    const gs = await res.json().catch(() => []);
    MS_GROUP = (Array.isArray(gs) ? gs : []).find(g => g.id === MS_GROUP_ID) || null;
  } catch (e) { MS_GROUP = null; }
  if (MS_GROUP) {
    // هجرة غير مدمّرة: استكمال وكلاء المرحلة الثانية الجدد وكتب التخريج المختصر
    // في المجموعة القائمة، بلا مساس بنماذج المحقق وكتبه المضبوطة بيده
    let changed = false;
    if (MS_GROUP.name === 'مجموعة تحقيق المخطوطات') { MS_GROUP.name = 'تحقيق المخطوطات'; changed = true; }
    // استبعاد Astra Pro من المجلس لغلائه واستبدال Gemini Argon به، ومساعد المدير Gemini Carbon
    (MS_GROUP.agents || []).forEach(a => {
      if (a.ms_key === 'advisor_astra' || /astra/i.test(String(a.model || '')) || /Astra/.test(String(a.name || ''))) {
        a.ms_key = 'advisor_argon'; a.id = 'msag_advisor_argon';
        a.name = 'عضو مجلس المستشارين — Gemini Argon'; a.model = 'google/gemini-4-argon';
        changed = true;
      }
      if (['ayat', 'hadith', 'tarajim', 'lugha', 'tafsir', 'aqeedah', 'authorworks'].includes(a.ms_key)
          && a.model === '~openai/gpt-luna-latest') { a.model = 'google/gemini-4-carbon'; changed = true; }
    });
    MS_GROUP.agents = MS_GROUP.agents || [];
    MS_GROUP_DEFAULT_AGENTS.forEach(d => {
      if (!MS_GROUP.agents.some(a => a.ms_key === d.key)) {
        MS_GROUP.agents.push({
          id: 'msag_' + d.key, ms_key: d.key, name: d.name, desc: d.desc, model: d.model,
          enabled: true, active: true, role: d.key === 'leader' ? 'director' : 'agent',
          is_director: d.key === 'leader', books: [...d.books], booksScope: [...d.books],
          scope_summary: d.desc, system_prompt: d.desc, stage: d.stage || 2, advisor: !!d.advisor,
        });
        changed = true;
      }
    });
    Object.entries(MS_GROUP_BOOK_UPGRADES).forEach(([key, titles]) => {
      const a = msGroupAgent(key);
      if (!a) return;
      a.books = a.books || [];
      titles.forEach(t => { if (!a.books.includes(t)) { a.books.push(t); changed = true; } });
      a.booksScope = [...a.books];
    });
    if (changed) { msSaveGroup(); msToast('حُدّثت «مجموعة تحقيق المخطوطات» ببنية المرحلتين: مجلس مستشارين ووكيلا تفسير وعقيدة وكتب التخريج المختصر — ضبطك القائم محفوظ'); }
  }
  renderMsGroup();
  msApplyGroupModelDefaults();
  return MS_GROUP;
}

// نماذج التشغيل البشري الافتراضية تُضبط من المجموعة المعتمدة (والمحقق يبدلها بيده إن شاء)
function msApplyGroupModelDefaults() {
  if (!MS_GROUP) return;
  const set = (id, key) => {
    const el = document.getElementById(id);
    const model = msGroupModel(key, '');
    if (el && model && [...el.options].some(o => o.value === model)) el.value = model;
  };
  set('msAgentModel', 'hadith');
  set('msAuthorModel', 'authorworks');
  set('msMonitorModel', 'leader');
}

function msGroupAgent(key) { return MS_GROUP ? (MS_GROUP.agents || []).find(a => a.ms_key === key) || null : null; }
function msGroupModel(key, fallback) { const a = msGroupAgent(key); return (a && a.model) || fallback; }
function msBookTitleOf(s) { return String(s || '').replace(/^#\d+\s*/, '').trim(); }
function msGroupBookTitles(key) {
  const a = msGroupAgent(key);
  return a ? (a.books || []).map(msBookTitleOf).filter(Boolean) : [];
}

function msBuildGroup() {
  return {
    id: MS_GROUP_ID, name: 'تحقيق المخطوطات',
    desc: 'فريق تحقيق المخطوطات على مرحلتين: المرحلة الأولى قراءة النص ومقابلة النسخ وتدقيقها، والمرحلة الثانية تحقيق النص بمدير تحقيق ومجلس مستشارين ووكيل ذهبي مؤقت لكل مخطوط ومتخصصين مختصرين (تخريج، لغة وأشعار، سير وتراجم، تفسير، عقيدة) بنماذج وكتب مضبوطة من الشاملة.',
    ms_kind: 'manuscripts',
    agents: MS_GROUP_DEFAULT_AGENTS.map(d => ({
      id: 'msag_' + d.key, ms_key: d.key, name: d.name, desc: d.desc, model: d.model,
      enabled: true, active: true, role: d.key === 'leader' ? 'director' : 'agent',
      is_director: d.key === 'leader', books: [...d.books], booksScope: [...d.books],
      scope_summary: d.desc, system_prompt: d.desc, stage: d.stage || 2, advisor: !!d.advisor,
    })),
  };
}

async function msSeedGroup(force) {
  if (MS_GROUP && !force) { renderMsGroup(); return; }
  if (force && !confirm('إعادة ضبط مجموعة تحقيق المخطوطات إلى ضبط المصنع؟ ستفقد تعديلات النماذج والكتب التي ضبطتها.')) return;
  const g = msBuildGroup();
  try {
    const res = await fetch('/api/agent-groups', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(g) });
    if (!res.ok) throw new Error('حفظ');
    MS_GROUP = g; renderMsGroup();
    msToast('اعتمدت «مجموعة تحقيق المخطوطات» مرجعًا للتحقيق الآلي والبشري بنماذجها وكتبها');
  } catch (e) { msToast('تعذر حفظ المجموعة المعتمدة'); }
}

async function msSaveGroup() {
  if (!MS_GROUP) return;
  try {
    await fetch('/api/agent-groups', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(MS_GROUP) });
  } catch (e) { /* يعاد الحفظ عند أي تعديل لاحق */ }
}

function msGroupSetModel(key, model) {
  const a = msGroupAgent(key);
  if (!a || !model) return;
  a.model = model;
  msSaveGroup();
  msToast(`حُفظ نموذج «${a.name}»: ${model} — يسري على التشغيلات القادمة آليًا وبشريًا`);
}

function msGroupRemoveBook(key, idx) {
  const a = msGroupAgent(key);
  if (!a) return;
  a.books.splice(idx, 1);
  a.booksScope = [...a.books];
  msSaveGroup(); renderMsGroup();
}

// كتب المظان للتشغيل البشري: كتب وكلاء المجموعة المعتمدة + ما أضافه المحقق بيده
function msManualExtraBooks(keys) {
  const all = [];
  (keys || []).forEach(k => msGroupBookTitles(k).forEach(t => { if (!all.includes(t)) all.push(t); }));
  (MS_AGENT_BOOK_TITLES || []).forEach(t => { const x = msBookTitleOf(t); if (x && !all.includes(x)) all.push(x); });
  return all.length ? all : undefined;
}

function msGroupPickBooks(key) {
  const a = msGroupAgent(key);
  if (!a) return;
  MS_GROUP_PICK_KEY = key;
  window._msGroupCurrentBooks = [...(a.books || [])];
  if (typeof openSearchScopeModal === 'function') openSearchScopeModal('ms_group');
  else msToast('نافذة انتقاء الكتب غير متاحة في هذه الصفحة');
}

window.onMsGroupBooks = function (titles) {
  const a = msGroupAgent(MS_GROUP_PICK_KEY);
  if (!a) return;
  (titles || []).forEach(t => { if (t && !a.books.includes(t)) a.books.push(t); });
  a.booksScope = [...a.books];
  msSaveGroup(); renderMsGroup();
  msToast(`كتب «${a.name}» المعتمدة الآن: ${a.books.length} كتابًا`);
};

function renderMsGroup() {
  const box = document.getElementById('msGroupBody');
  if (!box) return;
  if (!MS_GROUP) {
    box.innerHTML = `<div class="ms-hint">لم تُنشأ المجموعة المعتمدة بعد. أنشئها لتكون مرجع التحقيق بمرحلتيه: مدير تحقيق ومجلس مستشارين (٣) ومعتمِد صور وجودة ومتخصصون مختصرون (آيات، تخريج، سير وتراجم، لغة وأشعار، تفسير، عقيدة، ترجمة مؤلف، مقارنة بمؤلفات المؤلف)، لكلٍّ نموذجه وكتبه المعتمدة من الشاملة.</div>
      <div class="ms-form-row"><button type="button" class="ms-btn ms-btn-primary" onclick="msSeedGroup(false)">⭐ إنشاء واعتماد مجموعة تحقيق المخطوطات</button></div>`;
    return;
  }
  box.innerHTML = `
    <div class="ms-hint" style="margin-bottom:8px">هذه المجموعة — <strong>«تحقيق المخطوطات»</strong> في قسم الوكلاء — هي <strong>المرجع المعتمد لمرحلتي التحقيق</strong>: مدير التحقيق ومجلس مستشارينه ومتخصصوه المختصرون بنماذجهم وكتبهم، يسري ضبطها على المرحلة الثانية آليًا وبشريًا. وكيل مقارنة المؤلف متغير: تُحلّ كتب صاحب كل مخطوط آليًا عند تشغيله. يمكنك إضافة كتب لأي وكيل في أي وقت فتسري على القادم.</div>
    ${MS_GROUP.agents.map(a => `
      <div class="ms-group-agent">
        <div class="ms-group-agent-head">
          <strong>${msEsc(a.name)}</strong>
          <select class="ms-group-model" onchange="msGroupSetModel('${msEsc(a.ms_key)}', this.value)">
            ${MS_GROUP_MODELS.map(([v, l]) => `<option value="${v}"${v === a.model ? ' selected' : ''}>${l}</option>`).join('')}
            ${MS_GROUP_MODELS.some(([v]) => v === a.model) ? '' : `<option value="${msEsc(a.model)}" selected>${msEsc(a.model)}</option>`}
          </select>
        </div>
        <div class="ms-hint">${msEsc(a.desc || '')}</div>
        <div class="ms-group-books">
          ${(a.books || []).map((b, i) => `<span class="ms-book-chip">${msEsc(b)} <button type="button" class="ms-chip-x" title="إزالة" onclick="msGroupRemoveBook('${msEsc(a.ms_key)}', ${i})">✕</button></span>`).join('') || '<span class="ms-hint">لا كتب مثبتة — يعمل بنطاقه الافتراضي</span>'}
          <button type="button" class="ms-btn" onclick="msGroupPickBooks('${msEsc(a.ms_key)}')">📚 إضافة كتب من الشاملة</button>
        </div>
      </div>`).join('')}
    <div class="ms-form-row"><button type="button" class="ms-btn" onclick="msSeedGroup(true)">↺ إعادة ضبط المصنع للمجموعة</button></div>`;
}

// ---------- المرحلة الثانية: تحقيق النص (مدير تحقيق + مجلس + ذهبي + متخصصون) ----------
// المرحلة الأولى (قراءة النص ومقابلة النسخ وتدقيقها) تنتهي بتسليم مديرها النسخة
// الجاهزة بهوامشها إلى مدير التحقيق؛ فيستشير المجلس، وينشئ الوكيل الذهبي،
// ويشغّل المتخصصين المختصرين، ثم يعتمد النص المحقق.
function msInitStage2(p) {
  if (!p.stage2) p.stage2 = { status: 'idle', handed_at: '', advisors: [], anchors: [], books: [], missing: [],
    golden: null, log: [], cost: 0, done: {}, accepted: 0, dismissed: 0, manager_note: '' };
  if (!p.stage2.done) p.stage2.done = {};
  if (!p.stage2.log) p.stage2.log = [];
  return p.stage2;
}

function msStage2Log(p, msg) {
  const s2 = msInitStage2(p);
  s2.log.push({ at: new Date().toLocaleTimeString('ar-EG'), msg });
  if (s2.log.length > 160) s2.log = s2.log.slice(-160);
}

function msStage1Status(p) {
  const base = msBaseCopy(p);
  const folios = base ? (base.folios || []) : [];
  const withText = folios.filter(f => (f.text || '').trim()).length;
  const approved = folios.filter(f => f.status === 'approved').length;
  const entries = ((p.collation || {}).entries || []);
  const pending = entries.filter(e => e.status === 'pending').length;
  return { base, total: folios.length, withText, approved, entries: entries.length, pending,
           ready: !!base && folios.length > 0 && withText === folios.length && pending === 0 };
}

function msStageText(p) {
  const base = msBaseCopy(p);
  if (!base) return '';
  return (base.folios || []).filter(f => (f.text || '').trim()).map(f => f.text.trim()).join('\n');
}

function msStageApparatus(p) {
  const lines = [];
  ((p.collation || {}).entries || []).filter(e => e.status === 'accepted').forEach(e => {
    lines.push(`[مقابلة لوحة ${e.folio} مع (${e.siglum})] ${msApparatusPrint(e)}`);
  });
  const base = msBaseCopy(p);
  if (base) (base.folios || []).forEach(f => {
    if ((f.ed_note || '').trim()) lines.push(`[تحقيق لوحة ${f.label}] ${msEdNotePrint(f.ed_note)}`);
  });
  return lines.join('\n');
}

function renderMsStage2() {
  const box = document.getElementById('msStage2Body');
  const p = msCurrentProject();
  if (!box || !p) return;
  const s1 = msStage1Status(p);
  const s2 = msInitStage2(p);
  const handed = !!s2.handed_at;
  const adv = s2.advisors || [];
  box.innerHTML = `
    <div class="ms-stage-track">
      <div class="ms-stage-node ${s1.ready ? 'is-done' : ''}">
        <strong>المرحلة الأولى: قراءة النص ومقابلة النسخ</strong>
        <span>${s1.total ? `${s1.withText}/${s1.total} لوحة منسوخة في الأم (${s1.approved} معتمدة)` : 'لا لوحات بعد'}${s1.entries ? ` · مقابلة: ${s1.entries} فرقًا، ${s1.pending} معلّق` : ''} — ${s1.ready ? '✔ جاهزة للتسليم' : 'لم تكتمل بعد'}</span>
      </div>
      <div class="ms-stage-arrow">⟵ تسليم</div>
      <div class="ms-stage-node ${handed ? 'is-done' : ''}">
        <strong>المرحلة الثانية: تحقيق النص</strong>
        <span>${handed ? `سُلّمت النسخة الجاهزة إلى مدير التحقيق (${msEsc(s2.handed_at)})` : 'بانتظار تسليم المرحلة الأولى'} · الحالة: ${msEsc({ idle: 'لم تبدأ', consulted: 'استُشير المجلس', golden: 'الذهبي أنجز', running: 'المتخصصون يعملون', done: 'معتمدة من مدير التحقيق', handed: 'مستلمة' }[s2.status] || s2.status)}${s2.cost ? ` · كلفة المرحلة: $${Number(s2.cost).toFixed(4)}` : ''}</span>
      </div>
    </div>
    <div class="ms-form-row">
      <button type="button" class="ms-btn ms-btn-primary" id="msStage2HandoverBtn" onclick="msStage2Handover()" ${handed || !s1.withText ? 'disabled' : ''}>📤 تسليم النسخة الجاهزة إلى مدير التحقيق (مع النص وكل هوامشه)</button>
      ${handed ? `<button type="button" class="ms-btn" onclick="if(confirm('إعادة التسليم تلغي حالة المرحلة الثانية الحالية وتسجيلاتها؟')){const p=msCurrentProject(); p.stage2=null; msSave(); renderMsStage2();}">↺ إعادة تهيئة المرحلة الثانية</button>` : ''}
    </div>
    ${handed ? `
    <div class="ms-form-row">
      <button type="button" class="ms-btn ms-btn-primary" id="msStage2AuthorBtn" onclick="msStage2AuthorProfile()">🪪 ٠) بناء بطاقة المؤلف وتصنيفه المذهبي والعقدي</button>
      <span class="ms-wb-meta">عصب المرحلة الثانية: الاسم الصحيح والمشهور وصيغ النساخ، والمذهب والعقيدة، وكتبه وتسلسلها وكتب طبقات مذهبه — تُبنى عليها الترجمة والمظان والموازاة</span>
    </div>
    ${p.author_profile ? `<div class="ms-margin-title">🪪 بطاقة المؤلف وتصنيفه — عصب المرحلة الثانية</div>
      <div class="ms-group-books" style="white-space:pre-wrap">${msEsc(msAuthorCardText(p))}</div>
      ${(p.author_profile.works || []).length ? `<div class="ms-group-books"><strong>مؤلفاته وتسلسلها:</strong> ${p.author_profile.works.map(w => `<span class="ms-book-chip">${msEsc(w.title)}${w.in_shamela ? ' ✔ في الشاملة' : ''}</span>`).join('')}</div>` : ''}
      ${s2.author_verdict && s2.author_verdict.famous ? `<div class="ms-hint">حكم مجلس المستشارين على الاسم والتصنيف: الصحيح «${msEsc(s2.author_verdict.correct || '—')}» · المشهور «${msEsc(s2.author_verdict.famous)}» · ${msEsc(s2.author_verdict.madhhab || '')} · ${msEsc(s2.author_verdict.aqeedah || '')}</div>` : ''}`
    : '<div class="ms-hint">ابدأ ببطاقة المؤلف قبل المجلس: فتصنيفه مذهبيًا وعقديًا يوجّه اختيار كتب الطبقات والتراجم، واسمه المشهور يفتح كتبه للموازاة الدقيقة.</div>'}
    <div class="ms-form-row">
      <button type="button" class="ms-btn ms-btn-primary" id="msStage2ConsultBtn" onclick="msStage2Consult()">🧭 ١) استشارة مجلس المستشارين (كلٌّ تصله النسخة كاملة)</button>
      <button type="button" class="ms-btn ms-btn-primary" id="msStage2GoldenBtn" onclick="msStage2Golden()" ${adv.length ? '' : 'disabled'}>🥇 ٢) إنشاء الوكيل الذهبي وتشغيله في كتب المجلس</button>
      <button type="button" class="ms-btn ms-btn-primary" id="msStage2RunBtn" onclick="msStage2Specialists()" ${adv.length ? '' : 'disabled'}>🔍 ٣) تشغيل المتخصصين المختصرين (تخريج/لغة وأشعار/سير/تفسير/عقيدة)</button>
      <button type="button" class="ms-btn" id="msStage2ApproveBtn" onclick="msStage2Approve()">✔ ٤) اعتماد مدير التحقيق وبناء الفهارس</button>
    </div>
    ${adv.length ? `<div class="ms-margin-title">مجلس المستشارين — تحليلاتهم ومراسي التحقيق وكتبهم المطابَقة في الشاملة</div>
      ${adv.map(a => `<div class="ms-group-agent"><div class="ms-group-agent-head"><strong>${msEsc(a.name)}</strong><span class="ms-wb-meta">${msEsc(a.model || '')}</span></div>
        ${a.error ? `<div class="ms-hint">تعذر: ${msEsc(a.error)}</div>` : `<div class="ms-group-books" style="white-space:pre-wrap">${msEsc(a.analysis || '')}</div>
        <div class="ms-group-books">${(a.books || []).map(b => `<span class="ms-book-chip">${msEsc(b.title)}${b.assign_to ? ` ← ${msEsc(b.assign_to)}` : ''}</span>`).join('')}</div>`}
      </div>`).join('')}
      <div class="ms-group-books"><strong>كتب المجلس بعد المطابقة في الشاملة:</strong> ${(s2.books || []).map(b => `<span class="ms-book-chip">${msEsc(b.resolved_title || b.title)}${b.resolved ? ' ✔ مطابق' : ' ✘ لم يوجد بمؤلفه'} (${b.votes || 1} صوت)</span>`).join('') || '—'}</div>
      <div class="ms-group-books"><strong>مراسي التحقيق الموحدة:</strong> ${(s2.anchors || []).map(a => `<span class="ms-book-chip">${msEsc(a)}</span>`).join('') || '—'}
      ${(s2.missing || []).length ? `<br><span class="ms-hint">كتب رشّحها المجلس ولم توجد في الشاملة بمؤلفيها فلم تُعتمد: ${s2.missing.map(msEsc).join('، ')}</span>` : ''}</div>`
    : '<div class="ms-hint">استشر المجلس أولًا: كل مستشار تصله النسخة الجاهزة كاملة استقلالًا، فيحلل النص وينشئ مراسي التحقيق ويقترح أمهات الكتب، وتُطابَق كتبهم في الشاملة بمؤلفيها قبل أن يعمل بها أحد.</div>'}
    ${s2.golden ? `<div class="ms-margin-title">🥇 الوكيل الذهبي المؤقت — أنشأه مدير التحقيق لهذا المخطوط بعينه</div>
      <div class="ms-group-books" style="white-space:pre-wrap">${msEsc(s2.golden.prompt || '')}</div>
      <div class="ms-hint">نطاقه الوحيد كتب المجلس المطابقة: ${(s2.golden.scope_books || []).map(msEsc).join('، ') || '—'} · اقتراحاته في بطاقة الوكلاء بالأسفل موسومة «الذهبي».</div>` : ''}
    ${s2.manager_note ? `<div class="ms-margin-title">اعتماد مدير التحقيق</div><div class="ms-group-books" style="white-space:pre-wrap">${msEsc(s2.manager_note)}</div>` : ''}
    ` : '<div class="ms-hint">حين تكتمل المرحلة الأولى (نص الأم كاملًا بلا فروق معلقة) سلّم النسخة الجاهزة؛ فيتولى مدير التحقيق تحقيق النص تحقيقًا مختصرًا محكمًا بفريقه.</div>'}
    ${(s2.log || []).length ? `<div class="ms-auto-log">${s2.log.map(l => `<div><span class="ms-auto-log-at">${msEsc(l.at)}</span> ${msEsc(l.msg)}</div>`).join('')}</div>` : ''}`;
}

// بطاقة المؤلف المصنّفة: عصب المرحلة الثانية (اسم صحيح/مشهور، مذهب، عقيدة، كتب)
function msAuthorName(p) {
  const pr = (p && p.author_profile) || {};
  return pr.famous_name || pr.correct_name || (p && p.author) || '';
}

function msAuthorCardText(p) {
  const pr = (p && p.author_profile) || null;
  if (!pr) return '';
  return [
    `الاسم كما كُتب: ${pr.written || p.author || '—'}`,
    `الاسم الصحيح: ${pr.correct_name || '—'} · المشهور: ${pr.famous_name || '—'}`,
    `صيغ الاسم في النسخ والتراجم: ${(pr.variants || []).join('، ') || '—'}`,
    `المذهب الفقهي: ${pr.madhhab || '—'} · العقيدة: ${pr.aqeedah || '—'} · العصر: ${pr.era || '—'} · الوفاة: ${pr.death || '—'}`,
    pr.classification_basis ? `قرينة التصنيف: ${pr.classification_basis}` : '',
    (pr.works_in_shamela || []).length ? `كتبه الموجودة في الشاملة (للموازاة بدقة): ${pr.works_in_shamela.join('، ')}` : '',
    pr.attribution ? `نسبة هذا المخطوط إليه: ${pr.attribution.verdict || '—'}${pr.attribution.summary ? ' — ' + pr.attribution.summary : ''}` : '',
    pr.attribution && pr.attribution.claim_basis ? `قول أهل التراجم والببليوغرافيا في النسبة: ${pr.attribution.claim_basis}` : '',
    (pr.tarajim_candidates || []).filter(c => c.resolved).length ? `كتب طبقات مذهبه وتراجمه المرشحة المطابقة: ${pr.tarajim_candidates.filter(c => c.resolved).map(c => c.resolved_title || c.title).join('، ')}` : '',
  ].filter(Boolean).join('\n');
}

async function msStage2AuthorProfile() {
  const p = msCurrentProject();
  if (!p) return;
  if (!String(p.author || '').trim()) { msToast('اكتب اسم المؤلف كما ورد في بيانات المشروع أولًا (كما كتبه النساخ)'); return; }
  await msLoadGroup();
  const btn = document.getElementById('msStage2AuthorBtn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ وكيل بطاقة المؤلف يصنّفه ويتحقق في الشاملة...'; }
  const s2 = msInitStage2(p);
  try {
    const res = await fetch('/api/manuscripts/author-profile', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        author: p.author, title: p.title, desc: p.desc || '',
        text: (s2.text_snapshot || msStageText(p)).slice(0, 3500),
        model: msGroupModel('authorid', MS_WONDER_MODEL),
        tarajim_books: [...new Set([...msGroupBookTitles('authorid'), ...msGroupBookTitles('bio')])],
        api_key: msApiKey(),
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذرت بطاقة المؤلف');
    p.author_profile = data;
    msStage2Log(p, `بُنيت بطاقة المؤلف: الصحيح «${data.correct_name || '—'}» والمشهور «${data.famous_name || '—'}» — المذهب: ${data.madhhab || '—'}، العقيدة: ${data.aqeedah || '—'}؛ كتبه في الشاملة ${(data.works_in_shamela || []).length} بصيغة «${data.works_form || '—'}»، وشواهد ترجمته ${data.bio_snippets || 0} في ${(data.bio_books || []).join('، ') || '—'}.`);
    if (data.attribution) msStage2Log(p, `نسبة «${p.title}» إليه: ${data.attribution.verdict || '—'}${data.attribution.summary ? ' — ' + data.attribution.summary : ''}`);
    msSave(); renderMsStage2();
    msToast('✔ بُنيت بطاقة المؤلف وتصنيفه — ستغذي المجلس والمتخصصين والمقدمة والموازاة', 7000);
  } catch (e) { msToast('❌ ' + e.message, 7000); }
  if (btn) { btn.disabled = false; btn.textContent = '🪪 ٠) بناء بطاقة المؤلف وتصنيفه المذهبي والعقدي'; }
}

function msStage2Handover() {
  const p = msCurrentProject();
  if (!p) return;
  const s1 = msStage1Status(p);
  if (!s1.withText) { msToast('لا نص جاهزًا بعد — أكمل نسخ لوحات الأم في المرحلة الأولى'); return; }
  if (s1.pending) { msToast(`تنبيه: بقي ${s1.pending} فرق مقابلة معلّقًا — سيُسلَّم النص بهوامشه القائمة، ويمكن حسم المعلّق لاحقًا من بطاقة المقابلة`, 6000); }
  const s2 = msInitStage2(p);
  s2.handed_at = new Date().toLocaleString('ar-EG');
  s2.status = 'handed';
  s2.text_snapshot = msStageText(p).slice(0, 60000);
  s2.apparatus_snapshot = msStageApparatus(p).slice(0, 12000);
  msStage2Log(p, `سلّم مدير المرحلة الأولى النسخة الجاهزة إلى مدير التحقيق: نص الأم كاملًا (${s1.withText} لوحة) مع هوامش المقابلة والتحقيق القائمة.`);
  msSave(); renderMsStage2();
  msToast('✔ سُلّمت النسخة الجاهزة إلى مدير التحقيق — تبدأ المرحلة الثانية باستشارة المجلس');
}

async function msStage2Consult() {
  const p = msCurrentProject();
  if (!p) return;
  await msLoadGroup();
  const advisors = (MS_GROUP ? MS_GROUP.agents : []).filter(a => a.advisor || String(a.ms_key || '').startsWith('advisor'))
    .map(a => ({ name: a.name, model: a.model }));
  const specialists = (MS_GROUP ? MS_GROUP.agents : []).filter(a => ['hadith', 'lugha', 'tarajim', 'tafsir', 'aqeedah', 'ayat'].includes(a.ms_key)).map(a => a.name);
  const btn = document.getElementById('msStage2ConsultBtn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ المجلس يدرس النسخة...'; }
  const s2 = msInitStage2(p);
  try {
    const res = await fetch('/api/manuscripts/stage2-consult', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: p.title, author: p.author, desc: p.desc || '',
        sigla: (p.copies || []).map(c => `(${c.siglum}) = ${c.library || ''} ${c.shelfmark || ''}`).join('؛ '),
        text: s2.text_snapshot || msStageText(p), apparatus: s2.apparatus_snapshot || msStageApparatus(p),
        author_card: msAuthorCardText(p),
        advisors, specialists, director_model: msGroupModel('leader', MS_WONDER_MODEL), api_key: msApiKey(),
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذرت الاستشارة');
    s2.advisors = data.advisors || [];
    s2.author_verdict = data.author_verdict || null;
    if (s2.author_verdict && s2.author_verdict.famous) {
      msStage2Log(p, `حكم المجلس على اسم المؤلف وتصنيفه: المشهور «${s2.author_verdict.famous}» — ${s2.author_verdict.madhhab || ''} · ${s2.author_verdict.aqeedah || ''}.`);
      if (p.author_profile) {
        ['correct_name|correct', 'famous_name|famous', 'madhhab|madhhab', 'aqeedah|aqeedah'].forEach(pair => {
          const [mine, theirs] = pair.split('|');
          if (s2.author_verdict[theirs]) p.author_profile[mine] = s2.author_verdict[theirs];
        });
      }
    }
    s2.anchors = data.anchors || [];
    s2.books = data.books || [];
    s2.missing = data.missing || [];
    s2.status = 'consulted';
    const okBooks = s2.books.filter(b => b.resolved).length;
    msStage2Log(p, `استُشير المجلس (${s2.advisors.length} عضوًا بمن فيهم مدير التحقيق مشاركًا في الترشيح): ${okBooks} كتابًا طُوبق في الشاملة من ${s2.books.length} مرشحًا، و${s2.anchors.length} مرساة تحقيق.`);
    msSave(); renderMsStage2();
    msToast(`✔ أنهى المجلس: ${okBooks} كتابًا مطابقًا و${s2.anchors.length} مرساة — راجع تحليلاتهم ثم أنشئ الوكيل الذهبي`, 7000);
  } catch (e) { msToast('❌ ' + e.message, 7000); }
  if (btn) { btn.disabled = false; btn.textContent = '🧭 ١) استشارة مجلس المستشارين (كلٌّ تصله النسخة كاملة)'; }
}

async function msStage2Golden() {
  const p = msCurrentProject();
  if (!p) return;
  const s2 = msInitStage2(p);
  const books = (s2.books || []).filter(b => b.resolved).map(b => b.resolved_title || b.title);
  if (!books.length) { msToast('لا كتب مطابقة من المجلس بعد — استشر المجلس أولًا'); return; }
  const btn = document.getElementById('msStage2GoldenBtn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ الوكيل الذهبي يبحث في كتب المجلس...'; }
  try {
    const res = await fetch('/api/manuscripts/stage2-golden', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: p.title, author: p.author, text: s2.text_snapshot || msStageText(p),
        books, anchors: s2.anchors || [], model: msGroupModel('leader', MS_WONDER_MODEL), api_key: msApiKey(),
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر الوكيل الذهبي');
    s2.golden = { prompt: data.golden_prompt || '', scope_books: data.scope_books || [], at: new Date().toISOString() };
    s2.cost = (Number(s2.cost) || 0) + (Number(data.cost) || 0);
    s2.status = 'golden';
    p.agent_suggestions = p.agent_suggestions || [];
    (data.suggestions || []).forEach(s => p.agent_suggestions.push({ ...s, id: msUid(), folio: (msBaseCopy(p).folios || []).find(f => (f.text || '').includes((s.anchor || '').slice(0, 24)))?.label || '', status: 'pending', agent: 'golden', stage2: true }));
    msStage2Log(p, `أُنشئ الوكيل الذهبي المؤقت وشُغّل في ${books.length} كتابًا من كتب المجلس: ${(data.suggestions || []).length} اقتراحًا صلبًا بانتظار بوابة التوثيق.`);
    msSave(); renderMsStage2(); renderMsAgents();
    msToast('✔ أنهى الوكيل الذهبي — اقتراحاته في بطاقة الوكلاء، والموثّق منها سيُثبت عند تشغيل المتخصصين واعتماد المدير', 7000);
  } catch (e) { msToast('❌ ' + e.message, 7000); }
  if (btn) { btn.disabled = false; btn.textContent = '🥇 ٢) إنشاء الوكيل الذهبي وتشغيله في كتب المجلس'; }
}

// متخصصو المرحلة الثانية المختصرون: لكل فن تركيزه وكتبه وانضباط اختصاره
const MS_STAGE2_JOBS = [
  ['ayat', 'وكيل تخريج الآيات', s => s.kind === 'takhrij' && !!s.surah, 'الآيات القرآنية وحدها: عزو كل آية إلى سورتها ورقمها وضبط لفظها على المصحف، باختصار'],
  ['hadith', 'وكيل التخريج', s => s.kind === 'takhrij' && !s.surah, 'الأحاديث والآثار وحدها باختصار المحققين: عزو الحديث إلى مصدره ورقمه، ودرجته مختصرة من كتب التخريج المعتمدة (التلخيص الحبير، نصب الراية، إرواء الغليل، سلسلة الأحاديث الصحيحة، سلسلة الأحاديث الضعيفة)؛ لا سرد للأسانيد ولا استطراد، وما كان في الصحيحين اكتفِ بعزوه إليهما'],
  ['tarajim', 'وكيل السير والتراجم', s => s.kind === 'tarjama', 'الأعلام الواردون في المتن وحدهم، بترجمة مختصرة جدًا لا تتجاوز ٤-٥ أسطر: تعريف بالمترجم له ومذهبه وعقيدته وأهم شيوخه وتلاميذه ومؤلفاته وسنة وفاته؛ وما لم يثبت من كتب التراجم والطبقات لا يُذكر أو يُنسب بقيل'],
  ['lugha', 'وكيل اللغة والأشعار', s => s.kind === 'lugha' || s.kind === 'dabt', 'غريب الألفاظ وضبط المشكل وكشف التصحيف من لسان العرب والقاموس المحيط وتاج العروس، والأبيات الشعرية الواردة وقائليها من كتب الأدب والدواوين — باختصار، لفظًا لفظًا'],
  ['tafsir', 'وكيل التفسير', s => s.kind === 'tafsir', 'الآيات التي يفسرها المؤلف أو يستدل بها وحده: بيان معناها ووجه الاستدلال باختصار من أمهات كتب التفسير — ونوع كل اقتراحاتك في هذه الجولة tafsir حصرًا'],
  ['aqeedah', 'وكيل العقيدة', s => s.kind === 'aqeedah', 'مواضع الاعتقاد التي يذكرها المؤلف في ثنايا بحثه وحدها: بيّن باختصار موثّق هل هذا مذهب أهل السنة والجماعة أو خلافه، من كتب الاعتقاد المعتمدة، بلا توسع ولا تكفير ولا تبديع لأعيان — ونوع كل اقتراحاتك في هذه الجولة aqeedah حصرًا'],
];

async function msStage2Specialists() {
  const p = msCurrentProject();
  if (!p) return;
  const base = msBaseCopy(p);
  const s2 = msInitStage2(p);
  const folios = base ? (base.folios || []).filter(f => (f.text || '').trim()) : [];
  if (!folios.length) { msToast('لا نص في لوحات الأم'); return; }
  const btn = document.getElementById('msStage2RunBtn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ المتخصصون يعملون...'; }
  s2.status = 'running';
  p.agent_suggestions = p.agent_suggestions || [];
  // كتب المجلس المطابقة تُطعَّم في مظان كل متخصص بحسب إسناد المستشارين
  const councilBooks = (s2.books || []).filter(b => b.resolved).map(b => b.resolved_title || b.title);
  try {
    // بطاقة المؤلف المصنّفة توجّه متخصصي السير والعقيدة والتفسير في مواضعهم
    const cardCtx = p.author_profile
      ? ` — بطاقة المؤلف: «${msAuthorName(p)}» مذهبه ${p.author_profile.madhhab || '—'} وعقيدته ${p.author_profile.aqeedah || '—'}`
      : '';
    const FOCUS_CTX = {
      tarajim: cardCtx + '؛ راعِ في التراجم طبقةَ المؤلف ومذهبه وعصره وكتبَ طبقات مذهبه',
      aqeedah: cardCtx + '؛ والمؤلف نفسه على هذا التصنيف، فبيّن موافقة كلامه لمذهب أهل السنة أو مخالفته مع مراعاة مسلك مذهبه العقدي في التأويل من غير إسقاط حكم معاصر',
      tafsir: cardCtx,
    };
    for (const f of folios) {
      for (const [key, label, pred, focus0] of MS_STAGE2_JOBS) {
        const focus = focus0 + (FOCUS_CTX[key] || '');
        const doneKey = f.label + ':' + key;
        if (s2.done[doneKey]) continue;
        const extra = [...new Set([...msGroupBookTitles(key), ...councilBooks])];
        msStage2Log(p, `${label} على لوحة (${f.label}) بنموذج ${msGroupModel(key, MS_LUNA_MODEL)}...`);
        renderMsStage2();
        const res = await fetch('/api/manuscripts/agents', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: f.text, title: p.title, author: p.author,
            model: msGroupModel(key, MS_LUNA_MODEL), api_key: msApiKey(),
            extra_books: extra.length ? extra : undefined, agent_focus: focus }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `تعذر ${label}`);
        s2.cost = (Number(s2.cost) || 0) + (Number(data.cost) || 0);
        (data.suggestions || []).filter(pred).forEach(s =>
          p.agent_suggestions.push({ ...s, id: msUid(), folio: f.label, status: 'pending', agent: key, stage2: true }));
        s2.done[doneKey] = true;
        msSave(); renderMsAgents();
      }
    }
    const gate = msStage2Gate(p);
    msStage2Log(p, `بوابة التوثيق: أُثبت ${gate.acc} اقتراحًا موثقًا/لغويًا في هامش التحقيق، وبقي ${gate.left} بانتظار اعتماد المحقق في بطاقة الوكلاء، ورُد ${gate.dis} لعدم ثبوته.`);
    msSave(); renderMsStage2(); renderMsAgents();
    msToast(`✔ أنهى متخصصو المرحلة الثانية: أُثبت ${gate.acc} تعليقًا موثقًا، وبانتظار اعتمادك ${gate.left}`, 7000);
  } catch (e) { msToast('❌ ' + e.message, 7000); }
  if (btn) { btn.disabled = false; btn.textContent = '🔍 ٣) تشغيل المتخصصين المختصرين (تخريج/لغة وأشعار/سير/تفسير/عقيدة)'; }
}

// بوابة توثيق المرحلة الثانية: لا يدخل الهامش إلا موثّق بشاهد أو لغوي/ضبطي؛
// التفسير والعقيدة والتراجم غير الموثقة تبقى للمحقق لا تُرد ولا تُثبت خلسة
function msStage2Gate(p) {
  const s2 = msInitStage2(p);
  let acc = 0, dis = 0;
  (p.agent_suggestions || []).filter(s => s.status === 'pending' && s.stage2).forEach(s => {
    const v = (s.verify || {}).status || '';
    if (v === 'verified' || v === 'found' || s.kind === 'lugha' || s.kind === 'dabt') {
      msAcceptSuggestion(p, s); acc++;
    } else if (v === 'not_found' && s.kind === 'takhrij') {
      s.status = 'dismissed';
      s.auto_reason = 'رُد في بوابة المرحلة الثانية: لم يثبت في المظان فلا يُثبت في هامش التحقيق';
      dis++;
    }
  });
  const left = (p.agent_suggestions || []).filter(s => s.status === 'pending' && s.stage2).length;
  s2.accepted = (s2.accepted || 0) + acc;
  s2.dismissed = (s2.dismissed || 0) + dis;
  return { acc, dis, left };
}

async function msStage2Approve() {
  const p = msCurrentProject();
  if (!p) return;
  const s2 = msInitStage2(p);
  const gate = msStage2Gate(p);
  const btn = document.getElementById('msStage2ApproveBtn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ مدير التحقيق يراجع ويعتمد...'; }
  try {
    const res = await fetch('/api/manuscripts/monitor', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_title: p.title, author: p.author, phase: 'اعتماد مدير التحقيق (المرحلة الثانية)',
        context: msMonitorContext(p, 'شاملة')
          + `\n\n== المرحلة الثانية ==\nاستُشير المجلس: ${(s2.advisors || []).length} عضوًا، كتب مطابقة: ${(s2.books || []).filter(b => b.resolved).length}، مراسٍ: ${(s2.anchors || []).length}. أُثبت في الهامش ${s2.accepted || 0} تعليقًا موثقًا ورُد ${s2.dismissed || 0}. المطلوب: اعتمادك مديرًا للتحقيق — هل النص المحقق بصورته الحالية صالح للإصدار الأكاديمي؟ وما أهم ما يجب تنبيه المحقق إليه باختصار؟`,
        model: msGroupModel('leader', MS_WONDER_MODEL), api_key: msApiKey(),
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر اعتماد المدير');
    s2.cost = (Number(s2.cost) || 0) + (Number(data.cost) || 0);
    s2.manager_note = String(data.findings || '').slice(0, 3000);
    s2.status = 'done';
    s2.approved_at = new Date().toISOString();
    (p.monitor_log = p.monitor_log || []).push({ id: msUid(), phase: 'اعتماد مدير التحقيق', at: new Date().toISOString(),
      model: data.model || MS_WONDER_MODEL, findings: data.findings || '', status: 'open', cost: data.cost, stage2: true });
    msStage2Log(p, `اعتمد مدير التحقيق النص المحقق (أُثبت في هذه الجولة ${gate.acc} تعليقًا إضافيًا) — ملاحظاته في بطاقة المراقبة، والنص جاهز لبناء الفهارس والإصدار من بطاقة المرحلة الأخيرة.`);
    msBuildIndexes();
    msSave(); renderMsStage2(); renderMsMonitor();
    msToast('✔ اعتمد مدير التحقيق النص — راجع اعتمادَه ثم عاين الطباعة النهائية من بطاقة الفهارس والإخراج', 7000);
  } catch (e) { msToast('❌ ' + e.message, 7000); }
  if (btn) { btn.disabled = false; btn.textContent = '✔ ٤) اعتماد مدير التحقيق وبناء الفهارس'; }
}

// ---------- التحقيق الآلي الكامل بقيادة المدقق الذكي ----------
// المدقق Muse Wonder يقود، وGoogle Argon يقرأ الصور ويدقق النسخ،
// ووكلاء التحقيق يعملون تحت قراره: نسخ واعتماد، مقابلة، حسم، تخريج،
// موازاة بمؤلفات المؤلف، مقارنة مرجعية، مقدمة وترجمة، فهارس، إصدار.
const MS_WONDER_MODEL = 'meta/muse-wonder';   // القائد والمدقق: يحسم ويكتب المقدمة
const MS_LUNA_MODEL = 'google/gemini-4-carbon'; // مساعد مدير التحقيق التنفيذي (Gemini Carbon): وكلاء وموازاة ورقابة مساعدة
const MS_ARGON_MODEL = 'google/gemini-4-argon';  // المعتمِد: يدقق الصور ويعتمد نهائيًا
const MS_AUTO_STEPS = [
  ['transcribe', 'نسخ كل اللوحات واعتماد أرغون لها'],
  ['collate', 'المقابلة بين النسخ'],
  ['decide', 'حسم مواضع الخلاف (Wonder، وما احتاج صورة حسمه أرغون منها)'],
  ['agents', 'وكلاء التحقيق بمساعدة مساعد مدير التحقيق (Gemini Carbon): تخريج وسير ولغة وأشعار وتفسير وعقيدة'],
  ['author', 'الموازاة بمؤلفات المؤلف ومسح أسلوبه'],
  ['monitor', 'رقابة القائد الشاملة'],
  ['compare', 'المقارنة المرجعية بتحقيق منشور'],
  ['intro', 'كتابة مقدمة التحقيق وترجمة المؤلف'],
  ['indexes', 'بناء الفهارس'],
  ['approve', 'اعتماد أرغون النهائي للجودة'],
  ['output', 'إصدار النسخة النهائية PDF وWord'],
];
let MS_AUTO_RUNNING = false;
let MS_AUTO_STOP = false;

function msAutoInit(p) {
  if (!p.auto) p.auto = { status: 'idle', steps: {}, log: [], report: null, cost: 0 };
  if (!p.auto.steps) p.auto.steps = {};
  if (!p.auto.log) p.auto.log = [];
  return p.auto;
}

function msAutoLog(p, msg) {
  const a = msAutoInit(p);
  a.log.push({ at: new Date().toLocaleTimeString('ar-EG'), msg });
  if (a.log.length > 200) a.log = a.log.slice(-200);
}

function msAutoStep(p, key, status, info) {
  msAutoInit(p).steps[key] = { status, info: info || '', at: new Date().toISOString() };
}

function msAutoCheck(p) {
  if (MS_AUTO_STOP) throw new Error('أوقف المحقق التحقيق الآلي');
}

function renderMsAuto() {
  const card = document.getElementById('msAutoCard');
  if (!card) return;
  const p = msCurrentProject();
  if (!p || p.mode !== 'auto') { card.hidden = true; return; }
  card.hidden = false;
  const a = msAutoInit(p);
  const base = msBaseCopy(p);
  const baseFolios = base ? (base.folios || []).length : 0;
  const icons = { done: '✔', run: '⏳', held: '⏸', err: '✖', todo: '○' };
  const colors = { done: '#2e7d5b', run: '#8a6414', held: '#8a6414', err: '#b03a2e', todo: '#999' };
  const stepsHtml = MS_AUTO_STEPS.map(([key, label]) => {
    const st = a.steps[key] || { status: 'todo' };
    return `<div class="ms-auto-step"><span style="color:${colors[st.status] || '#999'};font-weight:800">${icons[st.status] || '○'}</span> ${msEsc(label)}${st.info ? `<span class="ms-auto-step-info">${msEsc(st.info)}</span>` : ''}</div>`;
  }).join('');
  const statusText = { idle: 'ارفع النسخ ولوحاتها واوصفها، ثم اضغط «اعتمد التحقيق الآلي» فيجري التحقيق من بدايته إلى النسخة النهائية بلا أي تدخل بشري',
    running: '⏳ التحقيق الآلي الذاتي جارٍ الآن — كل خطوة تُحفظ فور إنجازها...',
    done: '✔ اكتمل التحقيق الآلي وصدرت النسخة النهائية', stopped: '⏸ أُوقف التحقيق الآلي بطلبك — محفوظ عند نقطة التوقف',
    paused_network: '⏸ انقطع الاتصال — كل شيء محفوظ عند نقطة التوقف وسيستأنف تلقائيًا فور عودته، لا يحتاجك إلا في إعادة الاتصال',
    interrupted: '⏸ توقف مفاجئ — محفوظ عند نقطة التوقف وسيستأنف ذاتيًا بعد قليل',
    error: '✖ توقف التحقيق الآلي بعد محاولتين — راجع آخر سطر في السجل' }[a.status] || a.status;
  const rolesLine = '<div class="ms-hint" style="margin:4px 0">مدير التحقيق والقائد: Muse Wonder · مساعد مدير التحقيق: Gemini Carbon · المعتمِد النهائي: Google Argon (يدقق الصور ويعتمد النسخ والجودة)</div>';
  const ckpt = a.checkpoint ? `<div class="ms-hint">نقطة الحفظ الأخيرة: ${msEsc(a.checkpoint.step)} — ${msEsc(a.checkpoint.item || '')} · ${msEsc(new Date(a.checkpoint.at).toLocaleString('ar-EG'))}${a.resumes ? ` · استئنافات ذاتية: ${a.resumes}` : ''}</div>` : '';
  const r = a.report || {};
  const reportHtml = (a.status === 'done') ? `
    <div class="ms-auto-report">
      <div class="ms-disputes-title">تقرير التحقيق الآلي</div>
      <div>لوحات منسوخة ومعتمدة من أرغون: ${r.foliosTranscribed ?? 0} · مواضع خلاف حُسمت: ${r.decided ?? 0} (منها ${r.decidedAdopted ?? 0} اعتُمدت فيها قراءة النسخ الأخرى، و${r.imageDecided ?? 0} حسمها أرغون من الصورة) · بقيت بلا حسم: ${r.held ?? 0}</div>
      <div>اقتراحات وكلاء أُثبتت في الهامش: ${r.agentsAccepted ?? 0} · موازيات مؤلف أُثبتت: ${r.authorAccepted ?? 0} · رُدت لعدم ثبوت توثيقها: ${r.autoDismissed ?? 0}</div>
      ${r.approval ? `<div>اعتماد أرغون النهائي: ${msEsc(String(r.approval).slice(0, 220))}…</div>` : ''}
      <div>${(r.compare && r.compare.length) ? `المقارنات المرجعية: ${r.compare.map(c => `«${msEsc(c.book || '')}» تطابق ${c.similarity}٪ و${c.rows} فرقًا`).join('؛ ')}` : 'المقارنة المرجعية: لم يُحدد كتابها في بطاقة المقارنة'} · الفهارس: ${r.indexEntries ?? 0} مدخلًا</div>
      <div>${(r.bioSources || []).length ? `مصادر ترجمة المؤلف: ${r.bioSources.map(msEsc).join('، ')}` : 'ترجمة المؤلف: لم تُعثر شواهد كافية في كتب التراجم'}</div>
      <div class="ms-hint">كل قرارات المدقق موثقة في مواضعها وقابلة لمراجعتك وتعديلك في أي وقت من بطاقات المشروع اليدوية بالأسفل.</div>
    </div>` : '';
  document.getElementById('msAutoBody').innerHTML = `
    <div class="ms-auto-status">${msEsc(statusText)}${a.cost ? ` · كلفة الجولات: $${Number(a.cost).toFixed(4)}` : ''}</div>
    ${rolesLine}${ckpt}
    <div class="ms-auto-steps">${stepsHtml}</div>
    ${reportHtml}
    <div class="ms-auto-log">${(a.log || []).slice(-60).map(l => `<div><span class="ms-auto-log-at">${msEsc(l.at)}</span> ${msEsc(l.msg)}</div>`).join('')}</div>`;
  const startBtn = document.getElementById('msAutoStartBtn');
  const stopBtn = document.getElementById('msAutoStopBtn');
  if (startBtn) {
    startBtn.disabled = MS_AUTO_RUNNING || !baseFolios;
    startBtn.title = MS_AUTO_RUNNING ? 'التحقيق الآلي جارٍ الآن'
      : (!baseFolios ? 'لن يُتاح الاعتماد حتى ترفع لوحة واحدة على الأقل في النسخة الأم وتتحقق منها' : 'يبدأ التحقيق الآلي الكامل من النسخ حتى النسخة النهائية');
    startBtn.textContent = a.status === 'done' ? '↻ إعادة تشغيل التحقيق الآلي الكامل'
      : ['stopped', 'error', 'paused_network', 'interrupted'].includes(a.status) ? '▶ استئناف التحقيق الآلي الآن' : '✅ اعتمد التحقيق الآلي';
  }
  if (stopBtn) stopBtn.disabled = !MS_AUTO_RUNNING;
  const logBox = document.querySelector('#msAutoBody .ms-auto-log');
  if (logBox) logBox.scrollTop = logBox.scrollHeight;
}

function msAutoStop() {
  MS_AUTO_STOP = true;
  const p = msCurrentProject();
  if (p) { msAutoLog(p, 'طلب المحقق إيقاف التحقيق الآلي...'); renderMsAuto(); }
}

function msSleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// حفظ فوري غير مؤجل — يُستدعى عند كل نقطة توقف حتى لا يضيع عمل عند انقطاع
async function msSaveNow() {
  clearTimeout(msSaveTimer);
  try {
    await fetch('/api/manuscripts', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projects: msProjects }) });
  } catch (e) { /* سيُستأنف الحفظ عند عودة الاتصال */ }
}

// طلب بخطوات التحقيق الآلي: محاولة أولى ثم محاولتان آليتان قبل أي استسلام،
// وانقطاع الشبكة يُعلَّم .network ليتحول التشغيل إلى انتظار ذاتي الاستئناف
async function msAutoFetch(url, body) {
  const tries = 3;
  let lastErr = null;
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = new Error(data.detail || ('HTTP ' + res.status));
        err.status = res.status;
        if (res.status >= 500 && i < tries - 1) { lastErr = err; await msSleep(5000 * (i + 1)); continue; }
        throw err;
      }
      return data;
    } catch (e) {
      lastErr = e;
      const isNet = (e instanceof TypeError) || /Failed to fetch|NetworkError|Load failed|network/i.test(e.message || '');
      if (i < tries - 1) { await msSleep(isNet ? 7000 * (i + 1) : 5000 * (i + 1)); continue; }
      if (isNet) { const ne = new Error('انقطع الاتصال بالشبكة'); ne.network = true; throw ne; }
      throw e;
    }
  }
  throw lastErr || new Error('تعذر الطلب');
}

async function msAutoRun(p) {
  const a = msAutoInit(p);
  if (!a.report) a.report = {};
  const R = a.report;
  const addCost = v => { a.cost = (Number(a.cost) || 0) + (Number(v) || 0); };
  const step = async (key, critical, fn) => {
    const prevSt = a.steps[key];
    if (prevSt && (prevSt.status === 'done' || prevSt.status === 'held')) {
      msAutoLog(p, `⏭ خطوة «${key}» منجزة من نقطة حفظ سابقة — تُتخطى بلا إعادة كلفة.`);
      return;
    }
    a.checkpoint = { step: key, item: '', at: new Date().toISOString() };
    msAutoStep(p, key, 'run'); await msSaveNow(); renderMsAuto();
    const cost0 = Number(a.cost) || 0;
    try {
      await fn();
      if (!R.costs) R.costs = {};
      R.costs[key] = +(((Number(a.cost) || 0) - cost0).toFixed(4));
      const prev = a.steps[key] || {};
      msAutoStep(p, key, prev.heldInfo ? 'held' : 'done', prev.heldInfo || '');
      a.checkpoint = { step: key, item: 'اكتملت', at: new Date().toISOString() };
    } catch (e) {
      if (MS_AUTO_STOP || e.network || /أوقف المحقق/.test(e.message || '')) throw e;
      msAutoStep(p, key, 'err', String(e.message || '').slice(0, 90));
      msAutoLog(p, `⚠️ تعثرت خطوة: ${e.message}`);
      if (critical) throw e;
    }
    await msSaveNow(); renderMsAuto();
  };
  const base = msBaseCopy(p);
  // المرجع المعتمد: مجموعة تحقيق المخطوطات بنماذج وكلائها وكتبهم
  await msLoadGroup();
  const LEADER = msGroupModel('leader', MS_WONDER_MODEL);
  const APPROVER = msGroupModel('approver', MS_ARGON_MODEL);
  R.group = MS_GROUP ? MS_GROUP.name : 'غير معتمدة — افتراضي خطة الجودة';
  msAutoLog(p, `المرجع المعتمد لهذا التشغيل: ${R.group} (القائد ${LEADER}، المعتمِد ${APPROVER}).`);

  // ١) النسخ والاعتماد بثلاثة النماذج (المعتمِد مدققًا على الصورة)
  await step('transcribe', true, async () => {
    const choice = msModelChoice();
    choice.auditor = APPROVER;
    let done = 0;
    for (const c of p.copies || []) {
      for (const f of c.folios || []) {
        msAutoCheck(p);
        if (f.status === 'approved' && (f.text || '').trim()) continue;
        if (!f.file_path) { msAutoLog(p, `تخطي لوحة (${f.label}) في (${c.siglum}) — لم تُرفع صورتها.`); continue; }
        msAutoLog(p, `نسخ لوحة (${f.label}) من (${c.siglum}): قارئ أول وثانٍ ومدقق على الصورة...`);
        const data = await msAutoFetch('/api/manuscripts/transcribe', {
          file_path: f.file_path, api_key: msApiKey(),
          primary_model: choice.primary, checker_model: choice.checker, auditor_model: choice.auditor });
        const primary = data.primary || {}, checker = data.checker || {}, auditor = data.auditor || {};
        // توثيق سقوط أي قارئ وإسناده الاحتياطي في اللوحة والسجل — لا نجاح صامت بنصف فريق
        f.reader_notes = [primary, checker].filter(r => r.fallback || r.error || r.fallback_error).map(r =>
          `${r.requested_model || r.model || 'قارئ'}: ${r.fallback ? `سقط (${r.first_error || 'رد فارغ'}) فأُسند احتياطيًا إلى ${r.model} وقرأ اللوحة` : (r.error || r.fallback_error || '')}`);
        if (f.reader_notes.length) msAutoLog(p, `⚠️ لوحة (${f.label}) في (${c.siglum}): ${f.reader_notes.join('؛ ')}`);
        if (!primary.text && !checker.text) throw new Error(`لوحة (${f.label}) في (${c.siglum}): لم يرجع القارئان نصًا حتى بعد الإسناد الاحتياطي — تُحفظ وتُستأنف`);
        f.primary_text = primary.text || ''; f.checker_text = checker.text || '';
        f.audited_text = auditor.text || ''; f.audit_notes = auditor.notes || '';
        f.model_primary = primary.model || choice.primary; f.model_checker = checker.model || choice.checker;
        f.model_auditor = auditor.model || choice.auditor;
        f.disputes = data.disputes || []; f.agreement = data.agreement;
        f._view = 'audited';
        f.cost = (Number(primary.cost) || 0) + (Number(checker.cost) || 0) + (Number(auditor.cost) || 0);
        f.text = f.audited_text || f.primary_text;
        f.status = 'approved';
        f.approver = choice.auditor; // اعتماد أرغون للنسخ المدقق على الصورة
        a.checkpoint = { step: 'transcribe', item: `(${c.siglum}) ${f.label}`, at: new Date().toISOString() };
        done++; addCost(f.cost);
        msAutoLog(p, `✔ اعتُمدت لوحة (${f.label}) في (${c.siglum}) — اتفاق القارئين ${data.agreement ?? '—'}٪`);
        msSave(); renderMsAuto(); renderMsCopies();
      }
    }
    R.foliosTranscribed = done;
    if (!done && !(base.folios || []).some(f => (f.text || '').trim())) throw new Error('لا نصوص معتمدة في أي نسخة');
  });

  // ٢) المقابلة بين النسخ على الأم
  await step('collate', true, async () => {
    const prior = ((p.collation || {}).entries || []);
    if (prior.length && prior.some(e => e.status !== 'pending' || e.rec)) {
      R.collationEntries = prior.filter(e => e.status === 'pending').length;
      msAutoLog(p, 'المقابلة محفوظة من جولة سابقة بقراراتها — لا تُعاد حتى لا تضيع الحُسوم.');
      return;
    }
    const others = (p.copies || []).filter(c => c.id !== base.id && (c.folios || []).some(f => (f.text || '').trim()));
    if (!others.length) { R.collationEntries = 0; msAutoLog(p, 'لا نسخ أخرى مكتملة النص — تُتخطى المقابلة ويُحقَّق النص من الأم وحدها.'); return; }
    const items = [];
    (base.folios || []).filter(f => (f.text || '').trim()).forEach(bf => {
      const comparisons = others.map(c => {
        const of = (c.folios || []).find(x => x.label === bf.label);
        return of && (of.text || '').trim()
          ? { copy_id: c.id, siglum: c.siglum, text: of.text }
          : { copy_id: c.id, siglum: c.siglum, text: '' };
      });
      items.push({ folio: bf.label, base_text: bf.text, comparisons });
    });
    const data = await msAutoFetch('/api/manuscripts/collate', { items });
    let autoRuled = 0;
    p.collation = { at: new Date().toISOString(), baseCopyId: base.id,
      entries: (data.entries || []).map(e => {
        if (e.type === 'ضبط/رسم') { autoRuled++; return { ...e, id: msUid(), status: 'dismissed',
          rec: { decision: 'قاعدة المحقق: فروق الضبط/رسم المحض تُردّ ولا تدخل الهامش', auto_rule: 'orthography_only', at: new Date().toISOString(), auto: true } }; }
        return { ...e, id: msUid(), status: 'pending' };
      }) };
    R.collationEntries = p.collation.entries.filter(e => e.status === 'pending').length;
    msAutoLog(p, `المقابلة: ${R.collationEntries} فرقًا جوهريًا بانتظار حسم المدقق، ورُدّ آليًا ${autoRuled} فرق ضبط/رسم محض.`);
    renderMsCollation();
  });

  // ٣) حسم مواضع الخلاف: Wonder يقضي، وما احتاج صورة اعتمده أرغون منها بنفسه
  await step('decide', false, async () => {
    const entries = ((p.collation || {}).entries || []).filter(e => e.status === 'pending');
    let decided = 0, adopted = 0, imageDecided = 0, failed = 0;
    for (const e of entries) {
      msAutoCheck(p);
      a.checkpoint = { step: 'decide', item: `(${e.folio}) ${e.type} مع (${e.siglum})`, at: new Date().toISOString() };
      const bf = (base.folios || []).find(x => x.label === e.folio);
      let excerpt = '';
      if (bf && bf.text) {
        const anchor = (e.context && bf.text.includes(e.context)) ? e.context : (e.base || '');
        const idx = anchor ? bf.text.indexOf(anchor) : -1;
        excerpt = idx >= 0 ? bf.text.slice(Math.max(0, idx - 700), idx + 900) : bf.text.slice(0, 1500);
      }
      try {
        const data = await msAutoFetch('/api/manuscripts/recommend', {
          title: p.title, author: p.author, folio: e.folio, type: e.type,
          base: e.base, other: e.other, siglum: e.siglum, context: e.context, excerpt, api_key: msApiKey(),
          model: LEADER });
        addCost(data.cost);
        const [opt] = MS_REC_ACTIONS[data.action] || MS_REC_ACTIONS.needs_image;
        if (data.action === 'needs_image' || opt === 'comment_only') {
          // مساعدة ذاتية: أرغون المعتمِد يفحص صورة اللوحة ويحسم بنفسه
          const imgPath = bf && (bf.enhanced_file_path || bf.file_path);
          if (!imgPath) throw new Error('لا صورة للوحة الأم لهذا الموضع');
          const verdict = await msAutoFetch('/api/manuscripts/image-decide', {
            file_path: imgPath, title: p.title, author: p.author, folio: e.folio, type: e.type,
            base: e.base, other: e.other, siglum: e.siglum, excerpt, api_key: msApiKey(), model: APPROVER });
          addCost(verdict.cost);
          const opt2 = verdict.reading === 'other' ? 'adopt_other' : 'keep_note';
          const corrected = msApplyRecommendation(p, e,
            { action: verdict.reading === 'other' ? 'adopt_other' : 'keep_base_note', margin_note: '', model: MS_ARGON_MODEL, confidence: verdict.confidence },
            opt2, { auto: true, useNote: false,
              decisionLabel: `اعتماد أرغون من صورة اللوحة: ${verdict.reason || 'طابقت القراءة خط اللوحة'}` });
          e.rec.approver = MS_ARGON_MODEL; e.rec.image_decided = true;
          decided++; imageDecided++; if (corrected) adopted++;
          msAutoLog(p, `حسم أرغون من الصورة لوحة (${e.folio}) ${e.type} مع (${e.siglum}): قراءة ${verdict.reading === 'other' ? 'النسخة الأخرى' : 'الأم'} — ${verdict.reason || ''}`);
        } else {
          const corrected = msApplyRecommendation(p, e, data, opt, { auto: true,
            decisionLabel: 'قرار التحقيق الآلي بقيادة المدقق الذكي' });
          decided++; if (corrected) adopted++;
          msAutoLog(p, `حُسمت لوحة (${e.folio}) ${e.type} مع (${e.siglum}): ${data.recommendation || opt}`);
        }
      } catch (err) {
        if (err.network || MS_AUTO_STOP) throw err;
        failed++;
        msAutoLog(p, `⚠️ تعذر حسم موضع (${e.folio}) ${e.type} آليًا: ${err.message} — سيُعاد في الاستئناف.`);
      }
      await msSaveNow(); renderMsAuto(); renderMsCollation();
    }
    R.decided = (R.decided || 0) + decided; R.decidedAdopted = (R.decidedAdopted || 0) + adopted;
    R.imageDecided = (R.imageDecided || 0) + imageDecided;
    R.held = ((p.collation || {}).entries || []).filter(e => e.status === 'pending').length;
    if (R.held) a.steps.decide.heldInfo = `${R.held} موضعًا ينتظر الاستئناف الآلي`;
  });

  // ٤) وكلاء التحقيق ثم اعتماد الموثّق واللغوي بقرار المدقق
  const decideSuggestions = (kinds, label) => {
    let acc = 0, dismissedN = 0;
    (p.agent_suggestions || []).filter(s => s.status === 'pending' && kinds.includes(s.kind)).forEach(s => {
      const v = (s.verify || {}).status || '';
      if (v === 'verified' || v === 'found' || s.kind === 'lugha' || s.kind === 'dabt'
          || (s.kind === 'author' && (s.parallels || []).length)) {
        msAcceptSuggestion(p, s); acc++;
      } else {
        // قاعدة الاعتماد الآلي: ما لم يثبت توثيقه لا يدخل الهامش — يُرد موثقًا لا يُعلَّق لبشري
        s.status = 'dismissed';
        s.auto_reason = 'رُد آليًا: لم يثبت توثيقه في المظان فلا يُثبت في هامش التحقيق';
        dismissedN++;
      }
    });
    R.autoDismissed = (R.autoDismissed || 0) + dismissedN;
    msAutoLog(p, `${label}: أُثبت ${acc} اقتراحًا موثقًا في الهامش، ورُد ${dismissedN} لعدم ثبوت توثيقه.`);
    return acc;
  };
  await step('agents', false, async () => {
    p.agent_suggestions = p.agent_suggestions || [];
    a.agentDone = a.agentDone || {};
    // وكلاء المجموعة المعتمدة المتخصصون: لكلٍّ نموذجه وكتبه وتركيزه
    // متخصصو المرحلة الثانية الستة المختصرون (التعريف الموحد في MS_STAGE2_JOBS)
    const JOBS = MS_STAGE2_JOBS;
    for (const f of (base.folios || []).filter(x => (x.text || '').trim())) {
      for (const [key, label, pred, focus] of JOBS) {
        msAutoCheck(p);
        const doneKey = f.label + ':' + key;
        if (a.agentDone[doneKey]) continue;
        a.checkpoint = { step: 'agents', item: `${label} — لوحة (${f.label})`, at: new Date().toISOString() };
        msAutoLog(p, `${label} (نموذج ${msGroupModel(key, MS_LUNA_MODEL)}) على لوحة (${f.label})...`);
        const data = await msAutoFetch('/api/manuscripts/agents', {
          text: f.text, title: p.title, author: p.author,
          model: msGroupModel(key, MS_LUNA_MODEL), api_key: msApiKey(),
          extra_books: msGroupBookTitles(key).length ? msGroupBookTitles(key) : undefined,
          agent_focus: focus });
        addCost(data.cost);
        (data.suggestions || []).filter(pred).forEach(s =>
          p.agent_suggestions.push({ ...s, id: msUid(), folio: f.label, status: 'pending', agent: key }));
        a.agentDone[doneKey] = true;
        await msSaveNow(); renderMsAuto();
      }
    }
    R.agentsAccepted = decideSuggestions(['takhrij', 'tarjama', 'lugha', 'dabt', 'tafsir', 'aqeedah'], 'متخصصو المرحلة الثانية');
    renderMsAgents();
  });

  // ٥) وكيل المؤلف + مسح الأسلوب على الصيغ المتنازعة
  await step('author', false, async () => {
    p.agent_suggestions = p.agent_suggestions || [];
    if (!(p.author || '').trim()) { msAutoLog(p, 'لا اسم مؤلف في المشروع — تُتخطى الموازاة بكتب المؤلف.'); R.authorAccepted = 0; return; }
    for (const f of (base.folios || []).filter(x => (x.text || '').trim())) {
      msAutoCheck(p);
      if ((p.agent_suggestions || []).some(s => s.folio === f.label && s.kind === 'author')) continue;
      msAutoLog(p, `وكيل مقارنة أقوال المؤلف بكتبه (متغير بحسب «${p.author}») على لوحة (${f.label})...`);
      const data = await msAutoFetch('/api/manuscripts/author-agent', {
        text: f.text, title: p.title, author: msAuthorName(p),
        model: msGroupModel('authorworks', MS_LUNA_MODEL), api_key: msApiKey(),
        extra_books: msGroupBookTitles('authorworks').length ? msGroupBookTitles('authorworks') : undefined });
      addCost(data.cost);
      (data.suggestions || []).forEach(s => p.agent_suggestions.push({ ...s, id: msUid(), folio: f.label, status: 'pending' }));
      msSave(); renderMsAuto();
    }
    R.authorAccepted = decideSuggestions(['author'], 'وكيل المؤلف');
    renderMsAuthor();
    const swaps = ((p.collation || {}).entries || []).filter(e => e.status === 'accepted' && e.type === 'تبديل'
      && (e.base || '').length >= 4 && (e.base || '').length <= 70 && (e.other || '').length <= 70);
    let styled = 0;
    for (const e of swaps.slice(0, 12)) {
      msAutoCheck(p);
      try {
        const data = await msAutoFetch('/api/manuscripts/author-style',
          { author: p.author, title: p.title, phrases: [e.base, e.other] });
        if (data && data.dominant) {
          const win = (data.results || []).find(r => r.phrase === data.dominant);
          const occ = win && (win.occurrences || [])[0];
          e.rec = Object.assign({}, e.rec || {}, { style: { dominant: data.dominant,
            totals: (data.results || []).map(r => ({ phrase: r.phrase, total: r.total })) } });
          if (occ) e.custom_apparatus = `في (${e.siglum}): «${e.other}» بدل «${e.base}» — والأقرب لصياغة المؤلف في كتبه: «${data.dominant}»؛ انظر: ${occ.book} ص (${occ.page || '—'})`;
          styled++;
        }
      } catch (err) { /* مسح الأسلوب معزز اختياري */ }
    }
    if (styled) msAutoLog(p, `مسح الأسلوب: وُثّقت ${styled} صيغة متنازعة من كتب المؤلف في هوامشها.`);
  });

  // ٦) مراقبة الجودة الشاملة (Muse Wonder)
  await step('monitor', false, async () => {
    if ((p.monitor_log || []).some(m => m.auto && m.phase === 'شاملة')) { msAutoLog(p, 'رقابة الجودة محفوظة من جولة سابقة.'); return; }
    msAutoCheck(p);
    const data = await msAutoFetch('/api/manuscripts/monitor', {
      project_title: p.title, author: p.author, phase: 'شاملة',
      context: msMonitorContext(p, 'شاملة'), model: LEADER, api_key: msApiKey() });
    addCost(data.cost);
    (p.monitor_log = p.monitor_log || []).push({ id: msUid(), phase: 'شاملة', at: new Date().toISOString(),
      model: data.model || MS_WONDER_MODEL, findings: data.findings || '', status: 'open',
      cost: data.cost, seconds: data.seconds, auto: true });
    R.monitorFindings = (String(data.findings || '').match(/^\s*[-•*\d]/gm) || []).length || (data.findings ? 1 : 0);
    msAutoLog(p, `المراقبة الشاملة: دوّن المدقق ملاحظاته في بطاقة المراقبة (${data.seconds ?? '—'}ث).`);
    renderMsMonitor();
  });

  // ٧) المقارنة المرجعية بتحقيق منشور (إن حُدّد كتابه)
  await step('compare', false, async () => {
    // حتى ثلاثة تحقيقات مرجعية مضبوطة في المشروع؛ فإن لم تُضبط جرّب عنوان الكتاب نفسه
    let books = msCompareBooks(p).slice(0, 3);
    if (!books.length) {
      const bookEl = document.getElementById('msCompareBook');
      const cand = String((bookEl && bookEl.value) || p.title || '').trim();
      if (cand) books = [cand];
    }
    if (!books.length) { msAutoLog(p, 'لا مرشح للمقارنة المرجعية — تُتخطى.'); return; }
    const ourText = (base.folios || []).map(f => f.text || '').join('\n');
    const datas = [], results = [];
    for (const book of books) {
      msAutoCheck(p);
      try {
        const data = await msAutoFetch('/api/manuscripts/compare-edition', { text: ourText, book });
        if (!data.found) { msAutoLog(p, `المقارنة بـ «${book}»: لا محاذاة — يُنتقل لغيره.`); continue; }
        datas.push(data);
        results.push({ book: (data.book || {}).title || book, similarity: data.similarity, rows: (data.rows || []).length });
        msAutoLog(p, `المقارنة المرجعية بـ «${results[results.length - 1].book}»: تطابق ${data.similarity}٪ و${results[results.length - 1].rows} فرقًا.`);
      } catch (err) {
        if (err.network || MS_AUTO_STOP) throw err;
        msAutoLog(p, `المقارنة بـ «${book}» تعثرت: ${err.message}`);
      }
    }
    if (datas.length) {
      MS_COMPARE = { ...datas[0], list: datas };
      p.compareSummary = results;
      R.compare = results;
    } else {
      msAutoLog(p, 'تعذرت المقارنة المرجعية بكل المرشحين — تُتخطى ولا توقف التحقيق.');
    }
  });

  // ٨) مقدمة التحقيق وترجمة المؤلف من كتب التراجم
  await step('intro', false, async () => {
    if (p.intro && a.introDone) { msAutoLog(p, 'المقدمة وترجمة المؤلف محفوظتان من جولة سابقة.'); return; }
    const stepsSummary = [
      `نُسخت لوحات ${(p.copies || []).length} نسخة بقارئين ومدقق على الصورة واعتُمدت.`,
      R.collationEntries != null ? `قوبلت النسخ على الأم؛ حُسم ${R.decided || 0} موضع خلاف بقرار المدقق، واعتُمدت قراءة النسخ في المتن ${R.decidedAdopted || 0} مرة، وعُلّق ${R.held || 0} موضعًا لعين المحقق.` : '',
      `أُثبت في الهامش ${R.agentsAccepted || 0} تخريجًا وتعليقًا من وكلاء التحقيق، و${R.authorAccepted || 0} موازاة من مؤلفات المؤلف.`,
      (R.compare && R.compare.length) ? `قورن النص بتحقيقات مرجعية: ${R.compare.map(c => `«${c.book}» (تطابق ${c.similarity}٪)`).join('، ')}.` : '',
    ].filter(Boolean).join('\n');
    const data = await msAutoFetch('/api/manuscripts/intro', {
      title: p.title, author: msAuthorName(p), api_key: msApiKey(),
      attribution: (p.author_profile && p.author_profile.attribution) || undefined,
      bio_names: p.author_profile ? [p.author_profile.correct_name, p.author_profile.famous_name, p.author].filter(Boolean) : undefined,
      classification: p.author_profile ? [
        p.author_profile.madhhab ? `المذهب الفقهي: ${p.author_profile.madhhab}` : '',
        p.author_profile.aqeedah ? `العقيدة: ${p.author_profile.aqeedah}` : '',
        p.author_profile.classification_basis ? `قرينة التصنيف: ${p.author_profile.classification_basis}` : '',
      ].filter(Boolean).join('\n') || undefined : undefined,
      model: msGroupModel('bio', LEADER),
      bio_books: msGroupBookTitles('bio').length ? msGroupBookTitles('bio') : undefined,
      copies: (p.copies || []).map(c => ({ siglum: c.siglum, library: c.library, shelfmark: c.shelfmark,
        date: c.date, script: c.script, notes: c.notes })),
      sigla: (p.copies || []).map(c => `(${c.siglum}) = ${c.library || ''} ${c.shelfmark || ''}`).join('؛ '),
      steps: stepsSummary });
    addCost(data.cost);
    p.intro = data.intro;
    a.introDone = true;
    R.bioSources = data.bio_sources || [];
    msAutoLog(p, `كُتبت مقدمة التحقيق وترجمة المؤلف من ${data.bio_snippets || 0} شاهدًا في كتب التراجم: ${(data.bio_sources || []).join('، ') || '—'}.`);
    const ta = document.getElementById('msIntroText'); if (ta) ta.value = p.intro;
  });

  // ٩) الفهارس
  await step('indexes', false, async () => {
    const accepted = (p.agent_suggestions || []).filter(s => s.status === 'accepted');
    if (!accepted.length) { R.indexEntries = 0; msAutoLog(p, 'لا اقتراحات معتمدة لبناء الفهارس منها.'); return; }
    p.indexes = { at: new Date().toISOString(), groups: msIndexGroups(p) };
    R.indexEntries = Object.values(p.indexes.groups || {}).reduce((n, g) => n + (Array.isArray(g) ? g.length : 0), 0);
    msRenderIndexes();
    msAutoLog(p, `بُنيت الفهارس: ${R.indexEntries} مدخلًا.`);
  });

  // ١٠) اعتماد أرغون النهائي للجودة قبل الإصدار
  await step('approve', false, async () => {
    if (a.approveDone) { msAutoLog(p, 'اعتماد أرغون النهائي محفوظ من جولة سابقة.'); return; }
    msAutoCheck(p);
    const ctx = msMonitorContext(p, 'شاملة')
      + '\n\n== مقدمة التحقيق وترجمة المؤلف ==\n' + String(p.intro || '').slice(0, 4000)
      + '\n\n== ملخص قرارات التحقيق الآلي ==\n' + JSON.stringify(R || {}).slice(0, 1600);
    const data = await msAutoFetch('/api/manuscripts/monitor', {
      project_title: p.title, author: p.author, phase: 'اعتماد أرغون النهائي',
      context: ctx, model: APPROVER, api_key: msApiKey() });
    addCost(data.cost);
    (p.monitor_log = p.monitor_log || []).push({ id: msUid(), phase: 'اعتماد أرغون', at: new Date().toISOString(),
      model: data.model || MS_ARGON_MODEL, findings: data.findings || '', status: 'open',
      cost: data.cost, seconds: data.seconds, auto: true, approver: true });
    a.approveDone = true;
    R.approval = String(data.findings || '').slice(0, 400);
    msAutoLog(p, '✔ فحص أرغون النسخة كاملة واعتمدها اعتمادًا نهائيًا للجودة (ملاحظاته في بطاقة المراقبة).');
    renderMsMonitor();
  });

  // ١١) إصدار النسخة النهائية PDF وWord بمسار الأبحاث نفسه
  await step('output', true, async () => {
    await msExportPdf();
    msAutoLog(p, '✔ نُزّل PDF النسخة النهائية المحققة.');
    msAutoCheck(p);
    msPreviewPrint();
    const frame = document.getElementById('chatReadingFrame');
    if (!frame) throw new Error('تعذر فتح إطار تقسيم الصفحات لملف Word');
    const t0 = Date.now();
    await new Promise((resolve, reject) => {
      const timer = setInterval(() => {
        let done = false;
        try { done = frame.contentWindow && frame.contentWindow.__pagedDone === true; } catch (e) {}
        if (done) { clearInterval(timer); resolve(); }
        else if (Date.now() - t0 > 120000) { clearInterval(timer); reject(new Error('لم يكتمل تقسيم الصفحات لملف Word')); }
      }, 400);
    });
    await exportWordFromDoc(frame.contentDocument);
    const overlay = document.getElementById('chatReadingOverlay');
    if (overlay) overlay.hidden = true;
    msAutoLog(p, '✔ نُزّل Word النسخة النهائية المحققة بحواشٍ صفحية مرقمة.');
  });

  a.status = 'done';
  a.finishedAt = new Date().toISOString();
  msAutoLog(p, 'اكتمل التحقيق الآلي: النسخة النهائية بين يديك PDF وWord، وكل القرارات موثقة قابلة لمراجعتك.');
}

// حارس الاستئناف الذاتي: يوقظ التشغيل المتوقف بالانقطاع أو بإغلاق التطبيق
let MS_AUTO_WATCH = null;
function msAutoArmWatchdog() {
  if (MS_AUTO_WATCH) return;
  MS_AUTO_WATCH = setInterval(() => msAutoMaybeResume('حارس الاستئناف'), 45000);
  window.addEventListener('online', () => msAutoMaybeResume('عودة الاتصال'));
}

function msAutoMaybeResume(src) {
  if (MS_AUTO_RUNNING) return;
  const p = msCurrentProject();
  if (!p || p.mode !== 'auto') return;
  const a = msAutoInit(p);
  if (a.status === 'paused_network' || a.status === 'interrupted') {
    msAutoLog(p, `استئناف ذاتي (${src}) من نقطة الحفظ: ${a.checkpoint ? a.checkpoint.step + ' — ' + a.checkpoint.item : ''}`);
    msAutoStart();
  }
}

// تشغيل/استئناف التحقيق الآلي: من البداية إلى الإخراج بلا أي تدخل بشري.
// كل خطوة وبند محفوظ فور إنجازه، فالانقطاع أو إعادة التشغيل تعود لنقطة الحفظ.
async function msAutoStart() {
  const p = msCurrentProject();
  if (!p || MS_AUTO_RUNNING) return;
  const base = msBaseCopy(p);
  if (!base || !(base.folios || []).length) { msToast('ارفع لوحات النسخة الأم أولًا واوصف بقية النسخ ولوحاتها، ثم اضغط «اعتمد التحقيق الآلي»'); return; }
  msAutoArmWatchdog();
  MS_AUTO_RUNNING = true; MS_AUTO_STOP = false;
  const a = msAutoInit(p);
  const resumable = a.status && a.status !== 'done' && a.status !== 'idle'
    && Object.keys(a.steps || {}).length;
  if (resumable) {
    a.resumes = (a.resumes || 0) + 1;
    msAutoLog(p, `استئناف التحقيق الآلي من نقطة الحفظ (الاستئناف رقم ${a.resumes}) — الخطوات المنجزة لن تُعاد.`);
  } else {
    a.steps = {}; a.report = {}; a.failCount = 0; a.resumes = 0;
    a.startedAt = new Date().toISOString();
    msAutoLog(p, 'بدأ التحقيق الآلي الذاتي: مدير التحقيق Muse Wonder، مساعده Gemini Carbon، المعتمِد Google Argon — من النسخ إلى الإخراج بلا تدخل بشري.');
  }
  a.status = 'running';
  await msSaveNow(); renderMsAuto();
  try {
    await msAutoRun(p);
  } catch (e) {
    if (MS_AUTO_STOP || /أوقف المحقق/.test(e.message || '')) {
      a.status = 'stopped';
      msAutoLog(p, '⏸ أُوقف التحقيق الآلي بطلبك — كل ما أُنجز محفوظ عند نقطة التوقف.');
    } else if (e.network) {
      a.status = 'paused_network';
      msAutoLog(p, '⏸ انقطع الاتصال بعد المحاولة والمحاولتين الآليتين. كل شيء محفوظ عند نقطة التوقف، وسيستأنف التحقيق تلقائيًا فور عودة الاتصال — لا يحتاجك إلا في إعادة الاتصال نفسه إن طال انقطاعه.');
    } else {
      a.failCount = (a.failCount || 0) + 1;
      if (a.failCount >= 2) {
        a.status = 'error';
        msAutoLog(p, '❌ توقف التحقيق الآلي بعد محاولتين عند: ' + e.message + ' — هذا وحده ما قد يحتاج نظرك.');
      } else {
        a.status = 'interrupted';
        msAutoLog(p, '⚠️ توقف مفاجئ: ' + e.message + ' — محفوظ عند نقطة التوقف وسيستأنف ذاتيًا.');
      }
    }
  }
  MS_AUTO_RUNNING = false;
  await msSaveNow(); renderMsAuto();
  renderMsCopies(); renderMsCollation(); renderMsAgents(); renderMsAuthor(); renderMsMonitor();
  if (a.status === 'interrupted' || a.status === 'paused_network') {
    setTimeout(() => msAutoMaybeResume('محاولة لاحقة'), 20000);
  }
}

// ---------- وثيقة خطة التحقيق والنقاش مع المحقق الآلي ----------
function msReportSections(p) {
  const a = p.auto || {};
  const R = a.report || {};
  const base = msBaseCopy(p);
  const entries = ((p.collation || {}).entries || []);
  const sugs = p.agent_suggestions || [];
  const accSugs = sugs.filter(s => s.status === 'accepted');
  const verifiedAcc = accSugs.filter(s => ['verified', 'found'].includes((s.verify || {}).status) || s.kind === 'lugha' || s.kind === 'dabt');
  const stepName = Object.fromEntries(MS_AUTO_STEPS);
  const stTxt = { done: 'منجزة ✔', held: 'منجزة بملاحظات ⏸', err: 'تعثرت ✖', run: 'كانت جارية', todo: 'لم تُشغَّل' };
  const lines = [];
  const S = [];
  S.push({ name: 'بيانات المشروع والنسخ المعتمدة', body: [
    `الكتاب: ${p.title}`,
    `المؤلف: ${p.author || '—'}`,
    p.desc ? `الوصف: ${p.desc}` : '',
    `نوع التحقيق: ${p.mode === 'auto' ? 'آلي كامل ذاتي' : 'بخطوات مراجعة بشرية'}`,
    `المرجع المعتمد: ${(MS_GROUP && MS_GROUP.name) || R.group || 'مجموعة تحقيق المخطوطات'}`,
    `النسخة الأم: (${(base || {}).siglum || '—'})`,
    ...(p.copies || []).map(c => {
      const pr = msFolioProgress(c);
      return `نسخة (${c.siglum}) — ${c.library || ''} ${c.shelfmark ? 'رقم ' + c.shelfmark : ''} ${c.date || ''} ${c.script || ''} — ${pr.total} لوحة، معتمدة ${pr.approved}${c.notes ? ' — ' + c.notes : ''}`;
    }),
  ].filter(Boolean).join('\n') });
  S.push({ name: 'خطة التحقيق وخطواتها من البداية إلى النهاية', body: [
    `بدأ: ${a.startedAt ? new Date(a.startedAt).toLocaleString('ar-EG') : '—'} · انتهى: ${a.finishedAt ? new Date(a.finishedAt).toLocaleString('ar-EG') : '—'} · الحالة: ${a.status || '—'} · استئنافات ذاتية: ${a.resumes || 0}`,
    ...MS_AUTO_STEPS.map(([k, label]) => {
      const st = (a.steps || {})[k];
      const cost = R.costs && R.costs[k] != null ? ` — كلفتها $${Number(R.costs[k]).toFixed(4)}` : '';
      return `${label}: ${st ? (stTxt[st.status] || st.status) : 'لم تُشغَّل'}${st && st.info ? ' (' + st.info + ')' : ''}${cost}`;
    }),
    `نقطة الحفظ الأخيرة: ${a.checkpoint ? a.checkpoint.step + ' — ' + (a.checkpoint.item || '') : '—'}`,
  ].join('\n') });
  const byStatus = st => entries.filter(e => e.status === st);
  S.push({ name: 'قرارات المقابلة بين النسخ', body: [
    `إجمالي الفروق: ${entries.length} — مقبولة في الهامش: ${byStatus('accepted').length}، مردودة: ${byStatus('dismissed').length}، بلا حسم: ${byStatus('pending').length}`,
    ...entries.slice(0, 220).map(e => `لوحة (${e.folio}) ${e.type} مع (${e.siglum}): الأم «${(e.base || '—').slice(0, 90)}» / الأخرى «${(e.other || '—').slice(0, 90)}» — ${e.status}${e.rec && e.rec.decision ? ' — ' + e.rec.decision : ''}${e.rec && e.rec.approver ? ' [اعتماد المعتمِد من الصورة]' : ''}`),
  ].join('\n') });
  const imgDec = entries.filter(e => e.rec && e.rec.image_decided);
  S.push({ name: 'اعتماد المعتمِد (أرغون) من صور اللوحات', body: [
    `مواضع حسمها المعتمِد بفحص صورة اللوحة: ${imgDec.length}`,
    ...imgDec.slice(0, 80).map(e => `لوحة (${e.folio}) ${e.type} مع (${e.siglum}): ${e.rec.decision || ''}`),
    `لوحات اعتمد نسخَها المعتمِد على الصورة: ${(p.copies || []).reduce((n, c) => n + (c.folios || []).filter(f => f.status === 'approved').length, 0)}`,
  ].join('\n') });
  S.push({ name: 'التخريج والتوثيق وموازيات المؤلف', body: [
    `اقتراحات الوكلاء: ${sugs.length} — أُثبت في الهامش: ${accSugs.length} (موثقة أو لغوية/ضبطية: ${verifiedAcc.length})، رُدت: ${sugs.filter(s => s.status === 'dismissed').length}، معلقة: ${sugs.filter(s => s.status === 'pending').length}`,
    ...accSugs.slice(0, 160).map(s => `[${MS_AGENT_KINDS[s.kind] || s.kind}] لوحة (${s.folio}) «${(s.anchor || '').slice(0, 80)}» — ${(s.body || '').slice(0, 160)}${s.source ? ' (' + s.source + ')' : ''}${s.verify && s.verify.detail ? ' — توثيق: ' + s.verify.detail : ''}`),
    ...entries.filter(e => e.rec && e.rec.style).slice(0, 40).map(e => `مسح أسلوب المؤلف — لوحة (${e.folio}): الصيغة الغالبة في كتبه «${e.rec.style.dominant}»`),
  ].join('\n') });
  const cmps = (p.compareSummary && p.compareSummary.length) ? p.compareSummary : (R.compare || []);
  S.push({ name: 'المقارنات المرجعية بالتحقيقات المنشورة', body: cmps.length
    ? cmps.map(c => `«${c.book}»: نسبة التطابق ${c.similarity}٪ وعدد الفروق ${c.rows} (جداولها التفصيلية في بطاقة المقارنة)`).join('\n')
    : 'لم تُجرَ مقارنة مرجعية بعد.' });
  S.push({ name: 'رقابة الجودة واعتماد المعتمِد النهائي', body: (p.monitor_log || []).length
    ? (p.monitor_log || []).slice(-5).map(m => `[${m.phase}] بنموذج ${m.model || '—'}:\n${String(m.findings || '').slice(0, 1400)}`).join('\n\n')
    : 'لا ملاحظات رقابة مسجلة بعد.' });
  S.push({ name: 'المقدمة وترجمة المؤلف', body: [
    `مصادر الترجمة من كتب التراجم: ${(R.bioSources || []).join('، ') || '—'}`,
    p.intro ? String(p.intro).slice(0, 2600) + '\n…(النص الكامل في بطاقة المقدمة ويتصدر النسخة النهائية)' : 'لم تُكتب المقدمة بعد.',
  ].join('\n') });
  const s2r = p.stage2 || {};
  S.push({ name: 'المرحلة الثانية: تحقيق النص (مدير التحقيق والمجلس والذهبي والمتخصصون)', body: s2r.handed_at ? [
    `التسليم من مدير المرحلة الأولى: ${s2r.handed_at} — نص الأم مع هوامش مقابلته وتحققيقه القائمة.`,
    `مجلس المستشارين: ${(s2r.advisors || []).length} عضوًا درس كلٌّ منهم النسخة كاملة استقلالًا؛ كتب مطابقة في الشاملة: ${(s2r.books || []).filter(b => b.resolved).length} من ${(s2r.books || []).length} مرشحًا${(s2r.missing || []).length ? ' — لم يوجد بمؤلفيها: ' + s2r.missing.join('، ') : ''}.`,
    `مراسي التحقيق الموحدة: ${(s2r.anchors || []).join('، ') || '—'}`,
    s2r.golden ? `الوكيل الذهبي المؤقت: بُحث في كتب المجلس حصرًا (${(s2r.golden.scope_books || []).join('، ')}) بتوجيه مدير التحقيق الموثق في بطاقة المرحلة الثانية.` : 'الوكيل الذهبي: لم يُنشأ بعد.',
    `بوابة التوثيق: أُثبت ${s2r.accepted || 0} تعليقًا موثقًا في هامش التحقيق، ورُد ${s2r.dismissed || 0} لعدم ثبوته، وكلفة المرحلة $${Number(s2r.cost || 0).toFixed(4)}.`,
    s2r.manager_note ? `اعتماد مدير التحقيق:\n${String(s2r.manager_note).slice(0, 1800)}` : 'اعتماد مدير التحقيق: لم يُسجل بعد.',
  ].join('\n') : 'لم تُسلَّم النسخة الجاهزة إلى مدير التحقيق بعد — المرحلة الثانية تبدأ بالتسليم من بطاقتها.' });
  const groups = (p.indexes || {}).groups || {};
  S.push({ name: 'الفهارس', body: Object.keys(groups).length
    ? Object.entries(groups).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.length : 0} مدخلًا`).join('\n')
    : 'لم تُبنَ الفهارس بعد.' });
  const totalFolios = (base && base.folios || []).length;
  const approvedFolios = (base && base.folios || []).filter(f => f.status === 'approved').length;
  const gates = [
    [`كل لوحات الأم منسوخة ومعتمدة من المعتمِد (${approvedFolios}/${totalFolios})`, totalFolios > 0 && approvedFolios === totalFolios],
    [`لا مواضع خلاف معلقة بلا حسم (${byStatus('pending').length})`, byStatus('pending').length === 0],
    [`كل المُثبت في الهامش موثق بشاهد أو لغوي/ضبطي (${verifiedAcc.length}/${accSugs.length})`, verifiedAcc.length === accSugs.length],
    ['اعتماد المعتمِد النهائي للجودة مسجل', (p.monitor_log || []).some(m => m.approver)],
    ['المرحلة الثانية (تحقيق النص) معتمدة من مدير التحقيق', (p.stage2 || {}).status === 'done'],
    ['مقدمة التحقيق وترجمة المؤلف مكتوبتان', !!(p.intro || '').trim()],
    ['الفهارس مبنية', Object.keys(groups).length > 0],
    ['النسخة النهائية صدرت', !!((a.steps || {}).output && a.steps.output.status === 'done') || p.mode !== 'auto'],
  ];
  S.push({ name: 'بوابات الجودة', body: gates.map(([t, ok]) => `${ok ? '✔' : '✖'} ${t}`).join('\n') });
  S.push({ name: 'التصحيحات المتفق عليها مع الباحث في النقاش', body: (p.corrections && p.corrections.length)
    ? p.corrections.map(c => `${new Date(c.at).toLocaleString('ar-EG')} — لوحة (${c.folio}) ${c.type}: ${c.option}${c.reason ? ' — ' + c.reason : ''}`).join('\n')
    : 'لا تصحيحات نقاشية بعد — افتح النقاش مع المحقق الآلي أسفل هذه البطاقة لتصحيح أي نقطة.' });
  S.push({ name: 'الكلفة والسجل', body: [
    `الكلفة الإجمالية للجولات الآلية: $${Number(a.cost || 0).toFixed(4)}`,
    ...MS_AUTO_STEPS.filter(([k]) => R.costs && R.costs[k] != null).map(([k, label]) => `${label}: $${Number(R.costs[k]).toFixed(4)}`),
    `آخر تحديث للوثيقة: ${new Date().toLocaleString('ar-EG')}`,
  ].join('\n') });
  return S;
}

function msReportText(p) {
  return msReportSections(p).map(s => s.name + '\n' + s.body).join('\n\n');
}

function msShowReport() {
  const p = msCurrentProject();
  if (!p) return;
  const sections = msReportSections(p);
  p.final_report = { at: new Date().toISOString(), text: sections.map(s => s.name + '\n' + s.body).join('\n\n') };
  msSave();
  if (typeof buildAcademicPaperHtml !== 'function' || typeof openChatReadingOverlay !== 'function') {
    msToast('تعذر فتح الوثيقة في هذه الصفحة');
    return;
  }
  const runData = { projectTitle: 'وثيقة خطة التحقيق — ' + p.title,
    rounds: sections.map((s, i) => ({ round: i + 1, name: s.name, output: s.body })) };
  openChatReadingOverlay(buildAcademicPaperHtml(runData, {}), true);
  msToast('فُتحت وثيقة خطة التحقيق — قابلة للطباعة وتصدير Word من شريطها');
}

function msDiscussContext(p) {
  const entries = ((p.collation || {}).entries || []).slice(0, 140).map(e =>
    `${e.id} | لوحة (${e.folio}) ${e.type} مع (${e.siglum}) | الأم:«${(e.base || '').slice(0, 70)}» الأخرى:«${(e.other || '').slice(0, 70)}» | الحالة:${e.status} | القرار:${(e.rec && e.rec.decision) || '—'}`).join('\n');
  return (msReportText(p).slice(0, 23000) + '\n\nفهرس مواضع الخلاف (استخدم id عند اقتراح تصحيح):\n' + entries).slice(0, 34000);
}

function renderMsDiscussion() {
  const box = document.getElementById('msDiscussLog');
  if (!box) return;
  const p = msCurrentProject();
  if (!p) { box.innerHTML = ''; return; }
  const msgs = p.discussion || [];
  box.innerHTML = msgs.length ? msgs.map((m, i) => m.role === 'user'
    ? `<div class="ms-discuss-user"><strong>الباحث:</strong> ${msEsc(m.content)}</div>`
    : `<div class="ms-discuss-ai"><strong>المحقق الآلي:</strong><br>${msEsc(m.content).replace(/\n/g, '<br>')}
       ${m.apply && !m.applied ? `<div class="ms-form-row" style="margin-top:6px"><button type="button" class="ms-btn ms-btn-primary" onclick="msDiscussApply(${i})">✔ تطبيق التصحيح المتفق عليه (لوحة ${msEsc(((((p.collation || {}).entries || []).find(e => e.id === m.apply.entry_id) || {}).folio) || '')})</button></div>` : ''}
       ${m.applied ? '<div class="ms-hint" style="color:#2e7d5b;font-weight:700">✔ طُبق هذا التصحيح في المشروع</div>' : ''}</div>`
  ).join('') : '<div class="ms-hint">لا نقاش بعد. اسأل المحقق الآلي عن أي قرار في الوثيقة، أو اطلب تصحيح نقطة بعينها — فإذا اتفقتما ظهر زر تطبيق التصحيح تحت رده.</div>';
  box.scrollTop = box.scrollHeight;
}

async function msDiscussSend() {
  const p = msCurrentProject();
  if (!p) return;
  const ta = document.getElementById('msDiscussInput');
  const text = (ta.value || '').trim();
  if (!text) return;
  p.discussion = p.discussion || [];
  const history = p.discussion.slice(-10).map(m => ({ role: m.role, content: m.content }));
  p.discussion.push({ role: 'user', content: text, at: new Date().toISOString() });
  ta.value = '';
  msSave(); renderMsDiscussion();
  const btn = document.getElementById('msDiscussSendBtn');
  if (btn) btn.disabled = true;
  try {
    const data = await msAutoFetch('/api/manuscripts/discuss', {
      context: msDiscussContext(p), history, message: text,
      api_key: msApiKey(), model: msGroupModel('leader', MS_WONDER_MODEL) });
    let reply = data.reply || '';
    let apply = null;
    const start = reply.lastIndexOf('{"apply"');
    if (start >= 0) {
      const jsonText = reply.slice(start).replace(/```/g, '').trim();
      try { apply = (JSON.parse(jsonText) || {}).apply || null; } catch (e) { apply = null; }
      if (apply) reply = reply.slice(0, start).replace(/```json\s*$/g, '').trim();
    }
    p.discussion.push({ role: 'assistant', content: reply, at: new Date().toISOString(), apply, model: data.model });
  } catch (e) {
    p.discussion.push({ role: 'assistant', content: 'تعذر الرد الآن: ' + e.message, at: new Date().toISOString() });
  }
  if (btn) btn.disabled = false;
  msSave(); renderMsDiscussion();
}

function msDiscussApply(i) {
  const p = msCurrentProject();
  if (!p) return;
  const msg = (p.discussion || [])[i];
  if (!msg || !msg.apply || msg.applied) return;
  const prop = msg.apply;
  const e = ((p.collation || {}).entries || []).find(x => x.id === prop.entry_id);
  if (!e) { msToast('لم يُعثر على الموضع المقصود في المقابلة الحالية'); return; }
  const option = ['adopt_other', 'keep_note', 'keep_drop'].includes(prop.option) ? prop.option : 'keep_note';
  msApplyRecommendation(p, e,
    { action: option === 'adopt_other' ? 'adopt_other' : (option === 'keep_drop' ? 'keep_base_drop' : 'keep_base_note'),
      margin_note: prop.apparatus || '', model: msGroupModel('leader', MS_WONDER_MODEL) },
    option, { useNote: !!prop.apparatus,
      decisionLabel: 'تصحيح باتفاق النقاش مع المحقق الآلي' + (prop.reason ? ': ' + prop.reason : '') });
  e.rec.discussion = true;
  (p.corrections = p.corrections || []).push({ at: new Date().toISOString(), entry_id: e.id,
    folio: e.folio, type: e.type, option, reason: prop.reason || '' });
  msg.applied = true;
  msSave(); renderMsDiscussion(); renderMsCollation();
  msToast('✔ طُبق التصحيح المتفق عليه وسُجل في الوثيقة — أعد إصدار النسخة النهائية ليظهر فيها');
}

// ---------- المرحلة ٤: الفهارس والمقدمة والإخراج ----------
function msIndexGroups(p) {
  const accepted = (p.agent_suggestions || []).filter(s => s.status === 'accepted');
  // فهارس لصيقة بالمتن وحده: آيات وأحاديث وأشعار وأعلام ولغة، وموازيات
  // المؤلف حواشي في مواضعها لا فهرس، وما لا فائدة لصيقة فيه لا يُفهرس
  const groups = { 'الآيات القرآنية': [], 'الأحاديث والأقوال': [], 'الأشعار': [], 'الأعلام': [], 'اللغة': [], 'مصادر ومراجع التحقيق': [] };
  const sources = new Set();
  const trimA = a => { const t = String(a || '').trim(); return t.length > 70 ? t.slice(0, 70) + '…' : t; };
  accepted.forEach(s => {
    const item = `«${trimA(s.anchor)}» — لوحة (${s.folio})`;
    if (s.kind === 'takhrij' && s.surah) {
      groups['الآيات القرآنية'].push(`«${trimA(s.anchor)}» (${s.source || ('سورة ' + s.surah)}، الآية ${s.ayah || '—'}) — لوحة (${s.folio})`);
    } else if (s.kind === 'takhrij') {
      if (/شعر|أبيات|بيت شعر|قصيدة/.test(`${s.title || ''} ${s.source || ''}`)) groups['الأشعار'].push(item);
      else groups['الأحاديث والأقوال'].push(item);
    } else if (s.kind === 'tarjama') {
      const nm = String(s.body || '').match(/([ء-ي]{3,}\s+بن\s+[ء-ي]{3,}(?:\s+[ء-ي]{3,}){0,3})/);
      if (nm) groups['الأعلام'].push(`${nm[1].trim()} — لوحة (${s.folio})`);
    } else if (s.kind === 'lugha') {
      groups['اللغة'].push(item);
    }
    const bookOf = str => {
      const m = String(str || '').match(/^([^()،]{3,60})/);
      return m ? m[1].trim() : '';
    };
    if (s.source) { const b = bookOf(s.source); if (b) sources.add(b); }
    if (s.verify && s.verify.locus && s.verify.locus.title) sources.add(s.verify.locus.title);
  });
  groups['مصادر ومراجع التحقيق'] = [...sources]
    .sort((a, b) => (typeof compareBiblioTitles === 'function' ? compareBiblioTitles(a, b) : String(a).localeCompare(String(b), 'ar')));
  Object.keys(groups).forEach(k => { if (!groups[k].length) delete groups[k]; });
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
نُسخت اللوحات بنماذج رؤية متعددة (قارئان مستقلان ومدقق يقابلهما على الصورة) واعتمد المحقق نص كل لوحة بعينه، ثم قوبلت النسخ على النسخة الأم ولوحاتها المرقمة، وصُنّفت الفروق (سقط/زيادة/تبديل/ضبط/رسم/بياض) في «هامش مقابلة» مستقل لا يدخله فرق إلا باعتماد المحقق، واعتُمدت قاعدة ردّ فروق الضبط والرسم المحضة (كاختلاف الهمزات والألف المقصورة والتاء المربوطة) فلم تُثبت في الهامش ولم تُعدّ فروقًا. وخُرّجت الآيات والأحاديث والأشعار وتراجم الأعلام في «هامش تحقيق» مستقل، مع توثيق آلي من مكتبة الشاملة وتمييز ما ثبت بما لم يثبت. وحالة اللوحات المعتمدة حتى توليد هذه المسودة: ${acceptedCount} معتمدة من أصل ${((base || {}).folios || []).length} في الأم، وفروق مقابلة معتمدة: ${colAcc}. [يُستكمل: رموز الأقواس والاصطلاحات وطريقة ضبط النص.]`;
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
      msEdNoteDisplay(f.ed_note).split('\n').forEach(l => { if (l.trim()) sections.push({ h: l, level: 'p' }); });
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

let MS_COMPARE = null;

function msHighlightCompare(text, rows, side) {
  const key = side === 'ours' ? 'ours' : 'theirs';
  let out = msEsc(text || '');
  const seen = {};
  (rows || []).forEach(r => {
    const ph = (r[key] || '').trim();
    if (!ph || ph.length < 2 || seen[ph]) return;
    seen[ph] = 1;
    const cls = r.type === 'ضبط/رسم' ? 'ms-cmp-orth' : 'ms-cmp-diff';
    const escPh = msEsc(ph);
    out = out.split(escPh).join(`<mark class="${cls}" title="${msEsc(r.type)}">${escPh}</mark>`);
  });
  return out;
}

function msOpenCompareBook() {
  if (!MS_COMPARE || !MS_COMPARE.book) { msToast('شغّل المقارنة أولًا'); return; }
  const b = MS_COMPARE.book;
  msOpenStyleBook(b.book_id, (b.from && b.from.part) || '', (b.from && b.from.page) || 0, '');
}

function msExportCompareTable() {
  if (!MS_COMPARE) { msToast('شغّل المقارنة أولًا'); return; }
  const list = MS_COMPARE.list && MS_COMPARE.list.length ? MS_COMPARE.list : [MS_COMPARE];
  const rows = [['التحقيق المرجعي', '#', 'النوع', 'تحقيقنا', 'التحقيق المقارن', 'السياق']];
  list.forEach(d => (d.rows || []).forEach((r, i) =>
    rows.push([(d.book || {}).title || '', i + 1, r.type, r.ours || '', r.theirs || '', r.context || ''])));
  const csv = rows.map(r => r.map(c => '"' + String(c).replace(/"/g, '""') + '"').join(',')).join('\n');
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
  const name = (MS_COMPARE.book && MS_COMPARE.book.title) ? `فروق — ${MS_COMPARE.book.title}.csv` : 'فروق التحقيق.csv';
  msDownloadBlob(blob, name);
}

function msOpenCompareBookPicker() {
  if (typeof openSearchScopeModal === 'function') openSearchScopeModal('ms_compare');
  else msToast('نافذة انتقاء الكتب غير متاحة في هذه الصفحة');
}

// التحقيقات المرجعية للمقارنة: حتى ثلاثة، تُدار قائمتها في المشروع
function msCompareBooks(p) {
  if (!p) return [];
  if (!Array.isArray(p.compareBooks)) p.compareBooks = p.compareBook ? [p.compareBook] : [];
  return p.compareBooks;
}

function renderMsCompareChips() {
  const box = document.getElementById('msCompareChips');
  if (!box) return;
  const p = msCurrentProject();
  const books = p ? msCompareBooks(p) : [];
  box.innerHTML = books.map((b, i) =>
    `<span class="ms-book-chip">${msEsc(b)} <button type="button" class="ms-chip-x" title="إزالة" onclick="msRemoveCompareBook(${i})">✕</button></span>`).join('')
    + (books.length ? `<span class="ms-hint">${books.length} من ٣ تحقيقات مرجعية كحد أقصى</span>` : '<span class="ms-hint">أضف حتى ٣ تحقيقات منشورة للمقارنة المرجعية (اكتب الاسم وأضفه، أو تصفح الكتب)</span>');
}

function msRemoveCompareBook(i) {
  const p = msCurrentProject();
  if (!p) return;
  msCompareBooks(p).splice(i, 1);
  p.compareBook = msCompareBooks(p)[0] || '';
  msSave(); renderMsCompareChips();
}

function msAddCompareBook(title) {
  const p = msCurrentProject();
  if (!p) return false;
  const t = String(title || '').trim();
  if (!t) return false;
  const books = msCompareBooks(p);
  if (books.includes(t)) { msToast('هذا التحقيق المرجعي مضاف من قبل'); return false; }
  if (books.length >= 3) { msToast('بلغت الحد الأقصى: ثلاثة تحقيقات مرجعية'); return false; }
  books.push(t);
  p.compareBook = books[0];
  msSave(); renderMsCompareChips();
  return true;
}

function msAddCompareFromInput() {
  const input = document.getElementById('msCompareBook');
  if (input && msAddCompareBook(input.value)) input.value = '';
}

window.onMsCompareBook = function (title) {
  if (title && msAddCompareBook(title)) msToast(`أضيف التحقيق المرجعي: «${title}»`);
};

function msCompareSectionHtml(ourText, data, idx) {
  const rows = data.rows.map((r, i) => `<tr><td>${i + 1}</td><td>${msEsc(r.type)}</td><td>${msEsc(r.ours || '—')}</td><td>${msEsc(r.theirs || '—')}</td><td>${msEsc(r.context || '')}</td></tr>`).join('');
  return `
    <div class="ms-disputes-title" style="margin-top:16px">التحقيق المرجعي ${idx + 1}: «${msEsc(data.book.title)}» (ج ${msEsc(data.book.from.part || '—')} ص ${msEsc(data.book.from.page || '—')} – ص ${msEsc(data.book.to.page || '—')}) — تطابق ${data.similarity}٪ و${data.rows.length} فرقًا</div>
    <div class="ms-compare-grid">
      <div class="ms-compare-col"><div class="ms-collate-folio-title">تحقيقنا (متن الأم كما اعتمدناه)</div><div class="ms-compare-text">${msHighlightCompare(ourText, data.rows, 'ours')}</div></div>
      <div class="ms-compare-col"><div class="ms-collate-folio-title">التحقيق المقارن — ${msEsc(data.book.title)}</div><div class="ms-compare-text">${msHighlightCompare(data.their_text || '', data.rows, 'theirs')}</div></div>
    </div>
    <div class="ms-disputes-title">جدول الفروقات الآلي (${data.rows.length}) — ${Object.entries(data.counts || {}).map(([k, v]) => `${msEsc(k)}: ${v}`).join(' · ')} — المظلَّل في النصين هو موضع الفرق</div>
    <div class="ms-compare-tablewrap"><table class="ms-compare-table">
      <thead><tr><th>#</th><th>النوع</th><th>تحقيقنا</th><th>التحقيق المقارن</th><th>السياق قبل الفرق</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="5">لا فروق جوهرية — تطابق تام في المواضع المحاذاة</td></tr>'}</tbody>
    </table></div>`;
}

async function msCompareEdition() {
  const p = msCurrentProject();
  if (!p) return;
  const base = msBaseCopy(p);
  if (!base) { msToast('لا نسخة أم بعد'); return; }
  const ourText = (base.folios || []).filter(f => (f.text || '').trim())
    .map(f => f.text).join('\n');
  if (!ourText.trim()) { msToast('لا متن محققًا في لوحات الأم بعد'); return; }
  const typed = document.getElementById('msCompareBook').value.trim();
  if (!msCompareBooks(p).length && typed) msAddCompareBook(typed);
  const books = msCompareBooks(p).slice(0, 3);
  if (!books.length) { msToast('أضف تحقيقًا منشورًا واحدًا على الأقل للمقارنة'); return; }
  const btn = document.getElementById('msCompareBtn');
  const info = document.getElementById('msCompareInfo');
  btn.disabled = true; info.textContent = `⏳ جارٍ محاذاة تحقيقنا على ${books.length} تحقيقًا منشورًا واستخراج الفروق...`;
  const list = [];
  let html = '';
  for (const book of books) {
    try {
      const res = await fetch('/api/manuscripts/compare-edition', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: ourText, book }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'تعذرت المقارنة');
      if (!data.found) throw new Error(data.detail || 'تعذرت المحاذاة');
      list.push(data);
      html += msCompareSectionHtml(ourText, data, list.length - 1);
    } catch (e) {
      html += `<div class="ms-rec-loading">❌ «${msEsc(book)}»: ${msEsc(e.message)}</div>`;
    }
  }
  if (list.length) {
    MS_COMPARE = { ...list[0], list };
    p.compareSummary = list.map(d => ({ book: d.book.title, similarity: d.similarity, rows: d.rows.length }));
    msSave();
    info.textContent = 'قورن تحقيقنا بـ: ' + p.compareSummary.map(s => `«${s.book}» تطابق ${s.similarity}٪ و${s.rows} فرقًا`).join('؛ ');
  } else {
    info.textContent = '';
  }
  document.getElementById('msCompareResult').innerHTML = html;
  btn.disabled = false;
}

// الإخراج النهائي للقارئ: صفحة عنوان، مقدمة، نص اللوحات بهوامش مرسّاة
// (فروق المقابلة وتعليقات التحقيق حواشٍ سفلية حقيقية مرقمة في مواضعها)، وفهارس
// صياغة الحواشي للمنشور الأكاديمي: داخل التطبيق تبقى النسبة موثقة ([وكيل]/[قرار المحقق])،
// أما الإخراج النهائي فنظيف لا أسماء وكلاء فيه ولا عبارات آلية
function msEdNotePrint(text) {
  return (text || '').split('\n').map(l => {
    let out = l.trim();
    out = out.replace(/^\[(وكيل [^\]]+|قرار المحقق[^\]]*|تنبيه المحقق|تصحيح المحقق|تصحيح قراءة بقرار المحقق|تعليق المحقق[^\]]*|مسح أسلوب المؤلف[^\]]*|تخريج|توثيق|لغة|ضبط\/تصحيف|ضبط|تصحيف|تراجم|ترجمة)\]\s*/, '');
    out = out.replace(/\s*[—-]?\s*قرار المحقق بعد توصية[^.؛]*/g, '');
    out = out.replace(/بعد توصية (Muse Wonder|المدقق الذكي)[^.؛]*/g, '');
    out = out.replace(/\(ثقة\s*[^)]*\)/g, '');
    out = out.replace(/\s*وفحص الشواهد بعينه/g, '');
    out = out.replace(/،?\s*مقابل صفر[^،؛.]*/g, '');
    // التوثيق البرمجي يتحول في المنشور إلى مرجع دقيق: (شاهد: الكتاب، ج، ص)
    out = out.replace(/\s*\[توثيق:([^\]]*)\]/g, (m, inner) => {
      const loc = inner.match(/«([^»]+)»\s*\(ج\s*([^،)]*?)[،\s]*ص\s*([^)]+)\)/);
      return loc ? ` (شاهد: ${loc[1].trim()}، ج${loc[2].trim()} ص${loc[3].trim()})` : '';
    });
    out = out.replace(/\s*\[(تنبيه|مصدر|مراجعة)[^\]]*\]/g, '');
    out = out.replace(/\s*\(ملاحظة محقق\)/g, '');
    return out.replace(/\s+/g, ' ').trim();
  }).filter(Boolean).join('\n');
}

function msFinalParts(p) {
  const base = msBaseCopy(p);
  const accepted = ((p.collation || {}).entries || []).filter(e => e.status === 'accepted');
  const rawFolios = ((base || {}).folios || []).filter(f => (f.text || '').trim());
  // النص المحقق يبدأ بلوحة الافتتاح (البسملة والحمدلة) ثم بقية اللوحات
  // بترتيبها، ولو اختلف ترتيب إدخال اللوحات أو ترقيمها في المشروع
  const openIdx = rawFolios.findIndex(f => /بسم الله/.test((f.text || '').slice(0, 160)));
  const orderedFolios = openIdx > 0
    ? [rawFolios[openIdx], ...rawFolios.filter((_, i) => i !== openIdx)]
    : rawFolios;
  const folios = orderedFolios
    .map(f => ({
      label: f.label, siglum: base.siglum, text: f.text || '',
      apparatus: accepted.filter(e => e.folio === f.label).map(e => msApparatusText(e)),
      entries: accepted.filter(e => e.folio === f.label),
      edLines: (f.ed_note || '').trim() ? msEdNotePrint(f.ed_note).split('\n').filter(l => l.trim()) : [],
    }));
  const groups = (p.indexes || {}).groups || null;
  return { base, folios, groups };
}

// عبارة الإرساء لتعليق تحقيق: أول عبارة مقوّسة «...» في مطلعه
function msEdAnchorPhrase(line) {
  const m = (line || '').match(/«([^»]{2,80})»/);
  return m ? m[1] : '';
}

// أسطر النسخ أسطرٌ مادية في المخطوط؛ تُصهر في المنشور فقراتٍ متدفقة
// (فواصل الأسطر الفارغة وحدها تفصل الفقرات) فينضبط السطر يمينًا وشمالًا
function msFlowParagraphs(text) {
  // فقرات طبيعية كما في الكتب المحققة: تُصهر أسطر النسخ، وتُختم الفقرة
  // عند تمام جملة بعد حد أدنى من الطول (وسطر فارغ يفصل حتمًا) — فلا
  // فقرة عملاقة تمتد صفحات فيتصل ترقيم حواشيها ويتكدس ذيلها
  const paras = [];
  let cur = [];
  const flush = () => { if (cur.length) { paras.push(cur.join(' ')); cur = []; } };
  (text || '').split('\n').forEach(line => {
    const t = line.trim();
    if (!t) { flush(); return; }
    cur.push(t);
    const joinedLen = cur.join(' ').length;
    if ((/[.!؟»؛:]\s*$/.test(t) && joinedLen >= 380) || joinedLen >= 750) flush();
  });
  flush();
  return paras;
}

// صياغة الحاشية للمنشور: اختصار المحققين «الكلمة]» يُكتب «الكلمة» كامل القوسين
function msApparatusPrint(e) {
  let t = msApparatusText(e);
  if (e.custom_apparatus) t = t.replace(/^([^:\n]{1,70}?)\]\s*/, '«$1» ');
  return t;
}

// تطبيع رسم للإرساء فقط: تجريد التشكيل وتوحيد الهمزات والألف المقصورة
// والواو والياء المهموزتين، فلا يفشل التطابق لاختلاف رسم النسخ
function msNormAnchor(s) {
  const rep = { 'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ؤ': 'و', 'ئ': 'ي', 'ة': 'ه' };
  let norm = '', map = [];
  const src = String(s || '');
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (/[ً-ٰٟـ]/.test(ch)) continue;
    norm += rep[ch] || ch;
    map.push(i);
  }
  return { norm, map };
}

// يقطّع فقرة المتن مقاطع مرسّاة: كل مقطع نصٌّ، وما اتصلت به حاشية أعقبه مقطع fn
function msAnchorSegments(text, items, fnTextOf) {
  // كل حاشية تجد موضع عبارتها مستقلةً (عبارات مكررة أو متداخلة في مقطع
  // طويل لا تُقصي بعضها)، ثم تُرتَّب النقاط بنهاياتها فتخرج المقاطع متسلسلة
  const { norm, map } = msNormAnchor(text);
  const anchors = [];
  items.filter(e => e.base && !e._anchored).forEach((e, ord) => {
    let n = msNormAnchor(e.base).norm;
    let idx = n ? norm.indexOf(n) : -1;
    // مقطع طويل لم يطابق كاملًا (سقط ممتد): يُرسى عند مطلع عبارته
    if (idx < 0 && n && n.length > 30) {
      const head = n.split(' ').slice(0, 6).join(' ');
      if (head) {
        const h = norm.indexOf(head);
        if (h >= 0) { idx = h; n = head; }
      }
    }
    if (idx < 0 || !n) return;
    anchors.push({ e, ord, endN: idx + n.length });
  });
  anchors.sort((a, b) => a.endN - b.endN || a.ord - b.ord);
  const segs = [];
  let posN = 0;
  for (const a of anchors) {
    const oEnd = map[a.endN - 1] + 1;
    const oStart = posN === 0 ? 0 : map[posN];
    if (oEnd < oStart) continue;
    if (oEnd > oStart) segs.push({ text: text.slice(oStart, oEnd) });
    segs.push({ text: '', fn: fnTextOf(a.e) });
    a.e._anchored = true;
    posN = a.endN;
  }
  const restStart = posN === 0 ? 0 : (map[posN] !== undefined ? map[posN] : text.length);
  if (restStart < text.length) segs.push({ text: text.slice(restStart) });
  return segs.length ? segs : [{ text }];
}

async function msExportDocx() {
  const p = msCurrentProject();
  if (!p) return;
  const info = document.getElementById('msExportInfo');
  await msPrefetchBiblio(p);
  // مسار وورد الأبحاث نفسه: من ورقة الطباعة المقسمة في إطار القراءة
  // (exportWordFromDoc) فتتطابق الحواشي والترقيم والضبط مع المعاينة
  msPreviewPrint();
  info.textContent = 'جارٍ تجهيز Word من ورقة الطباعة المقسمة...';
  const frame = document.getElementById('chatReadingFrame');
  if (!frame) { info.textContent = '❌ تعذر فتح إطار القراءة'; return; }
  const t0 = Date.now();
  const timer = setInterval(async () => {
    let done = false;
    try { done = frame.contentWindow && frame.contentWindow.__pagedDone === true; } catch (e) {}
    if (!done && Date.now() - t0 < 90000) return;
    clearInterval(timer);
    if (!done) { info.textContent = '❌ لم يكتمل تقسيم الصفحات لتصدير وورد'; return; }
    try {
      await exportWordFromDoc(frame.contentDocument);
      info.textContent = 'نُزّل ملف Word النهائي بحواشٍ صفحية مرقمة من (١) في كل صفحة كما في الأبحاث';
    } catch (e) {
      info.textContent = '❌ ' + e.message;
    }
  }, 400);
}

async function msExportPdf() {
  const p = msCurrentProject();
  if (!p) return;
  await msPrefetchBiblio(p);
  // ضبط الأبحاث الشرعية نفسه حرفيًا: forPdf بهوامش Paged الصفرية، وخطوط
  // وألوان ومقاسات وفواصل وخلفية من إعدادات طباعة المنظومة عبر paperPrintCss
  const html = msBuildPrintHtml(p, { toolbar: false, forPdf: true });
  document.getElementById('msExportInfo').textContent = 'جارٍ توليد PDF مضبوط الصف...';
  try {
    const res = await fetch('/api/projects/export-pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: p.title, html }),
    });
    if (!res.ok) throw new Error('فشل توليد PDF');
    msDownloadBlob(await res.blob(), `${p.title}.pdf`);
    document.getElementById('msExportInfo').textContent = 'نُزّل ملف PDF النهائي: صفحات A4 مرقمة بحواشٍ سفلية مرسّاة';
  } catch (e) {
    document.getElementById('msExportInfo').textContent = '❌ ' + e.message;
  }
}

// متن التحقيق يُبنى بسكربت إنتاج الأبحاث الشرعية في التطبيق نفسه
// (buildAcademicPaperHtml): حواشٍ صفحية مرقمة من (١) في كل صفحة،
// وضبط سطر، وخطوط وألوان من قسم الطباعة — بلا مُخرِج موازٍ
function msArabicDigits(n) {
  return String(n).replace(/[0-9]/g, d => '٠١٢٣٤٥٦٧٨٩'[d]);
}

// بيانات كتب الإحالات (مؤلف/أجزاء) تُجلب من قاعدة الكتب قبل الإخراج
let MS_BOOK_META = {};
function msBookKey(t) {
  return String(t || '').replace(/[ً-ٰٟ]/g, '')
    .replace(/\s*[-–]\s*(ت|ط)\s.*$/, '').replace(/\s+/g, ' ').trim();
}
async function msPrefetchBiblio(p) {
  const ids = new Set(), titles = new Set();
  (p.agent_suggestions || []).forEach(s => {
    if (s.verify && s.verify.locus && s.verify.locus.book_id) ids.add(s.verify.locus.book_id);
    const b = (String(s.source || '').match(/^([^()،]{3,60})/) || [])[1];
    if (b) titles.add(b.trim());
  });
  if (!ids.size && !titles.size) return;
  try {
    const res = await fetch('/api/manuscripts/bibliography', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ book_ids: [...ids].slice(0, 60), titles: [...titles].slice(0, 60) }),
    });
    if (!res.ok) return;
    const data = await res.json();
    MS_BOOK_META = {};
    (data.rows || []).forEach(r => { MS_BOOK_META[msBookKey(r.title)] = r; });
    p._biblioRows = data.rows || [];
  } catch (e) {}
}

// صياغة إحالة الحاشية بالمعيار القياسي للتطبيق نفسه (كما في البحوث
// الشرعية المطبوعة): «انظر:» للنقل الحرفي و«ينظر:» للمعنوي أو متعدد
// المصادر، ثم اسم الكتاب للمؤلف (جزء-صفحة). صرامة آلية: تُستخرج
// الإحالات من أي موضع في الحاشية، وما لا موضع موثّقًا له (جزء وصفحة
// أو صفحة) يُحذف حذفًا تامًا فلا تخرج إحالة عارية أبدًا
const MS_DICT_RE = /لسان العرب|القاموس المحيط|تاج العروس|النهاية في غريب|المصباح المنير|مختار الصحاح|المعجم الوسيط/;
function msCiteParts(citeStr) {
  const toLatin = s => String(s || '').replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
  const parts = [];
  const seen = {};
  String(citeStr || '').split('؛').forEach(rawPart => {
    let part = String(rawPart || '').trim()
      .replace(/^شاهد:\s*/, '').replace(/^و(?=[^\s،])/, '')
      .replace(/\((?![^)]*(?:ج\s|ص\s|مادة|رقم|[0-9٠-٩]\s*-\s*[0-9٠-٩]))[^)]*\)/g, '')
      .replace(/\s+/g, ' ').trim();
    if (!part) return;
    const title = (part.split('،')[0] || '').trim()
      .replace(/\s*\([0-9٠-٩]+-[0-9٠-٩]+\)\s*$/, '').trim();
    if (!title) return;
    let madda = (part.match(/مادة \(([^)]+)\)/) || [])[1] || '';
    if (!madda) {
      const sub = (part.match(/^[^(]+\(([^()]{1,24})\)/) || [])[1] || '';
      if (sub && MS_DICT_RE.test(title) && !/^[0-9٠-٩\s-]+$/.test(sub)) madda = sub;
    }
    const jm = part.match(/ج\s*([0-9٠-٩]+)\s*[,،]?\s*ص\s*([0-9٠-٩]+)/)
      || part.match(/\(([0-9٠-٩]+)-([0-9٠-٩]+)\)/);
    const pg = jm ? null : (part.match(/ص\s*([0-9٠-٩]+)/) || [])[1];
    if (!jm && !pg) return; // لا موضع موثّقًا: تُحذف الإحالة ولا تخرج عارية
    const meta = MS_BOOK_META[msBookKey(title)] || null;
    const author = meta && meta.author ? meta.author : '';
    const dispTitle = title.replace(/\s*[-–]\s*(ت|ط)\s.*$/, '').trim();
    const authorDup = author && dispTitle.includes(author.split(/[،\s]/)[0].replace(/^ال/, ''));
    const head = (author && !authorDup)
      ? `${dispTitle} ${author.startsWith('ال') ? 'ل' + author.slice(1) : 'لـ' + author}` : dispTitle;
    const txt = (jm ? `${head} (${toLatin(jm[1])}-${toLatin(jm[2])})` : `${head} ص (${toLatin(pg)})`)
      + (madda ? `، مادة (${madda})` : '');
    const key = msBookKey(title);
    // الكتاب الواحد بصيغتين («لسان العرب» و«لسان العرب لابن منظور») إحالة واحدة
    const dupKey = Object.keys(seen).find(k => key === k || key.startsWith(k + ' ') || k.startsWith(key + ' '));
    if (dupKey) {
      if (madda && !/مادة/.test(seen[dupKey].txt)) seen[dupKey].txt += `، مادة (${madda})`;
      return;
    }
    seen[key] = { txt };
    parts.push(seen[key]);
  });
  return parts;
}
function msStandardCite(citeStr, literal) {
  const parts = msCiteParts(citeStr);
  if (!parts.length) return '';
  const prefix = (parts.length > 1 || !literal) ? 'ينظر: ' : 'انظر: ';
  return prefix + parts.map((x, i) => (i === 0 ? x.txt : 'و' + x.txt)).join('؛ ');
}
function msFnPrint(t) {
  let out = String(t || '').trim();
  // تخريج حديث: متن الحاشية نفسه إحالتها بقالب «أخرجه فلان، حديث رقم
  // (N)، (ج-ص)» فلا يُلحق بها شاهد كتاب آخر ولا قوس كتب عارٍ في ذيلها
  if (/أخرجه|أخرجها|رواه/.test(out)) {
    out = out.replace(/\s*\(شاهد:[^()]*\)/g, '');
    out = out.replace(/\s*\((?:صحيح|سنن|مسند|جامع|كتاب)\s+[^(]{2,50}\([^()]*\)[^()]*\)\s*$/, '');
    out = out.replace(/\s*\((?:صحيح [^()]{2,40}|السلسلة الصحيحة|سنن [^()]{2,30}|مسند [^()]{2,30})(?:\s+و[^()]*)?\)\s*$/, '');
    out = out.replace(/أخرجه (البخاري|مسلم|ابن حبان|ابن حبّان|أحمد|الترمذي|أبو داود|النسائي|ابن ماجه|الدارمي|مالك)\s*\(([0-9٠-٩]+)\)/g,
      'أخرجه $1، حديث رقم ($2)');
    out = out.replace(/(^|[؛.)])\s*و(مسلم|البخاري|أحمد|الترمذي)\s*\(([0-9٠-٩]+)\)/g, '$1 و$2، حديث رقم ($3)');
    out = out.replace(/،\s*رقم\s*\(([0-9٠-٩]+)\)/g, '، حديث رقم ($1)');
    return out.replace(/\s+/g, ' ').replace(/\(\s*\)/g, '').trim();
  }
  const cites = [];
  let base = out;
  base = base.replace(/\(شاهد:\s*([^()]+)\)/g, (m, c) => { cites.push(c.trim()); return ' '; });
  const anz = base.match(/\s+(?:انظر|ينظر):\s*([\s\S]+)$/);
  if (anz) { cites.push(anz[1].trim()); base = base.slice(0, anz.index).trimEnd(); }
  base = base.replace(/\(([^()]{3,90}?)\)/g, (m, inner) => {
    if (/،\s*ج\s*[0-9٠-٩—-]+\s*[,،]?\s*ص\s*[0-9٠-٩]+/.test(inner) || /\([0-9٠-٩]+-[0-9٠-٩]+\)/.test(inner)) {
      cites.push(inner.trim()); return ' ';
    }
    return m;
  });
  // قوس المصدر الختامي (كتاب (مادة/رقم)) أو اسم كتاب صريح بلا موضع:
  // مرشح إحالة، فإن لم يكن له موضع في الشواهد حُذف ولا يخرج عاريًا
  const bookish = /تفسير|صحيح|سنن|مسند|جامع|شرح|لسان العرب|قاموس|تاج العروس|نهاية|مصباح|مختار الصحاح|تاريخ|طبقات|أعلام|معجم|كشف الظنون|حلية|قوت القلوب|زاد المسير|محرر|لوامع|تدمرية|عقيدة|فتاوى|بداية ونهاية|شذرات|إيضاح|مطبوعات|سلسلة|دليل الفالحين/;
  base = base.replace(/\s*\(([^()]{2,80}?)(?:\s*\(([^()]{1,24})\))?[^()]{0,60}\)\s*$/, (m, bk, sub) => {
    if (!bookish.test(bk) && !sub) return m;
    if (/سورة|آية|حديث|قال|صلى/.test(bk) && !sub) return m;
    cites.push(sub ? `${bk.trim()} (${sub.trim()})` : bk.trim());
    return '';
  });
  const citeStr = cites.filter(Boolean).join('؛ ');
  base = base.replace(/\(\s*\)/g, '').replace(/\s*(?:انظر|ينظر):\s*$/, '')
    .replace(/[؛,،]\s*$/, '').replace(/\s+/g, ' ').trim();
  if (!citeStr) return base;
  // النقل النصي: ﴿﴾ أو تصريح بالنص أو نقل منقول بقول/أورد/نقل،
  // فأما كلمة المتن المشروحة بين تنصيص فليست نقلًا من المصدر
  const literal = /﴿/.test(out) || /نصًّا|بنصّه|بنصه/.test(out)
    || /(?:قال|يقول|أورد|نقل|ذكر)\s*(?:في[^:]{0,40})?:?\s*«[^»]{12,}»/.test(out);
  const std = msStandardCite(citeStr, literal);
  return std ? (base + ' ' + std).replace(/\s+/g, ' ').trim() : base;
}

function msPaperRunData(p) {
  const { folios, groups } = msFinalParts(p);
  const escMd = s => String(s || '').replace(/([*_`])/g, '\\$1');
  const footnoteTexts = [];
  const refFor = t => {
    footnoteTexts.push(t);
    return `(${msArabicDigits(footnoteTexts.length)})`;
  };
  // مراجع المقدمة المكتوبة بصيغة (الكتاب، ج، ص) تصير حواشيَ مرقمة
  // كحواشي المتن تمامًا، وترقيمها يسبق ترقيم حواشي المتن لترتيب الورقة
  let introMd = (p.intro || '').trim();
  if (introMd) {
    // هرمية عناوين صارمة: الأقسام الكبرى (أولًا/ثانيًا...) عناوين
    // رئيسية بارزة بخط العناوين الكبرى، وتحت «ترجمة المؤلف» عناوين
    // فرعية أصغر (اسمه، شيوخه...) فلا يستوي المهم بالأقل أهمية
    introMd = introMd.split('\n').map(l => {
      const tx = l.trim().replace(/^\*\*|\*\*$/g, '');
      if (/^(أولًا|ثانيًا|ثالثًا|رابعًا|خامسًا|سادسًا|سابعًا|ثامنًا)[:：]/.test(tx)) return `## ${tx}`;
      return l;
    }).join('\n');
    // حواشي المقدمة بالمعيار القياسي نفسه: ينظر: كتاب للمؤلف (ج-ص)
    introMd = introMd.replace(/\(([^()]{3,140}?،\s*ج\s*[^()]+?ص\s*[٠-٩0-9]+[^()]*)\)/g,
      (m, cite) => refFor(msStandardCite(cite.trim(), false) || cite.trim()));
    // فاصل ختام المقدمة: ثلاث نجوم وسط الصفحة، ولا نجوم في غير موضعها
    introMd += '\n\n***';
  }
  const bodyParas = [];
  folios.forEach(f => {
    const entries = f.entries.map(e => ({ ...e, base: e.base || (e.type === 'زيادة' ? e.other : '') }));
    const edRaw = f.edLines.map(l => ({ base: msEdAnchorPhrase(l), _ed: true, _text: l }));
    // موضع واحد في المتن = حاشية واحدة: تُدمج تعليقات الوكلاء المتعددة
    // على العبارة نفسها في حاشية محقق واحدة فلا تتكدس العلامات على كلمة
    const stripLead = s => s.replace(/^«[^»]+»\s*[—–-]?\s*/, '');
    const edGrouped = []; const byKey = new Map();
    edRaw.forEach(e => {
      const key = msNormAnchor(e.base || '').norm;
      if (key && byKey.has(key)) { byKey.get(key)._parts.push(e._text); return; }
      const g = { base: e.base, _ed: true, _parts: [e._text] };
      if (key) byKey.set(key, g);
      edGrouped.push(g);
    });
    edGrouped.forEach(g => {
      g._text = g._parts.length === 1 ? g._parts[0]
        : g._parts[0] + ' ' + g._parts.slice(1).map(stripLead).join(' ');
      delete g._parts;
    });
    const fnTextOf = e => e._ed ? msFnPrint(e._text) : msApparatusPrint(e);
    // لا حاشيتين متماثلتين في لوحة واحدة (فروق مكررة من جولات مقابلة)
    const seenFn = new Set();
    const all = entries.concat(edGrouped).filter(e => {
      const t = fnTextOf(e);
      if (seenFn.has(t)) return false;
      seenFn.add(t);
      return true;
    });
    const paras = msFlowParagraphs(f.text);
    paras.forEach((para, pi) => {
      const segs = msAnchorSegments(para, all, fnTextOf);
      let md = segs.map(seg => seg.fn !== undefined ? escMd(seg.text) + refFor(seg.fn) : escMd(seg.text)).join('');
      if (pi === paras.length - 1) {
        // ما لم يجد مرساة في المتن يُجمع في حاشية واحدة بذيل اللوحة
        // فلا تتكدس علامات متتابعة في آخر السطر
        const un = all.filter(e => !e._anchored);
        if (un.length === 1) md += refFor(fnTextOf(un[0]));
        else if (un.length > 1) md += refFor(un.map(fnTextOf).join(' '));
      }
      if (pi === 0) md = `[${f.label}] ` + md;
      bodyParas.push(md);
    });
  });
  const escHtml = s => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
  let body = bodyParas.join('\n\n');
  if (footnoteTexts.length) {
    body += '\n\n<ol>' + footnoteTexts.map((t, i) =>
      `<li id="fn${i + 1}">(${msArabicDigits(i + 1)}) ${escHtml(t)}</li>`).join('') + '</ol>';
  }
  const rounds = [];
  if (p.author) rounds.push({ name: '', output: `تأليف: ${p.author} — تحقيق ودراسة` });
  if (introMd) {
    rounds.push({ name: 'مقدمة المحقق', output: introMd.split('\n').filter(l => l.trim()).join('\n\n') });
  }
  rounds.push({ name: 'النص المحقق', output: body });
  if (groups) {
    const idxParts = [];
    Object.keys(groups).forEach(name => {
      if (!(groups[name] || []).length) return;
      // المصادر والمراجع تخرج بآلية البحوث (صفحة مستقلة ببيانات
      // كاملة مرتبة) متى جُلبت بياناتها، فلا تتكرر مجموعة فهارس
      if (name === 'مصادر ومراجع التحقيق' && (p._biblioRows || []).length) return;
      idxParts.push(name === 'مصادر ومراجع التحقيق' ? '**المصادر والمراجع**' : `**فهرس ${name}**`);
      (groups[name] || []).forEach(i => idxParts.push(escMd(i)));
    });
    if (idxParts.length) rounds.push({ name: 'الفهارس', output: idxParts.join('\n\n') });
  }
  return { projectTitle: p.title, rounds, bibliography: p._biblioRows || [] };
}

function msBuildPrintHtml(p, options) {
  if (typeof buildAcademicPaperHtml !== 'function') return '';
  let html = buildAcademicPaperHtml(msPaperRunData(p), options || {});
  // الأقسام الكبرى في المقدمة تأخذ طراز عناوين الجولات الكبرى البارز
  html = html.replace(/<h2>(أولًا|ثانيًا|ثالثًا|رابعًا|خامسًا|سادسًا|سابعًا|ثامنًا)/g,
    '<h2 class="academic-round-title ms-main-head">$1');
  // لا نجوم متسربة من صياغة النماذج في المنشور، وفاصل ختام المقدمة وحده نجوم وسطى
  html = html.replace(/\*\*/g, '');
  html = html.replace(/<hr[^>]*>/g, '<p style="text-align:center;text-indent:0">***</p>');
  html = html.replace(/<p[^>]*>\*\*\*<\/p>/g, '<p style="text-align:center;text-indent:0">***</p>');
  // «النص المحقق» عنوان وسطي في مطلع صفحة جديدة بعد مقدمة التحقيق
  html = html.replace('<h2 class="academic-round-title">النص المحقق</h2>',
    '<h2 class="academic-round-title ms-matn-start">النص المحقق</h2>');
  // أرقام الحواشي العربية داخل روابطها باتجاه معزول فلا تنعكس (١٠ لا تظهر ٠١)
  html = html.replace('</head>', '<style>.pg-fn-call,.pg-fn-marker{direction:ltr;unicode-bidi:isolate}.ms-matn-start{text-align:center !important;break-before:page;page-break-before:always}</style></head>');
  return html;
}

function msPreviewPrint() {
  const p = msCurrentProject();
  if (!p) return;
  const html = msBuildPrintHtml(p);
  if (typeof openChatReadingOverlay === 'function') {
    openChatReadingOverlay(html, true);
    msToast('فُتحت معاينة الطباعة النهائية بنفس إطار إقفال الإجابة المعتمدة في الشات');
  } else {
    const w = window.open('', '_blank');
    if (!w) { msToast('اسمح بالنوافذ المنبثقة لمعاينة الطباعة'); return; }
    w.document.open(); w.document.write(html); w.document.close();
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
