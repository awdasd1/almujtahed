// =============================================================================
// منظومة المجتهد - الكود الأساسي (app.js)
// إدارة التبويبات، الإعدادات، والسمات البصرية
// =============================================================================

// المفاتيح في التخزين المحلي (LocalStorage)
const STORAGE_KEYS = {
  SETTINGS: 'almojtahed_settings',
  THEME: 'almojtahed_theme',
  FONT_SIZE: 'almojtahed_text_size',
  ACTIVE_TAB: 'almojtahed_active_tab',
};

// الإعدادات الافتراضية
const DEFAULT_SETTINGS = {
  themePreset: 'sand',
  fontFamily: "'Amiri', 'Noto Naskh Arabic', 'Lotus Linotype', serif",
  textSize: 19,
  providers: {
    claude: '',
    google: '',
    deepseek: '',
    openai: '',
    openrouter: ''
  },
  modelParams: {
    systemPrompt: `أنت "المجتهد"، باحث تراثي وعالم فقهي رقمي دقيق متصل بالمكتبة الشاملة الكاملة. استند بدقة إلى النصوص الموثقة من كتب التراث، واذكر اسم الكتاب، والمؤلف، والجزء والصفحة بدقة مع الالتزام بالحياد العلمي والأمانة في النقل.`,
    temperature: 0.2,
    topK: 40,
    repPenalty: 1.1,
    maxTokens: 65536
  }
};

let currentSettings = { ...DEFAULT_SETTINGS };

// تهيئة التطبيق عند اكتمال تحميل الصفحة
document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  initTheme();
  initThemeSelects();
  setupEventListeners();

  // استعادة التبويب النشط من الـ URL hash أو التخزين المحلي
  const hashTab = (window.location.hash || '').replace('#', '');
  const savedTab = hashTab || localStorage.getItem(STORAGE_KEYS.ACTIVE_TAB) || 'search';
  if (['search', 'chat', 'agents', 'projects', 'providers'].includes(savedTab)) {
    switchMainTab(savedTab);
  }
});

// =============================================================================
// إدارة التبويبات الرئيسية (Main Navigation Tabs)
// =============================================================================
function switchMainTab(tabName) {
  // إخفاء كافة الألواح
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-tab-btn').forEach(el => el.classList.remove('active'));

  // تفعيل اللوح المطلوب والزر المقابل
  if (tabName === 'search') {
    document.getElementById('paneSearch').classList.add('active');
    document.getElementById('tabNavSearch').classList.add('active');
    if (typeof updateHybridToggleUI === 'function') {
      updateHybridToggleUI();
    }
  } else if (tabName === 'chat') {
    document.getElementById('paneChat').classList.add('active');
    document.getElementById('tabNavChat').classList.add('active');
    if (typeof syncChatModelDropdown === 'function') {
      syncChatModelDropdown();
    }
    if (typeof updateChatHybridToggleUI === 'function') {
      updateChatHybridToggleUI();
    }
  } else if (tabName === 'agents') {
    document.getElementById('paneAgents').classList.add('active');
    document.getElementById('tabNavAgents').classList.add('active');
    if (typeof renderGroupsTable === 'function') {
      renderGroupsTable();
    }
  } else if (tabName === 'projects') {
    const pane = document.getElementById('paneProjects');
    if (pane) pane.classList.add('active');
    const btn = document.getElementById('tabNavProjects');
    if (btn) btn.classList.add('active');
    if (typeof initProjectsTab === 'function') {
      initProjectsTab();
    }
  } else if (tabName === 'tools') {
    const pane = document.getElementById('paneTools');
    if (pane) pane.classList.add('active');
    const btn = document.getElementById('tabNavTools');
    if (btn) btn.classList.add('active');
    if (typeof initToolsTab === 'function') {
      initToolsTab();
    }
  } else if (tabName === 'providers') {
    document.getElementById('paneProviders').classList.add('active');
    document.getElementById('tabNavProviders').classList.add('active');
  }

  localStorage.setItem(STORAGE_KEYS.ACTIVE_TAB, tabName);
}

// =============================================================================
// السمات البصرية وتبديل الألوان (Claude Theme & Fonts)
// =============================================================================
const THEME_ORDER = ['sand', 'ink', 'oasis', 'silk', 'charcoal', 'marine', 'north-sand', 'lilac', 'marshmallow'];
const THEME_META = {
  sand: { label: 'الرملي', icon: 'sun' },
  ink: { label: 'الحبر', icon: 'square' },
  oasis: { label: 'الواحة', icon: 'leaf' },
  silk: { label: 'الحرير', icon: 'sparkles' },
  charcoal: { label: 'الفحمي', icon: 'gem' },
  marine: { label: 'البحري', icon: 'waves' },
  'north-sand': { label: 'رمال الشمال', icon: 'sun-medium' },
  lilac: { label: 'ليلك', icon: 'flower-2' },
  marshmallow: { label: 'مارشملو', icon: 'candy' },
};

function normalizeTheme(preset) {
  const map = {
    sand: 'sand',
    ink: 'ink',
    oasis: 'oasis',
    silk: 'silk',
    charcoal: 'charcoal',
    marine: 'marine',
    'north-sand': 'north-sand',
    lilac: 'lilac',
    marshmallow: 'marshmallow',
    light: 'sand',
    'claude-warm': 'sand',
    dark: 'ink',
    'claude-dark': 'ink',
    manuscript: 'oasis',
  };
  return map[preset] || 'sand';
}

function initTheme() {
  const savedTheme = normalizeTheme(localStorage.getItem(STORAGE_KEYS.THEME) || currentSettings.themePreset || 'sand');
  applyVisualThemePreset(savedTheme, { silent: true });

  const savedSize = localStorage.getItem(STORAGE_KEYS.FONT_SIZE) || 19;
  updateTextSize(savedSize, false);
}

function toggleTheme() {
  const current = normalizeTheme(document.documentElement.getAttribute('data-theme'));
  const next = THEME_ORDER[(THEME_ORDER.indexOf(current) + 1) % THEME_ORDER.length];
  applyVisualThemePreset(next);
}

function updateThemeIcon(theme) {
  const btn = document.getElementById('themeToggleBtn');
  if (!btn) return;
  const meta = THEME_META[normalizeTheme(theme)];
  btn.innerHTML = `<i data-lucide="${meta.icon}" class="icon" id="themeIconSun" aria-hidden="true"></i>`;
  btn.title = `الثيم الحالي: ${meta.label} — انقر للتبديل`;
  if (typeof window.refreshLucideIcons === 'function') {
    window.refreshLucideIcons();
  } else if (window.lucide && typeof lucide.createIcons === 'function') {
    lucide.createIcons({ attrs: { 'stroke-width': 1.75, class: 'icon' } });
  }
}

function applyVisualThemePreset(preset, options = {}) {
  const theme = normalizeTheme(preset);
  ['--bg-canvas', '--bg-surface', '--accent-clay'].forEach((name) => {
    document.documentElement.style.removeProperty(name);
  });
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(STORAGE_KEYS.THEME, theme);
  currentSettings.themePreset = theme;
  const select = document.getElementById('themePresetSelect');
  if (select && select.value !== theme) select.value = theme;
  updateThemeIcon(theme);
  if (!options.silent && typeof showToast === 'function') {
    showToast(`تم التبديل إلى ثيم ${THEME_META[theme].label}`);
  }
}

