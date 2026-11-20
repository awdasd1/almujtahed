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
function rdNowStamp(from) {
  let now = from instanceof Date ? from : (from ? new Date(from) : new Date());
  if (Number.isNaN(now.getTime())) now = new Date();
  const weekday = new Intl.DateTimeFormat('ar-EG', { weekday: 'long' }).format(now);
  const hijri = new Intl.DateTimeFormat('ar-SA-u-ca-islamic', { day: 'numeric', month: 'long', year: 'numeric' }).format(now);
  const greg = new Intl.DateTimeFormat('ar-EG', { day: 'numeric', month: 'long', year: 'numeric' }).format(now);
  const time = now.toLocaleTimeString('ar-EG');
  return { iso: now.toISOString ? now.toISOString() : new Date().toISOString(), display: `${weekday} ${hijri} — الموافق ${greg} — ${time}` };
}
function rdStampOn(obj) {
  if (!obj) return obj;
  if (obj.created_at && obj.created_display) return obj;
  const s = obj.created_at ? rdNowStamp(obj.created_at) : rdNowStamp();
  obj.created_at = obj.created_at || s.iso;
  obj.created_display = obj.created_display || s.display;
  return obj;
}

let rdDetailId = null;

async function initReadingTab() {
  if (rdLoaded) { renderRdProjects(); if (rdDetailId) rdRenderProjectDetail(); return; }
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

function rdPartsOf(p) {
  if (!p || !p.book) return [];
  const b = rdEnsureParts(p.book);
  return (b && b.parts) || [];
}
function rdBundleSpan(parts, idx) {
  const part = parts && parts[idx];
  if (!part || !part.bundleId) return { start: idx, count: 1 };
  let start = idx, end = idx;
  while (start > 0 && parts[start - 1] && parts[start - 1].bundleId === part.bundleId) start--;
  while (end + 1 < parts.length && parts[end + 1] && parts[end + 1].bundleId === part.bundleId) end++;
  return { start, count: end - start + 1 };
}
function rdBookRows(p) {
  const parts = rdPartsOf(p);
  const rows = [];
  for (let i = 0; i < parts.length; ) {
    const span = rdBundleSpan(parts, i);
    const meta = rdPartMetaOf(p, parts[i], i);
    if (span.count > 1) meta.partNo = 'جميع الأجزاء';
    rows.push({ start: i, count: span.count, meta, part: parts[i] });
    i += span.count;
  }
  return rows;
}
function rdBookCount(p) { return rdBookRows(p).length; }

function renderRdProjects() {
  const tbody = document.getElementById('rdProjectsTableBody');
  if (!tbody) return;
  if (!rdProjects.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="4" class="groups-empty-state">
          <p style="font-size: 14px; margin-bottom: 12px;">لا مشاريع قراءة بعد. أنشئ أول مشروع، ثم أضف كتبه وأجزاءه داخله.</p>
          <button type="button" class="btn-flat-primary" onclick="rdOpenCreateModal()" style="margin: 0 auto;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
            <span>إنشاء مشروع جديد</span>
          </button>
        </td>
      </tr>`;
    return;
  }
  tbody.innerHTML = rdProjects.map(p => {
    const count = rdBookCount(p);
    return `
      <tr id="rdrow_${p.id}">
        <td>
          <div class="group-name-cell" onclick="rdOpenProjectDetail('${p.id}')" title="انقر لفتح المشروع وإضافة الكتب">
            <span class="group-icon-avatar">📖</span>
            <span>${rdEsc(p.title)}</span>
          </div>
        </td>
        <td><div class="group-desc-cell">${rdEsc(p.desc || '')}</div></td>
        <td style="text-align:center">
          <span class="group-badge-count">${count ? `${count} ${count === 1 ? 'كتاب' : 'أجزاء'}` : 'بلا كتب'}</span>
        </td>
        <td style="text-align:center">
          <div class="group-actions-cell">
            <button type="button" class="action-icon-btn btn-edit-group" onclick="rdOpenProjectDetail('${p.id}')" title="فتح المشروع وإضافة الكتب">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button type="button" class="action-icon-btn btn-duplicate-group" onclick="rdDuplicateProject('${p.id}')" title="تكرار المشروع">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="13" height="13" x="9" y="9" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
            <button type="button" class="action-icon-btn btn-export-group" onclick="rdExportProject('${p.id}')" title="تصدير المشروع وكتبه ZIP">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            </button>
            <button type="button" class="action-icon-btn btn-share-group" onclick="rdShareProjectPack('${p.id}')" title="مشاركة المشروع مضغوطًا مع كتبه">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
            </button>
            <button type="button" class="action-icon-btn btn-delete-group" onclick="rdDeleteProject('${p.id}')" title="حذف المشروع">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </td>
      </tr>`;
  }).join('');
}

function rdOpenCreateModal(editId) {
  const overlay = document.getElementById('rdProjectModalOverlay');
  const idEl = document.getElementById('rdEditProjectId');
  const nameEl = document.getElementById('rdGroupNameInput');
  const descEl = document.getElementById('rdGroupDescInput');
  const titleEl = document.getElementById('rdProjectModalTitle');
  const btn = document.getElementById('rdProjectModalSubmit');
  const hint = document.getElementById('rdNewDateHint');
  const p = editId ? rdProject(editId) : null;
  if (idEl) idEl.value = p ? p.id : '';
  if (nameEl) nameEl.value = p ? (p.title || '') : '';
  if (descEl) descEl.value = p ? (p.desc || '') : '';
  if (titleEl) titleEl.textContent = p ? 'تعديل مشروع القراءة' : 'إنشاء مشروع قراءة';
  if (btn) btn.textContent = p ? 'حفظ' : 'إنشاء';
  if (hint) hint.textContent = p ? `أُنشئ: ${p.created_display || ''}` : `تاريخ بداية المشروع إن اعتمدته الآن: ${rdNowStamp().display}`;
  if (overlay) overlay.classList.add('open');
  setTimeout(() => nameEl && nameEl.focus(), 80);
}
function rdCloseCreateModal() {
  const overlay = document.getElementById('rdProjectModalOverlay');
  if (overlay) overlay.classList.remove('open');
}
function rdHandleProjectModalOverlay(e) {
  if (e.target.id === 'rdProjectModalOverlay') rdCloseCreateModal();
}
function rdSaveProjectFromModal() {
  const editId = (document.getElementById('rdEditProjectId').value || '').trim();
  const title = (document.getElementById('rdGroupNameInput').value || '').trim();
  const desc = (document.getElementById('rdGroupDescInput').value || '').trim();
  if (!title) { rdToast('اكتب اسم المشروع'); document.getElementById('rdGroupNameInput')?.focus(); return; }
  if (!desc) { rdToast('اكتب وصف المشروع'); document.getElementById('rdGroupDescInput')?.focus(); return; }
  if (editId) {
    const p = rdProject(editId);
    if (!p) return;
    p.title = title; p.desc = desc; p.updated_at = new Date().toISOString();
    rdSave(); renderRdProjects(); rdRenderProjectDetail(); rdCloseCreateModal();
    rdToast(`حُدّث مشروع «${title}»`);
    return;
  }
  const stamp = rdNowStamp();
  const p = {
    id: rdUid(), title, desc,
    bookName: '', author: '', edition: '',
    created_at: stamp.iso, created_display: stamp.display,
    book: null, page: 1, annotations: {}, updated_at: stamp.iso,
  };
  rdProjects.unshift(p);
  rdSave(); renderRdProjects(); rdCloseCreateModal();
  rdOpenProjectDetail(p.id);
  rdToast(`أُنشئ مشروع «${title}» — أضف كتبه أو أجزاءه`);
}
function rdShowProjectsView() {
  rdDetailId = null;
  const list = document.getElementById('rdProjectsSection');
  const det = document.getElementById('rdProjectDetailSection');
  if (list) list.style.display = '';
  if (det) det.style.display = 'none';
  renderRdProjects();
}
function rdOpenProjectDetail(id) {
  const p = rdProject(id);
  if (!p) return;
  rdDetailId = id;
  const list = document.getElementById('rdProjectsSection');
  const det = document.getElementById('rdProjectDetailSection');
  if (list) list.style.display = 'none';
  if (det) det.style.display = '';
  rdRenderProjectDetail();
}
window.rdOpenProjectDetail = rdOpenProjectDetail;
function rdPartStartPage(book, idx) {
  let n = 1;
  const parts = (book && book.parts) || [];
  for (let i = 0; i < idx; i++) n += Number(parts[i].pages) || 0;
  return n;
}
function rdPartSourceLabel(part) {
  if (!part) return '—';
  if (part.source === 'shamela') return 'الشاملة المصوّرة';
  if (part.source === 'web') return 'من الشبكة';
  return 'PDF مرفوع';
}
function rdPartMetaOf(p, part, idx) {
  const n = (idx == null ? 0 : idx) + 1;
  return {
    book: (part && (part.bookName || part.title)) || (p && (p.bookName || (p.book && p.book.title))) || '',
    author: (part && part.author) || (p && p.author) || '',
    edition: (part && part.edition) || (p && p.edition) || '',
    partNo: (part && (part.partNo || part.part)) || String(n),
  };
}
function rdRenderProjectDetail() {
  const p = rdProject(rdDetailId);
  if (!p) { rdShowProjectsView(); return; }
  const title = document.getElementById('rdDetailTitle');
  const desc = document.getElementById('rdDetailDesc');
  const crumb = document.getElementById('rdProjectBreadcrumb');
  const tbody = document.getElementById('rdPartsTableBody');
  if (title) title.textContent = p.title;
  if (desc) desc.textContent = p.desc || '';
  if (crumb) crumb.textContent = `مشروع: ${p.title}`;
  if (!tbody) return;
  const parts = rdPartsOf(p);
  if (!parts.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="groups-empty-state"><p style="font-size:14px">لا توجد كتب في هذا المشروع بعد. أضف الكتاب أو الجزء الأول من الأزرار أسفل الجدول.</p></td></tr>`;
    return;
  }
  tbody.innerHTML = rdBookRows(p).map(row => {
    const i = row.start;
    const meta = row.meta;
    const part = row.part;
    const many = row.count > 1;
    return `
    <tr>
      <td>
        <div class="group-name-cell" onclick="rdOpenPartInReader('${p.id}', ${i})" title="فتح هذا الكتاب في نافذة القراءة">
          <span>${rdEsc(meta.book || part.title || `كتاب ${i + 1}`)}</span>
        </div>
      </td>
      <td><div class="group-desc-cell">${rdEsc(rdDash(meta.author))}</div></td>
      <td><div class="group-desc-cell">${rdEsc(rdDash(meta.edition))}</div></td>
      <td style="text-align:center"><span class="group-badge-count">${rdEsc(meta.partNo)}</span></td>
      <td style="text-align:center">
        <div class="group-actions-cell">
          <button type="button" class="action-icon-btn btn-edit-group" onclick="rdEditPartMeta('${p.id}', ${i})" title="تعديل الاسم والوصف">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button type="button" class="action-icon-btn" onclick="rdOpenBookAnalysis('${p.id}', ${i})" title="تحليل الكتاب">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>
          </button>
          <button type="button" class="action-icon-btn" onclick="rdOpenPartInReader('${p.id}', ${i})" title="فتح القراءة">📖</button>
          <button type="button" class="action-icon-btn btn-export-group" onclick="rdExportProject('${p.id}', ${i})" title="${many ? 'تصدير هذا الكتاب ZIP' : 'تصدير هذا الجزء ZIP'}">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          </button>
          <button type="button" class="action-icon-btn btn-share-group" onclick="rdShareProjectPack('${p.id}', ${i})" title="${many ? 'مشاركة هذا الكتاب مضغوطًا' : 'مشاركة هذا الجزء مضغوطًا'}">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
          </button>
          <button type="button" class="action-icon-btn btn-delete-group" onclick="rdDeletePart('${p.id}', ${i})" title="حذف هذا الكتاب من المشروع">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/></svg>
          </button>
        </div>
      </td>
    </tr>`;
  }).join('');
}
function rdOpenPartInReader(id, idx) {
  const p = rdProject(id);
  if (!p || !p.book) { rdOpenProject(id); return; }
  rdEnsureParts(p.book);
  p.page = rdPartStartPage(p.book, idx);
  rdOpenProject(id);
}
window.rdOpenPartInReader = rdOpenPartInReader;

function rdRemapPagesAfterPartDelete(p, start, len) {
  const end = start + Math.max(0, len) - 1;
  const shift = n => {
    const v = Number(n);
    if (!v) return v;
    if (v >= start && v <= end) return null;
    if (v > end) return v - len;
    return v;
  };
  const ann = p.annotations || {};
  const nextAnn = {};
  Object.keys(ann).forEach(k => {
    const nv = shift(k);
    if (nv == null) return;
    nextAnn[String(nv)] = ann[k];
  });
  p.annotations = nextAnn;
  const discs = p.discussions || {};
  Object.keys(discs).forEach(id => {
    const d = discs[id];
    if (!d) return;
    const nv = shift(d.page);
    if (nv == null) delete discs[id];
    else d.page = nv;
  });
}
async function rdDeletePart(id, idx) {
  const p = rdProject(id);
  if (!p) return;
  const parts = rdPartsOf(p);
  const i = Number(idx);
  const part = parts[i];
  if (!part) return;
  const span = rdBundleSpan(parts, i);
  const meta = rdPartMetaOf(p, part, i);
  const partLabel = span.count > 1 ? 'جميع الأجزاء' : (meta.partNo && `الجزء ${meta.partNo}`);
  const label = [meta.book || part.title || 'الكتاب', partLabel].filter(Boolean).join(' — ');
  let ok = false;
  if (typeof showConfirmDialog === 'function') {
    ok = await showConfirmDialog({
      title: 'تأكيد حذف الكتاب',
      message: `حذف «${label}» من المشروع مع تعليقاته على صفحاته؟`,
      confirmText: 'نعم، احذف',
      cancelText: 'إلغاء',
      danger: true,
      icon: 'trash-2',
    });
  } else {
    ok = confirm(`حذف «${label}» من المشروع؟`);
  }
  if (!ok) return;
  const start = rdPartStartPage(p.book, span.start);
  const len = parts.slice(span.start, span.start + span.count).reduce((s, x) => s + (Number(x.pages) || 0), 0);
  rdRemapPagesAfterPartDelete(p, start, len);
  parts.splice(span.start, span.count);
  if (!parts.length) {
    p.book = null;
    p.page = 1;
    p.annotations = {};
  } else {
    rdEnsureParts(p.book);
    const first = rdPartMetaOf(p, parts[0], 0);
    if (first.book) {
      p.book.title = first.book;
      p.bookName = first.book;
    }
    if (p.page >= start && p.page < start + len) p.page = Math.max(1, start - 1) || 1;
    else if (p.page >= start + len) p.page -= len;
    p.page = Math.max(1, Math.min(p.book.pages || 1, p.page || 1));
  }
  if (rdBookAnalysisId === id) {
    if (rdBookAnalysisPartIdx === i || (Number.isInteger(rdBookAnalysisPartIdx) && rdBookAnalysisPartIdx >= span.start && rdBookAnalysisPartIdx < span.start + span.count)) {
      rdBookAnalysisId = null; rdBookAnalysisPartIdx = null; rdCloseModal('rdBookAnalysisModal');
    } else if (Number.isInteger(rdBookAnalysisPartIdx) && rdBookAnalysisPartIdx >= span.start + span.count) rdBookAnalysisPartIdx -= span.count;
  }
  if (rdCurrent && rdCurrent.id === id) {
    if (!p.book && rdReaderIsOpen()) rdCloseReader();
    else if (rdReaderIsOpen()) { rdUpdateBookUI(); rdLoadPage(p.page || 1); }
  }
  rdSave();
  rdRenderProjectDetail();
  renderRdProjects();
  rdToast(`حُذف «${label}» من المشروع`);
}
window.rdDeletePart = rdDeletePart;

let rdPendingPartMeta = null;
function rdMountDetailUploadInput() {
  const el = document.getElementById('rdDetailUploadInput');
  if (!el) return null;
  if (el.parentElement !== document.body) document.body.appendChild(el);
  el.classList.add('rd-top-file-input');
  el.style.cssText = 'position:fixed;left:0;top:0;width:1px;height:1px;opacity:0;z-index:2147483647;pointer-events:none;';
  return el;
}
function rdAddPart(kind) {
  const p = rdProject(rdDetailId);
  if (!p) { rdToast('افتح مشروعًا أولًا'); return false; }
  rdCurrent = p;
  rdAppendMode = !!p.book;
  rdOpenPartMetaModal({ kind });
  return false;
}
window.rdAddPart = rdAddPart;
function rdOpenPartMetaModal(opts) {
  const overlay = document.getElementById('rdPartMetaOverlay');
  const p = rdProject(rdDetailId);
  const parts = rdPartsOf(p);
  const editIdx = opts && opts.editIdx != null && opts.editIdx !== '' ? Number(opts.editIdx) : null;
  const kind = (opts && opts.kind) || '';
  const editing = Number.isInteger(editIdx) && parts[editIdx];
  const last = parts.length ? parts[parts.length - 1] : null;
  const lastMeta = last ? rdPartMetaOf(p, last, parts.length - 1) : null;
  const nextNo = lastMeta && /^\d+$/.test(String(lastMeta.partNo).trim())
    ? String(Number(lastMeta.partNo) + 1)
    : String(parts.length + 1);
  const meta = editing ? rdPartMetaOf(p, parts[editIdx], editIdx) : {
    book: lastMeta ? lastMeta.book : '',
    author: lastMeta ? lastMeta.author : '',
    edition: lastMeta ? lastMeta.edition : '',
    partNo: nextNo,
  };
  if (editing && rdBundleSpan(parts, editIdx).count > 1) meta.partNo = 'جميع الأجزاء';
  const setv = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
  setv('rdPartMetaKind', editing ? 'edit' : kind);
  setv('rdPartMetaEditIdx', editing ? String(editIdx) : '');
  setv('rdPartBookName', meta.book);
  setv('rdPartAuthor', meta.author);
  setv('rdPartEdition', meta.edition);
  setv('rdPartNo', meta.partNo);
  const titleEl = document.getElementById('rdPartMetaTitle');
  const btn = document.getElementById('rdPartMetaSubmit');
  if (titleEl) titleEl.textContent = editing ? 'تعديل بيانات الكتاب' : 'بيانات الكتاب';
  if (btn) btn.textContent = editing ? 'حفظ' : (kind === 'upload' ? 'متابعة واختيار الملف' : 'متابعة');
  if (overlay) {
    if (overlay.parentElement !== document.body) document.body.appendChild(overlay);
    overlay.classList.add('open');
  }
  setTimeout(() => document.getElementById('rdPartBookName')?.focus(), 80);
}
function rdClosePartMetaModal() {
  const overlay = document.getElementById('rdPartMetaOverlay');
  if (overlay) overlay.classList.remove('open');
}
function rdHandlePartMetaOverlay(e) {
  if (e.target.id === 'rdPartMetaOverlay') rdClosePartMetaModal();
}
function rdReadPartMetaForm() {
  const bookName = (document.getElementById('rdPartBookName')?.value || '').trim();
  const author = (document.getElementById('rdPartAuthor')?.value || '').trim();
  const edition = (document.getElementById('rdPartEdition')?.value || '').trim();
  const partNo = (document.getElementById('rdPartNo')?.value || '').trim();
  if (!bookName) { rdToast('اكتب اسم الكتاب'); document.getElementById('rdPartBookName')?.focus(); return null; }
  if (!partNo) { rdToast('اكتب رقم الجزء أو اسمه'); document.getElementById('rdPartNo')?.focus(); return null; }
  return { bookName, author, edition, partNo };
}
function rdApplyMetaToPart(part, meta, keepPartNo) {
  if (!part || !meta) return part;
  part.bookName = meta.bookName;
  part.title = meta.bookName || part.title;
  part.author = meta.author;
  part.edition = meta.edition;
  if (!keepPartNo) part.partNo = meta.partNo;
  return part;
}
function rdEditPartMeta(id, idx) {
  rdDetailId = id;
  rdOpenPartMetaModal({ kind: 'edit', editIdx: idx });
}
window.rdEditPartMeta = rdEditPartMeta;
function rdSubmitPartMeta() {
  const meta = rdReadPartMetaForm();
  if (!meta) return;
  const kind = (document.getElementById('rdPartMetaKind')?.value || '').trim();
  const editRaw = (document.getElementById('rdPartMetaEditIdx')?.value || '').trim();
  const p = rdProject(rdDetailId);
  if (!p) return;
  if (kind === 'edit') {
    const idx = Number(editRaw);
    const parts = rdPartsOf(p);
    if (!parts[idx]) return;
    const span = rdBundleSpan(parts, idx);
    const keepNos = span.count > 1 && /^(جميع|كل)\s*الأجزاء$/.test(String(meta.partNo || '').trim());
    for (let j = span.start; j < span.start + span.count; j++) {
      rdApplyMetaToPart(parts[j], meta, keepNos);
    }
    if (idx === 0) {
      p.bookName = meta.bookName;
      p.author = meta.author;
      p.edition = meta.edition;
    }
    if (p.book) p.book.title = meta.bookName || p.book.title;
    rdSave(); rdRenderProjectDetail();
    if (rdCurrent && rdCurrent.id === p.id) rdUpdateBookUI();
    rdClosePartMetaModal();
    rdToast('حُفظت بيانات الكتاب');
    return;
  }
  rdPendingPartMeta = meta;
  rdCurrent = p;
  rdAppendMode = !!p.book;
  rdClosePartMetaModal();
  if (kind === 'upload') {
    const input = rdMountDetailUploadInput();
    if (input) {
      input.value = '';
      input.click();
    } else rdToast('تعذر فتح نافذة اختيار الملف');
    return;
  }
  rdOpenSource(kind);
}

function rdBookMeta(p) {
  return {
    book: (p && (p.bookName || (p.book && p.book.title) || p.title)) || '',
    author: (p && p.author) || '',
    edition: (p && p.edition) || '',
  };
}
function rdDash(v) { const s = String(v || '').trim(); return s || '—'; }
function rdCommentWhen(item) {
  if (!item) return '—';
  if (item.created_display) return item.created_display;
  if (item.created_at) return rdNowStamp(item.created_at).display;
  return '—';
}
function rdFormatRefs(disc) {
  const rows = [];
  const seen = new Set();
  const pushW = (w) => {
    if (!w) return;
    const title = w.title || w.book_title || w.book || '';
    const part = w.part ? `الجزء ${w.part}` : '';
    const page = w.page ? `صفحة ${w.page}` : '';
    const line = [title ? `«${title}»` : '', part, page].filter(Boolean).join(' — ');
    if (line && !seen.has(line)) { seen.add(line); rows.push(line); }
  };
  (disc && disc.messages || []).forEach(m => (m.witnesses || []).forEach(pushW));
  if (rows.length) return rows.join('\n');
  const text = (disc && disc.messages || []).filter(m => m.role === 'assistant').map(m => m.content || '').join('\n');
  const re = /«([^»]{2,80})»[^\n]{0,60}?(?:الجزء|جـ|ج)\s*([\d٠-٩]+)[^\n]{0,28}?(?:صفحة|ص)\s*([\d٠-٩]+)/g;
  let m;
  while ((m = re.exec(text))) {
    const line = `«${m[1]}» — الجزء ${m[2]} — صفحة ${m[3]}`;
    if (!seen.has(line)) { seen.add(line); rows.push(line); }
  }
  return rows.join('\n');
}
function rdLocus(filePage, book) {
  const n = Number(filePage) || 1;
  if (!book) return { filePage: n, part: 1, shown: n };
  const info = rdPartInfoAt(book, n);
  return { filePage: n, part: info.idx + 1, shown: info.local - info.off };
}
function rdCollectComments(p) {
  if (!p) return [];
  const rows = [];
  const book = p.book;
  const anns = p.annotations || {};
  Object.keys(anns).forEach(page => {
    const ann = anns[page] || {};
    const loc = rdLocus(page, book);
    const base = () => ({ filePage: loc.filePage, part: loc.part, shown: loc.shown });
    (ann.highlights || []).forEach(h => rows.push({
      kind: 'تحديد', text: h.text || '', analysis: '', refs: '', commentKind: '',
      when: rdCommentWhen(h), at: h.created_at || '', ...base(),
    }));
    (ann.strokes || []).forEach(s => rows.push({
      kind: 'رسم بالقلم', text: '', analysis: '', refs: '', commentKind: '',
      when: rdCommentWhen(s), at: s.created_at || '', ...base(),
    }));
    (ann.crops || []).forEach(c => rows.push({
      kind: 'تحديد', text: c.text || '', analysis: '', refs: '', commentKind: '',
      when: rdCommentWhen(c), at: c.created_at || '', ...base(),
    }));
    (ann.notes || []).forEach(n => {
      if (!String(n.text || '').trim()) return;
      rows.push({
        kind: 'ملحوظة', text: n.text, analysis: '', refs: '', commentKind: 'ملحوظة من تعليق القارئ',
        when: rdCommentWhen(n), at: n.created_at || '', ...base(),
      });
    });
  });
  Object.values(p.discussions || {}).forEach(d => {
    const loc = rdLocus(d.page, book);
    const answers = (d.messages || []).filter(m => m && m.role === 'assistant').map(m => m.content || '').filter(Boolean);
    rows.push({
      kind: 'تحليل',
      text: d.extracted_text || '',
      analysis: answers.join('\n\n'),
      refs: rdFormatRefs(d),
      commentKind: d.mode === 'fast' ? 'تحليل سريع من ذاكرة النموذج' : 'محرر',
      when: rdCommentWhen(d),
      at: d.created_at || '',
      filePage: loc.filePage, part: loc.part, shown: loc.shown,
    });
  });
  (p.summaries || []).forEach(s => {
    const loc = rdLocus(s.fileFrom || s.filePage || 1, book);
    const from = s.from != null ? s.from : loc.shown;
    const to = s.to != null ? s.to : from;
    const same = from === to;
    rows.push({
      kind: 'تلخيص',
      text: same ? `صفحة ${from}` : `صفحات ${from}–${to}`,
      analysis: s.text || '',
      refs: '',
      commentKind: 'تلخيص',
      when: rdCommentWhen(s),
      at: s.created_at || '',
      filePage: loc.filePage,
      part: loc.part,
      shown: same ? from : `${from}–${to}`,
    });
  });
  rows.sort((a, b) => String(a.at).localeCompare(String(b.at)));
  return rows;
}
let rdBookAnalysisId = null;
let rdBookAnalysisPartIdx = null;
let rdReturnToAnalysis = false;
function rdCommentPartLabel(p, r) {
  const book = p && p.book;
  if (book && r && r.filePage) {
    const info = rdPartInfoAt(book, r.filePage);
    if (info.vol) return rdVolumeLabel(info.vol.name, 0);
    const meta = rdPartMetaOf(p, info.part, info.idx);
    const n = String((meta && meta.partNo) || '').trim();
    if (n && !/^(جميع|كل)\s*الأجزاء$/.test(n)) return n;
  }
  const n = r && r.part;
  return n == null || n === '' ? '' : String(n);
}
function rdFilterCommentsForPart(p, partIdx) {
  let rows = rdCollectComments(p);
  if (!Number.isInteger(partIdx)) return { rows, span: { start: 0, count: 0 } };
  const parts = rdPartsOf(p);
  const span = rdBundleSpan(parts, partIdx);
  if (span.count > 1) {
    rows = rows.filter(r => Number(r.part) >= span.start + 1 && Number(r.part) < span.start + span.count + 1);
  } else {
    rows = rows.filter(r => Number(r.part) === partIdx + 1);
  }
  return { rows, span };
}
function rdOpenBookAnalysis(id, partIdx) {
  const p = rdProject(id);
  if (!p) return;
  rdBookAnalysisId = id;
  rdBookAnalysisPartIdx = (partIdx == null || partIdx === '') ? null : Number(partIdx);
  const parts = rdPartsOf(p);
  const part = Number.isInteger(rdBookAnalysisPartIdx) ? parts[rdBookAnalysisPartIdx] : null;
  const meta = part ? rdPartMetaOf(p, part, rdBookAnalysisPartIdx) : rdBookMeta(p);
  const sliced = rdFilterCommentsForPart(p, rdBookAnalysisPartIdx);
  const rows = sliced.rows;
  if (sliced.span.count > 1) meta.partNo = 'جميع الأجزاء';
  const title = document.getElementById('rdBookAnalysisTitle');
  const hint = document.getElementById('rdBookAnalysisMeta');
  const wrap = document.getElementById('rdBookAnalysisWrap');
  const dl = document.getElementById('rdBookAnalysisDownload');
  const sh = document.getElementById('rdBookAnalysisShare');
  const partLabel = meta.partNo === 'جميع الأجزاء' ? meta.partNo : (meta.partNo ? `الجزء ${meta.partNo}` : '');
  if (title) title.textContent = `تحليل الكتاب — ${meta.book || p.title}${partLabel ? ` — ${partLabel}` : ''}`;
  if (hint) hint.textContent = [meta.book && `الكتاب: ${meta.book}`, meta.author && `المؤلف: ${meta.author}`, meta.edition && `الطبعة: ${meta.edition}`, partLabel, `${rows.length} تعليقًا`].filter(Boolean).join(' · ');
  if (dl) dl.disabled = !rows.length;
  if (sh) sh.disabled = !rows.length;
  if (wrap) {
    if (!rows.length) {
      wrap.innerHTML = `<div class="rd-book-analysis-empty">${Number.isInteger(rdBookAnalysisPartIdx) ? 'لا تعليقات مرصودة بعد في هذا الجزء.' : 'لا تعليقات مرصودة بعد في هذا المشروع.'}</div>`;
    } else {
      wrap.innerHTML = `<table class="rd-book-analysis-table">
        <thead><tr>
          <th>اسم الكتاب</th><th>المؤلف</th><th>الطبعة</th><th>الجزء</th><th>الصفحة</th><th>النوع</th>
          <th>النص</th><th>التحليل والتعليق</th><th>المرجع</th><th>نوع التعليق</th><th>التاريخ والوقت</th><th>الموضع</th>
        </tr></thead>
        <tbody>${rows.map(r => `<tr>
          <td>${rdEsc(rdDash(meta.book))}</td>
          <td>${rdEsc(rdDash(meta.author))}</td>
          <td>${rdEsc(rdDash(meta.edition))}</td>
          <td>${rdEsc(rdDash(rdCommentPartLabel(p, r)))}</td>
          <td>${rdEsc(rdDash(r.shown))}</td>
          <td>${rdEsc(r.kind)}</td>
          <td class="rd-ba-text">${rdEsc(rdDash(r.text))}</td>
          <td class="rd-ba-analysis">${rdEsc(rdDash(r.analysis))}</td>
          <td>${rdEsc(rdDash(r.refs))}</td>
          <td>${rdEsc(rdDash(r.commentKind))}</td>
          <td>${rdEsc(rdDash(r.when))}</td>
          <td class="rd-ba-locus"><button type="button" class="rd-ba-go" title="فتح الصفحة في نافذة القراءة" onclick="rdGotoCommentPage('${p.id}', ${Number(r.filePage) || 1})">📄</button></td>
        </tr>`).join('')}</tbody>
      </table>`;
    }
  }
  rdShowModal('rdBookAnalysisModal');
}
window.rdOpenBookAnalysis = rdOpenBookAnalysis;
function rdGotoCommentPage(id, filePage) {
  const p = rdProject(id);
  if (!p || !p.book) { rdToast('لا كتاب في هذا المشروع بعد'); return; }
  rdReturnToAnalysis = true;
  rdCloseModal('rdBookAnalysisModal');
  p.page = Math.max(1, Math.min(p.book.pages || 1, Number(filePage) || 1));
  rdOpenProject(id);
}
window.rdGotoCommentPage = rdGotoCommentPage;
function rdCsvCell(v) {
  return `"${String(v ?? '').replace(/"/g, '""')}"`;
}
function rdBookAnalysisCsv() {
  const p = rdProject(rdBookAnalysisId);
  if (!p) return null;
  const parts = rdPartsOf(p);
  const part = Number.isInteger(rdBookAnalysisPartIdx) ? parts[rdBookAnalysisPartIdx] : null;
  const meta = part ? rdPartMetaOf(p, part, rdBookAnalysisPartIdx) : rdBookMeta(p);
  const sliced = rdFilterCommentsForPart(p, rdBookAnalysisPartIdx);
  const rows = sliced.rows;
  if (sliced.span.count > 1) meta.partNo = 'جميع الأجزاء';
  if (!rows.length) return null;
  const heads = ['اسم الكتاب', 'المؤلف', 'الطبعة', 'الجزء', 'الصفحة', 'النوع', 'النص', 'التحليل والتعليق', 'المرجع', 'نوع التعليق', 'التاريخ والوقت'];
  const lines = [heads.map(rdCsvCell).join(',')];
  rows.forEach(r => {
    lines.push([meta.book, meta.author, meta.edition, rdCommentPartLabel(p, r), r.shown, r.kind, r.text, r.analysis, r.refs, r.commentKind, r.when].map(rdCsvCell).join(','));
  });
  const book = String(meta.book || p.title || 'كتاب').replace(/[\\/:*?"<>|]+/g, ' ').trim() || 'كتاب';
  const fileName = `تحليل-${book}.csv`;
  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
  const file = new File([blob], fileName, { type: 'text/csv' });
  return { p, meta, rows, blob, file, fileName, title: `تحليل ${book}` };
}
function rdDownloadBookAnalysis() {
  const pack = rdBookAnalysisCsv();
  if (!pack) { rdToast('لا صفوف لتحميلها'); return; }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(pack.blob);
  a.download = pack.fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  rdToast('⬇ جرى تحميل الجدول');
}
window.rdDownloadBookAnalysis = rdDownloadBookAnalysis;
function rdShareBookAnalysis() {
  const pack = rdBookAnalysisCsv();
  if (!pack) { rdToast('لا صفوف لمشاركتها'); return; }
  rdShowShareModal('', pack.file, pack.title);
}
window.rdShareBookAnalysis = rdShareBookAnalysis;

function rdDuplicateProject(id) {
  const original = rdProject(id);
  if (!original) return;
  const cloned = JSON.parse(JSON.stringify(original));
  const stamp = rdNowStamp();
  cloned.id = rdUid();
  cloned.title = `${original.title} (نسخة)`;
  cloned.created_at = stamp.iso;
  cloned.created_display = stamp.display;
  cloned.updated_at = stamp.iso;
  rdProjects.unshift(cloned);
  rdSave(); renderRdProjects();
  rdToast(`كُرّر مشروع «${cloned.title}»`);
}
window.rdDuplicateProject = rdDuplicateProject;

async function rdFetchProjectZip(id, partIdx) {
  await rdSave();
  const body = { project_id: id };
  if (partIdx != null && partIdx !== '') {
    const i = Number(partIdx);
    body.part_index = i;
    const span = rdBundleSpan(rdPartsOf(rdProject(id)), i);
    if (span.count > 1) body.part_count = span.count;
  }
  const res = await fetch('/api/reading-projects/export-project', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const blob = await res.blob();
  if (!res.ok) {
    let msg = 'تعذر تصدير المشروع';
    try { const j = JSON.parse(await blob.text()); msg = j.detail || msg; } catch (e) { /* */ }
    throw new Error(msg);
  }
  const p = rdProject(id);
  const parts = rdPartsOf(p);
  const i = Number(partIdx);
  const part = Number.isInteger(i) ? parts[i] : null;
  const span = Number.isInteger(i) ? rdBundleSpan(parts, i) : { count: 0 };
  const meta = part ? rdPartMetaOf(p, part, i) : null;
  if (meta && span.count > 1) meta.partNo = 'جميع الأجزاء';
  const safe = String((meta && meta.book) || (p && p.title) || 'مشروع').replace(/[\\/:*?"<>|]+/g, ' ').trim() || 'مشروع';
  const partBit = meta && meta.partNo ? `-ج${meta.partNo}` : '';
  return {
    blob,
    fileName: `قراءة-${safe}${partBit}.zip`,
    title: meta ? `${meta.book || safe}${meta.partNo ? ` — ${meta.partNo === 'جميع الأجزاء' ? meta.partNo : 'الجزء ' + meta.partNo}` : ''}` : ((p && p.title) || 'مشروع قراءة'),
  };
}
async function rdExportProject(id, partIdx) {
  try {
    rdToast(partIdx == null || partIdx === '' ? 'جارٍ تحزيم المشروع وكتبه...' : 'جارٍ تحزيم هذا الجزء...');
    const pack = await rdFetchProjectZip(id, partIdx);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(pack.blob);
    a.download = pack.fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    rdToast(`📤 صُدّر «${pack.title}» ملفًا مضغوطًا`);
  } catch (e) { rdToast(`❌ ${e.message}`, 5000); }
}
window.rdExportProject = rdExportProject;
async function rdShareProjectPack(id, partIdx) {
  try {
    rdToast(partIdx == null || partIdx === '' ? 'جارٍ تحزيم المشروع للمشاركة...' : 'جارٍ تحزيم هذا الجزء للمشاركة...');
    const pack = await rdFetchProjectZip(id, partIdx);
    const file = new File([pack.blob], pack.fileName, { type: 'application/zip' });
    rdShowShareModal('', file, pack.title);
  } catch (e) { rdToast(`❌ ${e.message}`, 5000); }
}
window.rdShareProjectPack = rdShareProjectPack;
async function rdHandleProjectImport(ev) {
  const file = (ev.target && ev.target.files && ev.target.files[0]) || null;
  if (ev.target) ev.target.value = '';
  if (!file) return;
  rdToast('جارٍ استيراد المشروع...');
  try {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/reading-projects/import-project', { method: 'POST', body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر الاستيراد');
    rdLoaded = false;
    await initReadingTab();
    if (data.id) rdOpenProjectDetail(data.id);
    rdToast(`✔ استُورد مشروع «${data.title || ''}»`);
  } catch (e) { rdToast(`❌ ${e.message}`, 5000); }
}
window.rdHandleProjectImport = rdHandleProjectImport;

async function rdDeleteProject(id) {
  const p = rdProject(id);
  if (!p) return;
  const parts = rdBookCount(p);
  const msg = parts
    ? `حذف مشروع «${p.title}» وكل كتبه وتعليقاته (${parts} جزءًا)؟`
    : `حذف مشروع قراءة «${p.title}» بكل تعليقاته؟`;
  let ok = false;
  if (typeof showConfirmDialog === 'function') {
    ok = await showConfirmDialog({
      title: 'تأكيد حذف مشروع القراءة',
      message: msg,
      confirmText: 'نعم، احذف المشروع',
      cancelText: 'إلغاء',
      danger: true,
      icon: 'trash-2',
    });
  } else {
    ok = confirm(msg);
  }
  if (!ok) return;
  rdProjects = rdProjects.filter(x => x.id !== id);
  if (rdDetailId === id) rdShowProjectsView();
  if (rdCurrent && rdCurrent.id === id) { rdCloseModal('rdReaderModal'); rdCurrent = null; }
  rdSave(); renderRdProjects();
  rdToast(`حُذف مشروع «${p.title}»`);
}

// ---------- نافذة القراءة ----------
function rdOpenProject(id) {
  const p = rdProject(id);
  if (!p) return;
  rdCurrent = p;
  if (p.book) rdEnsureParts(p.book);
  rdShowModal('rdReaderModal');
  rdBuildColorBars();
  rdSetTool('pen');
  rdUpdateBookUI();
  rdApplyView();
  rdLoadPage(p.page || 1);
  rdEnsureShamelaVolumes(p);
}
window.rdOpenProject = rdOpenProject;

function rdCloseReader() {
  const backId = rdReturnToAnalysis ? rdBookAnalysisId : null;
  const backPart = rdReturnToAnalysis ? rdBookAnalysisPartIdx : null;
  rdReturnToAnalysis = false;
  rdSaveNow(false);
  rdCloseModal('rdReaderModal');
  if (rdDetailId) rdCurrent = rdProject(rdDetailId);
  else rdCurrent = null;
  renderRdProjects();
  if (rdDetailId) rdRenderProjectDetail();
  if (backId) rdOpenBookAnalysis(backId, backPart);
}

function rdSaveNow(manual) {
  if (rdCurrent) rdCurrent.updated_at = new Date().toISOString();
  clearTimeout(rdSaveTimer);
  rdSave();
  const st = document.getElementById('rdSaveState');
  if (st && rdCurrent) st.textContent = `يُحفظ تلقائيًا — صفحة ${rdShownPage(rdCurrent.page, rdCurrent.book)}`;
}
function rdSaveSoon() {
  clearTimeout(rdSaveTimer);
  rdSaveTimer = setTimeout(() => rdSaveNow(false), 400);
}

// كتاب متعدد الأجزاء: parts متسلسلة وصفحات المشروع مرقّمة عبر الأجزاء كلها
function rdPartOf(nb) {
  const meta = rdPendingPartMeta || {};
  return {
    source: nb.source,
    title: meta.bookName || nb.title,
    bookName: meta.bookName || nb.title || '',
    author: meta.author || nb.author || '',
    edition: meta.edition || nb.edition || '',
    partNo: meta.partNo || nb.partNo || '',
    file_name: nb.file_name || null,
    book_id: nb.book_id || null,
    pages: nb.pages || 1,
    volumes: Array.isArray(nb.volumes) ? nb.volumes : undefined,
    bundleId: nb.bundleId || undefined,
  };
}
function rdEnsureParts(b) {
  if (!b) return null;
  if (!Array.isArray(b.parts) || !b.parts.length) b.parts = [rdPartOf(b)];
  b.pages = b.parts.reduce((s, x) => s + (x.pages || 0), 0) || b.pages || 1;
  return b;
}
function rdShamelaPartName(part) {
  const n = String((part && (part.partNo || part.part)) || '').trim();
  if (!n || /^(جميع|كل)\s*الأجزاء$/.test(n)) return '';
  return n;
}
function rdPartPageUrl(part, localPage) {
  if (part.source === 'shamela') {
    const q = [`book_id=${part.book_id}`, `pdf_page=${localPage}`, `v=${Date.now()}`];
    const name = rdShamelaPartName(part);
    if (name) q.push(`part=${encodeURIComponent(name)}`);
    return `/api/book/pdf-image?${q.join('&')}`;
  }
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
function rdReaderIsOpen() {
  const m = document.getElementById('rdReaderModal');
  return !!(m && !m.hidden);
}
function rdApplyBook(nb, asAppend, quiet) {
  if (!rdCurrent) return;
  const part = rdPartOf(nb);
  const meta = rdPendingPartMeta;
  rdPendingPartMeta = null;
  if (asAppend && rdCurrent.book) {
    const b = rdEnsureParts(rdCurrent.book);
    const startPage = b.pages + 1;
    b.parts.push(part);
    rdEnsureParts(b);
    if (rdReaderIsOpen()) { rdUpdateBookUI(); rdLoadPage(startPage); }
    rdSaveNow(false);
    rdRenderProjectDetail();
    if (!quiet) rdToast(`✔ أُضيف الجزء ${part.partNo || b.parts.length} «${part.title}» (${part.pages} صفحة) — يبدأ من صفحة ${startPage}`);
    return;
  }
  nb.parts = [part];
  nb.title = part.title || nb.title;
  rdCurrent.book = nb;
  if (meta && meta.bookName) rdCurrent.bookName = meta.bookName;
  else if (!rdCurrent.bookName && nb.title) rdCurrent.bookName = nb.title;
  if (meta && meta.author) rdCurrent.author = meta.author;
  if (meta && meta.edition) rdCurrent.edition = meta.edition;
  rdCurrent.annotations = {};
  if (rdReaderIsOpen()) { rdUpdateBookUI(); rdLoadPage(1); }
  else rdCurrent.page = 1;
  rdSaveNow(false);
  rdRenderProjectDetail();
}

// تنبيه وجود كتاب حالي عند ضغط أي زر سحب/رفع
let rdPendingSource = null;
let rdAppendMode = false;
function rdGuardSource(kind, ev) {
  rdPendingPartMeta = null;
  if (rdCurrent && rdCurrent.book) {
    if (ev) ev.preventDefault();
    rdPendingSource = kind;
    const b = rdEnsureParts(rdCurrent.book);
    document.getElementById('rdBookExistsText').textContent =
      `في هذا المشروع كتاب قائم الآن: «${b.title}» — ${b.pages} صفحة${b.parts.length > 1 ? ` في ${b.parts.length} أجزاء` : ''}، وأنت واقف عند صفحة ${rdShownPage(rdCurrent.page, b)}.`;
    rdShowModal('rdBookExistsModal');
    return false;
  }
  rdOpenSource(kind);
  return true;
}
function rdOpenSource(kind) {
  if (kind === 'shamela') rdOpenShamelaPicker();
  else if (kind === 'web') rdOpenWebFetch();
  else if (kind === 'upload') {
    const input = rdMountDetailUploadInput();
    if (input) { input.value = ''; input.click(); }
  }
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
    rdCloseModal('rdReaderModal');
    rdOpenCreateModal();
    rdToast('📖 أنشئ مشروع قراءة جديدًا لهذا الكتاب', 4000);
  } else {
    rdAppendMode = false;
  }
}

function rdOffsetOf(book) {
  const n = Math.trunc(Number(book && book.pageOffset) || 0);
  return Number.isFinite(n) ? n : 0;
}
function rdOffsetOfPart(part, book) {
  if (part && part.pageOffset != null && String(part.pageOffset) !== '') {
    const n = Math.trunc(Number(part.pageOffset));
    if (Number.isFinite(n)) return n;
  }
  return rdOffsetOf(book);
}
function rdOffsetOfVolume(vol, part, book) {
  if (vol && vol.pageOffset != null && String(vol.pageOffset) !== '') {
    const n = Math.trunc(Number(vol.pageOffset));
    if (Number.isFinite(n)) return n;
  }
  return rdOffsetOfPart(part, book);
}
function rdPartInfoAt(book, filePage) {
  const n = Math.max(1, Number(filePage) || 1);
  const b = rdEnsureParts(book);
  const offBook = rdOffsetOf(b);
  if (!b || !Array.isArray(b.parts) || !b.parts.length) {
    return { part: null, idx: 0, start: 1, pages: (b && b.pages) || 1, local: n, off: offBook, fileLocal: n };
  }
  let rest = n, idx = 0;
  for (let i = 0; i < b.parts.length; i++) {
    const pg = Number(b.parts[i].pages) || 0;
    if (rest <= pg) { idx = i; break; }
    rest -= pg;
    idx = i;
  }
  const part = b.parts[idx];
  const start = rdPartStartPage(b, idx);
  const localInFile = Math.max(1, rest);
  const vols = part && Array.isArray(part.volumes) && part.volumes.length > 1 ? part.volumes : null;
  if (vols) {
    let vi = 0;
    for (let i = 0; i < vols.length; i++) {
      const st = Math.max(1, Number(vols[i].pdf_start) || 1);
      if (localInFile >= st) vi = i;
    }
    const st = Math.max(1, Number(vols[vi].pdf_start) || 1);
    const nextRaw = vi + 1 < vols.length ? Number(vols[vi + 1].pdf_start) : NaN;
    const next = Number.isFinite(nextRaw) && nextRaw > st ? nextRaw : (Number(part.pages) || st) + 1;
    const pages = Math.max(1, next - st);
    return {
      part, idx, vol: vols[vi],
      start: start + st - 1,
      pages,
      local: localInFile - st + 1,
      off: rdOffsetOfVolume(vols[vi], part, b),
      fileLocal: localInFile,
    };
  }
  return {
    part, idx, vol: null,
    start,
    pages: Number(part.pages) || 1,
    local: localInFile,
    off: rdOffsetOfPart(part, b),
    fileLocal: localInFile,
  };
}
function rdShownPage(filePage, book) {
  const info = rdPartInfoAt(book, filePage);
  return info.local - info.off;
}
function rdFileFromShown(shown, book) {
  const here = (rdCurrent && rdCurrent.page) || 1;
  const info = rdPartInfoAt(book, here);
  const local = Math.max(1, Math.min(info.pages, (Number(shown) || 1) + info.off));
  return info.start + local - 1;
}
function rdSyncPageField(filePage) {
  const book = rdCurrent && rdCurrent.book;
  const input = document.getElementById('rdPageInput');
  if (!input || !book) return;
  const info = rdPartInfoAt(book, filePage);
  input.min = String(1 - info.off);
  input.max = String(info.pages - info.off);
  input.value = info.local - info.off;
}
function rdOpenPageOffset() {
  if (!rdCurrent || !rdCurrent.book) { rdToast('اسحب كتابًا أولًا'); return; }
  const info = rdPartInfoAt(rdCurrent.book, rdCurrent.page || 1);
  const input = document.getElementById('rdPageOffsetInput');
  if (input) input.value = info.off;
  rdRefreshOffsetPreview();
  rdShowModal('rdPageOffsetModal');
  setTimeout(() => input && input.focus(), 40);
}
function rdRefreshOffsetPreview() {
  const el = document.getElementById('rdPageOffsetPreview');
  const input = document.getElementById('rdPageOffsetInput');
  if (!el || !rdCurrent || !rdCurrent.book) return;
  const info = rdPartInfoAt(rdCurrent.book, rdCurrent.page || 1);
  const off = Math.trunc(Number(input && input.value) || 0);
  const shown = info.local - (Number.isFinite(off) ? off : 0);
  el.textContent = `هذا الجزء: صفحة الملف ${info.local} من ${info.pages}، ويظهر في الترقيم صفحة ${shown}.`;
}
function rdApplyPageOffset() {
  if (!rdCurrent || !rdCurrent.book) return;
  const raw = document.getElementById('rdPageOffsetInput').value;
  const off = Math.trunc(Number(raw));
  if (!Number.isFinite(off)) { rdToast('أدخل رقمًا فارقًا صحيحًا'); return; }
  const info = rdPartInfoAt(rdCurrent.book, rdCurrent.page || 1);
  if (Math.abs(off) >= info.pages) { rdToast('الرقم الفارق أصغر من عدد صفحات هذا الجزء'); return; }
  if (info.vol) info.vol.pageOffset = off;
  else if (info.part) info.part.pageOffset = off;
  else rdCurrent.book.pageOffset = off;
  rdUpdateBookUI();
  rdSyncPageField(rdCurrent.page || 1);
  rdSaveSoon();
  rdCloseModal('rdPageOffsetModal');
  rdToast(off ? `ضُبط هذا الجزء بفارق ${off}: رقم الكتاب = رقم الملف − ${off}` : 'أُلغي الفارق في هذا الجزء وعاد الترقيم إلى صفحات الملف');
}

function rdReaderHeading(p) {
  if (!p) return '📖 مشروع قراءة';
  if (!p.book) return `📖 ${p.title}`;
  const parts = rdPartsOf(p);
  const idx = Math.max(0, (rdLocus(p.page || 1, p.book).part || 1) - 1);
  const meta = rdPartMetaOf(p, parts[idx], idx);
  const bits = [meta.book || p.book.title || p.title, meta.author, meta.edition].filter(Boolean);
  return `📖 ${bits.join(' — ')}`;
}
function rdVolumeLabel(raw, i) {
  const s = String(raw || '').trim();
  if (!s) return String(i + 1);
  if (/^\d+$/.test(s)) return s;
  return s;
}
function rdVolumesOf(p) {
  if (!p || !p.book) return [];
  const book = rdEnsureParts(p.book);
  const parts = rdPartsOf(p);
  const idx = Math.max(0, (rdLocus(p.page || 1, p.book).part || 1) - 1);
  const span = rdBundleSpan(parts, idx);
  if (span.count > 1) {
    return Array.from({ length: span.count }, (_, k) => {
      const i = span.start + k;
      const meta = rdPartMetaOf(p, parts[i], i);
      return { label: rdVolumeLabel(meta.partNo, i), start: rdPartStartPage(book, i) };
    });
  }
  if (parts.length > 1 && !parts.some(x => x && x.bundleId)) {
    return parts.map((part, i) => {
      const meta = rdPartMetaOf(p, part, i);
      return { label: rdVolumeLabel(meta.partNo, i), start: rdPartStartPage(book, i) };
    });
  }
  const cur = parts[idx] || parts[0];
  const vols = cur && Array.isArray(cur.volumes) ? cur.volumes : [];
  if (vols.length > 1) {
    const base = rdPartStartPage(book, Math.max(0, parts.indexOf(cur)));
    return vols.map((v, i) => ({
      label: rdVolumeLabel(v && v.name, i),
      start: base + Math.max(1, Number(v && v.pdf_start) || 1) - 1,
    }));
  }
  return [];
}
function rdFillPartSelect() {
  const sel = document.getElementById('rdPartSelect');
  if (!sel) return;
  const vols = rdVolumesOf(rdCurrent);
  if (vols.length < 2) {
    sel.hidden = true;
    sel.innerHTML = '';
    return;
  }
  const page = (rdCurrent && rdCurrent.page) || 1;
  let cur = vols[0].start;
  vols.forEach(v => { if (page >= v.start) cur = v.start; });
  sel.innerHTML = vols.map(v => {
    const lab = /^\d+$/.test(v.label) ? `الجزء ${rdEsc(v.label)}` : rdEsc(v.label);
    return `<option value="${v.start}">${lab}</option>`;
  }).join('');
  sel.value = String(cur);
  sel.hidden = false;
}
function rdGoPart(start) {
  rdLoadPage(Number(start) || 1);
}
window.rdGoPart = rdGoPart;
async function rdEnsureShamelaVolumes(p) {
  const parts = rdPartsOf(p);
  const part = parts[0];
  if (!part || parts.length > 1 || part.source !== 'shamela' || !part.book_id) return;
  if (Array.isArray(part.volumes) && part.volumes.length > 1) return;
  try {
    const res = await fetch(`/api/book/pdf-info?book_id=${part.book_id}`);
    const info = await res.json();
    if (Array.isArray(info.volumes) && info.volumes.length > 1) {
      part.volumes = info.volumes;
      rdSaveSoon();
      rdFillPartSelect();
    }
  } catch (e) { /* بدون قائمة إن تعذر الجلب */ }
}
function rdUpdateBookUI() {
  const p = rdCurrent;
  const has = !!(p && p.book);
  document.getElementById('rdToolbar').classList.toggle('is-disabled', !has);
  document.getElementById('rdEmpty').style.display = has ? 'none' : 'flex';
  document.getElementById('rdPageImg').style.display = has ? 'block' : 'none';
  document.getElementById('rdA4').classList.toggle('has-book', has);
  const pi = has ? rdPartInfoAt(p.book, p.page || 1) : null;
  document.getElementById('rdPageTotal').textContent = pi ? (pi.pages - pi.off) : '—';
  const titleEl = document.getElementById('rdReaderTitle');
  if (titleEl) titleEl.textContent = rdReaderHeading(p);
  if (has) rdEnsureParts(p.book);
  rdFillPartSelect();
  const info = document.getElementById('rdBookInfo');
  if (!info) return;
  if (!has) { info.textContent = ''; return; }
  const parts = rdPartsOf(p);
  const idx = Math.max(0, pi.idx);
  const meta = rdPartMetaOf(p, parts[idx], idx);
  const src = p.book.source === 'shamela' ? 'من الشاملة المصوّرة' : p.book.source === 'web' ? 'من الشبكة' : 'PDF مرفوع';
  const partLabel = (pi.vol && rdVolumeLabel(pi.vol.name, 0)) || (meta.partNo && !/^(جميع|كل)\s*الأجزاء$/.test(String(meta.partNo)) ? meta.partNo : '');
  info.textContent = [
    meta.book && `الكتاب: ${meta.book}`,
    meta.author && `المؤلف: ${meta.author}`,
    meta.edition && `الطبعة: ${meta.edition}`,
    partLabel && `الجزء ${partLabel}`,
    `${pi.pages} صفحة في هذا الجزء`,
    `(${src})`,
  ].filter(Boolean).join(' — ');
}

function rdLoadPage(n) {
  const p = rdCurrent;
  if (!p || !p.book) { rdRenderAnnotations(); return; }
  n = Math.max(1, Math.min(p.book.pages || 1, Number(n) || 1));
  p.page = n;
  rdUpdateBookUI();
  rdSyncPageField(n);
  const img = document.getElementById('rdPageImg');
  img.onload = () => { rdFitCanvas(); rdRenderAnnotations(); };
  img.onerror = () => { rdToast('تعذر عرض هذه الصفحة'); };
  img.src = rdBookPageUrl(n);
  document.getElementById('rdPageScroll').scrollTop = 0;
  rdHideSelBar();
  rdActiveSel = null;
  rdSyncPageSumBadge();
  rdSaveSoon();
}

function rdFlipPage(d) {
  if (!rdCurrent || !rdCurrent.book) return;
  rdLoadPage((rdCurrent.page || 1) + d);
}
function rdGoPage(v) { rdLoadPage(rdFileFromShown(v, rdCurrent && rdCurrent.book)); }

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
      + `<span class="rd-color-ops"><button type="button" class="rd-color-add" title="إضافة لون من منتقي الألوان" onclick="rdAddColor('${target}', event)">+</button><button type="button" class="rd-color-add" title="إزالة آخر لون مضاف" onclick="rdRemoveColor('${target}')">−</button></span>`;
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
  if (target === 'bg') {
    const v = rdView();
    picker.value = v.bgColor || '#f4efe4';
  } else picker.value = target === 'note' ? rdNoteColor : rdColor;
  try {
    if (typeof picker.showPicker === 'function') picker.showPicker();
    else picker.click();
  } catch (e) {
    picker.click();
  }
}
function rdRemoveColor(target) {
  const key = target === 'note' ? 'note' : 'pen';
  const list = rdCustomColors[key] || [];
  if (!list.length) return;
  const removed = list.pop();
  try { localStorage.setItem('rdCustomColors', JSON.stringify(rdCustomColors)); } catch (e) { /* */ }
  const base = key === 'note' ? RD_NOTE_COLORS : RD_COLORS;
  const cur = key === 'note' ? rdNoteColor : rdColor;
  if (String(cur).toLowerCase() === String(removed).toLowerCase()) {
    const next = list.length ? list[list.length - 1] : base[0];
    if (key === 'note') rdNoteColor = next; else rdColor = next;
  }
  rdBuildColorBars();
}
document.addEventListener('DOMContentLoaded', () => {
  const picker = document.getElementById('rdColorPicker');
  if (!picker) return;
  picker.addEventListener('input', () => {
    const c = picker.value;
    if (rdColorTarget === 'bg') { rdApplyCustomBg(c); return; }
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
  const cv = document.getElementById('rdCanvas');
  if (cv) cv.style.cursor = t === 'crop' ? 'crosshair' : (t === 'loupe' ? 'none' : '');
  rdRenderAnnotations();
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
  let handleRect = null;
  if (rdDraw && rdDraw.type === 'resize') {
    handleRect = (ann.crops || [])[rdDraw.index];
  } else if (rdActiveSel && rdActiveSel.kind === 'c' && rdActiveSel.page === (rdCurrent.page || 1)) {
    handleRect = rdActiveSel.rect;
  }
  if (handleRect) rdDrawCropHandles(ctx, handleRect, W, H);
  rdRenderNotes();
  rdRenderCropsBar();
  rdSyncPageSumBadge();
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
  bar.innerHTML = crops.map((c, i) => `<button type="button" class="rd-crop-chip" onclick="rdZoomToCrop(${i})">✂ قصاصة ${i + 1} — صفحة ${rdShownPage(rdCurrent.page, rdCurrent.book)}</button>`).join('');
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
  const el = document.getElementById('rdClearPageText');
  if (el) el.textContent = `سيتم إزالة جميع التعليقات من هذه الصفحة فقط (صفحة ${rdShownPage(rdCurrent.page, rdCurrent.book)}: رسوم الأقلام والتظليل والقصاصات وملصقات الملحوظات)، وتبقى تعليقات بقية الصفحات كما هي دون مساس.`;
  rdShowModal('rdClearPageModal');
}
function rdConfirmClearPage() {
  if (!rdCurrent) { rdCloseModal('rdClearPageModal'); return; }
  const page = rdCurrent.page || 1;
  const ann = rdPageAnn();
  ann.strokes = []; ann.highlights = []; ann.crops = []; ann.notes = []; ann.seq = [];
  document.querySelectorAll('.rd-note-editor').forEach(x => { if (x._rdNoteRo) x._rdNoteRo.disconnect(); x.remove(); });
  rdCloseModal('rdClearPageModal');
  rdRenderAnnotations(); rdSaveSoon();
  rdToast(`🧹 مُسحت كل تعليقات صفحة ${rdShownPage(page, rdCurrent.book)} وحدها`);
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
  const custom = v.bg === 'custom' && v.bgColor;
  const bg = custom
    ? { page: v.bgColor, sepia: 0, bright: 1, sat: 1 }
    : (RD_BGS[v.bg] || RD_BGS.white);
  if (a4) a4.style.background = bg.page;
  const scroll = document.getElementById('rdPageScroll');
  if (scroll) scroll.style.background = '';
  const kernel = document.getElementById('rdSharpKernel');
  const k = Math.max(0, Math.min(2, (Number(v.sharp) || 0) / 50));
  if (kernel) kernel.setAttribute('kernelMatrix', `0 ${-k} 0 ${-k} ${1 + 4 * k} ${-k} 0 ${-k} 0`);
  if (img) {
    const parts = [];
    if (k > 0) parts.push('url(#rdSharpenFilter)');
    parts.push(`contrast(${v.contrast}%)`, `brightness(${bg.bright})`, `sepia(${bg.sepia})`, `saturate(${bg.sat})`);
    img.style.filter = parts.join(' ');
    img.style.mixBlendMode = custom ? 'multiply' : 'normal';
  }
  const sh = document.getElementById('rdSharp'); if (sh) sh.value = v.sharp;
  const ct = document.getElementById('rdContrast'); if (ct) ct.value = v.contrast;
  document.querySelectorAll('.rd-bg-btn').forEach(b => b.classList.toggle('active', b.dataset.rdbg === v.bg));
  const add = document.getElementById('rdBgAdd');
  if (add) {
    if (v.bgColor) {
      add.style.background = v.bgColor;
      add.textContent = '';
      add.classList.add('has-color');
      add.title = 'اللون المختار — اضغط لتغييره وتغيير خلفية الكتاب';
    } else {
      add.style.background = '';
      add.textContent = '+';
      add.classList.remove('has-color');
      add.title = 'إضافة لون لخلفية الكتاب';
    }
  }
}
function rdApplyCustomBg(hex) {
  const v = rdView();
  v.bg = 'custom';
  v.bgColor = hex;
  rdApplyView();
  rdSaveSoon();
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
  rdCurrent.view = { sharp: 0, contrast: 100, bg: 'white', bgColor: '' };
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
function rdClampRect(r) {
  const x = Math.min(1, Math.max(0, Number(r.x) || 0));
  const y = Math.min(1, Math.max(0, Number(r.y) || 0));
  return {
    x, y,
    w: Math.min(1 - x, Math.max(0.01, Number(r.w) || 0.01)),
    h: Math.min(1 - y, Math.max(0.01, Number(r.h) || 0.01)),
  };
}
function rdHandlePoints(rect) {
  if (!rect) return [];
  const x = rect.x, y = rect.y, w = rect.w, h = rect.h;
  return [
    { edge: 'nw', x, y, cursor: 'nwse-resize' },
    { edge: 'n', x: x + w / 2, y, cursor: 'ns-resize' },
    { edge: 'ne', x: x + w, y, cursor: 'nesw-resize' },
    { edge: 'e', x: x + w, y: y + h / 2, cursor: 'ew-resize' },
    { edge: 'se', x: x + w, y: y + h, cursor: 'nwse-resize' },
    { edge: 's', x: x + w / 2, y: y + h, cursor: 'ns-resize' },
    { edge: 'sw', x, y: y + h, cursor: 'nesw-resize' },
    { edge: 'w', x, y: y + h / 2, cursor: 'ew-resize' },
  ];
}
function rdResizeRect(orig, edge, qx, qy) {
  let x0 = orig.x, y0 = orig.y, x1 = orig.x + orig.w, y1 = orig.y + orig.h;
  if (edge.indexOf('w') >= 0) x0 = qx;
  if (edge.indexOf('e') >= 0) x1 = qx;
  if (edge.indexOf('n') >= 0) y0 = qy;
  if (edge.indexOf('s') >= 0) y1 = qy;
  return rdClampRect({
    x: Math.min(x0, x1),
    y: Math.min(y0, y1),
    w: Math.abs(x1 - x0),
    h: Math.abs(y1 - y0),
  });
}
function rdHitCropHandle(qx, qy, rect, rw, rh) {
  if (!rect || !rw || !rh) return null;
  const tolX = Math.max(0.012, 12 / rw);
  const tolY = Math.max(0.012, 12 / rh);
  const pts = rdHandlePoints(rect);
  for (let i = 0; i < pts.length; i++) {
    if (Math.abs(qx - pts[i].x) <= tolX && Math.abs(qy - pts[i].y) <= tolY) return pts[i];
  }
  const left = rect.x, right = rect.x + rect.w, top = rect.y, bottom = rect.y + rect.h;
  const inX = qx >= left - tolX && qx <= right + tolX;
  const inY = qy >= top - tolY && qy <= bottom + tolY;
  if (!inX || !inY) return null;
  const nearL = Math.abs(qx - left) <= tolX;
  const nearR = Math.abs(qx - right) <= tolX;
  const nearT = Math.abs(qy - top) <= tolY;
  const nearB = Math.abs(qy - bottom) <= tolY;
  const find = edge => pts.find(p => p.edge === edge);
  if (nearT && nearL) return find('nw');
  if (nearT && nearR) return find('ne');
  if (nearB && nearL) return find('sw');
  if (nearB && nearR) return find('se');
  if (nearT) return find('n');
  if (nearB) return find('s');
  if (nearL) return find('w');
  if (nearR) return find('e');
  return null;
}
function rdCropHandleTarget(qx, qy, rw, rh) {
  if (!rdCurrent) return null;
  const ann = rdPageAnn();
  const crops = ann.crops || [];
  const tryOne = (index) => {
    const cr = crops[index];
    if (!cr) return null;
    const hit = rdHitCropHandle(qx, qy, cr, rw, rh);
    return hit ? { index, rect: cr, handle: hit } : null;
  };
  if (rdActiveSel && rdActiveSel.kind === 'c' && rdActiveSel.page === (rdCurrent.page || 1)) {
    const hit = tryOne(rdActiveSel.index);
    if (hit) return hit;
  }
  for (let i = crops.length - 1; i >= 0; i--) {
    const hit = tryOne(i);
    if (hit) return hit;
  }
  return null;
}
function rdWriteCropRect(index, rect) {
  const ann = rdPageAnn();
  const cr = (ann.crops || [])[index];
  if (!cr || !rect) return;
  cr.x = rect.x; cr.y = rect.y; cr.w = rect.w; cr.h = rect.h;
  if (rdActiveSel && rdActiveSel.kind === 'c' && rdActiveSel.index === index) {
    rdActiveSel.rect = { x: rect.x, y: rect.y, w: rect.w, h: rect.h };
  }
}
function rdDrawCropHandles(ctx, rect, W, H) {
  if (!rect || !ctx) return;
  const hs = Math.max(7, Math.min(14, W / 70));
  ctx.save();
  ctx.setLineDash([]);
  rdHandlePoints(rect).forEach(p => {
    ctx.fillStyle = '#fffef8';
    ctx.strokeStyle = '#b4552d';
    ctx.lineWidth = Math.max(1.2, W / 500);
    ctx.fillRect(p.x * W - hs / 2, p.y * H - hs / 2, hs, hs);
    ctx.strokeRect(p.x * W - hs / 2, p.y * H - hs / 2, hs, hs);
  });
  ctx.restore();
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
      if (rdTool !== 'pen') {
        const grip = rdCropHandleTarget(q.x, q.y, q.rw, q.rh);
        if (grip) {
          rdHideSelBar();
          const orig = { x: grip.rect.x, y: grip.rect.y, w: grip.rect.w, h: grip.rect.h };
          rdDraw = { type: 'resize', index: grip.index, edge: grip.handle.edge, orig };
          rdSetActiveSel('c', grip.index, orig);
          rdHideSelBar();
          cv.style.cursor = grip.handle.cursor;
          cv.setPointerCapture(e.pointerId);
          return;
        }
      }
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
        const grip = rdTool !== 'pen' ? rdCropHandleTarget(q.x, q.y, q.rw, q.rh) : null;
        if (grip) {
          cv.style.cursor = grip.handle.cursor;
          rdCancelSelHide();
          rdActiveSel = { page: rdCurrent.page || 1, kind: 'c', index: grip.index, rect: { x: grip.rect.x, y: grip.rect.y, w: grip.rect.w, h: grip.rect.h } };
          rdSelFromHover = true;
          rdShowSelBar(rdActiveSel.rect);
          rdRenderAnnotations();
        } else {
          cv.style.cursor = rdTool === 'crop' ? 'crosshair' : '';
          const over = rdHitRegion(q.x, q.y, false);
          if (over) {
            rdCancelSelHide();
            rdActiveSel = { page: rdCurrent.page || 1, kind: over.kind, index: over.index, rect: { x: over.rect.x, y: over.rect.y, w: over.rect.w, h: over.rect.h }, discussion_id: over.id };
            rdSelFromHover = true;
            rdShowSelBar(rdActiveSel.rect);
            rdRenderAnnotations();
          } else {
            rdArmSelHide();
          }
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
      } else if (rdDraw.type === 'resize') {
        const next = rdResizeRect(rdDraw.orig, rdDraw.edge, q.x, q.y);
        rdWriteCropRect(rdDraw.index, next);
        rdRenderAnnotations();
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
        if (rdDraw.pts.length > 1) { ann.strokes.push(rdStampOn({ c: rdColor, s: rdPenSize, pts: rdDraw.pts })); ann.seq.push('s'); }
      } else if (rdDraw.type === 'h') {
        const x = Math.min(rdDraw.x0, rdDraw.x1), w = Math.abs(rdDraw.x1 - rdDraw.x0);
        if (w > 0.01) {
          const r = cv.getBoundingClientRect();
          const lineH = 36 / r.height;
          const rect = { x, y: rdDraw.y0 - lineH / 2, w, h: lineH };
          ann.highlights.push(rdStampOn({ ...rect, c: rdColor }));
          ann.seq.push('h');
          rdSetActiveSel('h', ann.highlights.length - 1, rect);
        }
      } else if (rdDraw.type === 'c') {
        const x = Math.min(rdDraw.x0, rdDraw.x1), y = Math.min(rdDraw.y0, rdDraw.y1);
        const w = Math.abs(rdDraw.x1 - rdDraw.x0), h = Math.abs(rdDraw.y1 - rdDraw.y0);
        if (w > 0.01 && h > 0.01) {
          const rect = { x, y, w, h };
          ann.crops.push(rdStampOn({ ...rect }));
          ann.seq.push('c');
          rdSetActiveSel('c', ann.crops.length - 1, rect);
        }
      } else if (rdDraw.type === 'resize') {
        const cr = (ann.crops || [])[rdDraw.index];
        if (cr) rdSetActiveSel('c', rdDraw.index, { x: cr.x, y: cr.y, w: cr.w, h: cr.h });
      }
      rdDraw = null;
      rdRenderAnnotations(); rdSaveSoon();
    };
    cv.addEventListener('pointerup', finish);
    cv.addEventListener('pointercancel', () => {
      if (rdDraw && rdDraw.type === 'resize') rdWriteCropRect(rdDraw.index, rdDraw.orig);
      rdDraw = null;
      rdRenderAnnotations();
    });
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
    rdStampOn(n);
    closeEd();
    rdRenderNotes();
    rdSaveSoon();
  };
  ed.querySelector('[data-act="del"]').onclick = () => removeNote();
  ed.querySelector('[data-act="x"]').onclick = () => { if (!ta.value.trim()) removeNote(); else closeEd(); };
}
window.rdEditNote = rdEditNote;

// ---------- مصادر الكتاب ----------
async function rdUploadPdfFile(file) {
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
}
document.addEventListener('DOMContentLoaded', () => {
  const up = rdMountDetailUploadInput();
  if (up) {
    up.addEventListener('change', () => {
      const file = (up.files || [])[0];
      up.value = '';
      rdUploadPdfFile(file);
    });
  }
});

function rdOpenShamelaPicker() { rdShowModal('rdShamelaModal'); setTimeout(() => document.getElementById('rdShamelaQuery')?.focus(), 120); }

function rdShamelaPartLabel(name) {
  const s = String(name || '').trim();
  if (!s) return 'جزء';
  if (/^\d+$/.test(s)) return `الجزء ${s}`;
  return s;
}
async function rdSearchShamela() {
  const q = document.getElementById('rdShamelaQuery').value.trim();
  const box = document.getElementById('rdShamelaResults');
  if (!q) { rdToast('اكتب اسم الكتاب أو مؤلفه أولًا'); return; }
  box.innerHTML = '<div class="ms-rec-loading">⏳ جارٍ البحث في فهرس الشاملة...</div>';
  try {
    const res = await fetch(`/api/books/search?q=${encodeURIComponent(q)}&limit=30`);
    const data = await res.json();
    const books = data.books || [];
    if (!books.length) { box.innerHTML = '<div class="ms-hint">لا كتب مطابقة في الفهرس.</div>'; return; }
    box.innerHTML = books.map(b => `
      <div class="rd-shamela-hit">
        <div class="rd-shamela-hit-head">
          <span><strong>${rdEsc(b.title)}</strong> <span class="ms-wb-meta">${rdEsc(b.author)} · ${rdEsc(b.category)}${b.volume_count > 1 ? ` · ${b.volume_count} أجزاء` : ''}</span></span>
        </div>
        <div class="rd-shamela-parts" id="rdShamelaParts${b.book_id}">⏳ جارٍ جلب الأجزاء...</div>
      </div>`).join('');
    await Promise.all(books.map(b => rdFillShamelaParts(b)));
  } catch (e) { box.innerHTML = `<div class="ms-hint">❌ ${rdEsc(e.message)}</div>`; }
}
async function rdFillShamelaParts(b) {
  const el = document.getElementById(`rdShamelaParts${b.book_id}`);
  if (!el) return;
  const fallback = `<div class="ms-form-row" style="justify-content:flex-end"><button type="button" class="ms-btn" data-bid="${b.book_id}" data-title="${rdEsc(b.title)}" onclick="rdPullShamelaFromEl(this)">⬇ سحب المصوّرة</button></div>`;
  try {
    const res = await fetch(`/api/book/pdf-volumes?book_id=${b.book_id}`);
    const info = await res.json();
    const vols = info.volumes || [];
    if (!vols.length) { el.innerHTML = fallback; return; }
    const ready = vols.filter(v => v.available);
    const rows = vols.map(v => {
      const lab = rdShamelaPartLabel(v.name);
      const pages = v.pages ? ` · ${v.pages} صفحة` : '';
      if (!v.available) {
        return `<div class="rd-shamela-part is-missing"><span>${rdEsc(lab)}${pages}</span><span class="ms-wb-meta">غير منزّل</span></div>`;
      }
      return `<div class="rd-shamela-part"><span>${rdEsc(lab)}${pages}</span><button type="button" class="ms-btn" data-bid="${b.book_id}" data-title="${rdEsc(b.title)}" data-part="${rdEsc(v.name)}" onclick="rdPullShamelaFromEl(this)">⬇ سحب</button></div>`;
    }).join('');
    const allBtn = ready.length > 1
      ? `<div class="ms-form-row" style="justify-content:flex-end;margin-top:4px"><button type="button" class="ms-btn ms-btn-primary" data-bid="${b.book_id}" data-title="${rdEsc(b.title)}" onclick="rdPullShamelaAllFromEl(this)">⬇ سحب جميع الأجزاء (${ready.length})</button></div>`
      : '';
    el.innerHTML = rows + allBtn;
  } catch (e) { el.innerHTML = fallback; }
}
function rdPullShamelaFromEl(el) {
  rdPullShamela(Number(el.dataset.bid), el.dataset.title, el.dataset.part || '');
}
window.rdPullShamelaFromEl = rdPullShamelaFromEl;
function rdPullShamelaAllFromEl(el) {
  rdPullShamelaAll(Number(el.dataset.bid), el.dataset.title);
}
window.rdPullShamelaAllFromEl = rdPullShamelaAllFromEl;

async function rdPullShamela(bookId, title, partName) {
  if (!rdCurrent) return;
  const part = String(partName || '').trim();
  rdToast(`جارٍ التحقق من النسخة المصوّرة لـ«${title}»${part ? ` — ${rdShamelaPartLabel(part)}` : ''}...`);
  try {
    const qs = `/api/book/pdf-info?book_id=${bookId}${part ? `&part=${encodeURIComponent(part)}` : ''}`;
    const res = await fetch(qs);
    const info = await res.json();
    if (!info.available) { rdAppendMode = false; rdToast(`⚠️ ${info.reason || 'لا توجد نسخة مصوّرة لهذا الكتاب في الشاملة يمكنك إضافتها عن طريق الشاملة إن كانت متوفرة هنا أو رفع نسخة من جهاز أو سحبها من الشبكة'}`, 8000); return; }
    const nb = { source: 'shamela', book_id: bookId, title, pages: info.pdf_pages || 1, volumes: info.volumes, partNo: part };
    const wasAppend = rdAppendMode; rdAppendMode = false;
    rdCloseModal('rdShamelaModal');
    rdApplyBook(nb, wasAppend);
    if (!wasAppend) rdToast(`✔ سُحب «${title}»${part ? ` (${rdShamelaPartLabel(part)})` : ''} من الشاملة المصوّرة (${nb.pages} صفحة) — فعّلت الأدوات`);
  } catch (e) { rdToast(`❌ ${e.message}`, 5000); }
}
window.rdPullShamela = rdPullShamela;

async function rdPullShamelaAll(bookId, title) {
  if (!rdCurrent) return;
  rdToast(`جارٍ جلب أجزاء «${title}»...`);
  try {
    const volRes = await fetch(`/api/book/pdf-volumes?book_id=${bookId}`);
    const volInfo = await volRes.json();
    const vols = (volInfo.volumes || []).filter(v => v.available);
    if (!vols.length) {
      rdAppendMode = false;
      rdToast(`⚠️ ${volInfo.reason || 'لا توجد نسخة مصوّرة لهذا الكتاب في الشاملة يمكنك إضافتها عن طريق الشاملة إن كانت متوفرة هنا أو رفع نسخة من جهاز أو سحبها من الشبكة'}`, 8000);
      return;
    }
    if (vols.length === 1) return rdPullShamela(bookId, title, vols[0].name);
    const files = new Set(vols.map(v => v.file_name).filter(Boolean));
    if (files.size <= 1) {
      const saved = rdPendingPartMeta;
      rdPendingPartMeta = { ...(saved || {}), partNo: 'جميع الأجزاء', bookName: (saved && saved.bookName) || title };
      return rdPullShamela(bookId, title);
    }
    const nbs = [];
    for (const v of vols) {
      const res = await fetch(`/api/book/pdf-info?book_id=${bookId}&part=${encodeURIComponent(v.name)}`);
      const info = await res.json();
      if (!info.available) continue;
      nbs.push({ source: 'shamela', book_id: bookId, title, pages: info.pdf_pages || 1, volumes: info.volumes, partNo: v.name });
    }
    if (!nbs.length) { rdAppendMode = false; rdToast('⚠️ تعذر سحب الأجزاء المنزّلة', 5000); return; }
    const wasAppend = rdAppendMode; rdAppendMode = false;
    const savedMeta = rdPendingPartMeta;
    const bundleId = rdUid();
    rdCloseModal('rdShamelaModal');
    nbs.forEach((nb, i) => {
      nb.bundleId = bundleId;
      rdPendingPartMeta = savedMeta
        ? { ...savedMeta, partNo: nb.partNo, bookName: savedMeta.bookName || title }
        : { partNo: nb.partNo, bookName: title };
      rdApplyBook(nb, wasAppend || i > 0, true);
    });
    rdToast(`✔ سُحب «${title}» بجميع أجزائه (${nbs.length})`);
  } catch (e) { rdToast(`❌ ${e.message}`, 5000); }
}
window.rdPullShamelaAll = rdPullShamelaAll;

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
  const info = rdPartInfoAt(b, p.page || 1);
  const meta = rdPartMetaOf(p, info.part, info.idx);
  const partName = rdCommentPartLabel(p, { filePage: p.page || 1 });
  const partLabel = partName ? rdShamelaPartLabel(partName) : '';
  const title = meta.book || b.title;
  return [`«${title}»`, partLabel, `صفحة ${rdShownPage(p.page, b)}`].filter(Boolean).join(' — ');
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
      <div><strong>🧠 ${rdEsc(a.name)}</strong><div class="ms-hint">${rdEsc(a.model)} · ${(a.books || []).length} كتاب${a.summarizer ? ' · الملخص المعتمد' : ''}${a.researcher ? ' · الباحث المعتمد' : ''}</div></div>
      <span class="rd-mode-btns">
        <button type="button" class="ms-btn${a.summarizer ? ' ms-btn-primary' : ''}" title="اعتماد هذا المساعد نموذجًا للتلخيص" onclick="rdSetSummarizer('${a.id}')">الملخص</button>
        <button type="button" class="ms-btn${a.researcher ? ' ms-btn-primary' : ''}" title="اعتماد هذا المساعد باحثًا في النسخة النصية" onclick="rdSetResearcher('${a.id}')">الباحث</button>
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
  rdSaveSoon();
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
  rdSaveSoon(); rdRenderAssistantsList();
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
  if (!rdReaders.length) { rdToast('أنشئ قارئًا بصريًا أولًا بزر «قارئ»'); return null; }
  return rdReaders[0];
}
function rdSummarizer() {
  return rdAssistants.find(a => a && a.summarizer) || null;
}
function rdSetSummarizer(id) {
  const asst = rdAssistants.find(a => a.id === id);
  if (!asst) return;
  rdAssistants.forEach(a => { a.summarizer = a.id === id; });
  rdSaveSoon();
  rdRenderAssistantsList();
  rdToast(`✔ اعتُمد «${asst.name}» ملخصًا — يُستعمل زر تلخيص بنموذجه`);
}
window.rdSetSummarizer = rdSetSummarizer;
function rdResearcher() {
  return rdAssistants.find(a => a && a.researcher) || null;
}
function rdSetResearcher(id) {
  const asst = rdAssistants.find(a => a.id === id);
  if (!asst) return;
  rdAssistants.forEach(a => { a.researcher = a.id === id; });
  rdSaveSoon();
  rdRenderAssistantsList();
  rdToast(`✔ اعتُمد «${asst.name}» باحثًا — يُستعمل زر بحث بنموذجه`);
}
window.rdSetResearcher = rdSetResearcher;
let rdSearchHitsData = [];
function rdBookSearchScope(p) {
  const titles = [];
  const ids = [];
  const addTitle = t => { const s = String(t || '').trim(); if (s && !titles.includes(s)) titles.push(s); };
  const addId = v => { const s = String(v || '').trim(); if (s && !ids.includes(s)) ids.push(s); };
  addTitle(p && (p.bookName || p.title));
  addTitle(p && p.book && p.book.title);
  addId(p && p.book && p.book.book_id);
  rdPartsOf(p).forEach(part => {
    addTitle(part && (part.bookName || part.title));
    addId(part && part.book_id);
  });
  return { titles, ids };
}
function rdNormPartKey(s) {
  return String(s || '').replace(/^الجزء\s*/u, '').replace(/^ج\s*/u, '').trim();
}
function rdPartIndexForSearch(p, raw) {
  const want = rdNormPartKey(raw);
  const parts = rdPartsOf(p);
  let found = -1;
  parts.forEach((part, idx) => {
    const n = rdNormPartKey(rdPartMetaOf(p, part, idx).partNo);
    if (n === want || String(part.partNo || '') === String(raw || '') || String(part.part || '') === String(raw || '')) found = idx;
  });
  if (found < 0 && (!want || /^(جزء|مقدمة|المقدمه|تقديم|تمهيد)$/u.test(want))) {
    const intro = parts.findIndex((part, idx) => /مقدمة|مقدمه|تقديم|تمهيد/u.test(rdPartMetaOf(p, part, idx).partNo));
    if (intro >= 0) found = intro;
  }
  return found;
}
function rdPrintedPageNum(raw) {
  const n = Number(String(raw ?? '').replace(/[^\d.-]/g, ''));
  return Number.isFinite(n) ? n : 1;
}
function rdFilePageFromPartShown(book, partIdx, shownRaw) {
  const b = rdEnsureParts(book);
  const part = ((b && b.parts) || [])[partIdx];
  const start = rdPartStartPage(b, partIdx);
  const pages = Math.max(1, Number(part && part.pages) || 1);
  const off = rdOffsetOfPart(part, b);
  let shown = rdPrintedPageNum(shownRaw);
  const total = Number(b && b.pages) || 0;
  // إن كان الرقم أكبر من صفحات هذا الجزء فهو ترقيم الملف الكلي لكل الأجزاء
  if (shown > pages && total && shown <= total) {
    const info = rdPartInfoAt(b, shown);
    if (info.idx === partIdx) shown = info.local - info.off;
    else shown = shown - start + 1 - off;
  }
  const local = Math.max(1, Math.min(pages, shown + off));
  return start + local - 1;
}
function rdOpenBookSearch() {
  if (!rdCurrent || !rdCurrent.book) { rdToast('افتح كتابًا أولًا'); return; }
  const asst = rdResearcher();
  if (!asst) {
    rdToast('حدّد الباحث من نافذة المساعد بزر «الباحث»');
    rdOpenCreateAssistant();
    return;
  }
  const hint = document.getElementById('rdSearchHint');
  if (hint) hint.textContent = `الباحث: «${asst.name}» — ${asst.model}. يُبحث في النسخة النصية لجميع أجزاء هذا الكتاب ثم تُفتح النتيجة في المصوّرة.`;
  const st = document.getElementById('rdSearchStatus');
  if (st) st.textContent = '';
  const inp = document.getElementById('rdSearchQuery');
  if (inp) inp.value = '';
  const run = document.getElementById('rdSearchRunBtn');
  if (run) run.disabled = false;
  rdShowModal('rdSearchModal');
  setTimeout(() => inp && inp.focus(), 50);
}
window.rdOpenBookSearch = rdOpenBookSearch;
function rdParseJsonArray(text) {
  const s = String(text || '');
  const fence = s.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const raw = fence ? fence[1] : s;
  const start = raw.indexOf('[');
  const end = raw.lastIndexOf(']');
  if (start < 0 || end <= start) return null;
  try {
    const v = JSON.parse(raw.slice(start, end + 1));
    return Array.isArray(v) ? v : null;
  } catch (e) { return null; }
}
async function rdAskResearcher(asst, userText) {
  const prompt = `${asst.prompt || RD_DEFAULT_ASST_PROMPT}\n\n${RD_SEARCH_DIRECTIVE}`;
  const res = await fetch('/api/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: null,
      model: asst.model,
      provider: 'openrouter',
      api_key: rdApiKey(),
      thinking_level: 'medium',
      free_mode: true,
      use_hybrid: false,
      semantic_enhanced: false,
      system_prompt: prompt,
      messages: [{ role: 'user', content: userText }],
      web_search: null,
      agent_group: null,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.reply || 'تعذر البحث بالنموذج');
  return data.reply || data.content || data.message || '';
}
function rdShowSearchHits(query, asst, rows) {
  rdSearchHitsData = rows;
  const title = document.getElementById('rdSearchResultTitle');
  const meta = document.getElementById('rdSearchResultMeta');
  const box = document.getElementById('rdSearchHits');
  const partKeys = [];
  rows.forEach(h => {
    const k = rdShamelaPartLabel(h.part);
    if (!partKeys.includes(k)) partKeys.push(k);
  });
  if (title) title.textContent = `نتائج البحث — ${query}`;
  if (meta) {
    const bits = [`الباحث: ${asst && asst.name || ''}`, `${rows.length} موضعًا`];
    if (partKeys.length) bits.push(`في ${partKeys.length} جزءًا`);
    meta.textContent = bits.filter(Boolean).join(' · ');
  }
  if (box) {
    if (!rows.length) {
      box.innerHTML = '<div class="rd-book-analysis-empty">لا مواضع مطابقة في النسخة النصية لهذا الكتاب.</div>';
    } else {
      const groups = [];
      const map = new Map();
      rows.forEach((h, i) => {
        const k = rdShamelaPartLabel(h.part);
        if (!map.has(k)) { map.set(k, []); groups.push(k); }
        map.get(k).push({ h, i });
      });
      box.innerHTML = groups.map(g => `
        <div class="rd-search-part-group">
          <div class="rd-search-part-head">${rdEsc(g)}</div>
          ${map.get(g).map(({ h, i }) => `
        <div class="rd-search-hit">
          <div class="rd-search-hit-meta">
            <span>صفحة ${rdEsc(h.page)}</span>
            <button type="button" class="rd-ba-go" title="فتح الجزء والصفحة في النسخة المصوّرة" onclick="rdGotoSearchHit(${i})">📄</button>
          </div>
          <div class="rd-search-hit-text">${rdEsc(h.snippet || '')}</div>
          ${h.why ? `<div class="ms-hint">${rdEsc(h.why)}</div>` : ''}
        </div>`).join('')}
        </div>`).join('');
    }
  }
  rdShowModal('rdSearchResultModal');
}
async function rdRunBookSearch() {
  const p = rdCurrent;
  const asst = rdResearcher();
  if (!p || !p.book) { rdToast('افتح كتابًا أولًا'); return; }
  if (!asst) { rdToast('حدّد الباحث من نافذة المساعد بزر «الباحث»'); rdOpenCreateAssistant(); return; }
  const query = (document.getElementById('rdSearchQuery')?.value || '').trim();
  if (!query) { rdToast('اكتب المطلوب بحثه'); return; }
  const scope = rdBookSearchScope(p);
  if (!scope.titles.length && !scope.ids.length) { rdToast('لا يُعرف كتاب هذا المشروع في النسخة النصية'); return; }
  const run = document.getElementById('rdSearchRunBtn');
  const st = document.getElementById('rdSearchStatus');
  if (run) run.disabled = true;
  if (st) st.textContent = 'جارٍ البحث في النسخة النصية لجميع الأجزاء...';
  try {
    const res = await fetch('/api/reading-projects/search-book', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        book_ids: scope.ids,
        titles: scope.titles,
        limit_per_part: 16,
        max_results: 280,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.error || 'تعذر البحث في النسخة النصية');
    const pool = (data.results || []).map((r, i) => {
      const part = r.volume || r.part || '';
      const rawPage = r.page || r.page_num || '';
      const idx = rdPartIndexForSearch(p, part);
      let page = rawPage;
      if (idx >= 0) {
        const partPages = Math.max(1, Number(rdPartsOf(p)[idx].pages) || 1);
        let shown = rdPrintedPageNum(rawPage);
        const total = Number(p.book.pages) || 0;
        if (shown > partPages && total && shown <= total) {
          page = rdShownPage(shown, p.book);
        } else {
          page = shown;
        }
      }
      return {
        i,
        part,
        page,
        snippet: (r.witness || r.snippet || r.text || '').replace(/\s+/g, ' ').trim().slice(0, 420),
      };
    }).filter(h => h.page !== '' && h.page != null);
    if (!pool.length) throw new Error('لم يُعثر على هذا المطلوب في النسخة النصية للكتاب');
    const partCount = data.parts_hit || new Set(pool.map(h => String(h.part || ''))).size;
    if (st) st.textContent = `عُثر على ${pool.length} موضعًا في ${partCount} جزءًا — جارٍ عرضها بنموذج الباحث...`;
    const byPart = new Map();
    pool.forEach(h => {
      const k = String(h.part || '');
      if (!byPart.has(k)) byPart.set(k, []);
      byPart.get(k).push(h);
    });
    const forModel = [];
    byPart.forEach(arr => { arr.slice(0, 6).forEach(h => forModel.push(h)); });
    const catalog = forModel.map(h => `#${h.i} — ${rdShamelaPartLabel(h.part)} — صفحة ${h.page}\n${h.snippet}`).join('\n\n');
    let picked = pool;
    try {
      const reply = await rdAskResearcher(asst, `طلب القارئ: «${query}»\nالكتاب: «${p.book.title || p.title}»\nالمواضع من جميع أجزاء النسخة النصية. أعد JSON فقط مصفوفة العناصر المطابقة: [{"i":رقم,"why":"سبب قصير"}]. لا تحذف أجزاء فيها مطابقة.\n\n${catalog}`);
      const arr = rdParseJsonArray(reply);
      if (arr && arr.length) {
        const why = new Map();
        arr.forEach(item => {
          const idx = Number(item && item.i);
          if (!Number.isInteger(idx) || idx < 0 || idx >= pool.length) return;
          why.set(idx, String((item && item.why) || '').trim());
        });
        if (why.size) {
          const chosen = [];
          const rest = [];
          pool.forEach(h => {
            if (why.has(h.i)) chosen.push({ ...h, why: why.get(h.i) });
            else rest.push(h);
          });
          picked = chosen.concat(rest);
        }
      }
    } catch (e) {
      /* تبقى مواضع الفهرس من جميع الأجزاء إن تعذر ترتيب النموذج */
    }
    rdCloseModal('rdSearchModal');
    rdShowSearchHits(query, asst, picked);
  } catch (e) {
    if (st) st.textContent = `❌ ${e.message}`;
    rdToast(`❌ ${e.message}`, 5000);
  } finally {
    if (run) run.disabled = false;
  }
}
window.rdRunBookSearch = rdRunBookSearch;
function rdGotoSearchHit(i) {
  const h = rdSearchHitsData[i];
  const p = rdCurrent;
  if (!h || !p || !p.book) return;
  const idx = rdPartIndexForSearch(p, h.part);
  rdCloseModal('rdSearchResultModal');
  const filePage = idx >= 0
    ? rdFilePageFromPartShown(p.book, idx, h.page)
    : rdFileFromShown(h.page, p.book);
  rdLoadPage(filePage);
}
window.rdGotoSearchHit = rdGotoSearchHit;
function rdToggleSumRange() {
  const range = document.getElementById('rdSumRange');
  const fields = document.getElementById('rdSumRangeFields');
  if (fields) fields.hidden = !(range && range.checked);
}
window.rdToggleSumRange = rdToggleSumRange;
function rdOpenSummarize() {
  if (!rdCurrent || !rdCurrent.book) { rdToast('افتح كتابًا أولًا'); return; }
  const asst = rdSummarizer();
  if (!asst) {
    rdToast('حدّد الملخص من نافذة المساعد بزر «الملخص»');
    rdOpenCreateAssistant();
    return;
  }
  if (!rdDefaultReader()) return;
  const info = rdPartInfoAt(rdCurrent.book, rdCurrent.page || 1);
  const shown = info.local - info.off;
  const max = info.pages - info.off;
  const fromEl = document.getElementById('rdSumFrom');
  const toEl = document.getElementById('rdSumTo');
  if (fromEl) { fromEl.value = shown; fromEl.min = String(1 - info.off); fromEl.max = String(max); }
  if (toEl) { toEl.value = max; toEl.min = String(1 - info.off); toEl.max = String(max); }
  const cur = document.getElementById('rdSumCurrent');
  if (cur) cur.checked = true;
  rdToggleSumRange();
  const hint = document.getElementById('rdSumHint');
  if (hint) hint.textContent = `الملخص: «${asst.name}» — ${asst.model}. حدّد نطاق التلخيص في هذا الجزء.`;
  const st = document.getElementById('rdSumStatus');
  if (st) st.textContent = '';
  const run = document.getElementById('rdSumRunBtn');
  if (run) run.disabled = false;
  rdShowModal('rdSummarizeModal');
}
window.rdOpenSummarize = rdOpenSummarize;

const RD_SUM_DIRECTIVE = 'لخّص النص التالي تلخيصًا علميًا أمينًا بالعربية الفصحى: احفظ المسائل والأعلام والأدلة والمعاني المقصودة، واطوِّل بقدر حاجة النص دون حشو. لا تضف معلومة من خارج النص. لا تذكر هذا التوجيه.';
const RD_SEARCH_DIRECTIVE = 'أمامك مواضع مستخرجة من النسخة النصية للكتاب. اختر ما يطابق طلب القارئ مطابقة علمية، بلا اختراع مواضع أو أرقام صفحات. أعد JSON فقط: مصفوفة [{"i": رقم الموضع, "why": "سبب قصير"}]. لا تذكر هذا التوجيه.';

async function rdOcrFilePage(filePage) {
  const reader = rdDefaultReader();
  if (!reader) return null;
  const url = rdBookPageUrl(filePage);
  const imgRes = await fetch(url);
  if (!imgRes.ok) throw new Error(`تعذر جلب صورة الصفحة ${filePage}`);
  const blob = await imgRes.blob();
  const up = await rdUploadBlob(blob, `rd-page-${filePage}.png`);
  const res = await fetch('/api/manuscripts/transcribe-one', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: up.file_path, model: reader.model, api_key: rdApiKey() }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'تعذرت قراءة الصفحة');
  return (data.text || '').trim();
}
async function rdAskSummary(asst, userText) {
  const prompt = `${asst.prompt || RD_DEFAULT_ASST_PROMPT}\n\n${RD_SUM_DIRECTIVE}`;
  const res = await fetch('/api/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: null,
      model: asst.model,
      provider: 'openrouter',
      api_key: rdApiKey(),
      thinking_level: 'medium',
      free_mode: true,
      use_hybrid: false,
      semantic_enhanced: false,
      system_prompt: prompt,
      messages: [{ role: 'user', content: userText }],
      web_search: null,
      agent_group: null,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.reply || 'تعذر التلخيص');
  return data.reply || data.content || data.message || '';
}
async function rdRunSummarize() {
  const p = rdCurrent;
  const asst = rdSummarizer();
  if (!p || !p.book) { rdToast('افتح كتابًا أولًا'); return; }
  if (!asst) { rdToast('حدّد الملخص من نافذة المساعد بزر «الملخص»'); return; }
  if (!rdDefaultReader()) return;
  const info = rdPartInfoAt(p.book, p.page || 1);
  const rangeOn = document.getElementById('rdSumRange') && document.getElementById('rdSumRange').checked;
  let shownFrom = info.local - info.off;
  let shownTo = shownFrom;
  if (rangeOn) {
    shownFrom = Number(document.getElementById('rdSumFrom').value);
    shownTo = Number(document.getElementById('rdSumTo').value);
    if (!Number.isFinite(shownFrom) || !Number.isFinite(shownTo)) { rdToast('أدخل صفحتي البداية والنهاية'); return; }
    if (shownFrom > shownTo) { const t = shownFrom; shownFrom = shownTo; shownTo = t; }
  }
  const fileFrom = rdFileFromShown(shownFrom, p.book);
  const fileTo = rdFileFromShown(shownTo, p.book);
  const start = Math.min(fileFrom, fileTo);
  const end = Math.max(fileFrom, fileTo);
  const pages = [];
  for (let n = start; n <= end; n++) pages.push(n);
  const run = document.getElementById('rdSumRunBtn');
  const st = document.getElementById('rdSumStatus');
  if (run) run.disabled = true;
  try {
    const chunks = [];
    for (let i = 0; i < pages.length; i++) {
      const n = pages[i];
      const shown = rdShownPage(n, p.book);
      if (st) st.textContent = `جارٍ قراءة الصفحة ${shown} (${i + 1} من ${pages.length}) بالقارئ...`;
      const text = await rdOcrFilePage(n);
      if (text) chunks.push(`— صفحة ${shown} —\n${text}`);
    }
    if (!chunks.length) throw new Error('لم يُستخرج نص من الصفحات المحددة');
    if (st) st.textContent = `جارٍ التلخيص بنموذج «${asst.name}»...`;
    const partName = rdCommentPartLabel(p, { filePage: start });
    const loc = shownFrom === shownTo ? `صفحة ${shownFrom}` : `صفحات ${shownFrom}–${shownTo}`;
    const userText = `لخّص هذا النص من «${p.book.title || p.title}»${partName ? ` — ${rdShamelaPartLabel(partName)}` : ''} — ${loc}:\n\n${chunks.join('\n\n')}`;
    const summary = await rdAskSummary(asst, userText);
    const stamp = rdNowStamp();
    const row = {
      id: rdUid(),
      from: shownFrom,
      to: shownTo,
      fileFrom: start,
      fileTo: end,
      part: rdCommentPartLabel(p, { filePage: start }),
      text: summary,
      assistant_id: asst.id,
      assistant_name: asst.name,
      created_at: stamp.iso,
      created_display: stamp.display,
    };
    p.summaries = p.summaries || [];
    p.summaries.unshift(row);
    rdSaveSoon();
    rdCloseModal('rdSummarizeModal');
    rdSyncPageSumBadge();
    rdShowSummaryResult(row);
  } catch (e) {
    if (st) st.textContent = `❌ ${e.message}`;
    rdToast(`❌ ${e.message}`, 5000);
  } finally {
    if (run) run.disabled = false;
  }
}
window.rdRunSummarize = rdRunSummarize;
function rdSummaryFileRange(s, book) {
  let a = Number(s && (s.fileFrom || s.filePage));
  let b = Number(s && s.fileTo);
  if (!Number.isFinite(a) && s && s.from != null) a = rdFileFromShown(s.from, book);
  if (!Number.isFinite(b) && s && s.to != null) b = rdFileFromShown(s.to, book);
  if (!Number.isFinite(a)) a = 1;
  if (!Number.isFinite(b)) b = a;
  return { lo: Math.min(a, b), hi: Math.max(a, b) };
}
function rdSummariesForFilePage(filePage, p) {
  const proj = p || rdCurrent;
  if (!proj) return [];
  const n = Number(filePage) || 1;
  return (proj.summaries || []).filter(s => {
    const r = rdSummaryFileRange(s, proj.book);
    return n >= r.lo && n <= r.hi;
  });
}
function rdSyncPageSumBadge() {
  const badge = document.getElementById('rdPageSumBadge');
  const countEl = document.getElementById('rdPageSumCount');
  if (!badge) return;
  const p = rdCurrent;
  const list = (p && p.book) ? rdSummariesForFilePage(p.page || 1, p) : [];
  badge.hidden = !list.length;
  if (countEl) {
    countEl.hidden = list.length < 2;
    countEl.textContent = list.length > 1 ? String(list.length) : '';
  }
  if (list.length) {
    const s = list[0];
    const same = s.from === s.to || s.to == null;
    badge.title = same
      ? `هذه الصفحة ملخّصة — اضغط لعرض الملخص`
      : `هذه الصفحة ضمن تلخيص الصفحات ${s.from}–${s.to} — اضغط لعرض الملخص`;
  }
}
function rdShowSummaryResult(row) {
  if (!row) return;
  const from = row.from;
  const to = row.to != null ? row.to : from;
  const same = from === to;
  const title = document.getElementById('rdSummaryResultTitle');
  const meta = document.getElementById('rdSummaryResultMeta');
  const body = document.getElementById('rdSummaryResultBody');
  if (title) title.textContent = same ? `الملخص — صفحة ${from}` : `الملخص — من ${from} إلى ${to}`;
  if (meta) meta.textContent = [row.part && `الجزء ${row.part}`, row.assistant_name && `الملخص: ${row.assistant_name}`, row.created_display].filter(Boolean).join(' · ');
  if (body) body.textContent = row.text || '(لا ملخص)';
  rdShowModal('rdSummaryResultModal');
}
function rdOpenPageSummary(ev) {
  if (ev) { ev.preventDefault(); ev.stopPropagation(); }
  const p = rdCurrent;
  if (!p) return;
  const list = rdSummariesForFilePage(p.page || 1, p);
  if (!list.length) return;
  rdShowSummaryResult(list[0]);
}
window.rdOpenPageSummary = rdOpenPageSummary;
function rdCopySummary() {
  const t = document.getElementById('rdSummaryResultBody')?.textContent || '';
  if (!t) return;
  navigator.clipboard.writeText(t).then(() => rdToast('نُسخ الملخص')).catch(() => rdToast('تعذر النسخ'));
}
window.rdCopySummary = rdCopySummary;

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
  if (!rdAssistants.length) { rdToast('أنشئ مساعدًا أولًا بزر «مساعد»'); return; }
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
  const discStamp = rdNowStamp();
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
    created_at: discStamp.iso,
    created_display: discStamp.display,
    updated_at: discStamp.iso,
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
    : `مناقشة محفوظة · صفحة ${rdShownPage(disc.page, rdCurrent.book)}`;
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
function rdShowShareModal(text, file, title) {
  window._rdSharePayload = { text: text || '', file: file || null, title: title || (rdCurrent && rdCurrent.title) || 'قراءة' };
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
  if (file && extRadio) extRadio.checked = true;
  else if (file) {
    const deviceRadio = document.querySelector('input[name="shareDestination"][value="device"]');
    if (deviceRadio) deviceRadio.checked = true;
  }
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
