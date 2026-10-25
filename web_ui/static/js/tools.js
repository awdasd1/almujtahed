/**
 * =============================================================================
 * tools.js - مستودع الأدوات والإضافات الذكية (Tools & Extensions Hub)
 * =============================================================================
 * إدارة وتجربة واعتماد الأدوات المساعدة (مكتبات ويب / أكواد بايثون)
 * وربطها التلقائي بمهندس المشروع ومدير المشروع
 */

let toolsState = {
  tools: [],
  filter: 'all',
  editingToolId: null,
  activeChartInstance: null,
  playgroundChartInstance: null
};

// =============================================================================
// تهيئة التبويب وتحميل الأدوات
// =============================================================================
async function initToolsTab() {
  await loadToolsList();
}

async function loadToolsList() {
  const grid = document.getElementById('toolsCardsGrid');
  if (grid) {
    grid.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">
        <div class="spinner" style="margin: 0 auto 12px;"></div>
        <div>جارٍ جلب وتحديث مستودع الأدوات المعتمدة...</div>
      </div>
    `;
  }

  try {
    const res = await fetch('/api/tools');
    if (!res.ok) throw new Error('فشل استرجاع قائمة الأدوات');
    const data = await res.json();
    toolsState.tools = (data.tools || (Array.isArray(data) ? data : [])).map(t => ({
      ...t,
      tool_type: t.tool_type || (t.type === 'python_script' ? 'python_code' : 'ready_web_lib'),
      description: t.description || t.desc || '',
      library_url: t.library_url || t.github_url || ''
    }));
    updateToolsCounts();
    renderToolsGrid();
    populateProjectToolsDropdown(toolsState.tools);
    if (window._openSharedToolId) {
      const sharedId = window._openSharedToolId;
      window._openSharedToolId = '';
      openToolPlayground(sharedId);
    }
  } catch (err) {
    console.error('Error loading tools:', err);
    if (grid) {
      grid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 30px; color: #ef4444;">
          فشل تحميل الأدوات: ${escapeHtml(err.message)}
          <br><br>
          <button class="btn-secondary-action" onclick="loadToolsList()">إعادة المحاولة 🔄</button>
        </div>
      `;
    }
  }
}

function updateToolsCounts() {
  const allCount = toolsState.tools.length;
  const webCount = toolsState.tools.filter(t => t.tool_type === 'ready_web_lib').length;
  const pyCount = toolsState.tools.filter(t => t.tool_type === 'python_code').length;

  const cAll = document.getElementById('countAllTools');
  const cWeb = document.getElementById('countWebTools');
  const cPy = document.getElementById('countPythonTools');

  if (cAll) cAll.textContent = allCount;
  if (cWeb) cWeb.textContent = webCount;
  if (cPy) cPy.textContent = pyCount;
}

function filterTools(filterType, btnEl) {
  toolsState.filter = filterType;
  document.querySelectorAll('.tools-filter-pill').forEach(b => b.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  renderToolsGrid();
}

// =============================================================================
// عرض شبكة كروت الأدوات
// =============================================================================
function renderToolsGrid() {
  const grid = document.getElementById('toolsCardsGrid');
  if (!grid) return;

  let list = toolsState.tools;
  if (toolsState.filter === 'ready_web_lib') {
    list = list.filter(t => t.tool_type === 'ready_web_lib');
  } else if (toolsState.filter === 'python_code') {
    list = list.filter(t => t.tool_type === 'python_code');
  }

  if (list.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 50px 20px; color: var(--text-muted); background: var(--bg-surface); border-radius: var(--radius-md); border: 1px dashed var(--border-subtle);">
        <div style="font-size: 32px; margin-bottom: 12px;">🛠️</div>
        <div style="font-size: 16px; font-weight: 600; color: var(--text-main); margin-bottom: 6px;">لا توجد أدوات ضمن هذا التصنيف حالياً</div>
        <div style="font-size: 13px;">يمكنك إضافة أداة جديدة الآن بتركيب مكتبة ويب أو إنشاء كود بايثون بالذكاء الاصطناعي.</div>
        <br>
        <button class="btn-primary-gradient" onclick="openAddToolModal()" style="margin: 0 auto;">إضافة أداة جديدة ➕</button>
      </div>
    `;
    return;
  }

  const enabledChatIds = (function() {
    try {
      const s = localStorage.getItem('almojtahed_chat_enabled_tools');
      return s ? JSON.parse(s) : ['markmap_mindmap', 'charts_metrics'];
    } catch (e) {
      return ['markmap_mindmap', 'charts_metrics'];
    }
  })();

  grid.innerHTML = list.map(t => {
    const isWeb = t.tool_type === 'ready_web_lib';
    const badgeClass = isWeb ? 'tool-badge-web' : 'tool-badge-python';
    const badgeText = isWeb ? '🌐 مكتبة ويب جاهزة' : '🐍 كود بايثون مخصص';
    const isEnabled = t.enabled !== false;
    const isBuiltin = ['charts_metrics', 'astronomy_hijri_sync', 'hadith_isnad_tree'].includes(t.id);
    const isChatEnabled = enabledChatIds.includes(t.id);

    return `
      <div class="tool-card ${isEnabled ? '' : 'disabled'}" id="tool-card-${escapeHtml(t.id)}">
        <div class="tool-card-header">
          <div class="tool-card-title-area">
            <div class="tool-card-title">
              <span>${isWeb ? '📊' : '⚙️'}</span>
              <span>${escapeHtml(t.name)}</span>
            </div>
            <span class="tool-card-type-badge ${badgeClass}">${badgeText}</span>
          </div>

          <label class="switch" title="${isEnabled ? 'تعطيل الأداة عن النظام' : 'تفعيل الأداة في النظام'}">
            <input type="checkbox" ${isEnabled ? 'checked' : ''} onchange="toggleToolEnabled('${escapeHtml(t.id)}', this.checked)">
            <span class="slider round"></span>
          </label>
        </div>

        <div class="tool-card-desc">
          ${escapeHtml(t.description || 'لا يوجد وصف مدون للأداة.')}
        </div>

        <!-- شريط تفعيل واستدعاء الأداة في الشات الذكي -->
        <div class="tool-chat-toggle-box" style="display: flex; align-items: center; justify-content: space-between; margin: 8px 0 6px; padding: 7px 12px; background: ${isChatEnabled ? 'rgba(37, 99, 235, 0.08)' : 'var(--bg-muted)'}; border: 1px solid ${isChatEnabled ? 'rgba(37, 99, 235, 0.28)' : 'var(--border-subtle)'}; border-radius: var(--radius-md); transition: all 0.2s ease;">
          <div style="display: flex; align-items: center; gap: 7px;">
            <span style="font-size: 15px;">💬</span>
            <div>
              <div style="font-size: 12px; font-weight: 700; color: ${isChatEnabled ? '#2563eb' : 'var(--text-main)'};">
                تفعيل في المحادثة (الشات)
              </div>
              <div style="font-size: 10.5px; color: var(--text-muted);">
                ${isChatEnabled ? 'الأداة ظاهرة في الشريط الجانبي للشات' : 'معطلة عن الظهور في قسم أدوات الشات'}
              </div>
            </div>
          </div>
          <button type="button" class="btn-tool-chat-toggle" onclick="toggleToolChatEnabled('${escapeHtml(t.id)}', !${isChatEnabled})" style="padding: 4px 10px; font-size: 11.5px; border-radius: 6px; cursor: pointer; border: 1px solid ${isChatEnabled ? '#2563eb' : 'var(--border-subtle)'}; background: ${isChatEnabled ? '#2563eb' : 'var(--bg-surface)'}; color: ${isChatEnabled ? '#fff' : 'var(--text-muted)'}; font-weight: 600; display: flex; align-items: center; gap: 4px; transition: all 0.15s ease;">
            <span>${isChatEnabled ? 'مفعلة بالشات ✅' : 'تفعيل في الشات ➕'}</span>
          </button>
        </div>

        <div class="tool-card-meta">
          <div><strong>معرّف الأداة:</strong> <code>${escapeHtml(t.id)}</code></div>
          ${isWeb && t.library_url ? `<div style="text-overflow: ellipsis; overflow: hidden; white-space: nowrap;"><strong>المصدر:</strong> <a href="${escapeHtml(t.library_url)}" target="_blank" rel="noopener" style="color: var(--accent-clay);">${escapeHtml(t.library_url)}</a></div>` : ''}
          ${!isWeb && t.entry_function ? `<div><strong>نقطة الدخول:</strong> <code>def ${escapeHtml(t.entry_function)}()</code></div>` : ''}
          <div><strong>حالة الاعتماد:</strong> <span style="color: ${isEnabled ? '#16a34a' : '#ef4444'}; font-weight: 600;">${isEnabled ? '✅ معتمدة ومتاحة للمنظومة' : '⏸️ معطلة مؤقتاً'}</span></div>
        </div>

        <div class="tool-card-footer">
          <div class="tool-card-actions">
            <button class="btn-secondary-action" onclick="openToolPlayground('${escapeHtml(t.id)}')" style="padding: 6px 12px; font-size: 12.5px;">
              <span>تجربة 🧪</span>
            </button>
            <button class="btn-secondary-action" onclick="toggleToolChatEnabled('${escapeHtml(t.id)}', !${isChatEnabled})" style="padding: 6px 10px; font-size: 12px; ${isChatEnabled ? 'border-color: #2563eb; color: #2563eb; background: rgba(37,99,235,0.08); font-weight: 600;' : ''}" title="${isChatEnabled ? 'تعطيل ظهور الأداة في الشات' : 'تفعيل ظهور الأداة في الشات'}">
              <span>${isChatEnabled ? 'بالشات 💬' : 'إضافة للشات 💬'}</span>
            </button>
            <button class="btn-secondary-action" onclick="openEditToolModal('${escapeHtml(t.id)}')" style="padding: 6px 10px; font-size: 12.5px;" title="تعديل خصائص الأداة">
              ✏️
            </button>
            <button class="btn-secondary-action" type="button" data-share-kind="tool" data-share-id="${escapeHtml(t.id)}" data-share-label="${escapeHtml(t.name || 'الأداة')}" style="padding: 6px 10px; font-size: 12.5px;" title="مشاركة الأداة مع الأعضاء أو حفظها في الجهاز">
              <span>مشاركة</span>
            </button>
          </div>

          ${!isBuiltin ? `
            <button class="btn-icon" onclick="deleteToolConfirm('${escapeHtml(t.id)}', '${escapeHtml(t.name)}')" title="حذف الأداة نهائياً" style="color: #ef4444;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          ` : `
            <span style="font-size: 11px; color: var(--text-muted); font-weight: 500;">أداة نظام أساسية</span>
          `}
        </div>
      </div>
    `;
  }).join('');
}

// =============================================================================
// تفعيل / تعطيل ظهور الأداة في شات المحادثة
// =============================================================================
function toggleToolChatEnabled(toolId, isEnabled) {
  let enabledIds = [];
  try {
    const saved = localStorage.getItem('almojtahed_chat_enabled_tools');
    if (saved) enabledIds = JSON.parse(saved);
    else enabledIds = ['markmap_mindmap', 'charts_metrics'];
  } catch (e) {
    enabledIds = ['markmap_mindmap', 'charts_metrics'];
  }

  if (isEnabled) {
    if (!enabledIds.includes(toolId)) enabledIds.push(toolId);
  } else {
    enabledIds = enabledIds.filter(id => id !== toolId);
  }

  try {
    localStorage.setItem('almojtahed_chat_enabled_tools', JSON.stringify(enabledIds));
  } catch (e) {
    console.error('Error saving chat enabled tools:', e);
  }

  const tool = toolsState.tools.find(t => t.id === toolId);
  if (tool) {
    tool.enabled_in_chat = isEnabled;
  }

  renderToolsGrid();

  // تحديث فوري لقائمة الأدوات في الشريط الجانبي للشات
  if (typeof renderChatAssistantTools === 'function') {
    renderChatAssistantTools();
  } else if (typeof window.renderChatAssistantTools === 'function') {
    window.renderChatAssistantTools();
  }

  const toolName = tool ? tool.name : toolId;
  showToast(isEnabled ? `تم تفعيل «${toolName}» في المحادثة والشات 💬` : `تم تعطيل ظهور «${toolName}» في الشات`);
}

window.toggleToolChatEnabled = toggleToolChatEnabled;

// =============================================================================
// تفعيل / تعطيل أداة
// =============================================================================
async function toggleToolEnabled(toolId, isEnabled) {
  const tool = toolsState.tools.find(t => t.id === toolId);
  if (!tool) return;
  tool.enabled = isEnabled;

  try {
    const res = await fetch('/api/tools', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tool)
    });
    if (!res.ok) throw new Error('فشل تحديث حالة الأداة');
    const card = document.getElementById(`tool-card-${toolId}`);
    if (card) {
      if (isEnabled) card.classList.remove('disabled');
      else card.classList.add('disabled');
    }
    showToast(isEnabled ? `تم تفعيل «${tool.name}» وإتاحتها لمهندس المشروع` : `تم تعطيل «${tool.name}»`);
    populateProjectToolsDropdown(toolsState.tools);
  } catch (err) {
    console.error('Error toggling tool:', err);
    showToast(`خطأ في تحديث الأداة: ${err.message}`, true);
    loadToolsList();
  }
}

// =============================================================================
// إضافة / تعديل أداة
// =============================================================================
function openAddToolModal() {
  toolsState.editingToolId = null;
  const modal = document.getElementById('toolConfigModal');
  if (!modal) return;

  document.getElementById('toolModalTitle').textContent = 'إضافة أداة مساعدة جديدة ➕';
  document.getElementById('toolIdInput').value = '';
  document.getElementById('toolIdInput').disabled = false;
  document.getElementById('toolNameInput').value = '';
  document.getElementById('toolDescInput').value = '';
  document.getElementById('toolWebUrlInput').value = '';
  document.getElementById('toolWebInitScript').value = '';
  document.getElementById('toolWebMockData').value = '{\n  "labels": ["القول 1", "القول 2", "القول 3"],\n  "values": [65, 25, 10]\n}';
  document.getElementById('toolPythonCode').value = 'def run_tool(input_data):\n    """دالة التحقق أو الحساب التراثي"""\n    # اكتب كود المعالجة هنا\n    return {"status": "success", "result": input_data}\n';
  document.getElementById('toolPythonTestInput').value = '{\n  "year": 12,\n  "month": "رمضان",\n  "city": "بغداد"\n}';
  document.getElementById('toolPythonTestOutput').innerHTML = '';
  document.getElementById('toolWebTestPreview').innerHTML = '';
  const filterInput = document.getElementById('toolAiModelFilterInput');
  if (filterInput) filterInput.value = '';

  switchToolModalType('ready_web_lib');
  modal.classList.add('active', 'open');
}

function openEditToolModal(toolId) {
  const tool = toolsState.tools.find(t => t.id === toolId);
  if (!tool) return;

  toolsState.editingToolId = toolId;
  const modal = document.getElementById('toolConfigModal');
  if (!modal) return;

  document.getElementById('toolModalTitle').textContent = `تعديل أداة: «${tool.name}» ✏️`;
  document.getElementById('toolIdInput').value = tool.id;
  document.getElementById('toolIdInput').disabled = true;
  document.getElementById('toolNameInput').value = tool.name || '';
  document.getElementById('toolDescInput').value = tool.description || '';
  document.getElementById('toolWebUrlInput').value = tool.library_url || '';
  document.getElementById('toolWebInitScript').value = tool.init_script || '';
  document.getElementById('toolWebMockData').value = tool.mock_test_data ? (typeof tool.mock_test_data === 'string' ? tool.mock_test_data : JSON.stringify(tool.mock_test_data, null, 2)) : '';
  document.getElementById('toolPythonCode').value = tool.python_code || '';
  document.getElementById('toolPythonTestInput').value = tool.mock_test_data ? (typeof tool.mock_test_data === 'string' ? tool.mock_test_data : JSON.stringify(tool.mock_test_data, null, 2)) : '{\n}';
  document.getElementById('toolPythonTestOutput').innerHTML = '';
  document.getElementById('toolWebTestPreview').innerHTML = '';
  const filterInput = document.getElementById('toolAiModelFilterInput');
  if (filterInput) filterInput.value = '';

  const isPython = (tool.tool_type === 'python_code' || tool.type === 'python_script');
  switchToolModalType(isPython ? 'python_code' : 'ready_web_lib');
  if (isPython) {
    initToolAiModels(tool.model || null);
  }
  modal.classList.add('active', 'open');
}

function closeToolModal() {
  const modal = document.getElementById('toolConfigModal');
  if (modal) modal.classList.remove('active', 'open');
  toolsState.editingToolId = null;
}

function switchToolModalType(type) {
  const radioWeb = document.getElementById('radioTypeWeb');
  const radioPy = document.getElementById('radioTypePython');
  const cardWeb = document.getElementById('cardRadioWeb');
  const cardPy = document.getElementById('cardRadioPython');
  const sectionWeb = document.getElementById('sectionWebLibConfig');
  const sectionPy = document.getElementById('sectionPythonConfig');

  if (type === 'ready_web_lib') {
    if (radioWeb) radioWeb.checked = true;
    if (cardWeb) cardWeb.classList.add('active');
    if (cardPy) cardPy.classList.remove('active');
    if (sectionWeb) sectionWeb.style.display = 'block';
    if (sectionPy) sectionPy.style.display = 'none';
  } else {
    if (radioPy) radioPy.checked = true;
    if (cardPy) cardPy.classList.add('active');
    if (cardWeb) cardWeb.classList.remove('active');
    if (sectionWeb) sectionWeb.style.display = 'none';
    if (sectionPy) sectionPy.style.display = 'block';
    // تحميل نماذج مزود الخدمة الافتراضي OpenRouter تلقائياً عند اختيار بايثون
    initToolAiModels();
  }
}

// =============================================================================
// إدارة وفلترة نماذج OpenRouter لأدوات بايثون
// =============================================================================
function toolSuggestedModels() {
  return window.SUGGESTED_MODELS || [
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
}

let toolAiAllModels = [];
let toolAiSelectedModel = 'google/gemini-2.5-flash';

async function initToolAiModels(preferredModel = null) {
  if (preferredModel) {
    toolAiSelectedModel = preferredModel;
  }
  const countBadge = document.getElementById('toolAiModelCountBadge');

  if (window.openrouterModelsList && window.openrouterModelsList.length > 0) {
    toolAiAllModels = window.openrouterModelsList;
  } else {
    try {
      if (countBadge) countBadge.textContent = 'جارٍ جلب النماذج... ⏳';
      let savedKeys = {};
      try { savedKeys = readProviderKeys(); } catch (e) { }
      const apiKey = savedKeys.openrouter || '';
      const url = `/api/openrouter/models${apiKey ? '?api_key=' + encodeURIComponent(apiKey) : ''}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        toolAiAllModels = data.models || [];
        window.openrouterModelsList = toolAiAllModels;
      }
    } catch (e) {
      console.warn('Could not fetch OpenRouter models for tools:', e);
    }
  }

  const filterInput = document.getElementById('toolAiModelFilterInput');
  const filterVal = filterInput ? filterInput.value : '';
  renderToolAiModelsDropdown(filterVal, toolAiSelectedModel);
}

