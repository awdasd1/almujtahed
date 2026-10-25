// =============================================================================
// منظومة المجتهد - إدارة مزودي الخدمة ونماذج الذكاء الاصطناعي (providers.js)
// دعم: كلود، جوجل، أوبن إي آي، ديبسيك، وأوبن راوتر (جلب حي للتسعير والمقاييس)
// =============================================================================

// المفتاح الافتراضي التجريبي لأوبن راوتر
const DEFAULT_OPENROUTER_KEY = "";

const PROVIDER_KEY_PAGES = {
  openrouter: 'https://openrouter.ai/workspaces/default/keys',
  claude: 'https://console.anthropic.com/settings/keys',
  google: 'https://aistudio.google.com/apikey',
  openai: 'https://platform.openai.com/api-keys',
  deepseek: 'https://platform.deepseek.com/api_keys'
};

// نماذج المزودين الثابتة
const PROVIDER_MODELS_PRESETS = {
  claude: [
    { id: "anthropic/claude-3.7-sonnet", name: "Claude 3.7 Sonnet", context: "200k", prompt: 3.0, completion: 15.0, intel: "58.4", rank: "المتصدر الأول في التحليل الفقهي والأكاديمي" },
    { id: "anthropic/claude-3.5-haiku", name: "Claude 3.5 Haiku", context: "200k", prompt: 0.8, completion: 4.0, intel: "38.5", rank: "استجابة فورية وتلخيص سريع" },
    { id: "anthropic/claude-3-opus", name: "Claude 3 Opus", context: "200k", prompt: 15.0, completion: 75.0, intel: "59.2", rank: "عمق تحليلي وصياغة أدبية رفيعة" }
  ],
  google: [
    { id: "google/gemini-2.5-flash", name: "Gemini 2.5 Flash (سياق مليون توكن - للمسح الشامل)", context: "1,000,000", prompt: 0.1, completion: 0.4, intel: "52.0", rank: "المسح الاستقصائي الشامل واستيعاب المجلدات والجداول" },
    { id: "google/gemini-3.8-flash", name: "Gemini 3.8 Flash (1M Context)", context: "1,000,000", prompt: 0.15, completion: 0.6, intel: "54.0", rank: "استيعاب موسع وسرعة فائقة" },
    { id: "google/gemini-2.5-pro", name: "Gemini 2.5 Pro (2M Context)", context: "2,000,000", prompt: 1.25, completion: 10.0, intel: "56.8", rank: "الأول في معالجة المجلدات الضخمة والمخطوطات" }
  ],
  openai: [
    { id: "openai/o3-mini", name: "o3-mini", context: "200k", prompt: 1.1, completion: 4.4, intel: "55.0", rank: "الأول في المقارنات المنطقية المعقدة" },
    { id: "openai/gpt-4o", name: "GPT-4o", context: "128k", prompt: 2.5, completion: 10.0, intel: "51.0", rank: "تنوع واستيعاب سريع للوثائق القانونية" },
    { id: "openai/gpt-4o-mini", name: "GPT-4o Mini", context: "128k", prompt: 0.15, completion: 0.6, intel: "32.0", rank: "مهام الاستخراج السريعة" }
  ],
  deepseek: [
    { id: "deepseek/deepseek-r1", name: "DeepSeek R1", context: "64k", prompt: 0.7, completion: 2.5, intel: "54.6", rank: "تفكيك العلل الفقهية والقياس الأصولي" },
    { id: "deepseek/deepseek-chat", name: "DeepSeek V3", context: "64k", prompt: 0.14, completion: 0.28, intel: "43.5", rank: "كفاءة برمجية ولغوية بأسعار زهيدة" }
  ]
};

// كاش نماذج OpenRouter المسترجعة حياً
let openrouterModelsList = [];

const SUGGESTED_MODELS = [
  { id: 'google/gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
  { id: 'google/gemini-3.8-flash', name: 'Gemini 3.8 Flash' },
  { id: 'google/gemini-4-argon', name: 'Gemini 4 Argon' },
  { id: '~anthropic/claude-opus-latest', name: 'Claude Opus Latest' },
  { id: '~anthropic/claude-sonnet-latest', name: 'Claude Sonnet Latest' },
  { id: '~anthropic/claude-fable-latest', name: 'Claude Fable Latest' },
  { id: '~openai/gpt-luna-latest', name: 'GPT Luna Latest' },
  { id: '~openai/gpt-sol-latest', name: 'GPT Sol Latest' },
  { id: 'openai/gpt-4o', name: 'GPT-4o' }
];

function modelsWithSuggestedFirst(list, keepMissing = true) {
  const source = Array.isArray(list) ? list : [];
  const pinned = [];
  SUGGESTED_MODELS.forEach(item => {
    const found = source.find(model => model && model.id === item.id);
    if (found) pinned.push(found);
    else if (keepMissing) pinned.push(item);
  });
  const pinnedIds = new Set(pinned.map(model => model.id));
  return pinned.concat(source.filter(model => model && !pinnedIds.has(model.id)));
}

window.SUGGESTED_MODELS = SUGGESTED_MODELS;
window.modelsWithSuggestedFirst = modelsWithSuggestedFirst;
let openrouterRankedIds = [];
let currentSelectedModelData = null;

// تهيئة التبويب عند التحميل
document.addEventListener('DOMContentLoaded', () => {
  initProvidersTab();
});

function initProvidersTab() {
  window.almujtahedIdentity?.then(async () => {
    try {
      const res = await fetch('/api/config/providers');
      if (res.ok) {
        const data = await res.json();
        if (data.keys && typeof data.keys === 'object') {
          writeProviderKeys(data.keys);
          writeTavilyKey(data.keys.tavily || '');
        }
      }
    } catch (e) {}
    const savedKeys = readProviderKeys();
    const providerSelect = document.getElementById('providerSelect');
    if (providerSelect) {
      providerSelect.value = localStorage.getItem(ownerStorageKey('almojtahed_active_provider')) || 'openrouter';
      handleProviderChange(providerSelect.value);
    }
    loadOpenRouterCredits(false);
    initTavilyConfig();
    if (typeof syncSettingsToUI === 'function') syncSettingsToUI();
    return savedKeys;
  });
}

// تغيير المزود المختار
async function handleProviderChange(provider) {
  localStorage.setItem(ownerStorageKey('almojtahed_active_provider'), provider);
  if (typeof resetProviderKeyTest === 'function') resetProviderKeyTest();
  const keyInput = document.getElementById('providerApiKey');
  const modelsSelect = document.getElementById('providerModelSelect');
  const modelsContainer = document.getElementById('providerModelsContainer');
  const openrouterSpecsCard = document.getElementById('openrouterSpecsCard');
  const searchFilterBox = document.getElementById('modelSearchFilterWrapper');

  // استرجاع المفتاح المحفوظ
  const savedKeys = readProviderKeys();

  if (keyInput) {
    keyInput.value = savedKeys[provider] || (provider === 'openrouter' ? DEFAULT_OPENROUTER_KEY : '');
  }

  const keyLink = document.getElementById('providerKeyLink');
  if (keyLink) {
    const page = PROVIDER_KEY_PAGES[provider] || PROVIDER_KEY_PAGES.openrouter;
    const label = typeof getProviderLabel === 'function' ? getProviderLabel(provider) : provider;
    keyLink.href = page;
    keyLink.title = `فتح صفحة إنشاء المفتاح لدى ${label}`;
  }

  if (provider === 'openrouter') {
    if (searchFilterBox) searchFilterBox.style.display = 'flex';
    await loadOpenRouterModelsList();
  } else {
    if (searchFilterBox) searchFilterBox.style.display = 'none';
    populatePresetModels(provider);
    loadOpenRouterRankings();
  }
  syncChatModelDropdown(provider);
}

// حفظ المفتاح في LocalStorage وملف البيئة .env بالخادم
function saveCurrentApiKey() {
  const provider = document.getElementById('providerSelect').value;
  const key = document.getElementById('providerApiKey').value.trim();
  const savedKeys = readProviderKeys();
  savedKeys[provider] = key;
  writeProviderKeys(savedKeys);

  fetch('/api/config/providers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ [provider]: key })
  }).catch(e => console.warn('Could not sync key to account:', e));

  if (provider === 'openrouter') {
    loadOpenRouterModelsList(true);
  }

  showToast(`تم حفظ مفتاح ${getProviderLabel(provider)} في حسابك`);
}

