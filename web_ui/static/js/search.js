// =============================================================================
// منظومة المجتهد - محرك البحث الدلالي (search.js)
// البحث الدلالي، الفلترة الفقهية، وإعادة الترتيب (Reranking)
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        performSearch();
      }
    });
  }

  // دعم الاستعلام المباشر عبر رابط الصفحة (URL Parameters)
  const urlParams = new URLSearchParams(window.location.search);
  const queryParam = urlParams.get('query') || urlParams.get('q');
  const catParam = urlParams.get('category') || urlParams.get('cat');
  const bookParam = urlParams.get('book');
  const poolParam = urlParams.get('pool_size') || urlParams.get('pool');
  const topKParam = urlParams.get('top_k') || urlParams.get('k');

  if (poolParam && document.getElementById('filterResultLimit')) {
    const sel = document.getElementById('filterResultLimit');
    const opt = sel.querySelector(`option[value="${poolParam}"]`);
    if (opt) {
      sel.value = poolParam;
    } else {
      sel.value = 'custom';
      handleResultLimitChange(sel);
      const customInp = document.getElementById('filterResultLimitCustom');
      if (customInp) customInp.value = poolParam;
    }
  }

  if (topKParam && document.getElementById('filterResultLimit')) {
    const sel = document.getElementById('filterResultLimit');
    const opt = sel.querySelector(`option[value="${topKParam}"]`);
    if (opt) {
      sel.value = topKParam;
    } else {
      sel.value = 'custom';
      handleResultLimitChange(sel);
      const customInp = document.getElementById('filterResultLimitCustom');
      if (customInp) customInp.value = topKParam;
    }
  }

  if (queryParam) {
    if (searchInput) searchInput.value = queryParam;
    if (catParam && document.getElementById('filterCategory')) {
      document.getElementById('filterCategory').value = catParam;
    }
    if (bookParam && document.getElementById('filterBookName')) {
      document.getElementById('filterBookName').value = bookParam;
    }
    setTimeout(performSearch, 300);
  }

  // تهيئة حالة زر التبديل للبحث الهجين
  initHybridToggleState();
});

// إدارة وتفعيل / تعطيل نمط البحث الهجين (Dense + BM25)
let isHybridSearchEnabled = true;

function initHybridToggleState() {
  const saved = localStorage.getItem('almojtahed_hybrid_search');
  if (saved !== null) {
    isHybridSearchEnabled = saved === 'true';
  }
  updateHybridToggleUI();
}

function toggleHybridSearchMode() {
  isHybridSearchEnabled = !isHybridSearchEnabled;
  localStorage.setItem('almojtahed_hybrid_search', isHybridSearchEnabled);
  updateHybridToggleUI();
  if (typeof showToast === 'function') {
    if (isHybridSearchEnabled) {
      showToast('تم تفعيل نمط البحث الهجين (Dense + BM25) ⚡');
    } else {
      showToast('تم تفعيل نمط البحث الدلالي الصرف (Dense Vector Only) 🧠');
    }
  }
  // إعادة تشغيل البحث فوراً إذا كان هناك استعلام نشط في شريط البحث
  const q = document.getElementById('searchInput')?.value?.trim();
  const resList = document.getElementById('searchResultsList');
  if (q && resList && resList.children.length > 0 && !resList.querySelector('.search-welcome-card')) {
    performSearch();
  }
}