function renderToolAiModelsDropdown(filterQuery = '', selectedVal = null) {
  const selectEl = document.getElementById('toolAiModelSelect');
  const countBadge = document.getElementById('toolAiModelCountBadge');
  const clearBtn = document.getElementById('toolAiModelClearFilterBtn');
  if (!selectEl) return;

  const currentVal = selectedVal || selectEl.value || toolAiSelectedModel || 'google/gemini-2.5-flash';
  const q = (filterQuery || '').trim().toLowerCase();

  if (clearBtn) {
    clearBtn.style.display = q ? 'block' : 'none';
  }

  const topIds = new Set(toolSuggestedModels().map(m => m.id));
  const otherModels = (toolAiAllModels || []).filter(m => !topIds.has(m.id));
  otherModels.sort((a, b) => (a.name || a.id).localeCompare(b.name || b.id));

  let matchedTop = toolSuggestedModels();
  let matchedOthers = otherModels;

  if (q) {
    matchedTop = toolSuggestedModels().filter(m =>
      m.id.toLowerCase().includes(q) || (m.name && m.name.toLowerCase().includes(q))
    );
    matchedOthers = otherModels.filter(m =>
      m.id.toLowerCase().includes(q) ||
      (m.name && m.name.toLowerCase().includes(q)) ||
      (m.description && m.description.toLowerCase().includes(q))
    );
  }

  const totalMatched = matchedTop.length + matchedOthers.length;
  if (countBadge) {
    if (q) {
      countBadge.textContent = `${totalMatched} نموذج مطابق`;
    } else {
      const totalCount = toolSuggestedModels().length + otherModels.length;
      countBadge.textContent = `${totalCount} نموذج متاح من OpenRouter 🌐`;
    }
  }

  let html = '';

  const inTop = matchedTop.some(m => m.id === currentVal);
  const inOthers = matchedOthers.some(m => m.id === currentVal);
  if (!inTop && !inOthers && currentVal) {
    html += `<option value="${currentVal}" selected>${escapeHtml(currentVal)} (المحدد حالياً)</option>`;
  }

  if (matchedTop.length > 0) {
    const topOptions = matchedTop.map(m =>
      `<option value="${m.id}" ${m.id === currentVal ? 'selected' : ''}>${escapeHtml(m.name)}</option>`
    ).join('');
    html += `<optgroup label="⭐ النماذج المقترحة">${topOptions}</optgroup>`;
  }

  if (matchedOthers.length > 0) {
    const otherOptions = matchedOthers.map(m => {
      const label = m.name ? `${m.name} (${m.id})` : m.id;
      return `<option value="${m.id}" ${m.id === currentVal ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    }).join('');
    html += `<optgroup label="🌐 كافة نماذج مزود OpenRouter (${matchedOthers.length} نموذج)">${otherOptions}</optgroup>`;
  }

  if (totalMatched === 0 && !html) {
    html = `<option value="" disabled selected>لا توجد نماذج مطابقة للبحث «${escapeHtml(q)}»</option>`;
  }

  selectEl.innerHTML = html;
  if (inTop || inOthers) {
    selectEl.value = currentVal;
    toolAiSelectedModel = currentVal;
  } else if (matchedTop.length > 0) {
    selectEl.value = matchedTop[0].id;
    toolAiSelectedModel = matchedTop[0].id;
  } else if (matchedOthers.length > 0) {
    selectEl.value = matchedOthers[0].id;
    toolAiSelectedModel = matchedOthers[0].id;
  }
}

function filterToolAiModels(query) {
  renderToolAiModelsDropdown(query, document.getElementById('toolAiModelSelect')?.value);
}

function clearToolAiModelFilter() {
  const input = document.getElementById('toolAiModelFilterInput');
  if (input) {
    input.value = '';
    input.focus();
  }
  renderToolAiModelsDropdown('', document.getElementById('toolAiModelSelect')?.value);
}

// =============================================================================
// توليد كود بايثون بالذكاء الاصطناعي
// =============================================================================
async function generatePythonToolAI() {
  const promptInput = document.getElementById('toolAiPromptInput');
  const prompt = promptInput ? promptInput.value.trim() : '';
  if (!prompt) {
    showToast('يرجى كتابة ما تريده من الخوارزمية في حقل الطلب أولاً', true);
    if (promptInput) promptInput.focus();
    return;
  }

  const modelSelect = document.getElementById('toolAiModelSelect');
  const model = modelSelect ? modelSelect.value : 'google/gemini-2.5-flash';
  const genBtn = document.getElementById('toolAiGenBtn');

  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) { }
  const apiKey = savedKeys.openrouter || '';

  if (genBtn) {
    genBtn.disabled = true;
    genBtn.innerHTML = '<span>جارٍ هندسة وتوليد الكود بالذكاء الاصطناعي... ⏳</span>';
  }

  try {
    const res = await fetch('/api/tools/generate-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, model, api_key: apiKey })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || errData.message || 'فشل التوليد');
    }
    const data = await res.json();
    if (data.status === 'error') {
      throw new Error(data.message || 'حدث خطأ أثناء التوليد');
    }

    if (data.code) {
      document.getElementById('toolPythonCode').value = data.code;
    }
    if (data.sample_input) {
      document.getElementById('toolPythonTestInput').value = JSON.stringify(data.sample_input, null, 2);
    } else if (data.code) {
      autoDetectMockDataFromCode(data.code, true);
    }
    if (data.tool_name && !document.getElementById('toolNameInput').value) {
      document.getElementById('toolNameInput').value = data.tool_name;
    }
    if (data.tool_id && !document.getElementById('toolIdInput').value) {
      document.getElementById('toolIdInput').value = data.tool_id;
    }

    const outBox = document.getElementById('toolPythonTestOutput');
    if (outBox) {
      outBox.className = '';
      outBox.innerHTML = '';
    }

    showToast('تمت هندسة وبرمجة كود الأداة بنجاح ✨ يمكنك الآن تشغيله واختباره للتحقق من عمله');

    // لفت انتباه المستخدم لزر الفحص والتجربة المباشرة
    const testBtn = document.getElementById('btnTestPythonCode');
    if (testBtn) {
      testBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
      testBtn.style.boxShadow = '0 0 0 3px rgba(99, 102, 241, 0.4)';
      setTimeout(() => { if (testBtn) testBtn.style.boxShadow = ''; }, 2500);
    }
  } catch (err) {
    console.error('Error generating tool code:', err);
    showToast(`فشل توليد الكود: ${err.message}`, true);
  } finally {
    if (genBtn) {
      genBtn.disabled = false;
      genBtn.innerHTML = '<span>توليد كود بايثون بالذكاء الاصطناعي ✨</span>';
    }
  }
}

// =============================================================================
// استخراج بيانات الاختبار الوهمية تلقائياً من كود بايثون
// =============================================================================
let _codeChangeDebounceTimer = null;
function onPythonCodeInputChanged() {
  clearTimeout(_codeChangeDebounceTimer);
  _codeChangeDebounceTimer = setTimeout(() => {
    autoDetectMockDataFromCode(null, true);
  }, 1200);
}

function autoDetectMockDataFromCode(codeOverride = null, silent = false) {
  const codeEl = document.getElementById('toolPythonCode');
  const inputEl = document.getElementById('toolPythonTestInput');
  const code = (codeOverride !== null ? codeOverride : (codeEl ? codeEl.value : '')).trim();
  if (!code || !inputEl) return null;

  let detectedJson = null;

  // 1. فحص وجود قاموس مثال صريح في الكود (مثل input_data_example أو mock_test_input)
  const regexPatterns = [
    /(?:input_data_example|mock_test_input|sample_input|example_input|test_input|mock_data)\s*=\s*(\{[\s\S]*?\n\s*\})/,
    /(?:input_data_example|mock_test_input|sample_input|example_input|test_input|mock_data)\s*=\s*(\{.*?\})/
  ];

  for (const re of regexPatterns) {
    const match = code.match(re);
    if (match && match[1]) {
      try {
        let jsonStr = match[1]
          .replace(/'/g, '"')
          .replace(/True/g, 'true')
          .replace(/False/g, 'false')
          .replace(/None/g, 'null')
          .replace(/,\s*([\}\]])/g, '$1');
        detectedJson = JSON.parse(jsonStr);
        break;
      } catch (e) {
        // خطأ بسيط في التحويل، نتجاوزه للمحاولة التالية
      }
    }
  }

  // 2. إذا لم نجد متغيراً صريحاً، نفحص المفاتيح التي تطلبها دالة run_tool
  if (!detectedJson) {
    const keyMatches = [...code.matchAll(/input_data(?:\.get\(|\[)\s*['"]([a-zA-Z0-9_]+)['"]/g)];
    if (keyMatches && keyMatches.length > 0) {
      const keys = [...new Set(keyMatches.map(m => m[1]))];
      detectedJson = {};
      for (const k of keys) {
        const kLow = k.toLowerCase();
        if (kLow.includes('date1') || kLow.includes('start_date') || kLow.includes('from_date') || kLow.includes('first_date')) {
          detectedJson[k] = '2023-01-01';
        } else if (kLow.includes('date2') || kLow.includes('end_date') || kLow.includes('to_date') || kLow.includes('second_date')) {
          detectedJson[k] = '2024-03-15';
        } else if (kLow.includes('date') || kLow.includes('time')) {
          detectedJson[k] = '2024-01-01';
        } else if (kLow.includes('year') || kLow.includes('hijri')) {
          detectedJson[k] = kLow.includes('hijri') ? 1445 : 2024;
        } else if (kLow.includes('month')) {
          detectedJson[k] = 'رمضان';
        } else if (kLow.includes('day') || kLow.includes('num') || kLow.includes('count') || kLow.includes('id') || kLow.includes('page')) {
          detectedJson[k] = 1;
        } else if (kLow.includes('city') || kLow.includes('place')) {
          detectedJson[k] = 'بغداد';
        } else if (kLow.includes('text') || kLow.includes('query') || kLow.includes('sentence') || kLow.includes('phrase')) {
          detectedJson[k] = 'نص تجريبي للتحقق';
        } else if (kLow.startsWith('is_') || kLow.startsWith('has_') || kLow.includes('flag')) {
          detectedJson[k] = true;
        } else if (kLow.includes('list') || kLow.includes('items') || kLow.includes('books')) {
          detectedJson[k] = ['عنصر 1', 'عنصر 2'];
        } else {
          detectedJson[k] = 'قيمة تجريبية';
        }
      }
    }
  }

  if (detectedJson && Object.keys(detectedJson).length > 0) {
    inputEl.value = JSON.stringify(detectedJson, null, 2);
    inputEl.style.borderColor = 'rgba(16, 185, 129, 0.5)';
    setTimeout(() => { if (inputEl) inputEl.style.borderColor = ''; }, 2000);
    if (!silent) {
      showToast('✨ تم استخراج وتعبئة بيانات الاختبار المناسبة للكود بنجاح!');
    }
    return detectedJson;
  } else if (!silent) {
    showToast('لم يتم العثور على مفاتيح محددة، يمكنك كتابة قاموس JSON تجريبي يدوياً', true);
  }
  return null;
}

// =============================================================================
// تشغيل واختبار كود بايثون مباشرة للتحقق من عمله
// =============================================================================
async function testPythonToolSnippet() {
  const code = document.getElementById('toolPythonCode').value;
  const inputStr = document.getElementById('toolPythonTestInput').value;
  const outBox = document.getElementById('toolPythonTestOutput');

  if (!code || !code.trim()) {
    showToast('يرجى توليد أو كتابة كود بايثون للأداة أولاً', true);
    return;
  }

  let testInput = {};
  try {
    testInput = inputStr ? JSON.parse(inputStr) : {};
  } catch (e) {
    showToast('صيغة مدخلات الاختبار (JSON) غير صحيحة، يرجى تصحيح الأقواس', true);
    return;
  }

  // فحص ذكي: إذا كانت المدخلات الحالية لا تطابق الحقول المستخدمة في الكود، نستخرجها فوراً
  const codeReqKeys = [...code.matchAll(/input_data(?:\.get\(|\[)\s*['"]([a-zA-Z0-9_]+)['"]/g)].map(m => m[1]);
  if (codeReqKeys.length > 0) {
    const hasAnyKey = codeReqKeys.some(k => k in testInput);
    if (!hasAnyKey) {
      const autoData = autoDetectMockDataFromCode(code, true);
      if (autoData) {
        testInput = autoData;
      }
    }
  }

  if (outBox) {
    outBox.className = 'tool-test-result-box';
    outBox.innerHTML = '<div style="display: flex; align-items: center; gap: 8px;"><span>جارٍ تشغيل واختبار الكود في بيئة معزولة...</span><span class="spinner-inline">⏳</span></div>';
  }

  try {
    const res = await fetch('/api/tools/test-python', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: code,
        input_data: testInput,
        entry_function: 'run_tool'
      })
    });
    const result = await res.json();

    // إذا استعان الخادم بمثال مضمن في الكود لإنقاذ الفحص، نحدث حقل المدخلات بالواجهة
    if (result.fallback_input) {
      document.getElementById('toolPythonTestInput').value = JSON.stringify(result.fallback_input, null, 2);
    }

    const isLogicError = typeof result.output === 'object' && result.output !== null && (result.output.status === 'error' || result.output.status === 'fail' || (result.output.error && !result.output.status));

    if (result.success && !isLogicError) {
      outBox.className = 'tool-test-result-box tool-test-success';
      outBox.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; flex-wrap: wrap;">
          <strong style="color: #10b981; display: flex; align-items: center; gap: 6px; font-size: 13px;">
            <span>✅</span>
            <span>نجح الاختبار بنجاح! مخرجات التنفيذ صالحة ومطابقة (${result.execution_time_ms || 0} ms):</span>
          </strong>
          <button type="button" class="btn-primary-gradient" onclick="saveToolConfig()" style="padding: 5px 16px; font-size: 12.5px; border-radius: 6px;">
            <span>اعتماد وحفظ الأداة في المنظومة الآن 💾</span>
          </button>
        </div>
        <div style="background: rgba(0,0,0,0.25); padding: 10px; border-radius: 6px; font-family: monospace; font-size: 12px; white-space: pre-wrap; direction: ltr; text-align: left;">${escapeHtml(JSON.stringify(result.output, null, 2))}</div>
      `;
      showToast('🎉 نجح اختبار كود الأداة بنجاح! يمكنك اعتمادها الآن');
    } else if (isLogicError) {
      outBox.className = 'tool-test-result-box tool-test-failure';
      outBox.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; flex-wrap: wrap;">
          <strong style="color: #f59e0b; display: flex; align-items: center; gap: 6px; font-size: 13px;">
            <span>⚠️</span>
            <span>أرجعت الدالة تنبيهاً / خطأ منطقياً في مدخلات الاختبار:</span>
          </strong>
          <button type="button" class="btn-secondary-action" onclick="autoDetectMockDataFromCode(); testPythonToolSnippet();" style="padding: 4px 14px; font-size: 12px; border-color: #f59e0b; color: #f59e0b;">
            <span>🪄 استخراج المدخلات المطلوبة وتجربة الكود مجدداً</span>
          </button>
        </div>
        <div style="background: rgba(0,0,0,0.25); padding: 10px; border-radius: 6px; font-family: monospace; font-size: 12px; white-space: pre-wrap; direction: ltr; text-align: left; color: #fde68a;">${escapeHtml(JSON.stringify(result.output, null, 2))}</div>
        <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 6px;">
          💡 الدالة البرمجية تتطلب مدخلات معينة (مثل التواريخ أو المفاتيح المذكورة في الرسالة). اضغط على زر <strong>«استخراج المدخلات المطلوبة»</strong> بالأعلى لتعبئتها وتجربتها فوراً.
        </div>
      `;
    } else {
      outBox.className = 'tool-test-result-box tool-test-failure';
      outBox.innerHTML = `
        <strong style="color: #ef4444; display: flex; align-items: center; gap: 6px; margin-bottom: 8px; font-size: 13px;">
          <span>❌</span>
          <span>فشل الاختبار أو حدث خطأ برمجي أثناء تشغيل الكود:</span>
        </strong>
        <div style="background: rgba(0,0,0,0.25); padding: 10px; border-radius: 6px; font-family: monospace; font-size: 12px; white-space: pre-wrap; direction: ltr; text-align: left; color: #fca5a5;">${escapeHtml(result.error || 'خطأ غير معروف')}</div>
      `;
    }
  } catch (err) {
    if (outBox) {
      outBox.className = 'tool-test-result-box tool-test-failure';
      outBox.innerHTML = `خطأ أثناء الاتصال بالخادم: ${escapeHtml(err.message)}`;
    }
  }
}

// =============================================================================
// جلب وفحص الإضافة تلقائياً من مخزن GitHub أو رابط المكتبة
// =============================================================================
async function fetchExtensionFromUrl() {
  const urlInput = document.getElementById('toolWebUrlInput');
  const statusEl = document.getElementById('fetchUrlStatus');
  const url = urlInput ? urlInput.value.trim() : '';

  if (!url) {
    if (statusEl) {
      statusEl.innerHTML = '<span style="color: #ef4444;">⚠️ يرجى إدخال رابط المخزن أو المكتبة أولاً</span>';
    }
    showToast('يرجى إدخال رابط الإضافة (GitHub أو CDN)', true);
    return;
  }

  if (statusEl) {
    statusEl.innerHTML = '<span style="color: var(--accent-clay);">⏳ جارٍ الاتصال وفحص المخزن وجلب السكربتات والبيانات...</span>';
  }

  try {
    const res = await fetch('/api/tools/fetch-repo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'تعذر جلب بيانات الرابط');
    }

    const data = await res.json();

    // ملء حقول المودال تلقائياً بالبيانات المستخرجة
    const nameInput = document.getElementById('toolNameInput');
    const idInput = document.getElementById('toolIdInput');
    const descInput = document.getElementById('toolDescInput');
    const scriptInput = document.getElementById('toolWebInitScript');
    const mockInput = document.getElementById('toolWebMockData');

    if (nameInput && data.name) nameInput.value = data.name;
    if (idInput && data.id) idInput.value = data.id;
    if (descInput && data.desc) descInput.value = data.desc;
    if (urlInput && data.library_url) urlInput.value = data.library_url;
    if (scriptInput && data.init_script) scriptInput.value = data.init_script;
    
    if (mockInput && data.mock_data) {
      if (typeof data.mock_data === 'object') {
        if (data.mock_data.markdown) {
          mockInput.value = data.mock_data.markdown;
        } else {
          mockInput.value = JSON.stringify(data.mock_data, null, 2);
        }
      } else {
        mockInput.value = String(data.mock_data);
      }
    }

    if (statusEl) {
      statusEl.innerHTML = `<span style="color: #10b981; font-weight: 600;">✅ تم جلب إضافة «${escapeHtml(data.name || 'الأداة')}» بنجاح! تم تجهيز كود التهيئة والبيانات التجريبية.</span>`;
    }

    showToast(`تم استيراد بيانات «${data.name}» بنجاح! جرى تشغيل المعاينة الحية.`);

    // تشغيل المعاينة الحية فوراً ليراها المستخدم
    setTimeout(() => {
      testWebLibraryMock();
    }, 150);

  } catch (err) {
    console.error('Fetch repo error:', err);
    if (statusEl) {
      statusEl.innerHTML = `<span style="color: #ef4444;">❌ فشل جلب الرابط: ${escapeHtml(err.message)}</span>`;
    }
    showToast(`تعذر جلب بيانات الإضافة: ${err.message}`, true);
  }
}

// =============================================================================
// اختبار حقيقي وتشغيل حي لمكتبة الويب (Markmap / Chart.js / Vis.js / Custom)
// =============================================================================
let activeMarkmapInstance = null;

function testWebLibraryMock() {
  const preview = document.getElementById('toolWebTestPreview');
  const statusEl = document.getElementById('testWebLibStatus');
  const mockText = document.getElementById('toolWebMockData') ? document.getElementById('toolWebMockData').value.trim() : '';
  const urlVal = document.getElementById('toolWebUrlInput') ? document.getElementById('toolWebUrlInput').value.trim().toLowerCase() : '';
  const nameVal = document.getElementById('toolNameInput') ? document.getElementById('toolNameInput').value.trim().toLowerCase() : '';
  const initScript = document.getElementById('toolWebInitScript') ? document.getElementById('toolWebInitScript').value : '';

  if (!preview) return;

  // تحديد نوع الأداة المراد اختبارها
  const isMarkmap = urlVal.includes('markmap') || nameVal.includes('markmap') || nameVal.includes('تشجير') || mockText.startsWith('#');
  const isVisNetwork = urlVal.includes('vis') || nameVal.includes('أسانيد') || mockText.includes('"nodes"') || mockText.includes('"edges"');

  if (statusEl) {
    statusEl.innerHTML = '<span style="color: var(--accent-clay);">⏳ تشغيل واختبار الأداة حياً...</span>';
  }

  // الحالة 1: أداة التشجير والخرائط الذهنية Markmap
  if (isMarkmap) {
    const markmapSvgId = 'testMarkmapSvg_' + Date.now();
    preview.innerHTML = `
      <div style="background: var(--bg-surface); padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); margin-top: 10px; box-shadow: var(--shadow-sm);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
          <div style="font-weight: 700; font-size: 14px; color: var(--accent-clay); display: flex; align-items: center; gap: 6px;">
            <span>🌳</span>
            <span>معاينة حية لشجرة وخريطة Markmap التفاعلية:</span>
          </div>
          <div style="display: flex; gap: 6px;">
            <button type="button" class="btn-chart-type" onclick="zoomTestMarkmap(1.2)" title="تكبير">🔍+ تكبير</button>
            <button type="button" class="btn-chart-type" onclick="zoomTestMarkmap(0.8)" title="تصغير">🔍- تصغير</button>
            <button type="button" class="btn-chart-type" onclick="fitTestMarkmap()" title="ملاءمة الشاشة">⛶ ضبط</button>
          </div>
        </div>
        <div style="height: 380px; width: 100%; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); background: var(--bg-muted); overflow: hidden; position: relative;">
          <svg id="${markmapSvgId}" style="width: 100%; height: 100%; display: block;"></svg>
        </div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
          💡 الشجرة تفاعلية بالكامل: اسحب بالفأرة للتحريك، وانقر على الدوائر في العُقد لطي أو فرد الفروع، واستخدم عجلة الفأرة للتكبير.
        </div>
      </div>
    `;

    try {
      if (!window.markmap || !window.markmap.Markmap) {
        throw new Error('مكتبة Markmap لم يتم تحميلها بعد في الصفحة');
      }

      // تحضير نص الماركداون للشجرة
      let mdContent = mockText;
      if (mockText.startsWith('{') && mockText.includes('"markdown"')) {
        try {
          const parsed = JSON.parse(mockText);
          mdContent = parsed.markdown || mockText;
        } catch (e) {}
      }

      const { Transformer, Markmap } = window.markmap;
      const transformer = new Transformer();
      const { root } = transformer.transform(mdContent);
      const svg = document.getElementById(markmapSvgId);

      if (activeMarkmapInstance) {
        try { activeMarkmapInstance.destroy(); } catch (e) {}
      }

      activeMarkmapInstance = Markmap.create(svg, { autoFit: true, duration: 350 }, root);
      window._curTestMarkmap = activeMarkmapInstance;

      if (statusEl) {
        statusEl.innerHTML = '<span style="color: #10b981; font-weight: 600;">✅ نجح الاختبار: تم تشغيل ورسم شجرة Markmap التفاعلية بنجاح!</span>';
      }
      showToast('تم تشغيل ومعاينة خريطة وتشجير Markmap بنجاح 🌳');
    } catch (err) {
      console.error('Markmap render error:', err);
      preview.innerHTML += `<div style="color: #ef4444; font-size: 12px; margin-top: 8px;">خطأ تشغيل Markmap: ${escapeHtml(err.message)}</div>`;
      if (statusEl) {
        statusEl.innerHTML = `<span style="color: #ef4444;">❌ فشل الاختبار: ${escapeHtml(err.message)}</span>`;
      }
    }
    return;
  }

  // الحالة 2: أداة شجرة الأسانيد وشبكات الرواة Vis.js
  if (isVisNetwork) {
    const visContainerId = 'testVisContainer_' + Date.now();
    preview.innerHTML = `
      <div style="background: var(--bg-surface); padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); margin-top: 10px;">
        <div style="font-weight: 700; font-size: 13.5px; color: var(--accent-clay); margin-bottom: 8px;">معاينة شبكة الأسانيد التفاعلية (Vis.js Network):</div>
        <div id="${visContainerId}" style="height: 320px; width: 100%; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); background: var(--bg-muted);"></div>
      </div>
    `;

    try {
      let parsed = {};
      try { parsed = JSON.parse(mockText); } catch (e) {
        parsed = {
          nodes: [{ id: 1, label: "الزهري (مدار)" }, { id: 2, label: "مالك بن أنس" }],
          edges: [{ from: 1, to: 2, label: "سماع" }]
        };
      }
      const container = document.getElementById(visContainerId);
      if (window.vis && window.vis.Network && container) {
        const data = {
          nodes: new vis.DataSet(parsed.nodes || []),
          edges: new vis.DataSet(parsed.edges || [])
        };
        new vis.Network(container, data, {
          layout: { hierarchical: { direction: 'UD', sortMethod: 'directed' } },
          nodes: { font: { face: 'Amiri, sans-serif', size: 14, color: '#ffffff' }, margin: 8 },
          edges: { arrows: 'to', color: '#b45309' }
        });
        if (statusEl) {
          statusEl.innerHTML = '<span style="color: #10b981; font-weight: 600;">✅ نجح الاختبار: تم رسم شبكة الرواة التفاعلية بنجاح!</span>';
        }
        showToast('تم تشغيل ومعاينة شبكة الأسانيد بنجاح 🕸️');
      }
    } catch (err) {
      console.error('Vis test error:', err);
      if (statusEl) statusEl.innerHTML = `<span style="color: #ef4444;">❌ خطأ: ${escapeHtml(err.message)}</span>`;
    }
    return;
  }

  // الحالة 3: أداة المؤشرات والشارتات Chart.js
  let mockData = {};
  try {
    mockData = mockText ? JSON.parse(mockText) : { labels: ["أ", "ب", "ج"], values: [10, 20, 30] };
  } catch (e) {
    mockData = { labels: ["الجمهور", "الحنفية", "المالكية"], values: [65, 20, 15] };
  }

  preview.innerHTML = `
    <div style="background: var(--bg-surface); padding: 16px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); margin-top: 10px;">
      <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--accent-clay);">معاينة حية للمكتبة مع البيانات التجريبية:</div>
      <div style="max-height: 240px; position: relative;">
        <canvas id="toolWebTestCanvas" style="max-height: 220px; width: 100%;"></canvas>
      </div>
    </div>
  `;

  try {
    const ctx = document.getElementById('toolWebTestCanvas');
    if (window.Chart && ctx) {
      if (toolsState.activeChartInstance) {
        toolsState.activeChartInstance.destroy();
      }
      const labels = mockData.labels || Object.keys(mockData);
      const values = mockData.values || mockData.data || Object.values(mockData);

      toolsState.activeChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'المؤشر الإحصائي المقارن',
            data: values,
            backgroundColor: ACADEMIC_CHART_COLORS.slice(0, labels.length),
            borderColor: ACADEMIC_CHART_COLORS.slice(0, labels.length),
            borderWidth: 1.5,
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: true } }
        }
      });
      if (statusEl) {
        statusEl.innerHTML = '<span style="color: #10b981; font-weight: 600;">✅ نجح الاختبار: تم رسم الشارت البياني بنجاح!</span>';
      }
      showToast('تم تشغيل المعاينة الحية بنجاح 📊');
    }
  } catch (err) {
    console.error('Error testing web tool:', err);
    preview.innerHTML += `<div style="color: #ef4444; font-size: 12px; margin-top: 6px;">خطأ في العرض: ${escapeHtml(err.message)}</div>`;
    if (statusEl) statusEl.innerHTML = `<span style="color: #ef4444;">❌ خطأ: ${escapeHtml(err.message)}</span>`;
  }
}

function zoomTestMarkmap(scale) {
  if (window._curTestMarkmap) {
    try {
      window._curTestMarkmap.rescale(scale);
    } catch (e) {}
  }
}

function fitTestMarkmap() {
  if (window._curTestMarkmap) {
    try {
      window._curTestMarkmap.fit();
    } catch (e) {}
  }
}

// =============================================================================
// حفظ واعتماد الأداة في المنظومة
// =============================================================================
async function saveToolConfig() {
  const idInput = document.getElementById('toolIdInput');
  const nameInput = document.getElementById('toolNameInput');
  const descInput = document.getElementById('toolDescInput');

  let id = idInput ? idInput.value.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_') : '';
  let name = nameInput ? nameInput.value.trim() : '';
  const description = descInput ? descInput.value.trim() : '';

  if (!name) {
    const promptVal = document.getElementById('toolAiPromptInput')?.value.trim();
    if (promptVal) {
      name = promptVal.slice(0, 35) + '...';
      if (nameInput) nameInput.value = name;
    } else {
      showToast('يرجى إدخال اسم الأداة في الحقل المخصص', true);
      if (nameInput) {
        nameInput.focus();
        nameInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }
  }
  if (!id) {
    id = 'tool_' + Date.now();
  }

  const isWeb = document.getElementById('radioTypeWeb').checked;
  const toolType = isWeb ? 'ready_web_lib' : 'python_code';
  const selectedAiModel = !isWeb ? (document.getElementById('toolAiModelSelect')?.value || '') : '';

  let mockData = {};
  const mockStr = isWeb ? document.getElementById('toolWebMockData').value : document.getElementById('toolPythonTestInput').value;
  try {
    if (mockStr) {
      if (mockStr.trim().startsWith('{') || mockStr.trim().startsWith('[')) {
        mockData = JSON.parse(mockStr);
      } else {
        mockData = { markdown: mockStr };
      }
    }
  } catch (e) {
    mockData = { markdown: mockStr };
  }

  // تصنيف الأداة
  let category = 'أدوات مخصصة';
  if (isWeb) {
    if (name.includes('تشجير') || name.includes('Markmap') || name.includes('خرائط') || id.includes('markmap')) {
      category = 'تشجير ومفاهيم';
    } else if (name.includes('شارت') || name.includes('بيانات') || id.includes('chart')) {
      category = 'بيانات وإحصاء';
    } else if (name.includes('أسانيد') || name.includes('حديث') || id.includes('isnad')) {
      category = 'حديث ورجال';
    }
  } else {
    category = 'حساب وفلك';
  }

  const payload = {
    id: id,
    name: name,
    desc: description,
    description: description,
    type: isWeb ? 'web_library' : 'python_script',
    tool_type: toolType,
    category: category,
    enabled: true,
    model: selectedAiModel,
    library_url: isWeb ? document.getElementById('toolWebUrlInput').value.trim() : '',
    github_url: isWeb ? document.getElementById('toolWebUrlInput').value.trim() : '',
    init_script: isWeb ? document.getElementById('toolWebInitScript').value.trim() : '',
    python_code: !isWeb ? document.getElementById('toolPythonCode').value : '',
    entry_function: 'run_tool',
    mock_data: mockData,
    mock_test_data: mockData
  };

  try {
    const res = await fetch('/api/tools', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'فشل حفظ الأداة');
    }
    showToast(`🎉 تم حفظ واعتماد أداة «${name}» بنجاح! أصبحت متاحة لمهندس ومدير المشروع.`);
    closeToolModal();
    await loadToolsList();
  } catch (err) {
    console.error('Error saving tool:', err);
    showToast(`فشل حفظ الأداة: ${err.message}`, true);
  }
}

// =============================================================================
// حذف أداة
// =============================================================================
async function deleteToolConfirm(toolId, toolName) {
  const confirmed = await showConfirmDialog({
    title: 'تأكيد حذف الأداة البرمجية',
    message: `هل أنت متأكد من حذف أداة «${toolName}» نهائياً من المنظومة؟`,
    confirmText: 'نعم، احذف الأداة',
    cancelText: 'إلغاء',
    danger: true,
    icon: 'trash-2'
  });

  if (!confirmed) {
    return;
  }

  try {
    const res = await fetch(`/api/tools/${toolId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('فشل الحذف');
    showToast(`تم حذف أداة «${toolName}»`);
    await loadToolsList();
  } catch (err) {
    console.error('Error deleting tool:', err);
    showToast(`فشل حذف الأداة: ${err.message}`, true);
  }
}

// =============================================================================
// تصدير واستيراد الأدوات البرمجية (Export & Import Tools)
// =============================================================================

function downloadJsonFile(filename, dataObj) {
  const jsonStr = JSON.stringify(dataObj, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// 1. تصدير أداة واحدة محددة
function exportSingleTool(toolId) {
  const tool = toolsState.tools.find(t => t.id === toolId);
  if (!tool) {
    showToast('الأداة غير موجودة لتصديرها', true);
    return;
  }
  const cleanId = (tool.id || 'tool').replace(/[^a-zA-Z0-9_-]/g, '_');
  const filename = `tool_${cleanId}.json`;
  const exportPayload = {
    export_version: '1.0',
    exported_at: new Date().toISOString(),
    type: 'almojtahed_tool',
    tool: tool
  };
  downloadJsonFile(filename, exportPayload);
  showToast(`تم حفظ أداة «${tool.name}» في جهازك`);
}

// 2. تصدير كافة الأدوات كحزمة كاملة
function exportAllTools() {
  if (!toolsState.tools || toolsState.tools.length === 0) {
    showToast('لا توجد أدوات لتصديرها حالياً', true);
    return;
  }
  const filename = `almojtahed_tools_all_${new Date().toISOString().slice(0, 10)}.json`;
  const exportPayload = {
    export_version: '1.0',
    exported_at: new Date().toISOString(),
    type: 'almojtahed_tools_bundle',
    tools_count: toolsState.tools.length,
    tools: toolsState.tools
  };
  downloadJsonFile(filename, exportPayload);
  showToast(`📤 تم تصدير كافة الأدوات (${toolsState.tools.length} أداة) كحزمة بنجاح!`);
}

// 3. تصدير الأداة الحالية المفتوحة في المحرر
function shareCurrentModalTool() {
  const id = (document.getElementById('toolIdInput')?.value || '').trim();
  const name = (document.getElementById('toolNameInput')?.value || '').trim() || 'الأداة';
  const saved = toolsState.tools.some(tool => tool.id === id);
  if (typeof openSharePicker !== 'function') return;
  openSharePicker('tool', id, name, { device: 'editor', unsaved: !saved });
}

function exportCurrentModalTool() {
  const idInput = document.getElementById('toolIdInput');
  const nameInput = document.getElementById('toolNameInput');
  const descInput = document.getElementById('toolDescInput');

  const name = nameInput ? nameInput.value.trim() : '';
  let id = idInput ? idInput.value.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_') : '';
  const description = descInput ? descInput.value.trim() : '';

  if (!name && !id) {
    showToast('يرجى كتابة اسم أو معرّف للأداة قبل حفظها', true);
    return false;
  }

  const isWeb = document.getElementById('radioTypeWeb').checked;
  const toolType = isWeb ? 'ready_web_lib' : 'python_code';
  const selectedAiModel = !isWeb ? (document.getElementById('toolAiModelSelect')?.value || '') : '';

  let mockData = {};
  const mockStr = isWeb ? document.getElementById('toolWebMockData').value : document.getElementById('toolPythonTestInput').value;
  try {
    if (mockStr) {
      if (mockStr.trim().startsWith('{') || mockStr.trim().startsWith('[')) {
        mockData = JSON.parse(mockStr);
      } else {
        mockData = { markdown: mockStr };
      }
    }
  } catch (e) {
    mockData = { markdown: mockStr };
  }

  const toolData = {
    id: id || 'tool_' + Date.now(),
    name: name || 'أداة بدون اسم',
    desc: description,
    description: description,
    type: isWeb ? 'web_library' : 'python_script',
    tool_type: toolType,
    category: isWeb ? 'مكتبات ويب' : 'أدوات بايثون',
    enabled: true,
    model: selectedAiModel,
    library_url: isWeb ? document.getElementById('toolWebUrlInput').value.trim() : '',
    github_url: isWeb ? document.getElementById('toolWebUrlInput').value.trim() : '',
    init_script: isWeb ? document.getElementById('toolWebInitScript').value.trim() : '',
    python_code: !isWeb ? document.getElementById('toolPythonCode').value : '',
    entry_function: 'run_tool',
    mock_data: mockData,
    mock_test_data: mockData
  };

  const cleanId = (toolData.id).replace(/[^a-zA-Z0-9_-]/g, '_');
  const filename = `tool_${cleanId}.json`;
  const exportPayload = {
    export_version: '1.0',
    exported_at: new Date().toISOString(),
    type: 'almojtahed_tool',
    tool: toolData
  };
  downloadJsonFile(filename, exportPayload);
  showToast('تم حفظ الأداة في جهازك');
  return true;
}

// 4. معالجة استيراد أداة أو حزمة من ملف JSON (التبويب الرئيسي)
async function handleImportToolFile(event) {
  const fileInput = event.target;
  const file = fileInput.files && fileInput.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async function(e) {
    try {
      const rawText = e.target.result;
      let parsed = JSON.parse(rawText);

      let toolsToImport = [];
      if (parsed.type === 'almojtahed_tools_bundle' && Array.isArray(parsed.tools)) {
        toolsToImport = parsed.tools;
      } else if (parsed.type === 'almojtahed_tool' && parsed.tool) {
        toolsToImport = [parsed.tool];
      } else if (Array.isArray(parsed)) {
        toolsToImport = parsed;
      } else if (typeof parsed === 'object' && (parsed.name || parsed.python_code || parsed.id)) {
        toolsToImport = [parsed];
      } else {
        throw new Error('ملف JSON لا يحتوي على بيانات أداة صالحة لمنظومة المجتهد');
      }

      if (toolsToImport.length === 0) {
        showToast('لم يتم العثور على أدوات صالحة داخل الملف', true);
        return;
      }

      if (toolsToImport.length === 1) {
        const tool = toolsToImport[0];
        const existing = toolsState.tools.find(t => t.id === tool.id);
        let overwrite = false;
        if (existing) {
          const choice = await showConfirmDialog({
            title: 'الأداة موجودة مسبقاً',
            message: `الأداة «${tool.name || tool.id}» مسجلة مسبقاً بنفس المعرف التقني (${tool.id}). هل ترغب في استبدال الأداة الحالية أم استيرادها كنسخة جديدة؟`,
            confirmText: 'استبدال الحالية',
            cancelText: 'استيراد كنسخة جديدة',
            danger: false,
            icon: 'alert-circle'
          });
          overwrite = choice;
        }

        const res = await fetch('/api/tools/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data: tool, overwrite: overwrite })
        });
        const result = await res.json();
        if (!res.ok) throw new Error(result.detail || 'فشل الاستيراد');

        showToast(`🎉 تم استيراد أداة «${tool.name}» بنجاح!`);
        await loadToolsList();
      } else {
        const confirmBulk = await showConfirmDialog({
          title: 'تأكيد استيراد حزمة أدوات',
          message: `تم العثور على حزمة تحتوي (${toolsToImport.length}) أدوات برمجية. هل تريد استيرادها الآن؟`,
          confirmText: 'نعم، استورد الكل',
          cancelText: 'إلغاء',
          icon: 'download'
        });
        if (!confirmBulk) return;

        const res = await fetch('/api/tools/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data: toolsToImport, overwrite: false })
        });
        const result = await res.json();
        if (!res.ok) throw new Error(result.detail || 'فشل استيراد الحزمة');

        showToast(`🎉 تم استيراد (${result.imported_count || toolsToImport.length}) أداة بنجاح!`);
        await loadToolsList();
      }
    } catch (err) {
      console.error('Error importing tool:', err);
      showToast(`فشل استيراد الأداة: ${err.message}`, true);
    } finally {
      fileInput.value = '';
    }
  };
  reader.readAsText(file);
}

// 5. استيراد ملف أداة مباشرة إلى نافذة المحرر (Modal)
function handleImportModalToolFile(event) {
  const fileInput = event.target;
  const file = fileInput.files && fileInput.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(e) {
    try {
      const rawText = e.target.result;
      let parsed = JSON.parse(rawText);

      let tool = null;
      if (parsed.type === 'almojtahed_tool' && parsed.tool) {
        tool = parsed.tool;
      } else if (parsed.type === 'almojtahed_tools_bundle' && Array.isArray(parsed.tools) && parsed.tools.length > 0) {
        tool = parsed.tools[0];
      } else if (Array.isArray(parsed) && parsed.length > 0) {
        tool = parsed[0];
      } else if (typeof parsed === 'object') {
        tool = parsed;
      }

      if (!tool || (!tool.name && !tool.python_code && !tool.library_url)) {
        throw new Error('ملف الأداة غير صالح أو فارغ');
      }

      // تعبئة حقول المحرر
      const idInput = document.getElementById('toolIdInput');
      const nameInput = document.getElementById('toolNameInput');
      const descInput = document.getElementById('toolDescInput');

      if (nameInput) nameInput.value = tool.name || '';
      if (idInput) {
        idInput.value = tool.id || '';
        idInput.disabled = false;
      }
      if (descInput) descInput.value = tool.description || tool.desc || '';

      const isWeb = (tool.tool_type === 'ready_web_lib' || tool.type === 'web_library');
      switchToolModalType(isWeb ? 'ready_web_lib' : 'python_code');

      if (isWeb) {
        const urlInput = document.getElementById('toolWebUrlInput');
        const scriptInput = document.getElementById('toolWebInitScript');
        const mockInput = document.getElementById('toolWebMockData');
        if (urlInput) urlInput.value = tool.library_url || tool.github_url || '';
        if (scriptInput) scriptInput.value = tool.init_script || '';
        if (mockInput) {
          const mData = tool.mock_data || tool.mock_test_data || '';
          mockInput.value = typeof mData === 'string' ? mData : JSON.stringify(mData, null, 2);
        }
      } else {
        const codeInput = document.getElementById('toolPythonCode');
        const testInput = document.getElementById('toolPythonTestInput');
        if (codeInput) codeInput.value = tool.python_code || '';
        if (testInput) {
          const mData = tool.mock_data || tool.mock_test_data || '';
          testInput.value = typeof mData === 'string' ? mData : JSON.stringify(mData, null, 2);
        }
        if (tool.model) {
          initToolAiModels(tool.model);
        }
      }

      showToast(`📥 تم استيراد بيانات أداة «${tool.name || 'المخصصة'}» إلى المحرر بنجاح! يمكنك تجربتها واعتمادها الآن.`);
    } catch (err) {
      console.error('Error importing tool to modal:', err);
      showToast(`فشل قراءة ملف الأداة: ${err.message}`, true);
    } finally {
      fileInput.value = '';
    }
  };
  reader.readAsText(file);
}

// =============================================================================
// نافذة تجربة الأداة التفاعلية (Playground Modal)
// =============================================================================
function openToolPlayground(toolId) {
  const tool = toolsState.tools.find(t => t.id === toolId);
  if (!tool) return;

  const modal = document.getElementById('toolPlaygroundModal');
  if (!modal) return;

  document.getElementById('playgroundToolTitle').textContent = `بيئة تجربة أداة: «${tool.name}» 🧪`;
  document.getElementById('playgroundToolDesc').textContent = tool.description || '';

  const isWeb = tool.tool_type === 'ready_web_lib' || tool.type === 'web_library';
  const container = document.getElementById('playgroundWorkArea');
  if (!container) return;

  if (toolId === 'markmap_mindmap' || tool.category === 'تشجير ومفاهيم' || toolId.includes('markmap')) {
    const rawMd = (tool.mock_data && tool.mock_data.markdown) ? tool.mock_data.markdown :
`# مسألة إتيان المرأة في دبرها: تحرير المذاهب والأقوال
## 1. القول الأول: التحريم القطعي (جمهور الأمة)
- المالكية: مذهب المدونة والمشهور عن مالك
- الشافعية: نصوص الأم ومختصر المزني
- الحنابلة: رواية الجماعة عن أحمد ورأي الخلال
- الحنفية: ظاهر الرواية والمبسوط وبدائع الصنائع
## 2. القول الثاني: روايات الكراهة التنزيهية أو الرخصة
- روايات منسوبة لبعض التابعين (محل نقد وتعليل)
- تأويل ما نُسب لمالك وبيان كذب الواقدي
## 3. مسالك الاستدلال والترجيح
- آية الحرث: ﴿فَأْتُوا حَرْثَكُمْ أَنَّى شِئْتُمْ﴾ وموضع الولد
- أحاديث النهي الواردة ودرجاتها وأسانيدها
- القياس الأصولي: تعليل الحرمة بالأذى ومجانبة الفطرة
## 4. المقاربة الطبية المعاصرة
- تقارير منظمة الصحة العالمية والمجلات الطبية (Lancet & CDC)
- المخاطر الوبائية والتهتك النسيجي وأضرار الإتيان المعاصرة`;

    container.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 14px;">
        <div style="font-size: 13.5px; color: var(--text-secondary);">
          رسم شجرة المسائل والمفاهيم والخريطة الذهنية التفاعلية (Markmap Interactive Mindmap):
        </div>
        <div style="display: flex; gap: 14px; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 320px;">
            <label style="font-size: 12.5px; font-weight: 600;">نص الشجرة والمسائل (Markdown):</label>
            <textarea id="playgroundMarkmapInput" class="tool-code-box" rows="12">${escapeHtml(rawMd)}</textarea>
            <div style="margin-top: 10px; display: flex; gap: 8px;">
              <button class="btn-primary-gradient" onclick="renderPlaygroundMarkmap()">🌳 تحديث الشجرة والخريطة</button>
            </div>
          </div>
          <div style="flex: 1.4; min-width: 360px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <label style="font-size: 12.5px; font-weight: 600;">الخريطة الذهنية والشجرة التفاعلية:</label>
              <div style="display: flex; gap: 6px;">
                <button type="button" class="btn-chart-type" onclick="zoomPlaygroundMarkmap(1.25)">🔍+ تكبير</button>
                <button type="button" class="btn-chart-type" onclick="zoomPlaygroundMarkmap(0.75)">🔍- تصغير</button>
                <button type="button" class="btn-chart-type" onclick="fitPlaygroundMarkmap()">⛶ ملاءمة</button>
              </div>
            </div>
            <div style="height: 380px; width: 100%; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); background: var(--bg-muted); overflow: hidden; position: relative;">
              <svg id="playgroundMarkmapSvg" style="width: 100%; height: 100%; display: block;"></svg>
            </div>
            <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 6px;">
              💡 انقر على دوائر العُقد لتفريع الأقوال أو طيها، واسحب الشجرة بالفأرة للتنقل والتكبير.
            </div>
          </div>
        </div>
      </div>
    `;

    setTimeout(() => {
      renderPlaygroundMarkmap();
    }, 100);
    modal.classList.add('active', 'open');
    return;
  }

  if (toolId === 'hadith_isnad_tree') {
    container.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 14px;">
        <div style="font-size: 13.5px; color: var(--text-secondary);">
          رسم شجرة الأسانيد وشبكة الرواة التفاعلية بصرياً (Vis.js Network):
        </div>
        <div style="display: flex; gap: 12px; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 280px;">
            <label style="font-size: 12.5px; font-weight: 600;">بيانات العُقد والأطراف (JSON):</label>
            <textarea id="playgroundIsnadInput" class="tool-code-box" rows="8">${escapeHtml(
              JSON.stringify(
                tool.mock_data || tool.mock_test_data || {
                  nodes: [
                    { id: 1, label: "ابن شهاب الزهري (مدار)", shape: "box", color: "#b45309" },
                    { id: 2, label: "مالك بن أنس (الموطأ)", shape: "ellipse", color: "#059669" },
                    { id: 3, label: "سفيان بن عيينة", shape: "ellipse", color: "#059669" },
                    { id: 4, label: "معمر بن راشد", shape: "ellipse", color: "#059669" }
                  ],
                  edges: [
                    { from: 1, to: 2, label: "سماع صريح" },
                    { from: 1, to: 3, label: "سماع صريح" },
                    { from: 1, to: 4, label: "سماع صريح" }
                  ]
                },
                null,
                2
              )
            )}</textarea>
            <div style="margin-top: 8px; display: flex; gap: 8px;">
              <button class="btn-primary-gradient" onclick="renderPlaygroundIsnadTree('UD')">🌳 شجرة هرمية (أعلى-أسفل)</button>
              <button class="btn-secondary-action" onclick="renderPlaygroundIsnadTree('free')">🕸️ شبكة حرة</button>
            </div>
          </div>
          <div style="flex: 1.3; min-width: 340px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 16px;">
            <div style="font-weight: 700; font-size: 14px; margin-bottom: 8px; color: var(--text-main); display: flex; justify-content: space-between;">
              <span>شجرة الأسانيد الحية:</span>
              <span style="font-size: 11px; color: var(--text-muted);">اسحب العُقد أو قرّب بالماوس</span>
            </div>
            <div id="playgroundIsnadContainer" style="height: 280px; width: 100%; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); background: var(--bg-muted);"></div>
          </div>
        </div>
      </div>
    `;
    setTimeout(() => renderPlaygroundIsnadTree('UD'), 100);
  } else if (toolId === 'charts_metrics' || isWeb) {
    container.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 14px;">
        <div style="font-size: 13.5px; color: var(--text-secondary);">
          أدخل بيانات إحصائية أو نسباً مقارنة لتوليد الشارتات والمؤشرات البيانية فورياً:
        </div>
        <div style="display: flex; gap: 12px; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 280px;">
            <label style="font-size: 12.5px; font-weight: 600;">بيانات المقارنة (JSON):</label>
            <textarea id="playgroundDataInput" class="tool-code-box" rows="7">{\n  "labels": ["القول بالجواز (الجمهور)", "القول بالمنع والتحريم", "القول بالكراهة التنزيهية", "التوقف والتردد"],\n  "values": [58, 26, 11, 5]\n}</textarea>
            <div style="margin-top: 8px; display: flex; gap: 8px;">
              <button class="btn-primary-gradient" onclick="renderPlaygroundChart('bar')">📊 رسم بياني بالأعمدة</button>
              <button class="btn-secondary-action" onclick="renderPlaygroundChart('pie')">🥧 رسم دائري (Pie)</button>
              <button class="btn-secondary-action" onclick="renderPlaygroundChart('doughnut')">🍩 دونات (Doughnut)</button>
            </div>
          </div>
          <div style="flex: 1.2; min-width: 320px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 16px;">
            <div style="font-weight: 700; font-size: 14px; margin-bottom: 8px; color: var(--text-main);">اللوحة البيانية الحية:</div>
            <div style="height: 260px; position: relative;">
              <canvas id="playgroundCanvas"></canvas>
            </div>
          </div>
        </div>
      </div>
    `;
    setTimeout(() => renderPlaygroundChart('bar'), 100);
  } else {
    // Python tool
    container.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 14px;">
        <div style="display: flex; gap: 12px; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 300px;">
            <label style="font-size: 12.5px; font-weight: 600;">مدخلات الفحص (JSON):</label>
            <textarea id="playgroundPyInput" class="tool-code-box" rows="8">${escapeHtml(tool.mock_test_data ? JSON.stringify(tool.mock_test_data, null, 2) : '{\n  "year": 12,\n  "text": "انكسفت الشمس"\n}')}</textarea>
            <button class="btn-primary-gradient" onclick="runPlaygroundPythonTool('${escapeHtml(tool.id)}')" style="margin-top: 10px;">
              تشغيل الخوارزمية ⚡
            </button>
          </div>
          <div style="flex: 1; min-width: 300px;">
            <label style="font-size: 12.5px; font-weight: 600;">نتيجة الحساب والتحقق:</label>
            <div id="playgroundPyResult" class="tool-test-result-box" style="height: 190px; margin-top: 0;">
              اضغط «تشغيل الخوارزمية» لمشاهدة المخرجات الحية...
            </div>
          </div>
        </div>
      </div>
    `;
  }

  modal.classList.add('active', 'open');
}

function closeToolPlayground() {
  const modal = document.getElementById('toolPlaygroundModal');
  if (modal) modal.classList.remove('active', 'open');
  if (toolsState.playgroundChartInstance) {
    toolsState.playgroundChartInstance.destroy();
    toolsState.playgroundChartInstance = null;
  }
}

function renderPlaygroundChart(chartType) {
  const dataInput = document.getElementById('playgroundDataInput');
  const canvas = document.getElementById('playgroundCanvas');
  if (!dataInput || !canvas || !window.Chart) return;

  let parsed = {};
  try {
    parsed = JSON.parse(dataInput.value);
  } catch (e) {
    showToast('بيانات JSON غير صالحة', true);
    return;
  }

  if (toolsState.playgroundChartInstance) {
    toolsState.playgroundChartInstance.destroy();
  }

  const labels = parsed.labels || Object.keys(parsed);
  const values = parsed.values || Object.values(parsed);

  const colors = [
    'rgba(180, 83, 9, 0.75)',
    'rgba(37, 99, 235, 0.75)',
    'rgba(22, 163, 74, 0.75)',
    'rgba(217, 119, 6, 0.75)',
    'rgba(147, 51, 234, 0.75)',
    'rgba(225, 29, 72, 0.75)'
  ];

  toolsState.playgroundChartInstance = new Chart(canvas, {
    type: chartType || 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'النسبة والعدد المستخرج',
        data: values,
        backgroundColor: colors.slice(0, labels.length),
        borderColor: colors.map(c => c.replace('0.75', '1')),
        borderWidth: 1.5,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: chartType !== 'bar',
          position: 'bottom',
          labels: { font: { family: 'Tajawal, sans-serif' } }
        }
      }
    }
  });
}

