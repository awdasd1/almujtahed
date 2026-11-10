/* قسم «النصوص» داخل تبويب «نشر»: موضوع → بحث في الكتب المحددة بنموذج ثابت
   (Gemini 3.8 Flash) يستخرج فائدة نفيسة مختصرة منسوبة لقائلها ومذيلة بمصدرها،
   جاهزة للنسخ أو النشر النصي في مواقع التواصل. مستنسخ من قسم التصاميم بكل
   أدواته (نطاق فنون + تصفح كتب + بحث الشاملة) وبحالة مستقلة تمامًا. */
const TEXTS_STORE_KEY = 'almujtahed_texts_v1';
const TEXT_KIND_STATE_KEY = 'almujtahed_texts_kinds_v1';
const TEXT_BOOKS_STATE_KEY = 'almujtahed_texts_books_v1';
let textMessages = [];
let textBusy = false;
let textsInitDone = false;
let textKindState = { auto: true, selected: [] };
let textBooksState = { added: [], removed: [] };

function loadTextKindState() {
  try {
    const raw = localStorage.getItem(TEXT_KIND_STATE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      textKindState = { auto: parsed.auto !== false, selected: Array.isArray(parsed.selected) ? parsed.selected : [] };
    }
  } catch (e) { /* افتراضي */ }
  return textKindState;
}
function saveTextKindState() {
  try { localStorage.setItem(TEXT_KIND_STATE_KEY, JSON.stringify(textKindState)); } catch (e) {}
}
function loadTextBooksState() {
  try {
    const raw = localStorage.getItem(TEXT_BOOKS_STATE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      textBooksState = { added: Array.isArray(parsed.added) ? parsed.added : [], removed: Array.isArray(parsed.removed) ? parsed.removed : [] };
    }
  } catch (e) { /* افتراضي */ }
  return textBooksState;
}
function saveTextBooksState() {
  try { localStorage.setItem(TEXT_BOOKS_STATE_KEY, JSON.stringify(textBooksState)); } catch (e) {}
}

function textScopeBasisBooks() {
  loadTextKindState();
  const kinds = designKindsList();
  if (!textKindState.auto && textKindState.selected.length) {
    return [...new Set(kinds.filter(k => textKindState.selected.includes(k.id)).flatMap(k => k.books || []))];
  }
  return designBooksUnion();
}

function effectiveTextBooks(baseBooks) {
  loadTextBooksState();
  const removed = new Set(textBooksState.removed);
  const seen = new Set();
  const result = [];
  [...(baseBooks || []), ...textBooksState.added].forEach(book => {
    if (!removed.has(book) && !seen.has(book)) { seen.add(book); result.push(book); }
  });
  return result;
}

function resolveTextScope(topic) {
  loadTextKindState();
  const kinds = designKindsList();
  if (!textKindState.auto) {
    const chosen = textKindState.selected.length
      ? kinds.filter(kind => textKindState.selected.includes(kind.id))
      : kinds;
    if (chosen.length) {
      return {
        label: (textKindState.selected.length
          ? chosen.map(kind => `${kind.icon} ${kind.label}`).join(' + ')
          : 'كل الفنون') + ' (يدوي)',
        books: effectiveTextBooks([...new Set(chosen.flatMap(kind => kind.books || []))]),
        angles: chosen.map(kind => kind.angle).join('؛ ')
      };
    }
  }
  const classified = classifyDesignKinds(topic);
  classified.books = effectiveTextBooks(classified.books);
  return classified;
}

function updateTextKindButton() {
  if (typeof updateTextBooksButton === 'function') updateTextBooksButton();
  const btn = document.getElementById('textKindBtn');
  if (!btn) return;
  const kinds = designKindsList();
  if (textKindState.auto || !textKindState.selected.length) {
    btn.textContent = textKindState.auto ? '🔍 نطاق البحث: تلقائي' : '🎯 نطاق البحث: يدوي (كل الفنون)';
    return;
  }
  const chosen = kinds.filter(k => textKindState.selected.includes(k.id));
  const bookCount = new Set(chosen.flatMap(k => k.books || [])).size;
  btn.textContent = `🎯 نطاق البحث: ${chosen.map(k => k.label).join(' + ')} (${bookCount} كتابًا)`;
}

