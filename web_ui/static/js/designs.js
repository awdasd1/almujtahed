/* تبويب «تصاميم»: فكرة قصيرة → بحث في كتب «تعليق وشرح مختصر» المعتمدة
   بنموذج ثابت (Gemini 3.8 Flash) يصوغ توجيه صورة بهوية المجتهد →
   توليد الصورة بنموذج ثابت عبر OpenRouter وختمها بشعار المجتهد. */
const DESIGN_TEXT_MODEL = 'google/gemini-3.8-flash';
const DESIGNS_STORE_KEY = 'almujtahed_designs_v1';
let designMessages = [];
let designBusy = false;
let designsInitDone = false;

function designBooksUnion() {
  const books = new Set();
  try {
    (SELECTION_RESEARCH_KINDS || []).forEach(kind => (kind.books || []).forEach(b => books.add(b)));
  } catch (e) { /* chat.js لم يُحمّل بعد */ }
  return [...books];
}

/* فحص الطلب وتصنيفه إلى فنّه: كلمات مفتاحية مرجحة لكل فن من فنون
   «تعليق وشرح مختصر»، فيُحصر البحث في كتب الفن الغالب (أو فنّين
   متقاربين) بدل الكتب كلها — دقة أعلى وبحث أسرع. */
const DESIGN_KIND_KEYWORDS = {
  tafsir: ['تفسير', 'قوله تعالى', 'سورة', 'المفسر', 'تأويل الآية', 'آيات القرآن', 'سبب النزول'],
  fiqh: ['فقه', 'حكم شرعي', 'الصلاة', 'الصيام', 'الزكاة', 'الحج', 'الطلاق', 'الزواج', 'البيع', 'الميراث', 'الطهارة', 'المذهب', 'المالكية', 'الشافعية', 'الحنفية', 'الحنابلة', 'مسألة فقهية', 'العبادات', 'المعاملات', 'الأحكام'],
  aqeeda: ['عقيدة', 'التوحيد', 'الإيمان والكفر', 'الشرك', 'البدعة', 'الأسماء والصفات', 'القضاء والقدر', 'أهل السنة', 'المعتزلة', 'الأشاعرة'],
  hadith: ['شرح حديث', 'حديث نبوي', 'قال رسول الله', 'رواه البخاري في صحيحه', 'رواه مسلم', 'أحاديث الأحكام', 'فوائد الحديث'],
  takhrij: ['تخريج', 'درجة الحديث', 'صححه', 'ضعفه', 'إسناد الحديث', 'رجال الإسناد', 'علل الحديث', 'حسن صحيح'],
  usul: ['أصول الفقه', 'قاعدة فقهية', 'مقاصد الشريعة', 'القياس', 'الإجماع', 'الاستحسان', 'سد الذرائع', 'المصلحة المرسلة'],
  language: ['معنى كلمة', 'في اللغة', 'اشتقاق', 'غريب الحديث', 'إعراب', 'البلاغة', 'النحو', 'الصرف', 'معجم'],
  tarikh: ['تاريخ', 'معركة', 'غزوة', 'الدولة', 'الخليفة', 'الفتوحات', 'الأندلس', 'العثمانية', 'الأموية', 'العباسية', 'حصار', 'العصور', 'وقعة'],
  sira: ['سيرة', 'ترجمة', 'تراجم', 'مناقب', 'طلب الحديث', 'طلب العلم', 'رحلة الإمام', 'شيوخه', 'تلاميذه', 'وفاة', 'مولده', 'نشأته', 'ابن تيمية', 'ابن خلدون', 'الإمام البخاري', 'الإمام الشافعي', 'الإمام مالك', 'ابن حنبل', 'الغزالي', 'النووي', 'الذهبي', 'ابن كثير', 'رحلة'],
  mudun: ['مدينة', 'أين تقع', 'البلدان', 'جغرافيا', 'معالم المدينة', 'أحياء المدينة', 'أسوار المدينة'],
  fatawa: ['فتوى', 'فتاوى', 'يفتي', 'المفتي', 'أفتى']
};

function normalizeDesignText(text) {
  return String(text || '')
    .replace(/[ً-ٰٟ]/g, '')
    .replace(/[أإآ]/g, 'ا')
    .replace(/ة/g, 'ه')
    .replace(/ى/g, 'ي')
    .toLowerCase();
}

function classifyDesignKinds(idea) {
  let kinds = [];
  try { kinds = SELECTION_RESEARCH_KINDS || []; } catch (e) { kinds = []; }
  if (!kinds.length) return { kinds: [], label: 'الكتب المعتمدة', books: designBooksUnion(), angles: '' };
  const text = normalizeDesignText(idea);
  const scored = kinds.map(kind => {
    let score = 0;
    (DESIGN_KIND_KEYWORDS[kind.id] || []).forEach(phrase => {
      if (text.includes(normalizeDesignText(phrase))) score += phrase.length >= 5 ? 3 : 2;
    });
    return { kind, score };
  }).filter(item => item.score > 0).sort((a, b) => b.score - a.score);

  let chosen;
  if (!scored.length) {
    chosen = kinds;
  } else if (scored.length === 1 || scored[0].score - scored[1].score >= 2) {
    chosen = [scored[0].kind];
  } else {
    chosen = scored.filter(item => item.score >= scored[0].score - 2).slice(0, 2).map(item => item.kind);
  }
  const books = [...new Set(chosen.flatMap(kind => kind.books || []))];
  const label = chosen.length === kinds.length ? 'كل الفنون المعتمدة' : chosen.map(kind => `${kind.icon} ${kind.label}`).join(' + ');
  return { kinds: chosen, label, books, angles: chosen.map(kind => kind.angle).join('؛ ') };
}