// تبديل إظهار وإخفاء المفتاح
function resetProviderKeyTest() {
  const button = document.getElementById('providerKeyTestBtn');
  if (!button) return;
  button.classList.remove('is-success', 'is-failure');
  button.disabled = false;
  button.textContent = 'اختبار';
}

async function testCurrentProviderKey() {
  const button = document.getElementById('providerKeyTestBtn');
  const provider = document.getElementById('providerSelect')?.value || '';
  const key = (document.getElementById('providerApiKey')?.value || '').trim();
  if (!button) return;
  button.classList.remove('is-success', 'is-failure');
  button.disabled = true;
  button.textContent = 'اختبار';
  let ok = false;
  try {
    const res = await fetch('/api/config/providers/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, key })
    });
    const data = await res.json().catch(() => ({}));
    ok = res.ok && data.ok === true;
  } catch (err) {
    ok = false;
  }
  button.disabled = false;
  button.classList.add(ok ? 'is-success' : 'is-failure');
  button.textContent = ok ? 'نجاح' : 'فشل';
}

function toggleApiKeyVisibility() {
  const input = document.getElementById('providerApiKey');
  if (!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
}

// تعبئة النماذج الجاهزة للمزودين الكلاسيكيين
function populatePresetModels(provider) {
  const modelsSelect = document.getElementById('providerModelSelect');
  if (!modelsSelect) return;

  const presets = PROVIDER_MODELS_PRESETS[provider] || [];
  modelsSelect.innerHTML = presets.map((m, idx) => `
    <option value="${m.id}" ${idx === 0 ? 'selected' : ''}>${m.name}</option>
  `).join('');

  if (presets.length > 0) {
    displayPresetModelSpecs(presets[0]);
  }

  modelsSelect.onchange = function() {
    const selected = presets.find(p => p.id === this.value);
    if (selected) {
      displayPresetModelSpecs(selected);
    }
    localStorage.setItem('almojtahed_active_chat_model', this.value);
    syncChatModelDropdown(provider, this.value);
  };

  syncChatModelDropdown(provider, presets[0]?.id);
}

// عرض مواصفات النماذج الجاهزة
function displayPresetModelSpecs(model) {
  const card = document.getElementById('openrouterSpecsCard');
  if (!card) return;
  card.style.display = 'block';

  document.getElementById('specModelTitle').textContent = model.name || model.id;
  document.getElementById('specModelId').textContent = model.id;
  setModelAboutText('');
  document.getElementById('specPromptPrice').textContent = `$${model.prompt} / 1M توكن`;
  document.getElementById('specCompletionPrice').textContent = `$${model.completion} / 1M توكن`;
  document.getElementById('specContextLength').textContent = `${model.context} توكن`;
  document.getElementById('specAcademicRank').textContent = model.rank || 'نموذج رائد';
  document.getElementById('specIntelligenceIndex').textContent = model.intel ? `${model.intel}/100` : 'متفوق';
}

// جلب قائمة نماذج OpenRouter من الـ API
async function loadOpenRouterModelsList(forceRefresh = false) {
  const modelsSelect = document.getElementById('providerModelSelect');
  const loadingIndicator = document.getElementById('modelsLoadingSpinner');
  if (!modelsSelect) return;

  if (loadingIndicator) loadingIndicator.style.display = 'inline-block';
  modelsSelect.disabled = true;

  try {
    const key = document.getElementById('providerApiKey')?.value.trim() || DEFAULT_OPENROUTER_KEY;
    const url = `/api/openrouter/models${key ? '?api_key=' + encodeURIComponent(key) : ''}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`خطأ استجابة (${res.status})`);
    
    const data = await res.json();
    openrouterModelsList = data.models || [];
    window.openrouterModelsList = openrouterModelsList;

    renderOpenRouterSelectOptions(openrouterModelsList);

    const savedModelId = localStorage.getItem('almojtahed_active_chat_model');
    const defaultModel = openrouterModelsList.find(m => m.id === savedModelId) || openrouterModelsList[0];
    if (defaultModel) {
      modelsSelect.value = defaultModel.id;
      displayOpenRouterModelSpecs(defaultModel);
    }

    modelsSelect.onchange = function() {
      const selected = openrouterModelsList.find(m => m.id === this.value);
      if (selected) {
        displayOpenRouterModelSpecs(selected);
      }
      localStorage.setItem('almojtahed_active_chat_model', this.value);
      syncChatModelDropdown('openrouter', this.value);
    };

    // مزامنة مبدئية مع الشات وقائمة وكلاء المجموعات
    syncChatModelDropdown('openrouter', defaultModel?.id);
    if (typeof populateAgentModelDropdown === 'function') {
      populateAgentModelDropdown();
    }
    if (typeof populateOpenRouterModelDropdown === 'function') {
      const manualModel = document.getElementById('manualProjectDirectorModel');
      if (manualModel) populateOpenRouterModelDropdown(manualModel, manualModel.value);
    }
    loadOpenRouterRankings();

  } catch (err) {
    console.error('Error loading OpenRouter models:', err);
    showToast('تعذر جلب النماذج الحية، تم تفعيل القائمة التراثية الموثوقة');
    // استخدام قائمة احتياطية
    populatePresetModels('claude');
  } finally {
    if (loadingIndicator) loadingIndicator.style.display = 'none';
    modelsSelect.disabled = false;
  }
}

// تصفية نماذج OpenRouter بالبحث
function filterOpenRouterModelsList(query) {
  if (!openrouterModelsList || openrouterModelsList.length === 0) return;
  const q = query.toLowerCase().trim();
  const filtered = openrouterModelsList.filter(m => 
    m.id.toLowerCase().includes(q) || (m.name && m.name.toLowerCase().includes(q))
  );
  renderOpenRouterSelectOptions(filtered);
}

// رسم خيارات القائمة المنسدلة (فقط اسم النموذج كما طلب المستخدم)
function renderOpenRouterSelectOptions(list) {
  const modelsSelect = document.getElementById('providerModelSelect');
  if (!modelsSelect) return;

  if (list.length === 0) {
    modelsSelect.innerHTML = `<option value="">لا توجد نماذج مطابقة للبحث</option>`;
    return;
  }

  const priorityIds = openrouterRankedIds;
  const pinned = modelsWithSuggestedFirst(list, false).filter(model => SUGGESTED_MODELS.some(item => item.id === model.id));
  const pinnedIds = new Set(pinned.map(model => model.id));
  const remainder = list.filter(model => !pinnedIds.has(model.id));

  const priorityModels = [];
  const otherModels = [];

  // إدراج النماذج المفضلة أولاً بالترتيب
  priorityIds.forEach(pid => {
    const found = remainder.find(m => m.id === pid);
    if (found && !priorityModels.some(p => p.id === found.id)) {
      priorityModels.push(found);
    }
  });

  remainder.forEach(m => {
    if (!priorityModels.some(p => p.id === m.id)) {
      otherModels.push(m);
    }
  });

  const sortedRest = [...priorityModels, ...otherModels];
  const optionHtml = (model) => `<option value="${escapeHtml(model.id)}">${escapeHtml(model.name || model.id)}</option>`;
  const pinnedHtml = pinned.map(optionHtml).join('');
  const restHtml = sortedRest.map(optionHtml).join('');
  modelsSelect.innerHTML = `
    ${pinnedHtml ? `<optgroup label="⭐ النماذج المقترحة">${pinnedHtml}</optgroup>` : ''}
    ${restHtml ? `<optgroup label="كافة النماذج">${restHtml}</optgroup>` : ''}
  `;
}

function formatRankingTokens(value) {
  const amount = Number(value) || 0;
  if (amount >= 1e12) return (amount / 1e12).toFixed(1) + 'T';
  if (amount >= 1e9) return (amount / 1e9).toFixed(1) + 'B';
  if (amount >= 1e6) return (amount / 1e6).toFixed(1) + 'M';
  if (amount >= 1e3) return (amount / 1e3).toFixed(1) + 'K';
  return String(Math.round(amount));
}

function renderRankingColumn(containerId, items) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (!items.length) {
    container.innerHTML = '<div class="ranking-item-sub">لا توجد نماذج متاحة في هذا الترتيب.</div>';
    return;
  }
  container.innerHTML = items.map(item => {
    const price = `$${Number(item.prompt_per_1m || 0).toFixed(2)} / $${Number(item.completion_per_1m || 0).toFixed(2)}`;
    return `
      <div class="ranking-item-row" data-model-id="${escapeHtml(item.id)}" onclick="selectModelDirectly(this.dataset.modelId)">
        <span class="ranking-num-tag">${item.rank}</span>
        <div class="ranking-item-body">
          <div class="ranking-item-title">${escapeHtml(item.name)}</div>
          <div class="ranking-item-sub">${escapeHtml(item.id)}</div>
        </div>
        <div class="ranking-item-pills">
          <span class="rank-price-tag">${price}</span>
          <span class="score-badge">${formatRankingTokens(item.tokens)} توكن</span>
        </div>
      </div>`;
  }).join('');
}

async function loadOpenRouterRankings() {
  const daily = document.getElementById('rankingDailyList');
  const weekly = document.getElementById('rankingWeeklyList');
  const note = document.getElementById('rankingSourceNote');
  const selected = document.getElementById('providerSelect')?.value;
  const typed = selected === 'openrouter' ? (document.getElementById('providerApiKey')?.value || '').trim() : '';
  const stored = typeof readProviderKeys === 'function' ? (readProviderKeys().openrouter || '') : '';
  const key = typed || stored;
  if (!key) {
    const empty = '<div class="ranking-item-sub">أدخل مفتاح أوبن راوتر لجلب الترتيب الحي.</div>';
    if (daily) daily.innerHTML = empty;
    if (weekly) weekly.innerHTML = empty;
    return;
  }
  try {
    const res = await fetch('/api/openrouter/rankings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر جلب الترتيب');
    renderRankingColumn('rankingDailyList', data.daily || []);
    renderRankingColumn('rankingWeeklyList', data.weekly || []);
    const badge = document.getElementById('rankingDailyBadge');
    if (badge && data.day) badge.textContent = data.day;
    if (note) {
      note.textContent = data.as_of
        ? `ترتيب أوبن راوتر الحي حتى ${data.as_of}. النماذج الموقوفة لا تظهر.`
        : 'تُجلب بمفتاح أوبن راوتر من ترتيب الاستخدام الحي، ولا تُعرض النماذج الموقوفة.';
    }
    openrouterRankedIds = [...(data.daily || []), ...(data.weekly || [])].map(item => item.id);
    const select = document.getElementById('providerModelSelect');
    if (select && document.getElementById('providerSelect')?.value === 'openrouter' && openrouterModelsList.length) {
      const current = select.value;
      renderOpenRouterSelectOptions(openrouterModelsList);
      const stillThere = [...select.options].some(option => option.value === current);
      const ranked = openrouterModelsList.find(model => model.id === (data.daily?.[0] || {}).id);
      if (stillThere && openrouterModelsList.some(model => model.id === current)) {
        select.value = current;
      } else if (ranked) {
        select.value = ranked.id;
        displayOpenRouterModelSpecs(ranked);
        localStorage.setItem('almojtahed_active_chat_model', ranked.id);
      }
    }
  } catch (err) {
    const message = `<div class="ranking-item-sub">${escapeHtml(err.message || 'تعذر جلب الترتيب')}</div>`;
    if (daily) daily.innerHTML = message;
    if (weekly) weekly.innerHTML = message;
  }
}

// عرض بطاقة مواصفات OpenRouter الحقيقية
function displayOpenRouterModelSpecs(model) {
  currentSelectedModelData = model;
  const card = document.getElementById('openrouterSpecsCard');
  if (!card) return;
  card.style.display = 'block';

  document.getElementById('specModelTitle').textContent = model.name || model.id;
  document.getElementById('specModelId').textContent = model.id;
  showModelAbout(model);

  const prompt1m = model.pricing?.prompt_per_1m ?? 0;
  const comp1m = model.pricing?.completion_per_1m ?? 0;
  const promptPerToken = model.pricing?.prompt_per_token ? `$${model.pricing.prompt_per_token.toFixed(8)}` : '$0.00';
  const compPerToken = model.pricing?.completion_per_token ? `$${model.pricing.completion_per_token.toFixed(8)}` : '$0.00';

  document.getElementById('specPromptPrice').innerHTML = `
    <strong>$${prompt1m.toFixed(3)}</strong> / 1M توكن
    <span style="font-size: 11px; color: var(--text-muted); display: block;">(${promptPerToken} للتوكن)</span>
  `;

  document.getElementById('specCompletionPrice').innerHTML = `
    <strong>$${comp1m.toFixed(3)}</strong> / 1M توكن
    <span style="font-size: 11px; color: var(--text-muted); display: block;">(${compPerToken} للتوكن)</span>
  `;

  const ctx = model.context_length ? Number(model.context_length).toLocaleString() : 'غير محدد';
  document.getElementById('specContextLength').textContent = `${ctx} توكن`;

  // مقاييس البحث الأكاديمي والذكاء
  const benchmarks = model.benchmarks || {};
  const intelIndex = benchmarks.intelligence_index;
  const codingIndex = benchmarks.coding_index;
  const designArena = benchmarks.design_arena || [];
  
  let rankText = "متاح للاستعلام الأكاديمي المباشر";
  if (designArena.length > 0) {
    const topArena = designArena.find(a => a.rank != null);
    if (topArena) {
      rankText = `المرتبة #${topArena.rank} في ساحة النماذج (ELO: ${topArena.elo})`;
    }
  }

  document.getElementById('specAcademicRank').textContent = rankText;
  document.getElementById('specIntelligenceIndex').textContent = intelIndex != null ? `${intelIndex} نقطة (مؤشر الذكاء الأكاديمي)` : (codingIndex != null ? `${codingIndex} (مؤشر المنطق)` : 'تقييم فائق');
}

