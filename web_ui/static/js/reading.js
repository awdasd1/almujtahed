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
let rdAsstDraftBooks = [];
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
  document.getElementById('rdReaderTitle').textContent = `📖 ${p.title}`;
  rdShowModal('rdReaderModal');
  rdBuildColorBars();
  rdSetTool('pen');
  rdUpdateBookUI();
  rdApplyView();
  rdInitResize();
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
      + `<button type="button" class="rd-color-add" title="لون فارغ — اضغطه لإضافة لون جديد من منتقي الألوان" onclick="rdAddColor('${target}')">+</button>`;
  };
  mk('rdColors', RD_COLORS.concat(rdCustomColors.pen || []), rdColor, 'rdSetColor', 'pen');
  mk('rdNoteColors', RD_NOTE_COLORS.concat(rdCustomColors.note || []), rdNoteColor, 'rdSetNoteColor', 'note');
}
// اللون الفارغ: يفتح منتقي ألوان النظام فيُضاف اللون المختار إلى اللوحة ويُحفظ
function rdAddColor(target) {
  rdColorTarget = target;
  const picker = document.getElementById('rdColorPicker');
  if (!picker) return;
  picker.value = target === 'note' ? rdNoteColor : rdColor;
  picker.click();
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
    `<span class="rd-note" style="right:${n.x * 100}%;top:${n.y * 100}%;background:${n.c}" title="${rdEsc(n.text || 'ملحوظة')}" onclick="rdEditNote(${i}, event)">📌</span>`).join('');
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
  document.querySelectorAll('.rd-note-editor').forEach(x => x.remove());
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