const DESIGN_KIND_STATE_KEY = 'almujtahed_designs_kinds_v1';
let designKindState = { auto: true, selected: [] };

function loadDesignKindState() {
  try {
    const raw = localStorage.getItem(DESIGN_KIND_STATE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      designKindState = {
        auto: parsed.auto !== false,
        selected: Array.isArray(parsed.selected) ? parsed.selected : []
      };
    }
  } catch (e) { /* حالة افتراضية */ }
  return designKindState;
}

function saveDesignKindState() {
  try { localStorage.setItem(DESIGN_KIND_STATE_KEY, JSON.stringify(designKindState)); } catch (e) {}
}

function designKindsList() {
  try { return SELECTION_RESEARCH_KINDS || []; } catch (e) { return []; }
}

function updateDesignKindButton() {
  const btn = document.getElementById('designKindBtn');
  if (!btn) return;
  const kinds = designKindsList();
  if (designKindState.auto || !designKindState.selected.length) {
    btn.textContent = designKindState.auto ? '🔍 نطاق البحث: تلقائي' : '🎯 نطاق البحث: يدوي (كل الفنون)';
    return;
  }
  const chosen = kinds.filter(k => designKindState.selected.includes(k.id));
  const bookCount = new Set(chosen.flatMap(k => k.books || [])).size;
  btn.textContent = `🎯 نطاق البحث: ${chosen.map(k => k.label).join(' + ')} (${bookCount} كتابًا)`;
}

function initDesignKindPicker() {
  loadDesignKindState();
  const grid = document.getElementById('designKindGrid');
  const autoBox = document.getElementById('designKindAuto');
  const btn = document.getElementById('designKindBtn');
  const panel = document.getElementById('designKindPanel');
  if (!grid || !btn || !panel) return;
  if (autoBox) autoBox.checked = !!designKindState.auto;
  grid.innerHTML = designKindsList().map(kind =>
    `<label class="design-kind-item"><input type="checkbox" value="${kind.id}" ${designKindState.selected.includes(kind.id) ? 'checked' : ''} ${designKindState.auto ? 'disabled' : ''}><span>${kind.icon} ${kind.label} (${(kind.books || []).length})</span></label>`
  ).join('');
  updateDesignKindButton();
  if (btn.dataset.wired) return;
  btn.dataset.wired = '1';
  btn.addEventListener('click', (event) => {
    event.stopPropagation();
    panel.hidden = !panel.hidden;
  });
  panel.addEventListener('click', (event) => event.stopPropagation());
  document.addEventListener('click', () => { panel.hidden = true; });
  if (autoBox) autoBox.addEventListener('change', () => {
    designKindState.auto = autoBox.checked;
    saveDesignKindState();
    grid.querySelectorAll('input[type="checkbox"]').forEach(box => { box.disabled = designKindState.auto; });
    updateDesignKindButton();
  });
  grid.addEventListener('change', () => {
    designKindState.selected = [...grid.querySelectorAll('input[type="checkbox"]:checked')].map(box => box.value);
    saveDesignKindState();
    updateDesignKindButton();
  });
}

function resolveDesignScope(idea) {
  loadDesignKindState();
  const kinds = designKindsList();
  if (!designKindState.auto) {
    const chosen = designKindState.selected.length
      ? kinds.filter(kind => designKindState.selected.includes(kind.id))
      : kinds;
    if (chosen.length) {
      return {
        kinds: chosen,
        label: (designKindState.selected.length
          ? chosen.map(kind => `${kind.icon} ${kind.label}`).join(' + ')
          : 'كل الفنون') + ' (يدوي)',
        books: [...new Set(chosen.flatMap(kind => kind.books || []))],
        angles: chosen.map(kind => kind.angle).join('؛ ')
      };
    }
  }
  return classifyDesignKinds(idea);
}

function designSystemPrompt() {
  return [
    'أنت مهندس توجيهات صور (Prompt Engineer) لتبويب «تصاميم» في تطبيق المجتهد للبحث التراثي.',
    'مهمتك الوحيدة: تحويل فكرة المستخدم إلى توجيه توليد صورة واحد (Image Prompt) بالإنجليزية فقط، جاهز للإرسال مباشرة إلى نموذج توليد صور، مستندًا إلى الشواهد المرفقة من كتب التراث المعتمدة — لا تخترع وقائع أو أماكن أو تواريخ لا تدعمها الشواهد.',
    'أخرج التوجيه وحده في فقرة واحدة متصلة، بلا مقدمة ولا شرح ولا عناوين ولا علامات تنقيط عربية.',
    'يجب أن يتضمن التوجيه حتمًا هذه العناصر:',
    '1) نوع العمل: highly detailed historical infographic / documentary illustration مناسب لموضوع الفكرة (خريطة رحلة، خط زمني، مشهد تاريخي موثق...) بحسب ما تدعمه الشواهد.',
    '2) خطوط الصورة العربية: العنوان الرئيسي والعناوين الفرعية داخل الصورة بخط المراعي (Almarai — Google Fonts) بالوزن العريض، وبقية النصوص العربية (الشروح والتسميات والقوائم والتعليقات) بخط الأميري (Amiri — Google Fonts) الأنيق. اختر عنوانًا عربيًا دقيقًا للفكرة واكتبه في التوجيه بحروف عربية حرفيًا بين علامتي تنصيص، مثل: The main title reads clearly in Arabic: "رحلة الإمام البخاري لطلب الحديث", set in bold Almarai (Google Fonts), ivory white with coral highlights; all other Arabic text, labels and captions in Amiri (Google Fonts) — crisp, perfectly legible, with no distorted characters.',
    '3) هوية المجتهد البصرية الثابتة: Modern editorial cartography combined with Andalusian manuscript warmth. Strictly use: deep ocean navy, muted teal, slate gray, ivory sand, and vibrant coral-orange accents. Absolutely avoid standard black-and-gold or dark vintage fantasy themes.',
    '4) الأشخاص إن ظهروا: من الخلف تمامًا (strictly and entirely from the back)، بلا وجوه ولا ملامح جانبية، بملابس تاريخية موقرة.',
    '5) تفاصيل موثقة من الشواهد: أسماء الأماكن والأعلام والمسارات كما وردت، بمؤشرات جغرافية نظيفة وخطوط مسار مرجانية مضيئة عند الحاجة.',
    '6) بلا أي شعارات أو علامات مائية داخل الصورة (الشعار يضيفه التطبيق لاحقًا)، وبلا نصوص إنجليزية داخل الصورة سوى أسماء الأماكن على الخريطة عند الحاجة.'
  ].join('\n');
}

