// =============================================================================
// قراءة وتحليل — مشاريع قراءة خاصة: كروت مشاريع، نافذة قراءة على هيئة صفحة،
// أدوات (أقلام وأحجام وألوان، تظليل بمقدار السطر، قص، تكبير/تصغير، منظار،
// ملصقات ملحوظات)، وكتاب من رفع PDF أو الشاملة المصوّرة أو الشبكة، مع حفظ
// موضع وقوف القارئ وتعليقاته على الصفحات.
// =============================================================================
let rdProjects = [];
let rdAssistants = [];
let rdReaders = [];
let rdLoaded = false;
let rdCurrent = null; // مشروع القراءة المفتوح
let rdTool = 'pen';
let rdPenSize = 3;
let rdColor = '#b03a2e';
let rdNoteColor = '#ffe58a';
let rdDraw = null; // رسم جارٍ {type, pts|x0...}
let rdSaveTimer = null;
let rdActiveSel = null; // {page, kind:'h'|'c', index, rect:{x,y,w,h}}
let rdSelFromHover = false; // شريط الأيقونات ظاهر بسبب تمرير على تحليل سابق
let rdAsstDraftBooks = [];
let rdEditingAsstId = null;
let rdAnalysis = null; // {id, discussion} المناقشة المفتوحة
let rdAnalysisAbort = null;
let rdMediaAction = null; // 'share' | 'publish'

const RD_COLORS = ['#b03a2e', '#1f6fb2', '#2e7d5b', '#b8860b', '#7a5aa1', '#222222'];
const RD_NOTE_COLORS = ['#ffe58a', '#ffd1dc', '#c8f0c8', '#bfe3ff', '#e6ccff'];
const RD_DISC_COLOR = 'rgba(120,120,120,0.28)';
const RD_DEFAULT_ASST_PROMPT =
`أنت مختص بمساعدة قارئ الكتاب
سيقوم القارئ بتزويدك بنص من الكتاب المقروء وعليك تحليل النص وتصنيفه
فقه - عقيدة - تفسير - حديث - لغة .. الخ
عليك الاستعانة بنماذج مراسي البحث للتصنيف الدلالي الدقيق
يجب أن تكون الإجابة ما بين متوسطة إلى مختصرة اختصارا غير مخل
يجب عليك الالتزام التام بطريقة الإحالة
التزم بالمطلوب بدقة تامة`;
let rdCustomColors = { pen: [], note: [] };
try { rdCustomColors = Object.assign(rdCustomColors, JSON.parse(localStorage.getItem('rdCustomColors') || '{}')); } catch (e) { /* لوحة افتراضية */ }
let rdColorTarget = 'pen'; // منتقي الألوان يضيف للوحة الأقلام أو الملصقات

function rdEsc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function rdToast(msg, ms) { if (typeof showToast === 'function') showToast(msg, ms || 3500); }
function rdUid() { return 'rd' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
function rdShowModal(id) {
  const m = document.getElementById(id);
  if (!m) return null;
  if (m.parentElement !== document.body) document.body.appendChild(m);
  m.hidden = false;
  m.scrollTop = 0;
  return m;
}
function rdCloseModal(id) { const m = document.getElementById(id); if (m) m.hidden = true; }

// تاريخ البداية: اليوم + التاريخان الهجري والميلادي + الوقت
function rdNowStamp() {
  const now = new Date();
  const weekday = new Intl.DateTimeFormat('ar-EG', { weekday: 'long' }).format(now);
  const hijri = new Intl.DateTimeFormat('ar-SA-u-ca-islamic', { day: 'numeric', month: 'long', year: 'numeric' }).format(now);
  const greg = new Intl.DateTimeFormat('ar-EG', { day: 'numeric', month: 'long', year: 'numeric' }).format(now);
  const time = now.toLocaleTimeString('ar-EG');
  return { iso: now.toISOString(), display: `${weekday} ${hijri} — الموافق ${greg} — ${time}` };
}

async function initReadingTab() {
  const hint = document.getElementById('rdNewDateHint');
  if (hint) hint.textContent = `تاريخ بداية المشروع الجديد إن اعتمدته الآن: ${rdNowStamp().display}`;
  if (rdLoaded) { renderRdProjects(); return; }
  try {
    const res = await fetch('/api/reading-projects');
    const data = await res.json();
    rdProjects = Array.isArray(data.projects) ? data.projects : [];
    rdAssistants = Array.isArray(data.assistants) ? data.assistants : [];
    rdReaders = Array.isArray(data.readers) ? data.readers : [];
  } catch (e) { rdProjects = []; rdAssistants = []; rdReaders = []; }
  rdLoaded = true;
  renderRdProjects();
}
window.initReadingTab = initReadingTab;

function rdProject(id) { return rdProjects.find(p => p.id === id) || null; }

async function rdSave() {
  try {
    await fetch('/api/reading-projects', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projects: rdProjects, assistants: rdAssistants, readers: rdReaders }),
    });
  } catch (e) { /* يحفظ عند عودة الاتصال */ }
}

function renderRdProjects() {
  const wrap = document.getElementById('rdProjectsList');
  if (!wrap) return;
  if (!rdProjects.length) {
    wrap.innerHTML = '<div class="ms-empty">لا مشاريع قراءة بعد. أنشئ أول مشروع، ثم اسحب كتابه وابدأ القراءة والتحليل.</div>';
    return;
  }
  wrap.innerHTML = rdProjects.map(p => `
    <div class="ms-project-card">
      <div class="ms-project-card-title">📖 ${rdEsc(p.title)}</div>
      ${p.desc ? `<div class="ms-project-card-desc">${rdEsc(p.desc)}</div>` : ''}
      <div class="ms-project-card-stats">بدأ: ${rdEsc(p.created_display || '')}</div>
      <div class="ms-project-card-stats">${p.book ? `الكتاب: ${rdEsc(p.book.title)} · ${p.book.pages} صفحة${(p.book.parts && p.book.parts.length > 1) ? ` · ${p.book.parts.length} أجزاء` : ''} · وقفت عند صفحة ${p.page || 1}` : 'لا كتاب مسحوبًا بعد'}</div>
      <div class="ms-card-actions">
        <button type="button" class="ms-btn ms-btn-primary" onclick="rdOpenProject('${p.id}')">فتح القراءة</button>
        <button type="button" class="ms-btn ms-btn-danger" onclick="rdDeleteProject('${p.id}')">حذف</button>
      </div>
    </div>`).join('');
}

function rdCreateProject() {
  const title = document.getElementById('rdNewTitle').value.trim();
  if (!title) { rdToast('اكتب اسم المشروع أولًا'); return; }
  const stamp = rdNowStamp();
  const p = {
    id: rdUid(), title,
    desc: document.getElementById('rdNewDesc').value.trim(),
    created_at: stamp.iso, created_display: stamp.display,
    book: null, page: 1, annotations: {}, updated_at: stamp.iso,
  };
  rdProjects.unshift(p);
  document.getElementById('rdNewTitle').value = '';
  document.getElementById('rdNewDesc').value = '';
  rdSave(); renderRdProjects();
  rdOpenProject(p.id);
}

function rdDeleteProject(id) {
  const p = rdProject(id);
  if (!p || !confirm(`حذف مشروع قراءة «${p.title}» بكل تعليقاته وملصقاته؟`)) return;
  rdProjects = rdProjects.filter(x => x.id !== id);
  rdSave(); renderRdProjects();
}

// ---------- نافذة القراءة ----------
function rdOpenProject(id) {
  const p = rdProject(id);
  if (!p) return;
  rdCurrent = p;
  if (p.book) rdEnsureParts(p.book);
  document.getElementById('rdReaderTitle').textContent = `📖 ${p.book ? p.book.title : p.title}`;
  rdShowModal('rdReaderModal');
  rdBuildColorBars();
  rdSetTool('pen');
  rdUpdateBookUI();
  rdApplyView();
  rdLoadPage(p.page || 1);
}
window.rdOpenProject = rdOpenProject;

function rdCloseReader() {
  rdSaveNow(false);
  rdCloseModal('rdReaderModal');
  rdCurrent = null;
  renderRdProjects();
}

function rdSaveNow(manual) {
  if (!rdCurrent) return;
  rdCurrent.updated_at = new Date().toISOString();
  clearTimeout(rdSaveTimer);
  rdSave();
  const st = document.getElementById('rdSaveState');
  if (st) st.textContent = `حُفظ المشروع وموضع وقوفك (صفحة ${rdCurrent.page || 1}) — ${new Date().toLocaleTimeString('ar-EG')}`;
  if (manual) rdToast('💾 حُفظ المشروع وموضع وقوفك في القراءة');
}
function rdSaveSoon() {
  clearTimeout(rdSaveTimer);
  rdSaveTimer = setTimeout(() => rdSaveNow(false), 900);
}

// كتاب متعدد الأجزاء: parts متسلسلة وصفحات المشروع مرقّمة عبر الأجزاء كلها
function rdPartOf(nb) {
  return { source: nb.source, title: nb.title, file_name: nb.file_name || null, book_id: nb.book_id || null, pages: nb.pages || 1 };
}
function rdEnsureParts(b) {
  if (!b) return null;
  if (!Array.isArray(b.parts) || !b.parts.length) b.parts = [rdPartOf(b)];
  b.pages = b.parts.reduce((s, x) => s + (x.pages || 0), 0) || b.pages || 1;
  return b;
}
function rdPartPageUrl(part, localPage) {
  if (part.source === 'shamela') return `/api/book/pdf-image?book_id=${part.book_id}&pdf_page=${localPage}&v=${Date.now()}`;
  return `/api/reading-projects/page-image?file=${encodeURIComponent(part.file_name)}&page=${localPage}`;
}
function rdBookPageUrl(n) {
  const b = rdCurrent && rdEnsureParts(rdCurrent.book);
  if (!b) return '';
  let rest = n;
  for (const part of b.parts) {
    if (rest <= part.pages) return rdPartPageUrl(part, rest);
    rest -= part.pages;
  }
  const last = b.parts[b.parts.length - 1];
  return rdPartPageUrl(last, last.pages);
}
// اعتماد كتاب مسحوب: كتابًا أول أو جزءًا تاليًا يلحق بالتسلسل
function rdApplyBook(nb, asAppend) {
  if (!rdCurrent) return;
  if (asAppend && rdCurrent.book) {
    const b = rdEnsureParts(rdCurrent.book);
    const startPage = b.pages + 1;
    b.parts.push(rdPartOf(nb));
    rdEnsureParts(b);
    rdUpdateBookUI(); rdLoadPage(startPage); rdSaveNow(false);
    rdToast(`✔ أُضيف الجزء التالي «${nb.title}» (${nb.pages} صفحة) — يبدأ من صفحة ${startPage}، والكتاب الآن ${b.parts.length} أجزاء`);
    return;
  }
  nb.parts = [rdPartOf(nb)];
  rdCurrent.book = nb;
  rdCurrent.annotations = {};
  rdUpdateBookUI(); rdLoadPage(1); rdSaveNow(false);
}