function initThemeSelects() {
  if (window.__themeSelectsReady) return;
  window.__themeSelectsReady = true;

  const menu = document.createElement('div');
  menu.className = 'theme-select-menu';
  menu.style.zIndex = '100020';
  menu.hidden = true;
  menu.setAttribute('role', 'listbox');
  document.body.appendChild(menu);

  let openSelect = null;
  let activeIndex = -1;

  function hookSelectSync() {
    ['value', 'selectedIndex'].forEach((prop) => {
      const desc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, prop);
      if (!desc || !desc.set || desc.set.__themeWrapped) return;
      const wrapped = function (next) {
        desc.set.call(this, next);
        this.dispatchEvent(new CustomEvent('theme-select-sync'));
      };
      wrapped.__themeWrapped = true;
      Object.defineProperty(HTMLSelectElement.prototype, prop, {
        get: desc.get,
        set: wrapped,
        configurable: true,
      });
    });
  }

  function optionButtons() {
    return [...menu.querySelectorAll('.theme-select-option:not(:disabled)')];
  }

  function closeMenu() {
    menu.hidden = true;
    menu.replaceChildren();
    menu.style.width = '';
    menu.style.minWidth = '';
    menu.style.top = '';
    menu.style.left = '';
    if (openSelect) {
      const wrap = openSelect.closest('.theme-select');
      if (wrap) wrap.classList.remove('is-open');
      const trigger = wrap && wrap.querySelector('.theme-select-trigger');
      if (trigger) trigger.setAttribute('aria-expanded', 'false');
    }
    openSelect = null;
    activeIndex = -1;
  }

  function syncLabel(select) {
    const wrap = select.closest('.theme-select');
    if (!wrap) return;
    const label = wrap.querySelector('.theme-select-label');
    const trigger = wrap.querySelector('.theme-select-trigger');
    const selected = select.selectedOptions[0];
    if (label) label.textContent = selected ? selected.textContent.trim() : '';
    if (trigger) trigger.disabled = select.disabled;
  }

  function placeMenu(trigger) {
    const rect = trigger.getBoundingClientRect();
    menu.style.width = 'max-content';
    menu.style.minWidth = Math.max(rect.width, 160) + 'px';
    menu.style.maxWidth = 'min(440px, calc(100vw - 16px))';
    menu.hidden = false;
    const width = Math.min(menu.offsetWidth, window.innerWidth - 16);
    menu.style.width = width + 'px';
    const height = Math.min(menu.scrollHeight, 280);
    const spaceBelow = window.innerHeight - rect.bottom;
    const top = spaceBelow < height + 12 && rect.top > height
      ? rect.top - height - 6
      : rect.bottom + 6;
    const left = Math.min(Math.max(8, rect.left), window.innerWidth - width - 8);
    menu.style.top = Math.max(8, top) + 'px';
    menu.style.left = left + 'px';
  }

  function paintMenu(select) {
    menu.replaceChildren();
    const addOption = (option) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'theme-select-option';
      item.textContent = option.textContent.trim() || option.value;
      item.disabled = option.disabled;
      item.setAttribute('role', 'option');
      if (option.selected) item.classList.add('is-selected');
      item.addEventListener('click', () => {
        if (option.disabled) return;
        const changed = select.value !== option.value;
        select.value = option.value;
        if (changed) select.dispatchEvent(new Event('change', { bubbles: true }));
        closeMenu();
      });
      menu.appendChild(item);
    };
    [...select.children].forEach((node) => {
      if (node.tagName === 'OPTGROUP') {
        const title = document.createElement('div');
        title.className = 'theme-select-group';
        title.textContent = node.label;
        menu.appendChild(title);
        [...node.children].forEach(addOption);
      } else if (node.tagName === 'OPTION') {
        addOption(node);
      }
    });
  }

  function openMenu(select) {
    if (select.disabled) return;
    if (openSelect === select && !menu.hidden) {
      closeMenu();
      return;
    }
    closeMenu();
    openSelect = select;
    const wrap = select.closest('.theme-select');
    const trigger = wrap.querySelector('.theme-select-trigger');
    wrap.classList.add('is-open');
    trigger.setAttribute('aria-expanded', 'true');
    paintMenu(select);
    placeMenu(trigger);
    const buttons = optionButtons();
    const current = menu.querySelector('.theme-select-option.is-selected');
    activeIndex = current ? buttons.indexOf(current) : 0;
    if (buttons[activeIndex]) buttons[activeIndex].classList.add('is-active');
  }

  function moveActive(step) {
    const buttons = optionButtons();
    if (!buttons.length) return;
    if (buttons[activeIndex]) buttons[activeIndex].classList.remove('is-active');
    activeIndex = (activeIndex + step + buttons.length) % buttons.length;
    buttons[activeIndex].classList.add('is-active');
    buttons[activeIndex].scrollIntoView({ block: 'nearest' });
  }

  function enhanceSelect(select) {
    if (!select || select.dataset.themeSelect === '1') return;
    if (select.multiple || select.size > 1 || select.hidden) return;
    const inline = select.getAttribute('style') || '';
    if (/display\s*:\s*none/i.test(inline)) return;
    select.dataset.themeSelect = '1';

    const wrap = document.createElement('div');
    wrap.className = 'theme-select';
    const fluid = select.classList.contains('form-select')
      || select.classList.contains('form-select-sm')
      || /width\s*:\s*100%/i.test(inline);
    if (fluid) wrap.classList.add('is-fluid');

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'theme-select-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    const label = document.createElement('span');
    label.className = 'theme-select-label';
    const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    chevron.setAttribute('viewBox', '0 0 24 24');
    chevron.setAttribute('class', 'theme-select-chevron');
    chevron.setAttribute('aria-hidden', 'true');
    chevron.innerHTML = '<path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>';
    trigger.append(label, chevron);

    select.classList.add('theme-select-native');
    select.tabIndex = -1;
    select.parentNode.insertBefore(wrap, select);
    wrap.append(trigger, select);
    syncLabel(select);

    trigger.addEventListener('click', () => openMenu(select));
    trigger.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        event.stopPropagation();
        if (menu.hidden || openSelect !== select) openMenu(select);
        else moveActive(event.key === 'ArrowDown' ? 1 : -1);
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        event.stopPropagation();
        if (menu.hidden || openSelect !== select) openMenu(select);
        else {
          const buttons = optionButtons();
          if (buttons[activeIndex]) buttons[activeIndex].click();
        }
      } else if (event.key === 'Escape') {
        closeMenu();
      }
    });
    select.addEventListener('theme-select-sync', () => syncLabel(select));
    select.addEventListener('change', () => syncLabel(select));
    select.addEventListener('focus', () => trigger.focus());

    const observer = new MutationObserver(() => {
      syncLabel(select);
      if (openSelect === select) paintMenu(select);
    });
    observer.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'label'] });
  }

  hookSelectSync();
  document.querySelectorAll('select').forEach(enhanceSelect);
  new MutationObserver((records) => {
    records.forEach((record) => {
      record.addedNodes.forEach((node) => {
        if (node.nodeType !== 1) return;
        if (node.matches && node.matches('select')) enhanceSelect(node);
        if (node.querySelectorAll) node.querySelectorAll('select').forEach(enhanceSelect);
      });
    });
  }).observe(document.body, { childList: true, subtree: true });

  document.addEventListener('click', (event) => {
    if (!openSelect) return;
    const wrap = openSelect.closest('.theme-select');
    if (wrap.contains(event.target) || menu.contains(event.target)) return;
    closeMenu();
  });
  document.addEventListener('keydown', (event) => {
    if (!openSelect || menu.hidden) return;
    if (event.key === 'Escape') closeMenu();
  });
  window.addEventListener('resize', closeMenu);
  window.addEventListener('scroll', (event) => {
    if (menu.contains(event.target)) return;
    closeMenu();
  }, true);
}