function loadDesignMessages() {
  try {
    const raw = localStorage.getItem(DESIGNS_STORE_KEY);
    designMessages = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(designMessages)) designMessages = [];
  } catch (e) { designMessages = []; }
}

function saveDesignMessages() {
  try { localStorage.setItem(DESIGNS_STORE_KEY, JSON.stringify(designMessages.slice(-30))); } catch (e) {}
}

function designAspectLabel(aspect) {
  return aspect === '9:16' ? '📱 طولي 9:16' : '🖥️ عرضي 16:9';
}

const DESIGN_SAR_RATE = 3.75;
function fmtUsd(value) {
  if (value == null || isNaN(value)) return '—';
  return '$' + Number(value).toFixed(Number(value) < 1 ? 4 : 2);
}
function fmtSar(value) {
  if (value == null || isNaN(value)) return '—';
  return (Number(value) * DESIGN_SAR_RATE).toFixed(2) + ' ر.س';
}
function fmtDesignDuration(seconds) {
  if (seconds == null || isNaN(seconds)) return '—';
  const total = Math.max(0, Math.round(seconds));
  return Math.floor(total / 60) + ':' + String(total % 60).padStart(2, '0');
}

let designTimerId = null;
let designTimerStart = 0;
function startDesignTimer(label) {
  designTimerStart = Date.now();
  setDesignStatus(label);
  stopDesignTimerOnly();
  designTimerId = setInterval(() => {
    const el = document.getElementById('designTimerTick');
    if (el) el.textContent = fmtDesignDuration((Date.now() - designTimerStart) / 1000);
  }, 250);
}
function stopDesignTimerOnly() {
  if (designTimerId) { clearInterval(designTimerId); designTimerId = null; }
}
function stopDesignTimer() {
  stopDesignTimerOnly();
  setDesignStatus('');
}

function renderDesignMessages() {
  const box = document.getElementById('designMessages');
  if (!box) return;
  if (!designMessages.length) {
    box.innerHTML = '<div class="design-empty">مثال: «رحلة الإمام البخاري في طلب الحديث» — ستتحول إلى خريطة إنفوغرافيك تاريخية بعنوان عربي وأسلوب المجتهد البصري.</div>';
    return;
  }
  box.innerHTML = designMessages.map((msg, idx) => {
    if (msg.role === 'user') {
      return `<div class="design-msg design-msg-user"><div class="design-bubble">${escapeHtml(msg.text || '')}</div></div>`;
    }
    const books = (msg.books || []).slice(0, 8).map(b => `<span class="design-book-chip">${escapeHtml(b)}</span>`).join('');
    const costChip = msg.cost_usd != null
      ? `<span class="design-chip">💲 التكلفة: ${fmtUsd(msg.cost_usd)} (${fmtSar(msg.cost_usd)})</span>` : '';
    const durChip = msg.duration_s != null
      ? `<span class="design-chip">⏱️ مدة التوليد: ${fmtDesignDuration(msg.duration_s)}</span>` : '';
    const publishChip = msg.publish?.status
      ? `<span class="design-chip">${msg.publish.status === 'scheduled' ? '🗓️' : '📤'} ${escapeHtml(msg.publish.label || msg.publish.status)}</span>` : '';
    return `<div class="design-msg design-msg-assistant"><div class="design-card">
      <div class="design-card-head">
        <div class="design-card-info">
          ${msg.title ? `<span class="design-title">🖼️ ${escapeHtml(msg.title)}</span>` : ''}
          <span class="design-chip">${designAspectLabel(msg.aspect || '16:9')}</span>
          ${msg.discipline ? `<span class="design-chip">🔍 ${escapeHtml(msg.discipline)}</span>` : ''}
          ${msg.branded ? '<span class="design-chip">🟢 مختوم بشعار المجتهد</span>' : '<span class="design-chip">الشعار غير مطبوع (راجع التثبيت)</span>'}
          ${costChip}${durChip}
          ${msg.file_name ? `<span class="design-chip">📄 ${escapeHtml(msg.file_name)}</span>` : ''}
          ${publishChip}
        </div>
        <div class="design-card-actions">
          ${msg.image_url ? `<button type="button" class="design-mini-btn" data-design-action="fold" data-idx="${idx}">${msg.collapsed ? '👁️ عرض الصورة' : '🙈 طي الصورة'}</button>` : ''}
          ${msg.image_url ? `<button type="button" class="design-mini-btn" data-design-action="zoom" data-idx="${idx}">🔍 تكبير</button>` : ''}
          ${msg.image_url ? `<button type="button" class="design-mini-btn" data-design-action="share" data-idx="${idx}">🔗 مشاركة</button>` : ''}
          ${msg.image_url ? `<button type="button" class="design-mini-btn" data-design-action="publish" data-idx="${idx}">📤 نشر</button>` : ''}
          ${msg.image_url ? `<a class="design-download" href="${escapeHtml(msg.image_url)}" download>⬇️ تنزيل</a>` : ''}
          <button type="button" class="design-mini-btn" data-design-action="archive" data-idx="${idx}">🗄️ أرشفة</button>
          ${msg.image_url ? `<button type="button" class="design-mini-btn design-danger" data-design-action="delete" data-idx="${idx}">🗑️ حذف نهائي</button>` : ''}
        </div>
      </div>
      ${msg.image_url && !msg.collapsed ? `<img class="design-image" src="${escapeHtml(msg.image_url)}" alt="تصميم المجتهد" loading="lazy" data-design-zoom="${idx}" title="انقر للتكبير">` : ''}
      ${books ? `<div class="design-books">📚 من كتب: ${books}</div>` : ''}
      ${msg.prompt ? `<details class="design-prompt"><summary>توجيه الصورة الذي أُرسل للنموذج</summary><p dir="ltr">${escapeHtml(msg.prompt)}</p></details>` : ''}
    </div></div>`;
  }).join('');
  box.scrollTop = box.scrollHeight;
}