// =============================================================================
// دوال تشغيل ومعاينة خريطة وتشجير Markmap في الـ Playground
// =============================================================================
let activePlaygroundMarkmap = null;

function renderPlaygroundMarkmap() {
  const inputEl = document.getElementById('playgroundMarkmapInput');
  const svgEl = document.getElementById('playgroundMarkmapSvg');
  if (!inputEl || !svgEl) return;

  if (!window.markmap || !window.markmap.Markmap) {
    showToast('مكتبة Markmap غير جاهزة بعد', true);
    return;
  }

  try {
    const { Transformer, Markmap } = window.markmap;
    const transformer = new Transformer();
    const { root } = transformer.transform(inputEl.value);

    if (activePlaygroundMarkmap) {
      try { activePlaygroundMarkmap.destroy(); } catch (e) {}
    }

    activePlaygroundMarkmap = Markmap.create(svgEl, { autoFit: true, duration: 400 }, root);
    window._curPlaygroundMarkmap = activePlaygroundMarkmap;
  } catch (err) {
    console.error('Playground Markmap error:', err);
    showToast(`خطأ في رسم الشجرة: ${err.message}`, true);
  }
}

function zoomPlaygroundMarkmap(factor) {
  if (window._curPlaygroundMarkmap) {
    try { window._curPlaygroundMarkmap.rescale(factor); } catch (e) {}
  }
}