// تنبيه وجود كتاب حالي عند ضغط أي زر سحب/رفع
let rdPendingSource = null;
let rdAppendMode = false;
function rdGuardSource(kind, ev) {
  if (rdCurrent && rdCurrent.book) {
    if (ev) ev.preventDefault();
    rdPendingSource = kind;
    const b = rdEnsureParts(rdCurrent.book);
    document.getElementById('rdBookExistsText').textContent =
      `في هذا المشروع كتاب قائم الآن: «${b.title}» — ${b.pages} صفحة${b.parts.length > 1 ? ` في ${b.parts.length} أجزاء` : ''}، وأنت واقف عند صفحة ${rdCurrent.page || 1}.`;
    rdShowModal('rdBookExistsModal');
    return false;
  }
  rdOpenSource(kind);
  return true;
}
function rdOpenSource(kind) {
  if (kind === 'shamela') rdOpenShamelaPicker();
  else if (kind === 'web') rdOpenWebFetch();
  else if (kind === 'upload') document.getElementById('rdUploadInput')?.click();
}
function rdBookExistsChoice(choice) {
  rdCloseModal('rdBookExistsModal');
  const kind = rdPendingSource;
  rdPendingSource = null;
  if (choice === 'append') {
    rdAppendMode = true;
    rdToast('اختر الجزء التالي — سيُلحق بصفحات الكتاب الحالي متسلسلًا');
    if (kind) rdOpenSource(kind);
  } else if (choice === 'new') {
    rdAppendMode = false;
    rdCloseReader();
    rdToast('📖 لحسن التنظيم: أنشئ مشروع قراءة جديدًا لهذا الكتاب من الأعلى', 5000);
    const t = document.getElementById('rdNewTitle');
    if (t) { t.scrollIntoView({ behavior: 'smooth', block: 'center' }); setTimeout(() => t.focus(), 350); }
  } else {
    rdAppendMode = false;
  }
}

function rdUpdateBookUI() {
  const p = rdCurrent;
  const has = !!(p && p.book);
  document.getElementById('rdToolbar').classList.toggle('is-disabled', !has);
  document.getElementById('rdEmpty').style.display = has ? 'none' : 'flex';
  document.getElementById('rdPageImg').style.display = has ? 'block' : 'none';
  document.getElementById('rdA4').classList.toggle('has-book', has);
  document.getElementById('rdPageTotal').textContent = has ? p.book.pages : '—';
  const titleEl = document.getElementById('rdReaderTitle');
  if (titleEl) titleEl.textContent = `📖 ${has ? p.book.title : p.title}`;
  if (has) rdEnsureParts(p.book);
  document.getElementById('rdBookInfo').textContent = has
    ? `الكتاب: ${p.book.title} (${p.book.source === 'shamela' ? 'من الشاملة المصوّرة' : p.book.source === 'web' ? 'من الشبكة' : 'PDF مرفوع'}) — ${p.book.pages} صفحة${p.book.parts.length > 1 ? ` في ${p.book.parts.length} أجزاء متسلسلة` : ''}`
    : '';
}

function rdLoadPage(n) {
  const p = rdCurrent;
  if (!p || !p.book) { rdRenderAnnotations(); return; }
  n = Math.max(1, Math.min(p.book.pages || 1, Number(n) || 1));
  p.page = n;
  document.getElementById('rdPageInput').value = n;
  const img = document.getElementById('rdPageImg');
  img.onload = () => { rdFitCanvas(); rdRenderAnnotations(); };
  img.onerror = () => { rdToast('تعذر عرض هذه الصفحة'); };
  img.src = rdBookPageUrl(n);
  document.getElementById('rdPageScroll').scrollTop = 0;
  rdHideSelBar();
  rdActiveSel = null;
  rdSaveSoon();
}

function rdFlipPage(d) {
  if (!rdCurrent || !rdCurrent.book) return;
  rdLoadPage((rdCurrent.page || 1) + d);
}
function rdGoPage(v) { rdLoadPage(Number(v)); }

function rdZoom(d) {
  const a4 = document.getElementById('rdA4');
  const cur = a4.offsetWidth || 595;
  const next = Math.max(280, Math.min(1500, cur + d * 600));
  a4.style.width = `${next}px`;
  setTimeout(() => { rdFitCanvas(); rdRenderAnnotations(); }, 30);
}

// ---------- الأدوات والرسم ----------
function rdBuildColorBars() {
  const mk = (elId, colors, cur, fn, target) => {
    const el = document.getElementById(elId);
    if (!el) return;
    el.innerHTML = colors.map(c => `<button type="button" class="rd-color${c === cur ? ' active' : ''}" style="background:${c}" onclick="${fn}('${c}')"></button>`).join('')
      + `<button type="button" class="rd-color-add" title="لون فارغ — اضغطه لإضافة لون جديد من منتقي الألوان" onclick="rdAddColor('${target}', event)">+</button>`;
  };
  mk('rdColors', RD_COLORS.concat(rdCustomColors.pen || []), rdColor, 'rdSetColor', 'pen');
  mk('rdNoteColors', RD_NOTE_COLORS.concat(rdCustomColors.note || []), rdNoteColor, 'rdSetNoteColor', 'note');
}
// اللون الفارغ: يفتح منتقي ألوان النظام فيُضاف اللون المختار إلى اللوحة ويُحفظ
function rdAddColor(target, ev) {
  if (ev) ev.stopPropagation();
  rdColorTarget = target;
  const picker = document.getElementById('rdColorPicker');
  if (!picker) return;
  if (picker.parentElement !== document.body) document.body.appendChild(picker);
  const btn = ev && ev.currentTarget;
  const r = btn ? btn.getBoundingClientRect() : { left: 24, top: 24, width: 28, height: 28 };
  picker.hidden = false;
  picker.style.position = 'fixed';
  picker.style.left = `${Math.max(8, r.left)}px`;
  picker.style.top = `${Math.max(8, r.top)}px`;
  picker.style.width = `${Math.max(28, r.width)}px`;
  picker.style.height = `${Math.max(28, r.height)}px`;
  picker.style.zIndex = '500000';
  picker.style.opacity = '0.02';
  picker.style.pointerEvents = 'auto';
  picker.value = target === 'note' ? rdNoteColor : rdColor;
  try {
    if (typeof picker.showPicker === 'function') picker.showPicker();
    else picker.click();
  } catch (e) {
    picker.click();
  }
}
document.addEventListener('DOMContentLoaded', () => {
  const picker = document.getElementById('rdColorPicker');
  if (!picker) return;
  picker.addEventListener('input', () => {
    const c = picker.value;
    const key = rdColorTarget === 'note' ? 'note' : 'pen';
    rdCustomColors[key] = rdCustomColors[key] || [];
    if (!rdCustomColors[key].includes(c)) rdCustomColors[key].push(c);
    try { localStorage.setItem('rdCustomColors', JSON.stringify(rdCustomColors)); } catch (e) { /* */ }
    if (key === 'note') rdNoteColor = c; else rdColor = c;
    rdBuildColorBars();
  });
});
function rdSetColor(c) { rdColor = c; rdBuildColorBars(); }
function rdSetNoteColor(c) { rdNoteColor = c; rdBuildColorBars(); }
function rdSetPenSize(s) {
  rdPenSize = s;
  document.querySelectorAll('#rdPenSizes button').forEach(b =>
    b.classList.toggle('active', Number(b.dataset.rdSize) === Number(s)));
}
function rdSetTool(t) {
  rdTool = t;
  document.querySelectorAll('#rdToolbar .rd-tool[data-rd-tool]').forEach(b =>
    b.classList.toggle('active', b.dataset.rdTool === t));
  document.getElementById('rdLoupe').hidden = t !== 'loupe';
}

function rdPageAnn() {
  const p = rdCurrent;
  if (!p) return { strokes: [], highlights: [], crops: [], notes: [], seq: [] };
  p.annotations = p.annotations || {};
  const k = String(p.page || 1);
  if (!p.annotations[k]) p.annotations[k] = { strokes: [], highlights: [], crops: [], notes: [], seq: [] };
  return p.annotations[k];
}

function rdFitCanvas() {
  const img = document.getElementById('rdPageImg');
  const cv = document.getElementById('rdCanvas');
  if (!img || !cv || !img.naturalWidth) return;
  cv.width = img.naturalWidth;
  cv.height = img.naturalHeight;
}

function rdRenderAnnotations() {
  const cv = document.getElementById('rdCanvas');
  if (!cv || !rdCurrent) return;
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  const ann = rdPageAnn();
  const W = cv.width, H = cv.height;
  (ann.highlights || []).forEach(h => {
    ctx.save();
    if (h.discussion_id) {
      ctx.fillStyle = RD_DISC_COLOR;
      ctx.fillRect(h.x * W, h.y * H, h.w * W, h.h * H);
    } else {
      ctx.globalAlpha = 0.35;
      ctx.fillStyle = h.c;
      ctx.fillRect(h.x * W, h.y * H, h.w * W, h.h * H);
    }
    ctx.restore();
  });
  (ann.strokes || []).forEach(s => {
    if (!s.pts || s.pts.length < 2) return;
    ctx.save();
    ctx.strokeStyle = s.c;
    ctx.lineWidth = Math.max(1, s.s * (W / 595));
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    s.pts.forEach(([x, y], i) => { if (i) ctx.lineTo(x * W, y * H); else ctx.moveTo(x * W, y * H); });
    ctx.stroke();
    ctx.restore();
  });
  (ann.crops || []).forEach(cr => {
    ctx.save();
    if (cr.discussion_id) {
      ctx.fillStyle = RD_DISC_COLOR;
      ctx.fillRect(cr.x * W, cr.y * H, cr.w * W, cr.h * H);
      ctx.strokeStyle = '#777';
    } else {
      ctx.strokeStyle = '#b4552d';
    }
    ctx.lineWidth = Math.max(1.5, W / 400);
    ctx.setLineDash([10, 7]);
    ctx.strokeRect(cr.x * W, cr.y * H, cr.w * W, cr.h * H);
    ctx.restore();
  });
  rdRenderNotes();
  rdRenderCropsBar();
}

function rdRenderNotes() {
  const layer = document.getElementById('rdNotesLayer');
  if (!layer || !rdCurrent) return;
  const ann = rdPageAnn();
  layer.innerHTML = (ann.notes || []).map((n, i) =>
    `<span class="rd-note" style="left:${n.x * 100}%;top:${n.y * 100}%;background:${n.c}" title="${rdEsc(n.text || 'ملحوظة')}" onclick="rdEditNote(${i}, event)">📌</span>`).join('');
}

function rdRenderCropsBar() {
  const bar = document.getElementById('rdCropsBar');
  if (!bar || !rdCurrent) return;
  const ann = rdPageAnn();
  const crops = ann.crops || [];
  bar.hidden = !crops.length;
  bar.innerHTML = crops.map((c, i) => `<button type="button" class="rd-crop-chip" onclick="rdZoomToCrop(${i})">✂ قصاصة ${i + 1} — صفحة ${rdCurrent.page}</button>`).join('');
}

function rdZoomToCrop(i) {
  const ann = rdPageAnn();
  const cr = (ann.crops || [])[i];
  if (!cr) return;
  const a4 = document.getElementById('rdA4');
  a4.style.width = `${Math.min(1500, Math.max(700, 595 / Math.max(cr.w, 0.08)))}px`;
  setTimeout(() => {
    rdFitCanvas(); rdRenderAnnotations();
    const sc = document.getElementById('rdPageScroll');
    sc.scrollTop = Math.max(0, cr.y * a4.offsetHeight - 120);
  }, 40);
}

function rdUndo() {
  const ann = rdPageAnn();
  const last = (ann.seq || []).pop();
  if (last === 's') ann.strokes.pop();
  else if (last === 'h') ann.highlights.pop();
  else if (last === 'c') ann.crops.pop();
  rdRenderAnnotations(); rdSaveSoon();
}

