// =============================================================================
// منظومة المغني - محرك البحث الدلالي (search.js)
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
});

function searchTabSelectedBooks() {
  const titles = (window._searchTabBooks && window._searchTabBooks.length > 0)
    ? window._searchTabBooks
    : (selectedBooksScope && selectedBooksScope.length > 0 ? selectedBooksScope : null);
  if (!titles || !titles.length) return null;
  const byTitle = {};
  (catalogBooksCache || []).forEach((book) => {
    if (book && book.title != null && book.id != null && byTitle[book.title] == null) {
      byTitle[book.title] = book.id;
    }
  });
  return titles.map((title) => {
    const id = byTitle[title];
    return id != null ? `#${id} ${title}` : title;
  });
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
      <p style="font-family: var(--font-amiri); font-size: 18px;">جارٍ البحث اللفظي في المكتبة حسب النطاق المحدد...</p>
    </div>
  `;

  const startTime = performance.now();

  try {
    const activeBooks = searchTabSelectedBooks();

    const payload = {
      query: query,
      category: (!activeBooks && category) ? category : null,
      book_name: bookName || null,
      selected_books: activeBooks,
      death_max: deathMax ? parseInt(deathMax) : null,
      use_reranker: false,
      use_hybrid: true,
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
        <p style="color: #c0392b; font-weight: 600; margin-bottom: 6px;">تعذر استكمال البحث</p>
        <p style="font-size: 13px;">${err.message}. يرجى المحاولة مرة أخرى.</p>
      </div>
    `;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>ابحث الآن</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 18-6-6 6-6"/></svg>`;
  }
}