function fitPlaygroundMarkmap() {
  if (window._curPlaygroundMarkmap) {
    try { window._curPlaygroundMarkmap.fit(); } catch (e) {}
  }
}

async function runPlaygroundPythonTool(toolId) {
  const tool = toolsState.tools.find(t => t.id === toolId);
  if (!tool) return;

  const inBox = document.getElementById('playgroundPyInput');
  const resBox = document.getElementById('playgroundPyResult');
  if (!inBox || !resBox) return;

  let inputData = {};
  try {
    inputData = JSON.parse(inBox.value);
  } catch (e) {
    showToast('صيغة مدخلات JSON غير صحيحة', true);
    return;
  }

  resBox.className = 'tool-test-result-box';
  resBox.innerHTML = 'جارٍ تشغيل الخوارزمية... ⏳';

  try {
    const res = await fetch('/api/tools/test-python', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: tool.python_code || '',
        input_data: inputData,
        entry_function: tool.entry_function || 'run_tool'
      })
    });
    const data = await res.json();
    if (data.success) {
      resBox.className = 'tool-test-result-box tool-test-success';
      resBox.innerHTML = `<strong>✅ النتيجة بنجاح:</strong>\n\n${escapeHtml(JSON.stringify(data.output, null, 2))}`;
    } else {
      resBox.className = 'tool-test-result-box tool-test-failure';
      resBox.innerHTML = `<strong>❌ خطأ في التنفيذ:</strong>\n\n${escapeHtml(data.error || 'خطأ غير معروف')}`;
    }
  } catch (err) {
    resBox.className = 'tool-test-result-box tool-test-failure';
    resBox.innerHTML = `خطأ في الاتصال: ${escapeHtml(err.message)}`;
  }
}

