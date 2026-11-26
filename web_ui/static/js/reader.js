// =============================================================================
// منظومة المغني - قارئ الكتب التراثية الأصلي (reader.js)
// تقليب الصفحات، اختيار الأجزاء، إظهار/إخفاء التشكيل، وبطاقة الكتاب، ونقل التحديد للشات
// =============================================================================

let readerLoadToken = 0;

let readerState = {
  isOpen: false,
  relPath: '',
  bookTitle: '',
  author: '',
  deathYear: null,
  category: '',
  part: '',
  pageNum: 1,
  seq: 1,
  totalPages: 1,
  parts: [],
  rawBody: '',
  footnotes: '',
  betakaText: '',
  annalisticYear: null,
  isSurroundingView: false,
  showTashkeel: true,
  showBetaka: false,
  selectedText: '',
  prevPage: null,
  nextPage: null,
  highlightText: '',
  bookId: '',
  missing: false,
  pdfInfo: null,
  pdfPage: null,
  pdfOpen: false
};

let readerBooksCatalog = null;

// تشغيل مستمعات الأحداث
document.addEventListener('DOMContentLoaded', () => {
  // إغلاق عبر زر الهروب أو النقر خارج النافذة
  document.addEventListener('keydown', (e) => {
    if (!readerState.isOpen) return;
    if (e.key === 'Escape') {
      closeBookReader();
    } else if (e.key === 'ArrowLeft') {
      // في قراءة العربية: السهم لليسار ينقل للصفحة اللاحقة
      navigateReaderPage('next');
    } else if (e.key === 'ArrowRight') {
      // السهم لليمين ينقل للصفحة السابقة
      navigateReaderPage('prev');
    }
  });

  // النقر خارج البطاقة المنبثقة
  const modal = document.getElementById('bookReaderModal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeBookReader();
      }
    });
  }

  const filterInput = document.getElementById('readerBookFilterInput');
  const filterMenu = document.getElementById('readerBookFilterMenu');
  if (filterInput) {
    filterInput.addEventListener('input', () => renderReaderBookFilter(filterInput.value));
    filterInput.addEventListener('focus', () => renderReaderBookFilter(filterInput.value));
  }
  if (filterMenu) {
    filterMenu.addEventListener('click', (event) => {
      const item = event.target.closest('[data-reader-book]');
      if (!item) return;
      const book = (filterMenu._books || [])[Number(item.dataset.readerBook)];
      if (book) switchReaderBook(book);
    });
  }
  document.addEventListener('click', (event) => {
    if (!event.target.closest('#readerBookFilter')) closeReaderBookFilter();
  });
  const studyTip = document.getElementById('readerSelectionTooltip');
  if (studyTip && !studyTip.dataset.bound) {
    studyTip.dataset.bound = '1';
    studyTip.addEventListener('mousedown', (event) => event.preventDefault());
  }
  document.addEventListener('selectionchange', () => {
    if (readerState.isOpen) onReaderTextSelected();
  });
});

// فتح قارئ الكتاب من بطاقة نتيجة البحث الدلالي
function openBookReaderFromSearch(idx) {
  const item = window._lastSearchResults?.[idx];
  if (!item) return;

  openBookReader({
    rel_path: item.rel_path || '',
    book_id: item.book_id || '',
    book_title: item.book_title || item.book || item.title || '',
    part: item.volume || '',
    page_num: parseInt(item.page) || null,
    // الشاهد القابل للتحديد وحده، لا نص الصفحة (نص الصفحة مطلعها فيقع
    // التحديد في أعلى الصفحة دائمًا). الدلالي بلا شاهد فلا تحديد له
    highlight: window._lastSearchQuery || item.witness || ''
  });
}

// فتح نافذة القارئ وتنزيل الصفحة المستهدفة (يدعم كائن الإعدادات أو المعاملات المباشرة)
async function openBookReader(arg1, arg2, arg3, arg4, arg5) {
  let params = {};
  if (typeof arg1 === 'object' && arg1 !== null) {
    params = { ...arg1 };
  } else {
    params = {
      rel_path: arg1 || '',
      book_title: arg2 || '',
      part: arg3 !== undefined ? arg3 : '',
      page_num: arg4 ? parseInt(arg4, 10) : null,
      seq: arg5 ? parseInt(arg5, 10) : null
    };
  }

  const modal = document.getElementById('bookReaderModal');
  if (!modal) return;

  readerState.isOpen = true;
  readerState.bookId = params.book_id || '';
  readerState.relPath = params.rel_path || '';
  readerState.highlightText = params.highlight || '';
  readerState.showBetaka = false;
  readerState.isSurroundingView = false;
  clearReaderBookFilter();
  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden'; // قفل التمرير في الخلفية

  // تنظيف الحاوية وعرض مؤشر التحميل
  document.getElementById('readerPageBody').innerHTML = `
    <div style="text-align: center; padding: 60px 20px; color: var(--text-muted);">
      <div style="display: inline-block; width: 32px; height: 32px; border: 3px solid var(--border-subtle); border-top-color: var(--accent-clay); border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 12px;"></div>
      <p style="font-family: var(--font-amiri); font-size: 19px;">جارٍ استحضار صفحة الكتاب من الخزانة الأصلية...</p>
    </div>
  `;
  document.getElementById('readerFootnotes').style.display = 'none';
  document.getElementById('readerBetakaPanel').style.display = 'none';

  await loadReaderPage(params);
}