function rdClearPage() {
  if (!rdCurrent) return;
  if (!confirm(`⚠️ تنبيه: سيتم إزالة جميع التعليقات من هذه الصفحة فقط (صفحة ${rdCurrent.page || 1}: رسوم الأقلام والتظليل والقصاصات وملصقات الملحوظات)، وتبقى تعليقات بقية الصفحات كما هي دون مساس. متابعة المسح؟`)) return;
  const ann = rdPageAnn();
  ann.strokes = []; ann.highlights = []; ann.crops = []; ann.notes = []; ann.seq = [];
  document.querySelectorAll('.rd-note-editor').forEach(x => { if (x._rdNoteRo) x._rdNoteRo.disconnect(); x.remove(); });
  rdRenderAnnotations(); rdSaveSoon();
  rdToast(`🧹 مُسحت كل تعليقات صفحة ${rdCurrent.page || 1} وحدها`);
}

// ---------- عرض الصفحة: حدّة وتباين وخلفية ورقية ----------
const RD_BGS = {
  white: { page: '#ffffff', sepia: 0, bright: 1, sat: 1, scroll: '#8a8378' },
  yellow: { page: '#f7e7b4', sepia: 0.38, bright: 1.03, sat: 1.02, scroll: '#8a7f63' },
  beige: { page: '#eee0c3', sepia: 0.25, bright: 1.01, sat: 1, scroll: '#877d68' },
  gray: { page: '#e3e3e0', sepia: 0, bright: 0.98, sat: 0.72, scroll: '#6f6f6c' },
};
function rdView() {
  if (!rdCurrent) return { sharp: 0, contrast: 100, bg: 'white' };
  rdCurrent.view = Object.assign({ sharp: 0, contrast: 100, bg: 'white' }, rdCurrent.view || {});
  return rdCurrent.view;
}
function rdApplyView() {
  const v = rdView();
  const img = document.getElementById('rdPageImg');
  const a4 = document.getElementById('rdA4');
  const bg = RD_BGS[v.bg] || RD_BGS.white;
  if (a4) a4.style.background = bg.page;
  const scroll = document.getElementById('rdPageScroll');
  if (scroll) scroll.style.background = bg.scroll;
  const kernel = document.getElementById('rdSharpKernel');
  const k = Math.max(0, Math.min(2, (Number(v.sharp) || 0) / 50));
  if (kernel) kernel.setAttribute('kernelMatrix', `0 ${-k} 0 ${-k} ${1 + 4 * k} ${-k} 0 ${-k} 0`);
  if (img) {
    const parts = [];
    if (k > 0) parts.push('url(#rdSharpenFilter)');
    parts.push(`contrast(${v.contrast}%)`, `brightness(${bg.bright})`, `sepia(${bg.sepia})`, `saturate(${bg.sat})`);
    img.style.filter = parts.join(' ');
  }
  const sh = document.getElementById('rdSharp'); if (sh) sh.value = v.sharp;
  const ct = document.getElementById('rdContrast'); if (ct) ct.value = v.contrast;
  document.querySelectorAll('.rd-bg-btn').forEach(b => b.classList.toggle('active', b.dataset.rdbg === v.bg));
}
function rdSetView(key, val) {
  const v = rdView();
  v[key] = Number(val);
  rdApplyView(); rdSaveSoon();
}
function rdSetBg(bg) {
  const v = rdView();
  v.bg = bg;
  rdApplyView(); rdSaveSoon();
}
function rdResetView() {
  if (!rdCurrent) return;
  rdCurrent.view = { sharp: 0, contrast: 100, bg: 'white' };
  rdApplyView(); rdSaveSoon();
}

function rdHideSelBar() {
  const bar = document.getElementById('rdSelBar');
  if (bar) bar.hidden = true;
}
function rdShowSelBar(rect) {
  const bar = document.getElementById('rdSelBar');
  const a4 = document.getElementById('rdA4');
  if (!bar || !a4 || !rect) return;
  const left = (rect.x + rect.w / 2) * a4.offsetWidth;
  const top = rect.y * a4.offsetHeight;
  bar.style.left = `${left}px`;
  bar.style.top = `${Math.max(18, top)}px`;
  bar.hidden = false;
}
function rdSetActiveSel(kind, index, rect) {
  if (!rdCurrent || !rect) return;
  rdActiveSel = { page: rdCurrent.page || 1, kind, index, rect: { ...rect } };
  rdShowSelBar(rect);
}
function rdHitRegion(qx, qy, discussedOnly) {
  if (!rdCurrent) return null;
  const ann = rdPageAnn();
  const hit = (arr, kind) => {
    for (let i = (arr || []).length - 1; i >= 0; i--) {
      const r = arr[i];
      if (discussedOnly && !r.discussion_id) continue;
      if (qx >= r.x && qx <= r.x + r.w && qy >= r.y && qy <= r.y + r.h) {
        return { id: r.discussion_id || '', kind, index: i, rect: r };
      }
    }
    return null;
  };
  return hit(ann.crops, 'c') || hit(ann.highlights, 'h');
}
function rdHitDiscussion(qx, qy) { return rdHitRegion(qx, qy, true); }

// الشريط لا يبقى ظاهرًا: يختفي بعد مغادرة الموضع وشريطه مع مهلة قصيرة تكفي لبلوغ الأيقونات
let rdSelHideTimer = null;
function rdCancelSelHide() { clearTimeout(rdSelHideTimer); }
function rdArmSelHide() {
  clearTimeout(rdSelHideTimer);
  rdSelHideTimer = setTimeout(() => { rdHideSelBar(); rdSelFromHover = false; }, 320);
}

// أحداث الرسم على اللوحة
(function rdInitCanvasEvents() {
  const ready = () => {
    const cv = document.getElementById('rdCanvas');
    if (!cv) { setTimeout(ready, 600); return; }
    const selBar = document.getElementById('rdSelBar');
    if (selBar && !selBar.dataset.rdBound) {
      selBar.dataset.rdBound = '1';
      selBar.addEventListener('pointerenter', rdCancelSelHide);
      selBar.addEventListener('pointerleave', rdArmSelHide);
    }
    const pos = (e) => {
      const r = cv.getBoundingClientRect();
      return {
        x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
        y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
        px: e.clientX - r.left, py: e.clientY - r.top, rw: r.width, rh: r.height,
      };
    };
    cv.addEventListener('pointerdown', (e) => {
      if (!rdCurrent || !rdCurrent.book) return;
      const q = pos(e);
      const disc = rdHitDiscussion(q.x, q.y);
      // ضغط على موضع مناقشة محفوظة يفتحها مباشرة (أولوية على بدء رسم جديد)
      if (disc) {
        rdOpenDiscussion(disc.id);
        return;
      }
      if (rdTool === 'pen') {
        rdHideSelBar();
        rdDraw = { type: 's', pts: [[q.x, q.y]] };
        cv.setPointerCapture(e.pointerId);
      } else if (rdTool === 'highlight' || rdTool === 'crop') {
        rdHideSelBar();
        rdDraw = { type: rdTool === 'highlight' ? 'h' : 'c', x0: q.x, y0: q.y, x1: q.x, y1: q.y };
        cv.setPointerCapture(e.pointerId);
      } else if (rdTool === 'note') {
        const ann = rdPageAnn();
        ann.notes.push({ x: q.x, y: q.y, c: rdNoteColor, text: '' });
        rdRenderNotes(); rdSaveSoon();
        rdEditNote(ann.notes.length - 1);
      }
    });
    cv.addEventListener('pointermove', (e) => {
      const q = pos(e);
      // شريط أيقونات (تحليل/قراءة/مشاركة/نشر) عند التمرير على تحليل سابق رمادي فقط
      if (!rdDraw && rdTool !== 'loupe' && rdCurrent && rdCurrent.book) {
        const over = rdHitRegion(q.x, q.y, false);
        if (over) {
          rdCancelSelHide();
          rdActiveSel = { page: rdCurrent.page || 1, kind: over.kind, index: over.index, rect: { x: over.rect.x, y: over.rect.y, w: over.rect.w, h: over.rect.h }, discussion_id: over.id };
          rdSelFromHover = true;
          rdShowSelBar(rdActiveSel.rect);
        } else {
          rdArmSelHide();
        }
      }
      if (rdTool === 'loupe' && rdCurrent && rdCurrent.book) {
        const loupe = document.getElementById('rdLoupe');
        const limg = document.getElementById('rdLoupeImg');
        const img = document.getElementById('rdPageImg');
        loupe.hidden = false;
        loupe.style.right = `${q.px - 90}px`;
        loupe.style.top = `${q.py - 90}px`;
        const Z = 2.4;
        limg.src = img.src;
        limg.style.filter = img.style.filter;
        limg.style.width = `${q.rw * Z}px`;
        limg.style.right = `${-(q.x * q.rw * Z - 90)}px`;
        limg.style.top = `${-(q.y * q.rh * Z - 90)}px`;
        return;
      }
      if (!rdDraw) return;
      if (rdDraw.type === 's') {
        rdDraw.pts.push([q.x, q.y]);
        rdRenderAnnotations();
        const cvx = cv.getContext('2d');
        const s = { c: rdColor, s: rdPenSize, pts: rdDraw.pts };
        cvx.save();
        cvx.strokeStyle = s.c; cvx.lineWidth = Math.max(1, s.s * (cv.width / 595));
        cvx.lineCap = 'round'; cvx.lineJoin = 'round';
        cvx.beginPath();
        s.pts.forEach(([x, y], i) => { if (i) cvx.lineTo(x * cv.width, y * cv.height); else cvx.moveTo(x * cv.width, y * cv.height); });
        cvx.stroke(); cvx.restore();
      } else {
        rdDraw.x1 = q.x; rdDraw.y1 = q.y;
        rdRenderAnnotations();
        const cvx = cv.getContext('2d');
        const x = Math.min(rdDraw.x0, rdDraw.x1), w = Math.abs(rdDraw.x1 - rdDraw.x0);
        if (rdDraw.type === 'h') {
          const lineH = 36 / q.rh;
          cvx.save(); cvx.globalAlpha = 0.35; cvx.fillStyle = rdColor;
          cvx.fillRect(x * cv.width, (rdDraw.y0 - lineH / 2) * cv.height, w * cv.width, lineH * cv.height);
          cvx.restore();
        } else {
          const y = Math.min(rdDraw.y0, rdDraw.y1), h = Math.abs(rdDraw.y1 - rdDraw.y0);
          cvx.save(); cvx.strokeStyle = '#b4552d'; cvx.lineWidth = 2; cvx.setLineDash([8, 6]);
          cvx.strokeRect(x * cv.width, y * cv.height, w * cv.width, h * cv.height);
          cvx.restore();
        }
      }
    });
    const finish = (e) => {
      if (!rdDraw) return;
      const ann = rdPageAnn();
      if (rdDraw.type === 's') {
        if (rdDraw.pts.length > 1) { ann.strokes.push({ c: rdColor, s: rdPenSize, pts: rdDraw.pts }); ann.seq.push('s'); }
      } else if (rdDraw.type === 'h') {
        const x = Math.min(rdDraw.x0, rdDraw.x1), w = Math.abs(rdDraw.x1 - rdDraw.x0);
        if (w > 0.01) {
          const r = cv.getBoundingClientRect();
          const lineH = 36 / r.height;
          const rect = { x, y: rdDraw.y0 - lineH / 2, w, h: lineH };
          ann.highlights.push({ ...rect, c: rdColor });
          ann.seq.push('h');
          rdSetActiveSel('h', ann.highlights.length - 1, rect);
        }
      } else if (rdDraw.type === 'c') {
        const x = Math.min(rdDraw.x0, rdDraw.x1), y = Math.min(rdDraw.y0, rdDraw.y1);
        const w = Math.abs(rdDraw.x1 - rdDraw.x0), h = Math.abs(rdDraw.y1 - rdDraw.y0);
        if (w > 0.01 && h > 0.01) {
          const rect = { x, y, w, h };
          ann.crops.push({ ...rect });
          ann.seq.push('c');
          rdSetActiveSel('c', ann.crops.length - 1, rect);
        }
      }
      rdDraw = null;
      rdRenderAnnotations(); rdSaveSoon();
    };
    cv.addEventListener('pointerup', finish);
    cv.addEventListener('pointercancel', () => { rdDraw = null; rdRenderAnnotations(); });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
  else ready();
})();

// ملصق ملحوظات: محرر صغير فوق موضعه
function rdEditNote(i, ev) {
  if (ev) ev.stopPropagation();
  const ann = rdPageAnn();
  const n = (ann.notes || [])[i];
  if (!n) return;
  document.querySelectorAll('.rd-note-editor').forEach(x => { if (x._rdNoteRo) x._rdNoteRo.disconnect(); x.remove(); });
  const layer = document.getElementById('rdNotesLayer');
  const ed = document.createElement('div');
  ed.className = 'rd-note-editor';
  ed.style.background = n.c;
  ed.style.left = `${Math.max(0, Math.min(62, n.x * 100))}%`;
  ed.style.right = 'auto';
  ed.style.top = `${n.y * 100}%`;
  ed.innerHTML = `<textarea placeholder="اكتب ملحوظتك هنا...">${rdEsc(n.text || '')}</textarea>
    <div class="rd-note-btns">
      <button type="button" data-act="save">حفظ الملحوظة</button>
      <button type="button" data-act="del">حذف الملصق</button>
      <button type="button" data-act="x">إغلاق</button>
    </div>`;
  layer.appendChild(ed);
  const ta = ed.querySelector('textarea');
  const anchorRight = ed.offsetLeft + ed.offsetWidth;
  const anchorTop = ed.offsetTop;
  const ro = new ResizeObserver(() => {
    const layerW = layer.clientWidth || 1;
    const layerH = layer.clientHeight || 1;
    let w = ed.offsetWidth;
    let h = ed.offsetHeight;
    const maxW = Math.max(160, layerW - 8);
    const maxH = Math.max(90, layerH - 8);
    if (w > maxW) {
      ta.style.width = `${Math.max(140, maxW - (w - ta.offsetWidth))}px`;
      w = ed.offsetWidth;
    }
    if (h > maxH) {
      ta.style.height = `${Math.max(62, maxH - (h - ta.offsetHeight))}px`;
      h = ed.offsetHeight;
    }
    let left = anchorRight - w;
    if (left < 4) left = 4;
    if (left + w > layerW - 4) left = Math.max(4, layerW - w - 4);
    let top = anchorTop;
    if (top + h > layerH - 4) top = Math.max(4, layerH - h - 4);
    ed.style.left = `${(left / layerW) * 100}%`;
    ed.style.top = `${(top / layerH) * 100}%`;
  });
  ro.observe(ta);
  ed._rdNoteRo = ro;
  const closeEd = () => { ro.disconnect(); ed.remove(); };
  const removeNote = () => {
    const idx = (ann.notes || []).indexOf(n);
    if (idx >= 0) ann.notes.splice(idx, 1);
    closeEd();
    rdRenderNotes();
    rdSaveSoon();
  };
  ta.focus();
  ed.querySelector('[data-act="save"]').onclick = () => {
    if (!ta.value.trim()) { removeNote(); return; }
    n.text = ta.value;
    closeEd();
    rdRenderNotes();
    rdSaveSoon();
  };
  ed.querySelector('[data-act="del"]').onclick = () => removeNote();
  ed.querySelector('[data-act="x"]').onclick = () => { if (!ta.value.trim()) removeNote(); else closeEd(); };
}
window.rdEditNote = rdEditNote;

// ---------- مصادر الكتاب ----------
document.addEventListener('DOMContentLoaded', () => {
  const up = document.getElementById('rdUploadInput');
  if (up) up.addEventListener('change', async () => {
    const file = (up.files || [])[0];
    up.value = '';
    if (!file || !rdCurrent) return;
    rdToast('جارٍ رفع الكتاب إلى مجلد مشاريع القراءة...');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/reading-projects/upload-book', { method: 'POST', body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'تعذر رفع الكتاب');
      const wasAppend = rdAppendMode; rdAppendMode = false;
      rdApplyBook({ source: 'pdf', title: data.title, file_name: data.file_name, pages: data.pages }, wasAppend);
      if (!wasAppend) rdToast(`✔ سُحب كتاب «${data.title}» (${data.pages} صفحة) — فعّلت الأدوات`);
    } catch (e) { rdToast(`❌ ${e.message}`, 5000); }
  });
});