function applyFontFamily(font) {
  document.documentElement.style.setProperty('--font-amiri', font);
}

function updateTextSize(size, save = true) {
  document.documentElement.style.setProperty('--text-passage-size', size + 'px');
  const valEl = document.getElementById('textSizeValue');
  if (valEl) valEl.textContent = size + 'px';
  const slider = document.getElementById('textSizeSlider');
  if (slider && slider.value != size) slider.value = size;

  // تحديث النصوص المعروضة
  document.querySelectorAll('.result-text').forEach(el => {
    el.style.fontSize = size + 'px';
  });

  if (save) localStorage.setItem(STORAGE_KEYS.FONT_SIZE, size);
}

// =============================================================================
// نافذة الإعدادات الشاملة (Settings Modal)
// =============================================================================
function openSettingsModal() {
  syncSettingsToUI();
  if (typeof updateAuxiliaryModelsList === 'function') {
    updateAuxiliaryModelsList();
  }
  document.getElementById('settingsModalOverlay').classList.add('open');
}

function closeSettingsModal() {
  document.getElementById('settingsModalOverlay').classList.remove('open');
}

function handleModalOverlayClick(e) {
  if (e.target.id === 'settingsModalOverlay') {
    closeSettingsModal();
  }
}

function switchSettingsTab(tabKey) {
  // إخفاء محتوى التبويبات وإلغاء تنشيط الأزرار
  document.querySelectorAll('.settings-pane').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.settings-tab-btn').forEach(el => el.classList.remove('active'));

  // الخريطة بين المفاتيح والألواح
  const map = {
    'visual': { pane: 'setPaneVisual', btn: 'setNavVisual' },
    'providers': { pane: 'setPaneProviders', btn: 'setNavProviders' },
    'modelParams': { pane: 'setPaneModelParams', btn: 'setNavModelParams' },
    'auxiliary': { pane: 'setPaneAuxiliary', btn: 'setNavAuxiliary' }
  };

  const target = map[tabKey];
  if (target) {
    const pane = document.getElementById(target.pane);
    const btn = document.getElementById(target.btn);
    if (pane) pane.style.display = 'flex';
    if (btn) btn.classList.add('active');
  }
}

// قراءة الإعدادات من التخزين وحقنها في الحقول
function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.SETTINGS);
    if (raw) {
      currentSettings = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
    }
  } catch (e) {
    console.error('Error reading settings from localStorage:', e);
  }
}

// عكس الإعدادات على عناصر واجهة المستخدم في Modal
function syncSettingsToUI() {
  // المزودون والمفاتيح
  const p = currentSettings.providers || {};
  if (document.getElementById('apiKeyClaude')) document.getElementById('apiKeyClaude').value = p.claude || '';
  if (document.getElementById('apiKeyGoogle')) document.getElementById('apiKeyGoogle').value = p.google || '';
  if (document.getElementById('apiKeyDeepSeek')) document.getElementById('apiKeyDeepSeek').value = p.deepseek || '';
  if (document.getElementById('apiKeyOpenAI')) document.getElementById('apiKeyOpenAI').value = p.openai || '';
  if (document.getElementById('apiKeyOpenRouter')) document.getElementById('apiKeyOpenRouter').value = p.openrouter || '';

  // معلمات النموذج
  const m = currentSettings.modelParams || {};
  if (document.getElementById('systemPromptInput')) document.getElementById('systemPromptInput').value = m.systemPrompt || '';
  if (document.getElementById('paramTemperature')) {
    document.getElementById('paramTemperature').value = m.temperature ?? 0.2;
    document.getElementById('valTemp').textContent = m.temperature ?? 0.2;
  }
  if (document.getElementById('paramTopK')) {
    document.getElementById('paramTopK').value = m.topK ?? 40;
    document.getElementById('valTopK').textContent = m.topK ?? 40;
  }
  if (document.getElementById('paramRepPenalty')) {
    document.getElementById('paramRepPenalty').value = m.repPenalty ?? 1.1;
    document.getElementById('valRepPenalty').textContent = m.repPenalty ?? 1.1;
  }
  if (document.getElementById('paramMaxTokens')) {
    document.getElementById('paramMaxTokens').value = m.maxTokens ?? 65536;
    document.getElementById('valMaxTokens').textContent = Number(m.maxTokens ?? 65536).toLocaleString() + ' توكن';
  }
}

// حفظ كافة الإعدادات
function saveAllSettings() {
  currentSettings.providers = {
    claude: document.getElementById('apiKeyClaude')?.value.trim() || '',
    google: document.getElementById('apiKeyGoogle')?.value.trim() || '',
    deepseek: document.getElementById('apiKeyDeepSeek')?.value.trim() || '',
    openai: document.getElementById('apiKeyOpenAI')?.value.trim() || '',
    openrouter: document.getElementById('apiKeyOpenRouter')?.value.trim() || '',
  };

  currentSettings.modelParams = {
    systemPrompt: document.getElementById('systemPromptInput')?.value.trim() || '',
    temperature: parseFloat(document.getElementById('paramTemperature')?.value || 0.2),
    topK: parseInt(document.getElementById('paramTopK')?.value || 40),
    repPenalty: parseFloat(document.getElementById('paramRepPenalty')?.value || 1.1),
    maxTokens: parseInt(document.getElementById('paramMaxTokens')?.value || 65536),
  };

  localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(currentSettings));
  closeSettingsModal();
  showToast('تم حفظ كافة الإعدادات بنجاح');
}

// معالجة رفع التمبلت الجديد
function handleTemplateUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function (evt) {
    try {
      if (file.name.endsWith('.json')) {
        const custom = JSON.parse(evt.target.result);
        if (custom.colors) {
          for (const [k, v] of Object.entries(custom.colors)) {
            document.documentElement.style.setProperty(k, v);
          }
        }
        showToast('تم تحميل وتطبيق التمبلت بنجاح');
      } else if (file.name.endsWith('.css')) {
        const style = document.createElement('style');
        style.textContent = evt.target.result;
        document.head.appendChild(style);
        showToast('تم تطبيق ملف الستايل بنجاح');
      }
    } catch (err) {
      showToast('تعذر قراءة ملف التمبلت: ' + err.message);
    }
  };
  reader.readAsText(file);
}