// استدعاء الصفحة من الخادم. كل فتح يلغي نتيجة الطلب السابق حتى لا تبقى نافذة عالقة.
async function loadReaderPage(params) {
  const myToken = ++readerLoadToken;
  try {
    const q = new URLSearchParams();
    if (params.rel_path) q.set('rel_path', params.rel_path);
    if (params.book_id) q.set('book_id', params.book_id);
    if (params.book_title) q.set('book_title', params.book_title);
    if (params.part !== undefined && params.part !== null) q.set('part', params.part);
    if (params.page_num) q.set('page_num', params.page_num);
    if (params.seq) q.set('seq', params.seq);
    if (params.highlight) q.set('highlight', String(params.highlight).slice(0, 180));
    if (params.strict) q.set('strict', '1');

    const res = await fetch(`/api/book/page?${q.toString()}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detail = Array.isArray(err.detail) ? 'تعذر تحميل الصفحة المطلوبة' : (err.detail || 'تعذر تحميل الصفحة المطلوبة');
      throw new Error(detail);
    }

    const data = await res.json();
    if (myToken !== readerLoadToken || !readerState.isOpen) return;

    readerState.relPath = data.rel_path;
    readerState.bookId = params.book_id || '';
    readerState.bookTitle = data.book_title;
    readerState.author = data.author;
    readerState.deathYear = data.death_year;
    readerState.category = data.category;
    readerState.part = data.part;
    readerState.pageNum = data.page_num;
    readerState.seq = data.seq;
    readerState.totalPages = data.total_pages;
    readerState.parts = data.parts || [];
    readerState.rawBody = data.body || '';
    readerState.footnotes = data.footnotes || '';
    readerState.betakaText = data.betaka_text || '';
    readerState.annalisticYear = data.annalistic_year || null;
    readerState.isSurroundingView = false;
    readerState.prevPage = data.prev_page;
    readerState.nextPage = data.next_page;
    readerState.missing = !!data.missing;

    const btnSurrounding = document.getElementById('btnToggleSurrounding');
    if (btnSurrounding) btnSurrounding.classList.remove('active');

    renderReaderView();

  } catch (err) {
    if (myToken !== readerLoadToken || !readerState.isOpen) return;
    if (params.strict) {
      readerState.missing = true;
      readerState.rawBody = '';
      readerState.footnotes = '';
      readerState.prevPage = null;
      readerState.nextPage = null;
      readerState.part = params.part || '';
      readerState.pageNum = params.page_num;
      renderReaderView();
      return;
    }
    console.error('Reader load error:', err);
    document.getElementById('readerPageBody').innerHTML = `
      <div style="text-align: center; padding: 40px; color: #c0392b;">
        <p style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">${escapeHtml(err.message || '')}</p>
        <div id="readerDiagBox" style="max-width: 620px; margin: 14px auto; text-align: right; font-size: 12.5px; color: var(--text-muted); background: var(--bg-surface-elevated, #f6f1e7); border: 1px solid var(--border-subtle); border-radius: 10px; padding: 12px 16px; display: none;"></div>
        <button class="btn-flat-secondary" onclick="closeBookReader()">إغلاق النافذة</button>
      </div>
    `;
    // تتبّع تشخيصي تلقائي: أين انكسر حلّ ملفات الكتاب؟
    try {
      const dq = new URLSearchParams();
      if (params.rel_path) dq.set('rel_path', params.rel_path);
      if (params.book_id) dq.set('book_id', params.book_id);
      if (params.book_title) dq.set('book_title', params.book_title);
      const dr = await fetch(`/api/book/diagnose?${dq.toString()}`);
      const dg = await dr.json();
      const box = document.getElementById('readerDiagBox');
      if (box) {
        const line = (k, v) => `<div style="display:flex;justify-content:space-between;gap:12px;padding:2px 0;"><span>${k}</span><b dir="auto" style="font-size:11.5px;">${escapeHtml(String(v ?? '—'))}</b></div>`;
        box.style.display = '';
        box.innerHTML = `<div style="font-weight:700;margin-bottom:6px;">تشخيص فتح الكتاب</div>` +
          line('رقم الكتاب المفسَّر', dg.book_id_parsed) +
          line('مساره في الكتالوج', dg.catalog_rel_path) +
          line('مجلده على القرص', dg.dir_for_rel || 'غير موجود') +
          line('رقم الشاملة المقابل', dg.their_id) +
          line('مصدر المكتبة', dg.library_source) +
          (dg.lazy_diag && dg.lazy_diag.error ? line('خطأ الاستخراج الكسول', dg.lazy_diag.error) : '');
      }
    } catch (e) { /* التشخيص اختياري */ }
  }
}

// عرض الصفحة وعناصر التحكم بالكامل
function renderReaderView() {
  // الترويسة
  document.getElementById('readerModalTitle').textContent = readerState.bookTitle;
  const authorStr = readerState.author + (readerState.deathYear ? ` (ت: ${readerState.deathYear} هـ)` : '');
  document.getElementById('readerModalAuthor').textContent = authorStr;
  document.getElementById('readerModalCategory').textContent = readerState.category || 'عام';

  // عرض بانر رأس الحولية التاريخية الحاكمة
  const banner = document.getElementById('readerContextBanner');
  const bannerText = document.getElementById('readerContextText');
  const bannerIcon = document.getElementById('readerContextIcon');
  if (banner && bannerText) {
    if (readerState.annalisticYear) {
      banner.style.display = 'flex';
      if (bannerIcon) bannerIcon.textContent = '📅';
      bannerText.textContent = `رأس الحولية التاريخية الحاكمة: ${readerState.annalisticYear}`;
    } else {
      banner.style.display = 'none';
    }
  }

  // تحديث قائمة الأجزاء المنسدلة
  const volSelect = document.getElementById('readerVolumeSelect');
  if (volSelect) {
    const readerParts = [...(readerState.parts || [])];
    if (readerState.part && !readerParts.map(part => String(part)).includes(String(readerState.part))) {
      readerParts.unshift(readerState.part);
    }
    if (readerParts.length > 0) {
      volSelect.parentElement.style.display = 'flex';
      volSelect.innerHTML = readerParts.map(p => {
        const label = p ? (isNaN(p) ? p : `الجزء ${p}`) : 'المجلد الرئيسي';
        const isSel = String(p) === String(readerState.part) ? 'selected' : '';
        return `<option value="${escapeHtml(p)}" ${isSel}>${escapeHtml(label)}</option>`;
      }).join('');
    } else {
      volSelect.parentElement.style.display = 'none';
    }
  }

  // تحديث حقل الصفحة
  const pageInput = document.getElementById('readerPageInput');
  if (pageInput) {
    pageInput.value = readerState.pageNum !== null ? readerState.pageNum : '';
  }

  // مؤشر الصفحة الإجمالية
  const partLabel = readerState.part ? `[جـ: ${readerState.part}] ` : '';
  const pageLabel = readerState.pageNum ? `ص: ${readerState.pageNum}` : `مقطع ${readerState.seq}`;
  const placeLabel = readerState.missing ? '' : ` (موضع: ${readerState.seq} من ${readerState.totalPages})`;
  document.getElementById('readerPageIndicator').textContent = `${partLabel}${pageLabel}${placeLabel}`;

  // أزرار التقليب
  const btnPrev = document.getElementById('btnReaderPrevPage');
  const btnNext = document.getElementById('btnReaderNextPage');
  if (btnPrev) {
    btnPrev.disabled = !readerState.prevPage;
    btnPrev.title = readerState.prevPage ? `الصفحة السابقة (ص: ${readerState.prevPage.page_num || '-'})` : 'بداية الكتاب';
  }
  if (btnNext) {
    btnNext.disabled = !readerState.nextPage;
    btnNext.title = readerState.nextPage ? `الصفحة اللاحقة (ص: ${readerState.nextPage.page_num || '-'})` : 'نهاية الكتاب';
  }

  // تعبئة بطاقة الكتاب
  const betakaEl = document.getElementById('readerBetakaContent');
  if (betakaEl) {
    betakaEl.textContent = readerState.betakaText || 'لا تتوفر بطاقة إضافية لهذا الكتاب في الشاملة.';
  }

  // عرض المتن والحواشي
  if (readerState.isSurroundingView) {
    loadSurroundingPagesView();
  } else {
    renderReaderBodyText();
  }

  // النسخة المصوّرة تتبع الصفحة المعروضة
  refreshReaderPdfButton();
}

// النسخة المصوّرة: زرها يظهر فقط إن كان لصفحة النص مقابل ممسوح عند الشاملة
let readerPdfToken = 0;

async function refreshReaderPdfButton() {
  const btn = document.getElementById('btnReaderPdf');
  if (!btn) return;
  const myToken = ++readerPdfToken;
  readerState.pdfInfo = null;
  readerState.pdfPage = null;
  closeReaderPdfPanel();
  btn.style.display = 'none';
  try {
    const q = new URLSearchParams();
    if (readerState.bookId) q.set('book_id', readerState.bookId);
    if (readerState.relPath) q.set('rel_path', readerState.relPath);
    if (readerState.part) q.set('part', readerState.part);
    if (readerState.pageNum) q.set('page_num', readerState.pageNum);
    const res = await fetch(`/api/book/pdf-info?${q.toString()}`);
    if (!res.ok || myToken !== readerPdfToken || !readerState.isOpen) return;
    const info = await res.json();
    if (myToken !== readerPdfToken || !info.available) return;
    readerState.pdfInfo = info;
    readerState.pdfPage = info.pdf_page;
    btn.style.display = '';
  } catch (e) { /* لا مصوّرة لهذه الصفحة */ }
}

function closeReaderPdfPanel() {
  closePdfViewer();
}

// نافذة النسخة المصوّرة المستقلة
const pdfView = {
  zoom: 1, lens: false, cropMode: false, cropRect: null
};

function pdfQuery(pdfPage) {
  const q = new URLSearchParams();
  if (readerState.bookId) q.set('book_id', readerState.bookId);
  if (readerState.relPath) q.set('rel_path', readerState.relPath);
  if (readerState.part) q.set('part', readerState.part);
  if (readerState.pageNum) q.set('page_num', readerState.pageNum);
  if (pdfPage) q.set('pdf_page', pdfPage);
  return q;
}

function toggleReaderPdf() {
  if (!readerState.pdfInfo) return;
  const modal = document.getElementById('pdfViewerModal');
  if (!modal) return;
  modal.style.display = 'flex';
  readerState.pdfOpen = true;
  document.getElementById('pdfViewerTitle').textContent =
    `النسخة المصوّرة — ${readerState.bookTitle || ''}`;
  const partSel = document.getElementById('pdfPartSelect');
  const parts = [...(readerState.parts || [])];
  if (readerState.part && !parts.map(String).includes(String(readerState.part))) parts.unshift(readerState.part);
  partSel.innerHTML = parts.map(p =>
    `<option value="${escapeHtml(p)}" ${String(p) === String(readerState.part) ? 'selected' : ''}>${escapeHtml(p ? (isNaN(p) ? p : `الجزء ${p}`) : 'المجلد الرئيسي')}</option>`).join('');
  document.getElementById('pdfPageInput').value = readerState.pageNum || '';
  bindPdfPageInteractions();
  pdfView.cropRect = null;
  renderReaderPdfPage();
}

function closePdfViewer() {
  const modal = document.getElementById('pdfViewerModal');
  if (modal) modal.style.display = 'none';
  readerState.pdfOpen = false;
  const btn = document.getElementById('btnReaderPdf');
  if (btn) btn.classList.remove('active');
}

function renderReaderPdfPage() {
  const info = readerState.pdfInfo;
  const img = document.getElementById('pdfViewerImg');
  if (!info || !img) return;
  img.src = `/api/book/pdf-image?${pdfQuery(readerState.pdfPage).toString()}`;
  const meta = document.getElementById('pdfViewerMeta');
  if (meta) meta.textContent = info.file_name || '';
  const label = document.getElementById('pdfPageLabel');
  if (label) label.textContent = `صفحة المصوّرة ${readerState.pdfPage} من ${info.pdf_pages || '؟'}`;
  const slider = document.getElementById('pdfPageSlider');
  if (slider) { slider.max = info.pdf_pages || 1; slider.value = readerState.pdfPage; }
  const lensImg = document.getElementById('pdfLensImg');
  if (lensImg) lensImg.src = img.src;
  clearPdfCrop();
  applyPdfZoom();
  if (info.pdf_pages && readerState.pdfPage < info.pdf_pages) {
    const pre = new Image();
    pre.src = `/api/book/pdf-image?${pdfQuery(readerState.pdfPage + 1).toString()}`;
  }
}

function pdfViewerNav(dir) {
  if (!readerState.pdfInfo) return;
  const total = readerState.pdfInfo.pdf_pages || 1;
  readerState.pdfPage = Math.max(1, Math.min(total, (readerState.pdfPage || 1) + dir));
  renderReaderPdfPage();
}

function readerPdfNav(dir) { pdfViewerNav(dir); }

function pdfViewerSlider(value) {
  readerState.pdfPage = Number(value) || 1;
  renderReaderPdfPage();
}

async function pdfViewerGo() {
  const part = document.getElementById('pdfPartSelect').value;
  const pageNum = Number(document.getElementById('pdfPageInput').value);
  if (!pageNum) { showToast('أدخل رقم الصفحة'); return; }
  try {
    const q = new URLSearchParams();
    if (readerState.bookId) q.set('book_id', readerState.bookId);
    if (readerState.relPath) q.set('rel_path', readerState.relPath);
    if (part) q.set('part', part);
    q.set('page_num', pageNum);
    const res = await fetch(`/api/book/pdf-info?${q.toString()}`);
    const info = await res.json();
    if (!info.available) { showToast(info.reason || 'لا مصوّرة لهذا الموضع', 6000); return; }
    readerState.pdfInfo = info;
    readerState.pdfPage = info.pdf_page;
    renderReaderPdfPage();
  } catch (e) {
    showToast('تعذر جلب النسخة المصوّرة');
  }
}

function applyPdfZoom() {
  const wrap = document.getElementById('pdfPageWrap');
  const label = document.getElementById('pdfZoomLabel');
  if (wrap) wrap.style.width = `${Math.round(pdfView.zoom * 100)}%`;
  if (label) label.textContent = `${Math.round(pdfView.zoom * 100)}%`;
}

function pdfViewerZoom(delta) {
  pdfView.zoom = Math.max(0.1, Math.min(2, pdfView.zoom + delta));
  applyPdfZoom();
}

function togglePdfLens() {
  pdfView.lens = !pdfView.lens;
  const btn = document.getElementById('btnPdfLens');
  if (btn) btn.classList.toggle('active', pdfView.lens);
  if (!pdfView.lens) document.getElementById('pdfLens').style.display = 'none';
}

function togglePdfCrop() {
  pdfView.cropMode = !pdfView.cropMode;
  const btn = document.getElementById('btnPdfCrop');
  if (btn) btn.classList.toggle('active', pdfView.cropMode);
  if (pdfView.cropMode) showToast('اسحب فوق الصورة لتحديد أي قصاصة من الصفحة');
}

function clearPdfCrop() {
  pdfView.cropRect = null;
  const box = document.getElementById('pdfCropBox');
  if (box) box.style.display = 'none';
  const get = document.getElementById('btnPdfCropGet');
  if (get) get.style.display = 'none';
  const send = document.getElementById('btnPdfCropSend');
  if (send) send.style.display = 'none';
}

// نقل نص أي قصاصة من الصفحة (لا الشاهد وحده) إلى محادثة جديدة بعد قراءته بصريًا
async function sendPdfCropToChat() {
  const rect = pdfView.cropRect;
  if (!rect) { showToast('حدّد قصاصة من الصفحة أولاً'); return; }
  const btn = document.getElementById('btnPdfCropSend');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ يقرأ النص…'; }
  try {
    const payload = Object.fromEntries(pdfQuery(readerState.pdfPage).entries());
    payload.rect = rect;
    const res = await fetch('/api/book/pdf-crop-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    const text = (data.text || '').trim();
    if (!text) { showToast(data.reason || 'لم يُقرأ نص في هذه القصاصة', 6000); return; }
    const promptMessage = text;
    closePdfViewer();
    closeBookReader();
    const bookName = (readerState.bookTitle || 'نص من الكتاب').trim();
    const sessionTitle = `مطالعة: ${bookName.slice(0, 32)}`;
    if (typeof startNewChatWithPrompt === 'function') {
      startNewChatWithPrompt(promptMessage, sessionTitle);
    } else {
      switchMainTab('chat');
      if (typeof createNewChatSession === 'function') createNewChatSession(true, sessionTitle);
      const chatInput = document.getElementById('chatInputText');
      if (chatInput) { chatInput.value = promptMessage; chatInput.focus(); }
    }
    showToast('نُقل نص القصاصة إلى المحادثة 💬');
  } catch (e) {
    showToast('تعذر قراءة نص القصاصة');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'نقل هذا النص إلى المحادثة'; }
  }
}

function downloadPdfCrop() {
  const img = document.getElementById('pdfViewerImg');
  const rect = pdfView.cropRect;
  if (!img || !rect || !img.naturalWidth) return;
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(rect.w * img.naturalWidth));
  canvas.height = Math.max(1, Math.round(rect.h * img.naturalHeight));
  canvas.getContext('2d').drawImage(
    img, rect.x * img.naturalWidth, rect.y * img.naturalHeight,
    rect.w * img.naturalWidth, rect.h * img.naturalHeight, 0, 0, canvas.width, canvas.height);
  const a = document.createElement('a');
  a.href = canvas.toDataURL('image/png');
  a.download = `شاهد-${readerState.bookId || 'كتاب'}-ص${readerState.pdfPage}.png`;
  a.click();
}

// نقل الشاهد وحده نصيًا (لا الصفحة كلها) إلى محادثة جديدة
function sendWitnessToChat() {
  const passage = (extractWitnessTarget(readerState.highlightText) || '').trim();
  if (!passage) {
    showToast('لا شاهد محددًا — افتح الكتاب من نتيجة بحث أولاً');
    return;
  }
  const promptMessage = passage;
  closePdfViewer();
  closeBookReader();
  const bookName = (readerState.bookTitle || 'نص من الكتاب').trim();
  const sessionTitle = `مطالعة: ${bookName.slice(0, 32)}`;
  if (typeof startNewChatWithPrompt === 'function') {
    startNewChatWithPrompt(promptMessage, sessionTitle);
  } else {
    switchMainTab('chat');
    if (typeof createNewChatSession === 'function') createNewChatSession(true, sessionTitle);
    const chatInput = document.getElementById('chatInputText');
    if (chatInput) {
      chatInput.value = promptMessage;
      chatInput.focus();
    }
  }
  showToast('نُقل الشاهد وحده إلى المحادثة 💬');
}

function bindPdfPageInteractions() {
  const wrap = document.getElementById('pdfPageWrap');
  const img = document.getElementById('pdfViewerImg');
  if (!wrap || !img || wrap.dataset.bound) return;
  wrap.dataset.bound = '1';
  let dragStart = null;
  img.addEventListener('mousedown', (ev) => {
    if (!pdfView.cropMode) return;
    const rect = img.getBoundingClientRect();
    dragStart = { x: (ev.clientX - rect.left) / rect.width, y: (ev.clientY - rect.top) / rect.height };
    ev.preventDefault();
  });
  img.addEventListener('mousemove', (ev) => {
    const lens = document.getElementById('pdfLens');
    const rect = img.getBoundingClientRect();
    const rx = (ev.clientX - rect.left) / rect.width;
    const ry = (ev.clientY - rect.top) / rect.height;
    if (pdfView.lens && lens) {
      const wrapRect = wrap.getBoundingClientRect();
      const size = 190, scale = 2.2;
      lens.style.display = 'block';
      lens.style.left = `${ev.clientX - wrapRect.left - size / 2}px`;
      lens.style.top = `${ev.clientY - wrapRect.top - size / 2}px`;
      const lensImg = document.getElementById('pdfLensImg');
      lensImg.style.width = `${rect.width * scale}px`;
      lensImg.style.height = `${rect.height * scale}px`;
      lensImg.style.left = `${-rx * rect.width * scale + size / 2}px`;
      lensImg.style.top = `${-ry * rect.height * scale + size / 2}px`;
    } else if (lens) {
      lens.style.display = 'none';
    }
    if (pdfView.cropMode && dragStart) {
      const box = document.getElementById('pdfCropBox');
      const x = Math.min(dragStart.x, rx), y = Math.min(dragStart.y, ry);
      const w = Math.abs(rx - dragStart.x), h = Math.abs(ry - dragStart.y);
      pdfView.cropRect = { x, y, w, h };
      box.style.display = 'block';
      box.style.left = `${x * 100}%`;
      box.style.top = `${y * 100}%`;
      box.style.width = `${w * 100}%`;
      box.style.height = `${h * 100}%`;
    }
  });
  img.addEventListener('mouseup', () => {
    if (pdfView.cropMode && pdfView.cropRect && pdfView.cropRect.w > 0.01) {
      document.getElementById('btnPdfCropGet').style.display = '';
      document.getElementById('btnPdfCropSend').style.display = '';
    }
    dragStart = null;
  });
  img.addEventListener('click', (ev) => {
    if (pdfView.lens || pdfView.cropMode) return;
    const rect = img.getBoundingClientRect();
    pdfViewerNav((ev.clientX - rect.left) / rect.width < 0.5 ? 1 : -1);
  });
}

// عرض متن الصفحة مع التشكيل أو بدونه وإبراز النص المبحوث عنه
function renderReaderBodyText() {
  const bodyContainer = document.getElementById('readerPageBody');
  const footContainer = document.getElementById('readerFootnotes');
  const btnTashkeel = document.getElementById('btnToggleTashkeel');

  if (btnTashkeel) {
    btnTashkeel.textContent = readerState.showTashkeel ? 'إخفاء التشكيل' : 'إظهار التشكيل';
    btnTashkeel.classList.toggle('active', !readerState.showTashkeel);
  }

  if (readerState.missing) {
    bodyContainer.innerHTML = '<div class="reader-empty-page"></div>';
    footContainer.style.display = 'none';
    bodyContainer.scrollTop = 0;
    return;
  }

  let text = readerState.rawBody;

  // إزالة التشكيل إذا رغب المستخدم
  if (!readerState.showTashkeel) {
    text = removeTashkeel(text);
  }

  // تحويل فواصل الأسطر والفقرات إلى فقرات منسقة
  const paragraphs = text.split(/\r?\n\r?\n/).map(p => p.trim()).filter(Boolean);
  let html = paragraphs.map(p => {
    const pEscaped = escapeHtml(p);
    return `<p class="reader-paragraph">${pEscaped.replace(/\r?\n/g, '<br>')}</p>`;
  }).join('');

  bodyContainer.innerHTML = html || '<p style="color: var(--text-muted); text-align: center;">صفحة فارغة أو عنوان</p>';

  // عرض الحواشي إن وجدت
  if (readerState.footnotes) {
    footContainer.style.display = 'block';
    let fText = readerState.footnotes;
    if (!readerState.showTashkeel) fText = removeTashkeel(fText);
    document.getElementById('readerFootnotesText').innerHTML = escapeHtml(fText).replace(/\r?\n/g, '<br>');
  } else {
    footContainer.style.display = 'none';
  }

  // التمرير لأعلى الصفحة
  bodyContainer.scrollTop = 0;

  // نافذة البحث بمنظار مفتوحة: إعادة التحديد على الصفحة الجديدة تلقائيًا
  refreshReaderSearchIfOpen();
}

// تبديل إظهار وإخفاء التشكيل
function toggleReaderTashkeel() {
  readerState.showTashkeel = !readerState.showTashkeel;
  renderReaderBodyText();
  showToast(readerState.showTashkeel ? 'تم إظهار التشكيل والحركات' : 'تم إخفاء التشكيل لسهولة القراءة');
}

// تبديل إظهار بطاقة الكتاب الكاملة
function toggleReaderBetaka() {
  readerState.showBetaka = !readerState.showBetaka;
  const panel = document.getElementById('readerBetakaPanel');
  const btn = document.getElementById('btnToggleBetaka');
  if (panel) {
    panel.style.display = readerState.showBetaka ? 'block' : 'none';
  }
  if (btn) {
    btn.classList.toggle('active', readerState.showBetaka);
  }
}

function clearReaderBookFilter() {
  closeReaderBookFilter();
  const input = document.getElementById('readerBookFilterInput');
  if (input) input.value = '';
}

function closeReaderBookFilter() {
  const menu = document.getElementById('readerBookFilterMenu');
  if (menu) menu.hidden = true;
}

async function ensureReaderBooks() {
  if (readerBooksCatalog) return readerBooksCatalog;
  const response = await fetch('/api/books');
  if (!response.ok) throw new Error('تعذر تحميل فهرس الكتب');
  readerBooksCatalog = await response.json();
  return readerBooksCatalog;
}

function renderReaderBookFilter(query) {
  const menu = document.getElementById('readerBookFilterMenu');
  if (!menu) return;
  const needle = (query || '').trim();
  ensureReaderBooks().then(books => {
    const list = (books || []).filter(book => {
      const haystack = `${book.title || ''} ${book.author || ''} ${book.category_name || ''}`;
      return !needle || haystack.includes(needle);
    }).slice(0, 40);
    menu._books = list;
    menu.hidden = false;
    menu.innerHTML = list.length
      ? list.map((book, index) => `
          <button type="button" class="reader-book-filter-item" data-reader-book="${index}">
            <span>${escapeHtml(book.title || '')}</span>
            <small>${escapeHtml(book.category_name || '')}</small>
          </button>
        `).join('')
      : '<div class="reader-book-filter-empty">لا توجد كتب مطابقة</div>';
  }).catch(() => {
    menu.hidden = false;
    menu.innerHTML = '<div class="reader-book-filter-empty">تعذر تحميل فهرس الشاملة</div>';
  });
}

async function switchReaderBook(book) {
  if (!book || !readerState.isOpen) return;
  closeReaderBookFilter();
  const part = readerState.part || '';
  const pageNum = readerState.pageNum;
  readerState.bookTitle = book.title || '';
  readerState.category = book.category_name || 'عام';
  readerState.author = book.author || '';
  readerState.deathYear = book.death || null;
  readerState.relPath = '';
  readerState.bookId = '';
  readerState.highlightText = '';
  readerState.isSurroundingView = false;
  clearReaderBookFilter();
  document.getElementById('readerModalTitle').textContent = readerState.bookTitle;
  document.getElementById('readerModalCategory').textContent = readerState.category;
  const authorStr = readerState.author + (readerState.deathYear ? ` (ت: ${readerState.deathYear} هـ)` : '');
  document.getElementById('readerModalAuthor').textContent = authorStr;
  await loadReaderPage({
    book_title: readerState.bookTitle,
    part,
    page_num: pageNum,
    strict: '1'
  });
}

// تغيير الجزء من القائمة المنسدلة
function onReaderVolumeChange() {
  const select = document.getElementById('readerVolumeSelect');
  if (!select) return;
  const newPart = select.value;
  loadReaderPage({
    rel_path: readerState.relPath,
    part: newPart,
    page_num: null // ينتقل لأول صفحة في هذا الجزء
  });
}

// الانتقال إلى رقم صفحة محدد
function onReaderJumpPage() {
  const input = document.getElementById('readerPageInput');
  if (!input || !input.value) return;
  const targetPage = parseInt(input.value.trim());
  if (isNaN(targetPage)) return;

  loadReaderPage({
    rel_path: readerState.relPath,
    part: readerState.part,
    page_num: targetPage
  });
}

// التقليب بين الصفحات (السابقة / اللاحقة) حتى نهاية الكتاب
function navigateReaderPage(direction) {
  if (direction === 'prev' && readerState.prevPage) {
    loadReaderPage({
      rel_path: readerState.relPath,
      seq: readerState.prevPage.seq
    });
  } else if (direction === 'next' && readerState.nextPage) {
    loadReaderPage({
      rel_path: readerState.relPath,
      seq: readerState.nextPage.seq
    });
  }
}

// رصد التحديد في متن الصفحة
function onReaderTextSelected() {
  const selection = window.getSelection();
  const tooltip = document.getElementById('readerSelectionTooltip');
  if (!tooltip) return;
  if (tooltip.contains(document.activeElement) || tooltip.matches(':hover')) return;

  const selectedStr = selection ? selection.toString().trim() : '';
  const root = document.getElementById('readerContentScroll') || document.getElementById('readerPageBody');
  const inside = !!(selection && selection.rangeCount && root && (
    root.contains(selection.anchorNode) || root.contains(selection.focusNode)
  ));

  if (inside && selectedStr) {
    readerState.selectedText = selectedStr;
    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    if (rect.width || rect.height) {
      tooltip.style.display = 'flex';
      tooltip.style.top = `${Math.max(16, rect.top - 8)}px`;
      tooltip.style.left = `${rect.left + (rect.width / 2)}px`;
      return;
    }
  }
  if (!selectedStr) readerState.selectedText = '';
  tooltip.style.display = 'none';
}
window.onReaderTextSelected = onReaderTextSelected;

// إرسال النص المحدد (أو الصفحة كاملة) إلى نافذة الشات للمناقشة مع النموذج
function sendReaderSelectionToChat() {
  let passage = readerState.selectedText;
  if (!passage && readerState.highlightText) {
    // النقل النصي ينقل الشاهد المحدد وحده لا مطلع الصفحة
    passage = extractWitnessTarget(readerState.highlightText);
  }
  if (!passage) {
    passage = readerState.rawBody.slice(0, 500).trim();
  }

  if (!passage) {
    showToast('يرجى تحديد نص من الصفحة أولاً');
    return;
  }

  const promptMessage = passage;

  // إغلاق القارئ
  closeBookReader();

  const bookName = (readerState.bookTitle || 'نص من الكتاب').trim();
  const sessionTitle = `مطالعة: ${bookName.slice(0, 32)}`;

  if (typeof startNewChatWithPrompt === 'function') {
    startNewChatWithPrompt(promptMessage, sessionTitle);
  } else {
    switchMainTab('chat');
    if (typeof createNewChatSession === 'function') {
      createNewChatSession(true, sessionTitle);
    }
    const chatInput = document.getElementById('chatInputText');
    if (chatInput) {
      chatInput.value = promptMessage;
      chatInput.style.height = 'auto';
      chatInput.style.height = `${Math.min(chatInput.scrollHeight, 200)}px`;
      chatInput.focus();
    }
  }

  showToast('تم فتح محادثة جديدة ونقل النص والتوثيق إلى نافذة الشات 💬');
}

// إغلاق القارئ
function closeBookReader() {
  readerLoadToken++;
  const modal = document.getElementById('bookReaderModal');
  if (modal) modal.style.display = 'none';
  document.body.style.overflow = '';
  readerState.isOpen = false;
  readerState.highlightText = '';
  if (document.getElementById('readerSearchModal')) closeReaderSearch();
  clearReaderBookFilter();
  const tooltip = document.getElementById('readerSelectionTooltip');
  if (tooltip) tooltip.style.display = 'none';
}

// دالة مساعدة لحذف الحركات والتشكيل
function removeTashkeel(text) {
  if (!text) return '';
  return text.replace(/[\u064B-\u0652\u0670\u0640]/g, '');
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// نص الشاهد المقصود بحرفه لنقله إلى المحادثة: المنقول بين علامتي
// تنصيص، أو متن الحديث بعد قال رسول الله، أو العبارة كما هي.
function extractWitnessTarget(phrase) {
  const raw = String(phrase || '').replace(/\s+/g, ' ').trim();
  if (!raw) return '';
  const quoted = raw.match(/«([^»]{8,})»/) || raw.match(/“([^”]{8,})”/) || raw.match(/"([^"]{8,})"/);
  if (quoted) return quoted[1].trim();
  const marker = raw.match(/(قال رسول الله|قال النبي|أن رسول الله|ان رسول الله|عن رسول الله|عن النبي)/);
  if (marker) {
    let rest = raw.slice(marker.index + marker[0].length);
    rest = rest.replace(/^[\s:ﷺ]*(صلى الله عليه (وآله )?وسلم)?[\s:ﷺ]*/, '');
    rest = rest.replace(/\s*\(?(رواه|أخرجه|متفق عليه).*$/, '');
    if (rest.trim().length >= 8) return rest.trim();
  }
  return raw.replace(/\s*\([^)]*\)\s*$/, '').trim() || raw;
}

// =============================================================================
// 🔭 بحث بمنظار في نص الكتاب المعروض: نسخة مطابقة لنافذة «بحث في الإجابة»
// — نافذة عائمة قابلة للسحب، تظليل تلقائي فوري أثناء الكتابة، عدّادات
// (مرات الورود وكلمات العبارة والجمل الحاوية)، وقائمة جمل يقفز منها
// القارئ إلى الموضع بعينه، مع تنقّل سابق/تالٍ بين المواضع.
// =============================================================================
let _readerSearch = { marks: [], current: -1 };

function _rdNormChar(ch) {
  if (/[\u064B-\u0652\u0670\u0640]/.test(ch)) return '';
  if ('إأآٱ'.includes(ch)) return 'ا';
  if (ch === 'ى') return 'ي';
  if (ch === 'ة') return 'ه';
  if (ch === 'ؤ') return 'و';
  if (ch === 'ئ') return 'ي';
  return ch;
}
function _rdNormalize(s) { return (s || '').split('').map(_rdNormChar).join(''); }

function _ensureReaderSearchModal() {
  if (document.getElementById('readerSearchModal')) return;
  const st = document.createElement('style');
  st.textContent = 'mark.rd-hit{background:#ffe58a;color:inherit;padding:0 1px;border-radius:3px;} mark.rd-hit.rd-current{background:#ff9d45;outline:2px solid #e07b1f;}';
  document.head.appendChild(st);
  const d = document.createElement('div');
  d.id = 'readerSearchModal';
  d.style.cssText = 'display:none;position:fixed;inset:0;z-index:10001;background:transparent;direction:rtl;pointer-events:none;';
  d.innerHTML = `
    <div id="readerSearchPanel" style="pointer-events:auto;position:absolute;top:7vh;left:50%;transform:translateX(-50%);width:min(640px,94vw);background:var(--bg-surface,#fff);border-radius:14px;box-shadow:0 18px 50px rgba(0,0,0,0.35);padding:16px 18px;max-height:84vh;display:flex;flex-direction:column;">
      <div id="readerSearchDragHandle" title="اسحب من هذا الشريط لتحريك النافذة ومشاهدة التظليل في نص الكتاب" style="display:flex;justify-content:space-between;align-items:center;gap:10px;cursor:move;touch-action:none;user-select:none;-webkit-user-select:none;">
        <strong style="font-size:15px;">🔭 بحث في نص الكتاب <span style="font-size:11px;opacity:0.65;font-weight:400;">(قابلة للسحب ⠿)</span></strong>
        <button type="button" class="btn-msg-export" onclick="closeReaderSearch()">إغلاق ✕</button>
      </div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;">
        <input id="readerSearchInput" type="text" placeholder="اكتب حرفًا أو كلمة أو جملة للبحث داخل المعروض من الكتاب..." style="flex:1;min-width:220px;padding:9px 12px;border:1px solid var(--border-subtle,#ccc);border-radius:9px;font-size:14px;" oninput="runReaderSearch()" onkeydown="if(event.key==='Enter'){event.preventDefault();stepReaderSearch(1);}">
        <button type="button" class="btn-msg-export" onclick="stepReaderSearch(-1)">▲ السابق</button>
        <button type="button" class="btn-msg-export" onclick="stepReaderSearch(1)">▼ التالي</button>
      </div>
      <label style="margin-top:8px;font-size:12.5px;display:flex;gap:6px;align-items:center;cursor:pointer;">
        <input id="readerSearchFlex" type="checkbox" checked onchange="runReaderSearch()">
        بحث مرن: تجاهل التشكيل والهمزات والألف المقصورة والتاء المربوطة
      </label>
      <div id="readerSearchStats" style="margin-top:9px;font-size:13px;line-height:1.9;color:var(--accent-gold,#9a6b1f);background:rgba(184,115,51,0.07);border:1px solid var(--border-subtle,#e2d8c3);border-radius:9px;padding:7px 11px;">اكتب عبارة البحث وستُظلَّل مواضعها في نص الكتاب تلقائيًا مع عدّاداتها هنا.</div>
      <div id="readerSearchResults" style="margin-top:10px;overflow-y:auto;display:flex;flex-direction:column;gap:6px;"></div>
    </div>`;
  document.body.appendChild(d);
  // سحب النافذة من شريط رأسها (ماوس ولمس) ليبقى نص الكتاب وتظليلاته مرئية
  const panel = d.querySelector('#readerSearchPanel');
  const handle = d.querySelector('#readerSearchDragHandle');
  if (panel && handle) {
    handle.addEventListener('pointerdown', (e) => {
      if (e.target.closest('button')) return;
      const rect = panel.getBoundingClientRect();
      panel.style.left = rect.left + 'px';
      panel.style.top = rect.top + 'px';
      panel.style.transform = 'none';
      const offX = e.clientX - rect.left, offY = e.clientY - rect.top;
      handle.setPointerCapture(e.pointerId);
      const move = (ev) => {
        const w = panel.offsetWidth, h = panel.offsetHeight;
        let x = ev.clientX - offX, y = ev.clientY - offY;
        x = Math.max(-w + 90, Math.min(x, window.innerWidth - 90));
        y = Math.max(0, Math.min(y, window.innerHeight - 44));
        panel.style.left = x + 'px';
        panel.style.top = y + 'px';
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
}

function openReaderSearch() {
  _ensureReaderSearchModal();
  _clearReaderHighlights();
  _readerSearch = { marks: [], current: -1 };
  const m = document.getElementById('readerSearchModal');
  m.style.display = 'block';
  const btn = document.getElementById('btnReaderLensSearch');
  if (btn) btn.classList.add('active');
  const inp = document.getElementById('readerSearchInput');
  if (inp) {
    if (!inp.value.trim() && readerState.highlightText) {
      inp.value = extractWitnessTarget(readerState.highlightText);
    }
    inp.focus();
    if (inp.value.trim().length >= 2) runReaderSearch();
  }
}
function closeReaderSearch() {
  _clearReaderHighlights();
  const m = document.getElementById('readerSearchModal');
  if (m) m.style.display = 'none';
  const btn = document.getElementById('btnReaderLensSearch');
  if (btn) btn.classList.remove('active');
  _readerSearch = { marks: [], current: -1 };
}
function _clearReaderHighlights() {
  const body = document.getElementById('readerPageBody');
  if (body) {
    body.querySelectorAll('mark.rd-hit').forEach(mk => {
      const parent = mk.parentNode;
      if (parent) { parent.replaceChild(document.createTextNode(mk.textContent), mk); parent.normalize(); }
    });
  }
  _readerSearch.marks = []; _readerSearch.current = -1;
}
// عند قلب الصفحة أو استيفاء السياق والنافذة مفتوحة: إعادة التحديد تلقائيًا
function refreshReaderSearchIfOpen() {
  const m = document.getElementById('readerSearchModal');
  if (!m || m.style.display === 'none') return;
  const inp = document.getElementById('readerSearchInput');
  if (inp && inp.value.trim().length >= 2) runReaderSearch();
}
function runReaderSearch() {
  _clearReaderHighlights();
  const stats = document.getElementById('readerSearchStats');
  const results = document.getElementById('readerSearchResults');
  const q = (document.getElementById('readerSearchInput')?.value || '').trim();
  const flex = !!document.getElementById('readerSearchFlex')?.checked;
  if (results) results.innerHTML = '';
  if (!q || q.length < 2) { if (stats) stats.textContent = 'اكتب حرفين على الأقل للبحث داخل المعروض من الكتاب.'; return; }
  const content = document.getElementById('readerPageBody');
  if (!content) { if (stats) stats.textContent = 'تعذر العثور على نص الكتاب المعروض.'; return; }

  // جمع العقد النصية (عدا الأزرار) ثم تظليل كل مواضع العبارة فيها
  const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      if (node.parentElement && node.parentElement.closest('button')) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const nq = flex ? _rdNormalize(q) : q;
  let total = 0;
  for (const node of nodes) {
    const text = node.nodeValue;
    let hay = text, map = null;
    if (flex) {
      hay = ''; map = [];
      for (let i = 0; i < text.length; i++) { const nc = _rdNormChar(text[i]); if (nc) { hay += nc; map.push(i); } }
    }
    const spans = [];
    let pos = 0;
    while (true) {
      const hit = hay.indexOf(nq, pos);
      if (hit < 0) break;
      const s = flex ? map[hit] : hit;
      const e = flex ? (map[hit + nq.length - 1] + 1) : (hit + nq.length);
      spans.push([s, e]); total++;
      pos = hit + Math.max(nq.length, 1);
    }
    if (!spans.length) continue;
    const frag = document.createDocumentFragment();
    let last = 0;
    for (const [s, e] of spans) {
      if (s > last) frag.appendChild(document.createTextNode(text.slice(last, s)));
      const mk = document.createElement('mark');
      mk.className = 'rd-hit'; mk.textContent = text.slice(s, e);
      frag.appendChild(mk);
      last = e;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
  }
  _readerSearch.marks = Array.from(content.querySelectorAll('mark.rd-hit'));

  // عدّادات: مرات الورود، حروف العبارة وكلماتها، والجمل الحاوية لها
  const plain = content.textContent || '';
  const sentences = plain.split(/(?<=[.!؟؛:])\s+|\n+/).map(s => s.trim()).filter(Boolean);
  let sentHits = [], markCursor = 0;
  for (const s of sentences) {
    const ns = flex ? _rdNormalize(s) : s;
    let c = 0, p = 0;
    while (true) { const h = ns.indexOf(nq, p); if (h < 0) break; c++; p = h + Math.max(nq.length, 1); }
    if (c) { sentHits.push({ sentence: s, count: c, firstMark: markCursor }); markCursor += c; }
  }
  const wordsCount = q.split(/\s+/).filter(Boolean).length;
  if (stats) {
    stats.innerHTML = total
      ? `وُجدت العبارة <strong>${total}</strong> مرة في المعروض من الكتاب | عبارة البحث: ${q.length} حرفًا و${wordsCount} ${wordsCount === 1 ? 'كلمة' : 'كلمات'} | وردت في <strong>${sentHits.length}</strong> جملة | تنقّل بالسابق/التالي أو اضغط أي جملة للقفز إلى موضعها.`
      : 'لا مواضع لهذه العبارة في المعروض من الكتاب. جرّب البحث المرن أو عبارة أقصر، أو وسّع المعروض باستيفاء السياق.';
  }
  if (results && sentHits.length) {
    results.innerHTML = sentHits.slice(0, 40).map((h, i) =>
      `<button type="button" onclick="jumpToReaderMark(${h.firstMark})" style="text-align:right;padding:8px 11px;border:1px solid var(--border-subtle,#ddd);border-radius:9px;background:transparent;cursor:pointer;font-size:12.5px;line-height:1.8;">
         <span style="color:var(--accent-gold,#9a6b1f);font-weight:700;">${i + 1}.</span> ${escapeHtml(h.sentence.slice(0, 220))}${h.sentence.length > 220 ? '…' : ''} <span style="opacity:0.7;">(${h.count}×)</span>
       </button>`).join('');
  }
  if (_readerSearch.marks.length) jumpToReaderMark(0);
}
function jumpToReaderMark(i) {
  const content = document.getElementById('readerPageBody');
  const marks = content ? Array.from(content.querySelectorAll('mark.rd-hit')) : [];
  _readerSearch.marks = marks;
  if (!marks.length) return;
  _readerSearch.current = ((i % marks.length) + marks.length) % marks.length;
  marks.forEach((mk, j) => mk.classList.toggle('rd-current', j === _readerSearch.current));
  marks[_readerSearch.current].scrollIntoView({ behavior: 'smooth', block: 'center' });
  const stats = document.getElementById('readerSearchStats');
  if (stats && marks.length) stats.innerHTML = stats.innerHTML.replace(/\| الموضع الحالي:.*$/, '') + ` | الموضع الحالي: ${_readerSearch.current + 1} من ${marks.length}`;
}
function stepReaderSearch(dir) { jumpToReaderMark((_readerSearch.current < 0 ? 0 : _readerSearch.current) + dir); }

// استيفاء وتقليب باقة الصفحات المتتالية (-2 إلى +2) لكشف رأس المسألة أو الحولية
// =============================================================================

function readerSurroundingSpan() {
  const read = (id) => {
    const el = document.getElementById(id);
    const n = parseInt(el && el.value, 10);
    if (!Number.isFinite(n) || n < 0) return 3;
    return Math.min(n, 100);
  };
  return {
    before: read('readerBeforePages'),
    after: read('readerAfterPages')
  };
}

function onReaderSurroundingSpanChange() {
  if (readerState.isSurroundingView) loadSurroundingPagesView();
}

async function showReaderPageText() {
  readerState.isSurroundingView = false;
  const btnToolbar = document.getElementById('btnToggleSurrounding');
  if (btnToolbar) btnToolbar.classList.remove('active');

  const bodyContainer = document.getElementById('readerPageBody');
  const footContainer = document.getElementById('readerFootnotes');
  if ((readerState.rawBody || '').trim()) {
    readerState.missing = false;
    renderReaderBodyText();
    return;
  }
  const myToken = ++readerLoadToken;
  if (!bodyContainer) return;

  bodyContainer.innerHTML = `
    <div style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
      <div style="display: inline-block; width: 28px; height: 28px; border: 3px solid var(--border-subtle); border-top-color: var(--accent-clay); border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 10px;"></div>
      <p style="font-family: var(--font-amiri); font-size: 17px;">جارٍ عرض متن الصفحة...</p>
    </div>
  `;
  if (footContainer) footContainer.style.display = 'none';

  const pickPage = (pages) => {
    const list = pages || [];
    const hint = (readerState.highlightText || '').replace(/\s+/g, ' ').trim().slice(0, 40);
    if (hint) {
      const hit = list.find(p => (p.body || '').includes(hint));
      if (hit && (hit.body || '').trim()) return hit;
    }
    return list.find(p => p.is_target && (p.body || '').trim())
      || list.find(p => (p.body || '').trim())
      || list.find(p => p.is_target)
      || null;
  };

  try {
    const loadSpan = async (before, after) => {
      const q = new URLSearchParams();
      if (readerState.relPath) q.set('rel_path', readerState.relPath);
      if (readerState.bookId) q.set('book_id', readerState.bookId);
      if (readerState.bookTitle) q.set('book_title', readerState.bookTitle);
      if (readerState.part !== undefined && readerState.part !== null) q.set('part', readerState.part);
      if (readerState.pageNum) q.set('page_num', readerState.pageNum);
      q.set('before', String(before));
      q.set('after', String(after));
      const res = await fetch(`/api/book/surrounding-pages?${q.toString()}`);
      if (!res.ok) throw new Error('تعذر عرض النص');
      return res.json();
    };

    let data = await loadSpan(0, 0);
    let page = pickPage(data.pages);
    if (!page || !(page.body || '').trim()) {
      data = await loadSpan(3, 3);
      page = pickPage(data.pages);
    }
    if (!page || !(page.body || '').trim()) throw new Error('تعذر عرض النص');
    if (myToken !== readerLoadToken || !readerState.isOpen) return;

    readerState.rawBody = page.body || '';
    readerState.footnotes = page.footnotes || '';
    if (page.part) readerState.part = page.part;
    if (page.page_num) readerState.pageNum = page.page_num;
    readerState.missing = false;
    renderReaderView();
  } catch (err) {
    console.error('Show page text error:', err);
    if (myToken !== readerLoadToken || !readerState.isOpen) return;
    if (bodyContainer) {
      bodyContainer.innerHTML = '<p style="text-align:center; padding: 30px; color: var(--text-muted);">تعذر عرض متن هذه الصفحة.</p>';
    }
  }
}

async function toggleSurroundingPagesView() {
  readerState.isSurroundingView = !readerState.isSurroundingView;
  const btnToolbar = document.getElementById('btnToggleSurrounding');
  if (btnToolbar) btnToolbar.classList.toggle('active', readerState.isSurroundingView);
  
  if (readerState.isSurroundingView) {
    await loadSurroundingPagesView();
  } else {
    renderReaderBodyText();
  }
}

async function loadSurroundingPagesView() {
  const bodyContainer = document.getElementById('readerPageBody');
  const footContainer = document.getElementById('readerFootnotes');
  if (!bodyContainer) return;

  const span = readerSurroundingSpan();
  bodyContainer.innerHTML = `
    <div style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
      <div style="display: inline-block; width: 28px; height: 28px; border: 3px solid var(--border-subtle); border-top-color: var(--accent-clay); border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 10px;"></div>
      <p style="font-family: var(--font-amiri); font-size: 17px;">جارٍ استيفاء ${span.before} صفحة سابقة و${span.after} صفحة لاحقة من الأصل التراثي...</p>
    </div>
  `;
  if (footContainer) footContainer.style.display = 'none';

  try {
    const q = new URLSearchParams();
    if (readerState.relPath) q.set('rel_path', readerState.relPath);
    if (readerState.bookId) q.set('book_id', readerState.bookId);
    if (readerState.bookTitle) q.set('book_title', readerState.bookTitle);
    if (readerState.part !== undefined && readerState.part !== null) q.set('part', readerState.part);
    if (readerState.pageNum) q.set('page_num', readerState.pageNum);
    q.set('before', String(span.before));
    q.set('after', String(span.after));

    const res = await fetch(`/api/book/surrounding-pages?${q.toString()}`);
    if (!res.ok) throw new Error('تعذر جلب باقة الصفحات المتتالية');

    const data = await res.json();
    if (data.book_title) {
      readerState.bookTitle = data.book_title;
      const titleEl = document.getElementById('readerModalTitle');
      if (titleEl) titleEl.textContent = data.book_title;
    }
    if (data.author) {
      readerState.author = data.author;
      readerState.deathYear = data.death_year || '';
      const authorEl = document.getElementById('readerModalAuthor');
      if (authorEl) {
        authorEl.textContent = data.author + (data.death_year ? ` (ت: ${data.death_year} هـ)` : '');
      }
    }
    const pages = data.pages || [];

    if (pages.length === 0) {
      bodyContainer.innerHTML = '<p style="text-align:center; padding: 30px; color: var(--text-muted);">لم يتم العثور على صفحات محيطة.</p>';
      return;
    }

    // تحديث رأس الحولية إذا كشفه استعلام باقة الصفحات
    if (data.annalistic_year) readerState.annalisticYear = data.annalistic_year;
    const banner = document.getElementById('readerContextBanner');
    const bannerText = document.getElementById('readerContextText');
    const bannerIcon = document.getElementById('readerContextIcon');
    if (banner && bannerText && readerState.annalisticYear) {
      banner.style.display = 'flex';
      if (bannerIcon) bannerIcon.textContent = '📅';
      bannerText.textContent = `رأس الحولية التاريخية الحاكمة: ${readerState.annalisticYear}`;
    }

    let html = `
      <div style="margin-bottom: 16px; padding: 10px 14px; background: rgba(199, 92, 58, 0.06); border: 1px solid rgba(199, 92, 58, 0.2); border-radius: 6px; font-size: 13px; color: var(--accent-clay); display: flex; justify-content: space-between; align-items: center;">
        <span>🔄 معروض باقة متتابعة من ${pages.length} صفحات (${pages[0].page_num || '-'} إلى ${pages[pages.length-1].page_num || '-'}) لإحكام سياق المسألة وتفادي البتر:</span>
        <button class="btn-flat-secondary reader-mini-btn" onclick="toggleSurroundingPagesView()">العودة لصفحة واحدة</button>
      </div>
    `;

    pages.forEach(p => {
      const isTarget = p.is_target;
      const cardClass = isTarget ? 'surrounding-page-card target-page' : 'surrounding-page-card';
      const partStr = p.part ? `جـ: ${p.part} | ` : '';
      const pLabel = p.page_num ? `ص: ${p.page_num}` : `مقطع ${p.seq}`;
      const targetBadge = isTarget ? ' <span style="background: var(--accent-clay); color: #fff; font-size: 10.5px; padding: 1px 6px; border-radius: 3px; margin-right: 6px;">الصفحة المستهدفة بالبحث</span>' : '';

      let text = p.body;
      if (!readerState.showTashkeel) text = removeTashkeel(text);

      const pParas = text.split(/\r?\n\r?\n/).map(pr => pr.trim()).filter(Boolean);
      let pBodyHtml = pParas.map(pr => {
        const esc = escapeHtml(pr);
        return `<p class="reader-paragraph">${esc.replace(/\r?\n/g, '<br>')}</p>`;
      }).join('');

      let titlesHtml = '';
      if (p.titles && p.titles.length > 0) {
        titlesHtml = `<div style="margin-bottom: 8px;">` + p.titles.map(t => `<span style="display: inline-block; background: var(--bg-muted); border: 1px solid var(--border-subtle); padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; color: var(--accent-clay); margin-left: 6px;">🏷️ ${escapeHtml(t)}</span>`).join('') + `</div>`;
      }

      let fnHtml = '';
      if (p.footnotes) {
        let fnText = p.footnotes;
        if (!readerState.showTashkeel) fnText = removeTashkeel(fnText);
        fnHtml = `
          <div style="margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--border-subtle); font-size: 13.5px; color: var(--text-secondary);">
            <div style="font-weight: 600; font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">الهوامش:</div>
            ${escapeHtml(fnText).replace(/\r?\n/g, '<br>')}
          </div>
        `;
      }

      html += `
        <div class="${cardClass}" id="page-card-${p.seq}">
          <div class="surrounding-page-badge">
            📖 ${partStr}${pLabel}${targetBadge}
          </div>
          ${titlesHtml}
          ${pBodyHtml}
          ${fnHtml}
        </div>
      `;
    });

    bodyContainer.innerHTML = html;
    refreshReaderSearchIfOpen();

    // التمرير التلقائي للصفحة المستهدفة
    setTimeout(() => {
      const targetEl = bodyContainer.querySelector('.surrounding-page-card.target-page');
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 260);

  } catch (err) {
    console.error('Surrounding pages error:', err);
    showToast('تعذر استيفاء السياق المتتابع');
    renderReaderBodyText();
  }
}

// تصدير الدوال على النطاق العام
window.onReaderSurroundingSpanChange = onReaderSurroundingSpanChange;
window.showReaderPageText = showReaderPageText;
window.toggleSurroundingPagesView = toggleSurroundingPagesView;
window.loadSurroundingPagesView = loadSurroundingPagesView;
window.sendReaderSelectionToChat = sendReaderSelectionToChat;
window.closeBookReader = closeBookReader;