function rdOpenShamelaPicker() { rdShowModal('rdShamelaModal'); setTimeout(() => document.getElementById('rdShamelaQuery')?.focus(), 120); }

async function rdSearchShamela() {
  const q = document.getElementById('rdShamelaQuery').value.trim();
  const box = document.getElementById('rdShamelaResults');
  if (!q) { rdToast('اكتب اسم الكتاب أو مؤلفه أولًا'); return; }
  box.innerHTML = '<div class="ms-rec-loading">⏳ جارٍ البحث في فهرس الشاملة...</div>';
  try {
    const res = await fetch(`/api/books/search?q=${encodeURIComponent(q)}&limit=30`);
    const data = await res.json();
    const books = data.books || [];
    box.innerHTML = books.length ? books.map(b => `
      <div class="ms-form-row" style="justify-content:space-between;border-bottom:1px dashed var(--border-subtle);padding:6px 0">
        <span><strong>${rdEsc(b.title)}</strong> <span class="ms-wb-meta">${rdEsc(b.author)} · ${rdEsc(b.category)}</span></span>
        <button type="button" class="ms-btn" onclick="rdPullShamela(${b.book_id}, '${rdEsc(b.title).replace(/'/g, '')}')">⬇ سحب المصوّرة</button>
      </div>`).join('') : '<div class="ms-hint">لا كتب مطابقة في الفهرس.</div>';
  } catch (e) { box.innerHTML = `<div class="ms-hint">❌ ${rdEsc(e.message)}</div>`; }
}

async function rdPullShamela(bookId, title) {
  if (!rdCurrent) return;
  rdToast(`جارٍ التحقق من النسخة المصوّرة لـ«${title}»...`);
  try {
    const res = await fetch(`/api/book/pdf-info?book_id=${bookId}`);
    const info = await res.json();
    if (!info.available) { rdAppendMode = false; rdToast(`⚠️ ${info.reason || 'لا نسخة مصوّرة منزّلة لهذا الكتاب على جهازك'}`, 6000); return; }
    const nb = { source: 'shamela', book_id: bookId, title, pages: info.pdf_pages || 1 };
    const wasAppend = rdAppendMode; rdAppendMode = false;
    rdCloseModal('rdShamelaModal');
    rdApplyBook(nb, wasAppend);
    if (!wasAppend) rdToast(`✔ سُحب «${title}» من الشاملة المصوّرة (${nb.pages} صفحة) — فعّلت الأدوات`);
  } catch (e) { rdToast(`❌ ${e.message}`, 5000); }
}
window.rdPullShamela = rdPullShamela;

function rdOpenWebFetch() {
  rdShowModal('rdWebModal');
  document.getElementById('rdWebBarWrap').hidden = true;
  document.getElementById('rdWebStatus').textContent = 'الصق رابط PDF مباشرًا للكتاب، فيُسحب إلى مجلد مشاريع القراءة على جهازك ويُعرض عند اكتماله.';
  setTimeout(() => document.getElementById('rdWebUrl')?.focus(), 120);
}