function setDesignStatus(text) {
  const box = document.getElementById('designMessages');
  if (!box) return;
  let el = document.getElementById('designStatusBubble');
  if (!text) { if (el) el.remove(); return; }
  if (!el) {
    el = document.createElement('div');
    el.id = 'designStatusBubble';
    el.className = 'design-msg design-msg-assistant';
    box.appendChild(el);
  }
  el.innerHTML = `<div class="design-status">⏳ ${escapeHtml(text)} <span class="design-timer" id="designTimerTick">0:00</span></div>`;
  box.scrollTop = box.scrollHeight;
}

async function loadDesignBalance() {
  const el = document.getElementById('designBalance');
  if (!el) return;
  try {
    // نفس مصدر وصيغة رصيد تبويب المحادثات تمامًا: أرصدة حساب OpenRouter
    let apiKey = '';
    try { apiKey = readProviderKeys().openrouter || ''; } catch (e) {}
    const resp = await fetch(`/api/openrouter/credits?api_key=${encodeURIComponent(apiKey)}`);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || '');
    const remUsd = Number(data.remaining_credits_usd);
    const remSar = Number(data.remaining_credits_sar);
    if (isNaN(remUsd)) throw new Error('بيانات رصيد ناقصة');
    el.textContent = `💰 الرصيد الحالي: $${remUsd.toFixed(2)} | ${remSar.toFixed(2)} ﷼`;
    el.title = `إجمالي الرصيد المشحون: ${fmtUsd(Number(data.total_credits_usd))} • إجمالي المستخدم: ${fmtUsd(Number(data.total_usage_usd))} (${fmtSar(Number(data.total_usage_usd))})`;
  } catch (e) {
    el.textContent = '💰 الرصيد الحالي: تعذر الجلب';
  }
}

async function runDesignGeneration(idea, aspect, scope) {
  const books = scope.books.length ? scope.books : designBooksUnion();
  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) {}
  const apiKey = savedKeys.openrouter || '';

  startDesignTimer(`فُحص الطلب: ${scope.label} — يبحث Gemini 3.8 Flash في ${books.length} كتابًا ويصوغ توجيه الصورة...`);
  const chatResp = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: DESIGN_TEXT_MODEL,
      provider: 'openrouter',
      api_key: apiKey,
      library_only: true,
      library_query: idea.slice(0, 800),
      selected_books: books,
      extraction_capacity: 10,
      witness_limit: 10,
      context_tokens: 64000,
      messages: [{ role: 'user', content: `فكرة التصميم: ${idea}\nصِغ توجيه الصورة الآن وفق تعليماتك.` }],
      system_prompt: designSystemPrompt() + (scope.angles ? `\nزاوية تركيز هذا الطلب بحسب فنّه المصنَّف (${scope.label}): ${scope.angles} — ركّز تفاصيل التوجيه الموثقة على هذه الزاوية.` : ''),
      temperature: 0.3,
      providers: savedKeys,
      agent_group: null
    })
  });
  const chatData = await chatResp.json().catch(() => ({}));
  if (!chatResp.ok) throw new Error(chatData.detail || 'تعذرت صياغة التوجيه');
  const prompt = String(chatData.reply || '').replace(/```[a-z]*|```/gi, '').trim();
  if (prompt.length < 40) throw new Error('جاء توجيه الصورة فارغًا أو قصيرًا — أعد المحاولة');

  const witnessBooks = [...new Set((chatData.witnesses || []).map(w => w.book_title || w.title || w.book || '').filter(Boolean))];

  setDesignStatus('يولّد نموذج الصورة التصميم الآن — قد يستغرق نحو دقيقة...');
  const imgResp = await fetch('/api/designs/image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, aspect, api_key: apiKey })
  });
  const imgData = await imgResp.json().catch(() => ({}));
  if (!imgResp.ok) throw new Error(imgData.detail || 'تعذر توليد الصورة');

  designMessages.push({
    role: 'assistant',
    prompt,
    image_url: imgData.image_url || '',
    file_name: imgData.file_name || '',
    title: imgData.title || '',
    branded: !!imgData.branded,
    aspect,
    discipline: scope.label,
    cost_usd: (typeof imgData.cost_usd === 'number') ? imgData.cost_usd : null,
    duration_s: (typeof imgData.duration_s === 'number') ? imgData.duration_s : null,
    collapsed: false,
    books: witnessBooks
  });
  saveDesignMessages();
  stopDesignTimer();
  renderDesignMessages();
  loadDesignBalance();
}