function initTextKindPicker() {
  loadTextKindState();
  const grid = document.getElementById('textKindGrid');
  const autoBox = document.getElementById('textKindAuto');
  const btn = document.getElementById('textKindBtn');
  const panel = document.getElementById('textKindPanel');
  if (!grid || !btn || !panel) return;
  if (autoBox) autoBox.checked = !!textKindState.auto;
  grid.innerHTML = designKindsList().map(kind =>
    `<label class="design-kind-item"><input type="checkbox" value="${kind.id}" ${textKindState.selected.includes(kind.id) ? 'checked' : ''} ${textKindState.auto ? 'disabled' : ''}><span>${kind.icon} ${kind.label} (${(kind.books || []).length})</span></label>`
  ).join('');
  updateTextKindButton();
  if (btn.dataset.wired) return;
  btn.dataset.wired = '1';
  btn.addEventListener('click', (event) => { event.stopPropagation(); panel.hidden = !panel.hidden; });
  panel.addEventListener('click', (event) => event.stopPropagation());
  document.addEventListener('click', () => { panel.hidden = true; });
  if (autoBox) autoBox.addEventListener('change', () => {
    textKindState.auto = autoBox.checked;
    saveTextKindState();
    grid.querySelectorAll('input[type="checkbox"]').forEach(box => { box.disabled = textKindState.auto; });
    updateTextKindButton();
  });
  grid.addEventListener('change', () => {
    textKindState.selected = [...grid.querySelectorAll('input[type="checkbox"]:checked')].map(box => box.value);
    saveTextKindState();
    updateTextKindButton();
  });
}

function setTextBookSelected(book, selected) {
  loadTextBooksState();
  if (selected) {
    textBooksState.removed = textBooksState.removed.filter(b => b !== book);
    if (!textScopeBasisBooks().includes(book) && !textBooksState.added.includes(book)) textBooksState.added.push(book);
  } else {
    textBooksState.added = textBooksState.added.filter(b => b !== book);
    if (!textBooksState.removed.includes(book)) textBooksState.removed.push(book);
  }
  saveTextBooksState();
  renderTextBooksChips();
  renderTextBooksList();
  document.querySelectorAll('#textBooksLibrary input[data-book]').forEach(box => {
    if (box.getAttribute('data-book') === book) box.checked = selected;
  });
  updateTextBooksButton();
}

function setAllTextBooks(selected) {
  loadTextBooksState();
  const all = designBooksUnion();
  if (selected) {
    const basis = new Set(textScopeBasisBooks());
    textBooksState.removed = textBooksState.removed.filter(b => !all.includes(b));
    textBooksState.added = [...new Set([...textBooksState.added, ...all.filter(b => !basis.has(b))])];
  } else {
    textBooksState.added = [];
    textBooksState.removed = [...all];
  }
  saveTextBooksState();
  renderTextBooksChips();
  renderTextBooksList();
  const effective = effectiveTextBooks(textScopeBasisBooks());
  document.querySelectorAll('#textBooksLibrary input[data-book]').forEach(box => {
    box.checked = effective.includes(box.getAttribute('data-book'));
  });
  updateTextBooksButton();
  if (typeof showToast === 'function') showToast(selected ? `حُدّدت كل كتب القائمة المعتمدة (${all.length} كتابًا)` : 'أُلغي تحديد كل الكتب');
}

function selectAllLibraryTextBooks() {
  const box = document.getElementById('textBooksLibrary');
  if (!box) return;
  const titles = [...box.querySelectorAll('input[data-book]')].map(b => b.getAttribute('data-book')).filter(Boolean);
  if (!titles.length) return;
  loadTextBooksState();
  const basis = new Set(textScopeBasisBooks());
  textBooksState.removed = textBooksState.removed.filter(b => !titles.includes(b));
  titles.forEach(t => { if (!basis.has(t) && !textBooksState.added.includes(t)) textBooksState.added.push(t); });
  saveTextBooksState();
  renderTextBooksChips();
  renderTextBooksList();
  box.querySelectorAll('input[data-book]').forEach(b => { b.checked = true; });
  updateTextBooksButton();
  if (typeof showToast === 'function') showToast(`أُضيفت كل نتائج الشاملة الظاهرة (${titles.length} كتابًا) إلى نطاق البحث`);
}

function renderTextBooksChips() {
  const chips = document.getElementById('textBooksChips');
  const count = document.getElementById('textBooksSelectedCount');
  if (!chips) return;
  const effective = effectiveTextBooks(textScopeBasisBooks());
  if (count) count.textContent = effective.length;
  chips.innerHTML = effective.length
    ? effective.map(b => `<span class="design-book-sel-chip">${escapeHtml(b)}<button type="button" data-remove-book="${escapeHtml(b)}" title="حذف من نطاق البحث" aria-label="حذف ${escapeHtml(b)}">×</button></span>`).join('')
    : '<span class="design-books-chips-empty">لا كتب محددة — حدّد كتابًا من القائمة بالأسفل</span>';
}

function renderTextBooksList() {
  const list = document.getElementById('textBooksList');
  if (!list) return;
  const query = normalizeDesignText(document.getElementById('textBooksSearch')?.value || '');
  const words = query.split(/\s+/).filter(Boolean);
  const effective = effectiveTextBooks(textScopeBasisBooks());
  const html = designKindsList().map(kind => {
    const books = (kind.books || []).filter(b => !words.length || words.every(w => normalizeDesignText(b).includes(w)));
    if (!books.length) return '';
    return `<div class="design-books-kind-head">${kind.icon} ${kind.label}</div>` + books.map(b =>
      `<label class="design-kind-item"><input type="checkbox" data-book="${escapeHtml(b)}" ${effective.includes(b) ? 'checked' : ''}><span>${escapeHtml(b)}</span></label>`
    ).join('');
  }).join('');
  list.innerHTML = html || '<div class="design-books-chips-empty">لا نتائج مطابقة في القائمة المعتمدة</div>';
}