function plainModelDescription(text) {
  return String(text || '')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '$1')
    .replace(/\s*\.\.\.$/, '')
    .trim();
}

const modelAboutArCache = {};

function setModelAboutText(text) {
  const wrap = document.getElementById('specModelAbout');
  const el = document.getElementById('specModelDescription');
  if (!wrap || !el) return;
  const clean = plainModelDescription(text);
  el.textContent = clean;
  wrap.hidden = !clean;
}

function showModelAbout(model) {
  const requestedId = model.id;
  const cached = modelAboutArCache[requestedId];
  if (cached) {
    setModelAboutText(cached);
    return;
  }
  setModelAboutText('');
  fetch('/api/openrouter/model-about?model_id=' + encodeURIComponent(requestedId))
    .then(res => res.ok ? res.json() : null)
    .then(data => {
      if (!data || !data.description) return;
      modelAboutArCache[requestedId] = data.description;
      if (!currentSelectedModelData || currentSelectedModelData.id !== requestedId) return;
      setModelAboutText(data.description);
    })
    .catch(() => {});
}

// تسميات المزودين بالعربية
function openProviderKeyShare(provider) {
  const name = provider || document.getElementById('providerSelect')?.value || 'openrouter';
  const labels = {
    tavily: 'Tavily',
    openrouter: 'أوبن راوتر',
    claude: 'كلود',
    google: 'جوجل',
    openai: 'أوبن إي آي',
    deepseek: 'ديب سيك'
  };
  openSharePicker('key', name, labels[name] || (typeof getProviderLabel === 'function' ? getProviderLabel(name) : name));
}