async function submitDesignIdea(event) {
  if (event) event.preventDefault();
  if (designBusy) return;
  const input = document.getElementById('designIdeaInput');
  const idea = (input?.value || '').trim();
  if (idea.length < 3) { if (typeof showToast === 'function') showToast('اكتب فكرة التصميم أولًا'); return; }
  const aspect = document.querySelector('input[name="designAspect"]:checked')?.value || '16:9';
  const scope = resolveDesignScope(idea);
  const userMsg = { role: 'user', text: idea };
  designMessages.push(userMsg);
  saveDesignMessages();
  renderDesignMessages();
  input.value = '';
  designBusy = true;
  const btn = document.getElementById('designSendBtn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ جارٍ التوليد...'; }
  try {
    await runDesignGeneration(idea, aspect, scope);
    // بعد إنشاء الصورة بنجاح يُحذف طلب المستخدم تلقائيًا — تبقى البطاقة وحدها
    const reqIdx = designMessages.indexOf(userMsg);
    if (reqIdx >= 0) {
      designMessages.splice(reqIdx, 1);
      saveDesignMessages();
      renderDesignMessages();
    }
  } catch (err) {
    stopDesignTimer();
    if (typeof showToast === 'function') showToast(err.message || 'تعذر توليد التصميم');
    const box = document.getElementById('designMessages');
    if (box) {
      const el = document.createElement('div');
      el.className = 'design-msg design-msg-assistant';
      el.innerHTML = `<div class="design-status design-status-error">⚠️ ${escapeHtml(err.message || 'تعذر توليد التصميم')}</div>`;
      box.appendChild(el);
      box.scrollTop = box.scrollHeight;
    }
  } finally {
    designBusy = false;
    if (btn) { btn.disabled = false; btn.textContent = '🎨 توليد التصميم'; }
  }
}

async function shareDesignImage(msg) {
  try {
    const resp = await fetch(msg.image_url);
    const blob = await resp.blob();
    const file = new File([blob], msg.file_name || 'تصميم-المجتهد.png', { type: blob.type || 'image/png' });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: msg.title || 'تصميم المجتهد' });
      return;
    }
    if (navigator.clipboard && window.ClipboardItem) {
      await navigator.clipboard.write([new ClipboardItem({ [blob.type || 'image/png']: blob })]);
      if (typeof showToast === 'function') showToast('نُسخت الصورة — الصقها أين تريد مشاركتها');
      return;
    }
    throw new Error('المشاركة غير مدعومة في هذا المتصفح — استخدم زر التنزيل');
  } catch (err) {
    if (err && err.name === 'AbortError') return;
    if (typeof showToast === 'function') showToast(err.message || 'تعذرت المشاركة');
  }
}

const AYRSHARE_PLATFORMS_UI = [
  ['instagram', '📸 إنستغرام'], ['twitter', '𝕏 إكس'], ['facebook', '📘 فيسبوك'],
  ['threads', '🧵 ثريدز'], ['telegram', '✈️ تيليغرام'], ['linkedin', '💼 لينكدإن'],
  ['tiktok', '🎵 تيك توك'], ['youtube', '▶️ يوتيوب'], ['pinterest', '📌 بينترست'],
  ['bluesky', '🦋 بلوسكاي'], ['reddit', '👽 ريديت'], ['snapchat', '👻 سناب شات'], ['gmb', '📍 نشاط جوجل']
];
const DESIGN_PUBLISH_PLATFORMS_KEY = 'almujtahed_designs_platforms_v1';
const DESIGN_PUBLISH_ACCOUNTS_KEY = 'almujtahed_designs_accounts_v1';
const DESIGN_PUBLISH_PROVIDER_KEY = 'almujtahed_designs_provider_v1';
let designPublishIdx = -1;

function designPublishProvider() {
  return document.querySelector('input[name="designPublishProvider"]:checked')?.value
    || localStorage.getItem(DESIGN_PUBLISH_PROVIDER_KEY) || 'zernio';
}

function platformLabelAr(platform) {
  const found = AYRSHARE_PLATFORMS_UI.find(([id]) => id === platform);
  return found ? found[1] : platform;
}

function designCaptionDraft(msg) {
  const tags = ['#المجتهد'];
  const disc = String(msg.discipline || '').replace(/\(يدوي\)|مسترجعة من المجلد/g, '').trim();
  disc.split('+').forEach(part => {
    const word = part.replace(/[^\u0600-\u06FF ]/g, '').trim().replace(/\s+/g, '');
    if (word.length > 1) tags.push('#' + word);
  });
  tags.push('#تراث', '#تاريخ_إسلامي');
  return `${msg.title || 'تصميم من المجتهد'}\n\n📚 تصميم موثّق من كتب التراث — عبر تطبيق «المجتهد»\n${[...new Set(tags)].join(' ')}`;
}