// تطويل النافذة من الأسفل فقط: مقبض سحب يغيّر ارتفاع نافذة القارئ رأسيًا
let rdResizeInit = false;
function rdInitResize() {
  if (rdResizeInit) return;
  const handle = document.getElementById('rdResizeHandle');
  const modal = document.querySelector('.rd-reader-modal');
  const scroll = document.getElementById('rdPageScroll');
  if (!handle || !modal || !scroll) return;
  rdResizeInit = true;
  handle.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    const startY = e.clientY;
    const startH = modal.offsetHeight;
    modal.style.maxHeight = 'none';
    const move = (ev) => {
      const h = Math.max(430, Math.min(window.innerHeight - 16, startH + (ev.clientY - startY)));
      modal.style.height = `${h}px`;
      scroll.style.maxHeight = `${Math.max(240, h - 250)}px`;
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
function rdHitDiscussion(qx, qy) {
  if (!rdCurrent) return null;
  const ann = rdPageAnn();
  const hit = (arr, kind) => {
    for (let i = (arr || []).length - 1; i >= 0; i--) {
      const r = arr[i];
      if (!r.discussion_id) continue;
      if (qx >= r.x && qx <= r.x + r.w && qy >= r.y && qy <= r.y + r.h) {
        return { id: r.discussion_id, kind, index: i };
      }
    }
    return null;
  };
  return hit(ann.crops, 'c') || hit(ann.highlights, 'h');
}

// أحداث الرسم على اللوحة
(function rdInitCanvasEvents() {
  const ready = () => {
    const cv = document.getElementById('rdCanvas');
    if (!cv) { setTimeout(ready, 600); return; }
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
  document.querySelectorAll('.rd-note-editor').forEach(x => x.remove());
  const layer = document.getElementById('rdNotesLayer');
  const ed = document.createElement('div');
  ed.className = 'rd-note-editor';
  ed.style.background = n.c;
  ed.style.right = `${Math.min(78, n.x * 100)}%`;
  ed.style.top = `${n.y * 100}%`;
  ed.innerHTML = `<textarea placeholder="اكتب ملحوظتك هنا...">${rdEsc(n.text || '')}</textarea>
    <div class="rd-note-btns">
      <button type="button" data-act="save">حفظ الملحوظة</button>
      <button type="button" data-act="del">حذف الملصق</button>
      <button type="button" data-act="x">إغلاق</button>
    </div>`;
  layer.appendChild(ed);
  const ta = ed.querySelector('textarea');
  ta.focus();
  ed.querySelector('[data-act="save"]').onclick = () => { n.text = ta.value; ed.remove(); rdRenderNotes(); rdSaveSoon(); };
  ed.querySelector('[data-act="del"]').onclick = () => { ann.notes.splice(i, 1); ed.remove(); rdRenderNotes(); rdSaveSoon(); };
  ed.querySelector('[data-act="x"]').onclick = () => ed.remove();
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

async function rdFillModels(selectId, visionOnly) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  sel.innerHTML = '<option value="">جارٍ تحميل النماذج...</option>';
  try {
    const url = visionOnly ? '/api/manuscripts/models' : '/api/openrouter/models';
    const res = await fetch(url);
    const data = await res.json();
    let models = data.models || data.data || [];
    if (visionOnly) models = models.filter(m => m.vision);
    else if (models.length && models[0].input_modalities) {
      /* قائمة openrouter كاملة */
    }
    if (!models.length) { sel.innerHTML = '<option value="">لا نماذج متاحة</option>'; return; }
    sel.innerHTML = models.map(m => {
      const id = m.id || m.model_id || m.name;
      const name = m.name || id;
      return `<option value="${rdEsc(id)}">${rdEsc(name)}</option>`;
    }).join('');
  } catch (e) {
    sel.innerHTML = `<option value="">تعذر التحميل: ${rdEsc(e.message)}</option>`;
  }
}

function rdRenderAssistantsList() {
  const box = document.getElementById('rdAssistantsList');
  if (!box) return;
  if (!rdAssistants.length) { box.innerHTML = '<div class="ms-hint">لا مساعدين بعد.</div>'; return; }
  box.innerHTML = rdAssistants.map(a => `
    <div class="rd-entity-card">
      <div><strong>🧠 ${rdEsc(a.name)}</strong><div class="ms-hint">${rdEsc(a.model)} · ${(a.books || []).length} كتاب</div></div>
      <button type="button" class="ms-btn ms-btn-danger" onclick="rdDeleteAssistant('${a.id}')">حذف</button>
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

function rdOpenCreateAssistant() {
  rdAsstDraftBooks = [];
  document.getElementById('rdAsstName').value = '';
  document.getElementById('rdAsstPrompt').value = RD_DEFAULT_ASST_PROMPT;
  document.getElementById('rdAsstBookQ').value = '';
  document.getElementById('rdAsstBookResults').innerHTML = '';
  document.getElementById('rdAsstBooksChosen').textContent = 'لا شيء بعد';
  rdShowModal('rdAssistantModal');
  rdFillModels('rdAsstModel', false);
  rdRenderAssistantsList();
}
function rdOpenCreateReader() {
  document.getElementById('rdVisName').value = '';
  rdShowModal('rdVisionReaderModal');
  rdFillModels('rdVisModel', true);
  rdRenderReadersList();
}

async function rdSearchAsstBooks() {
  const q = document.getElementById('rdAsstBookQ').value.trim();
  const box = document.getElementById('rdAsstBookResults');
  if (!q) { rdToast('اكتب اسم الكتاب أولًا'); return; }
  box.innerHTML = '<div class="ms-rec-loading">⏳ جارٍ البحث...</div>';
  try {
    const res = await fetch(`/api/books/search?q=${encodeURIComponent(q)}&limit=40`);
    const data = await res.json();
    const books = data.books || [];
    box.innerHTML = books.length ? books.map(b => {
      const checked = rdAsstDraftBooks.some(x => String(x.book_id) === String(b.book_id)) ? 'checked' : '';
      return `<label><input type="checkbox" ${checked} onchange="rdToggleAsstBook(${b.book_id}, '${rdEsc(b.title).replace(/'/g, '')}', this.checked)">
        <span><strong>${rdEsc(b.title)}</strong> <span class="ms-wb-meta">${rdEsc(b.author || '')}</span></span></label>`;
    }).join('') : '<div class="ms-hint">لا نتائج.</div>';
  } catch (e) { box.innerHTML = `<div class="ms-hint">❌ ${rdEsc(e.message)}</div>`; }
}
function rdToggleAsstBook(bookId, title, on) {
  if (on) {
    if (!rdAsstDraftBooks.some(x => String(x.book_id) === String(bookId)))
      rdAsstDraftBooks.push({ book_id: bookId, title });
  } else {
    rdAsstDraftBooks = rdAsstDraftBooks.filter(x => String(x.book_id) !== String(bookId));
  }
  document.getElementById('rdAsstBooksChosen').textContent =
    rdAsstDraftBooks.length ? rdAsstDraftBooks.map(b => b.title).join(' · ') : 'لا شيء بعد';
}

function rdAdoptAssistant() {
  const name = document.getElementById('rdAsstName').value.trim();
  const model = document.getElementById('rdAsstModel').value;
  const prompt = document.getElementById('rdAsstPrompt').value.trim() || RD_DEFAULT_ASST_PROMPT;
  if (!name) { rdToast('اكتب اسم المساعد'); return; }
  if (!model) { rdToast('اختر نموذجًا'); return; }
  rdAssistants.unshift({
    id: rdUid(), name, model, prompt,
    books: rdAsstDraftBooks.map(b => ({ ...b })),
    created_at: new Date().toISOString(),
  });
  rdSave();
  rdRenderAssistantsList();
  rdToast(`✔ اعتُمد المساعد «${name}»`);
  document.getElementById('rdAsstName').value = '';
  rdAsstDraftBooks = [];
  document.getElementById('rdAsstBooksChosen').textContent = 'لا شيء بعد';
}
function rdDeleteAssistant(id) {
  if (!confirm('حذف هذا المساعد؟')) return;
  rdAssistants = rdAssistants.filter(a => a.id !== id);
  rdSave(); rdRenderAssistantsList();
}
function rdAdoptVisionReader() {
  const name = document.getElementById('rdVisName').value.trim();
  const model = document.getElementById('rdVisModel').value;
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
  if (!rdAssistants.length) { rdToast('أنشئ مساعدًا أولًا بزر «إنشاء مساعد»'); return; }
  if (!rdDefaultReader()) return;
  const box = document.getElementById('rdPickAsstList');
  box.innerHTML = rdAssistants.map(a => `
    <div class="rd-entity-card">
      <div><strong>🧠 ${rdEsc(a.name)}</strong><div class="ms-hint">${rdEsc(a.model)} · ${(a.books || []).length} كتاب</div></div>
      <button type="button" class="ms-btn ms-btn-primary" onclick="rdStartAnalysis('${a.id}')">تحليل بهذا المساعد</button>
    </div>`).join('');
  document.getElementById('rdPickAsstHint').textContent = 'بعد الاختيار يُستخرج النص بالقارئ ثم يُرسل تلقائيًا للمساعد دون تدخل منك.';
  rdShowModal('rdPickAsstModal');
}

async function rdStartAnalysis(asstId) {
  const asst = rdAssistants.find(a => a.id === asstId);
  if (!asst || !rdCurrent || !rdActiveSel) return;
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
    const userMsg = `نص محدد من ${cite}:\n\n${ocr.text}\n\nحلّل هذا النص وصنّفه وفق توجيهك.`;
    disc.messages.push({ role: 'user', content: userMsg, at: new Date().toISOString() });
    rdRenderAnalysisMsgs();
    await rdAnalysisAsk(disc, asst, true);
    st.textContent = `مناقشة رقم ${discId} · المساعد «${asst.name}»`;
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
  rdAnalysis = { id, discussion: disc };
  document.getElementById('rdAnalysisTitle').textContent = `🧠 تحليل النص — ${disc.assistant_name || 'مساعد'}`;
  document.getElementById('rdAnalysisMeta').textContent = `رقم المناقشة: ${id}`;
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
  box.innerHTML = msgs.map(m => `
    <div class="rd-amsg ${m.role === 'user' ? 'user' : 'assistant'}">
      <div class="rd-amsg-role">${m.role === 'user' ? 'أنت' : 'المساعد'}</div>
      <div>${m.role === 'assistant' ? rdMd(m.content) : rdEsc(m.content).replace(/\n/g, '<br>')}</div>
    </div>`).join('');
  box.scrollTop = box.scrollHeight;
}

async function rdAnalysisAsk(disc, asst, isFirst) {
  const sendBtn = document.getElementById('rdAnalysisSend');
  const stopBtn = document.getElementById('rdAnalysisStop');
  sendBtn.disabled = true; stopBtn.hidden = false;
  rdAnalysisAbort = new AbortController();
  try {
    const books = (asst.books || []).map(b => b.title).filter(Boolean);
    const agent = {
      name: asst.name,
      model: asst.model,
      system_prompt: asst.prompt || RD_DEFAULT_ASST_PROMPT,
      books,
      booksScope: books,
      enabled: true,
      pool_size: 800,
      top_k: 60,
    };
    const body = {
      model: asst.model,
      provider: 'openrouter',
      api_key: rdApiKey(),
      system_prompt: asst.prompt || RD_DEFAULT_ASST_PROMPT,
      messages: (disc.messages || []).map(m => ({ role: m.role, content: m.content })),
      free_mode: books.length === 0,
      agent_group: books.length ? { agents: [agent], active_agent: agent } : null,
    };
    // في الوضع الحر لا يُمرَّر system_prompt؛ نضمّنه في أول رسالة مستخدم إن لزم
    if (body.free_mode && isFirst && disc.messages.length) {
      const first = disc.messages[0];
      body.messages = [
        { role: 'user', content: `[توجيه المساعد]\n${asst.prompt || RD_DEFAULT_ASST_PROMPT}\n\n[النص المطلوب تحليله]\n${first.content}` },
        ...disc.messages.slice(1).map(m => ({ role: m.role, content: m.content })),
      ];
    }
    const res = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      signal: rdAnalysisAbort.signal,
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.reply || 'تعذر التحليل');
    const reply = data.reply || data.content || data.message || '';
    disc.messages.push({ role: 'assistant', content: reply, at: new Date().toISOString() });
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
  rdMediaAction = 'share';
  document.getElementById('rdMediaChoiceTitle').textContent = 'مشاركة المحدد — نص أم صورة؟';
  rdShowModal('rdMediaChoiceModal');
}
function rdSelPublish() {
  if (!rdNeedActiveSel()) return;
  rdMediaAction = 'publish';
  document.getElementById('rdMediaChoiceTitle').textContent = 'نشر المحدد — نص أم صورة؟';
  rdShowModal('rdMediaChoiceModal');
}

async function rdMediaChoice(kind) {
  rdCloseModal('rdMediaChoiceModal');
  const action = rdMediaAction;
  rdMediaAction = null;
  if (!action) return;
  try {
    if (kind === 'text') {
      document.getElementById('rdReadTextStatus') && (document.getElementById('rdReadTextStatus').textContent = '');
      rdToast('جارٍ استخراج النص للمشاركة...');
      const ocr = await rdOcrSelection();
      const payload = `${ocr.text}\n\n—\n${rdCite()}`;
      if (action === 'share') await rdNativeShareText(payload);
      else if (typeof window.openDesignTextPublish === 'function') window.openDesignTextPublish(payload, null);
      else rdToast('نافذة النشر غير متاحة');
    } else {
      const blob = await rdCropSelBlob();
      if (!blob) throw new Error('تعذر قص الصورة');
      const up = await rdUploadBlob(blob, 'rd-share.png');
      const caption = rdCite();
      if (action === 'share') await rdNativeShareImage(blob, caption);
      else if (typeof window.openDesignImagePublish === 'function') {
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