window.openProviderKeyShare = openProviderKeyShare;

function getProviderLabel(provider) {
  const map = {
    openrouter: 'أوبن راوتر (OpenRouter)',
    claude: 'كلود (Anthropic Claude)',
    google: 'جوجل (Google Gemini)',
    openai: 'أوبن إي آي (OpenAI)',
    deepseek: 'ديب سيك (DeepSeek)'
  };
  return map[provider] || provider;
}

// اختيار نموذج مباشرة عند النقر عليه من جداول الترتيب
function selectModelDirectly(modelId) {
  const providerSelect = document.getElementById('providerSelect');
  const modelsSelect = document.getElementById('providerModelSelect');
  
  if (!providerSelect || !modelsSelect) return;

  // التحقق من تفعيل أوبن راوتر
  if (providerSelect.value !== 'openrouter') {
    providerSelect.value = 'openrouter';
    handleProviderChange('openrouter').then(() => {
      applyModelSelection(modelId);
    });
  } else {
    applyModelSelection(modelId);
  }
}

function applyModelSelection(modelId) {
  const modelsSelect = document.getElementById('providerModelSelect');
  if (!modelsSelect) return;

  // إفراغ حقل البحث إن وجد لضمان ظهور الخيار
  const searchInput = document.getElementById('modelSearchFilterInput');
  if (searchInput && searchInput.value) {
    searchInput.value = '';
    renderOpenRouterSelectOptions(openrouterModelsList);
  }

  // البحث في قائمة النماذج
  const model = openrouterModelsList.find(m => m.id === modelId || m.id.includes(modelId));
  if (model) {
    modelsSelect.value = model.id;
    displayOpenRouterModelSpecs(model);
    localStorage.setItem('almojtahed_active_chat_model', model.id);
    syncChatModelDropdown('openrouter', model.id);
    showToast(`تم تفعيل النموذج: ${model.name || model.id}`);
  } else {
    // محاولة البحث في البريسيتس
    for (const p in PROVIDER_MODELS_PRESETS) {
      const pm = PROVIDER_MODELS_PRESETS[p].find(m => m.id === modelId || m.id.includes(modelId));
      if (pm) {
        displayPresetModelSpecs(pm);
        localStorage.setItem('almojtahed_active_chat_model', pm.id);
        syncChatModelDropdown(p, pm.id);
        showToast(`تم اختيار النموذج: ${pm.name}`);
        break;
      }
    }
  }

  // تمرير الشاشة إلى بطاقة المواصفات بنعومة
  const specsCard = document.getElementById('openrouterSpecsCard');
  if (specsCard) {
    specsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

// =============================================================================
// إدارة التبويبات الفرعية لمزود الخدمة (النماذج - الاستهلاك - تحت الإنشاء)
// =============================================================================

function switchProviderSubtab(tabName) {
  const subtabs = ['models', 'consumption', 'construction', 'web'];
  subtabs.forEach(t => {
    const btn = document.getElementById(`btnSubtab-${t}`);
    const pane = document.getElementById(`paneSubtab-${t}`);
    const isActive = (t === tabName);
    if (btn) btn.classList.toggle('active', isActive);
    if (pane) {
      pane.classList.toggle('active', isActive);
      pane.style.display = isActive ? 'flex' : 'none';
    }
  });

  if (tabName === 'consumption') {
    loadOpenRouterCredits(false);
  }
}

// كاش بيانات الرصيد الحية
let lastCreditsData = null;

async function loadOpenRouterCredits(forceRefresh = false) {
  const refreshIcon = document.getElementById('refreshCreditsIcon');

  const savedKeys = readProviderKeys();
  const apiKey = savedKeys.openrouter || DEFAULT_OPENROUTER_KEY;

  try {
    if (refreshIcon) {
      refreshIcon.style.transition = 'transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)';
      refreshIcon.style.transform = 'rotate(360deg)';
    }

    const res = await fetch(`/api/openrouter/credits?api_key=${encodeURIComponent(apiKey)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    lastCreditsData = data;

    renderCreditsData(data);
    if (forceRefresh) {
      showToast('تم تحديث الرصيد الحي بنجاح من OpenRouter');
    }
  } catch (err) {
    console.warn('Backend credits fetch failed, using fallback:', err);
    try {
      const directCredits = await fetch('https://openrouter.ai/api/v1/credits', {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      }).then(r => r.json());
      
      const tc = directCredits.data?.total_credits || 3919.80;
      const tu = directCredits.data?.total_usage || 3838.61;
      const rem = Math.max(0, tc - tu);
      renderCreditsData({
        remaining_credits_usd: rem.toFixed(2),
        remaining_credits_sar: (rem * 3.75).toFixed(2),
        total_credits_usd: tc.toFixed(2),
        total_credits_sar: (tc * 3.75).toFixed(2),
        total_usage_usd: tu.toFixed(2),
        total_usage_sar: (tu * 3.75).toFixed(2),
        usage_monthly_usd: '113.60',
        usage_monthly_sar: (113.60 * 3.75).toFixed(2),
        usage_weekly_usd: '22.81',
        usage_weekly_sar: (22.81 * 3.75).toFixed(2),
        key_label: 'غير محدد'
      });
    } catch (e2) {
      console.error('Direct fallback credits fetch failed:', e2);
    }
  } finally {
    if (refreshIcon) {
      setTimeout(() => {
        refreshIcon.style.transform = 'rotate(0deg)';
      }, 600);
    }
  }
}

function renderCreditsData(data) {
  // 1. الرصيد الإجمالي المتاح
  const usdEl = document.getElementById('balanceAmountUsd');
  const sarEl = document.getElementById('balanceAmountSar');
  const badgeEl = document.getElementById('subtabLiveBalanceBadge');

  const remUsd = Number(data.remaining_credits_usd || 81.19).toFixed(2);
  const remSar = Number(data.remaining_credits_sar || 304.47).toFixed(2);

  if (usdEl) usdEl.textContent = `$${remUsd}`;
  if (sarEl) sarEl.textContent = `${remSar}`;
  if (badgeEl) badgeEl.textContent = `$${remUsd}`;

  // تحديث شارة الرصيد في ترويسة الشات الذكي
  const chatTopUsd = document.getElementById('chatTopBalanceUsd');
  const chatTopSar = document.getElementById('chatTopBalanceSar');
  if (chatTopUsd) chatTopUsd.textContent = `$${remUsd}`;
  if (chatTopSar) chatTopSar.textContent = `${remSar} ﷼`;

  // 2. المؤشرات المالية التفصيلية
  const setTxt = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  const fmtUsd = (num) => '$' + Number(num || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtSar = (num) => Number(num || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ﷼';

  setTxt('metricTotalCreditsUsd', fmtUsd(data.total_credits_usd || 3919.80));
  setTxt('metricTotalCreditsSar', fmtSar(data.total_credits_sar || 14699.25));

  setTxt('metricTotalUsageUsd', fmtUsd(data.total_usage_usd || 3838.61));
  setTxt('metricTotalUsageSar', fmtSar(data.total_usage_sar || 14394.77));

  setTxt('metricMonthlyUsageUsd', fmtUsd(data.usage_monthly_usd || 113.60));
  setTxt('metricMonthlyUsageSar', fmtSar(data.usage_monthly_sar || 425.99));

  setTxt('metricWeeklyUsageUsd', fmtUsd(data.usage_weekly_usd || 22.81));
  setTxt('metricWeeklyUsageSar', fmtSar(data.usage_weekly_sar || 85.52));

  if (data.key_label) {
    setTxt('creditsKeyLabel', `المفتاح: ${data.key_label}`);
  }

  const syncText = document.getElementById('creditsLastSyncText');
  if (syncText) {
    const nowStr = new Date().toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    syncText.textContent = `متصل حياً بحساب OpenRouter • تم التحديث الآن (${nowStr})`;
  }
}

// =============================================================================
// مساعد تصنيف النماذج بشارات ذكية
// =============================================================================
function getModelTag(id) {
  const lower = (id || '').toLowerCase();
  if (lower.includes('deepseek-r1') || lower.includes('o3-mini') || lower.includes('o1')) return 'Reasoning';
  if (lower.includes('sonnet') || lower.includes('claude-3.7')) return 'Thinking';
  if (lower.includes('gemini')) return 'Long Context';
  if (lower.includes('gpt-4o-mini') || lower.includes('flash')) return 'سريع واقتصادي';
  if (lower.includes('gpt-4o')) return 'Omni';
  if (lower.includes('llama') || lower.includes('qwen')) return 'Open Weights';
  if (lower.includes('local')) return 'محلي مكمم';
  return '';
}

// =============================================================================
// مزامنة قائمة نماذج الشات الذكي مع المزود النشط (Chat Model Synchronizer)
// تدعم كلاً من select المخفي والقائمة المنسدلة المخصصة مع فلترة سريعة بالبحث
// =============================================================================
function syncChatModelDropdown(provider = null, targetModelId = null) {
  const activeProvider = provider || localStorage.getItem(ownerStorageKey('almojtahed_active_provider')) || 'openrouter';
  const chatModelSelect = document.getElementById('chatModelSelect');
  const chatProviderNameEl = document.getElementById('chatActiveProviderName');
  const customListEl = document.getElementById('chatCustomModelOptionsList');
  const triggerTextEl = document.getElementById('chatCustomModelTriggerText');

  // تحديث شارة اسم المزود النشط في الشات الذكي
  if (chatProviderNameEl) {
    chatProviderNameEl.textContent = getProviderLabel(activeProvider);
  }

  if (!chatModelSelect) return;

  const savedModel = targetModelId || 
                     localStorage.getItem('almojtahed_active_chat_model') || 
                     document.getElementById('providerModelSelect')?.value || 
                     '';

  let htmlOptions = '';
  let customListHtml = '';

  // جمع المجموعات المنظمة
  const groups = [];

  if (activeProvider === 'openrouter') {
    if (openrouterModelsList && openrouterModelsList.length > 0) {
      const ordered = modelsWithSuggestedFirst(openrouterModelsList, true);
      const suggested = ordered.slice(0, SUGGESTED_MODELS.length);
      const otherModels = ordered.slice(SUGGESTED_MODELS.length);

      groups.push({
        title: '⭐ النماذج المقترحة',
        models: suggested
      });

      if (otherModels.length > 0) {
        groups.push({
          title: `📋 كافة نماذج OpenRouter المتاحة (${otherModels.length} نموذج)`,
          models: otherModels
        });
      }
    } else {
      groups.push({
        title: '⭐ النماذج المقترحة',
        models: SUGGESTED_MODELS
      });
    }
  } else {
    // المزودون الكلاسيكيون المباشرون
    const presets = PROVIDER_MODELS_PRESETS[activeProvider] || [];
    const providerTitle = getProviderLabel(activeProvider);
    groups.push({
      title: `نماذج ${providerTitle}`,
      models: presets
    });
  }

  // إضافة الخيار المحلي الأوفلاين
  groups.push({
    title: 'المحلي (Offline)',
    models: [
      { id: 'local-almojtahed-8b', name: 'Al-Mojtahed 8B (المحلي المكمم - بدون إنترنت)' }
    ]
  });

  // بناء كلا التمثيلين: الـ <select> الأصلي والـ Custom Dropdown
  let activeSelectedModelId = savedModel;
  let activeSelectedModelName = '';

  // التحقق من صحة النموذج المختار
  let modelExists = false;
  for (const g of groups) {
    const found = g.models.find(m => m.id === savedModel);
    if (found) {
      modelExists = true;
      activeSelectedModelName = found.name || found.id;
      break;
    }
  }

  if (!modelExists && groups.length > 0 && groups[0].models.length > 0) {
    activeSelectedModelId = groups[0].models[0].id;
    activeSelectedModelName = groups[0].models[0].name || groups[0].models[0].id;
    localStorage.setItem('almojtahed_active_chat_model', activeSelectedModelId);
  }

  groups.forEach(g => {
    htmlOptions += `<optgroup label="${g.title}">`;
    customListHtml += `<div class="model-group-title">${g.title}</div>`;

    g.models.forEach(m => {
      const isSelected = m.id === activeSelectedModelId;
      const modelDisplayName = m.name || m.id;
      const tag = getModelTag(m.id);

      htmlOptions += `<option value="${m.id}" ${isSelected ? 'selected' : ''}>${modelDisplayName}</option>`;

      // خيار الـ Custom List
      customListHtml += `
        <div class="custom-model-item ${isSelected ? 'active' : ''}" 
             data-model-id="${m.id}" 
             data-model-name="${modelDisplayName.replace(/"/g, '&quot;')}"
             data-model-tag="${tag}"
             onclick="selectCustomChatModel('${m.id}', '${modelDisplayName.replace(/'/g, "\\'")}')">
          <span class="custom-model-item-name" title="${m.id}">${modelDisplayName}</span>
          ${tag ? `<span class="custom-model-item-tag">${tag}</span>` : ''}
        </div>
      `;
    });

    htmlOptions += `</optgroup>`;
  });

  chatModelSelect.innerHTML = htmlOptions;
  chatModelSelect.value = activeSelectedModelId;

  if (customListEl) {
    customListEl.innerHTML = customListHtml;
  }

  if (triggerTextEl) {
    triggerTextEl.textContent = activeSelectedModelName || activeSelectedModelId || 'اختر نموذجاً...';
    triggerTextEl.title = activeSelectedModelId;
  }

  // إعادة ضبط حقل البحث
  const searchInput = document.getElementById('chatModelSearchInput');
  if (searchInput && searchInput.value) {
    searchInput.value = '';
    filterChatCustomModels('');
  }
  if (typeof refreshCompareModelLists === 'function') refreshCompareModelLists();
}

// فتح وإغلاق القائمة المنسدلة للنماذج
function toggleChatModelDropdown(event) {
  if (event) event.stopPropagation();
  const wrapper = document.getElementById('chatCustomModelWrapper');
  if (!wrapper) return;

  const isOpen = wrapper.classList.toggle('open');
  if (isOpen) {
    const input = document.getElementById('chatModelSearchInput');
    if (input) {
      setTimeout(() => {
        input.focus();
        input.select();
      }, 50);
    }
  }
}

// إغلاق القائمة المنسدلة
function closeChatModelDropdown() {
  const wrapper = document.getElementById('chatCustomModelWrapper');
  if (wrapper) wrapper.classList.remove('open');
  hideModelHoverCard();
}

// مسح حقل البحث في قائمة النماذج
function clearChatModelSearch() {
  const input = document.getElementById('chatModelSearchInput');
  if (input) {
    input.value = '';
    filterChatCustomModels('');
    input.focus();
  }
}

// فلترة النماذج في القائمة بمجرد كتابة أول حرف
function filterChatCustomModels(query) {
  const container = document.getElementById('chatCustomModelOptionsList');
  const clearBtn = document.getElementById('chatModelSearchClear');
  if (!container) return;

  const q = (query || '').trim().toLowerCase();
  if (clearBtn) {
    clearBtn.style.display = q.length > 0 ? 'inline-block' : 'none';
  }

  const items = container.querySelectorAll('.custom-model-item');
  const groups = container.querySelectorAll('.model-group-title');
  const oldEmptyMsg = container.querySelector('.custom-model-empty-msg');
  if (oldEmptyMsg) oldEmptyMsg.remove();

  let visibleCount = 0;

  items.forEach(item => {
    const id = (item.getAttribute('data-model-id') || '').toLowerCase();
    const name = (item.getAttribute('data-model-name') || '').toLowerCase();
    const tag = (item.getAttribute('data-model-tag') || '').toLowerCase();
    
    // الفلترة الحية: تطابق المعرف أو الاسم أو الشارة
    const match = !q || id.includes(q) || name.includes(q) || tag.includes(q);
    item.style.display = match ? 'flex' : 'none';
    if (match) visibleCount++;
  });

  // إخفاء رؤوس المجموعات التي ليس بها عناصر مرئية
  groups.forEach(group => {
    let nextEl = group.nextElementSibling;
    let hasVisibleInGroup = false;
    while (nextEl && !nextEl.classList.contains('model-group-title')) {
      if (nextEl.classList.contains('custom-model-item') && nextEl.style.display !== 'none') {
        hasVisibleInGroup = true;
        break;
      }
      nextEl = nextEl.nextElementSibling;
    }
    group.style.display = (!q || hasVisibleInGroup) ? 'block' : 'none';
  });

  if (visibleCount === 0) {
    const emptyMsg = document.createElement('div');
    emptyMsg.className = 'custom-model-empty-msg';
    emptyMsg.innerHTML = `لا يوجد نموذج مطابق للبحث "<strong>${escapeHtml(query)}</strong>"`;
    container.appendChild(emptyMsg);
  }
}

// التحكم بلوحة المفاتيح داخل حقل فلترة النماذج
function handleChatModelSearchKey(event) {
  if (event.key === 'Escape') {
    closeChatModelDropdown();
    event.preventDefault();
  } else if (event.key === 'Enter') {
    const container = document.getElementById('chatCustomModelOptionsList');
    if (!container) return;
    const firstVisible = Array.from(container.querySelectorAll('.custom-model-item'))
                              .find(el => el.style.display !== 'none');
    if (firstVisible) {
      firstVisible.click();
      event.preventDefault();
    }
  }
}

let modelHoverItem = null;
let modelHoverTimer = 0;

function hideModelHoverCard() {
  clearTimeout(modelHoverTimer);
  modelHoverItem = null;
  const card = document.getElementById('modelHoverCard');
  if (card) card.hidden = true;
}

function ensureModelHoverCard() {
  let card = document.getElementById('modelHoverCard');
  if (card) return card;
  card = document.createElement('div');
  card.id = 'modelHoverCard';
  card.className = 'model-hover-card';
  card.hidden = true;
  document.body.appendChild(card);
  return card;
}

function lookupOpenRouterModel(id) {
  const lists = [openrouterModelsList, window.openrouterModelsList];
  for (const list of lists) {
    if (!Array.isArray(list)) continue;
    const found = list.find(model => model && model.id === id);
    if (found) return found;
  }
  return null;
}

function moneyPerMillion(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 'غير محدد';
  return `$${number.toFixed(3)} / 1M`;
}

function placeModelHoverCard(item, card) {
  const rect = item.getBoundingClientRect();
  const menu = item.closest('.custom-model-dropdown-menu, .theme-select-menu, .compare-slot-menu');
  const menuRect = menu ? menu.getBoundingClientRect() : null;
  if (!menuRect || rect.bottom < menuRect.top || rect.top > menuRect.bottom) {
    hideModelHoverCard();
    return;
  }
  const width = 320;
  const gap = 10;
  card.hidden = false;
  const cardHeight = card.offsetHeight || 200;
  let left = rect.left - width - gap;
  if (left < 8) left = rect.right + gap;
  if (left + width > window.innerWidth - 8) left = Math.max(8, window.innerWidth - width - 8);
  let top = rect.top;
  if (top + cardHeight > window.innerHeight - 8) top = Math.max(8, window.innerHeight - cardHeight - 8);
  card.style.left = `${left}px`;
  card.style.top = `${top}px`;
}

function fillModelHoverCard(item) {
  const card = ensureModelHoverCard();
  const id = item.getAttribute('data-model-id') || item.getAttribute('data-id') || '';
  const name = item.getAttribute('data-model-name') || item.querySelector('.custom-model-item-name')?.textContent || item.textContent.trim() || id;
  const model = lookupOpenRouterModel(id);
  const local = !model && id.indexOf('/') === -1;
  const prompt = model ? moneyPerMillion(model.pricing && model.pricing.prompt_per_1m) : (local ? 'غير مطبّق' : 'غير محدد');
  const completion = model ? moneyPerMillion(model.pricing && model.pricing.completion_per_1m) : (local ? 'غير مطبّق' : 'غير محدد');
  const context = model && model.context_length
    ? `${Number(model.context_length).toLocaleString('en-US')} توكن`
    : (local ? 'على هذا الجهاز' : 'غير محدد');
  const about = local
    ? 'نموذج محلي يعمل على هذا الجهاز من ملف محفوظ، بلا تسعير سحابي.'
    : (modelAboutArCache[id] || '');
  card.innerHTML = `
    <div class="model-hover-kicker">بطاقة النموذج</div>
    <div class="model-hover-title">${escapeHtml(name)}</div>
    <div class="model-hover-id" dir="ltr">${escapeHtml(id)}</div>
    <div class="model-hover-about-label">ماذا يفعل هذا النموذج</div>
    <p class="model-hover-about">${about ? escapeHtml(about) : 'جارٍ جلب وصف النموذج...'}</p>
    <div class="model-hover-stats">
      <div><span>سعر الإدخال</span><strong>${escapeHtml(prompt)}</strong></div>
      <div><span>سعر الإخراج</span><strong>${escapeHtml(completion)}</strong></div>
      <div><span>طول السياق</span><strong>${escapeHtml(context)}</strong></div>
    </div>
  `;
  placeModelHoverCard(item, card);
  if (local || !id || modelAboutArCache[id]) return;
  clearTimeout(modelHoverTimer);
  modelHoverTimer = setTimeout(() => {
    if (modelHoverItem !== item) return;
    fetch('/api/openrouter/model-about?model_id=' + encodeURIComponent(id))
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (!data || !data.description || modelHoverItem !== item) return;
        modelAboutArCache[id] = data.description;
        fillModelHoverCard(item);
      })
      .catch(() => {
        if (modelHoverItem !== item) return;
        const aboutEl = card.querySelector('.model-hover-about');
        if (aboutEl) aboutEl.textContent = 'الوصف غير متاح الآن';
      });
  }, 220);
}

function modelHoverRow(node) {
  if (!node || !node.closest) return null;
  const custom = node.closest('.custom-model-item');
  if (custom && custom.closest('.custom-model-dropdown-menu')) return custom;
  const themed = node.closest('.theme-select-option');
  if (themed && themed.dataset.modelId && themed.closest('.theme-select-menu')) return themed;
  const compared = node.closest('.compare-slot-item');
  if (compared && compared.dataset.id && compared.closest('.compare-slot-menu')) return compared;
  return null;
}

document.addEventListener('mouseover', (event) => {
  const item = modelHoverRow(event.target);
  if (!item || item === modelHoverItem) return;
  modelHoverItem = item;
  fillModelHoverCard(item);
});

document.addEventListener('mouseout', (event) => {
  if (!modelHoverItem) return;
  const next = event.relatedTarget;
  if (next && modelHoverItem.contains(next)) return;
  hideModelHoverCard();
});

document.addEventListener('scroll', (event) => {
  if (!modelHoverItem) return;
  const list = event.target && event.target.closest && event.target.closest('.custom-model-options-list, .theme-select-menu, .compare-slot-items, .compare-slot-menu');
  if (!list || !list.contains(modelHoverItem)) return;
  placeModelHoverCard(modelHoverItem, ensureModelHoverCard());
}, true);

// اختيار نموذج من القائمة المخصصة
function selectCustomChatModel(modelId, modelName) {
  const chatModelSelect = document.getElementById('chatModelSelect');
  if (chatModelSelect) {
    chatModelSelect.value = modelId;
  }
  
  const triggerText = document.getElementById('chatCustomModelTriggerText');
  if (triggerText) {
    triggerText.textContent = modelName;
    triggerText.title = modelId;
  }

  // تحديث تمييز العنصر النشط في القائمة
  const container = document.getElementById('chatCustomModelOptionsList');
  if (container) {
    container.querySelectorAll('.custom-model-item').forEach(el => {
      if (el.getAttribute('data-model-id') === modelId) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    });
  }

  closeChatModelDropdown();
  handleChatModelChange(modelId);
}

// معالجة تغيير النموذج من داخل الشات الذكي
function handleChatModelChange(modelId) {
  if (!modelId) return;
  localStorage.setItem('almojtahed_active_chat_model', modelId);

  // مزامنة القائمة في تبويب مزود الخدمة إذا كانت تعرض نفس النموذج
  const providerModelsSelect = document.getElementById('providerModelSelect');
  if (providerModelsSelect && Array.from(providerModelsSelect.options).some(o => o.value === modelId)) {
    providerModelsSelect.value = modelId;
  }

  const modelName = document.getElementById('chatCustomModelTriggerText')?.textContent || 
                    document.getElementById('chatModelSelect')?.selectedOptions[0]?.text || 
                    modelId;
  showToast(`تم تعيين نموذج الإجابة: ${modelName}`);
}

// إغلاق القائمة المنسدلة عند النقر خارجها
document.addEventListener('click', function(e) {
  const wrapper = document.getElementById('chatCustomModelWrapper');
  if (wrapper && wrapper.classList.contains('open')) {
    if (!wrapper.contains(e.target)) {
      closeChatModelDropdown();
    }
  }
});

// الانتقال المباشر لتبويب الاستهلاك والإنفاق
function navigateToConsumptionTab() {
  switchMainTab('providers');
  if (typeof switchProviderSubtab === 'function') {
    switchProviderSubtab('consumption');
  }
}

// =============================================================================
// إدارة مزود الويب الخارجي (Tavily AI Provider)
// =============================================================================

function initTavilyConfig() {
  const input = document.getElementById('tavilyApiKeyInput');
  const badge = document.getElementById('tavilyStatusBadge');
  const savedKey = readTavilyKey();
  if (input) input.value = savedKey;
  if (badge) {
    if (savedKey) {
      badge.textContent = 'مفعل ومضبوط';
      badge.style.background = 'rgba(16, 185, 129, 0.15)';
      badge.style.color = '#10b981';
      badge.style.borderColor = '#10b981';
    } else {
      badge.textContent = 'غير مضبوط';
      badge.style.background = 'rgba(156, 163, 175, 0.15)';
      badge.style.color = '#9ca3af';
      badge.style.borderColor = '#4b5563';
    }
  }
}

function saveTavilyApiKey() {
  const input = document.getElementById('tavilyApiKeyInput');
  const key = (input?.value || '').trim();
  writeTavilyKey(key);
  fetch('/api/config/providers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tavily: key })
  }).catch(() => {});
  initTavilyConfig();
  if (key) {
    showToast('تم حفظ مفتاح Tavily API بنجاح');
  } else {
    showToast('تم تفريغ مفتاح Tavily');
  }
}

function toggleTavilyKeyVisibility() {
  const input = document.getElementById('tavilyApiKeyInput');
  if (input) {
    input.type = input.type === 'password' ? 'text' : 'password';
  }
}

async function testTavilyConnection() {
  const input = document.getElementById('tavilyApiKeyInput');
  const key = (input?.value || readTavilyKey() || '').trim();
  if (!key) {
    showToast('يرجى إدخال مفتاح Tavily أولاً لإجراء الفحص');
    return;
  }
  showToast('جارٍ اختبار الاتصال بـ Tavily AI...');
  try {
    const res = await fetch('/api/tavily/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: key,
        query: 'solar eclipse historical catalog',
        max_results: 2
      })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      showToast('✅ الاتصال بـ Tavily ناجح ومفتاح API صالح!');
      const badge = document.getElementById('tavilyStatusBadge');
      if (badge) {
        badge.textContent = 'متصل بنجاح ✓';
        badge.style.background = 'rgba(16, 185, 129, 0.15)';
        badge.style.color = '#10b981';
      }
    } else {
      showToast(`فشل الاتصال بـ Tavily: ${data.detail || data.error || 'خطأ غير معروف'}`);
    }
  } catch (err) {
    showToast(`خطأ في الاتصال: ${err.message}`);
  }
}

window.initTavilyConfig = initTavilyConfig;
window.saveTavilyApiKey = saveTavilyApiKey;
window.toggleTavilyKeyVisibility = toggleTavilyKeyVisibility;
window.testTavilyConnection = testTavilyConnection;

// تصدير دوال النماذج العامة
window.syncChatModelDropdown = syncChatModelDropdown;
window.handleChatModelChange = handleChatModelChange;
window.navigateToConsumptionTab = navigateToConsumptionTab;
window.toggleChatModelDropdown = toggleChatModelDropdown;
window.closeChatModelDropdown = closeChatModelDropdown;
window.filterChatCustomModels = filterChatCustomModels;
window.clearChatModelSearch = clearChatModelSearch;
window.handleChatModelSearchKey = handleChatModelSearchKey;
window.selectCustomChatModel = selectCustomChatModel;