let textLibrarySearchTimer = null;
let textLibrarySearchToken = 0;

function renderTextBooksLibrary() {
  const box = document.getElementById('textBooksLibrary');
  if (!box) return;
  const query = (document.getElementById('textBooksSearch')?.value || '').trim();
  if (query.length < 2) { box.innerHTML = ''; return; }
  box.innerHTML = '<div class="design-books-kind-head">📚 من مكتبة الشاملة</div><div class="design-books-chips-empty">جارٍ البحث في المكتبة...</div>';
  if (textLibrarySearchTimer) clearTimeout(textLibrarySearchTimer);
  textLibrarySearchTimer = setTimeout(async () => {
    const token = ++textLibrarySearchToken;
    try {
      const resp = await fetch(`/api/books/search?q=${encodeURIComponent(query)}&limit=30`);
      const data = await resp.json().catch(() => ({}));
      if (token !== textLibrarySearchToken) return;
      const books = Array.isArray(data.books) ? data.books : [];
      if (!books.length) {
        box.innerHTML = '<div class="design-books-kind-head">📚 من مكتبة الشاملة</div><div class="design-books-chips-empty">لا نتائج في مكتبة الشاملة لهذا البحث — جرّب كلمات أقل أو عنوانًا أدق</div>';
        return;
      }
      const effective = effectiveTextBooks(textScopeBasisBooks());
      box.innerHTML = '<div class="design-books-kind-head">📚 من مكتبة الشاملة — حدّد كتابًا لإضافته إلى نطاق البحث <button type="button" class="design-mini-btn" data-lib-select-all>☑️ تحديد الكل</button></div>' + books.map(b => {
        const meta = [b.author, (b.death && b.death !== '—') ? `ت ${b.death}` : '', b.category_name].filter(Boolean).join(' — ');
        return `<label class="design-kind-item"><input type="checkbox" data-book="${escapeHtml(b.title)}" ${effective.includes(b.title) ? 'checked' : ''}><span>${escapeHtml(b.title)}${meta ? ` <small style="color:var(--text-muted)">${escapeHtml(meta)}</small>` : ''}</span></label>`;
      }).join('');
    } catch (e) {
      if (token !== textLibrarySearchToken) return;
      box.innerHTML = '<div class="design-books-kind-head">📚 من مكتبة الشاملة</div><div class="design-books-chips-empty">تعذر البحث في المكتبة الآن</div>';
    }
  }, 280);
}

function updateTextBooksButton() {
  const btn = document.getElementById('textBooksBtn');
  if (!btn) return;
  const count = effectiveTextBooks(textScopeBasisBooks()).length;
  loadTextBooksState();
  const customized = textBooksState.added.length > 0 || textBooksState.removed.length > 0;
  btn.textContent = `📚 تصفح الكتب (${count} محددًا${customized ? ' • معدّلة يدويًا ✋' : ''})`;
}

function initTextBooksPicker() {
  loadTextBooksState();
  const btn = document.getElementById('textBooksBtn');
  const panel = document.getElementById('textBooksPanel');
  if (!btn || !panel) return;
  renderTextBooksChips();
  renderTextBooksList();
  updateTextBooksButton();
  if (btn.dataset.wired) return;
  btn.dataset.wired = '1';
  btn.addEventListener('click', (event) => {
    event.stopPropagation();
    panel.hidden = !panel.hidden;
    if (!panel.hidden) { renderTextBooksChips(); renderTextBooksList(); updateTextBooksButton(); }
  });
  panel.addEventListener('click', (event) => event.stopPropagation());
  document.addEventListener('click', () => { panel.hidden = true; });
  const chips = document.getElementById('textBooksChips');
  if (chips) chips.addEventListener('click', (event) => {
    const removeBtn = event.target.closest('[data-remove-book]');
    if (removeBtn) setTextBookSelected(removeBtn.getAttribute('data-remove-book'), false);
  });
  const list = document.getElementById('textBooksList');
  if (list) list.addEventListener('change', (event) => {
    const box = event.target.closest('input[data-book]');
    if (box) setTextBookSelected(box.getAttribute('data-book'), box.checked);
  });
  const library = document.getElementById('textBooksLibrary');
  if (library) library.addEventListener('change', (event) => {
    const box = event.target.closest('input[data-book]');
    if (box) setTextBookSelected(box.getAttribute('data-book'), box.checked);
  });
  if (library) library.addEventListener('click', (event) => {
    if (event.target.closest('[data-lib-select-all]')) selectAllLibraryTextBooks();
  });
  const search = document.getElementById('textBooksSearch');
  if (search) search.addEventListener('input', () => { renderTextBooksList(); renderTextBooksLibrary(); });
  const reset = document.getElementById('textBooksReset');
  if (reset) reset.addEventListener('click', () => {
    textBooksState = { added: [], removed: [] };
    saveTextBooksState();
    renderTextBooksChips();
    renderTextBooksList();
    updateTextBooksButton();
    if (typeof showToast === 'function') showToast('أُعيد تعيين تحديد الكتب إلى نطاق الفنون');
  });
  const selectAll = document.getElementById('textBooksSelectAll');
  if (selectAll) selectAll.addEventListener('click', () => setAllTextBooks(true));
  const selectNone = document.getElementById('textBooksSelectNone');
  if (selectNone) selectNone.addEventListener('click', () => setAllTextBooks(false));
}