// عرض رسالة سريعة Toast
function showToast(msg, duration = 3500) {
  let toast = document.getElementById('appGlobalToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'appGlobalToast';
    document.body.appendChild(toast);
  }
  toast.style.cssText = `
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--text-main);
    color: var(--bg-canvas);
    padding: 12px 26px;
    border-radius: var(--radius-pill);
    font-family: var(--font-amiri);
    font-size: 15.5px;
    font-weight: 700;
    box-shadow: 0 6px 24px rgba(0,0,0,0.35);
    z-index: 999999 !important;
    opacity: 0;
    transition: opacity 0.25s, transform 0.25s;
    pointer-events: none;
  `;

  toast.textContent = msg;
  toast.style.opacity = '1';
  toast.style.transform = 'translateX(-50%) translateY(0)';

  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(-50%) translateY(8px)';
  }, duration);
}

function setupEventListeners() {
  // اختصارات لوحة المفاتيح
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeSettingsModal();
      closeMaintenanceModal();
      if (typeof closeAgentModal === 'function') closeAgentModal();
    }
  });

  const maintBtn = document.getElementById('systemMaintenanceBtn');
  if (maintBtn) {
    maintBtn.addEventListener('click', (e) => {
      e.preventDefault();
      openMaintenanceModal();
    });
  }
}

// =============================================================================
// مركز الفحص الذاتي والصيانة التلقائية الشاملة للمنظومة
// =============================================================================
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function openMaintenanceModal() {
  const modal = document.getElementById('systemMaintenanceModal');
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('active', 'open');
    loadBackupsList();
  }
}

function closeMaintenanceModal() {
  const modal = document.getElementById('systemMaintenanceModal');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active', 'open');
  }
}

// -----------------------------------------------------------------------------
// مؤشر صحة وموارد السيرفر وتحسين الذاكرة (Server Health & Telemetry)
// -----------------------------------------------------------------------------
let serverHealthPoller = null;

function openServerHealthModal() {
  const modal = document.getElementById('serverHealthModal');
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('active', 'open');
    fetchServerHealth(false);
    if (window.lucide && typeof lucide.createIcons === 'function') {
      lucide.createIcons();
    }
  }
}

function closeServerHealthModal() {
  const modal = document.getElementById('serverHealthModal');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active', 'open');
  }
}

async function fetchServerHealth(showToast = false) {
  const refreshIcon = document.getElementById('serverRefreshIcon');
  if (refreshIcon) refreshIcon.style.animation = 'spin 0.8s linear infinite';

  try {
    const res = await fetch('/api/system/resources');
    if (!res.ok) throw new Error('تعذر جلب قراءات السيرفر');
    const data = await res.json();

    // 1. تحديث النقطة النابضة في الترويسة
    const pulseDot = document.getElementById('serverPulseDot');
    const modalLiveDot = document.getElementById('modalLiveDot');
    const summaryText = document.getElementById('serverHealthSummaryText');

    if (pulseDot) {
      pulseDot.className = 'status-pulse-dot status-' + (data.health_color || 'green');
    }
    if (modalLiveDot) {
      modalLiveDot.style.backgroundColor = data.health_color === 'red' ? '#ef4444' : (data.health_color === 'yellow' ? '#f59e0b' : '#10b981');
    }
    if (summaryText) {
      summaryText.textContent = data.health_label || 'السيرفر متصل ومستقر';
    }

    // 2. تحديث قراءات الرام (RAM)
    if (data.memory) {
      const ramPct = data.memory.percent || 0;
      const statRamVal = document.getElementById('statRamVal');
      const badgeRamStatus = document.getElementById('badgeRamStatus');
      const barRam = document.getElementById('barRam');
      const statRamDetail = document.getElementById('statRamDetail');
      const statRamFree = document.getElementById('statRamFree');

      if (statRamVal) statRamVal.textContent = `${data.memory.used_gb} GB (${ramPct}%)`;
      if (badgeRamStatus) {
        badgeRamStatus.textContent = `${ramPct}%`;
        badgeRamStatus.style.color = ramPct > 85 ? '#ef4444' : (ramPct > 75 ? '#f59e0b' : '#10b981');
      }
      if (barRam) {
        barRam.style.width = `${Math.min(100, Math.max(5, ramPct))}%`;
        barRam.style.background = ramPct > 85 ? 'linear-gradient(90deg, #f59e0b, #ef4444)' : 'linear-gradient(90deg, #10b981, #3b82f6)';
      }
      if (statRamDetail) statRamDetail.textContent = `مستخدم: ${data.memory.used_gb} GB من ${data.memory.total_gb} GB`;
      if (statRamFree) statRamFree.textContent = `شاغر: ${data.memory.free_gb} GB`;
    }

    // 3. تحديث قراءات القرص (Disk)
    if (data.disk) {
      const diskPct = data.disk.percent || 0;
      const statDiskVal = document.getElementById('statDiskVal');
      const badgeDiskStatus = document.getElementById('badgeDiskStatus');
      const barDisk = document.getElementById('barDisk');
      const statDiskDetail = document.getElementById('statDiskDetail');
      const statDiskFree = document.getElementById('statDiskFree');

      if (statDiskVal) statDiskVal.textContent = `${data.disk.used_gb} GB (${diskPct}%)`;
      if (badgeDiskStatus) {
        badgeDiskStatus.textContent = `${diskPct}%`;
        badgeDiskStatus.style.color = diskPct > 88 ? '#ef4444' : (diskPct > 80 ? '#f59e0b' : '#10b981');
      }
      if (barDisk) {
        barDisk.style.width = `${Math.min(100, Math.max(5, diskPct))}%`;
        barDisk.style.background = diskPct > 88 ? 'linear-gradient(90deg, #f59e0b, #ef4444)' : 'linear-gradient(90deg, #10b981, #f59e0b)';
      }
      if (statDiskDetail) statDiskDetail.textContent = `مستخدم: ${data.disk.used_gb} GB من ${data.disk.total_gb} GB`;
      if (statDiskFree) statDiskFree.textContent = `شاغر: ${data.disk.free_gb} GB`;
    }

    // 4. تحديث حالة Qdrant
    if (data.qdrant) {
      const statQdrantPoints = document.getElementById('statQdrantPoints');
      const statQdrantCollection = document.getElementById('statQdrantCollection');
      const badgeQdrantStatus = document.getElementById('badgeQdrantStatus');

      if (statQdrantPoints) statQdrantPoints.textContent = data.qdrant.points_count ? Number(data.qdrant.points_count).toLocaleString('en-US') : '8,148,092';
      if (statQdrantCollection) statQdrantCollection.textContent = data.qdrant.collection_name || 'shamela_almojtahed_8b_dense';
      if (badgeQdrantStatus) {
        badgeQdrantStatus.textContent = data.qdrant.connected ? 'متصل ومفهرس' : 'غير متصل';
        badgeQdrantStatus.style.color = data.qdrant.connected ? '#10b981' : '#ef4444';
      }
    }

    // 5. تحديث حالة النموذج
    if (data.model) {
      const statModelName = document.getElementById('statModelName');
      const statModelEngine = document.getElementById('statModelEngine');
      const badgeModelStatus = document.getElementById('badgeModelStatus');

      if (statModelName) statModelName.textContent = data.model.name || 'Al-Mojtahed 8B GGUF';
      if (statModelEngine) statModelEngine.textContent = data.model.loaded ? 'محمل في الذاكرة (سريع)' : 'غير محمل';
      if (badgeModelStatus) {
        badgeModelStatus.textContent = data.model.loaded ? 'جاهز' : 'متوقف';
        badgeModelStatus.style.color = data.model.loaded ? '#10b981' : '#ef4444';
      }
    }

    if (showToast && typeof showAlertDialog === 'function') {
      showAlertDialog({
        title: 'تم تحديث القراءات',
        message: 'تم جلب وتحديث مؤشرات موارد السيرفر الحية بنجاح.',
        type: 'success'
      });
    }
  } catch (err) {
    console.warn('Server health check notice:', err);
  } finally {
    if (refreshIcon) refreshIcon.style.animation = '';
  }
}