// =============================================================================
// تعبئة خيارات أداة التحقق في كروت المشاريع ديناميكياً
// =============================================================================
function populateProjectToolsDropdown(tools) {
  const select = document.getElementById('pCompToolType');
  if (!select) return;

  const currentVal = select.value;
  let optionsHtml = `
    <option value="none">بدون أداة مساعدة (أبحاث فقهية/لغوية لا تتطلب حسابات)</option>
  `;

  (tools || []).forEach(t => {
    if (t.enabled !== false) {
      const typeLabel = t.tool_type === 'ready_web_lib' ? 'مكتبة ويب' : 'كود بايثون';
      optionsHtml += `
        <option value="${escapeHtml(t.id)}">${escapeHtml(t.name)} (${typeLabel})</option>
      `;
    }
  });

  select.innerHTML = optionsHtml;
  if (currentVal) {
    select.value = currentVal;
  }
}

// =============================================================================
// مستخرج الشارتات البيانية التلقائي والمطور من جداول ونصوص نتائج المشروع
// =============================================================================

const renderedProjectCharts = {};
const ACADEMIC_CHART_COLORS = [
  '#B45309', // ذهبي ترابي
  '#1D4ED8', // أزرق أكاديمي
  '#059669', // زمردي
  '#7C3AED', // بنفسجي
  '#DC2626', // قرمزي
  '#0891B2', // سماوي
  '#D97706', // عنبري
  '#4F46E5', // نيلي
  '#0D9488', // تركوازي
  '#BE185D'  // وردي رصين
];