const TEXT_CHARLIMIT_KEY = 'almujtahed_texts_charlimit_v1';

function textCharLimit() {
  const sel = document.getElementById('textCharLimit');
  if (!sel) return 250;
  if (sel.value === 'custom') {
    const v = parseInt(document.getElementById('textCharLimitCustom')?.value || '', 10);
    return (v >= 50 && v <= 10000) ? v : 250;
  }
  return parseInt(sel.value, 10) || 250;
}

function initTextCharLimit() {
  const sel = document.getElementById('textCharLimit');
  const custom = document.getElementById('textCharLimitCustom');
  if (!sel) return;
  try {
    const saved = JSON.parse(localStorage.getItem(TEXT_CHARLIMIT_KEY) || 'null');
    if (saved && saved.sel) {
      sel.value = saved.sel;
      if (custom && saved.custom) custom.value = saved.custom;
    }
  } catch (e) { /* افتراضي */ }
  const sync = () => {
    if (custom) custom.hidden = sel.value !== 'custom';
    try { localStorage.setItem(TEXT_CHARLIMIT_KEY, JSON.stringify({ sel: sel.value, custom: custom ? custom.value : '' })); } catch (e) {}
  };
  if (!sel.dataset.wired) {
    sel.dataset.wired = '1';
    sel.addEventListener('change', sync);
    if (custom) custom.addEventListener('change', sync);
  }
  sync();
}

function textSystemPrompt(charLimit, booksList) {
  const limit = charLimit || 250;
  const bookNames = (Array.isArray(booksList) ? booksList : []).filter(Boolean);
  return [
    'أنت محرّر فوائد تراثية لقسم «النصوص» في تطبيق المجتهد للبحث التراثي.',
    'مهمتك الوحيدة: استخراج فائدة واحدة نفيسة حول موضوع المستخدم من الشواهد المرفقة من الكتب المحددة فقط — لا تخترع أقوالًا ولا تنسب قولًا لغير قائله ولا تخرج عن الشواهد.',
    `قيد صارم لا يُتجاوز مطلقًا: لا تستعمل إلا الشواهد المرفقة المستخرجة من الكتب المحددة التالية حصرًا${bookNames.length ? ': ' + bookNames.join('؛ ') : ''}. ممنوع منعًا باتًا أي قول أو معلومة من خارج هذه الشواهد أو من ذاكرتك ومعارفك العامة، وممنوع نسبة قول إلى كتاب أو مؤلف غير وارد فيها.`,
    'أخرج النص جاهزًا للنشر في مواقع التواصل بهذا القالب حرفيًا، بلا أي مقدمة أو خاتمة من عندك:',
    'القالب: [عنوان] ثم سطر فارغ ثم [متن الفائدة] ثم سطر فارغ ثم [📚 المصادر: تتبعها نقاط المصادر] ثم [الوسوم].',
    'تنبيه صارم: متن الفائدة المنقول أو المستفاد هو قلب النص — إياك أن تحذفه أو أن تكتفي بالعنوان والمصادر والوسوم؛ إخراج بلا متن مرفوض تمامًا.',
    'السطر الأول: عنوان قصير جذاب للفائدة (٣-٧ كلمات) بلا كلمة «عنوان» وبلا ترقيم زخرفي.',
    'ثم فراغ سطر، ثم متن الفائدة: إن وجدت في الشواهد عبارة منقولة بعينها فانقلها حرفيًا بين علامتي تنصيص «...» ومسبوقة بنسبتها: قال فلان رحمه الله: «...». وإن كانت الفائدة معنى مستخلصًا فصُغه بأسلوبك الفصيح الموجز وصدّره بما يدل على الاستفادة مثل: ومما يُستفاد: ... مع نسبة المعنى لصاحبه إن عُرف.',
    'إيجاز صارم: متن الفائدة بين ٤٠ و٩٠ كلمة، لغة فصيحة راقية، جمل قصيرة مؤثرة صالحة للتداول.',
    'ثم قسم المصادر معدودًا بنقاط: سطر مستقل «📚 المصادر:» ثم نقطة لكل كتاب أخذتَ منه الفائدة فعلًا، تبدأ بشرطة وبصيغة: - «اسم الكتاب» — اسم المؤلف — والجزء والصفحة كما يظهران في الشاهد بصيغة (ج٢، ص١٤٥) متى توفّرا في الشاهد. لا تذكر كتابًا لم تستعمله، وإياك أن تخترع جزءًا أو صفحة غير موجودين في الشاهد.',
    `حد الحروف الصارم: النص كاملًا بكل سطوره — العنوان والمتن والمصادر والوسوم وفواصل الأسطر — لا يتجاوز ${limit} حرفًا أبدًا (لأن بعض المنصات كإكس ترفض ما زاد). عدّ الحروف قبل الإخراج، وإن طال الاقتباس اختر أقصر عبارة دالة أو لخّص المعنى بأسلوبك حتى تلتزم بالحد دون حذف النسبة والمصادر.`,
    'ثم سطر أخير: ٣ إلى ٥ وسوم عربية متصلة بالموضوع تبدأ بـ # ومفصولة بمسافات، مثل: #فائدة #تراث',
    'إن لم تجد في الشواهد فائدة مباشرة في الموضوع فاستخرج أقرب فائدة إليه وصرّح في متنها بأنها في معنى الموضوع، ولا تدّعِ غير ذلك.'
  ].join('\n');
}