function updateHybridToggleUI() {
  const btn = document.getElementById('btnToggleHybridSearch');
  const label = document.getElementById('labelHybridToggle');
  const icon = document.getElementById('iconHybridToggle');
  if (!btn || !label) return;

  if (isHybridSearchEnabled) {
    btn.classList.add('is-active');
    btn.classList.remove('is-disabled');
    btn.setAttribute('aria-pressed', 'true');
    btn.title = 'البحث الهجين مفعّل: يدمج الفهم الدلالي للذكاء الاصطناعي مع التطابق اللفظي الصارم (BM25). انقر للتعطيل.';
    label.textContent = 'بحث هجين مفعّل (Dense + BM25)';
    if (icon) icon.setAttribute('data-lucide', 'layers');
  } else {
    btn.classList.remove('is-active');
    btn.classList.add('is-disabled');
    btn.setAttribute('aria-pressed', 'false');
    btn.title = 'البحث الدلالي الصرف مفعّل: يعتمد كلياً على تضمين المتجهات Al-Mojtahed 8B. انقر لتفعيل الدمج الهجين.';
    label.textContent = 'بحث دلالي صرف (Dense Only)';
    if (icon) icon.setAttribute('data-lucide', 'cpu');
  }

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

// معالجة تغيير عدد النتائج المسترجعة
function handleResultLimitChange(selectEl) {
  const customInput = document.getElementById('filterResultLimitCustom');
  if (!customInput) return;
  if (selectEl.value === 'custom') {
    customInput.style.display = 'inline-block';
    if (!customInput.value) customInput.value = '50';
    customInput.focus();
  } else {
    customInput.style.display = 'none';
  }
}

// توفير دوال التوافق القديمة إن استدعيت دون خطأ
function handleRerankTopKChange() {}
function handleUseRerankerToggle() {}


// تنفيذ عملية البحث الدلالي المباشر
async function performSearch() {
  const query = document.getElementById('searchInput').value.trim();
  if (!query) {
    showToast('يرجى كتابة نص أو مسألة للبحث');
    return;
  }

  const category = document.getElementById('filterCategory').value;
  const bookName = document.getElementById('filterBookName').value.trim();
  const deathMax = document.getElementById('filterDeathMax').value.trim();

  // استخراج عدد النتائج المطلوب (Pool Size)
  let poolSize = 50;
  const limitSelect = document.getElementById('filterResultLimit');
  if (limitSelect) {
    if (limitSelect.value === 'custom') {
      const customVal = parseInt(document.getElementById('filterResultLimitCustom')?.value);
      poolSize = !isNaN(customVal) && customVal > 0 ? customVal : 50;
    } else {
      poolSize = parseInt(limitSelect.value) || 50;
    }
  }

  const topK = poolSize;

  const resultsList = document.getElementById('searchResultsList');
  const metaInfo = document.getElementById('searchMetaInfo');
  const btn = document.getElementById('btnExecuteSearch');

  // تعطيل الزر وعرض حالة التحميل
  btn.disabled = true;
  btn.innerHTML = `<span>جارٍ البحث...</span>`;

  resultsList.innerHTML = `
    <div style="text-align: center; padding: 50px 20px; color: var(--text-muted);">
      <div style="display: inline-block; width: 32px; height: 32px; border: 3px solid var(--border-subtle); border-top-color: var(--accent-clay); border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 12px;"></div>
      <p style="font-family: var(--font-amiri); font-size: 18px;">جارٍ استخراج المتجهات وإعادة الترتيب بدقة من 8.14 مليون نص...</p>
    </div>
  `;

  const startTime = performance.now();

  try {
    const activeBooks = (window._searchTabBooks && window._searchTabBooks.length > 0)
      ? window._searchTabBooks
      : (selectedBooksScope && selectedBooksScope.length > 0 ? selectedBooksScope : null);

    const payload = {
      query: query,
      category: (!activeBooks && category) ? category : null,
      book_name: bookName || null,
      selected_books: activeBooks,
      death_max: deathMax ? parseInt(deathMax) : null,
      use_reranker: false,
      use_hybrid: isHybridSearchEnabled,
      pool_size: poolSize,
      top_k: topK
    };

    const res = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      throw new Error(`خطأ في الخادم (${res.status})`);
    }

    const data = await res.json();
    const duration = ((performance.now() - startTime) / 1000).toFixed(2);

    renderSearchResults(data.results || [], query, duration, data);

  } catch (err) {
    console.error('Search error:', err);
    resultsList.innerHTML = `
      <div class="result-card" style="text-align: center; color: var(--text-muted); padding: 30px;">
        <p style="color: #c0392b; font-weight: 600; margin-bottom: 6px;">تعذر استكمال البحث الدلالي</p>
        <p style="font-size: 13px;">${err.message}. يرجى التأكد من تشغيل مخزن المتجهات المحلي.</p>
      </div>
    `;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>ابحث الآن</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 18-6-6 6-6"/></svg>`;
  }
}