function extractNumericValue(text) {
  if (text === null || text === undefined) return NaN;
  let s = String(text).trim();
  if (!s) return NaN;
  // تحويل الأرقام المشرقية العربية ٠-٩ إلى أرقام لاتينية 0-9
  s = s.replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
  // إزالة علامات النسبة المئوية والفواصل والتنوين والكلمات الزائدة الشائعة
  s = s.replace(/[%٪,،~]/g, ' ');
  // استخراج أول رقم عشري أو صحيح
  const match = s.match(/[-+]?\d*\.?\d+/);
  return match ? parseFloat(match[0]) : NaN;
}

function switchChartType(chartId, newType) {
  const chartData = renderedProjectCharts[chartId];
  if (!chartData) return;
  chartData.currentType = newType;
  renderOrUpdateCanvasChart(chartId, newType);
}

function renderOrUpdateCanvasChart(chartId, type) {
  const chartData = renderedProjectCharts[chartId];
  const canvas = document.getElementById(chartId);
  if (!chartData || !canvas || !window.Chart) return;

  // تنظيف أي رسم سابق على نفس الكانفاس لمنع تعارض Chart.js
  if (chartData.instance) {
    try {
      chartData.instance.destroy();
    } catch (e) {}
    chartData.instance = null;
  }

  // تحديث حالة الأزرار في الترويسة
  const wrapper = canvas.closest('.chart-render-wrapper');
  if (wrapper) {
    wrapper.querySelectorAll('.btn-chart-type').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-type') === type);
    });
  }

  const labels = chartData.labels || [];
  const values = chartData.values || [];
  const title = chartData.title || 'المؤشرات والنسب';

  // توليد ألوان متناسقة لكل شريحة أو عمود
  const bgColors = labels.map((_, i) => ACADEMIC_CHART_COLORS[i % ACADEMIC_CHART_COLORS.length]);
  const borderColors = bgColors;

  const isCircular = (type === 'pie' || type === 'doughnut');
  const dataset = {
    label: title,
    data: values,
    backgroundColor: isCircular ? bgColors : (type === 'line' ? 'rgba(180, 83, 9, 0.2)' : bgColors),
    borderColor: isCircular ? '#ffffff' : (type === 'line' ? '#B45309' : borderColors),
    borderWidth: isCircular ? 2 : 1.5,
    borderRadius: type === 'bar' ? 6 : 0,
    fill: type === 'line',
    tension: 0.3
  };

  try {
    chartData.instance = new Chart(canvas, {
      type: type,
      data: {
        labels: labels,
        datasets: [dataset]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 400 },
        plugins: {
          legend: {
            display: isCircular,
            position: 'bottom',
            labels: {
              font: { family: 'Tajawal, sans-serif', size: 12 },
              padding: 12
            }
          },
          tooltip: {
            rtl: true,
            titleFont: { family: 'Tajawal, sans-serif' },
            bodyFont: { family: 'Tajawal, sans-serif' },
            callbacks: {
              label: function(context) {
                const val = context.raw;
                return ` ${context.dataset.label || ''}: ${val}%`;
              }
            }
          }
        },
        scales: isCircular ? {} : {
          y: {
            beginAtZero: true,
            ticks: { font: { family: 'Tajawal, sans-serif', size: 11 } }
          },
          x: {
            ticks: { font: { family: 'Tajawal, sans-serif', size: 11 } }
          }
        }
      }
    });
  } catch (err) {
    console.error('Failed to create Chart.js instance:', err);
  }
}