async function refreshDesignPublishTargets() {
  const provider = designPublishProvider();
  const grid = document.getElementById('designPublishPlatforms');
  const label = document.getElementById('designPublishTargetsLabel');
  const keyRow = document.getElementById('designPublishKeyRow');
  if (!grid) return;
  grid.innerHTML = '<div class="design-empty">جارٍ جلب وجهات النشر...</div>';
  try {
    if (provider === 'zernio') {
      const resp = await fetch('/api/designs/zernio-accounts');
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || 'تعذر جلب حسابات Zernio');
      keyRow.hidden = !!data.connected;
      label.textContent = 'حسابات Zernio المرتبطة:';
      if (!data.connected) {
        grid.innerHTML = '';
        return;
      }
      const accounts = data.accounts || [];
      if (!accounts.length) {
        grid.innerHTML = '<div class="design-empty">لا حسابات اجتماعية مرتبطة في Zernio بعد — اربطها من لوحة Zernio ثم «تحديث القائمة».</div>';
        return;
      }
      let savedAccounts = [];
      try { savedAccounts = JSON.parse(localStorage.getItem(DESIGN_PUBLISH_ACCOUNTS_KEY) || '[]'); } catch (e) {}
      grid.innerHTML = accounts.map(acc =>
        `<label class="design-kind-item"><input type="checkbox" value="${escapeHtml(acc.id)}" data-platform="${escapeHtml(acc.platform)}" ${savedAccounts.includes(acc.id) ? 'checked' : ''}><span>${platformLabelAr(acc.platform)} — ${escapeHtml(acc.label)}</span></label>`
      ).join('');
    } else {
      const resp = await fetch('/api/designs/ayrshare-status');
      const data = await resp.json().catch(() => ({}));
      keyRow.hidden = !!data.connected;
      label.textContent = 'الشبكات (المرتبطة بحسابك في Ayrshare):';
      let savedPlatforms = [];
      try { savedPlatforms = JSON.parse(localStorage.getItem(DESIGN_PUBLISH_PLATFORMS_KEY) || '[]'); } catch (e) {}
      grid.innerHTML = AYRSHARE_PLATFORMS_UI.map(([id, text]) =>
        `<label class="design-kind-item"><input type="checkbox" value="${id}" ${savedPlatforms.includes(id) ? 'checked' : ''}><span>${text}</span></label>`
      ).join('');
    }
  } catch (err) {
    grid.innerHTML = `<div class="design-empty">⚠️ ${escapeHtml(err.message || 'تعذر جلب الوجهات')}</div>`;
  }
}

async function openDesignPublish(idx) {
  const msg = designMessages[idx];
  if (!msg || !msg.image_url) return;
  designPublishIdx = idx;
  const overlay = document.getElementById('designPublishOverlay');
  if (!overlay) return;
  document.getElementById('designPublishImg').src = msg.image_url;
  document.getElementById('designPublishCaption').value = designCaptionDraft(msg);
  const savedProvider = localStorage.getItem(DESIGN_PUBLISH_PROVIDER_KEY) || 'zernio';
  document.querySelectorAll('input[name="designPublishProvider"]').forEach(radio => {
    radio.checked = radio.value === savedProvider;
  });
  const result = document.getElementById('designPublishResult');
  result.hidden = true;
  result.textContent = '';
  overlay.hidden = false;
  refreshDesignPublishTargets();
}

async function submitDesignPublish() {
  const msg = designMessages[designPublishIdx];
  if (!msg) return;
  const provider = designPublishProvider();
  const caption = document.getElementById('designPublishCaption').value;
  const checked = [...document.querySelectorAll('#designPublishPlatforms input[type="checkbox"]:checked')];
  const result = document.getElementById('designPublishResult');
  const showResult = (html) => { result.hidden = false; result.innerHTML = html; };
  if (!checked.length) { showResult('⚠️ اختر وجهة نشر واحدة على الأقل'); return; }
  const platforms = checked.map(b => provider === 'zernio' ? (b.getAttribute('data-platform') || b.value) : b.value);
  const accountIds = provider === 'zernio' ? checked.map(b => b.value) : [];
  try {
    localStorage.setItem(provider === 'zernio' ? DESIGN_PUBLISH_ACCOUNTS_KEY : DESIGN_PUBLISH_PLATFORMS_KEY,
      JSON.stringify(provider === 'zernio' ? accountIds : platforms));
  } catch (e) {}
  const when = document.querySelector('input[name="designPublishWhen"]:checked')?.value || 'now';
  let schedule = null;
  if (when === 'schedule') {
    const value = document.getElementById('designPublishDate').value;
    if (!value) { showResult('⚠️ حدد موعد الجدولة'); return; }
    schedule = new Date(value).toISOString();
    if (new Date(schedule).getTime() <= Date.now()) { showResult('⚠️ موعد الجدولة في الماضي'); return; }
  }
  const submitBtn = document.getElementById('designPublishSubmit');
  submitBtn.disabled = true;
  submitBtn.textContent = '⏳ جارٍ الرفع والنشر...';
  try {
    const resp = await fetch('/api/designs/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_url: msg.image_url, caption, platforms, provider, account_ids: accountIds, schedule })
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || 'تعذر النشر');
    const platformNames = platforms.map(p => platformLabelAr(p)).join('، ');
    const okLinks = (data.post_ids || []).filter(p => p.status === 'success')
      .map(p => p.postUrl ? `<a href="${escapeHtml(p.postUrl)}" target="_blank" rel="noopener">${escapeHtml(platformLabelAr(p.platform))}</a>` : escapeHtml(platformLabelAr(p.platform))).join('، ');
    const errText = (data.errors || []).map(e => `${escapeHtml(platformLabelAr(e.platform || ''))}: ${escapeHtml(e.message || '')}`).join('<br>');
    if (data.status === 'scheduled') {
      msg.publish = { status: 'scheduled', label: `مجدول: ${platformNames}` };
      showResult(`🗓️ جُدول النشر بنجاح على: ${escapeHtml(platformNames)}`);
    } else if ((data.post_ids || []).length) {
      msg.publish = { status: 'published', label: `${data.status === 'partial' ? 'نُشر جزئيًا' : 'نُشر'}: ${platformNames}` };
      showResult(`✅ نُشر على: ${okLinks || escapeHtml(platformNames)}${errText ? '<br>⚠️ ' + errText : ''}`);
    } else {
      showResult(`⚠️ لم يتم النشر${errText ? '<br>' + errText : ''}`);
      return;
    }
    saveDesignMessages();
    renderDesignMessages();
    loadDesignBalance();
  } catch (err) {
    showResult('⚠️ ' + escapeHtml(err.message || 'تعذر النشر'));
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = '📤 نشر التصميم';
  }
}