let rdWebPoll = null;
async function rdFetchWeb() {
  const urlInput = document.getElementById('rdWebUrl');
  let url = urlInput.value.trim();
  if (!url) { rdToast('الصق رابط الكتاب أولًا'); return; }
  // تُضاف https:// تلقائيًا إن غابت حتى لا يُرفض العنوان لخلوّه من البروتوكول
  if (!/^https?:\/\//i.test(url)) { url = 'https://' + url; urlInput.value = url; }
  const btn = document.getElementById('rdWebFetchBtn');
  const barWrap = document.getElementById('rdWebBarWrap');
  const bar = document.getElementById('rdWebBarFill');
  const st = document.getElementById('rdWebStatus');
  btn.disabled = true;
  barWrap.hidden = false;
  bar.style.width = '12%';
  st.textContent = 'بدأ السحب من الشبكة — فضلًا انتظر...';
  try {
    const res = await fetch('/api/reading-projects/fetch-web', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر بدء السحب');
    const job = data.job;
    clearInterval(rdWebPoll);
    rdWebPoll = setInterval(async () => {
      try {
        const pr = await fetch(`/api/reading-projects/fetch-web-progress?job=${job}`);
        const j = await pr.json();
        if (j.pct >= 0) bar.style.width = `${j.pct}%`;
        st.textContent = j.status === 'running'
          ? `جارٍ السحب: ${(j.downloaded / 1048576).toFixed(1)} MB${j.total ? ` من ${(j.total / 1048576).toFixed(1)} MB (${j.pct}٪)` : ''} — فضلًا انتظر...`
          : '';
        if (j.status === 'done') {
          clearInterval(rdWebPoll);
          bar.style.width = '100%';
          st.textContent = `✔ اكتمل سحب «${j.title}» (${j.pages} صفحة) — يُعرض الآن في نافذة القراءة.`;
          if (rdCurrent) {
            const wasAppend = rdAppendMode; rdAppendMode = false;
            rdApplyBook({ source: 'web', title: j.title, file_name: j.file_name, pages: j.pages }, wasAppend);
          }
          btn.disabled = false;
          setTimeout(() => rdCloseModal('rdWebModal'), 900);
        } else if (j.status === 'error') {
          clearInterval(rdWebPoll);
          st.textContent = `❌ تعذر السحب: ${j.error}`;
          btn.disabled = false;
        }
      } catch (e) { /* تستمر المحاولة التالية */ }
    }, 1000);
  } catch (e) {
    st.textContent = `❌ ${e.message}`;
    btn.disabled = false;
  }
}

// =============================================================================
// مساعدون وقرّاء وتحليل المحدد ومشاركة/نشر
// =============================================================================
function rdApiKey() {
  try {
    if (typeof getOpenRouterKey === 'function') return getOpenRouterKey() || '';
    return localStorage.getItem('openrouter_api_key') || '';
  } catch (e) { return ''; }
}
function rdMd(text) {
  const t = String(text || '');
  if (typeof marked !== 'undefined' && (marked.parse || typeof marked === 'function')) {
    try { return (marked.parse || marked)(t); } catch (e) { /* */ }
  }
  return rdEsc(t).replace(/\n/g, '<br>');
}
function rdCite() {
  const p = rdCurrent;
  if (!p || !p.book) return '';
  const b = rdEnsureParts(p.book);
  let rest = p.page || 1, partIdx = 0, local = rest;
  for (let i = 0; i < b.parts.length; i++) {
    if (rest <= b.parts[i].pages) { partIdx = i; local = rest; break; }
    rest -= b.parts[i].pages;
    partIdx = i; local = b.parts[i].pages;
  }
  const partLabel = b.parts.length > 1 ? `الجزء ${partIdx + 1}` : 'الجزء 1';
  return `«${b.title}» — ${partLabel} — صفحة ${local} (صفحة المشروع ${p.page})`;
}

// نماذج المساعد: قائمة منسدلة ببحث وفلترة سريعة (كنافذة بطاقات الوكلاء)
let rdModelCatalog = null;
let rdVisionCatalog = null;
async function rdLoadModelCatalog() {
  if (rdModelCatalog) return rdModelCatalog;
  const res = await fetch('/api/openrouter/models');
  const data = await res.json();
  const models = data.models || data.data || [];
  rdModelCatalog = models.map(m => ({ id: m.id || m.model_id || m.name, name: m.name || m.id })).filter(m => m.id);
  return rdModelCatalog;
}
async function rdLoadVisionCatalog() {
  if (rdVisionCatalog) return rdVisionCatalog;
  const res = await fetch('/api/manuscripts/models');
  const data = await res.json();
  rdVisionCatalog = (data.models || []).filter(m => m.vision)
    .map(m => ({ id: m.id || m.model_id || m.name, name: m.name || m.id })).filter(m => m.id);
  return rdVisionCatalog;
}
function rdRenderAsstModelOptions() {
  const list = document.getElementById('rdAsstModelOptions');
  const trigger = document.getElementById('rdAsstModelTriggerText');
  const hidden = document.getElementById('rdAsstModel');
  if (!list) return;
  const models = rdModelCatalog || [];
  if (!models.length) {
    list.innerHTML = '<div style="padding:10px;color:var(--text-muted)">لا نماذج متاحة — تحقق من مفتاح OpenRouter في الخدمات</div>';
    if (trigger) trigger.textContent = 'لا نماذج متاحة';
    return;
  }
  if (hidden && !hidden.value) hidden.value = models[0].id;
  const selId = hidden ? hidden.value : '';
  list.innerHTML = models.map(m => `
    <div class="custom-model-item ${m.id === selId ? 'active' : ''}" data-rd-model-id="${rdEsc(m.id)}" data-rd-model-name="${rdEsc(m.name)}" onclick="rdSelectAsstModel('${rdEsc(m.id)}')">
      <span class="custom-model-item-name" title="${rdEsc(m.id)}">${rdEsc(m.name)}</span>
    </div>`).join('');
  const sel = models.find(m => m.id === selId) || models[0];
  if (trigger && sel) { trigger.textContent = sel.name; trigger.title = sel.id; }
}
function rdToggleAsstModelDropdown(event) {
  if (event) event.stopPropagation();
  const w = document.getElementById('rdAsstModelWrapper');
  if (!w) return;
  const open = w.classList.toggle('open');
  if (open) setTimeout(() => document.getElementById('rdAsstModelSearch')?.focus(), 50);
}
function rdSelectAsstModel(id) {
  const hidden = document.getElementById('rdAsstModel');
  if (hidden) hidden.value = id;
  document.getElementById('rdAsstModelWrapper')?.classList.remove('open');
  rdRenderAsstModelOptions();
}
function rdFilterAsstModels(q) {
  const needle = String(q || '').trim().toLowerCase();
  document.querySelectorAll('#rdAsstModelOptions .custom-model-item').forEach(el => {
    const hay = `${el.dataset.rdModelId || ''} ${el.dataset.rdModelName || ''}`.toLowerCase();
    el.style.display = !needle || hay.includes(needle) ? 'flex' : 'none';
  });
}
function rdClearAsstModelSearch() {
  const inp = document.getElementById('rdAsstModelSearch');
  if (inp) { inp.value = ''; rdFilterAsstModels(''); inp.focus(); }
}
// نماذج القارئ: قائمة راديو قابلة للتصفية (كنماذج نافذة النقد والمقارنة)
function rdRenderVisionModelOptions() {
  const box = document.getElementById('rdVisModelList');
  if (!box) return;
  const models = rdVisionCatalog || [];
  if (!models.length) {
    box.innerHTML = '<div style="font-size:12.5px;color:var(--text-muted);padding:6px">لا نماذج بصرية متاحة — تحقق من الخدمات</div>';
    return;
  }
  const prev = box.querySelector('input[name="rdVisModelPick"]:checked')?.value || models[0].id;
  box.innerHTML = models.map(m => `
    <label class="crit-model-row"><input type="radio" name="rdVisModelPick" value="${rdEsc(m.id)}" ${m.id === prev ? 'checked' : ''}><span>${rdEsc(m.name)}</span></label>`).join('');
}
function rdFilterVisionModels(q) {
  const needle = String(q || '').trim().toLowerCase();
  document.querySelectorAll('#rdVisModelList .crit-model-row').forEach(el => {
    el.style.display = !needle || el.textContent.toLowerCase().includes(needle) ? 'flex' : 'none';
  });
}
function rdUpdateAsstScopeLabel() {
  const label = document.getElementById('rdAsstScopeLabel');
  const badge = document.getElementById('rdAsstScopeBadge');
  const clear = document.getElementById('rdAsstScopeClear');
  if (!label) return;
  const n = rdAsstDraftBooks.length;
  label.textContent = n === 0 ? 'جميع كتب الشاملة — المكتبة كاملة'
    : n === 1 ? rdAsstDraftBooks[0].title : `محدد: ${n} كتب`;
  if (badge) { badge.textContent = n; badge.style.display = n ? 'inline-block' : 'none'; }
  if (clear) clear.style.display = n ? 'inline-block' : 'none';
}
function rdOpenAssistantScope() {
  window._rdAssistantBookTitles = rdAsstDraftBooks.map(b => b.title);
  if (typeof openSearchScopeModal === 'function') openSearchScopeModal('rd_assistant');
  else rdToast('نافذة نطاق البحث غير متاحة');
}
window.onRdAssistantBooks = function (titles) {
  rdAsstDraftBooks = (titles || []).map(t => ({ title: t }));
  rdUpdateAsstScopeLabel();
};
function rdClearAssistantScope(event) {
  if (event) event.stopPropagation();
  rdAsstDraftBooks = [];
  window._rdAssistantBookTitles = [];
  rdUpdateAsstScopeLabel();
}

function rdRenderAssistantsList() {
  const box = document.getElementById('rdAssistantsList');
  if (!box) return;
  if (!rdAssistants.length) { box.innerHTML = '<div class="ms-hint">لا مساعدين بعد.</div>'; return; }
  box.innerHTML = rdAssistants.map(a => `
    <div class="rd-entity-card">
      <div><strong>🧠 ${rdEsc(a.name)}</strong><div class="ms-hint">${rdEsc(a.model)} · ${(a.books || []).length} كتاب</div></div>
      <span class="rd-mode-btns">
        <button type="button" class="ms-btn" onclick="rdEditAssistant('${a.id}')">تعديل</button>
        <button type="button" class="ms-btn ms-btn-danger" onclick="rdDeleteAssistant('${a.id}')">حذف</button>
      </span>
    </div>`).join('');
}
function rdRenderReadersList() {
  const box = document.getElementById('rdReadersList');
  if (!box) return;
  if (!rdReaders.length) { box.innerHTML = '<div class="ms-hint">لا قرّاء بعد.</div>'; return; }
  box.innerHTML = rdReaders.map(r => `
    <div class="rd-entity-card">
      <div><strong>👁 ${rdEsc(r.name)}</strong><div class="ms-hint">${rdEsc(r.model)}</div></div>
      <button type="button" class="ms-btn ms-btn-danger" onclick="rdDeleteReader('${r.id}')">حذف</button>
    </div>`).join('');
}

function rdSetAsstAdoptLabel() {
  const btn = document.getElementById('rdAsstAdoptBtn');
  if (btn) btn.textContent = rdEditingAsstId ? 'حفظ التعديل' : 'اعتمد';
}
async function rdOpenCreateAssistant() {
  rdEditingAsstId = null;
  rdSetAsstAdoptLabel();
  rdAsstDraftBooks = [];
  document.getElementById('rdAsstName').value = '';
  document.getElementById('rdAsstPrompt').value = RD_DEFAULT_ASST_PROMPT;
  const hidden = document.getElementById('rdAsstModel');
  if (hidden) hidden.value = '';
  const search = document.getElementById('rdAsstModelSearch');
  if (search) search.value = '';
  rdUpdateAsstScopeLabel();
  rdShowModal('rdAssistantModal');
  rdRenderAssistantsList();
  const list = document.getElementById('rdAsstModelOptions');
  if (list) list.innerHTML = '<div style="padding:10px;color:var(--text-muted)">جارٍ جلب النماذج...</div>';
  try { await rdLoadModelCatalog(); rdRenderAsstModelOptions(); }
  catch (e) { if (list) list.innerHTML = `<div style="padding:10px">❌ ${rdEsc(e.message)}</div>`; }
}
async function rdOpenCreateReader() {
  document.getElementById('rdVisName').value = '';
  const search = document.getElementById('rdVisModelSearch');
  if (search) search.value = '';
  rdShowModal('rdVisionReaderModal');
  rdRenderReadersList();
  const box = document.getElementById('rdVisModelList');
  if (box) box.innerHTML = '<div style="font-size:12.5px;color:var(--text-muted);padding:6px">جارٍ جلب النماذج البصرية...</div>';
  try { await rdLoadVisionCatalog(); rdRenderVisionModelOptions(); }
  catch (e) { if (box) box.innerHTML = `<div style="font-size:12.5px;padding:6px">❌ ${rdEsc(e.message)}</div>`; }
}

function rdAdoptAssistant() {
  const name = document.getElementById('rdAsstName').value.trim();
  const model = document.getElementById('rdAsstModel').value;
  const prompt = document.getElementById('rdAsstPrompt').value.trim() || RD_DEFAULT_ASST_PROMPT;
  if (!name) { rdToast('اكتب اسم المساعد'); return; }
  if (!model) { rdToast('اختر نموذجًا'); return; }
  const books = rdAsstDraftBooks.map(b => ({ ...b }));
  if (rdEditingAsstId) {
    const cur = rdAssistants.find(a => a.id === rdEditingAsstId);
    if (cur) Object.assign(cur, { name, model, prompt, books, updated_at: new Date().toISOString() });
    rdEditingAsstId = null;
    rdSetAsstAdoptLabel();
    rdToast(`✔ حُفظ تعديل المساعد «${name}»`);
  } else {
    rdAssistants.unshift({
      id: rdUid(), name, model, prompt, books,
      created_at: new Date().toISOString(),
    });
    rdToast(`✔ اعتُمد المساعد «${name}»`);
  }
  rdSave();
  rdRenderAssistantsList();
  document.getElementById('rdAsstName').value = '';
  document.getElementById('rdAsstPrompt').value = RD_DEFAULT_ASST_PROMPT;
  rdAsstDraftBooks = [];
  rdUpdateAsstScopeLabel();
}
async function rdEditAssistant(id) {
  const a = rdAssistants.find(x => x.id === id);
  if (!a) return;
  rdEditingAsstId = id;
  rdSetAsstAdoptLabel();
  document.getElementById('rdAsstName').value = a.name || '';
  document.getElementById('rdAsstPrompt').value = a.prompt || RD_DEFAULT_ASST_PROMPT;
  rdAsstDraftBooks = (a.books || []).map(b => ({ title: b.title, book_id: b.book_id }));
  window._rdAssistantBookTitles = rdAsstDraftBooks.map(b => b.title).filter(Boolean);
  rdUpdateAsstScopeLabel();
  try { await rdLoadModelCatalog(); } catch (e) { /* تبقى القائمة الحالية */ }
  const hidden = document.getElementById('rdAsstModel');
  if (hidden) hidden.value = a.model || '';
  rdRenderAsstModelOptions();
  document.getElementById('rdAsstName')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  rdToast(`تعديل «${a.name}» — عدّل الحقول ثم اضغط حفظ التعديل`);
}
function rdDeleteAssistant(id) {
  if (!confirm('حذف هذا المساعد؟')) return;
  rdAssistants = rdAssistants.filter(a => a.id !== id);
  if (rdEditingAsstId === id) { rdEditingAsstId = null; rdSetAsstAdoptLabel(); }
  rdSave(); rdRenderAssistantsList();
}
function rdAdoptVisionReader() {
  const name = document.getElementById('rdVisName').value.trim();
  const model = document.querySelector('input[name="rdVisModelPick"]:checked')?.value || '';
  if (!name) { rdToast('اكتب اسم القارئ'); return; }
  if (!model) { rdToast('اختر نموذجًا بصريًا'); return; }
  rdReaders.unshift({ id: rdUid(), name, model, created_at: new Date().toISOString() });
  rdSave(); rdRenderReadersList();
  rdToast(`✔ اعتُمد القارئ «${name}»`);
  document.getElementById('rdVisName').value = '';
}
function rdDeleteReader(id) {
  if (!confirm('حذف هذا القارئ؟')) return;
  rdReaders = rdReaders.filter(r => r.id !== id);
  rdSave(); rdRenderReadersList();
}

function rdNeedActiveSel() {
  if (!rdActiveSel || !rdCurrent) { rdToast('حدّد أولًا موضعًا بأداة التظليل أو القص'); return false; }
  return true;
}
function rdDefaultReader() {
  if (!rdReaders.length) { rdToast('أنشئ قارئًا بصريًا أولًا بزر «إنشاء قارئ»'); return null; }
  return rdReaders[0];
}

async function rdCropSelBlob() {
  if (!rdActiveSel) return null;
  const img = document.getElementById('rdPageImg');
  if (!img || !img.naturalWidth) return null;
  const r = rdActiveSel.rect;
  const sx = Math.max(0, Math.floor(r.x * img.naturalWidth));
  const sy = Math.max(0, Math.floor(r.y * img.naturalHeight));
  const sw = Math.max(1, Math.floor(r.w * img.naturalWidth));
  const sh = Math.max(1, Math.floor(r.h * img.naturalHeight));
  const c = document.createElement('canvas');
  c.width = sw; c.height = sh;
  c.getContext('2d').drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh);
  return await new Promise(resolve => c.toBlob(b => resolve(b), 'image/png'));
}

async function rdUploadBlob(blob, name) {
  const fd = new FormData();
  fd.append('file', blob, name || 'rd-sel.png');
  const up = await fetch('/api/chat/upload', { method: 'POST', body: fd });
  const data = await up.json().catch(() => ({}));
  if (!up.ok || !data.file_path) throw new Error(data.detail || 'تعذر رفع المحدد');
  return data;
}

async function rdOcrSelection() {
  const reader = rdDefaultReader();
  if (!reader) return null;
  const blob = await rdCropSelBlob();
  if (!blob) throw new Error('تعذر قص موضع التحديد من الصفحة');
  const up = await rdUploadBlob(blob, 'rd-sel.png');
  const res = await fetch('/api/manuscripts/transcribe-one', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: up.file_path, model: reader.model, api_key: rdApiKey() }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'تعذرت قراءة المحدد');
  return { text: (data.text || '').trim(), file_url: up.file_url || '', reader };
}

