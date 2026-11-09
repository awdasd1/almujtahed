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

function designSystemPrompt() {
  return [
    'أنت مهندس توجيهات صور (Prompt Engineer) لتبويب «تصاميم» في تطبيق المجتهد للبحث التراثي.',
    'مهمتك الوحيدة: تحويل فكرة المستخدم إلى توجيه توليد صورة واحد (Image Prompt) بالإنجليزية فقط، جاهز للإرسال مباشرة إلى نموذج توليد صور، مستندًا إلى الشواهد المرفقة من كتب التراث المعتمدة — لا تخترع وقائع أو أماكن أو تواريخ لا تدعمها الشواهد.',
    'أخرج التوجيه وحده في فقرة واحدة متصلة، بلا مقدمة ولا شرح ولا عناوين ولا علامات تنقيط عربية.',
    'يجب أن يتضمن التوجيه حتمًا هذه العناصر:',
    '1) نوع العمل: highly detailed historical infographic / documentary illustration مناسب لموضوع الفكرة (خريطة رحلة، خط زمني، مشهد تاريخي موثق...) بحسب ما تدعمه الشواهد.',
    '2) العنوان العربي داخل الصورة: اختر عنوانًا عربيًا دقيقًا للفكرة واكتبه في التوجيه بحروف عربية حرفيًا بين علامتي تنصيص، مثل: The main title reads clearly in Arabic: "رحلة الإمام البخاري لطلب الحديث" — واطلب كتابته بخط كوفي هندسي حديث (modern Geometric Kufic)، أبيض عاجي بلمسات مرجانية، حاد الحواف ومقروء تمامًا بلا حروف مشوهة.',
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

function renderDesignMessages() {
  const box = document.getElementById('designMessages');
  if (!box) return;
  if (!designMessages.length) {
    box.innerHTML = '<div class="design-empty">مثال: «رحلة الإمام البخاري في طلب الحديث» — ستتحول إلى خريطة إنفوغرافيك تاريخية بعنوان عربي وأسلوب المجتهد البصري.</div>';
    return;
  }
  box.innerHTML = designMessages.map(msg => {
    if (msg.role === 'user') {
      return `<div class="design-msg design-msg-user"><div class="design-bubble">${escapeHtml(msg.text || '')}</div></div>`;
    }
    const books = (msg.books || []).slice(0, 8).map(b => `<span class="design-book-chip">${escapeHtml(b)}</span>`).join('');
    return `<div class="design-msg design-msg-assistant"><div class="design-card">
      ${msg.image_url ? `<img class="design-image" src="${escapeHtml(msg.image_url)}" alt="تصميم المجتهد" loading="lazy">` : ''}
      <div class="design-card-meta">
        <span class="design-chip">${designAspectLabel(msg.aspect || '16:9')}</span>
        ${msg.branded ? '<span class="design-chip">🟢 مختوم بشعار المجتهد</span>' : '<span class="design-chip">الشعار غير مطبوع (راجع التثبيت)</span>'}
        ${msg.image_url ? `<a class="design-download" href="${escapeHtml(msg.image_url)}" download>⬇️ تنزيل الصورة</a>` : ''}
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
  el.innerHTML = `<div class="design-status">⏳ ${escapeHtml(text)}</div>`;
  box.scrollTop = box.scrollHeight;
}

async function runDesignGeneration(idea, aspect) {
  const books = designBooksUnion();
  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) {}
  const apiKey = savedKeys.openrouter || '';

  setDesignStatus('يبحث Gemini 3.8 Flash في الكتب المعتمدة ويصوغ توجيه الصورة...');
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
      system_prompt: designSystemPrompt(),
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
    branded: !!imgData.branded,
    aspect,
    books: witnessBooks
  });
  saveDesignMessages();
  setDesignStatus('');
  renderDesignMessages();
}

async function submitDesignIdea(event) {
  if (event) event.preventDefault();
  if (designBusy) return;
  const input = document.getElementById('designIdeaInput');
  const idea = (input?.value || '').trim();
  if (idea.length < 3) { if (typeof showToast === 'function') showToast('اكتب فكرة التصميم أولًا'); return; }
  const aspect = document.querySelector('input[name="designAspect"]:checked')?.value || '16:9';
  designMessages.push({ role: 'user', text: idea });
  saveDesignMessages();
  renderDesignMessages();
  input.value = '';
  designBusy = true;
  const btn = document.getElementById('designSendBtn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ جارٍ التوليد...'; }
  try {
    await runDesignGeneration(idea, aspect);
  } catch (err) {
    setDesignStatus('');
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

function initDesignsTab() {
  loadDesignMessages();
  renderDesignMessages();
  if (designsInitDone) return;
  designsInitDone = true;
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