// عرض بطاقات النتائج الفقهية مع ترقيمها المباشر
function renderSearchResults(results, query, duration, rawData = {}) {
  const container = document.getElementById('searchResultsList');
  const metaInfo = document.getElementById('searchMetaInfo');
  const countText = document.getElementById('searchStatusText');
  const timingText = document.getElementById('searchTimingText');

  metaInfo.style.display = 'flex';
  const poolCount = rawData.pool_size || rawData.pool_count || results.length;
  const modeLabel = rawData.is_reranked ? ' (هجين: Dense + BM25)' : ' (دلالي متجهات صرف)';
  countText.textContent = `تم العثور على ${results.length} نصاً محققاً ومطابقاً${modeLabel}`;
  timingText.textContent = `زمن البحث: ${duration} ثانية`;

  if (results.length === 0) {
    container.innerHTML = `
      <div class="result-card" style="text-align: center; padding: 40px 20px;">
        <p style="font-family: var(--font-amiri); font-size: 20px; color: var(--text-muted); margin-bottom: 6px;">لم يتم العثور على نتائج مطابقة للشروط المحددة</p>
        <p style="font-size: 13px; color: var(--text-light);">حاول توسيع نطاق البحث أو إزالة بعض الفلاتر.</p>
      </div>
    `;
    return;
  }

  const queryWords = query.split(/\s+/).filter(w => w.length > 2);

  container.innerHTML = results.map((item, idx) => {
    const currentRank = item.rank || (idx + 1);
    const isReranked = !!(item.reranked || item.is_reranked);
    const bookTitle = item.book_title || item.book || 'كتاب تراثي';
    const author = item.author || 'غير معروف';
    const deathYear = (item.death_year && item.death_year !== 99999) ? `(ت: ${item.death_year} هـ)` : (item.death_year === 99999 ? '(معاصر)' : '');
    const category = item.category || 'عام';
    const volume = item.volume ? `جـ: ${item.volume}` : '';
    const page = item.page ? `ص: ${item.page}` : '';
    const chapter = item.chapter || '';
    const score = item.score ? (item.score * 100).toFixed(1) + '%' : '';

    // إبراز الكلمات المفتاحية
    let text = escapeHtml(item.text || item.content || '');
    queryWords.forEach(w => {
      const regex = new RegExp(`(${w})`, 'gi');
      text = text.replace(regex, `<mark style="background-color: var(--accent-light); color: var(--accent-clay); border-radius: 2px; padding: 0 2px;">$1</mark>`);
    });

    return `
      <article class="result-card" id="resCard_${idx}">
        <div class="result-header-row">
          <div class="result-rank-box">
            <span class="rank-pill-current" title="الترتيب الحالي للنتيجة">#${currentRank}</span>
            <div class="result-book-meta" style="margin-right: 8px;">
              <span class="book-title-tag">${escapeHtml(bookTitle)}</span>
              <span class="author-tag">${escapeHtml(author)} ${deathYear}</span>
              <span style="font-size: 11.5px; background: var(--bg-muted); padding: 2px 8px; border-radius: var(--radius-sm); color: var(--text-muted);">${escapeHtml(category)}</span>
            </div>
          </div>
          ${score ? `<span class="score-badge" style="background: rgba(37, 99, 235, 0.08); color: #2563eb; border: 1px solid rgba(37, 99, 235, 0.2);">${isReranked ? 'هجين (متجه + BM25): ' : 'دلالي مباشر: '}${score}</span>` : ''}
        </div>

        ${chapter ? `<div class="result-chapter"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block; vertical-align: middle; margin-left: 4px;"><path d="m9 18 6-6-6-6"/></svg>${escapeHtml(chapter)}</div>` : ''}

        <div class="result-text">${text}</div>

        <div class="result-footer">
          <div>
            ${volume ? `<span>${volume}</span>` : ''}
            ${page ? `<span style="margin-right: 10px;">${page}</span>` : ''}
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn-flat-secondary" onclick="openBookReaderFromSearch(${idx})" style="padding: 4px 10px; font-size: 12.5px; color: var(--text-dark);">
              تصفح في الكتاب الأصلي 📖
            </button>
            <button class="btn-flat-secondary" onclick="verifySearchResultQuote(${idx})" style="padding: 4px 10px; font-size: 12.5px; color: #16a34a;" title="تحقق من مطابقة النص الحرفي في صفحات الشاملة الأصلية عبر أداة MCP">
              تحقق حرفي (MCP) 🔍
            </button>
            <button class="btn-flat-secondary" onclick="copyPassageText(${idx})" style="padding: 4px 10px; font-size: 12.5px;">
              نسخ النص
            </button>
            <button class="btn-flat-secondary" onclick="sendToChat(${idx})" style="padding: 4px 10px; font-size: 12.5px; color: var(--accent-clay);">
              مناقشة في الشات
            </button>
          </div>
        </div>
      </article>
    `;
  }).join('');

  // حفظ النتائج في الذاكرة لتسهيل الوصول إليها عند النسخ أو المناقشة
  window._lastSearchResults = results;
}

// متغير للاحتفاظ بمعلومات النتيجة التي تم فحصها لفتحها في القارئ
let _mcpLastVerifiedItem = null;

function closeMcpVerifyModal() {
  const modal = document.getElementById('mcpVerifyModal');
  if (modal) modal.style.display = 'none';
}

function openBookReaderFromMcp() {
  if (!_mcpLastVerifiedItem) return;
  closeMcpVerifyModal();
  if (typeof openBookReader === 'function') {
    openBookReader({
      rel_path: _mcpLastVerifiedItem.rel_path || '',
      book_title: _mcpLastVerifiedItem.book_title || '',
      part: _mcpLastVerifiedItem.part !== undefined ? _mcpLastVerifiedItem.part : '',
      page_num: _mcpLastVerifiedItem.page_num || null,
      seq: _mcpLastVerifiedItem.seq || null,
      highlight: _mcpLastVerifiedItem.snippet || ''
    });
  }
}

// التحقق من مطابقة النص الحرفي في صفحات الشاملة الأصلية عبر أداة MCP بنافذة خاصة بالثيم
async function verifySearchResultQuote(idx) {
  if (!window._lastSearchResults || !window._lastSearchResults[idx]) return;
  const item = window._lastSearchResults[idx];
  const quote = (item.text || item.content || '').slice(0, 160);
  const book = item.book_title || item.book;
  const pageHint = item.page ? parseInt(item.page, 10) : null;
  const partHint = item.volume ? String(item.volume) : null;

  const modal = document.getElementById('mcpVerifyModal');
  const loading = document.getElementById('mcpVerifyLoading');
  const content = document.getElementById('mcpVerifyContent');
  const bookSpan = document.getElementById('mcpVerifyBook');
  const partSpan = document.getElementById('mcpVerifyPart');
  const pageSpan = document.getElementById('mcpVerifyPage');
  const statusBox = document.getElementById('mcpVerifyStatusBox');
  const statusMsg = document.getElementById('mcpVerifyStatusMsg');
  const statusIcon = document.getElementById('mcpVerifyStatusIcon');
  const iconWrap = document.getElementById('mcpVerifyIcon');
  const snippetBox = document.getElementById('mcpVerifySnippetBox');
  const snippetText = document.getElementById('mcpVerifySnippet');
  const openReaderBtn = document.getElementById('mcpVerifyOpenReaderBtn');

  // تهيئة وعرض النافذة في حالة التحميل
  modal.style.display = 'flex';
  loading.style.display = 'block';
  content.style.display = 'none';
  openReaderBtn.style.display = 'none';

  bookSpan.textContent = book || '—';
  partSpan.textContent = partHint || '1';
  pageSpan.textContent = pageHint || '—';

  try {
    const res = await fetch('/api/mcp/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'verify_quote',
        arguments: {
          book: book,
          quote_text: quote,
          page_hint: pageHint,
          part: partHint
        }
      })
    });
    const data = await res.json();
    loading.style.display = 'none';
    content.style.display = 'block';

    if (data.verified && data.matches && data.matches.length > 0) {
      const match = data.matches[0];
      _mcpLastVerifiedItem = {
        book_title: data.book_title || book,
        part: match.part || partHint,
        page_num: match.page_num || pageHint,
        seq: match.seq || null,
        rel_path: data.rel_path || item.rel_path || null,
        snippet: match.snippet || quote
      };

      bookSpan.textContent = data.book_title || book;
      partSpan.textContent = match.part || '1';
      pageSpan.textContent = match.page_num || (pageHint || '—');

      iconWrap.style.background = 'rgba(22, 163, 74, 0.12)';
      iconWrap.style.color = '#16a34a';
      iconWrap.innerHTML = '<i data-lucide="check-circle-2" style="width: 20px; height: 20px;"></i>';

      statusBox.style.background = 'rgba(22, 163, 74, 0.08)';
      statusBox.style.border = '1px solid rgba(22, 163, 74, 0.25)';
      statusBox.style.color = '#15803d';
      statusIcon.innerHTML = '✅';
      statusMsg.innerHTML = `<strong>تم التحقق الحرفي بنجاح 100%!</strong><br>النص مطابق تماماً بالحرف في الصفحة رقم (<strong>${match.page_num}</strong>) من الجزء (<strong>${match.part || '1'}</strong>) من النسخة الأصلية المحققة.`;

      if (match.snippet) {
        snippetBox.style.display = 'block';
        snippetText.textContent = match.snippet;
      } else {
        snippetBox.style.display = 'none';
      }

      openReaderBtn.style.display = 'inline-flex';
    } else {
      _mcpLastVerifiedItem = null;
      iconWrap.style.background = 'rgba(234, 88, 12, 0.12)';
      iconWrap.style.color = '#ea580c';
      iconWrap.innerHTML = '<i data-lucide="alert-triangle" style="width: 20px; height: 20px;"></i>';

      statusBox.style.background = 'rgba(234, 88, 12, 0.08)';
      statusBox.style.border = '1px solid rgba(234, 88, 12, 0.25)';
      statusBox.style.color = '#c2410c';
      statusIcon.innerHTML = 'ℹ️';
      statusMsg.innerHTML = `<strong>لم يتم العثور على مطابقة حرفية تامة!</strong><br>لم يتطابق النص المقصوص حرفياً مع الصفحات المفحوصة في هذا الموضع، قد يرجع ذلك لاختلاف بسيط في رسم الكلمات أو ضبط النسخة المطبوعة.`;

      snippetBox.style.display = 'none';
      openReaderBtn.style.display = 'none';
    }

    if (window.refreshLucideIcons) window.refreshLucideIcons();
  } catch (err) {
    loading.style.display = 'none';
    content.style.display = 'block';
    iconWrap.style.background = 'rgba(239, 68, 68, 0.12)';
    iconWrap.style.color = '#ef4444';
    iconWrap.innerHTML = '<i data-lucide="x-circle" style="width: 20px; height: 20px;"></i>';

    statusBox.style.background = 'rgba(239, 68, 68, 0.08)';
    statusBox.style.border = '1px solid rgba(239, 68, 68, 0.25)';
    statusBox.style.color = '#b91c1c';
    statusIcon.innerHTML = '⚠️';
    statusMsg.innerHTML = `<strong>تعذر فحص الصفحة:</strong> ${err.message}`;
    snippetBox.style.display = 'none';
    openReaderBtn.style.display = 'none';
    if (window.refreshLucideIcons) window.refreshLucideIcons();
  }
}



// =============================================================================
// إدارة نافذة تحديد نطاق البحث في كتب الشاملة (Search Scope Modal Management)
// =============================================================================

let selectedBooksScope = [];
let catalogBooksCache = [];
let currentScopeCategory = '';
let currentScopeSearchQuery = '';
let scopeModalTarget = 'search'; // 'search' or 'agent'

// فتح نافذة تحديد نطاق البحث (تدعم البحث الدلالي أو تخصيص نطاق الوكيل أو وكلاء المشاريع البحثية)
async function openSearchScopeModal(target = 'search') {
  scopeModalTarget = target;
  const modal = document.getElementById('searchScopeModal');
  if (!modal) return;

  if (target === 'agent') {
    selectedBooksScope = [...(window._currentAgentBooks || [])];
    modal.style.zIndex = '250';
  } else if (target === 'project_subagent') {
    selectedBooksScope = [...(window._activeProjectSubagentBooks || [])];
    modal.style.zIndex = '350';
  } else {
    selectedBooksScope = [...(window._searchTabBooks || selectedBooksScope || [])];
    modal.style.zIndex = '250';
  }

  modal.style.display = 'flex';
  modal.classList.add('open');

  if (catalogBooksCache.length === 0) {
    const listContainer = document.getElementById('scopeBooksList');
    listContainer.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 50px 20px; color: var(--text-muted);">
        <div style="display: inline-block; width: 30px; height: 30px; border: 3px solid var(--border-subtle); border-top-color: var(--accent-clay); border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 10px;"></div>
        <p>جارٍ جلب فهرس كتب الشاملة الكامل (8,589 كتاباً)...</p>
      </div>
    `;

    try {
      const res = await fetch('/api/books');
      if (!res.ok) throw new Error('فشل جلب الكتب');
      catalogBooksCache = await res.json();
    } catch (err) {
      console.error(err);
      listContainer.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; color: #c0392b; padding: 40px;">
          تعذر تحميل فهرس الكتب. يرجى التأكد من تشغيل الخادم.
        </div>
      `;
      return;
    }
  }

  renderScopeBooks();
}

// إغلاق نافذة نطاق البحث
function closeSearchScopeModal() {
  const modal = document.getElementById('searchScopeModal');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('open');
    modal.style.zIndex = '250';
  }
}

// إغلاق عند النقر على الخلفية ومزامنة فلاتر البحث
document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('searchScopeModal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeSearchScopeModal();
    });
  }

  const filterCat = document.getElementById('filterCategory');
  if (filterCat) {
    filterCat.addEventListener('change', () => {
      if (filterCat.value) {
        // إذا اختار قسماً معيناً من القائمة الرئيسية، نلغي أي حصر يدوي بكتب فردية قديمة لمنع التضارب
        window._searchTabBooks = [];
        selectedBooksScope = [];
        const label = document.getElementById('scopeSelectorLabel');
        if (label) label.textContent = 'جميع كتب الشاملة';
        const badge = document.getElementById('scopeSelectedBadge');
        if (badge) badge.style.display = 'none';
        const clearBtn = document.getElementById('btnClearScope');
        if (clearBtn) clearBtn.style.display = 'none';
      }
    });
  }
});

// عرض قائمة الكتب مع الفلترة بالقسم والبحث السريع
function renderScopeBooks() {
  const listContainer = document.getElementById('scopeBooksList');
  if (!listContainer) return;

  const catId = currentScopeCategory ? parseInt(currentScopeCategory) : null;
  const q = currentScopeSearchQuery.trim().toLowerCase();

  const filtered = catalogBooksCache.filter(b => {
    if (catId !== null && b.category_id !== catId) return false;
    if (q) {
      const titleMatch = b.title && b.title.toLowerCase().includes(q);
      const authorMatch = b.author && b.author.toLowerCase().includes(q);
      if (!titleMatch && !authorMatch) return false;
    }
    return true;
  });

  const visibleCountEl = document.getElementById('scopeVisibleCountText');
  const selectedCountEl = document.getElementById('scopeSelectedCountText');
  const applyBadgeEl = document.getElementById('scopeApplyBadge');

  if (visibleCountEl) visibleCountEl.textContent = `المعروض: ${filtered.length} كتاب`;
  if (selectedCountEl) selectedCountEl.textContent = `المحدد: ${selectedBooksScope.length} كتاب`;
  if (applyBadgeEl) applyBadgeEl.textContent = selectedBooksScope.length;

  if (filtered.length === 0) {
    listContainer.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 40px 20px; color: var(--text-muted);">
        <p style="font-size: 16px;">لم يتم العثور على كتب مطابقة لشروط التصفية والبحث.</p>
      </div>
    `;
    return;
  }

  // عرض حتى 600 كتاب لمنع بطء التمرير مع إشعار إذا كان العدد أكبر
  const displaySlice = filtered.slice(0, 600);

  listContainer.innerHTML = displaySlice.map(b => {
    const isSelected = selectedBooksScope.includes(b.title);
    const death = b.death ? `(ت: ${b.death} هـ)` : '';
    const encodedTitle = escapeHtml(b.title);
    return `
      <div class="scope-book-card ${isSelected ? 'selected' : ''}" data-book-title="${encodedTitle}" onclick="toggleScopeBookElement(this)">
        <input type="checkbox" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation(); toggleScopeBookElement(this)">
        <div style="flex: 1; min-width: 0;">
          <div class="scope-book-title">${encodedTitle}</div>
          <div class="scope-book-meta">
            <span>${escapeHtml(b.author)} ${death}</span>
            <span class="scope-cat-tag">${escapeHtml(b.category_name || 'عام')}</span>
          </div>
        </div>
      </div>
    `;
  }).join('') + (filtered.length > 600 ? `
    <div style="grid-column: 1 / -1; text-align: center; padding: 15px; color: var(--text-muted); font-size: 13px;">
      يتم عرض أول 600 كتاب من أصل ${filtered.length}. استخدم حقل التصفية بالاسم للوصول لأي كتاب بدقة.
    </div>
  ` : '');
}

function escapeJsString(str) {
  return (str || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// تبديل اختيار كتاب من خلال عنصره الحاوي مباشرة لمنع أي خطأ ترميز
function toggleScopeBookElement(el) {
  if (!el) return;
  const card = el.classList.contains('scope-book-card') ? el : el.closest('.scope-book-card');
  if (!card) return;
  const title = card.getAttribute('data-book-title');
  if (title) {
    toggleScopeBook(title, card);
  }
}

// تبديل اختيار كتاب محدد
function toggleScopeBook(title, cardEl) {
  const idx = selectedBooksScope.indexOf(title);
  if (idx > -1) {
    selectedBooksScope.splice(idx, 1);
    if (cardEl) {
      cardEl.classList.remove('selected');
      const chk = cardEl.querySelector('input[type="checkbox"]');
      if (chk) chk.checked = false;
    }
  } else {
    selectedBooksScope.push(title);
    if (cardEl) {
      cardEl.classList.add('selected');
      const chk = cardEl.querySelector('input[type="checkbox"]');
      if (chk) chk.checked = true;
    }
  }

  const selectedCountEl = document.getElementById('scopeSelectedCountText');
  const applyBadgeEl = document.getElementById('scopeApplyBadge');
  if (selectedCountEl) selectedCountEl.textContent = `المحدد: ${selectedBooksScope.length} كتاب`;
  if (applyBadgeEl) applyBadgeEl.textContent = selectedBooksScope.length;
}

// تغيير قسم الكتب
function onScopeCategoryChange(catId) {
  currentScopeCategory = catId;
  renderScopeBooks();
}

// تغيير نص البحث في الكتب
function onScopeSearchInput(text) {
  currentScopeSearchQuery = text;
  const clearBtn = document.getElementById('scopeClearFilterBtn');
  if (clearBtn) clearBtn.style.display = text ? 'inline' : 'none';
  renderScopeBooks();
}

function clearScopeFilterText() {
  const inp = document.getElementById('scopeFilterQuery');
  if (inp) {
    inp.value = '';
    onScopeSearchInput('');
  }
}

// تحديد الكل المعروض حالياً
function scopeSelectAllVisible() {
  const catId = currentScopeCategory ? parseInt(currentScopeCategory) : null;
  const q = currentScopeSearchQuery.trim().toLowerCase();

  const filtered = catalogBooksCache.filter(b => {
    if (catId !== null && b.category_id !== catId) return false;
    if (q) {
      const titleMatch = b.title && b.title.toLowerCase().includes(q);
      const authorMatch = b.author && b.author.toLowerCase().includes(q);
      if (!titleMatch && !authorMatch) return false;
    }
    return true;
  });

  filtered.forEach(b => {
    if (!selectedBooksScope.includes(b.title)) {
      selectedBooksScope.push(b.title);
    }
  });

  renderScopeBooks();
  showToast(`تم تحديد ${filtered.length} كتاباً`);
}

// إلغاء تحديد الكل
function scopeDeselectAll() {
  selectedBooksScope = [];
  renderScopeBooks();
  showToast('تم إلغاء التحديد');
}

// تطبيق النطاق على البحث أو على الوكيل
function applySearchScopeSelection() {
  if (scopeModalTarget === 'project_subagent') {
    window._activeProjectSubagentBooks = [...selectedBooksScope];
    if (typeof window.onProjectSubagentScopeApplied === 'function') {
      window.onProjectSubagentScopeApplied([...selectedBooksScope]);
    }
    closeSearchScopeModal();
    showToast(`تم تحديد نطاق كتب الوكيل: ${selectedBooksScope.length > 0 ? selectedBooksScope.length + ' كتب' : 'جميع كتب الشاملة'}`);
    return;
  }

  if (scopeModalTarget === 'agent') {
    window._currentAgentBooks = [...selectedBooksScope];
    const agentLabel = document.getElementById('agentScopeSelectorLabel');
    const agentBadge = document.getElementById('agentScopeSelectedBadge');
    const agentClearBtn = document.getElementById('btnClearAgentScope');

    if (selectedBooksScope.length === 0) {
      if (agentLabel) agentLabel.textContent = 'جميع كتب الشاملة (8,589 كتاباً)';
      if (agentBadge) agentBadge.style.display = 'none';
      if (agentClearBtn) agentClearBtn.style.display = 'none';
    } else if (selectedBooksScope.length === 1) {
      if (agentLabel) agentLabel.textContent = selectedBooksScope[0];
      if (agentBadge) {
        agentBadge.textContent = '1';
        agentBadge.style.display = 'inline-block';
      }
      if (agentClearBtn) agentClearBtn.style.display = 'inline-block';
    } else {
      if (agentLabel) agentLabel.textContent = `محدد: ${selectedBooksScope.length} كتب`;
      if (agentBadge) {
        agentBadge.textContent = selectedBooksScope.length;
        agentBadge.style.display = 'inline-block';
      }
      if (agentClearBtn) agentClearBtn.style.display = 'inline-block';
    }

    closeSearchScopeModal();
    showToast(`تم تحديد نطاق كتب الوكيل: ${selectedBooksScope.length > 0 ? selectedBooksScope.length + ' كتب' : 'جميع الكتب'}`);
    return;
  }

  // الوضع الافتراضي لتبويب البحث الدلالي
  const label = document.getElementById('scopeSelectorLabel');
  const badge = document.getElementById('scopeSelectedBadge');
  const clearBtn = document.getElementById('btnClearScope');
  const filterCat = document.getElementById('filterCategory');

  if (selectedBooksScope.length === 0) {
    window._searchTabBooks = [];
    if (currentScopeCategory) {
      if (filterCat) filterCat.value = currentScopeCategory;
      const catSelect = document.getElementById('scopeCategorySelect');
      const catText = catSelect && catSelect.selectedIndex >= 0 ? catSelect.options[catSelect.selectedIndex].text : '';
      if (label) label.textContent = catText ? `قسم: ${catText}` : 'حسب التصنيف المختار';
      if (badge) badge.style.display = 'none';
      if (clearBtn) clearBtn.style.display = 'inline-block';
      closeSearchScopeModal();
      showToast(`تم تطبيق نطاق القسم: ${catText || currentScopeCategory}`);
      return;
    }
    if (label) label.textContent = 'جميع كتب الشاملة';
    if (badge) badge.style.display = 'none';
    if (clearBtn) clearBtn.style.display = 'none';
  } else if (selectedBooksScope.length === 1) {
    window._searchTabBooks = [...selectedBooksScope];
    if (filterCat) filterCat.value = ''; // تفريغ حقل التصنيف العام لمنع تضارب الفلاتر
    if (label) label.textContent = selectedBooksScope[0];
    if (badge) {
      badge.textContent = '1';
      badge.style.display = 'inline-block';
    }
    if (clearBtn) clearBtn.style.display = 'inline-block';
  } else {
    window._searchTabBooks = [...selectedBooksScope];
    if (filterCat) filterCat.value = ''; // تفريغ حقل التصنيف العام لمنع تضارب الفلاتر
    if (label) label.textContent = `محدد: ${selectedBooksScope.length} كتب`;
    if (badge) {
      badge.textContent = selectedBooksScope.length;
      badge.style.display = 'inline-block';
    }
    if (clearBtn) clearBtn.style.display = 'inline-block';
  }

  closeSearchScopeModal();
  showToast(`تم تطبيق نطاق البحث: ${selectedBooksScope.length > 0 ? selectedBooksScope.length + ' كتب' : 'جميع الكتب'}`);
}

// فتح نافذة تحديد كتب الوكيل
function openAgentSearchScopeModal() {
  openSearchScopeModal('agent');
}

// إلغاء نطاق كتب الوكيل والعودة لجميع كتب الشاملة
function resetAgentSearchScope(event) {
  if (event) event.stopPropagation();
  window._currentAgentBooks = [];
  const agentLabel = document.getElementById('agentScopeSelectorLabel');
  const agentBadge = document.getElementById('agentScopeSelectedBadge');
  const agentClearBtn = document.getElementById('btnClearAgentScope');
  if (agentLabel) agentLabel.textContent = 'جميع كتب الشاملة (8,589 كتاباً)';
  if (agentBadge) agentBadge.style.display = 'none';
  if (agentClearBtn) agentClearBtn.style.display = 'none';
  showToast('تمت إعادة نطاق الوكيل إلى جميع كتب الشاملة');
}

// إلغاء النطاق والعودة لجميع الكتب في البحث الدلالي
function scopeResetToAllBooks() {
  selectedBooksScope = [];
  window._searchTabBooks = [];
  currentScopeCategory = '';
  currentScopeSearchQuery = '';
  const filterCat = document.getElementById('filterCategory');
  if (filterCat) filterCat.value = '';
  const scopeCatSelect = document.getElementById('scopeCategorySelect');
  if (scopeCatSelect) scopeCatSelect.value = '';
  const scopeFilterInp = document.getElementById('scopeFilterQuery');
  if (scopeFilterInp) scopeFilterInp.value = '';
  const label = document.getElementById('scopeSelectorLabel');
  if (label) label.textContent = 'جميع كتب الشاملة';
  const badge = document.getElementById('scopeSelectedBadge');
  if (badge) badge.style.display = 'none';
  const clearBtn = document.getElementById('btnClearScope');
  if (clearBtn) clearBtn.style.display = 'none';
  closeSearchScopeModal();
  showToast('تمت العودة للبحث في جميع كتب الشاملة');
}

// إلغاء النطاق من الزر الصغير في شريط الفلاتر
function resetSearchScope(event) {
  if (event) event.stopPropagation();
  selectedBooksScope = [];
  window._searchTabBooks = [];
  currentScopeCategory = '';
  currentScopeSearchQuery = '';
  const filterCat = document.getElementById('filterCategory');
  if (filterCat) filterCat.value = '';
  const scopeCatSelect = document.getElementById('scopeCategorySelect');
  if (scopeCatSelect) scopeCatSelect.value = '';
  const scopeFilterInp = document.getElementById('scopeFilterQuery');
  if (scopeFilterInp) scopeFilterInp.value = '';
  const label = document.getElementById('scopeSelectorLabel');
  if (label) label.textContent = 'جميع كتب الشاملة';
  const badge = document.getElementById('scopeSelectedBadge');
  if (badge) badge.style.display = 'none';
  const clearBtn = document.getElementById('btnClearScope');
  if (clearBtn) clearBtn.style.display = 'none';
  showToast('تمت العودة للبحث في جميع كتب الشاملة');
}

// نسخ النص إلى الحافظة
function copyPassageText(idx) {
  const item = window._lastSearchResults?.[idx];
  if (!item) return;

  const textToCopy = `«${item.text || item.content}»\n[${item.book_title || item.book} - ${item.author} - ج: ${item.volume || '-'} ص: ${item.page || '-'}]`;

  navigator.clipboard.writeText(textToCopy).then(() => {
    showToast('تم نسخ النص والتوثيق إلى الحافظة');
  }).catch(() => {
    showToast('تعذر النسخ تلقائياً');
  });
}

// إرسال النص مباشرة إلى نافذة الشات للمناقشة في محادثة مستقلة جديدة لمنع التراكم والتداخل
function sendToChat(idx) {
  const item = window._lastSearchResults?.[idx];
  if (!item) return;

  const bookName = (item.book_title || item.book || 'مصدر تراثي').trim();
  const authorName = (item.author || '').trim();
  const locParts = [
    item.volume ? `الجزء: ${item.volume}` : (item.part ? `الجزء: ${item.part}` : ''),
    item.page ? `الصفحة: ${item.page}` : ''
  ].filter(Boolean).join('، ');
  const locCitation = locParts ? ` [${locParts}]` : '';
  const authorCitation = authorName ? ` للمؤلف: ${authorName}` : '';
  const chapterCitation = item.chapter ? ` (باب: ${item.chapter})` : '';

  const promptMessage = `أرجو شرح وتخريج هذا النص ومقارنة أقوال الفقهاء فيه:\n\n«${item.text || item.content}»\n\n📚 **المصدر:** «${bookName}»${authorCitation}${locCitation}${chapterCitation}`;
  const sessionTitle = `مناقشة: ${bookName.slice(0, 32)}`;

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

  showToast('تم فتح محادثة جديدة ونقل النص إلى الشات 💬');
}

// حماية من XSS
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}

window.openAgentSearchScopeModal = openAgentSearchScopeModal;
window.resetAgentSearchScope = resetAgentSearchScope;
window.openSearchScopeModal = openSearchScopeModal;
window.closeSearchScopeModal = closeSearchScopeModal;
window.applySearchScopeSelection = applySearchScopeSelection;
window.resetSearchScope = resetSearchScope;
window.sendToChat = sendToChat;