// ---- أيقونات التحديد ----
function rdSelAnalyze() {
  if (!rdNeedActiveSel()) return;
  rdHideSelBar(); rdSelFromHover = false;
  if (!rdAssistants.length) { rdToast('أنشئ مساعدًا أولًا بزر «إنشاء مساعد»'); return; }
  if (!rdDefaultReader()) return;
  const box = document.getElementById('rdPickAsstList');
  box.innerHTML = rdAssistants.map(a => `
    <div class="rd-entity-card">
      <div><strong>🧠 ${rdEsc(a.name)}</strong><div class="ms-hint">${rdEsc(a.model)} · ${(a.books || []).length ? `${a.books.length} كتاب محدد` : 'بلا نطاق كتب'}</div></div>
      <span class="rd-mode-btns">
        <button type="button" class="ms-btn" title="يجيب من ذاكرة النموذج" onclick="rdStartAnalysis('${a.id}', 'fast')">⚡ سريع</button>
        <button type="button" class="ms-btn ms-btn-primary" title="يجيب من نطاق الكتب المحددة ويمتنع عن ذاكرته" onclick="rdStartAnalysis('${a.id}', 'edited')">✒️ محرر</button>
      </span>
    </div>`).join('');
  rdShowModal('rdPickAsstModal');
}

const RD_FAST_DIRECTIVE = 'أجب من ذاكرتك مباشرة عن النص المعروض. لا تبحث في المكتبة ولا تستدعِ كتبًا ولا مراسي بحث ولا شواهد. الإجابة من ذاكرتك وحدها، بين متوسطة ومختصرة اختصارًا غير مخل، ووفق توجيه المساعد. لا تذكر هذا التوجيه ولا تعِده في إجابتك.';
const RD_EDITED_DIRECTIVE = 'أجب من نطاق الكتب المحددة وحدها، ومن الشواهد المسترجعة منه حصرًا. امتنع امتناعًا تامًا عن الإجابة من ذاكرتك؛ فما لم تجده في الشواهد المسترجعة صرّح بغيابه ولا تكمله من محفوظك. التزم بالإحالة النموذجية لكل دعوى. لا تذكر هذا التوجيه ولا تعِده في إجابتك.';

async function rdStartAnalysis(asstId, mode) {
  const asst = rdAssistants.find(a => a.id === asstId);
  if (!asst || !rdCurrent || !rdActiveSel) return;
  mode = mode === 'fast' ? 'fast' : 'edited';
  rdCloseModal('rdPickAsstModal');
  const discId = rdUid();
  const disc = {
    id: discId,
    page: rdActiveSel.page,
    kind: rdActiveSel.kind,
    index: rdActiveSel.index,
    rect: { ...rdActiveSel.rect },
    assistant_id: asst.id,
    assistant_name: asst.name,
    model: asst.model,
    mode,
    extracted_text: '',
    messages: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  rdCurrent.discussions = rdCurrent.discussions || {};
  rdCurrent.discussions[discId] = disc;
  // ربط التحديد بالمناقشة وتظليله رماديًا
  const ann = rdPageAnn();
  const arr = rdActiveSel.kind === 'c' ? ann.crops : ann.highlights;
  if (arr && arr[rdActiveSel.index]) {
    arr[rdActiveSel.index].discussion_id = discId;
    if (rdActiveSel.kind === 'h') arr[rdActiveSel.index].c = '#888888';
  }
  rdHideSelBar();
  rdRenderAnnotations();
  rdOpenDiscussion(discId, true);
  const st = document.getElementById('rdAnalysisStatus');
  st.textContent = 'جار تحليل النص... (استخراج بالنص بالقارئ ثم إرساله للمساعد)';
  try {
    const ocr = await rdOcrSelection();
    if (!ocr || !ocr.text) throw new Error('لم يُستخرج نص من المحدد');
    disc.extracted_text = ocr.text;
    st.textContent = `استُخرج النص بـ«${ocr.reader.name}» — يُرسل الآن إلى المساعد «${asst.name}»...`;
    const cite = rdCite();
    const userMsg = `نص محدد من ${cite}:\n\n${ocr.text}`;
    disc.messages.push({ role: 'user', content: userMsg, at: new Date().toISOString() });
    rdRenderAnalysisMsgs();
    await rdAnalysisAsk(disc, asst, true);
    const lastA = [...(disc.messages || [])].reverse().find(m => m.role === 'assistant');
    const wCount = lastA && Array.isArray(lastA.witnesses) ? lastA.witnesses.length : 0;
    st.textContent = mode === 'fast'
      ? `مناقشة رقم ${discId} · ${asst.name} · تحليل سريع من ذاكرة النموذج`
      : `مناقشة رقم ${discId} · ${asst.name} · تحليل محرر من نطاق الكتب (${wCount} شاهدًا) — 📖 تفتح الكتاب`;
  } catch (e) {
    st.textContent = `❌ ${e.message}`;
    rdToast(`❌ ${e.message}`, 5000);
  }
  rdSaveSoon();
}

function rdOpenDiscussion(id, fresh) {
  if (!rdCurrent) return;
  const disc = (rdCurrent.discussions || {})[id];
  if (!disc) { rdToast('المناقشة غير موجودة'); return; }
  rdHideSelBar();
  rdAnalysis = { id, discussion: disc };
  document.getElementById('rdAnalysisTitle').textContent = `🧠 تحليل النص — ${disc.assistant_name || 'مساعد'}`;
  const modeLabel = disc.mode === 'fast' ? 'سريع · من الذاكرة' : 'محرر · من نطاق الكتب';
  document.getElementById('rdAnalysisMeta').textContent = `رقم المناقشة: ${id} · ${modeLabel}`;
  document.getElementById('rdAnalysisStatus').textContent = fresh
    ? 'جار تحليل النص...'
    : `مناقشة محفوظة · صفحة ${disc.page}`;
  document.getElementById('rdAnalysisInput').value = '';
  rdShowModal('rdAnalysisModal');
  rdRenderAnalysisMsgs();
}

function rdRenderAnalysisMsgs() {
  const box = document.getElementById('rdAnalysisMsgs');
  if (!box || !rdAnalysis) return;
  const msgs = rdAnalysis.discussion.messages || [];
  if (!msgs.length) { box.innerHTML = '<div class="ms-hint">لا رسائل بعد.</div>'; return; }
  box.innerHTML = msgs.map((m, i) => `
    <div class="message-bubble ${m.role === 'user' ? 'user' : 'assistant'}" id="rdMsg${i}">
      <div class="message-avatar">${m.role === 'user' ? 'أنت' : 'مج'}</div>
      <div class="message-content">${m.role === 'assistant' ? rdMd(m.content) : rdEsc(m.content).replace(/\n/g, '<br>')}
      ${(m.role === 'assistant' && Array.isArray(m.tree_set) && m.tree_set.length && typeof smartTreesHtml === 'function') ? smartTreesHtml(m, i) : ''}</div>
    </div>`).join('');
  // أيقونات الإحالة النموذجية 📖 تفتح تصفح الكتاب الأصلي عند موضع الشاهد
  if (typeof window.enhanceProjectCitationsWithBookReader === 'function') {
    try { window.enhanceProjectCitationsWithBookReader(box); } catch (e) { /* */ }
  }
  if (typeof mountSmartTreeCards === 'function') {
    try { mountSmartTreeCards(box, { messages: msgs }); } catch (e) { /* */ }
  }
  if (typeof autoRenderChatInteractiveWidgets === 'function') {
    try { autoRenderChatInteractiveWidgets(box); } catch (e) { /* */ }
  }
  box.scrollTop = box.scrollHeight;
}

async function rdAnalysisAsk(disc, asst, isFirst) {
  const sendBtn = document.getElementById('rdAnalysisSend');
  const stopBtn = document.getElementById('rdAnalysisStop');
  sendBtn.disabled = true; stopBtn.hidden = false;
  rdAnalysisAbort = new AbortController();
  try {
    // التوجيهان يُرسلان في رسالة النظام فقط، فلا يُكتبان في رسائل النافذة.
    const fast = disc.mode === 'fast';
    const books = (asst.books || []).map(b => b.title).filter(Boolean);
    const basePrompt = asst.prompt || RD_DEFAULT_ASST_PROMPT;
    const prompt = `${basePrompt}\n\n${fast ? RD_FAST_DIRECTIVE : RD_EDITED_DIRECTIVE}`;
    const visible = (disc.messages || []).map(m => ({ role: m.role, content: m.content }));
    const agentObj = {
      id: asst.id || 'rd-asst', name: asst.name, desc: '',
      system_prompt: prompt, systemPrompt: prompt,
      model: asst.model, thinking: 'medium',
      books, booksScope: books,
      pool_size: 800, top_k: 60, temp: 0.2,
    };
    const body = fast ? {
      chat_id: null,
      model: asst.model,
      provider: 'openrouter',
      api_key: rdApiKey(),
      thinking_level: 'medium',
      free_mode: true,
      use_hybrid: false,
      semantic_enhanced: false,
      system_prompt: prompt,
      messages: visible,
      web_search: null,
      agent_group: null,
    } : {
      chat_id: null,
      model: asst.model,
      provider: 'openrouter',
      api_key: rdApiKey(),
      thinking_level: 'medium',
      use_hybrid: true,
      semantic_enhanced: true,
      system_prompt: prompt,
      messages: visible,
      selected_books: books.length ? books : null,
      witness_limit: 50,
      agent_group: {
        id: asst.id || 'rd-asst', name: asst.name, desc: '',
        active_agent: { ...agentObj },
        agents: [agentObj],
        disabled_agents: [],
      },
    };
    const res = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      signal: rdAnalysisAbort.signal,
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.reply || 'تعذر التحليل');
    const reply = data.reply || data.content || data.message || '';
    disc.messages.push({
      role: 'assistant', content: reply,
      witnesses: Array.isArray(data.witnesses) ? data.witnesses : [],
      at: new Date().toISOString(),
    });
    disc.updated_at = new Date().toISOString();
    rdRenderAnalysisMsgs();
    rdSaveSoon();
  } catch (e) {
    if (e.name === 'AbortError') rdToast('أُوقف التحليل');
    else throw e;
  } finally {
    sendBtn.disabled = false; stopBtn.hidden = true; rdAnalysisAbort = null;
  }
}