async function optimizeServerMemory() {
  const btn = document.getElementById('btnOptimizeServer');
  const feedback = document.getElementById('telemetryFeedbackMsg');
  const originalText = btn ? btn.innerHTML : '';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>جاري تنظيف الذاكرة... ⏳</span>';
  }

  try {
    const res = await fetch('/api/system/optimize', { method: 'POST' });
    const data = await res.json();

    if (feedback) {
      feedback.style.display = 'block';
      feedback.style.background = 'rgba(16, 185, 129, 0.12)';
      feedback.style.color = '#10b981';
      feedback.textContent = data.message || 'تم تنظيف الكاش والذاكرة المؤقتة بنجاح!';
      setTimeout(() => { feedback.style.display = 'none'; }, 6000);
    }

    await fetchServerHealth(false);
  } catch (err) {
    if (feedback) {
      feedback.style.display = 'block';
      feedback.style.background = 'rgba(239, 68, 68, 0.12)';
      feedback.style.color = '#ef4444';
      feedback.textContent = 'تعذر إجراء التحسين: ' + err.message;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalText;
      if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
      }
    }
  }
}

async function reloadServerModel() {
  if (!confirm('هل ترغب بإعادة تفريغ وتحميل نموذج التضمين الشرعي 8B في الرام؟ يستغرق ذلك بضع ثوانٍ.')) {
    return;
  }

  const btn = document.getElementById('btnReloadModel');
  const feedback = document.getElementById('telemetryFeedbackMsg');
  const originalText = btn ? btn.innerHTML : '';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>جاري إعادة التحميل... ⏳</span>';
  }

  try {
    const res = await fetch('/api/system/reload_model', { method: 'POST' });
    const data = await res.json();

    if (feedback) {
      feedback.style.display = 'block';
      if (data.status === 'ok') {
        feedback.style.background = 'rgba(16, 185, 129, 0.12)';
        feedback.style.color = '#10b981';
        feedback.textContent = data.message || 'تمت إعادة تحميل النموذج بنجاح!';
      } else {
        feedback.style.background = 'rgba(239, 68, 68, 0.12)';
        feedback.style.color = '#ef4444';
        feedback.textContent = data.message || 'تعذر إعادة تحميل النموذج.';
      }
      setTimeout(() => { feedback.style.display = 'none'; }, 6000);
    }

    await fetchServerHealth(false);
  } catch (err) {
    if (feedback) {
      feedback.style.display = 'block';
      feedback.style.background = 'rgba(239, 68, 68, 0.12)';
      feedback.style.color = '#ef4444';
      feedback.textContent = 'خطأ في الاتصال: ' + err.message;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalText;
      if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
      }
    }
  }
}

// بدء الفحص الدوري لموارد السيرفر كل 30 ثانية
if (typeof window !== 'undefined') {
  window.addEventListener('DOMContentLoaded', () => {
    fetchServerHealth(false);
    if (!serverHealthPoller) {
      serverHealthPoller = setInterval(() => {
        fetchServerHealth(false);
      }, 30000);
    }
  });
}

// -----------------------------------------------------------------------------
// إدارة واسترجاع النسخ الاحتياطية (Backup & Restore)
// -----------------------------------------------------------------------------
let currentBackupsList = [];

async function loadBackupsList() {
  const select = document.getElementById('backupSelectDropdown');
  const btn = document.getElementById('btnRestoreBackup');
  if (!select) return;

  select.innerHTML = '<option value="">جارٍ فحص وجلب النسخ الاحتياطية... ⏳</option>';
  try {
    const res = await fetch('/api/system/backups');
    if (!res.ok) throw new Error('فشل جلب قائمة النسخ');
    const data = await res.json();
    const backups = data.backups || [];
    currentBackupsList = backups;

    if (backups.length === 0) {
      select.innerHTML = '<option value="">لا توجد نسخ احتياطية محفوظة حالياً</option>';
      if (btn) btn.disabled = true;
      return;
    }

    let html = '';
    backups.forEach((b, idx) => {
      const selected = (idx === 0) ? 'selected' : '';
      html += `<option value="${escapeHtml(b.id)}" ${selected}>${escapeHtml(b.label)}</option>`;
    });
    select.innerHTML = html;
    if (btn) btn.disabled = false;
  } catch (err) {
    console.error('Error loading backups:', err);
    select.innerHTML = `<option value="">خطأ: ${escapeHtml(err.message)}</option>`;
    if (btn) btn.disabled = true;
  }
}

function promptRestoreBackup() {
  const select = document.getElementById('backupSelectDropdown');
  const feedback = document.getElementById('restoreStatusFeedback');
  if (!select || !feedback) return;

  const backupId = select.value;
  if (!backupId) {
    showToast('⚠️ يرجى اختيار نسخة احتياطية من القائمة أولاً');
    return;
  }

  const backupObj = currentBackupsList.find(b => b.id === backupId) || { id: backupId, label: backupId };

  feedback.style.display = 'block';
  feedback.innerHTML = `
    <div style="background: rgba(239, 68, 68, 0.08); border: 1.5px solid rgba(239, 68, 68, 0.35); border-radius: 8px; padding: 16px; margin-top: 6px;">
      <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: #ef4444; font-size: 14px; margin-bottom: 6px;">
        <span>⚠️</span>
        <span>تأكيد استرجاع النسخة الاحتياطية:</span>
      </div>
      <div style="font-size: 13px; line-height: 1.6; color: var(--text-main); margin-bottom: 12px;">
        أنت على وشك استرجاع بياناتك إلى: <strong>${escapeHtml(backupObj.label)}</strong>.
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
          سيقوم النظام تلقائياً بأخذ نقطة أمان سريعة للوضع الحالي، ثم استبدال ملفات المشاريع والأدوات الحالية بملفات النسخة المحددة.
        </div>
      </div>
      <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
        <button type="button" class="btn-primary-gradient" onclick="executeRestoreBackupNow('${escapeHtml(backupId)}')" style="background: #dc2626; border-color: #b91c1c; padding: 8px 22px; font-size: 13px; font-weight: 700;">
          <span>⏪ نعم، استرجع هذه النسخة الآن</span>
        </button>
        <button type="button" class="btn-secondary-action" onclick="cancelRestoreBackupPrompt()" style="padding: 8px 16px; font-size: 12.5px;">
          <span>إلغاء</span>
        </button>
      </div>
    </div>
  `;
}