function enrichTextSource(text, witnesses) {
  /* تثبيت الجزء والصفحة في نقاط المصادر من بيانات الشاهد الفعلية — لا من ذاكرة النموذج */
  const rows = (witnesses || []).filter(w => w && w.title);
  if (!rows.length) return text;
  const norm = (s) => normalizeDesignText(String(s || '')).replace(/[«»"()\-—–:]/g, ' ').replace(/\s+/g, ' ').trim();
  const bookText = (w) => {
    const parts = [`«${w.title}»`];
    if (w.author) parts.push(w.author + (w.death_year ? ` (ت ${w.death_year})` : ''));
    const loc = [];
    if (w.part) loc.push(`ج${w.part}`);
    if (w.page) loc.push(`ص${w.page}`);
    if (loc.length) parts.push(loc.join('، '));
    return parts.join(' — ');
  };
  const format = (w) => `📚 المصادر:\n- ${bookText(w)}`;
  const matchWitness = (line) => {
    const match = line.match(/«([^»]+)»/);
    const wanted = norm(match ? match[1] : '');
    return rows.find(w => { const t = norm(w.title); return wanted && (t.includes(wanted) || wanted.includes(t)); })
      || rows.find(w => norm(line).includes(norm(w.title)));
  };
  const lines = String(text).split('\n');
  const srcIdx = lines.findIndex(l => l.includes('المصدر'));
  if (srcIdx >= 0) {
    // أسلوب النقاط: ثبّت كل نقطة من شاهدها المطابق
    let i = srcIdx + 1;
    let fixedAny = false;
    while (i < lines.length) {
      const trimmed = lines[i].trim();
      if (!trimmed) { i++; continue; }
      if (!/^[-–•*·]/.test(trimmed)) break;
      const witness = matchWitness(trimmed);
      if (witness) { lines[i] = `- ${bookText(witness)}`; fixedAny = true; }
      i++;
    }
    if (fixedAny) return lines.join('\n');
    // أسلوب السطر الواحد القديم: حوّله إلى عنوان ونقطة مثبّتة
    const witness = matchWitness(lines[srcIdx]);
    if (witness) {
      lines[srcIdx] = format(witness);
      return lines.join('\n');
    }
    return text;
  }
  const tagIdx = lines.findIndex(l => l.trim().startsWith('#'));
  if (tagIdx >= 0) lines.splice(tagIdx, 0, '', format(rows[0]));
  else lines.push('', format(rows[0]));
  return lines.join('\n');
}

function loadTextMessages() {
  try {
    const raw = localStorage.getItem(TEXTS_STORE_KEY);
    textMessages = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(textMessages)) textMessages = [];
  } catch (e) { textMessages = []; }
}
function saveTextMessages() {
  try { localStorage.setItem(TEXTS_STORE_KEY, JSON.stringify(textMessages.slice(-30))); } catch (e) {}
}

function textFullText(msg) {
  return msg.text || '';
}

function renderTextMessages() {
  const box = document.getElementById('textMessages');
  if (!box) return;
  if (!textMessages.length) {
    box.innerHTML = '<div class="design-empty">مثال: «استخرج فائدة نفيسة عن الصحبة الصالحة» — ستأتيك فائدة مختصرة موثقة بقائلها ومصدرها جاهزة للنسخ أو النشر.</div>';
    return;
  }
  box.innerHTML = textMessages.map((msg, idx) => {
    if (msg.role === 'user') {
      return `<div class="design-msg design-msg-user"><div class="design-bubble">${escapeHtml(msg.text || '')}</div></div>`;
    }
    const books = (msg.books || []).slice(0, 8).map(b => `<span class="design-book-chip">${escapeHtml(b)}</span>`).join('');
    const durChip = msg.duration_s != null
      ? `<span class="design-chip">⏱️ مدة الاستخراج: ${fmtDesignDuration(msg.duration_s)}</span>` : '';
    const publishChip = msg.publish?.status
      ? `<span class="design-chip">${msg.publish.status === 'scheduled' ? '🗓️' : '📤'} ${escapeHtml(msg.publish.label || msg.publish.status)}</span>` : '';
    const charCount = (msg.text || '').length;
    const overLimit = msg.char_limit && charCount > msg.char_limit;
    const charChip = `<span class="design-chip" ${overLimit ? 'style="color:#b3261e;border-color:#b3261e66;font-weight:700"' : ''}>🔢 ${charCount} حرفًا${msg.char_limit ? ` / حد ${msg.char_limit}` : ''}${overLimit ? ' — تجاوز الحد!' : ''}</span>`;
    const bodyHtml = escapeHtml(msg.text || '').replace(/(📚 المصادر?:[^\n]*)/g, '<span class="design-text-source">$1</span>');
    return `<div class="design-msg design-msg-assistant"><div class="design-card">
      <div class="design-card-head">
        <div class="design-card-info">
          ${msg.title ? `<span class="design-title">✍️ ${escapeHtml(msg.title)}</span>` : ''}
          ${msg.discipline ? `<span class="design-chip">🔍 ${escapeHtml(msg.discipline)}</span>` : ''}
          ${durChip}${charChip}${publishChip}
        </div>
        <div class="design-card-actions">
          <button type="button" class="design-mini-btn" data-text-action="copy" data-idx="${idx}">📋 نسخ النص</button>
          <button type="button" class="design-mini-btn" data-text-action="share" data-idx="${idx}">🔗 مشاركة</button>
          <button type="button" class="design-mini-btn" data-text-action="publish" data-idx="${idx}">📤 نشر</button>
          <button type="button" class="design-mini-btn" data-text-action="archive" data-idx="${idx}">🗄️ أرشفة</button>
        </div>
      </div>
      <div class="design-text-body">${bodyHtml}</div>
      ${books ? `<div class="design-books">📚 من كتب: ${books}</div>` : ''}
    </div></div>`;
  }).join('');
  box.scrollTop = box.scrollHeight;
}

function setTextStatus(text) {
  const box = document.getElementById('textMessages');
  if (!box) return;
  let el = document.getElementById('textStatusBubble');
  if (!text) { if (el) el.remove(); return; }
  if (!el) {
    el = document.createElement('div');
    el.id = 'textStatusBubble';
    el.className = 'design-msg design-msg-assistant';
    box.appendChild(el);
  }
  el.innerHTML = `<div class="design-status">⏳ ${escapeHtml(text)} <span class="design-timer" id="textTimerTick">0:00</span></div>`;
  box.scrollTop = box.scrollHeight;
}

let textTimerId = null;
let textTimerStart = 0;
function startTextTimer(label) {
  textTimerStart = Date.now();
  setTextStatus(label);
  if (textTimerId) clearInterval(textTimerId);
  textTimerId = setInterval(() => {
    const el = document.getElementById('textTimerTick');
    if (el) el.textContent = fmtDesignDuration((Date.now() - textTimerStart) / 1000);
  }, 250);
}
function stopTextTimer() {
  if (textTimerId) { clearInterval(textTimerId); textTimerId = null; }
  setTextStatus('');
}

async function loadTextBalance() {
  const el = document.getElementById('textBalance');
  if (!el) return;
  try {
    let apiKey = '';
    try { apiKey = readProviderKeys().openrouter || ''; } catch (e) {}
    const resp = await fetch(`/api/openrouter/credits?api_key=${encodeURIComponent(apiKey)}`);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || '');
    const remUsd = Number(data.remaining_credits_usd);
    const remSar = Number(data.remaining_credits_sar);
    if (isNaN(remUsd)) throw new Error('بيانات رصيد ناقصة');
    el.textContent = `💰 الرصيد الحالي: $${remUsd.toFixed(2)} | ${remSar.toFixed(2)} ﷼`;
  } catch (e) {
    el.textContent = '💰 الرصيد الحالي: تعذر الجلب';
  }
}