async function rdAnalysisSend() {
  if (!rdAnalysis) return;
  const input = document.getElementById('rdAnalysisInput');
  const text = input.value.trim();
  if (!text) return;
  const disc = rdAnalysis.discussion;
  const asst = rdAssistants.find(a => a.id === disc.assistant_id) || {
    name: disc.assistant_name, model: disc.model, prompt: RD_DEFAULT_ASST_PROMPT, books: [],
  };
  disc.messages.push({ role: 'user', content: text, at: new Date().toISOString() });
  input.value = '';
  rdRenderAnalysisMsgs();
  document.getElementById('rdAnalysisStatus').textContent = 'جارٍ الرد...';
  try {
    await rdAnalysisAsk(disc, asst, false);
    document.getElementById('rdAnalysisStatus').textContent = `مناقشة رقم ${disc.id}`;
  } catch (e) {
    document.getElementById('rdAnalysisStatus').textContent = `❌ ${e.message}`;
    rdToast(`❌ ${e.message}`, 5000);
  }
}
function rdAnalysisStop() {
  if (rdAnalysisAbort) rdAnalysisAbort.abort();
}
function rdCloseAnalysis() {
  rdAnalysisStop();
  rdCloseModal('rdAnalysisModal');
  rdAnalysis = null;
  rdRenderAnnotations();
  rdSaveSoon();
}

async function rdSelRead() {
  if (!rdNeedActiveSel()) return;
  rdHideSelBar(); rdSelFromHover = false;
  if (!rdDefaultReader()) return;
  rdShowModal('rdReadTextModal');
  document.getElementById('rdReadTextStatus').textContent = 'جارٍ استخراج النص بالقارئ...';
  document.getElementById('rdReadTextBody').textContent = '';
  try {
    const ocr = await rdOcrSelection();
    document.getElementById('rdReadTextStatus').textContent = `✔ قُرئ بـ«${ocr.reader.name}» — ${rdCite()}`;
    document.getElementById('rdReadTextBody').textContent = ocr.text || '(لا نص)';
  } catch (e) {
    document.getElementById('rdReadTextStatus').textContent = `❌ ${e.message}`;
  }
}
function rdCopyReadText() {
  const t = document.getElementById('rdReadTextBody').textContent || '';
  if (!t) return;
  navigator.clipboard.writeText(t).then(() => rdToast('نُسخ النص')).catch(() => rdToast('تعذر النسخ'));
}

function rdSelShare() {
  if (!rdNeedActiveSel()) return;
  rdHideSelBar(); rdSelFromHover = false;
  rdMediaAction = 'share';
  document.getElementById('rdMediaChoiceTitle').textContent = 'مشاركة المحدد — نص أم صورة؟';
  rdShowModal('rdMediaChoiceModal');
}
function rdSelPublish() {
  if (!rdNeedActiveSel()) return;
  rdHideSelBar(); rdSelFromHover = false;
  rdMediaAction = 'publish';
  document.getElementById('rdMediaChoiceTitle').textContent = 'نشر المحدد — نص أم صورة؟';
  rdShowModal('rdMediaChoiceModal');
}

// رفع نافذة النشر فوق نافذة القراءة وكل النوافذ، بلا فرض display حتى ينجح الإغلاق
function rdRaisePublishOverlay() {
  const ov = document.getElementById('designPublishOverlay');
  if (!ov) return;
  if (ov.parentElement !== document.body) document.body.appendChild(ov);
  ov.style.removeProperty('display');
  ov.style.setProperty('z-index', '350000', 'important');
}
function rdShowShareModal(text, file) {
  window._rdSharePayload = { text: text || '', file: file || null, title: (rdCurrent && rdCurrent.title) || 'قراءة' };
  const modal = document.getElementById('shareModal');
  if (!modal || typeof openSharePicker !== 'function') {
    if (file) rdNativeShareImage(file, text); else rdNativeShareText(text);
    return;
  }
  if (modal.parentElement !== document.body) document.body.appendChild(modal);
  openSharePicker('chat', 'reading-selection', window._rdSharePayload.title);
  modal.style.setProperty('z-index', '400000', 'important');
  const ext = document.getElementById('shareExternalOption');
  if (ext) ext.hidden = false;
  const extRadio = document.querySelector('input[name="shareDestination"][value="external"]');
  if (extRadio) extRadio.checked = true;
  if (typeof toggleShareDestination === 'function') toggleShareDestination();
}
async function rdMediaChoice(kind) {
  rdCloseModal('rdMediaChoiceModal');
  const action = rdMediaAction;
  rdMediaAction = null;
  if (!action) return;
  try {
    if (kind === 'text') {
      rdToast('جارٍ استخراج النص للمشاركة...');
      const ocr = await rdOcrSelection();
      const payload = `${ocr.text}\n\n—\n${rdCite()}`;
      if (action === 'share') { rdShowShareModal(payload, null); return; }
      else if (typeof window.openDesignTextPublish === 'function') { rdRaisePublishOverlay(); window.openDesignTextPublish(payload, null); }
      else rdToast('نافذة النشر غير متاحة');
    } else {
      const blob = await rdCropSelBlob();
      if (!blob) throw new Error('تعذر قص الصورة');
      const up = await rdUploadBlob(blob, 'rd-share.png');
      const caption = rdCite();
      if (action === 'share') { rdShowShareModal(caption, new File([blob], 'قراءة.png', { type: 'image/png' })); return; }
      else if (typeof window.openDesignImagePublish === 'function') {
        rdRaisePublishOverlay();
        window.openDesignImagePublish(up.file_url, caption, null);
      } else rdToast('نافذة النشر غير متاحة');
    }
  } catch (e) { rdToast(`❌ ${e.message}`, 5000); }
}

async function rdNativeShareText(text) {
  if (typeof navigator.share === 'function') {
    try {
      await navigator.share({ title: rdCurrent?.title || 'قراءة', text });
      return;
    } catch (e) { if (e && e.name === 'AbortError') return; }
  }
  try {
    await navigator.clipboard.writeText(text);
    rdToast('نُسخ النص إلى الحافظة (المشاركة الأصلية غير متاحة)');
  } catch (e) { rdToast('تعذرت المشاركة'); }
}
async function rdNativeShareImage(blob, caption) {
  const file = new File([blob], 'قراءة.png', { type: 'image/png' });
  const payload = { files: [file], title: caption || 'قراءة', text: caption || '' };
  if (typeof navigator.share === 'function' && (!navigator.canShare || navigator.canShare(payload))) {
    try { await navigator.share(payload); return; }
    catch (e) { if (e && e.name === 'AbortError') return; }
  }
  // بديل: تنزيل الصورة
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'قراءة.png';
  a.click();
  rdToast('حُمّلت الصورة (المشاركة الأصلية غير متاحة لهذا النوع)');
}

document.addEventListener('click', (e) => {
  const w = document.getElementById('rdAsstModelWrapper');
  if (w && w.classList.contains('open') && !w.contains(e.target)) w.classList.remove('open');
});

// =============================================================================
// الأدوات المساعدة في نافذة التحليل: تشجير وجدولة على الإجابة (كما في المحادثات)
// =============================================================================
let rdToolKind = null; // 'tree' | 'tables'
let rdToolProposals = [];
let rdToolMaterial = '';
let rdToolToken = 0;

function rdToolSourceText() {
  if (!rdAnalysis) return '';
  const msgs = (rdAnalysis.discussion.messages || []).filter(m => m && m.role === 'assistant' && String(m.content || '').length > 40
    && !Array.isArray(m.tree_set));
  if (!msgs.length) return '';
  const src = msgs[msgs.length - 1];
  let text = String(src.content || '');
  if (typeof stripGraphFences === 'function') text = stripGraphFences(text);
  if (typeof stripChartFences === 'function') text = stripChartFences(text);
  return text.slice(0, 24000);
}
function rdToolBusy(title, hint) {
  const body = document.getElementById('rdToolBody');
  const foot = document.getElementById('rdToolFoot');
  document.getElementById('rdToolTitle').textContent = title;
  if (body) body.innerHTML = `<div class="smart-tree-wait"><span class="smart-tree-spinner"></span><div><b>جارٍ فحص إجابة التحليل…</b><small>${rdEsc(hint)}</small></div></div>`;
  if (foot) foot.innerHTML = '<button type="button" class="btn-msg-export" onclick="rdCloseToolModal()">إلغاء</button>';
}
function rdCloseToolModal() { rdToolToken += 1; rdCloseModal('rdToolModal'); }