function openDesignLightbox(url) {
  const box = document.getElementById('designLightbox');
  const img = document.getElementById('designLightboxImg');
  if (!box || !img || !url) return;
  img.src = url;
  box.hidden = false;
}

function closeDesignLightbox() {
  const box = document.getElementById('designLightbox');
  if (box) box.hidden = true;
}

async function onDesignCardAction(event) {
  const zoomImg = event.target.closest('[data-design-zoom]');
  if (zoomImg) {
    const msg = designMessages[Number(zoomImg.getAttribute('data-design-zoom'))];
    if (msg) openDesignLightbox(msg.image_url);
    return;
  }
  const btn = event.target.closest('[data-design-action]');
  if (!btn) return;
  const idx = Number(btn.getAttribute('data-idx'));
  const msg = designMessages[idx];
  if (!msg) return;
  const action = btn.getAttribute('data-design-action');
  if (action === 'zoom') {
    openDesignLightbox(msg.image_url);
  } else if (action === 'publish') {
    openDesignPublish(idx);
  } else if (action === 'fold') {
    msg.collapsed = !msg.collapsed;
    saveDesignMessages();
    renderDesignMessages();
  } else if (action === 'share') {
    shareDesignImage(msg);
  } else if (action === 'archive') {
    designMessages.splice(idx, 1);
    saveDesignMessages();
    renderDesignMessages();
    if (typeof showToast === 'function') showToast('أُرشفت الصورة — باقية في المجلد ويمكن استرجاعها');
  } else if (action === 'delete') {
    if (!window.confirm('حذف نهائي؟ ستُمسح الصورة من مجلد التصاميم كليًا ولا يمكن استرجاعها.')) return;
    try {
      const resp = await fetch('/api/designs/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_url: msg.image_url })
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || 'تعذر الحذف');
      designMessages.splice(idx, 1);
      saveDesignMessages();
      renderDesignMessages();
      if (typeof showToast === 'function') showToast('حُذفت الصورة نهائيًا من المجلد');
    } catch (err) {
      if (typeof showToast === 'function') showToast(err.message || 'تعذر الحذف');
    }
  }
}

async function openDesignRestore() {
  const overlay = document.getElementById('designRestoreOverlay');
  const list = document.getElementById('designRestoreList');
  if (!overlay || !list) return;
  overlay.hidden = false;
  list.innerHTML = '<div class="design-empty">جارٍ قراءة مجلد التصاميم...</div>';
  try {
    const resp = await fetch('/api/designs/list');
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || 'تعذر قراءة المجلد');
    const inChat = new Set(designMessages.map(m => m.image_url).filter(Boolean));
    const items = (data.items || []).filter(item => !inChat.has(item.image_url));
    if (!items.length) {
      list.innerHTML = '<div class="design-empty">لا صور إضافية في المجلد خارج المحادثة الحالية.</div>';
      return;
    }
    list.innerHTML = items.map(item => {
      const date = new Date(item.modified * 1000).toLocaleString('ar-EG');
      const size = item.size > 1048576 ? (item.size / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(item.size / 1024)) + ' KB';
      return `<label class="design-restore-item">
        <input type="checkbox" value="${escapeHtml(item.image_url)}" data-title="${escapeHtml(item.title || '')}" data-name="${escapeHtml(item.file_name || '')}">
        <img src="${escapeHtml(item.image_url)}" alt="" loading="lazy">
        <span class="design-restore-meta"><strong>${escapeHtml(item.title || item.file_name)}</strong><small>${escapeHtml(item.file_name)} • ${size} • ${escapeHtml(date)}</small></span>
      </label>`;
    }).join('');
  } catch (err) {
    list.innerHTML = `<div class="design-empty">⚠️ ${escapeHtml(err.message || 'تعذر قراءة المجلد')}</div>`;
  }
}

