// =============================================================================
// منظومة المجتهد - قارئ الكتب التراثية الأصلي (reader.js)
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
  fiqhIssue: null,
  isSurroundingView: false,
  showTashkeel: true,
  showBetaka: false,
  selectedText: '',
  prevPage: null,
  nextPage: null,
  highlightText: '',
  bookId: '',
  missing: false
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
    highlight: item.text || ''
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
    readerState.fiqhIssue = data.fiqh_issue || null;
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

  // عرض بانر رأس الحولية التاريخية أو رأس المسألة الفقهية الحاكمة
  const banner = document.getElementById('readerContextBanner');
  const bannerText = document.getElementById('readerContextText');
  const bannerIcon = document.getElementById('readerContextIcon');
  if (banner && bannerText) {
    if (readerState.annalisticYear) {
      banner.style.display = 'flex';
      if (bannerIcon) bannerIcon.textContent = '📅';
      bannerText.textContent = `رأس الحولية التاريخية الحاكمة: ${readerState.annalisticYear}`;
    } else if (readerState.fiqhIssue) {
      banner.style.display = 'flex';
      if (bannerIcon) bannerIcon.textContent = '⚖️';
      bannerText.textContent = `رأس المسألة الفقهية الحاكمة: ${readerState.fiqhIssue}`;
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
    let pEscaped = escapeHtml(p);
    // إبراز الكلمات أو النص إذا كان مفتوحاً من نتيجة بحث
    if (readerState.highlightText) {
      const words = readerState.highlightText.split(/\s+/).filter(w => w.length > 3).slice(0, 5);
      words.forEach(w => {
        const cleanW = readerState.showTashkeel ? w : removeTashkeel(w);
        const reg = new RegExp(`(${escapeRegex(cleanW)})`, 'gi');
        pEscaped = pEscaped.replace(reg, `<mark class="reader-highlight">$1</mark>`);
      });
    }
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
  const selectedStr = selection ? selection.toString().trim() : '';
  const tooltip = document.getElementById('readerSelectionTooltip');

  readerState.selectedText = selectedStr;

  if (selectedStr.length > 5 && tooltip) {
    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    tooltip.style.display = 'flex';
    tooltip.style.top = `${rect.top - 8}px`;
    tooltip.style.left = `${rect.left + (rect.width / 2)}px`;
  } else if (tooltip) {
    tooltip.style.display = 'none';
  }
}

// إرسال النص المحدد (أو الصفحة كاملة) إلى نافذة الشات للمناقشة مع النموذج
function sendReaderSelectionToChat() {
  let passage = readerState.selectedText;
  if (!passage) {
    // إذا لم يحدد نصاً، نأخذ مقطعاً من الصفحة
    passage = readerState.rawBody.slice(0, 500).trim();
  }

  if (!passage) {
    showToast('يرجى تحديد نص من الصفحة أولاً');
    return;
  }

  // صياغة السؤال التراثي المحكم
  const partText = readerState.part ? `الجزء: ${readerState.part}` : '';
  const pageText = readerState.pageNum ? `الصفحة: ${readerState.pageNum}` : '';
  const locParts = [partText, pageText].filter(Boolean).join('، ');
  const locCitation = locParts ? ` [${locParts}]` : '';

  const promptMessage = `أرجو شرح وتحرير هذه المسألة التراثية وبيان مذاهب الفقهاء فيها:\n\n«${passage}»\n\n📚 **المصدر:** «${readerState.bookTitle}» للمصنف ${readerState.author}${readerState.deathYear ? ` (ت: ${readerState.deathYear} هـ)` : ''}${locCitation}`;

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

// =============================================================================
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

    // تحديث رأس الحولية أو المسألة الفقهية إذا كشفها استعلام باقة الصفحات
    if (data.annalistic_year) readerState.annalisticYear = data.annalistic_year;
    if (data.fiqh_issue) readerState.fiqhIssue = data.fiqh_issue;
    const banner = document.getElementById('readerContextBanner');
    const bannerText = document.getElementById('readerContextText');
    const bannerIcon = document.getElementById('readerContextIcon');
    if (banner && bannerText) {
      if (readerState.annalisticYear) {
        banner.style.display = 'flex';
        if (bannerIcon) bannerIcon.textContent = '📅';
        bannerText.textContent = `رأس الحولية التاريخية الحاكمة: ${readerState.annalisticYear}`;
      } else if (readerState.fiqhIssue) {
        banner.style.display = 'flex';
        if (bannerIcon) bannerIcon.textContent = '⚖️';
        bannerText.textContent = `رأس المسألة الفقهية الحاكمة: ${readerState.fiqhIssue}`;
      }
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
        let esc = escapeHtml(pr);
        if (isTarget && readerState.highlightText) {
          const words = readerState.highlightText.split(/\s+/).filter(w => w.length > 3).slice(0, 5);
          words.forEach(w => {
            const cleanW = readerState.showTashkeel ? w : removeTashkeel(w);
            const reg = new RegExp(`(${escapeRegex(cleanW)})`, 'gi');
            esc = esc.replace(reg, `<mark class="reader-highlight">$1</mark>`);
          });
        }
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
    
    // التمرير التلقائي للصفحة المستهدفة
    setTimeout(() => {
      const targetEl = bodyContainer.querySelector('.surrounding-page-card.target-page');
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 120);

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