async function rdStartTreeScan(deep) {
  const text = rdToolSourceText();
  if (!text) { rdToast('لا توجد إجابة تحليل سابقة لتشجيرها'); return; }
  rdToolKind = 'tree';
  rdToolMaterial = text;
  const token = ++rdToolToken;
  rdToolBusy('🌳 تشجير ووسائط من إجابة التحليل', 'النموذج يمسح الإجابة ويستخرج تقسيماتها وخلافاتها القابلة للتشجير، فضلًا انتظر قليلًا.');
  rdShowModal('rdToolModal');
  try {
    const res = await fetch('/api/chat/tree-analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, api_key: rdApiKey(), deep: !!deep }),
    });
    const data = await res.json().catch(() => ({}));
    if (token !== rdToolToken) return;
    if (!res.ok) throw new Error(data.detail || 'تعذر تحليل المحتوى');
    rdRenderToolProposals('tree', Array.isArray(data.proposals) ? data.proposals : [], !!deep);
  } catch (e) {
    if (token !== rdToolToken) return;
    rdRenderToolError(e.message);
  }
}

async function rdStartTableScan() {
  const text = rdToolSourceText();
  if (!text) { rdToast('لا توجد إجابة تحليل سابقة لجدولتها'); return; }
  rdToolKind = 'tables';
  rdToolMaterial = text;
  const token = ++rdToolToken;
  rdToolBusy('📋 جدولة — مسح ذكي للبنية القابلة للجدولة', 'النموذج يستخرج مقارنات الإجابة وقوائمها ذات الخصائص المتكررة ويقترح جداولها، فضلًا انتظر قليلًا.');
  rdShowModal('rdToolModal');
  try {
    const res = await fetch('/api/chat/data-analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, api_key: rdApiKey(), mode: 'tables' }),
    });
    const data = await res.json().catch(() => ({}));
    if (token !== rdToolToken) return;
    if (!res.ok) throw new Error(data.detail || 'تعذر مسح المحتوى');
    rdRenderToolProposals('tables', Array.isArray(data.proposals) ? data.proposals : [], false);
  } catch (e) {
    if (token !== rdToolToken) return;
    rdRenderToolError(e.message);
  }
}

function rdRenderToolError(msg) {
  const body = document.getElementById('rdToolBody');
  const foot = document.getElementById('rdToolFoot');
  if (body) body.innerHTML = `<div class="pres-opt-hint">تعذر الفحص: ${rdEsc(msg || 'خطأ غير معروف')}</div>`;
  if (foot) foot.innerHTML = `<button type="button" class="btn-msg-export" onclick="rdCloseToolModal()">إغلاق</button>`
    + (rdToolKind === 'tree'
      ? '<button type="button" class="btn-msg-export pres-start-btn" onclick="rdStartTreeScan(false)">🔁 إعادة المحاولة</button>'
      : '<button type="button" class="btn-msg-export pres-start-btn" onclick="rdStartTableScan()">🔁 إعادة المحاولة</button>');
}

function rdRenderToolProposals(kind, proposals, deep) {
  rdToolProposals = proposals;
  const body = document.getElementById('rdToolBody');
  const foot = document.getElementById('rdToolFoot');
  if (!body || !foot) return;
  if (!proposals.length) {
    body.innerHTML = `<div class="pres-opt-hint">${kind === 'tree'
      ? (deep ? 'حتى بعد الفحص الأعمق لم تظهر في إجابة التحليل بنية قابلة للتشجير بثقة. جرّب تشجير إجابة أغنى بالتقسيمات والأقوال.' : 'لم تظهر في الفحص الأول مقترحات كافية. جرّب «الفحص الأعمق» لاستخراج التقسيمات الضمنية من بنية الإجابة.')
      : 'لم يجد المسح في إجابة التحليل بنية قابلة للجدولة بثقة (لا مقارنات ببنود متقابلة ولا قوائم ذات خصائص متكررة).'}</div>`;
    foot.innerHTML = '<button type="button" class="btn-msg-export" onclick="rdCloseToolModal()">إغلاق</button>'
      + (kind === 'tree' && !deep ? '<button type="button" class="btn-msg-export pres-start-btn" onclick="rdStartTreeScan(true)">🔍 فحص أعمق</button>' : '');
    return;
  }
  body.innerHTML = `<div class="pres-opt-label">${kind === 'tree' ? 'وجد النموذج في الإجابة ما يمكن تشجيره — حدّد مسألة أو أكثر' : 'وجد النموذج في الإجابة بنى قابلة للجدولة — حدّد جدولًا أو أكثر'}</div>
    <div class="smart-tree-select-row">
      <button type="button" class="btn-msg-export" id="rdToolSelectAllBtn" onclick="rdToolToggleAll()">☑ تحديد الكل</button>
      <span class="smart-tree-sel-count" id="rdToolSelCount"></span>
    </div>` + proposals.map((p, i) => `
    <label class="pres-radio-card"><input type="checkbox" name="rdToolProposal" value="${i}"${i === 0 ? ' checked' : ''} onchange="rdToolUpdateSel()"> <span><b>${rdEsc(p.kind_label || '')}: ${rdEsc(p.title || '')}</b><small>${rdEsc(p.columns ? `الأعمدة: ${p.columns} — ` : '')}${rdEsc(p.desc || '')}</small></span></label>`).join('');
  foot.innerHTML = '<button type="button" class="btn-msg-export" onclick="rdCloseToolModal()">إلغاء</button>'
    + (kind === 'tree'
      ? '<button type="button" class="btn-msg-export pres-start-btn" onclick="rdConfirmTool()">🌳 تشجير نصي</button>'
      : '<button type="button" class="btn-msg-export pres-start-btn" onclick="rdConfirmTool()">📋 إنشاء الجداول المحددة</button>');
  rdToolUpdateSel();
}
function rdToolToggleAll() {
  const boxes = [...document.querySelectorAll('input[name="rdToolProposal"]')];
  const all = boxes.length && boxes.every(b => b.checked);
  boxes.forEach(b => { b.checked = !all; });
  rdToolUpdateSel();
}
function rdToolUpdateSel() {
  const boxes = [...document.querySelectorAll('input[name="rdToolProposal"]')];
  const checked = boxes.filter(b => b.checked).length;
  const btn = document.getElementById('rdToolSelectAllBtn');
  if (btn) btn.textContent = (boxes.length && checked === boxes.length) ? '☐ إلغاء تحديد الكل' : '☑ تحديد الكل';
  const count = document.getElementById('rdToolSelCount');
  if (count) count.textContent = boxes.length ? `المحدّد: ${checked} من ${boxes.length}` : '';
}
function rdToolSelected() {
  return [...document.querySelectorAll('input[name="rdToolProposal"]:checked')]
    .map(el => rdToolProposals[parseInt(el.value, 10)]).filter(Boolean);
}

async function rdConfirmTool() {
  const selected = rdToolSelected();
  if (!selected.length) { rdToast(rdToolKind === 'tree' ? 'حدّد مسألة واحدة على الأقل للتشجير' : 'حدّد جدولًا واحدًا على الأقل'); return; }
  if (!rdAnalysis) return;
  const kind = rdToolKind;
  const disc = rdAnalysis.discussion;
  const model = disc.model || 'anthropic/claude-3.7-sonnet';
  rdCloseToolModal();
  const st = document.getElementById('rdAnalysisStatus');
  const keys = (typeof readProviderKeys === 'function') ? readProviderKeys() : {};
  const failures = [];
  try {
    if (kind === 'tree') {
      const trees = [];
      let done = 0;
      for (let s = 0; s < selected.length; s += 3) {
        const batch = selected.slice(s, s + 3);
        const settled = await Promise.allSettled(batch.map(p => rdFetchOneTree(p, model, keys)));
        settled.forEach((r, i) => {
          done += 1;
          if (r.status === 'fulfilled') trees.push(r.value);
          else failures.push(`${batch[i].title}: ${r.reason?.message || 'تعذر'}`);
        });
        if (st) st.textContent = `جارٍ تشجير المسائل: ${done} من ${selected.length}...`;
      }
      if (!trees.length) throw new Error(failures[0] || 'تعذر التشجير');
      disc.messages.push({
        role: 'assistant',
        content: `🌳 مشجّرات مولّدة من إجابة التحليل (${trees.length}):\n` + trees.map(t => `• ${t.kind_label}: ${t.title}`).join('\n'),
        tree_set: trees,
        at: new Date().toISOString(),
      });
      if (st) st.textContent = `اكتمل تشجير ${trees.length} مسألة في المناقشة ${disc.id}`;
    } else {
      const parts = [];
      let done = 0;
      for (let s = 0; s < selected.length; s += 3) {
        const batch = selected.slice(s, s + 3);
        const settled = await Promise.allSettled(batch.map(p => rdFetchOneTable(p, model, keys)));
        settled.forEach((r, i) => {
          done += 1;
          if (r.status === 'fulfilled') parts.push(r.value);
          else failures.push(`${batch[i].title}: ${r.reason?.message || 'تعذر'}`);
        });
        if (st) st.textContent = `جارٍ إنشاء الجداول: ${done} من ${selected.length}...`;
      }
      if (!parts.length) throw new Error(failures[0] || 'تعذر إنشاء الجداول');
      disc.messages.push({
        role: 'assistant',
        content: parts.join('\n\n'),
        table_request: true,
        at: new Date().toISOString(),
      });
      if (st) st.textContent = `اكتمل إنشاء ${parts.length} جدول في المناقشة ${disc.id}`;
    }
    disc.updated_at = new Date().toISOString();
    rdRenderAnalysisMsgs();
    rdSaveSoon();
    if (failures.length) rdToast(`اكتمل بعضها وتعذر ${failures.length}: ${failures[0]}`, 6000);
  } catch (e) {
    if (st) st.textContent = `❌ ${e.message}`;
    rdToast(`❌ ${e.message}`, 5000);
  }
}

async function rdFetchOneTree(p, model, keys) {
  const instruction = (typeof smartTreeInstruction === 'function')
    ? smartTreeInstruction(p)
    : `شجّر من الإجابة شجرة واحدة موضوعها «${p.title}» بصيغة force3d JSON فقط، بلا شرح قبلها ولا بعدها.`;
  const res = await fetch('/api/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model, provider: 'openrouter',
      api_key: keys.openrouter || rdApiKey(),
      use_hybrid: false, graph_only: true,
      messages: [{ role: 'user', content: `النتيجة المراد تشجيرها:\n${rdToolMaterial}` }],
      system_prompt: instruction,
      temperature: 0.2, providers: keys, agent_group: null,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'تعذر التشجير');
  const treeData = (typeof extractForce3dData === 'function') ? extractForce3dData(data.reply) : null;
  if (!treeData) throw new Error('لم يُعد النموذج شجرة صالحة');
  return { title: p.title, kind: p.kind, kind_label: p.kind_label || 'تشجير', data: treeData };
}

async function rdFetchOneTable(p, model, keys) {
  const instruction = (typeof tableProposalInstruction === 'function')
    ? tableProposalInstruction(p)
    : `جدول الإجابة فقط بعنوان «${p.title}» وأعمدة: ${p.columns || 'مناسبة'}، جدول ماركداون واحد بلا شرح.`;
  const res = await fetch('/api/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model, provider: 'openrouter',
      api_key: keys.openrouter || rdApiKey(),
      use_hybrid: false, table_only: true,
      messages: [{ role: 'user', content: `النتيجة المراد جدولتها:\n${rdToolMaterial}` }],
      system_prompt: instruction,
      temperature: 0.2, providers: keys, agent_group: null,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'تعذر إنشاء الجدول');
  const reply = String(data.reply || '');
  if (!reply.includes('|')) throw new Error('لم يُعد النموذج جدولًا صالحًا');
  return `### ${p.title}\n\n${reply.trim()}`;
}