function applyDesignRestore() {
  const boxes = document.querySelectorAll('#designRestoreList input[type="checkbox"]:checked');
  if (!boxes.length) {
    if (typeof showToast === 'function') showToast('حدد صورة واحدة على الأقل');
    return;
  }
  boxes.forEach(box => {
    designMessages.push({
      role: 'assistant',
      prompt: '',
      image_url: box.value,
      file_name: box.getAttribute('data-name') || '',
      title: box.getAttribute('data-title') || '',
      branded: true,
      aspect: '16:9',
      discipline: '♻️ مسترجعة من المجلد',
      cost_usd: null,
      duration_s: null,
      collapsed: false,
      books: []
    });
  });
  saveDesignMessages();
  renderDesignMessages();
  document.getElementById('designRestoreOverlay').hidden = true;
  if (typeof showToast === 'function') showToast('استُرجعت الصور المحددة إلى المحادثة');
}

function initDesignsTab() {
  loadDesignMessages();
  renderDesignMessages();
  loadDesignBalance();
  initDesignKindPicker();
  if (designsInitDone) return;
  designsInitDone = true;
  const messagesBox = document.getElementById('designMessages');
  if (messagesBox) messagesBox.addEventListener('click', onDesignCardAction);
  const balanceBtn = document.getElementById('designBalanceBtn');
  if (balanceBtn) balanceBtn.addEventListener('click', loadDesignBalance);
  const folderBtn = document.getElementById('designOpenFolderBtn');
  if (folderBtn) folderBtn.addEventListener('click', async () => {
    try {
      const resp = await fetch('/api/designs/open-folder', { method: 'POST' });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || 'تعذر فتح المجلد');
      if (typeof showToast === 'function') showToast('فُتح مجلد الصور: ' + (data.folder || ''));
    } catch (err) {
      if (typeof showToast === 'function') showToast(err.message || 'تعذر فتح المجلد');
    }
  });
  const restoreBtn = document.getElementById('designRestoreBtn');
  if (restoreBtn) restoreBtn.addEventListener('click', openDesignRestore);
  const restoreClose = document.getElementById('designRestoreClose');
  if (restoreClose) restoreClose.addEventListener('click', () => { document.getElementById('designRestoreOverlay').hidden = true; });
  const restoreOverlay = document.getElementById('designRestoreOverlay');
  if (restoreOverlay) restoreOverlay.addEventListener('click', (event) => { if (event.target === restoreOverlay) restoreOverlay.hidden = true; });
  const restoreApply = document.getElementById('designRestoreApply');
  if (restoreApply) restoreApply.addEventListener('click', applyDesignRestore);
  const clearBtn = document.getElementById('designClearBtn');
  if (clearBtn) clearBtn.addEventListener('click', () => {
    if (!designMessages.length) { if (typeof showToast === 'function') showToast('المحادثة فارغة أصلًا'); return; }
    if (!window.confirm('مسح محادثة التصاميم كلها؟ تبقى الصور في المجلد ويمكن استرجاعها منه.')) return;
    designMessages = [];
    saveDesignMessages();
    renderDesignMessages();
    if (typeof showToast === 'function') showToast('مُسحت المحادثة — الصور باقية في المجلد');
  });
  const publishClose = document.getElementById('designPublishClose');
  if (publishClose) publishClose.addEventListener('click', () => { document.getElementById('designPublishOverlay').hidden = true; });
  const publishOverlay = document.getElementById('designPublishOverlay');
  if (publishOverlay) publishOverlay.addEventListener('click', (event) => { if (event.target === publishOverlay) publishOverlay.hidden = true; });
  const publishSubmit = document.getElementById('designPublishSubmit');
  if (publishSubmit) publishSubmit.addEventListener('click', submitDesignPublish);
  document.querySelectorAll('input[name="designPublishWhen"]').forEach(radio => {
    radio.addEventListener('change', () => {
      const date = document.getElementById('designPublishDate');
      if (date) date.hidden = document.querySelector('input[name="designPublishWhen"]:checked')?.value !== 'schedule';
    });
  });
  const goServices = document.getElementById('designPublishGoServices');
  if (goServices) goServices.addEventListener('click', () => {
    document.getElementById('designPublishOverlay').hidden = true;
    if (typeof switchMainTab === 'function') switchMainTab('providers');
    setTimeout(() => {
      const card = document.getElementById('socialKeysCard');
      if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 120);
  });
  document.querySelectorAll('input[name="designPublishProvider"]').forEach(radio => {
    radio.addEventListener('change', () => {
      try { localStorage.setItem(DESIGN_PUBLISH_PROVIDER_KEY, designPublishProvider()); } catch (e) {}
      refreshDesignPublishTargets();
    });
  });
  const publishRefresh = document.getElementById('designPublishRefresh');
  if (publishRefresh) publishRefresh.addEventListener('click', refreshDesignPublishTargets);
  const lightbox = document.getElementById('designLightbox');
  if (lightbox) lightbox.addEventListener('click', (event) => { if (event.target !== document.getElementById('designLightboxImg')) closeDesignLightbox(); });
  const lightboxClose = document.getElementById('designLightboxClose');
  if (lightboxClose) lightboxClose.addEventListener('click', closeDesignLightbox);
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeDesignLightbox(); });
  const form = document.getElementById('designComposer');
  if (form) form.addEventListener('submit', submitDesignIdea);
  const input = document.getElementById('designIdeaInput');
  if (input) {
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        submitDesignIdea(event);
      }
    });
  }
}

window.initDesignsTab = initDesignsTab;
window.submitDesignIdea = submitDesignIdea;