function isValidBenefit(text) {
  if (!text || !text.includes('المصدر')) return false;
  const lines = text.split('\n').map(s => s.trim()).filter(Boolean);
  const srcIdx = lines.findIndex(l => l.includes('المصدر'));
  if (srcIdx < 1) return false;
  const body = lines.slice(1, srcIdx).join(' ').replace(/\s+/g, ' ').trim();
  return body.length >= 60;
}

async function runTextGeneration(topic, scope) {
  const books = scope.books.length ? scope.books : designBooksUnion();
  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) {}
  const apiKey = savedKeys.openrouter || '';
  const startedAt = Date.now();
  startTextTimer(`فُحص الطلب: ${scope.label} — يبحث Gemini 3.8 Flash في ${books.length} كتابًا ويستخرج الفائدة...`);
  const requestBenefit = async (extraInstruction) => {
    const chatResp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: DESIGN_TEXT_MODEL,
        provider: 'openrouter',
        api_key: apiKey,
        library_only: true,
        library_query: topic.slice(0, 800),
        selected_books: books,
        extraction_capacity: 10,
        witness_limit: 10,
        context_tokens: 64000,
        messages: [{ role: 'user', content: `موضوع الفائدة: ${topic}\nاستخرج الفائدة الآن وفق تعليماتك.${extraInstruction || ''}` }],
        system_prompt: textSystemPrompt(limit, books) + (scope.angles ? `\nزاوية تركيز هذا الطلب بحسب فنّه المصنَّف (${scope.label}): ${scope.angles} — ركّز اختيار الفائدة على هذه الزاوية.` : ''),
        temperature: 0.3,
        providers: savedKeys,
        agent_group: null
      })
    });
    const chatData = await chatResp.json().catch(() => ({}));
    if (!chatResp.ok) throw new Error(chatData.detail || 'تعذر استخراج الفائدة');
    return {
      text: String(chatData.reply || '').replace(/```[a-z]*|```/gi, '').trim(),
      witnesses: chatData.witnesses || []
    };
  };
  const limit = textCharLimit();
  let result = await requestBenefit('');
  const problemsOf = (t) => {
    const probs = [];
    if (!isValidBenefit(t)) probs.push('تنبيه إلزامي: لا تحذف متن الفائدة أبدًا؛ أخرج القالب كاملًا: عنوان، ثم متن الفائدة (المنقول حرفيًا بين «...» منسوبًا لقائله «قال فلان رحمه الله»)، ثم قسم «📚 المصادر:» منقّطًا بالكتب المستعملة فعلًا وبالجزء والصفحة، ثم الوسوم.');
    if (t.length > limit) probs.push(`تنبيه إلزامي: نصك السابق بلغ ${t.length} حرفًا والحد الأقصى ${limit} حرفًا للنص كاملًا — أعد الاستخراج أقصر: اختر عبارة منقولة أقصر أو لخّص المعنى، والتزم بالحد التزامًا صارمًا.`);
    return probs;
  };
  const problems = problemsOf(result.text);
  if (problems.length) {
    // النموذج أحيانًا يكتفي بالعنوان والمصدر أو يطيل فوق حد المنصة — إعادة واحدة مشددة
    setTextStatus('يُعاد ضبط الفائدة (قالب كامل وضمن حد الحروف)...');
    result = await requestBenefit('\n' + problems.join('\n'));
  }
  const chatData = { witnesses: result.witnesses };
  const text = enrichTextSource(result.text, chatData.witnesses);
  if (text.length < 40) throw new Error('جاءت الفائدة فارغة أو قصيرة — أعد المحاولة');
  const witnessBooks = [...new Set((chatData.witnesses || []).map(w => w.book_title || w.title || w.book || '').filter(Boolean))];
  const firstLine = text.split('\n').map(s => s.trim()).filter(Boolean)[0] || 'فائدة نفيسة';
  textMessages.push({
    role: 'assistant',
    text,
    title: firstLine.replace(/^#+\s*/, '').slice(0, 90),
    discipline: scope.label,
    duration_s: Math.round((Date.now() - startedAt) / 1000),
    books: witnessBooks,
    witnesses: (chatData.witnesses || []).slice(0, 10),
    char_limit: limit
  });
  saveTextMessages();
  stopTextTimer();
  renderTextMessages();
  loadTextBalance();
}