function cancelRestoreBackupPrompt() {
  const feedback = document.getElementById('restoreStatusFeedback');
  if (feedback) feedback.style.display = 'none';
}

async function executeRestoreBackupNow(backupId) {
  const feedback = document.getElementById('restoreStatusFeedback');
  const btn = document.getElementById('btnRestoreBackup');
  if (!feedback) return;

  if (btn) btn.disabled = true;
  feedback.style.display = 'block';
  feedback.innerHTML = `
    <div style="text-align: center; padding: 16px; color: var(--accent-gold);">
      <div style="font-size: 24px; margin-bottom: 6px;">⏳</div>
      <div style="font-weight: 700; font-size: 14px;">جارٍ استرجاع النسخة الاحتياطية وإعادة مزامنة الملفات...</div>
    </div>
  `;

  try {
    const res = await fetch('/api/system/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ backup_id: backupId })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'فشل استرجاع النسخة الاحتياطية');
    }
    const data = await res.json();

    const filesList = (data.restored_files || []).join('، ');
    feedback.innerHTML = `
      <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 8px; padding: 14px 16px;">
        <div style="font-weight: 700; color: #10b981; font-size: 14px; margin-bottom: 4px;">
          ✅ ${escapeHtml(data.message)}
        </div>
        <div style="font-size: 12.5px; color: var(--text-secondary); line-height: 1.6;">
          الملفات المسترجعة: <strong>${escapeHtml(filesList)}</strong>
        </div>
        <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 4px;">
          تم حفظ نقطة أمان قبل الاسترجاع: <code>${escapeHtml(data.pre_restore_backup)}</code>
        </div>
      </div>
    `;

    showToast('🎉 تم استرجاع النسخة الاحتياطية بنجاح!');

    // تحديث فوري للمشاريع والأدوات
    if (typeof loadProjectsList === 'function') loadProjectsList();
    if (typeof loadStoredTools === 'function') loadStoredTools();
    if (typeof loadToolsList === 'function') loadToolsList();
    if (typeof loadTools === 'function') loadTools();

    // تحديث القائمة بعد قليل لظهور نقطة الأمان الجديدة
    setTimeout(loadBackupsList, 1200);
  } catch (err) {
    console.error('Error during restore:', err);
    feedback.innerHTML = `
      <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px; padding: 14px 16px; color: #ef4444; font-size: 13px;">
        ❌ خطأ أثناء الاسترجاع: ${escapeHtml(err.message)}
      </div>
    `;
  } finally {
    if (btn) btn.disabled = false;
  }
}

function quickSaveCurrentWorkspace() {
  let savedSomething = false;
  try {
    if (typeof saveCardsConfiguration === 'function') {
      saveCardsConfiguration();
      savedSomething = true;
    }
  } catch (e) {
    console.warn('saveCardsConfiguration not applicable:', e);
  }

  try {
    if (typeof saveCurrentProject === 'function') {
      saveCurrentProject();
      savedSomething = true;
    }
  } catch (e) {
    console.warn('saveCurrentProject not applicable:', e);
  }

  // إشعار فوري داخل المودال نفسه
  const feedback = document.getElementById('quickSaveFeedback');
  if (feedback) {
    feedback.style.display = 'inline-flex';
    feedback.innerHTML = '✅ تم حفظ ومزامنة المشروع بنجاح!';
    setTimeout(() => {
      feedback.style.display = 'none';
    }, 4500);
  }

  showToast('💾 تم حفظ كافة إعدادات وبطاقات المشروع المفتوح بنجاح!');
}