async function runSearchDiagnose() {
  const box = document.getElementById('searchDiagTest');
  if (!box) return;
  box.textContent = 'جارٍ الفحص الكامل (قد يستغرق ثواني أول مرة)…';
  try {
    const r = await fetch('/api/search/diagnose');
    const d = await r.json();
    const t = d.bridge_test || {};
    box.innerHTML = t.status === 'ok'
      ? `✅ بحث تجريبي في جسر الشاملة: ناجح (${t.hits} نتيجة) خلال ${t.seconds} ثانية.`
      : `⚠️ بحث تجريبي في جسر الشاملة: ${t.status || 'فشل'}${t.message ? ` — <span dir="ltr" style="font-size:11px;">${t.message}</span>` : ''} خلال ${t.seconds ?? '—'} ثانية.`;
  } catch (e) {
    box.textContent = 'تعذّر الفحص.';
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
  // تسمية صادقة لمصدر النتائج: المصدر يأتي من الخادم ولا يُخترع هنا.
  const src = String(rawData.source || '');
  let modeLabel;
  if (rawData.is_reranked || rawData.is_hybrid) modeLabel = ' (هجين: دلالي + لفظي)';
  else if (/فهرس المكتبة|المراسي|لفظي/.test(src)) modeLabel = ' (بحث لفظي في فهرس المكتبة)';
  else if (/متجهات|دلالي/.test(src)) modeLabel = ' (دلالي متجهات صرف)';
  else modeLabel = src ? ` (${src})` : '';
  window._lastSearchQuery = query || '';
  countText.textContent = `تم العثور على ${results.length} نصاً محققاً ومطابقاً${modeLabel}`;
  timingText.textContent = `زمن البحث: ${duration} ثانية`;

  if (results.length === 0) {
    const d = rawData.diagnostics || {};
    const b = d.bridge || {};
    const le = (b.last_error || {}).message || '';
    const diagLine = (label, val) => `<div style="display:flex;justify-content:space-between;gap:12px;padding:2px 0;"><span>${label}</span><b dir="auto">${val}</b></div>`;
    container.innerHTML = `
      <div class="result-card" style="text-align: center; padding: 40px 20px;">
        <p style="font-family: var(--font-amiri); font-size: 20px; color: var(--text-muted); margin-bottom: 6px;">لم يتم العثور على نتائج مطابقة للشروط المحددة</p>
        <p style="font-size: 13px; color: var(--text-light);">حاول توسيع نطاق البحث أو إزالة بعض الفلاتر.</p>
        <div style="max-width: 560px; margin: 18px auto 0; text-align: right; font-size: 12.5px; color: var(--text-muted); background: var(--bg-surface-elevated, #f6f1e7); border: 1px solid var(--border-subtle); border-radius: 10px; padding: 12px 16px;">
          <div style="font-weight: 700; margin-bottom: 6px;">حالة البحث على هذا الجهاز</div>
          ${diagLine('مصدر المكتبة', d.library_source || '—')}
          ${diagLine('الشاملة مكتشفة', d.shamela_found ? 'نعم' : 'لا')}
          ${d.shamela_root ? diagLine('مسارها', `<span dir="ltr" style="font-size:11px;">${d.shamela_root}</span>`) : ''}
          ${diagLine('جسر بحث الشاملة (Java/Lucene)', b.jvm_found ? `جاهز (${b.lucene_jars} مكتبة)` : 'غير جاهز — لم يُعثر على JRE/Lucene الشاملة')}
          ${le ? diagLine('آخر خطأ من الجسر', `<span dir="ltr" style="font-size:11px;">${le}</span>`) : ''}
          ${diagLine('فهرس المكتبة المحلي', d.fts_available ? `جاهز (${d.fts_shards} شظية)` : 'غير مبني')}
          <div id="searchDiagTest" style="margin-top: 8px;"></div>
          <button type="button" class="btn-secondary-action" style="margin-top: 10px;" onclick="runSearchDiagnose()">فحص حالة البحث الآن</button>
        </div>
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
  if (typeof enhanceProjectCitationsWithBookReader === 'function') {
    enhanceProjectCitationsWithBookReader(container);
  }
  // نافذة «بحث في النتائج» مفتوحة: إعادة التحديد على النتائج الجديدة تلقائيًا
  refreshResultsSearchIfOpen();
}

// =============================================================================
// 🔭 بحث في نتائج البحث المعروضة: نسخة مطابقة لنافذة «بحث في الإجابة» —
// نافذة عائمة قابلة للسحب، تظليل تلقائي فوري أثناء الكتابة، عدّادات،
// وقائمة جمل يقفز منها الباحث إلى الموضع، مع سابق/تالٍ.
// =============================================================================
let _resultsSearch = { marks: [], current: -1 };

function _rsNormChar(ch) {
  if (/[\u064B-\u0652\u0670\u0640]/.test(ch)) return '';
  if ('إأآٱ'.includes(ch)) return 'ا';
  if (ch === 'ى') return 'ي';
  if (ch === 'ة') return 'ه';
  if (ch === 'ؤ') return 'و';
  if (ch === 'ئ') return 'ي';
  return ch;
}
function _rsNormalize(s) { return (s || '').split('').map(_rsNormChar).join(''); }

function _ensureResultsSearchModal() {
  if (document.getElementById('resultsSearchModal')) return;
  const st = document.createElement('style');
  st.textContent = 'mark.res-hit{background:#ffe58a;color:inherit;padding:0 1px;border-radius:3px;} mark.res-hit.res-current{background:#ff9d45;outline:2px solid #e07b1f;}';
  document.head.appendChild(st);
  const d = document.createElement('div');
  d.id = 'resultsSearchModal';
  d.style.cssText = 'display:none;position:fixed;inset:0;z-index:9999;background:transparent;direction:rtl;pointer-events:none;';
  d.innerHTML = `
    <div id="resultsSearchPanel" style="pointer-events:auto;position:absolute;top:7vh;left:50%;transform:translateX(-50%);width:min(640px,94vw);background:var(--bg-surface,#fff);border-radius:14px;box-shadow:0 18px 50px rgba(0,0,0,0.35);padding:16px 18px;max-height:84vh;display:flex;flex-direction:column;">
      <div id="resultsSearchDragHandle" title="اسحب من هذا الشريط لتحريك النافذة ومشاهدة التظليل في النتائج" style="display:flex;justify-content:space-between;align-items:center;gap:10px;cursor:move;touch-action:none;user-select:none;-webkit-user-select:none;">
        <strong style="font-size:15px;">🔭 بحث في نتائج البحث <span style="font-size:11px;opacity:0.65;font-weight:400;">(قابلة للسحب ⠿)</span></strong>
        <button type="button" class="btn-msg-export" onclick="closeResultsSearch()">إغلاق ✕</button>
      </div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;">
        <input id="resultsSearchInput" type="text" placeholder="اكتب حرفًا أو كلمة أو جملة للبحث داخل النتائج المعروضة..." style="flex:1;min-width:220px;padding:9px 12px;border:1px solid var(--border-subtle,#ccc);border-radius:9px;font-size:14px;" oninput="runResultsSearch()" onkeydown="if(event.key==='Enter'){event.preventDefault();stepResultsSearch(1);}">
        <button type="button" class="btn-msg-export" onclick="stepResultsSearch(-1)">▲ السابق</button>
        <button type="button" class="btn-msg-export" onclick="stepResultsSearch(1)">▼ التالي</button>
      </div>
      <label style="margin-top:8px;font-size:12.5px;display:flex;gap:6px;align-items:center;cursor:pointer;">
        <input id="resultsSearchFlex" type="checkbox" checked onchange="runResultsSearch()">
        بحث مرن: تجاهل التشكيل والهمزات والألف المقصورة والتاء المربوطة
      </label>
      <div id="resultsSearchStats" style="margin-top:9px;font-size:13px;line-height:1.9;color:var(--accent-gold,#9a6b1f);background:rgba(184,115,51,0.07);border:1px solid var(--border-subtle,#e2d8c3);border-radius:9px;padding:7px 11px;">اكتب عبارة البحث وستُظلَّل مواضعها في النتائج تلقائيًا مع عدّاداتها هنا.</div>
      <div id="resultsSearchList" style="margin-top:10px;overflow-y:auto;display:flex;flex-direction:column;gap:6px;"></div>
    </div>`;
  document.body.appendChild(d);
  const panel = d.querySelector('#resultsSearchPanel');
  const handle = d.querySelector('#resultsSearchDragHandle');
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

function openResultsSearch() {
  _ensureResultsSearchModal();
  _clearResultsHighlights();
  _resultsSearch = { marks: [], current: -1 };
  const m = document.getElementById('resultsSearchModal');
  m.style.display = 'block';
  const inp = document.getElementById('resultsSearchInput');
  if (inp) { inp.focus(); if (inp.value.trim().length >= 2) runResultsSearch(); }
}
function closeResultsSearch() {
  _clearResultsHighlights();
  const m = document.getElementById('resultsSearchModal');
  if (m) m.style.display = 'none';
  _resultsSearch = { marks: [], current: -1 };
}
function _clearResultsHighlights() {
  const content = document.getElementById('searchResultsList');
  if (content) {
    content.querySelectorAll('mark.res-hit').forEach(mk => {
      const parent = mk.parentNode;
      if (parent) { parent.replaceChild(document.createTextNode(mk.textContent), mk); parent.normalize(); }
    });
  }
  _resultsSearch.marks = []; _resultsSearch.current = -1;
}
function refreshResultsSearchIfOpen() {
  const m = document.getElementById('resultsSearchModal');
  if (!m || m.style.display === 'none') return;
  const inp = document.getElementById('resultsSearchInput');
  if (inp && inp.value.trim().length >= 2) runResultsSearch();
}
function runResultsSearch() {
  _clearResultsHighlights();
  const stats = document.getElementById('resultsSearchStats');
  const results = document.getElementById('resultsSearchList');
  const q = (document.getElementById('resultsSearchInput')?.value || '').trim();
  const flex = !!document.getElementById('resultsSearchFlex')?.checked;
  if (results) results.innerHTML = '';
  if (!q || q.length < 2) { if (stats) stats.textContent = 'اكتب حرفين على الأقل للبحث داخل النتائج المعروضة.'; return; }
  const content = document.getElementById('searchResultsList');
  if (!content || !content.querySelector('.result-card')) { if (stats) stats.textContent = 'لا نتائج معروضة الآن — نفّذ بحثًا أولًا.'; return; }

  const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      if (node.parentElement && node.parentElement.closest('button')) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const nq = flex ? _rsNormalize(q) : q;
  let total = 0;
  for (const node of nodes) {
    const text = node.nodeValue;
    let hay = text, map = null;
    if (flex) {
      hay = ''; map = [];
      for (let i = 0; i < text.length; i++) { const nc = _rsNormChar(text[i]); if (nc) { hay += nc; map.push(i); } }
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
      mk.className = 'res-hit'; mk.textContent = text.slice(s, e);
      frag.appendChild(mk);
      last = e;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
  }
  _resultsSearch.marks = Array.from(content.querySelectorAll('mark.res-hit'));

  // العدّادات والجمل من متون النتائج وحدها لا من أزرار البطاقات وترويساتها
  let sentHits = [], markCursor = 0;
  content.querySelectorAll('.result-text').forEach(el => {
    const sentences = (el.textContent || '').split(/(?<=[.!؟؛:])\s+|\n+/).map(s => s.trim()).filter(Boolean);
    for (const s of sentences) {
      const ns = flex ? _rsNormalize(s) : s;
      let c = 0, p = 0;
      while (true) { const h = ns.indexOf(nq, p); if (h < 0) break; c++; p = h + Math.max(nq.length, 1); }
      if (c) { sentHits.push({ sentence: s, count: c, firstMark: markCursor }); markCursor += c; }
    }
  });
  const wordsCount = q.split(/\s+/).filter(Boolean).length;
  if (stats) {
    stats.innerHTML = total
      ? `وُجدت العبارة <strong>${total}</strong> مرة في النتائج المعروضة | عبارة البحث: ${q.length} حرفًا و${wordsCount} ${wordsCount === 1 ? 'كلمة' : 'كلمات'} | وردت في <strong>${sentHits.length}</strong> جملة من متون النتائج | تنقّل بالسابق/التالي أو اضغط أي جملة للقفز إلى موضعها.`
      : 'لا مواضع لهذه العبارة في النتائج المعروضة. جرّب البحث المرن أو عبارة أقصر.';
  }
  if (results && sentHits.length) {
    results.innerHTML = sentHits.slice(0, 40).map((h, i) =>
      `<button type="button" onclick="jumpToResultsMark(${h.firstMark})" style="text-align:right;padding:8px 11px;border:1px solid var(--border-subtle,#ddd);border-radius:9px;background:transparent;cursor:pointer;font-size:12.5px;line-height:1.8;">
         <span style="color:var(--accent-gold,#9a6b1f);font-weight:700;">${i + 1}.</span> ${escapeHtml(h.sentence.slice(0, 220))}${h.sentence.length > 220 ? '…' : ''} <span style="opacity:0.7;">(${h.count}×)</span>
       </button>`).join('');
  }
  if (_resultsSearch.marks.length) jumpToResultsMark(0);
}
function jumpToResultsMark(i) {
  const content = document.getElementById('searchResultsList');
  const marks = content ? Array.from(content.querySelectorAll('mark.res-hit')) : [];
  _resultsSearch.marks = marks;
  if (!marks.length) return;
  _resultsSearch.current = ((i % marks.length) + marks.length) % marks.length;
  marks.forEach((mk, j) => mk.classList.toggle('res-current', j === _resultsSearch.current));
  marks[_resultsSearch.current].scrollIntoView({ behavior: 'smooth', block: 'center' });
  const stats = document.getElementById('resultsSearchStats');
  if (stats && marks.length) stats.innerHTML = stats.innerHTML.replace(/\| الموضع الحالي:.*$/, '') + ` | الموضع الحالي: ${_resultsSearch.current + 1} من ${marks.length}`;
}
function stepResultsSearch(dir) { jumpToResultsMark((_resultsSearch.current < 0 ? 0 : _resultsSearch.current) + dir); }

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
      highlight: window._lastSearchQuery || _mcpLastVerifiedItem.snippet || ''
    });
  }
}

// التحقق من مطابقة النص الحرفي في صفحات الشاملة الأصلية عبر أداة MCP بنافذة خاصة بالثيم
async function verifySearchResultQuote(idx) {
  if (!window._lastSearchResults || !window._lastSearchResults[idx]) return;
  const item = window._lastSearchResults[idx];
  return openMcpLiteralVerify({
    book: item.book_title || item.book || item.title,
    quote: (item.text || item.content || '').slice(0, 160),
    page: item.page ? parseInt(item.page, 10) : null,
    part: item.volume ? String(item.volume) : null,
    rel_path: item.rel_path || ''
  });
}

async function openMcpLiteralVerify({ book, quote, page, part, rel_path }) {
  const pageHint = page ? parseInt(page, 10) : null;
  const partHint = part ? String(part) : null;
  const quoteText = (quote || '').slice(0, 160);

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
          quote_text: quoteText,
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
        rel_path: data.rel_path || rel_path || null,
        snippet: match.snippet || quoteText
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
      if (data.error) {
        statusMsg.innerHTML = `<strong>تعذر فحص الصفحة:</strong> ${data.error}`;
      }
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
window.openMcpLiteralVerify = openMcpLiteralVerify;
window.verifySearchResultQuote = verifySearchResultQuote;



// =============================================================================
// إدارة نافذة تحديد نطاق البحث في كتب الشاملة (Search Scope Modal Management)
// =============================================================================

let selectedBooksScope = [];
let catalogBooksCache = [];
let currentScopeCategory = '';
let currentScopeSearchQuery = '';
let currentScopeDeathMax = null;
let scopeModalTarget = 'search'; // 'search' or 'agent'

function parseScopeDeathYear(value) {
  const normalized = String(value || '')
    .replace(/[٠-٩]/g, (digit) => '٠١٢٣٤٥٦٧٨٩'.indexOf(digit))
    .replace(/[۰-۹]/g, (digit) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(digit))
    .replace(/[^\d]/g, '');
  const year = parseInt(normalized, 10);
  return Number.isFinite(year) && year > 0 ? year : null;
}

function bookWithinScopeDeath(book, limit) {
  if (!limit) return true;
  const year = Number(book && book.death);
  return Number.isFinite(year) && year > 0 && year !== 99999 && year <= limit;
}

function scopeBooksMatchingFilters() {
  const catId = currentScopeCategory ? parseInt(currentScopeCategory, 10) : null;
  const q = currentScopeSearchQuery.trim().toLowerCase();
  const deathLimit = currentScopeDeathMax;
  return catalogBooksCache.filter((book) => {
    if (catId !== null && book.category_id !== catId) return false;
    if (!bookWithinScopeDeath(book, deathLimit)) return false;
    if (!q) return true;
    const titleMatch = book.title && book.title.toLowerCase().includes(q);
    const authorMatch = book.author && book.author.toLowerCase().includes(q);
    return titleMatch || authorMatch;
  });
}

// فتح نافذة تحديد نطاق البحث (تدعم البحث الدلالي أو تخصيص نطاق الوكيل أو وكلاء المشاريع البحثية)
async function openSearchScopeModal(target = 'search') {
  scopeModalTarget = target;
  const modal = document.getElementById('searchScopeModal');
  if (!modal) return;

  if (target === 'agent') {
    selectedBooksScope = [...(window._currentAgentBooks || [])];
    if (window._rdAssistantMode) modal.style.setProperty('z-index', '210000', 'important');
    else modal.style.zIndex = '250';
  } else if (target === 'architect_books') {
    selectedBooksScope = [];
    currentScopeCategory = '';
    currentScopeSearchQuery = '';
    const scopeCatSelect = document.getElementById('scopeCategorySelect');
    if (scopeCatSelect) scopeCatSelect.value = '';
    const scopeFilterInp = document.getElementById('scopeFilterQuery');
    if (scopeFilterInp) scopeFilterInp.value = '';
    currentScopeDeathMax = null;
    const scopeDeathInp = document.getElementById('scopeDeathMax');
    if (scopeDeathInp) scopeDeathInp.value = '';
    modal.style.zIndex = '800';
  } else if (target === 'project_subagent') {
    selectedBooksScope = [...(window._activeProjectSubagentBooks || [])];
    modal.style.zIndex = '350';
  } else if (target === 'selection_research') {
    selectedBooksScope = [...(window._selectionResearchBooks || [])];
    modal.style.zIndex = '420';
  } else if (target === 'ms_agents') {
    selectedBooksScope = [...(window._msAgentBookTitles || [])];
    modal.style.setProperty('z-index', '200000', 'important');
  } else if (target === 'ms_style') {
    selectedBooksScope = [...(window._msStyleBookTitles || [])];
    // فوق كل النوافذ (توصية المدقق 4000 وقارئ الكتب 100500) رغم قاعدة CSS ذات !important
    modal.style.setProperty('z-index', '200000', 'important');
  } else if (target === 'ms_compare') {
    selectedBooksScope = window._msCompareBookTitle ? [window._msCompareBookTitle] : [];
    modal.style.setProperty('z-index', '200000', 'important');
  } else if (target === 'ms_group') {
    selectedBooksScope = [...(window._msGroupCurrentBooks || [])];
    modal.style.setProperty('z-index', '200000', 'important');
  } else if (target === 'critique') {
    selectedBooksScope = [...(window._critiqueBookTitles || [])];
    modal.style.setProperty('z-index', '200000', 'important');
  } else if (target === 'rd_assistant') {
    selectedBooksScope = [...(window._rdAssistantBookTitles || [])];
    modal.style.setProperty('z-index', '200000', 'important');
  } else {
    selectedBooksScope = [...(window._searchTabBooks || selectedBooksScope || [])];
    modal.style.zIndex = '250';
  }

  modal.style.display = 'flex';
  modal.classList.add('open');
  const applyLabel = document.getElementById('scopeApplyLabel');
  if (applyLabel) applyLabel.textContent = target === 'architect_books' ? 'اعتماد' : 'تطبيق النطاق';

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
    modal.style.removeProperty('z-index');
    modal.style.zIndex = '250';
  }
  const applyLabel = document.getElementById('scopeApplyLabel');
  if (applyLabel) applyLabel.textContent = 'تطبيق النطاق';
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

  const filtered = scopeBooksMatchingFilters();

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
            <span>#${b.id} · ${escapeHtml(b.author)} ${death}</span>
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

function onScopeDeathInput(value) {
  currentScopeDeathMax = parseScopeDeathYear(value);
  renderScopeBooks();
}

// تحديد الكل المعروض حالياً
function scopeSelectAllVisible() {
  const filtered = scopeBooksMatchingFilters();

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
  if (scopeModalTarget === 'rd_assistant') {
    window._rdAssistantBookTitles = [...selectedBooksScope];
    if (typeof window.onRdAssistantBooks === 'function') window.onRdAssistantBooks([...selectedBooksScope]);
    closeSearchScopeModal();
    showToast(selectedBooksScope.length ? `حُددت ${selectedBooksScope.length} كتب لمساعد القراءة` : 'مساعد القراءة: المكتبة كاملة');
    return;
  }

  if (scopeModalTarget === 'critique') {
    window._critiqueBookTitles = [...selectedBooksScope];
    if (typeof window.onCritiqueBooks === 'function') window.onCritiqueBooks([...selectedBooksScope]);
    closeSearchScopeModal();
    showToast(selectedBooksScope.length ? `حُددت ${selectedBooksScope.length} كتب لنطاق النقد والمقارنة` : 'نطاق النقد: جميع كتب الشاملة');
    return;
  }

  if (scopeModalTarget === 'architect_books') {
    if (!selectedBooksScope.length) {
      showToast('حدد كتاباً واحداً على الأقل ثم اعتمد');
      return;
    }
    const books = selectedBooksScope.map(title => {
      const found = (catalogBooksCache || []).find(b => b.title === title);
      return { id: found && found.id != null ? found.id : '', title };
    });
    closeSearchScopeModal();
    if (typeof window.onArchitectExtraBooks === 'function') window.onArchitectExtraBooks(books);
    return;
  }

  if (scopeModalTarget === 'project_subagent') {
    window._activeProjectSubagentBooks = [...selectedBooksScope];
    if (typeof window.onProjectSubagentScopeApplied === 'function') {
      window.onProjectSubagentScopeApplied([...selectedBooksScope]);
    }
    closeSearchScopeModal();
    showToast(`تم تحديد نطاق كتب الوكيل: ${selectedBooksScope.length > 0 ? selectedBooksScope.length + ' كتب' : 'جميع كتب الشاملة'}`);
    return;
  }

  if (scopeModalTarget === 'selection_research') {
    window._selectionResearchBooks = [...selectedBooksScope];
    if (typeof window.onSelectionResearchBooks === 'function') {
      window.onSelectionResearchBooks([...selectedBooksScope]);
    }
    closeSearchScopeModal();
    return;
  }

  if (scopeModalTarget === 'ms_agents') {
    window._msAgentBookTitles = [...selectedBooksScope];
    if (typeof window.onMsAgentBooks === 'function') {
      window.onMsAgentBooks([...selectedBooksScope]);
    }
    closeSearchScopeModal();
    showToast(selectedBooksScope.length ? `حُددت ${selectedBooksScope.length} كتب مظان لبحث الوكلاء ومسحهم` : 'بحث الوكلاء في كتب الأصول وكتب المؤلف الافتراضية');
    return;
  }

  if (scopeModalTarget === 'ms_style') {
    window._msStyleBookTitles = [...selectedBooksScope];
    if (typeof window.onMsStyleBooks === 'function') {
      window.onMsStyleBooks([...selectedBooksScope]);
    }
    closeSearchScopeModal();
    showToast(selectedBooksScope.length ? `حُددت ${selectedBooksScope.length} كتب لمسح الأسلوب` : 'مسح الأسلوب في كل كتب المؤلف');
    return;
  }

  if (scopeModalTarget === 'ms_compare') {
    window._msCompareBookTitle = selectedBooksScope[0] || '';
    if (typeof window.onMsCompareBook === 'function') {
      window.onMsCompareBook(selectedBooksScope[0] || '', selectedBooksScope.length);
    }
    closeSearchScopeModal();
    return;
  }

  if (scopeModalTarget === 'ms_group') {
    if (typeof window.onMsGroupBooks === 'function') {
      window.onMsGroupBooks([...selectedBooksScope]);
    }
    closeSearchScopeModal();
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
  if (scopeModalTarget === 'architect_books') {
    selectedBooksScope = [];
    renderScopeBooks();
    closeSearchScopeModal();
    return;
  }
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
  currentScopeDeathMax = null;
  const scopeDeathInp = document.getElementById('scopeDeathMax');
  if (scopeDeathInp) scopeDeathInp.value = '';
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
  currentScopeDeathMax = null;
  const scopeDeathInp = document.getElementById('scopeDeathMax');
  if (scopeDeathInp) scopeDeathInp.value = '';
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