async function submitTextTopic(event) {
  if (event) event.preventDefault();
  if (textBusy) return;
  const input = document.getElementById('textIdeaInput');
  const topic = (input?.value || '').trim();
  if (topic.length < 3) { if (typeof showToast === 'function') showToast('اكتب موضوع الفائدة أولًا'); return; }
  const scope = resolveTextScope(topic);
  if (!scope.books.length) {
    if (typeof showToast === 'function') showToast('لا كتب في نطاق البحث — أضف كتابًا واحدًا على الأقل من «📚 تصفح الكتب»');
    return;
  }
  const userMsg = { role: 'user', text: topic };
  textMessages.push(userMsg);
  saveTextMessages();
  renderTextMessages();
  input.value = '';
  textBusy = true;
  const btn = document.getElementById('textSendBtn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ جارٍ الاستخراج...'; }
  try {
    await runTextGeneration(topic, scope);
    const reqIdx = textMessages.indexOf(userMsg);
    if (reqIdx >= 0) {
      textMessages.splice(reqIdx, 1);
      saveTextMessages();
      renderTextMessages();
    }
  } catch (err) {
    stopTextTimer();
    if (typeof showToast === 'function') showToast(err.message || 'تعذر استخراج الفائدة');
    const box = document.getElementById('textMessages');
    if (box) {
      const el = document.createElement('div');
      el.className = 'design-msg design-msg-assistant';
      el.innerHTML = `<div class="design-status design-status-error">⚠️ ${escapeHtml(err.message || 'تعذر استخراج الفائدة')}</div>`;
      box.appendChild(el);
      box.scrollTop = box.scrollHeight;
    }
  } finally {
    textBusy = false;
    if (btn) { btn.disabled = false; btn.textContent = '✍️ استخراج الفائدة'; }
  }
}

