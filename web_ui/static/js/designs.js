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

function resolveDesignScope(idea) {
  const select = document.getElementById('designKindSelect');
  const manual = select?.value || 'auto';
  if (manual && manual !== 'auto') {
    let kinds = [];
    try { kinds = SELECTION_RESEARCH_KINDS || []; } catch (e) { kinds = []; }
    const kind = kinds.find(item => item.id === manual);
    if (kind) {
      return { kinds: [kind], label: `${kind.icon} ${kind.label} (يدوي)`, books: [...(kind.books || [])], angles: kind.angle };
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
    return `<div class="design-msg design-msg-assistant"><div class="design-card">
      ${msg.title ? `<div class="design-title">🖼️ ${escapeHtml(msg.title)}</div>` : ''}
      ${msg.image_url && !msg.collapsed ? `<img class="design-image" src="${escapeHtml(msg.image_url)}" alt="تصميم المجتهد" loading="lazy">` : ''}
      <div class="design-card-meta">
        <span class="design-chip">${designAspectLabel(msg.aspect || '16:9')}</span>
        ${msg.discipline ? `<span class="design-chip">🔍 ${escapeHtml(msg.discipline)}</span>` : ''}
        ${msg.branded ? '<span class="design-chip">🟢 مختوم بشعار المجتهد</span>' : '<span class="design-chip">الشعار غير مطبوع (راجع التثبيت)</span>'}
        ${costChip}${durChip}
        ${msg.file_name ? `<span class="design-chip">📄 ${escapeHtml(msg.file_name)}</span>` : ''}
      </div>
      <div class="design-card-actions">
        ${msg.image_url ? `<button type="button" class="design-mini-btn" data-design-action="fold" data-idx="${idx}">${msg.collapsed ? '👁️ عرض الصورة' : '🙈 طي الصورة'}</button>` : ''}
        ${msg.image_url ? `<button type="button" class="design-mini-btn" data-design-action="share" data-idx="${idx}">🔗 مشاركة</button>` : ''}
        ${msg.image_url ? `<a class="design-download" href="${escapeHtml(msg.image_url)}" download>⬇️ تنزيل</a>` : ''}
        <button type="button" class="design-mini-btn" data-design-action="archive" data-idx="${idx}">🗄️ أرشفة</button>
        ${msg.image_url ? `<button type="button" class="design-mini-btn design-danger" data-design-action="delete" data-idx="${idx}">🗑️ حذف نهائي</button>` : ''}
      </div>
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
  designMessages.push({ role: 'user', text: idea });
  saveDesignMessages();
  renderDesignMessages();
  input.value = '';
  designBusy = true;
  const btn = document.getElementById('designSendBtn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ جارٍ التوليد...'; }
  try {
    await runDesignGeneration(idea, aspect, scope);
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

async function onDesignCardAction(event) {
  const btn = event.target.closest('[data-design-action]');
  if (!btn) return;
  const idx = Number(btn.getAttribute('data-idx'));
  const msg = designMessages[idx];
  if (!msg) return;
  const action = btn.getAttribute('data-design-action');
  if (action === 'fold') {
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
  const select = document.getElementById('designKindSelect');
  if (select && select.options.length <= 1) {
    try {
      (SELECTION_RESEARCH_KINDS || []).forEach(kind => {
        const opt = document.createElement('option');
        opt.value = kind.id;
        opt.textContent = `${kind.icon} ${kind.label} — ${(kind.books || []).length} كتابًا`;
        select.appendChild(opt);
      });
    } catch (e) { /* قائمة الفنون غير جاهزة */ }
  }
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