function autoRenderProjectResultCharts(containerElement) {
  if (!containerElement || !window.Chart) return;

  // 1. فحص كتل كود الماركداون المباشرة مثل ```chart أو ```json أو ```mermaid
  const codeBlocks = containerElement.querySelectorAll('pre code');
  codeBlocks.forEach((codeEl, idx) => {
    const rawText = codeEl.innerText.trim();
    const preEl = codeEl.closest('pre');
    if (!preEl || preEl.previousElementSibling?.classList.contains('chart-render-wrapper')) return;

    // أ) فحص كود Mermaid pie
    if (rawText.startsWith('pie title') || rawText.startsWith('pie\n')) {
      const lines = rawText.split('\n');
      let chartTitle = 'المؤشرات والنسب المقارنة';
      const cLabels = [];
      const cValues = [];
      lines.forEach(l => {
        l = l.trim();
        if (l.startsWith('pie title')) {
          chartTitle = l.replace('pie title', '').trim();
        } else if (l.includes(':')) {
          const parts = l.split(':');
          const lbl = parts[0].replace(/["']/g, '').trim();
          const val = extractNumericValue(parts[1]);
          if (lbl && !isNaN(val)) {
            cLabels.push(lbl);
            cValues.push(val);
          }
        }
      });

      if (cLabels.length >= 2) {
        insertChartComponent(preEl, `mermaidChart_${idx}_${Date.now()}`, chartTitle, cLabels, cValues, 'pie');
      }
    }
    // ب) فحص كود JSON للشارت (إذا كتب النموذج كود chart أو json)
    else if ((rawText.includes('"labels"') && (rawText.includes('"data"') || rawText.includes('"values"'))) || codeEl.className.includes('chart')) {
      try {
        let cleanJson = rawText.replace(/,\s*([}\]])/g, '$1');
        const parsed = JSON.parse(cleanJson);
        const chartObj = parsed.chart || parsed;
        const cLabels = chartObj.labels || [];
        const rawValues = chartObj.data || chartObj.values || [];
        const cValues = rawValues.map(v => extractNumericValue(v)).filter(v => !isNaN(v));
        const chartTitle = chartObj.title || 'شارت البيانات المستخرجة';
        const chartType = chartObj.type || 'bar';

        if (cLabels.length >= 2 && cValues.length >= 2) {
          insertChartComponent(preEl, `codeChart_${idx}_${Date.now()}`, chartTitle, cLabels, cValues, chartType);
        }
      } catch (e) {}
    }
  });

  // 2. فحص جداول الماركداون واستخراج الأعمدة الرقمية ونسب الأقوال
  const tables = containerElement.querySelectorAll('table');
  if (!tables || tables.length === 0) return;

  tables.forEach((table, idx) => {
    const nextElem = table.nextElementSibling;
    if (nextElem && nextElem.classList.contains('chart-render-wrapper')) return;

    const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    if (rows.length < 2) return;

    // فحص كافة الأعمدة لاكتشاف العمود الرقمي والعمود الوصفي
    let bestNumericCol = -1;
    let bestNumericCount = 0;
    let bestLabelCol = -1;

    for (let c = 0; c < headers.length; c++) {
      let numCount = 0;
      let isIndexCol = true;
      rows.forEach((r, rIdx) => {
        const cells = r.querySelectorAll('td');
        if (cells[c]) {
          const val = extractNumericValue(cells[c].innerText);
          if (!isNaN(val) && isFinite(val)) {
            numCount++;
            if (val !== rIdx + 1 && val !== rIdx) {
              isIndexCol = false;
            }
          }
        }
      });

      const headerText = headers[c] || '';
      const isHeaderMetric = /نسبة|نسب|أعداد|عدد|مجموع|تكرار|مؤشر|إحصاء|درجة|قيمة|طرق|شواهد|المجموع/i.test(headerText);
      const isHeaderIndex = /^[#م]$|^الرقم$|^ت$|^تسلسل$/i.test(headerText);

      if (isHeaderIndex || (isIndexCol && numCount === rows.length && !isHeaderMetric)) {
        continue;
      }

      if (numCount >= rows.length * 0.4 || (isHeaderMetric && numCount >= 1)) {
        if (numCount > bestNumericCount || isHeaderMetric) {
          bestNumericCol = c;
          bestNumericCount = numCount;
        }
      } else if (bestLabelCol === -1) {
        bestLabelCol = c;
      }
    }

    if (bestNumericCol === -1) return; // لا توجد بيانات رقمية كافية لرسم شارت

    if (bestLabelCol === -1) {
      for (let c = 0; c < headers.length; c++) {
        if (c !== bestNumericCol && !/^[#م]$|^الرقم$|^ت$/i.test(headers[c])) {
          bestLabelCol = c;
          break;
        }
      }
      if (bestLabelCol === -1) bestLabelCol = 0;
    }

    // استخراج التسميات والقيم الرقمية
    const chartLabels = [];
    const chartValues = [];
    rows.forEach(r => {
      const cells = r.querySelectorAll('td');
      if (cells[bestLabelCol] && cells[bestNumericCol]) {
        const lbl = cells[bestLabelCol].innerText.trim();
        const num = extractNumericValue(cells[bestNumericCol].innerText);
        if (!isNaN(num) && lbl) {
          chartLabels.push(lbl.length > 30 ? lbl.substring(0, 28) + '..' : lbl);
          chartValues.push(num);
        }
      }
    });

    if (chartLabels.length < 2) return;

    const chartTitle = headers[bestNumericCol] || 'المؤشرات والنسب المقارنة';
    const chartId = `tableChart_${idx}_${Date.now()}`;
    insertChartComponent(table, chartId, chartTitle, chartLabels, chartValues, 'bar');
  });
}

function insertChartComponent(anchorElement, chartId, title, labels, values, initialType = 'bar') {
  const chartWrapper = document.createElement('div');
  chartWrapper.className = 'chart-render-wrapper';
  chartWrapper.innerHTML = `
    <div class="chart-render-header">
      <div class="chart-render-title">
        <span>📊</span>
        <span>شارت المؤشرات المقارنة: ${escapeHtml(title)}</span>
      </div>
      <div class="chart-type-buttons">
        <button class="btn-chart-type ${initialType === 'bar' ? 'active' : ''}" data-type="bar" onclick="switchChartType('${chartId}', 'bar')">📊 أعمدة</button>
        <button class="btn-chart-type ${initialType === 'doughnut' ? 'active' : ''}" data-type="doughnut" onclick="switchChartType('${chartId}', 'doughnut')">🍩 دونات</button>
        <button class="btn-chart-type ${initialType === 'pie' ? 'active' : ''}" data-type="pie" onclick="switchChartType('${chartId}', 'pie')">🥧 دائري</button>
        <button class="btn-chart-type ${initialType === 'line' ? 'active' : ''}" data-type="line" onclick="switchChartType('${chartId}', 'line')">📈 خطي</button>
      </div>
    </div>
    <div style="height: 260px; position: relative; width: 100%;">
      <canvas id="${chartId}"></canvas>
    </div>
  `;

  anchorElement.parentNode.insertBefore(chartWrapper, anchorElement.nextSibling);

  renderedProjectCharts[chartId] = {
    title: title,
    labels: labels,
    values: values,
    currentType: initialType,
    instance: null
  };

  setTimeout(() => {
    renderOrUpdateCanvasChart(chartId, initialType);
  }, 60);
}

// =============================================================================
// رسم شجرة الأسانيد في نافذة التجربة التفاعلية (Playground)
// =============================================================================
function renderPlaygroundIsnadTree(layout = 'UD') {
  const container = document.getElementById('playgroundIsnadContainer');
  const inputEl = document.getElementById('playgroundIsnadInput');
  if (!container || !inputEl) return;

  let parsed = {};
  try {
    parsed = JSON.parse(inputEl.value);
  } catch (e) {
    showToast('صيغة بيانات JSON غير صحيحة', true);
    return;
  }

  if (window.vis && window.vis.Network) {
    const nodes = new vis.DataSet(parsed.nodes || []);
    const edges = new vis.DataSet(parsed.edges || []);
    const data = { nodes, edges };
    const isHierarchical = (layout === 'UD' || layout === 'DU');
    const options = {
      layout: {
        hierarchical: isHierarchical ? {
          direction: layout,
          sortMethod: 'directed',
          levelSeparation: 65,
          nodeSpacing: 110
        } : false
      },
      physics: !isHierarchical,
      nodes: {
        font: { face: 'Amiri, Tajawal, sans-serif', size: 13, color: '#ffffff' },
        borderWidth: 1.5,
        shadow: true,
        margin: 7
      },
      edges: {
        arrows: 'to',
        font: { face: 'Tajawal, sans-serif', size: 10, align: 'middle' },
        color: { color: '#b45309', highlight: '#d97706' },
        smooth: { type: 'cubicBezier' }
      }
    };
    new vis.Network(container, data, options);
  }
}

// =============================================================================
// مستخرج ورسام شجرة الأسانيد التلقائي من جداول ونصوص التقرير
// =============================================================================
function autoRenderProjectIsnadTrees(containerElement) {
  if (!containerElement || !window.vis || !window.vis.Network) return;

  // البحث في الجداول التي تحتوي على حقول أسانيد أو رواة
  const tables = containerElement.querySelectorAll('table');
  tables.forEach((table, idx) => {
    const nextElem = table.nextElementSibling;
    if (nextElem && (nextElem.classList.contains('isnad-render-wrapper') || nextElem.classList.contains('chart-render-wrapper'))) return;

    const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
    const isHadithTable = headers.some(h => /راوي|الراوي|الشيخ|السند|طريق|المدار|الصحابي|التابعي|الإسناد/i.test(h));
    if (!isHadithTable) return;

    const rows = Array.from(table.querySelectorAll('tbody tr'));
    if (rows.length < 2) return;

    const nodesMap = new Map();
    const edgesList = [];
    let prevNodeId = null;

    rows.forEach((r, rIdx) => {
      const cells = Array.from(r.querySelectorAll('td')).map(td => td.innerText.trim());
      const name = cells[1] || cells[0];
      const info = cells[2] || '';
      if (name && name.length > 2 && !/^\d+$/.test(name)) {
        const nodeId = rIdx + 1;
        const isMadar = /مدار|أصل/i.test(name) || /مدار/i.test(info);
        const isSahabi = /رضي الله عنه|صحابي/i.test(name) || /صحابي/i.test(info);

        nodesMap.set(nodeId, {
          id: nodeId,
          label: name.length > 25 ? name.substring(0, 23) + '..' : name,
          shape: isMadar ? 'box' : 'ellipse',
          color: isMadar ? '#b45309' : (isSahabi ? '#1e3a8a' : '#059669'),
          title: info || name
        });

        if (prevNodeId !== null) {
          edgesList.push({
            from: prevNodeId,
            to: nodeId,
            label: 'عن'
          });
        }
        prevNodeId = nodeId;
      }
    });

    if (nodesMap.size >= 2) {
      const isnadWrapper = document.createElement('div');
      isnadWrapper.className = 'isnad-render-wrapper';
      const treeId = `isnadTree_${idx}_${Date.now()}`;
      isnadWrapper.innerHTML = `
        <div class="isnad-render-header">
          <div class="isnad-render-title">
            <span>🌳</span>
            <span>شجرة الأسانيد وشبكة الرواة التفاعلية: ${escapeHtml(headers[1] || headers[0] || 'سلسلة الإسناد')}</span>
          </div>
          <div style="font-size: 12px; color: var(--text-muted);">أداة شجرة الأسانيد (Vis.js Network)</div>
        </div>
        <div id="${treeId}" class="isnad-canvas-container" style="height: 270px; width: 100%; border-radius: 6px; background: var(--bg-muted);"></div>
      `;

      table.parentNode.insertBefore(isnadWrapper, table.nextSibling);

      const treeContainer = document.getElementById(treeId);
      if (treeContainer) {
        const data = {
          nodes: new vis.DataSet(Array.from(nodesMap.values())),
          edges: new vis.DataSet(edgesList)
        };
        const options = {
          layout: {
            hierarchical: {
              direction: 'UD',
              sortMethod: 'directed',
              levelSeparation: 65,
              nodeSpacing: 100
            }
          },
          nodes: {
            font: { face: 'Amiri, Tajawal, sans-serif', size: 13, color: '#ffffff' },
            borderWidth: 1.5,
            margin: 6
          },
          edges: {
            arrows: 'to',
            font: { face: 'Tajawal, sans-serif', size: 10, align: 'middle' },
            color: '#b45309'
          }
        };
        new vis.Network(treeContainer, data, options);
      }
    }
  });
}

// =============================================================================
// مستخرج ورسام خرائط وتشجير Markmap التلقائي من كتل الماركداون والتقارير
// =============================================================================
function autoRenderProjectResultMarkmaps(containerElement) {
  if (!containerElement || !window.markmap || !window.markmap.Markmap) return;

  const codeBlocks = containerElement.querySelectorAll('pre code');
  codeBlocks.forEach((codeEl, idx) => {
    const rawText = codeEl.innerText.trim();
    const isMarkmap = codeEl.className.includes('markmap') || 
                      codeEl.className.includes('mindmap') ||
                      codeEl.className.includes('tree');

    const preEl = codeEl.closest('pre');
    if (!preEl || preEl.previousElementSibling?.classList.contains('markmap-render-wrapper')) return;

    if (isMarkmap) {
      const svgId = `projectMarkmap_${idx}_${Date.now()}`;
      const wrapper = document.createElement('div');
      wrapper.className = 'markmap-render-wrapper';
      wrapper.style.cssText = 'background: var(--bg-surface); padding: 18px; border-radius: 10px; border: 1px solid var(--border-subtle); margin: 24px 0; box-shadow: var(--shadow-sm);';
      wrapper.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 8px;">
          <div style="font-family: var(--font-amiri); font-size: 17px; font-weight: 700; color: var(--accent-clay); display: flex; align-items: center; gap: 8px;">
            <span>🌳</span>
            <span>الخريطة الذهنية والشجرة التفاعلية (Markmap)</span>
          </div>
          <div style="display: flex; gap: 6px;">
            <button type="button" class="btn-chart-type" onclick="window['markmapInstance_${svgId}']?.rescale(1.2)">🔍+ تكبير</button>
            <button type="button" class="btn-chart-type" onclick="window['markmapInstance_${svgId}']?.rescale(0.8)">🔍- تصغير</button>
            <button type="button" class="btn-chart-type" onclick="window['markmapInstance_${svgId}']?.fit()">⛶ ضبط</button>
          </div>
        </div>
        <div style="height: 380px; width: 100%; border: 1px solid var(--border-subtle); border-radius: 6px; background: var(--bg-muted); overflow: hidden; position: relative;">
          <svg id="${svgId}" style="width: 100%; height: 100%; display: block;"></svg>
        </div>
      `;

      preEl.parentNode.insertBefore(wrapper, preEl.nextSibling);
      preEl.style.display = 'none';

      try {
        const { Transformer, Markmap } = window.markmap;
        const transformer = new Transformer();
        const { root } = transformer.transform(rawText);
        const svg = document.getElementById(svgId);
        window[`markmapInstance_${svgId}`] = Markmap.create(svg, { autoFit: true, duration: 350 }, root);
      } catch (e) {
        console.error('Markmap render error:', e);
        preEl.style.display = 'block';
      }
    }
  });
}

// إتاحة الدوال على نطاق window
window.autoRenderProjectResultCharts = autoRenderProjectResultCharts;
window.switchChartType = switchChartType;
window.autoRenderProjectIsnadTrees = autoRenderProjectIsnadTrees;
window.autoRenderProjectResultMarkmaps = autoRenderProjectResultMarkmaps;
window.extractNumericValue = extractNumericValue;
window.fetchExtensionFromUrl = fetchExtensionFromUrl;
window.zoomTestMarkmap = zoomTestMarkmap;
window.fitTestMarkmap = fitTestMarkmap;
window.renderPlaygroundMarkmap = renderPlaygroundMarkmap;
window.zoomPlaygroundMarkmap = zoomPlaygroundMarkmap;
window.fitPlaygroundMarkmap = fitPlaygroundMarkmap;
window.exportSingleTool = exportSingleTool;
window.exportAllTools = exportAllTools;
window.exportCurrentModalTool = exportCurrentModalTool;
window.shareCurrentModalTool = shareCurrentModalTool;
window.handleImportToolFile = handleImportToolFile;
window.handleImportModalToolFile = handleImportModalToolFile;
window.autoDetectMockDataFromCode = autoDetectMockDataFromCode;
window.onPythonCodeInputChanged = onPythonCodeInputChanged;