async function onTextCardAction(event) {
  const btn = event.target.closest('[data-text-action]');
  if (!btn) return;
  const idx = Number(btn.getAttribute('data-idx'));
  const msg = textMessages[idx];
  if (!msg) return;
  const action = btn.getAttribute('data-text-action');
  if (action === 'copy') {
    try {
      await navigator.clipboard.writeText(textFullText(msg));
      if (typeof showToast === 'function') showToast('نُسخ النص كاملًا بمصدره ووسومه');
    } catch (e) {
      const ta = document.createElement('textarea');
      ta.value = textFullText(msg);
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); if (typeof showToast === 'function') showToast('نُسخ النص'); } catch (err) {}
      ta.remove();
    }
  } else if (action === 'share') {
    const text = textFullText(msg);
    if (navigator.share) {
      try { await navigator.share({ text }); } catch (e) { /* أُلغي */ }
    } else {
      try { await navigator.clipboard.writeText(text); if (typeof showToast === 'function') showToast('نُسخ النص للمشاركة'); } catch (e) {}
    }
  } else if (action === 'publish') {
    if (typeof window.openDesignTextPublish === 'function') {
      window.openDesignTextPublish(textFullText(msg), (publishObj) => {
        if (publishObj) {
          msg.publish = publishObj;
          saveTextMessages();
          renderTextMessages();
        }
      });
    }
  } else if (action === 'archive') {
    textMessages.splice(idx, 1);
    saveTextMessages();
    renderTextMessages();
    if (typeof showToast === 'function') showToast('أُرشفت الفائدة من المحادثة');
  }
}

function switchPublishSection(which) {
  const designsBtn = document.getElementById('publishSectionDesignsBtn');
  const textsBtn = document.getElementById('publishSectionTextsBtn');
  const designsSec = document.getElementById('publishDesignsSection');
  const textsSec = document.getElementById('publishTextsSection');
  const isTexts = which === 'texts';
  if (designsSec) designsSec.hidden = isTexts;
  if (textsSec) textsSec.hidden = !isTexts;
  if (designsBtn) designsBtn.classList.toggle('is-active', !isTexts);
  if (textsBtn) textsBtn.classList.toggle('is-active', isTexts);
  try { localStorage.setItem('almujtahed_publish_section_v1', isTexts ? 'texts' : 'designs'); } catch (e) {}
  if (isTexts && typeof loadTextBalance === 'function') loadTextBalance();
}

function initTextsTab() {
  loadTextMessages();
  renderTextMessages();
  loadTextBalance();
  initTextKindPicker();
  initTextBooksPicker();
  initTextCharLimit();
  // نافذة النشر مشتركة وتسكن جذر الصفحة (نقلها designs.js) حتى تظهر فوق كل التبويبات
  const publishOverlay = document.getElementById('designPublishOverlay');
  if (publishOverlay && publishOverlay.parentElement !== document.body) document.body.appendChild(publishOverlay);
  const designsBtn = document.getElementById('publishSectionDesignsBtn');
  const textsBtn = document.getElementById('publishSectionTextsBtn');
  if (designsBtn && !designsBtn.dataset.wired) {
    designsBtn.dataset.wired = '1';
    designsBtn.addEventListener('click', () => switchPublishSection('designs'));
  }
  if (textsBtn && !textsBtn.dataset.wired) {
    textsBtn.dataset.wired = '1';
    textsBtn.addEventListener('click', () => switchPublishSection('texts'));
  }
  let savedSection = 'designs';
  try { savedSection = localStorage.getItem('almujtahed_publish_section_v1') || 'designs'; } catch (e) {}
  switchPublishSection(savedSection === 'texts' ? 'texts' : 'designs');
  if (textsInitDone) return;
  textsInitDone = true;
  const messagesBox = document.getElementById('textMessages');
  if (messagesBox) messagesBox.addEventListener('click', onTextCardAction);
  const form = document.getElementById('textComposer');
  if (form) form.addEventListener('submit', submitTextTopic);
  const balanceBtn = document.getElementById('textBalanceBtn');
  if (balanceBtn) balanceBtn.addEventListener('click', loadTextBalance);
  const clearBtn = document.getElementById('textClearBtn');
  if (clearBtn) clearBtn.addEventListener('click', () => {
    textMessages = [];
    saveTextMessages();
    renderTextMessages();
    if (typeof showToast === 'function') showToast('مُسحت محادثة النصوص');
  });
}

window.initTextsTab = initTextsTab;
window.submitTextTopic = submitTextTopic;