async function runSystemDiagnose() {
  const container = document.getElementById('maintenanceResultsContainer');
  const btn = document.getElementById('btnRunDiagnose');
  if (!container) return;

  if (btn) btn.disabled = true;
  container.innerHTML = `
    <div style="text-align: center; padding: 28px; color: var(--accent-gold);">
      <div style="font-size: 24px; margin-bottom: 8px;">⏳</div>
      <div style="font-weight: 700;">جارٍ الفحص والتشخيص الشامل لكافة ملفات وأصول المنظومة...</div>
    </div>
  `;

  try {
    const res = await fetch('/api/system/diagnose');
    if (!res.ok) throw new Error('فشل جلب تقرير الفحص');
    const data = await res.json();

    renderDiagnoseResults(data);
  } catch (err) {
    console.error('Diagnose error:', err);
    container.innerHTML = `<div style="color: #ef4444; padding: 16px; text-align: center;">خطأ أثناء الفحص: ${escapeHtml(err.message)}</div>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

function runSystemRepair() {
  const container = document.getElementById('maintenanceResultsContainer');
  if (!container) return;

  // عرض بطاقة تأكيد داخلية أنيقة بدلاً من confirm() القياسية للمتصفح
  container.innerHTML = `
    <div style="background: rgba(184, 115, 51, 0.08); border: 1.5px solid var(--accent-clay); border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 14px;">
      <div style="font-size: 32px; margin-bottom: 8px;">🛡️</div>
      <div style="font-size: 16px; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">
        تأكيد بدء الصيانة والإصلاح والنسخ الاحتياطي
      </div>
      <div style="font-size: 13px; color: var(--text-secondary); max-width: 520px; margin: 0 auto 16px; line-height: 1.6;">
        سيقوم النظام فوراً بـ <strong>أخذ نسخة احتياطية كاملة ومؤرخة</strong> لمشاريعك، وترميم الملفات التالفة أو المفقودة، وتحديث الذاكرة المؤقتة لضمان عمل كافة الوظائف.
      </div>
      <div style="display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;">
        <button type="button" class="btn-primary-gradient" onclick="executeSystemRepairNow()" style="padding: 9px 24px; font-weight: 700; font-size: 13.5px;">
          <span>🚀 نعم، ابدأ الصيانة والنسخ الاحتياطي الآن</span>
        </button>
        <button type="button" class="btn-secondary-action" onclick="cancelRepairConfirm()" style="padding: 9px 18px; font-size: 13px;">
          <span>إلغاء</span>
        </button>
      </div>
    </div>
  `;
}

function cancelRepairConfirm() {
  const container = document.getElementById('maintenanceResultsContainer');
  if (!container) return;
  container.innerHTML = `
    <div style="text-align: center; padding: 24px 12px; color: var(--text-muted); font-size: 13px;">
      تم إلغاء إجراء الصيانة. يمكنك الضغط على «فحص وتشخيص النظام» أو «بدء الصيانة والإصلاح» في أي وقت...
    </div>
  `;
}

async function executeSystemRepairNow() {
  const container = document.getElementById('maintenanceResultsContainer');
  const btn = document.getElementById('btnRunRepair');
  if (!container) return;

  if (btn) btn.disabled = true;
  container.innerHTML = `
    <div style="text-align: center; padding: 28px; color: var(--accent-gold);">
      <div style="font-size: 28px; margin-bottom: 8px;">🔄</div>
      <div style="font-weight: 700; font-size: 15px;">جارٍ تأمين النسخة الاحتياطية وإصلاح الملفات وتحديث الذاكرة...</div>
      <div style="font-size: 12.5px; color: var(--text-muted); margin-top: 6px;">يرجى الانتظار لحظات لإتمام الفحص والترميم...</div>
    </div>
  `;

  try {
    const res = await fetch('/api/system/repair', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    if (!res.ok) throw new Error('فشلت عملية الإصلاح');
    const data = await res.json();

    renderRepairResults(data);
    showToast('🎉 اكتملت الصيانة والإصلاح والنسخ الاحتياطي بنجاح!');

    // تحديث قائمة نقاط الاستعادة فوراً لظهور النسخة الاحتياطية الجديدة في القائمة
    loadBackupsList();
  } catch (err) {
    console.error('Repair error:', err);
    container.innerHTML = `<div style="color: #ef4444; padding: 16px; text-align: center;">خطأ أثناء الإصلاح: ${escapeHtml(err.message)}</div>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderDiagnoseResults(data) {
  const container = document.getElementById('maintenanceResultsContainer');
  if (!container) return;

  const isHealthy = data.status === 'healthy';
  const checks = data.checks || [];

  let html = `
    <div style="margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; background: var(--bg-surface); padding: 12px 16px; border-radius: 8px; border: 1px solid var(--border-subtle);">
      <div>
        <strong style="font-size: 14px; color: ${isHealthy ? '#10b981' : '#f59e0b'};">
          ${isHealthy ? '✅ المنظومة سليمة 100%' : '⚠️ توجد بعض الملاحظات تحتاج صيانة'}
        </strong>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 3px;">${escapeHtml(data.summary)} - توقيت الفحص: ${escapeHtml(data.timestamp)}</div>
      </div>
    </div>

    <div style="display: flex; flex-direction: column; gap: 8px;">
  `;

  checks.forEach(c => {
    const icon = c.status === 'ok' ? '✅' : (c.status === 'warning' ? '⚠️' : '❌');
    const color = c.status === 'ok' ? '#10b981' : (c.status === 'warning' ? '#f59e0b' : '#ef4444');
    html += `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 6px; font-size: 13px;">
        <div>
          <span style="font-size: 11px; background: var(--bg-muted); padding: 2px 8px; border-radius: 10px; color: var(--text-secondary); margin-left: 6px;">${escapeHtml(c.category)}</span>
          <strong style="color: var(--text-main);">${escapeHtml(c.item)}</strong>
          <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">${escapeHtml(c.message)}</div>
        </div>
        <span style="font-weight: 700; color: ${color}; white-space: nowrap;">${icon} ${c.status === 'ok' ? 'سليم' : (c.status === 'warning' ? 'تنبيه' : 'خطأ')}</span>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}

function renderRepairResults(data) {
  const container = document.getElementById('maintenanceResultsContainer');
  if (!container) return;

  const actions = data.actions_taken || [];
  let html = `
    <div style="margin-bottom: 14px; background: rgba(16, 185, 129, 0.1); padding: 12px 16px; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.3);">
      <div style="font-weight: 700; color: #10b981; font-size: 14px;">✅ تم إنجاز الصيانة والإصلاح بنجاح!</div>
      <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">مسار النسخة الاحتياطية: <code style="direction: ltr; display: inline-block;">${escapeHtml(data.backup_path)}</code></div>
    </div>
    <div style="font-size: 13px; font-weight: 700; margin-bottom: 8px; color: var(--text-main);">الإجراءات التي تمت:</div>
    <ul style="padding-right: 20px; font-size: 12.5px; line-height: 1.8; color: var(--text-secondary);">
  `;

  actions.forEach(a => {
    html += `<li>${escapeHtml(a)}</li>`;
  });

  html += `</ul>`;
  container.innerHTML = html;
}

// =============================================================================
// نظام نوافذ الحوار والتأكيد الموحدة (Custom Dialog System - Confirm / Alert / Prompt)
// =============================================================================
function getOrCreateDialogOverlay() {
  let overlay = document.getElementById('appSystemDialogOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'appSystemDialogOverlay';
    overlay.className = 'app-dialog-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.innerHTML = `
      <div class="app-dialog-window" id="appSystemDialogWindow" onclick="event.stopPropagation()">
        <div class="app-dialog-header">
          <div class="app-dialog-icon-badge" id="appDialogIconBadge">
            <span id="appDialogIconContent"></span>
          </div>
          <div style="flex: 1; min-width: 0;">
            <div class="app-dialog-title" id="appDialogTitle"></div>
            <div class="app-dialog-message" id="appDialogMessage"></div>
          </div>
        </div>
        <div class="app-dialog-input-wrapper" id="appDialogInputWrapper" style="display: none;">
          <input type="text" class="app-dialog-input" id="appDialogInput" autocomplete="off" />
        </div>
        <div class="app-dialog-actions" id="appDialogActions"></div>
      </div>
    `;
    document.body.appendChild(overlay);
  }
  return overlay;
}

let activeDialogResolver = null;

function closeSystemDialog(resultValue) {
  const overlay = document.getElementById('appSystemDialogOverlay');
  if (overlay) {
    overlay.classList.remove('active');
  }
  if (activeDialogResolver) {
    const resolve = activeDialogResolver;
    activeDialogResolver = null;
    resolve(resultValue);
  }
}

/**
 * نافذة تأكيد أنيقة متجاوبة مع كافة الثيمات (Confirm Dialog)
 * @returns {Promise<boolean>}
 */
function showConfirmDialog(options = {}) {
  const config = typeof options === 'string' ? { message: options } : (options || {});
  const {
    title = 'تأكيد الإجراء',
    message = 'هل أنت متأكد من رغبتك في متابعة هذا الإجراء؟',
    confirmText = 'تأكيد',
    cancelText = 'إلغاء',
    danger = true,
    icon = danger ? 'trash-2' : 'alert-circle'
  } = config;

  return new Promise((resolve) => {
    activeDialogResolver = resolve;
    const overlay = getOrCreateDialogOverlay();

    document.getElementById('appDialogTitle').textContent = title;
    document.getElementById('appDialogMessage').textContent = message;
    document.getElementById('appDialogInputWrapper').style.display = 'none';

    const badge = document.getElementById('appDialogIconBadge');
    badge.className = `app-dialog-icon-badge ${danger ? 'danger' : 'warning'}`;
    const iconContainer = document.getElementById('appDialogIconContent');
    iconContainer.innerHTML = `<i data-lucide="${icon}" class="icon"></i>`;

    const actions = document.getElementById('appDialogActions');
    actions.innerHTML = `
      <button type="button" class="app-dialog-btn cancel" id="appDialogCancelBtn">
        <span>${escapeHtml(cancelText)}</span>
      </button>
      <button type="button" class="app-dialog-btn ${danger ? 'confirm-danger' : 'confirm-primary'}" id="appDialogConfirmBtn">
        <span>${escapeHtml(confirmText)}</span>
      </button>
    `;

    document.getElementById('appDialogCancelBtn').onclick = () => closeSystemDialog(false);
    document.getElementById('appDialogConfirmBtn').onclick = () => closeSystemDialog(true);
    overlay.onclick = (e) => {
      if (e.target === overlay) closeSystemDialog(false);
    };

    overlay.classList.add('active');
    if (typeof refreshLucideIcons === 'function') {
      refreshLucideIcons();
    }
    setTimeout(() => {
      const confirmBtn = document.getElementById('appDialogConfirmBtn');
      if (confirmBtn) confirmBtn.focus();
    }, 50);
  });
}

/**
 * نافذة تنبيه أنيقة متجاوبة مع كافة الثيمات (Alert Dialog)
 * @returns {Promise<void>}
 */
function showAlertDialog(options = {}) {
  const config = typeof options === 'string' ? { message: options } : (options || {});
  const {
    title = 'تنبيه',
    message = '',
    okText = 'حسناً',
    type = 'info',
    icon = type === 'danger' ? 'alert-octagon' : (type === 'warning' ? 'alert-triangle' : 'info')
  } = config;

  return new Promise((resolve) => {
    activeDialogResolver = resolve;
    const overlay = getOrCreateDialogOverlay();

    document.getElementById('appDialogTitle').textContent = title;
    document.getElementById('appDialogMessage').textContent = message;
    document.getElementById('appDialogInputWrapper').style.display = 'none';

    const badge = document.getElementById('appDialogIconBadge');
    badge.className = `app-dialog-icon-badge ${type === 'danger' ? 'danger' : (type === 'warning' ? 'warning' : 'primary')}`;
    const iconContainer = document.getElementById('appDialogIconContent');
    iconContainer.innerHTML = `<i data-lucide="${icon}" class="icon"></i>`;

    const actions = document.getElementById('appDialogActions');
    actions.innerHTML = `
      <button type="button" class="app-dialog-btn confirm-primary" id="appDialogOkBtn">
        <span>${escapeHtml(okText)}</span>
      </button>
    `;

    document.getElementById('appDialogOkBtn').onclick = () => closeSystemDialog(true);
    overlay.onclick = (e) => {
      if (e.target === overlay) closeSystemDialog(true);
    };

    overlay.classList.add('active');
    if (typeof refreshLucideIcons === 'function') {
      refreshLucideIcons();
    }
    setTimeout(() => {
      const okBtn = document.getElementById('appDialogOkBtn');
      if (okBtn) okBtn.focus();
    }, 50);
  });
}

/**
 * نافذة إدخال نص أنيقة متجاوبة مع كافة الثيمات (Prompt Dialog)
 * @returns {Promise<string|null>}
 */
function showPromptDialog(options = {}) {
  const config = typeof options === 'string' ? { message: options } : (options || {});
  const {
    title = 'إدخال بيانات',
    message = '',
    defaultValue = '',
    placeholder = '',
    confirmText = 'موافق',
    cancelText = 'إلغاء',
    icon = 'edit-3'
  } = config;

  return new Promise((resolve) => {
    activeDialogResolver = resolve;
    const overlay = getOrCreateDialogOverlay();

    document.getElementById('appDialogTitle').textContent = title;
    document.getElementById('appDialogMessage').textContent = message;

    const inputWrapper = document.getElementById('appDialogInputWrapper');
    inputWrapper.style.display = 'block';
    const input = document.getElementById('appDialogInput');
    input.value = defaultValue;
    input.placeholder = placeholder;

    const badge = document.getElementById('appDialogIconBadge');
    badge.className = 'app-dialog-icon-badge primary';
    const iconContainer = document.getElementById('appDialogIconContent');
    iconContainer.innerHTML = `<i data-lucide="${icon}" class="icon"></i>`;

    const actions = document.getElementById('appDialogActions');
    actions.innerHTML = `
      <button type="button" class="app-dialog-btn cancel" id="appDialogCancelBtn">
        <span>${escapeHtml(cancelText)}</span>
      </button>
      <button type="button" class="app-dialog-btn confirm-primary" id="appDialogConfirmBtn">
        <span>${escapeHtml(confirmText)}</span>
      </button>
    `;

    const handleConfirm = () => {
      const val = input.value;
      closeSystemDialog(val);
    };

    document.getElementById('appDialogCancelBtn').onclick = () => closeSystemDialog(null);
    document.getElementById('appDialogConfirmBtn').onclick = handleConfirm;

    input.onkeydown = (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleConfirm();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        closeSystemDialog(null);
      }
    };

    overlay.onclick = (e) => {
      if (e.target === overlay) closeSystemDialog(null);
    };

    overlay.classList.add('active');
    if (typeof refreshLucideIcons === 'function') {
      refreshLucideIcons();
    }
    setTimeout(() => {
      input.focus();
      input.select();
    }, 60);
  });
}

// دعم إغلاق النافذة بزر Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const overlay = document.getElementById('appSystemDialogOverlay');
    if (overlay && overlay.classList.contains('active')) {
      closeSystemDialog(false);
    }
  }
});

// توجيه alert الافتراضي للمتصفح إلى النافذة المخصصة الأنيقة
window.alert = function (msg) {
  showAlertDialog({ message: String(msg) });
};

window.showConfirmDialog = showConfirmDialog;
window.showAlertDialog = showAlertDialog;
window.showPromptDialog = showPromptDialog;
window.appConfirm = showConfirmDialog;
window.appAlert = showAlertDialog;
window.appPrompt = showPromptDialog;

window.openMaintenanceModal = openMaintenanceModal;
window.closeMaintenanceModal = closeMaintenanceModal;
window.openServerHealthModal = openServerHealthModal;
window.closeServerHealthModal = closeServerHealthModal;
window.fetchServerHealth = fetchServerHealth;
window.optimizeServerMemory = optimizeServerMemory;
window.reloadServerModel = reloadServerModel;
window.quickSaveCurrentWorkspace = quickSaveCurrentWorkspace;
window.runSystemDiagnose = runSystemDiagnose;
window.runSystemRepair = runSystemRepair;
window.executeSystemRepairNow = executeSystemRepairNow;
window.cancelRepairConfirm = cancelRepairConfirm;
window.loadBackupsList = loadBackupsList;
window.promptRestoreBackup = promptRestoreBackup;
window.cancelRestoreBackupPrompt = cancelRestoreBackupPrompt;
window.executeRestoreBackupNow = executeRestoreBackupNow;

window.logoutAlmujtahed = async function () {
  if (confirm('هل ترغب بالتأكيد في تسجيل الخروج من منظومة المجتهد؟')) {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch (e) { }
    localStorage.removeItem('almujtahed_auth_token');
    window.location.href = '/login';
  }
};

