/**
 * محرك المشاريع البحثية التراثية (Heritage Research Projects Hub)
 * تخطيط وهندسة المشاريع، إدارة الوكلاء، المقارنات المرجعية، والتحقق المتقاطع
 */

const PROJECTS_STORAGE_KEY = 'almojtahed_research_projects';
let projectsList = [];
let activeProjectId = null;
let currentPlanningBlueprint = null;
let currentProjectRunData = null;
let isProjectHybridSearchEnabled = true;

// =============================================================================
// التحكم في نمط استرجاع نصوص المشروع: بحث هجين (Dense + BM25) أو دلالي صرف
// =============================================================================

function toggleProjectHybridSearchMode() {
  isProjectHybridSearchEnabled = !isProjectHybridSearchEnabled;
  if (activeProjectId) {
    const p = projectsList.find(item => item.id === activeProjectId);
    if (p) {
      p.use_hybrid = isProjectHybridSearchEnabled;
      saveCurrentProjectWorkspaceState();
    }
  }
  updateProjectHybridToggleUI();
  if (typeof showToast === 'function') {
    if (isProjectHybridSearchEnabled) {
      showToast('المشاريع البحثية: تم تفعيل استرجاع النصوص بالبحث الهجين (Dense + BM25) ⚡');
    } else {
      showToast('المشاريع البحثية: تم تفعيل استرجاع النصوص بالبحث الدلالي الصرف (Dense Only) 🧠');
    }
  }
}

function updateProjectHybridToggleUI() {
  const btn = document.getElementById('btnToggleProjectHybridSearch');
  const label = document.getElementById('labelProjectHybridToggle');
  const icon = document.getElementById('iconProjectHybridToggle');
  if (!btn || !label) return;

  if (isProjectHybridSearchEnabled) {
    btn.classList.add('is-active');
    btn.classList.remove('is-disabled');
    btn.setAttribute('aria-pressed', 'true');
    btn.title = 'البحث الهجين في المشروع مفعّل: استرجاع الشواهد التراثية بالدمج بين التضمين الدلالي والتطابق اللفظي BM25. انقر للتعطيل.';
    label.textContent = 'بحث هجين مفعّل (Dense + BM25)';
    if (icon) icon.setAttribute('data-lucide', 'layers');
  } else {
    btn.classList.remove('is-active');
    btn.classList.add('is-disabled');
    btn.setAttribute('aria-pressed', 'false');
    btn.title = 'البحث الدلالي الصرف في المشروع مفعّل: استرجاع الشواهد التراثية بنموذج المتجهات فقط. انقر لتفعيل البحث الهجين.';
    label.textContent = 'بحث دلالي صرف (Dense Only)';
    if (icon) icon.setAttribute('data-lucide', 'brain');
  }
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

// =============================================================================
// تهيئة تبويب المشاريع البحثية
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
  // يتم استدعاؤها أيضاً من app.js عند التبديل
  if (typeof initProjectsTab === 'function') {
    // ترك التحميل الأولي حسب الحاجة
  }
});

async function initProjectsTab() {
  await loadProjectsData();
  renderProjectsList();
  populateLinkedAgentGroupsDropdown();
  updateProjectHybridToggleUI();
  if (typeof loadToolsList === 'function') {
    loadToolsList();
  }
  if (window._openSharedProjectId) {
    const sharedId = window._openSharedProjectId;
    window._openSharedProjectId = '';
    openProjectWorkspace(sharedId);
  }
}

// تحميل المشاريع من الخادم أو التخزين المحلي
async function loadProjectsData() {
  await (window.almujtahedIdentity || Promise.resolve());
  try {
    const res = await fetch('/api/projects');
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) {
        projectsList = data;
        safeSaveProjectsLocalStorage();
        return;
      }
    }
  } catch (err) {
    console.warn('Could not fetch projects from server, falling back to localStorage:', err);
  }

  // في حال تعذر الخادم، القراءة من التخزين المحلي
  try {
    const raw = localStorage.getItem(ownerStorageKey(PROJECTS_STORAGE_KEY));
    if (raw) {
      projectsList = JSON.parse(raw);
    }
  } catch (e) {
    projectsList = [];
  }
}

// دالة مساعدة لحفظ كاش احتياطي خفيف في المتصفح دون كسر التنفيذ عند امتلاء السعة
function safeSaveProjectsLocalStorage() {
  try {
    // نجرد المشاريع من المخرجات الضخمة (execution_data) قبل حفظها ككاش احتياطي في المتصفح
    const lightList = projectsList.map(p => {
      const copy = { ...p };
      if (copy.execution_data) {
        copy.execution_data = {
          has_data: true,
          rounds_count: copy.execution_data.rounds ? copy.execution_data.rounds.length : 1,
          summary: (copy.execution_data.rawOutput || '').slice(0, 300)
        };
      }
      return copy;
    });
    localStorage.setItem(ownerStorageKey(PROJECTS_STORAGE_KEY), JSON.stringify(lightList));
  } catch (e) {
    console.warn('localStorage quota reached, backend server handles full storage safely:', e);
  }
}

// حفظ مشروع أو تحديثه في الخادم والتخزين المحلي
async function saveProjectToStorage(project) {
  if (!project.id) {
    project.id = 'proj_' + Date.now();
  }
  project.updated_at = new Date().toISOString().split('T')[0];

  const idx = projectsList.findIndex(p => p.id === project.id);
  if (idx >= 0) {
    projectsList[idx] = project;
  } else {
    projectsList.unshift(project);
  }

  // 1. الحفظ الأساسي القطعي على خادم بايثون (سعة القرص الصلب غير المحدودة)
  try {
    await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(project)
    });
  } catch (err) {
    console.warn('Backend sync error:', err);
  }

  // 2. كاش احتياطي خفيف فقط في المتصفح دون كسر التنفيذ عند الامتلاء
  safeSaveProjectsLocalStorage();
}

// =============================================================================
// عرض قائمة المشاريع البحثية
// =============================================================================

function renderProjectsList(filtered = null) {
  const grid = document.getElementById('projectsCardsGrid');
  const countBadge = document.getElementById('projectsCountBadge');
  if (!grid) return;

  const list = filtered || projectsList;
  if (countBadge) {
    countBadge.textContent = `${list.length} مشروع بحثي`;
  }

  if (list.length === 0) {
    grid.innerHTML = `
      <div class="projects-empty-state">
        <div class="empty-icon">📂</div>
        <h3>لا توجد مشاريع بحثية حالياً</h3>
        <p>ابدأ بهندسة مشروعك البحثي التراثي الأول بالنقر على «تخطيط وهندسة المشروع» لتوليد الخطة القياسية المتكاملة.</p>
        <button type="button" class="btn-primary-gradient" onclick="openProjectPlanningModal('new')">
          <span>تخطيط وهندسة المشروع</span>
        </button>
      </div>
    `;
    return;
  }

  grid.innerHTML = list.map(p => {
    const directorModel = p.director?.model ? p.director.model.split('/').pop() : 'Gemini 2.5';
    const subAgentsCount = p.subagents_group?.agents ? p.subagents_group.agents.length : 2;
    const hasInternal = p.internal_benchmark?.enabled !== false;
    const hasExternal = p.external_web_benchmark?.enabled !== false;
    const hasTool = p.computational_tool?.enabled !== false;

    return `
      <div class="project-card" onclick="openProjectWorkspace('${p.id}')">
        <div class="project-card-header">
          <div class="project-card-badge">${p.status || 'جاهز للتنفيذ'}</div>
          <div class="project-card-date">${p.created_at || '2026-10-16'}</div>
        </div>

        <h3 class="project-card-title">${escapeHtml(p.title || 'مشروع بحثي جديد')}</h3>
        <p class="project-card-desc">${escapeHtml(p.desc || 'لا يوجد وصف للمشروع')}</p>

        <div class="project-card-meta-chips">
          <span class="meta-chip" title="النموذج الموجه">🧠 ${directorModel}</span>
          <span class="meta-chip" title="الوكلاء المساعدون">👥 ${subAgentsCount} وكلاء بالشاملة</span>
          ${hasInternal ? '<span class="meta-chip" title="المقارنة المرجعية الداخلية">⚖️ مقارنة تراثية</span>' : ''}
          ${hasExternal ? '<span class="meta-chip" title="المقارنة المرجعية الخارجية">🌐 Tavily Web</span>' : ''}
          ${hasTool ? '<span class="meta-chip" title="أداة التحقق الحسابية">📐 تدقيق فلكي/حسابي</span>' : ''}
        </div>

        <div class="project-card-footer" onclick="event.stopPropagation()">
          <button type="button" class="btn-card-action primary" onclick="openProjectWorkspace('${p.id}')">
            <span>فتح مساحة العمل 📂</span>
          </button>
          <div style="display: flex; gap: 6px; align-items: center;">
            <button type="button" class="btn-card-action" data-share-kind="project" data-share-id="${escapeHtml(p.id)}" data-share-label="${escapeHtml(p.title || 'المشروع')}" title="مشاركة المشروع مع الأعضاء أو حفظه في الجهاز">
              <span>مشاركة</span>
            </button>
            <button type="button" class="btn-card-action danger" onclick="deleteProject('${p.id}', event)" title="حذف المشروع">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function filterProjectsList() {
  const query = (document.getElementById('projectsSearchFilterInput')?.value || '').trim().toLowerCase();
  if (!query) {
    renderProjectsList();
    return;
  }
  const filtered = projectsList.filter(p => {
    return (p.title || '').toLowerCase().includes(query) ||
      (p.desc || '').toLowerCase().includes(query) ||
      (p.director?.name || '').toLowerCase().includes(query);
  });
  renderProjectsList(filtered);
}

// =============================================================================
// مساحة عمل المشروع (Project Detail Workspace)
// =============================================================================

function openProjectWorkspace(projectId) {
  const project = projectsList.find(p => p.id === projectId);
  if (!project) return;

  activeProjectId = projectId;
  currentPlanningProjectId = projectId;

  // مزامنة وعزل استوديو المهندس مع هذا المشروع لمنع الخلط بين المشاريع
  architectHistory = project.architect_dialog ? [...project.architect_dialog] : (project.architect_history ? [...project.architect_history] : []);
  currentStudioBlueprint = project.blueprint || null;

  // إخفاء القائمة وإظهار مساحة العمل
  const listWrapper = document.getElementById('projectsListViewWrapper');
  const wsWrapper = document.getElementById('projectDetailWorkspaceWrapper');
  if (listWrapper) listWrapper.style.display = 'none';
  if (wsWrapper) wsWrapper.style.display = 'flex';

  // تعبئة الترويسة
  const titleEl = document.getElementById('currentProjectTitle');
  const descEl = document.getElementById('currentProjectDesc');
  if (titleEl) titleEl.textContent = project.title || 'مشروع بحثي';
  if (descEl) descEl.textContent = project.desc || '';

  // 1. بطاقة المدير
  setValue('pDirectorName', project.director?.name || 'مدير المشروع');
  const dModel = project.director?.model || 'google/gemini-2.5-flash';
  setValue('pDirectorModel', dModel);
  populateOpenRouterModelDropdown(document.getElementById('pDirectorModel'), dModel);
  setValue('pDirectorThinking', project.director?.thinking || 'medium');
  setValue('pDirectorMaxTokens', project.director?.max_tokens || 262144);
  setValue('pDirectorPrompt', project.director?.system_prompt || '');

  // 2. بطاقة الوكلاء المساعدين وسعة الاستخراج والمراسي
  populateLinkedAgentGroupsDropdown(project.linked_group_id);
  renderSubagentsPreviewList(project.subagents_group?.agents || []);
  setValue('pExtractionCapacity', project.extraction_capacity || 150);
  const capLabel = document.getElementById('pExtractionCapacityLabel');
  if (capLabel) capLabel.textContent = (project.extraction_capacity || 150) + ' مقطعاً';
  setValue('pRetrievalAnchors', (project.retrieval_anchors || []).join('\n'));

  // نمط توزيع واستدعاء الوكلاء المساعدين (متوازي vs مباشر)
  const isDirectMode = project.agent_dispatch_mode === 'direct';
  const pDirectRadio = document.getElementById('pDispatchModeDirect');
  const pParallelRadio = document.getElementById('pDispatchModeParallel');
  if (isDirectMode && pDirectRadio) {
    pDirectRadio.checked = true;
  } else if (pParallelRadio) {
    pParallelRadio.checked = true;
  }
  if (typeof updateProjectDispatchModeUI === 'function') {
    updateProjectDispatchModeUI();
  }

  // ضبط حالة البحث الهجين للمشروع
  isProjectHybridSearchEnabled = (project.use_hybrid !== undefined) ? !!project.use_hybrid : true;
  updateProjectHybridToggleUI();

  // 3. المقارنة المرجعية الداخلية
  setCheckbox('pInternalBenchEnabled', project.internal_benchmark?.enabled !== false);
  setValue('pBenchTitle', project.internal_benchmark?.title || '');
  setValue('pBenchAuthor', project.internal_benchmark?.author || '');
  setValue('pBenchMethodology', project.internal_benchmark?.methodology || '');
  toggleComponentCard(document.getElementById('pInternalBenchEnabled'), 'cardInternalBench');

  // 4. المقارنة المرجعية الخارجية
  setCheckbox('pExternalBenchEnabled', project.external_web_benchmark?.enabled !== false);
  setValue('pExternalQuery', project.external_web_benchmark?.query || '');
  setValue('pExternalDomains', (project.external_web_benchmark?.domains || []).join(', '));
  setValue('pExternalPrompt', project.external_web_benchmark?.prompt || '');
  toggleComponentCard(document.getElementById('pExternalBenchEnabled'), 'cardExternalBench');

  // 5. أداة التحقق
  setCheckbox('pCompToolEnabled', project.computational_tool?.enabled !== false);
  setValue('pCompToolType', project.computational_tool?.tool_type || 'web_nasa_catalog');
  setValue('pCompToolDesc', project.computational_tool?.desc || '');
  toggleComponentCard(document.getElementById('pCompToolEnabled'), 'cardCompTool');

  // 6. المخرجات
  setCheckbox('pOutCsvResults', project.output_formats?.csv_results !== false);
  setCheckbox('pOutCsvBenchmark', project.output_formats?.csv_benchmark !== false);
  setCheckbox('pOutFormattedTxt', project.output_formats?.formatted_txt !== false);
  setCheckbox('pOutHtml', project.output_formats?.interactive_html !== false);
  setCheckbox('pOutPdf', project.output_formats?.academic_pdf !== false);

  // استرجاع نتائج التشغيل والجولات السابقة إن وُجدت
  const runResults = document.getElementById('projectRunResultsContainer');
  if (project.execution_data && (project.execution_data.rawOutput || (project.execution_data.rounds && project.execution_data.rounds.length > 0))) {
    currentProjectRunData = project.execution_data;
    renderProjectExecutionView();
  } else {
    currentProjectRunData = null;
    if (runResults) runResults.style.display = 'none';
  }

  // تحديث الشارات الملخصة وطي الكروت تلقائياً لتكون مساحة العمل مرتبة ومريحة
  updateCardQuickSummaries(project);
  collapseAllProjectCards();

  // التمرير لأعلى الصفحة بنعومة
  wsWrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function closeProjectWorkspace() {
  saveCurrentProjectWorkspaceState();
  activeProjectId = null;
  currentPlanningProjectId = null;
  architectHistory = [];
  currentStudioBlueprint = null;

  const listWrapper = document.getElementById('projectsListViewWrapper');
  const wsWrapper = document.getElementById('projectDetailWorkspaceWrapper');
  if (listWrapper) listWrapper.style.display = 'block';
  if (wsWrapper) wsWrapper.style.display = 'none';

  renderProjectsList();
}

function saveCurrentProjectWorkspaceState() {
  if (!activeProjectId) return;
  const p = projectsList.find(item => item.id === activeProjectId);
  if (!p) return;

  p.director = {
    name: getValue('pDirectorName'),
    model: getValue('pDirectorModel'),
    thinking: getValue('pDirectorThinking'),
    max_tokens: parseInt(getValue('pDirectorMaxTokens') || '262144', 10),
    system_prompt: getValue('pDirectorPrompt')
  };

  p.linked_group_id = getValue('pLinkedAgentGroupSelect');
  p.extraction_capacity = parseInt(getValue('pExtractionCapacity') || '150', 10);
  p.retrieval_anchors = (getValue('pRetrievalAnchors') || '')
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean);

  const directRadio = document.getElementById('pDispatchModeDirect');
  p.agent_dispatch_mode = (directRadio && directRadio.checked) ? 'direct' : 'parallel';
  p.use_hybrid = isProjectHybridSearchEnabled;

  p.internal_benchmark = {
    enabled: getCheckbox('pInternalBenchEnabled'),
    title: getValue('pBenchTitle'),
    author: getValue('pBenchAuthor'),
    methodology: getValue('pBenchMethodology')
  };

  const domainsStr = getValue('pExternalDomains');
  p.external_web_benchmark = {
    enabled: getCheckbox('pExternalBenchEnabled'),
    query: getValue('pExternalQuery'),
    domains: domainsStr.split(',').map(d => d.trim()).filter(Boolean),
    prompt: getValue('pExternalPrompt')
  };

  p.computational_tool = {
    enabled: getCheckbox('pCompToolEnabled'),
    tool_type: getValue('pCompToolType'),
    desc: getValue('pCompToolDesc')
  };

  p.output_formats = {
    csv_results: getCheckbox('pOutCsvResults'),
    csv_benchmark: getCheckbox('pOutCsvBenchmark'),
    formatted_txt: getCheckbox('pOutFormattedTxt'),
    interactive_html: getCheckbox('pOutHtml'),
    academic_pdf: getCheckbox('pOutPdf')
  };

  // حفظ مجموعة الوكلاء المربوطة بشكل دائم داخل كائن المشروع
  if (p.linked_group_id && window.agentGroups) {
    const grp = window.agentGroups.find(g => g.id === p.linked_group_id);
    if (grp) {
      p.subagents_group = {
        id: grp.id,
        name: grp.name,
        desc: grp.desc,
        agents: grp.agents
      };
    }
  }

  // حفظ سجل محادثة المهندس ونموذجه المختار فقط إذا كانت المحادثة تخص هذا المشروع حصراً
  if (currentPlanningProjectId === p.id && architectHistory && architectHistory.length > 0) {
    p.architect_dialog = [...architectHistory];
    p.architect_history = [...architectHistory];
  }
  if (currentPlanningProjectId === p.id && currentStudioBlueprint) {
    p.blueprint = currentStudioBlueprint;
  }
  const selModel = document.getElementById('architectModelSelect')?.value;
  if (selModel && currentPlanningProjectId === p.id) {
    p.architect_model = selModel;
    p.architect_thinking = document.getElementById('architectThinkingSelect')?.value || p.architect_thinking || 'medium';
  }

  saveProjectToStorage(p);
}

function manualSaveProjectWorkspace() {
  saveCurrentProjectWorkspaceState();
  if (typeof showToast === 'function') {
    showToast('💾 تم حفظ كافة إعدادات وبطاقات ومكونات المشروع بنجاح!');
  }
}

// =============================================================================
// طي وفرد بطاقات المشروع البحثي (Accordion / Card Collapsible)
// =============================================================================
function toggleProjectCard(cardId, event) {
  if (event && (event.target.tagName === 'INPUT' || event.target.closest('.switch-toggle') || event.target.closest('.p-toggle-switch'))) {
    return;
  }
  const card = document.getElementById(cardId);
  if (card) {
    card.classList.toggle('collapsed');
  }
}

function collapseAllProjectCards() {
  document.querySelectorAll('.project-component-card').forEach(card => {
    card.classList.add('collapsed');
  });
}

function expandAllProjectCards() {
  document.querySelectorAll('.project-component-card').forEach(card => {
    card.classList.remove('collapsed');
  });
}

function updateCardQuickSummaries(project) {
  if (!project) return;
  const dSummary = document.getElementById('pDirectorQuickSummary');
  if (dSummary) {
    const m = project.director?.model || 'Gemini 2.5';
    const name = m.split('/').pop().replace('gemini-', 'Gemini ').replace('claude-', 'Claude ');
    dSummary.textContent = `🧠 ${name}`;
  }

  const sSummary = document.getElementById('pSubAgentsQuickSummary');
  if (sSummary) {
    const count = (project.subagents_group?.agents || []).length || 2;
    const cap = project.extraction_capacity || 150;
    sSummary.textContent = `👥 ${count} وكلاء • ${cap} نص`;
  }

  const iSummary = document.getElementById('pInternalQuickSummary');
  if (iSummary) {
    const isEn = project.internal_benchmark?.enabled !== false;
    iSummary.textContent = isEn ? `⚖️ ${project.internal_benchmark?.title || 'مقارنة تراثية'}` : '⚖️ معطلة';
  }

  const eSummary = document.getElementById('pExternalQuickSummary');
  if (eSummary) {
    const isEn = project.external_web_benchmark?.enabled !== false;
    eSummary.textContent = isEn ? '🌐 Tavily Web' : '🌐 معطلة';
  }

  const tSummary = document.getElementById('pToolQuickSummary');
  if (tSummary) {
    const isEn = project.computational_tool?.enabled !== false;
    const tType = project.computational_tool?.tool_type || 'none';
    let tLabel = 'أداة مساعدة';
    if (tType === 'charts_metrics') tLabel = '📊 المؤشرات والشارتات';
    else if (tType === 'astronomy_hijri_sync') tLabel = '📐 تدقيق فلكي وتقويمي';
    else if (tType === 'hadith_isnad_tree') tLabel = '🌳 شجرة الأسانيد';
    else if (tType === 'none') tLabel = 'بدون أداة مساعدة';
    tSummary.textContent = isEn ? tLabel : '📐 معطلة';
  }
}

function toggleComponentCard(checkbox, cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;
  const isEnabled = checkbox ? checkbox.checked : true;
  card.classList.toggle('component-disabled', !isEnabled);
}

// تعبئة القائمة المنسدلة للمجموعات المتاحة
function populateLinkedAgentGroupsDropdown(selectedGroupId = null) {
  const select = document.getElementById('pLinkedAgentGroupSelect');
  if (!select) return;

  let groups = window.agentGroups || [];
  if (groups.length === 0) {
    try {
      const raw = localStorage.getItem(ownerStorageKey('almojtahed_agent_groups'));
      if (raw) groups = JSON.parse(raw);
    } catch (e) { }
  }

  if (groups.length === 0) {
    select.innerHTML = '<option value="">لا توجد مجموعات وكلاء معرفة</option>';
    return;
  }

  select.innerHTML = groups.map(g => {
    const isSel = (g.id === selectedGroupId) ? 'selected' : '';
    const count = g.agents ? g.agents.length : 0;
    return `<option value="${g.id}" ${isSel}>${escapeHtml(g.name)} (${count} وكلاء)</option>`;
  }).join('');

  if (!selectedGroupId && groups.length > 0) {
    select.value = groups[0].id;
    syncProjectLinkedGroup(groups[0].id);
  }
}

function syncProjectLinkedGroup(groupId) {
  let groups = window.agentGroups || [];
  if (groups.length === 0) {
    try {
      groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
    } catch (e) { }
  }

  const group = groups.find(g => g.id === groupId);
  if (group && group.agents) {
    renderSubagentsPreviewList(group.agents);
    const badge = document.getElementById('pLinkedAgentsCountBadge');
    if (badge) badge.textContent = `${group.agents.length} وكلاء مرتبطون`;

    // تحديث في المشروع الحالي
    if (activeProjectId) {
      const p = projectsList.find(x => x.id === activeProjectId);
      if (p) {
        p.linked_group_id = groupId;
        p.subagents_group = {
          name: group.name,
          desc: group.desc,
          agents: group.agents
        };
      }
    }
  }
}

// قائمة النماذج الموصى بها للوكلاء
function projectSuggestedModels() {
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

let projectSubagentAllModels = [];
let projectSubagentSelectedModel = 'google/gemini-2.5-flash';

function renderSubagentsPreviewList(agents) {
  const listEl = document.getElementById('pSubagentsPreviewList');
  if (!listEl) return;

  if (!agents || agents.length === 0) {
    listEl.innerHTML = `
      <div style="color: var(--text-muted); font-size: 13px; padding: 14px; text-align: center; border: 1px dashed var(--border-subtle); border-radius: 6px; background: var(--bg-surface);">
        لا يوجد وكلاء في هذا المشروع حالياً. انقر على «➕ إضافة وكيل استخراج جديد للمشروع» أعلاه لإضافة وكيل.
      </div>
    `;
    return;
  }

  listEl.innerHTML = agents.map((a, idx) => {
    const books = (a.booksScope && Array.isArray(a.booksScope)) ? a.booksScope : (a.books && Array.isArray(a.books)) ? a.books : [];
    const promptText = a.systemPrompt || a.system_prompt || a.directive || a.desc || '';
    const isEnabled = a.enabled !== false && a.active !== false;
    const modelId = a.model || 'google/gemini-2.5-flash';
    const temp = (a.temperature !== undefined) ? a.temperature : (a.temp !== undefined ? a.temp : 0.2);
    const topK = a.top_k || a.topK || 150;
    const freqPen = (a.frequency_penalty !== undefined) ? a.frequency_penalty : 0;
    const roleText = a.desc || a.role || '';

    return `
      <div class="subagent-preview-item" style="padding: 12px 14px; margin-bottom: 10px; border-radius: 8px; background: var(--bg-surface); border: 1px solid var(--border-subtle); box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <!-- ترويسة بطاقة الوكيل -->
        <div class="subagent-p-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px;">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <strong style="font-size: 13.5px; color: var(--text-main); font-weight: 700;">${idx + 1}. ${escapeHtml(a.name || 'وكيل استخراج')}</strong>
            <span style="font-size: 11px; background: ${isEnabled ? 'rgba(5, 150, 105, 0.1)' : 'rgba(239, 68, 68, 0.1)'}; color: ${isEnabled ? '#059669' : '#dc2626'}; border: 1px solid ${isEnabled ? 'rgba(5, 150, 105, 0.25)' : 'rgba(239, 68, 68, 0.25)'}; padding: 1px 7px; border-radius: 4px; font-weight: 600;">
              ${isEnabled ? '✅ مفعل للبحث' : '⚠️ معطل'}
            </span>
            ${roleText ? `<span style="font-size: 11px; color: var(--text-muted); background: var(--bg-canvas); padding: 1px 6px; border-radius: 4px; border: 1px solid var(--border-subtle);">${escapeHtml(roleText)}</span>` : ''}
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <span style="font-size: 11px; background: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.25); color: #2563eb; padding: 2px 7px; border-radius: 4px; font-weight: 600;">
              🤖 ${escapeHtml(modelId.split('/').pop())}
            </span>
            <span class="subagent-p-pool" style="font-size: 11px; background: rgba(180, 83, 9, 0.09); border: 1px solid rgba(180, 83, 9, 0.25); color: var(--accent-clay); padding: 2px 7px; border-radius: 4px; font-weight: 600;">
              مسح: ${topK} نص
            </span>
          </div>
        </div>

        <!-- التوجيه التخصصي للوكيل -->
        <div style="font-size: 12px; color: var(--text-light); background: var(--bg-canvas); padding: 7px 10px; border-radius: 6px; border: 1px dashed var(--border-subtle); margin: 6px 0; line-height: 1.5; font-family: var(--font-amiri);">
          <strong style="color: var(--accent-clay);">💬 التوجيه:</strong> ${escapeHtml(promptText || 'استخراج نصوص المسألة بدقة مع أرقام الأجزاء والصفحات.')}
        </div>

        <!-- شريط معلمات النموذج الدقيقة -->
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; font-size: 11px; color: var(--text-muted);">
          <span>⚙️ معلمات النموذج:</span>
          <span style="background: var(--bg-canvas); border: 1px solid var(--border-subtle); padding: 1px 6px; border-radius: 4px;">🌡️ حرارة: <strong>${temp}</strong></span>
          <span style="background: var(--bg-canvas); border: 1px solid var(--border-subtle); padding: 1px 6px; border-radius: 4px;">🎯 Top-P: <strong>${a.top_p ?? 0.9}</strong></span>
          <span style="background: var(--bg-canvas); border: 1px solid var(--border-subtle); padding: 1px 6px; border-radius: 4px;">🚫 عقوبة: <strong>${freqPen}</strong></span>
          <span style="background: var(--bg-canvas); border: 1px solid var(--border-subtle); padding: 1px 6px; border-radius: 4px;">📏 Max Tokens: <strong>${a.max_tokens || 4096}</strong></span>
        </div>

        <!-- نطاق الكتب المحققة والمحددة من المهندس -->
        <div class="subagent-p-scope" style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="color: #2563eb;">📚 نطاق الكتب (${books.length}):</strong>
            <button type="button" class="btn-secondary" onclick="openProjectSubagentScopePickerFromCard(${idx})" style="font-size: 11px; padding: 2px 8px; color: #2563eb; border-color: rgba(37,99,235,0.3); border-radius: 4px;">
              🔍 تحديد من كتب الشاملة
            </button>
          </div>
          ${books.length > 0 ? `
            <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;">
              ${books.map(b => `<span style="background: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.2); color: var(--text-main); padding: 2px 7px; border-radius: 4px; font-size: 11px;">📖 ${escapeHtml(b)}</span>`).join('')}
            </div>
          ` : '<span style="color: var(--text-muted); font-size: 11.5px; display: block; margin-top: 2px;"> كامل أمهات مصادر الشاملة (8,589 كتاباً)</span>'}
        </div>

        <!-- أزرار الإجراءات والتحكم الكامل بالوكيل -->
        <div style="display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border-subtle);">
          <button type="button" class="btn-secondary" onclick="openProjectSubagentConfigModal(${idx}, true)" style="font-size: 11.5px; padding: 4px 10px; color: var(--accent-clay); border-color: rgba(180, 83, 9, 0.3); display: inline-flex; align-items: center; gap: 4px;" title="تجربة استجابة الوكيل والنموذج حياً">
            🧪 تجربة حية
          </button>
          <button type="button" class="btn-primary" onclick="openProjectSubagentConfigModal(${idx}, false)" style="font-size: 11.5px; padding: 4px 12px; display: inline-flex; align-items: center; gap: 4px; font-weight: 600;">
            ⚙️ تعديل وضبط الوكيل
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// =============================================================================
// إدارة وضبط الوكلاء المساعدين من داخل المشروع البحثي (Subagents Studio Manager)
// =============================================================================

function getOrResolveActiveProject() {
  if (!activeProjectId) {
    if (typeof currentPlanningProjectId !== 'undefined' && currentPlanningProjectId) {
      activeProjectId = currentPlanningProjectId;
    } else if (projectsList && projectsList.length > 0) {
      activeProjectId = projectsList[0].id;
    }
  }
  let project = activeProjectId ? projectsList.find(p => p.id === activeProjectId) : null;
  if (!project && projectsList && projectsList.length > 0) {
    project = projectsList[0];
    activeProjectId = project.id;
  }
  if (!project) {
    // إنشاء كائن مشروع مؤقت إذا لم يكن هناك أي مشروع بعد
    project = {
      id: 'proj_' + Date.now(),
      title: 'مشروع بحثي جديد',
      subagents_group: { agents: [] }
    };
    projectsList.push(project);
    activeProjectId = project.id;
  }
  return project;
}

async function openProjectSubagentConfigModal(agentIdx, focusTest = false) {
  try {
    const project = getOrResolveActiveProject();
    if (!project) {
      if (typeof showToast === 'function') showToast('يرجى تحديد أو فتح مشروع أولاً', true);
      return;
    }

    let agents = project.subagents_group?.agents;
    if (!agents || agents.length === 0) {
      if (project.linked_group_id) {
        let groups = window.agentGroups || [];
        if (groups.length === 0) {
          try { groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]'); } catch (e) { }
        }
        const grp = groups.find(g => g.id === project.linked_group_id);
        if (grp && grp.agents) {
          agents = grp.agents;
          if (!project.subagents_group) {
            project.subagents_group = { name: grp.name, desc: grp.desc, agents: grp.agents };
          } else {
            project.subagents_group.agents = grp.agents;
          }
        }
      }
    }
    if (!agents) agents = [];

    const modal = document.getElementById('projectSubagentConfigModal');
    if (!modal) {
      console.error('Modal #projectSubagentConfigModal not found in DOM!');
      return;
    }

    window._activeProjectSubagentIdx = agentIdx;

    let agent = agents[agentIdx];
    if (!agent) {
      // وكيل جديد
      agent = {
        id: `agent_${Date.now()}`,
        name: `وكيل استخراج ${(parseInt(agentIdx) || 0) + 1}`,
        desc: 'استخراج نصوص الشاملة وتحقيق المسألة',
        role: 'استخراج نصوص الشاملة وتحقيق المسألة',
        model: 'google/gemini-2.5-flash',
        systemPrompt: 'استخرج نصوص المسألة بدقة مع أرقام الأجزاء والصفحات والمذاهب والأدلة.',
        booksScope: [],
        top_k: 150,
        temperature: 0.2,
        top_p: 0.9,
        frequency_penalty: 0.0,
        presence_penalty: 0.0,
        repetition_penalty: 1.0,
        max_tokens: 4096,
        enabled: true
      };
    }

    // تعبئة البيانات في النافذة
    const editIdxEl = document.getElementById('pSubagentEditIndex');
    if (editIdxEl) editIdxEl.value = agentIdx;
    const titleEl = document.getElementById('pSubagentModalTitle');
    if (titleEl) titleEl.textContent = `إعداد وضبط: «${agent.name || 'الوكيل المساعد'}»`;
    const nameEl = document.getElementById('pSubagentName');
    if (nameEl) nameEl.value = agent.name || '';
    const roleEl = document.getElementById('pSubagentRole');
    if (roleEl) roleEl.value = agent.desc || agent.role || '';
    const enEl = document.getElementById('pSubagentEnabled');
    if (enEl) enEl.value = String(agent.enabled !== false && agent.active !== false);
    const dirEl = document.getElementById('pSubagentDirective');
    if (dirEl) dirEl.value = agent.systemPrompt || agent.system_prompt || agent.directive || agent.desc || '';

    // سعة النصوص الممسوحة
    const scanned = agent.top_k || agent.topK || 150;
    syncSubagentScannedInput(scanned);

    // معلمات النموذج
    const currentModel = agent.model || 'google/gemini-2.5-flash';
    projectSubagentSelectedModel = currentModel;

    // عرض الخيارات الموصى بها فوراً في القائمة المنسدلة بدون انتظار للشبكة
    renderProjectSubagentModelsOptions('', currentModel);

    // تحميل وتحديث نماذج OpenRouter الإضافية في الخلفية دون تعطيل
    populateProjectSubagentModelsDropdown(currentModel).catch(e => console.warn(e));

    const temp = (agent.temperature !== undefined) ? agent.temperature : (agent.temp !== undefined ? agent.temp : 0.2);
    syncSubagentTemp(temp);

    const topP = (agent.top_p !== undefined) ? agent.top_p : (agent.topP !== undefined ? agent.topP : 0.9);
    syncSubagentTopP(topP);

    const freqPen = (agent.frequency_penalty !== undefined) ? agent.frequency_penalty : 0;
    syncSubagentFreqPen(freqPen);

    const presPen = (agent.presence_penalty !== undefined) ? agent.presence_penalty : 0;
    syncSubagentPresPen(presPen);

    const topKEl = document.getElementById('pSubagentModelTopKInput');
    if (topKEl) topKEl.value = agent.model_top_k || agent.modelTopK || '';
    const maxTokensEl = document.getElementById('pSubagentMaxTokensInput');
    if (maxTokensEl) maxTokensEl.value = agent.max_tokens || agent.maxTokens || 4096;

    // نطاق كتب الشاملة
    const books = (agent.booksScope && Array.isArray(agent.booksScope)) ? agent.booksScope : (agent.books && Array.isArray(agent.books)) ? agent.books : [];
    window._activeProjectSubagentBooks = [...books];
    renderProjectSubagentBooksChips();

    // مزامنة بطاقة سياق التجربة الحية مع التوجيه ونمط بحث المشروع والكتب
    syncSubagentTestContextUI();

    // تصفير التجربة الحية
    const testStatus = document.getElementById('pSubagentTestStatus');
    if (testStatus) testStatus.textContent = '';
    const resultBox = document.getElementById('pSubagentTestResultBox');
    if (resultBox) {
      resultBox.style.display = 'none';
      resultBox.innerHTML = '';
    }

    // فتح النافذة فوراً
    modal.style.display = 'flex';
    modal.classList.add('open');

    if (focusTest) {
      setTimeout(() => {
        const testInput = document.getElementById('pSubagentTestInput');
        const testSection = testInput?.closest('.form-group') || testInput;
        if (testSection) {
          testSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        if (testInput) {
          testInput.focus();
        }
      }, 100);
    }
  } catch (err) {
    console.error('Error in openProjectSubagentConfigModal:', err);
    if (typeof showToast === 'function') {
      showToast('خطأ أثناء فتح نافذة إعداد الوكيل: ' + (err.message || err), true);
    }
  }
}

function closeProjectSubagentConfigModal() {
  const modal = document.getElementById('projectSubagentConfigModal');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('open');
  }
}

function handleProjectSubagentModalOverlay(event) {
  if (event.target && event.target.id === 'projectSubagentConfigModal') {
    closeProjectSubagentConfigModal();
  }
}

// مزامنة حقول مسح النصوص
function syncSubagentScannedInput(val) {
  const num = parseInt(val) || 150;
  const range = document.getElementById('pSubagentScannedRange');
  const input = document.getElementById('pSubagentScannedInput');
  const badge = document.getElementById('pSubagentScannedBadge');
  if (range) range.value = num;
  if (input) input.value = num;
  if (badge) badge.textContent = `${num} نصاً`;
}

function syncSubagentScannedRange(val) {
  syncSubagentScannedInput(val);
}

// مزامنة معلمات النموذج
function syncSubagentTemp(val) {
  const num = parseFloat(val);
  const formatted = isNaN(num) ? '0.20' : num.toFixed(2);
  const range = document.getElementById('pSubagentTempRange');
  const input = document.getElementById('pSubagentTempInput');
  const badge = document.getElementById('pSubagentTempValBadge');
  if (range) range.value = formatted;
  if (input) input.value = formatted;
  if (badge) badge.textContent = formatted;
}

function syncSubagentTopP(val) {
  const num = parseFloat(val);
  const formatted = isNaN(num) ? '0.90' : num.toFixed(2);
  const range = document.getElementById('pSubagentTopPRange');
  const input = document.getElementById('pSubagentTopPInput');
  const badge = document.getElementById('pSubagentTopPValBadge');
  if (range) range.value = formatted;
  if (input) input.value = formatted;
  if (badge) badge.textContent = formatted;
}

function syncSubagentFreqPen(val) {
  const num = parseFloat(val);
  const formatted = isNaN(num) ? '0.00' : num.toFixed(2);
  const range = document.getElementById('pSubagentFreqPenRange');
  const input = document.getElementById('pSubagentFreqPenInput');
  const badge = document.getElementById('pSubagentFreqPenValBadge');
  if (range) range.value = formatted;
  if (input) input.value = formatted;
  if (badge) badge.textContent = formatted;
}

function syncSubagentPresPen(val) {
  const num = parseFloat(val);
  const formatted = isNaN(num) ? '0.00' : num.toFixed(2);
  const range = document.getElementById('pSubagentPresPenRange');
  const input = document.getElementById('pSubagentPresPenInput');
  const badge = document.getElementById('pSubagentPresPenValBadge');
  if (range) range.value = formatted;
  if (input) input.value = formatted;
  if (badge) badge.textContent = formatted;
}

// تعبئة القائمة المنسدلة للنماذج مع الفلترة
async function populateProjectSubagentModelsDropdown(preferredModel = null, filterQuery = '') {
  if (preferredModel) {
    projectSubagentSelectedModel = preferredModel;
  }
  const countBadge = document.getElementById('pSubagentModelCountBadge');

  if (window.openrouterModelsList && window.openrouterModelsList.length > 0) {
    projectSubagentAllModels = window.openrouterModelsList;
  } else {
    try {
      if (countBadge) countBadge.textContent = 'جارٍ فحص النماذج... ⏳';
      let savedKeys = {};
      try { savedKeys = readProviderKeys(); } catch (e) { }
      const apiKey = savedKeys.openrouter || '';
      const url = `/api/openrouter/models${apiKey ? '?api_key=' + encodeURIComponent(apiKey) : ''}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        projectSubagentAllModels = data.models || [];
        window.openrouterModelsList = projectSubagentAllModels;
      }
    } catch (e) {
      console.warn('Could not fetch OpenRouter models:', e);
    }
  }

  const filterInput = document.getElementById('pSubagentModelFilterInput');
  const q = (filterQuery !== undefined && filterQuery !== null && filterQuery !== '') ? filterQuery : (filterInput ? filterInput.value : '');
  renderProjectSubagentModelsOptions(q, projectSubagentSelectedModel);
}

function renderProjectSubagentModelsOptions(filterQuery = '', selectedVal = null) {
  const selectEl = document.getElementById('pSubagentModelSelect');
  const countBadge = document.getElementById('pSubagentModelCountBadge');
  const clearBtn = document.getElementById('pSubagentModelClearFilterBtn');
  if (!selectEl) return;

  const currentVal = selectedVal || selectEl.value || projectSubagentSelectedModel || 'google/gemini-2.5-flash';
  const q = (filterQuery || '').trim().toLowerCase();

  if (clearBtn) {
    clearBtn.style.display = q ? 'block' : 'none';
  }

  const topIds = new Set(projectSuggestedModels().map(m => m.id));
  const otherModels = (projectSubagentAllModels || []).filter(m => !topIds.has(m.id));
  otherModels.sort((a, b) => (a.name || a.id).localeCompare(b.name || b.id));

  let matchedTop = projectSuggestedModels();
  let matchedOthers = otherModels;

  if (q) {
    matchedTop = projectSuggestedModels().filter(m =>
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
      countBadge.textContent = `${totalMatched} نموذج مطابق للفلترة`;
    } else {
      countBadge.textContent = `${totalMatched} نموذج متاح عبر OpenRouter`;
    }
  }

  let html = '';
  const inTop = matchedTop.some(m => m.id === currentVal);
  const inOthers = matchedOthers.some(m => m.id === currentVal);

  if (!inTop && !inOthers && currentVal) {
    html += `<option value="${escapeHtml(currentVal)}" selected>${escapeHtml(currentVal)} (النموذج المحدد حالياً)</option>`;
  }

  if (matchedTop.length > 0) {
    const topOptions = matchedTop.map(m =>
      `<option value="${escapeHtml(m.id)}" ${m.id === currentVal ? 'selected' : ''}>${escapeHtml(m.name)}</option>`
    ).join('');
    html += `<optgroup label="⭐ النماذج المقترحة">${topOptions}</optgroup>`;
  }

  if (matchedOthers.length > 0) {
    const otherOptions = matchedOthers.map(m => {
      const label = m.name ? `${m.name} (${m.id})` : m.id;
      return `<option value="${escapeHtml(m.id)}" ${m.id === currentVal ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    }).join('');
    html += `<optgroup label="🌐 كافة نماذج OpenRouter (${matchedOthers.length} نموذج)">${otherOptions}</optgroup>`;
  }

  if (totalMatched === 0 && !html) {
    html = `<option value="" disabled selected>لا توجد نماذج مطابقة للبحث «${escapeHtml(q)}»</option>`;
  }

  selectEl.innerHTML = html;
  if (inTop || inOthers) {
    selectEl.value = currentVal;
    projectSubagentSelectedModel = currentVal;
  }
}

function filterProjectSubagentModels(query) {
  renderProjectSubagentModelsOptions(query, document.getElementById('pSubagentModelSelect')?.value);
}

function clearProjectSubagentModelFilter() {
  const input = document.getElementById('pSubagentModelFilterInput');
  if (input) {
    input.value = '';
    input.focus();
  }
  renderProjectSubagentModelsOptions('', document.getElementById('pSubagentModelSelect')?.value);
}

function onProjectSubagentModelChanged(val) {
  if (val) {
    projectSubagentSelectedModel = val;
  }
}

// عرض وإدارة بطاقات نطاق كتب الشاملة للوكيل
function renderProjectSubagentBooksChips() {
  const listEl = document.getElementById('pSubagentBooksChipsList');
  const countBadge = document.getElementById('pSubagentBooksCountBadge');
  if (!listEl) return;

  const books = window._activeProjectSubagentBooks || [];

  if (countBadge) {
    if (books.length === 0) {
      countBadge.textContent = 'كامل الشاملة (8,589 كتاباً)';
      countBadge.style.color = '#2563eb';
      countBadge.style.background = 'rgba(37, 99, 235, 0.1)';
    } else {
      countBadge.textContent = `مخصص: ${books.length} كتاباً`;
      countBadge.style.color = '#059669';
      countBadge.style.background = 'rgba(5, 150, 105, 0.12)';
    }
  }

  if (books.length === 0) {
    listEl.innerHTML = `
      <div style="font-size: 12px; color: var(--text-muted); padding: 6px 4px;">
        📖 لم يتم تخصيص كتب محددة — سيمسح هذا الوكيل كامل أمهات مصادر الشاملة (8,589 كتاباً). انقر على الزر أعلاه لتخصيص كتب معينة.
      </div>
    `;
    return;
  }

  listEl.innerHTML = books.map((bookName, idx) => `
    <span style="display: inline-flex; align-items: center; gap: 6px; background: rgba(37, 99, 235, 0.08); border: 1px solid rgba(37, 99, 235, 0.25); color: var(--text-main); padding: 3px 8px; border-radius: 5px; font-size: 11.5px;">
      <span>📖 ${escapeHtml(bookName)}</span>
      <button type="button" onclick="removeProjectSubagentBookChip(${idx})" style="background: none; border: none; cursor: pointer; color: #dc2626; font-size: 13px; line-height: 1; padding: 0 2px;" title="حذف هذا الكتاب">×</button>
    </span>
  `).join('');
}

function removeProjectSubagentBookChip(idx) {
  if (!window._activeProjectSubagentBooks) return;
  window._activeProjectSubagentBooks.splice(idx, 1);
  renderProjectSubagentBooksChips();
}

function clearProjectSubagentBooksScope() {
  window._activeProjectSubagentBooks = [];
  renderProjectSubagentBooksChips();
  showToast('تمت إعادة تعيين نطاق الوكيل إلى جميع كتب الشاملة (8,589 كتاباً)');
}

// فتح نافذة تحديد نطاق البحث في كتب الشاملة لصالح الوكيل المساعد
function openProjectSubagentScopePicker() {
  window.onProjectSubagentScopeApplied = function(newBooks) {
    window._activeProjectSubagentBooks = [...newBooks];
    renderProjectSubagentBooksChips();
  };
  openSearchScopeModal('project_subagent');
}

// فتح نافذة تحديد نطاق الكتب مباشرة من بطاقة الوكيل في الاستوديو
function openProjectSubagentScopePickerFromCard(agentIdx) {
  const project = getOrResolveActiveProject();
  if (!project) return;
  let agents = project.subagents_group?.agents;
  if (!agents || agents.length === 0) {
    if (project.linked_group_id) {
      let groups = window.agentGroups || [];
      if (groups.length === 0) {
        try { groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]'); } catch (e) { }
      }
      const grp = groups.find(g => g.id === project.linked_group_id);
      if (grp && grp.agents) {
        agents = grp.agents;
        if (!project.subagents_group) {
          project.subagents_group = { name: grp.name, desc: grp.desc, agents: grp.agents };
        } else {
          project.subagents_group.agents = grp.agents;
        }
      }
    }
  }
  if (!agents) agents = [];
  const agent = agents[agentIdx];
  if (!agent) return;

  window._activeProjectSubagentIdx = agentIdx;
  const currentBooks = (agent.booksScope && Array.isArray(agent.booksScope)) ? agent.booksScope : (agent.books && Array.isArray(agent.books)) ? agent.books : [];
  window._activeProjectSubagentBooks = [...currentBooks];

  window.onProjectSubagentScopeApplied = async function(newBooks) {
    agent.booksScope = [...newBooks];
    agent.books = [...newBooks];
    agent.scope_summary = newBooks.length > 0 ? newBooks.join('، ') : 'أمهات كتب التراث';
    await saveProjectToStorage(project);
    renderSubagentsPreviewList(project.subagents_group.agents);
  };

  openSearchScopeModal('project_subagent');
}

// إضافة وكيل استخراج جديد للمشروع
function addNewProjectSubagent() {
  const project = getOrResolveActiveProject();
  if (!project) {
    showToast('يرجى اختيار أو فتح مشروع أولاً', true);
    return;
  }

  if (!project.subagents_group) {
    project.subagents_group = {
      id: `group_${project.id}`,
      name: `فريق: ${(project.title || 'المشروع').slice(0, 20)}`,
      desc: 'فريق الوكلاء المساعدين للمشروع البحثي',
      agents: []
    };
  }
  if (!Array.isArray(project.subagents_group.agents)) {
    project.subagents_group.agents = [];
  }

  const newIdx = project.subagents_group.agents.length;
  const newAgent = {
    id: `agent_${Date.now()}_${newIdx}`,
    name: `وكيل استخراج ${newIdx + 1}`,
    desc: 'استخراج نصوص الشاملة وتحقيق المسألة',
    role: 'استخراج نصوص الشاملة وتحقيق المسألة',
    model: 'google/gemini-2.5-flash',
    systemPrompt: 'استخرج نصوص المسألة بدقة مع أرقام الأجزاء والصفحات والمذاهب والأدلة.',
    booksScope: [],
    books: [],
    top_k: 150,
    temperature: 0.2,
    top_p: 0.9,
    frequency_penalty: 0.0,
    presence_penalty: 0.0,
    repetition_penalty: 1.0,
    max_tokens: 4096,
    enabled: true
  };

  project.subagents_group.agents.push(newAgent);
  renderSubagentsPreviewList(project.subagents_group.agents);

  // فتح نافذة الإعداد له فورياً
  openProjectSubagentConfigModal(newIdx, false);
  showToast('تمت إضافة وكيل جديد، يمكنك ضبط توجيهه وكتبه ونموذجه الآن');
}

// حذف الوكيل الحالي من المشروع
async function deleteCurrentProjectSubagent() {
  const editIdx = parseInt(document.getElementById('pSubagentEditIndex')?.value);
  if (isNaN(editIdx) || editIdx < 0) return;

  const project = getOrResolveActiveProject();
  if (!project || !project.subagents_group?.agents) return;

  const agentName = project.subagents_group.agents[editIdx]?.name || 'هذا الوكيل';
  if (!confirm(`هل أنت متأكد من حذف «${agentName}» من هذا المشروع البحثي؟`)) {
    return;
  }

  project.subagents_group.agents.splice(editIdx, 1);
  await saveProjectToStorage(project);

  // مزامنة المجموعات العامة إن وجدت
  if (project.linked_group_id && window.agentGroups) {
    const linked = window.agentGroups.find(g => g.id === project.linked_group_id);
    if (linked) {
      linked.agents = [...project.subagents_group.agents];
      localStorage.setItem(ownerStorageKey('almojtahed_agent_groups'), JSON.stringify(window.agentGroups));
    }
  }

  renderSubagentsPreviewList(project.subagents_group.agents);
  closeProjectSubagentConfigModal();
  showToast(`تم حذف «${agentName}» بنجاح`);
}

// حفظ واعتماد تعديلات الوكيل المساعد
async function saveProjectSubagentConfig() {
  const project = getOrResolveActiveProject();
  if (!project) return;

  const editIdx = parseInt(document.getElementById('pSubagentEditIndex')?.value);
  if (isNaN(editIdx) || editIdx < 0) return;

  if (!project.subagents_group) {
    project.subagents_group = { id: `group_${project.id}`, name: 'فريق التحقيق', agents: [] };
  }
  if (!Array.isArray(project.subagents_group.agents)) {
    project.subagents_group.agents = [];
  }

  let agent = project.subagents_group.agents[editIdx];
  if (!agent) {
    agent = { id: `agent_${Date.now()}` };
    project.subagents_group.agents[editIdx] = agent;
  }

  const name = document.getElementById('pSubagentName')?.value.trim() || `وكيل استخراج ${editIdx + 1}`;
  const role = document.getElementById('pSubagentRole')?.value.trim() || '';
  const isEnabled = document.getElementById('pSubagentEnabled')?.value === 'true';
  const directive = document.getElementById('pSubagentDirective')?.value.trim() || '';
  const scanned = parseInt(document.getElementById('pSubagentScannedInput')?.value) || 150;
  const model = document.getElementById('pSubagentModelSelect')?.value || projectSubagentSelectedModel || 'google/gemini-2.5-flash';

  const temp = parseFloat(document.getElementById('pSubagentTempInput')?.value) || 0.2;
  const topP = parseFloat(document.getElementById('pSubagentTopPInput')?.value) || 0.9;
  const freqPen = parseFloat(document.getElementById('pSubagentFreqPenInput')?.value) || 0.0;
  const presPen = parseFloat(document.getElementById('pSubagentPresPenInput')?.value) || 0.0;
  const modelTopK = document.getElementById('pSubagentModelTopKInput')?.value ? parseInt(document.getElementById('pSubagentModelTopKInput').value) : null;
  const maxTokens = parseInt(document.getElementById('pSubagentMaxTokensInput')?.value) || 4096;

  const books = window._activeProjectSubagentBooks || [];

  agent.name = name;
  agent.desc = role;
  agent.role = role;
  agent.enabled = isEnabled;
  agent.active = isEnabled;
  agent.systemPrompt = directive;
  agent.system_prompt = directive;
  agent.directive = directive;
  agent.top_k = scanned;
  agent.topK = scanned;
  agent.model = model;
  agent.temperature = temp;
  agent.temp = temp;
  agent.top_p = topP;
  agent.frequency_penalty = freqPen;
  agent.presence_penalty = presPen;
  agent.model_top_k = modelTopK;
  agent.max_tokens = maxTokens;
  agent.booksScope = [...books];
  agent.books = [...books];
  agent.scope_summary = books.length > 0 ? books.join('، ') : 'أمهات كتب التراث';

  // حفظ في التخزين الدائم
  await saveProjectToStorage(project);

  // مزامنة مع مجموعة الوكلاء في التخزين العام
  if (project.linked_group_id && window.agentGroups) {
    const linked = window.agentGroups.find(g => g.id === project.linked_group_id);
    if (linked) {
      linked.agents = [...project.subagents_group.agents];
      localStorage.setItem(ownerStorageKey('almojtahed_agent_groups'), JSON.stringify(window.agentGroups));
    }
  }

  renderSubagentsPreviewList(project.subagents_group.agents);
  closeProjectSubagentConfigModal();
  showToast(`✅ تم حفظ وضبط «${name}» بنجاح!`);
}

// مزامنة بطاقة سياق التجربة الحية مع التوجيه ونمط بحث المشروع والكتب
function syncSubagentTestContextUI() {
  const dirVal = document.getElementById('pSubagentDirective')?.value?.trim();
  const dirPreview = document.getElementById('pSubagentTestDirectivePreview');
  if (dirPreview) {
    if (dirVal) {
      dirPreview.textContent = dirVal.length > 100 ? (dirVal.slice(0, 100) + '...') : dirVal;
      dirPreview.title = dirVal;
    } else {
      dirPreview.textContent = 'استخراج نصوص المسألة بدقة مع أرقام الأجزاء والصفحات والمذاهب والأدلة.';
    }
  }

  const searchBadge = document.getElementById('pSubagentTestSearchModeBadge');
  if (searchBadge) {
    if (isProjectHybridSearchEnabled) {
      searchBadge.textContent = '⚡ بحث هجين (Dense + BM25)';
      searchBadge.style.color = 'var(--accent-clay)';
    } else {
      searchBadge.textContent = '🧠 بحث دلالي صرف (Dense Only)';
      searchBadge.style.color = '#2563eb';
    }
  }

  const booksBadge = document.getElementById('pSubagentTestBooksBadge');
  if (booksBadge) {
    const books = window._activeProjectSubagentBooks || [];
    if (books.length > 0) {
      booksBadge.textContent = `${books.length} كتاباً مخصصاً لهذا الوكيل`;
      booksBadge.style.color = '#059669';
    } else {
      booksBadge.textContent = 'كامل مصادر الشاملة (8,589 كتاباً)';
      booksBadge.style.color = '#2563eb';
    }
  }
}

// اختبار استجابة الوكيل والنموذج والمعلمات حياً داخل سياق المشروع مع استخراج شواهد كتبه
async function runProjectSubagentTestLive() {
  const model = document.getElementById('pSubagentModelSelect')?.value || projectSubagentSelectedModel || 'google/gemini-2.5-flash';
  const directive = document.getElementById('pSubagentDirective')?.value.trim() || '';
  const testInput = document.getElementById('pSubagentTestInput')?.value.trim() || '';
  const agentName = document.getElementById('pSubagentName')?.value?.trim() || 'الوكيل المساعد';
  const agentRole = document.getElementById('pSubagentRole')?.value?.trim() || 'استخراج نصوص الشاملة وتحقيق المسألة';
  const booksScope = window._activeProjectSubagentBooks || [];
  const scanned = parseInt(document.getElementById('pSubagentScannedInput')?.value) || 10;
  
  const project = getOrResolveActiveProject();
  const projectTitle = project ? (project.title || '') : '';
  const useHybrid = (typeof isProjectHybridSearchEnabled !== 'undefined') ? isProjectHybridSearchEnabled : true;

  const temp = parseFloat(document.getElementById('pSubagentTempInput')?.value) || 0.2;
  const topP = parseFloat(document.getElementById('pSubagentTopPInput')?.value) || 0.9;
  const freqPen = parseFloat(document.getElementById('pSubagentFreqPenInput')?.value) || 0.0;
  const presPen = parseFloat(document.getElementById('pSubagentPresPenInput')?.value) || 0.0;
  const modelTopK = document.getElementById('pSubagentModelTopKInput')?.value ? parseInt(document.getElementById('pSubagentModelTopKInput').value) : null;
  const maxTokens = parseInt(document.getElementById('pSubagentMaxTokensInput')?.value) || 1500;

  let savedKeys = {};
  try { savedKeys = readProviderKeys(); } catch (e) { }
  const apiKey = savedKeys.openrouter || '';

  const testBtn = document.getElementById('btnRunSubagentTest');
  const statusEl = document.getElementById('pSubagentTestStatus');
  const resultBox = document.getElementById('pSubagentTestResultBox');

  if (testBtn) {
    testBtn.disabled = true;
    testBtn.innerHTML = '<span>جارٍ مسح كتب الوكيل واستخراج الشواهد... ⏳</span>';
  }
  if (statusEl) {
    statusEl.innerHTML = `<span style="color: var(--accent-clay);">جارٍ استخراج الشواهد الحية بالـ (${useHybrid ? 'هجين ⚡' : 'دلالي 🧠'}) وتطبيق التوجيه...</span>`;
  }
  if (resultBox) {
    resultBox.style.display = 'block';
    resultBox.innerHTML = '<span style="color: var(--text-muted);">جارٍ مسح متجهات الشاملة وتوليد الاستجابة الحية من النموذج...</span>';
  }

  try {
    const res = await fetch('/api/subagents/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: model,
        agent_name: agentName,
        agent_role: agentRole,
        system_prompt: directive,
        user_prompt: testInput,
        books_scope: booksScope,
        scanned_texts: Math.min(scanned, 15),
        use_hybrid: useHybrid,
        project_title: projectTitle,
        temperature: temp,
        top_p: topP,
        top_k: modelTopK,
        frequency_penalty: freqPen,
        presence_penalty: presPen,
        max_tokens: maxTokens,
        thinking_level: (typeof getOrResolveActiveProject === 'function' && getOrResolveActiveProject()?.director?.thinking) || 'medium',
        api_key: apiKey
      })
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();
    if (data.status === 'error') {
      throw new Error(data.message || 'فشل استدعاء النموذج');
    }

    if (statusEl) {
      statusEl.innerHTML = `<span style="color: #059669; font-weight: 600;">✅ استجاب «${escapeHtml(data.agent_name || agentName)}» بنجاح في ${data.elapsed_seconds} ثانية عبر «${escapeHtml(data.model)}»</span>`;
    }

    if (resultBox) {
      const citsCount = data.citations_count || 0;
      const citsHtml = (data.citations && data.citations.length > 0)
        ? `<div style="margin-top: 8px; margin-bottom: 8px; padding: 7px 10px; background: rgba(37, 99, 235, 0.05); border: 1px solid rgba(37, 99, 235, 0.2); border-radius: 6px; font-size: 11.5px;">
             <strong style="color: #2563eb;">📚 الشواهد المستخرجة حياً من كتب هذا الوكيل (${citsCount} نصوص مسندة):</strong>
             <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 5px;">
               ${data.citations.map(c => `<span style="background: var(--bg-surface); border: 1px solid var(--border-subtle); padding: 2px 7px; border-radius: 4px; color: var(--text-main);">📖 ${escapeHtml(c.title)} ${escapeHtml(c.loc || '')}</span>`).join('')}
             </div>
           </div>`
        : '';

      resultBox.innerHTML = `
        <div style="margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px dashed var(--border-subtle); font-size: 11.5px; color: var(--text-muted); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px;">
          <span>🤖 النموذج: <strong>${escapeHtml(data.model)}</strong></span>
          <span>🔍 النمط: <strong style="color: var(--accent-clay);">${escapeHtml(data.search_mode || (useHybrid ? 'هجين ⚡' : 'دلالي 🧠'))}</strong></span>
          <span>🌡️ حرارة: <strong>${temp}</strong> | 🎯 Top-P: <strong>${topP}</strong> | 🚫 عقوبة: <strong>${freqPen}</strong></span>
        </div>
        <div style="margin-bottom: 8px; font-size: 11.5px; background: var(--bg-canvas); padding: 6px 10px; border-radius: 5px; border: 1px dotted var(--border-subtle); color: var(--text-secondary); line-height: 1.5; font-family: var(--font-amiri);">
          <strong style="color: var(--accent-clay);">💬 التوجيه المعتمد المطبق:</strong> ${escapeHtml(data.applied_directive || directive || '(افتراضي)')}
        </div>
        ${citsHtml}
        <div style="color: var(--text-main); font-size: 13.5px; line-height: 1.7; font-family: var(--font-amiri);">${escapeHtml(data.reply || '(لا توجد استجابة نصية)')}</div>
      `;
    }

  } catch (err) {
    console.error('Test agent error:', err);
    if (statusEl) {
      statusEl.innerHTML = `<span style="color: #dc2626; font-weight: 600;">⚠️ خطأ في الاستدعاء: ${escapeHtml(err.message)}</span>`;
    }
    if (resultBox) {
      resultBox.innerHTML = `
        <div style="color: #dc2626;">
          تعذر اختبار النموذج: ${escapeHtml(err.message)}.<br>
          يرجى التحقق من مفتاح OpenRouter في تبويب «المزودون»، أو التأكد من إتاحة النموذج المحدد.
        </div>
      `;
    }
  } finally {
    if (testBtn) {
      testBtn.disabled = false;
      testBtn.innerHTML = '⚡ تجربة استجابة الوكيل والنموذج حياً';
    }
  }
}

window.toggleProjectDispatchMode = function() {
  if (!activeProjectId) {
    const current = localStorage.getItem('almojtahed_project_dispatch_mode') || 'parallel';
    const nextMode = (current === 'direct') ? 'parallel' : 'direct';
    localStorage.setItem('almojtahed_project_dispatch_mode', nextMode);
    updateProjectDispatchModeUI();
    return;
  }
  const project = projectsList.find(p => p.id === activeProjectId);
  if (!project) return;

  const currentMode = project.agent_dispatch_mode || 'parallel';
  const newMode = (currentMode === 'direct') ? 'parallel' : 'direct';
  project.agent_dispatch_mode = newMode;

  // مزامنة أزرار الاختيار الراديو داخل البطاقة 2
  const directRadio = document.getElementById('pDispatchModeDirect');
  const parallelRadio = document.getElementById('pDispatchModeParallel');
  if (directRadio && parallelRadio) {
    if (newMode === 'direct') {
      directRadio.checked = true;
    } else {
      parallelRadio.checked = true;
    }
  }

  updateProjectDispatchModeUI();

  if (typeof showToast === 'function') {
    showToast(newMode === 'direct'
      ? '🎯 تم تفعيل النمط المباشر الموحد (سريع جداً - استدعاء واحد لمدير المشروع)'
      : '⚡ تم تفعيل النمط التوكيلي الموزع (استدعاء نماذج الوكلاء المحددين بالتوازي)', 3200);
  }

  // حفظ التعديل فوراً
  saveCurrentProjectWorkspaceState();
};

window.updateProjectDispatchModeUI = function() {
  let isDirect = false;
  if (activeProjectId) {
    const project = projectsList.find(p => p.id === activeProjectId);
    if (project) {
      isDirect = project.agent_dispatch_mode === 'direct';
    }
  }
  const directRadio = document.getElementById('pDispatchModeDirect');
  if (directRadio && directRadio.checked) {
    isDirect = true;
  }

  // 1. زر شريط أدوات المشروع البارز (الجديد في واجهة المشاريع)
  const toggleBtn = document.getElementById('projectDispatchModeToggleBtn');
  const icon = document.getElementById('projectDispatchModeIcon');
  const txt = document.getElementById('projectDispatchModeText');
  if (toggleBtn) {
    if (isDirect) {
      toggleBtn.classList.add('mode-direct');
      if (icon) icon.textContent = '🎯';
      if (txt) txt.textContent = 'موحد مباشر (سريع)';
      toggleBtn.title = 'النمط المباشر الموحد: تجميع الشواهد دفعة واحدة لمدير المشروع (سريع جداً واستدعاء واحد - خط الرجعة) - انقر للتبديل للمتوازي ⚡';
    } else {
      toggleBtn.classList.remove('mode-direct');
      if (icon) icon.textContent = '⚡';
      if (txt) txt.textContent = 'توزيع متوازي (توكيلي)';
      toggleBtn.title = 'النمط التوكيلي الموزع: تشغيل نماذج الوكلاء بالتوازي في OpenRouter ثم الصياغة لمدير المشروع - انقر للتبديل للمباشر 🎯';
    }
  }

  // 2. الشارة داخل البطاقة 2
  const badge = document.getElementById('pDispatchModeBadge');
  if (badge) {
    if (isDirect) {
      badge.textContent = 'موحد مباشر 🎯';
      badge.style.background = 'rgba(100, 116, 139, 0.15)';
      badge.style.color = 'var(--text-secondary)';
      badge.style.border = '1px solid rgba(100, 116, 139, 0.3)';
    } else {
      badge.textContent = 'توزيع متوازي ⚡';
      badge.style.background = 'rgba(180, 83, 9, 0.12)';
      badge.style.color = 'var(--accent-clay)';
      badge.style.border = '1px solid rgba(180, 83, 9, 0.25)';
    }
  }

  // 3. شارة لوحة نتائج تشغيل المشروع
  const runBadge = document.getElementById('projectRunModeBadge');
  if (runBadge) {
    if (isDirect) {
      runBadge.textContent = '🎯 نمط موحد مباشر';
      runBadge.style.background = 'rgba(100, 116, 139, 0.15)';
      runBadge.style.color = 'var(--text-secondary)';
    } else {
      runBadge.textContent = '⚡ نمط متوازي';
      runBadge.style.background = 'rgba(180, 83, 9, 0.15)';
      runBadge.style.color = 'var(--accent-clay)';
    }
  }
};

// مطابقة وتحقق آلي لأسماء كتب الوكلاء مع العناوين الحرفية في المخزن
async function resolveAndVerifyProjectBooks() {
  if (!activeProjectId) {
    showToast('⚠️ يرجى فتح مشروع أولاً لمطابقة كتبه');
    return;
  }
  const project = projectsList.find(p => p.id === activeProjectId);
  if (!project) return;

  let agents = project.subagents_group?.agents || [];
  let allBooks = [];
  agents.forEach(a => {
    (a.books || []).forEach(b => {
      const trimmed = b.trim();
      if (trimmed && !allBooks.includes(trimmed)) allBooks.push(trimmed);
    });
  });

  if (allBooks.length === 0) {
    showToast('ℹ️ لا توجد كتب محددة في بطاقات الوكلاء لمطابقتها');
    return;
  }

  showToast('⏳ جارٍ مطابقة الكتب مع عناوين المخزن المتجهي (8.15M مقطع)...');

  try {
    const res = await fetch('/api/books/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ books: allBooks })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const map = {};
    let matchedCount = 0;

    (data.results || []).forEach(r => {
      if (r.resolved) {
        map[r.input] = r.resolved;
        if (r.resolved !== r.input || r.verified) matchedCount++;
      }
    });

    // تحديث الكتب في وكلاء المشروع
    agents.forEach(a => {
      if (a.books && a.books.length > 0) {
        a.books = a.books.map(b => map[b] || b);
        a.scope_summary = a.books.join('، ');
      }
    });

    // تحديث المجموعة المرتبطة إن وجدت
    if (project.linked_group_id) {
      let groups = window.agentGroups || [];
      let linkedGroup = groups.find(g => g.id === project.linked_group_id);
      if (linkedGroup && linkedGroup.agents) {
        linkedGroup.agents.forEach(a => {
          if (a.books && a.books.length > 0) {
            a.books = a.books.map(b => map[b] || b);
            a.scope_summary = a.books.join('، ');
          }
        });
        localStorage.setItem(ownerStorageKey('almojtahed_agent_groups'), JSON.stringify(groups));
      }
    }

    await saveProjectToStorage(project);
    renderSubagentsPreviewList(agents);
    showToast(`✅ تم التحقق ومطابقة ${matchedCount} كتاباً مع العناوين الحرفية في المخزن وتثبيتها بنجاح!`);
  } catch (err) {
    console.error('Error resolving books:', err);
    showToast(`تعذر مطابقة الكتب: ${err.message}`);
  }
}

// =============================================================================
// نافذة تخطيط وهندسة المشروع (Project Planning & Engineering Wizard)
// =============================================================================

// =============================================================================
// استوديو تخطيط وهندسة المشروع التفاعلي (Interactive Architecture Studio)
// حوار حي ومباشر مع كبير المهندسين المعماريين لتأسيس كروت المشروع وأدواته
// =============================================================================

let architectHistory = [];
let currentStudioBlueprint = null;
let currentPlanningProjectId = null;

async function openProjectPlanningModal(projectId = null) {
  const modal = document.getElementById('projectPlanningModal');
  if (!modal) return;

  const inputEl = document.getElementById('architectUserInput');
  modal.style.display = 'flex';

  // 1. تحديد هل المطلوب تعديل مشروع قائم ومحدد صراحة أم تأسيس مشروع جديد
  // إذا لم يُمرر projectId أو كان 'new'، فهو تأسيس جديد حتماً برقم فريد وذاكرة ممسوحة
  let targetPid = null;
  if (projectId && projectId !== 'new' && projectId !== 'null') {
    targetPid = projectId;
  }

  let targetModel = 'google/gemini-2.5-flash';
  let loadedFromProject = false;

  const titleEl = document.getElementById('planningStudioModalTitle');
  const subtitleEl = document.getElementById('planningStudioModalSubtitle');
  const updateBtn = document.getElementById('btnUpdateActiveProjectCards');
  const applyBtn = document.getElementById('btnApplyStudioBlueprint');
  const statusBadge = document.getElementById('blueprintLiveStatus');

  if (targetPid) {
    const p = projectsList.find(x => x.id === targetPid);
    if (p) {
      currentPlanningProjectId = targetPid;
      activeProjectId = targetPid;

      if (titleEl) titleEl.textContent = `استوديو تطوير وهندسة: «${p.title || 'مشروع بحثي'}»`;
      if (subtitleEl) subtitleEl.innerHTML = `معرّف المشروع: <code style="color:var(--accent-clay); font-weight:700;">${p.id}</code> — حوار مباشر لمراجعة وتطوير الخطة والكروت دون تكرار`;

      if (p.architect_model) targetModel = p.architect_model;
      const studioThink = document.getElementById('architectThinkingSelect');
      if (studioThink) studioThink.value = p.architect_thinking || 'medium';
      if ((p.architect_dialog && p.architect_dialog.length > 0) || (p.architect_history && p.architect_history.length > 0)) {
        architectHistory = [...(p.architect_dialog || p.architect_history)];
        renderArchitectChat();
        loadedFromProject = true;
      } else {
        const title = p.title || 'مشروعك البحثي';
        const welcomeText = `مرحباً بك أستاذنا الباحث الكريم في استوديو هندسة وتطوير المشاريع 🧭.\n\nأنا مهندسك المعماري ومستشارك التخطيطي لهذا المشروع: «**${title}**» (معرّف: \`${p.id}\`).\nأنا معك لمراجعة خطة المشروع، أو إعادة هندسة كروت الوكلاء والمصادر، أو ضبط وتطوير أدوات التحقق الحسابية والتقويمية وتوجيهات المدير.\n\nما الجانب الذي تود تحسينه أو تعديله في هذا المشروع؟`;
        architectHistory = [{ role: 'assistant', content: welcomeText }];
        renderArchitectChat();
        loadedFromProject = true;
      }

      // استعادة كروت المخطط وعرضها فورياً في الاستوديو
      if (p.blueprint) {
        currentStudioBlueprint = p.blueprint;
      } else {
        currentStudioBlueprint = {
          title: p.title,
          desc: p.desc,
          extraction_capacity: p.extraction_capacity || 150,
          retrieval_anchors: p.retrieval_anchors || [],
          director: p.director || {},
          subagents_group: p.subagents_group || { name: 'فريق التحقيق التخصصي', agents: [] },
          internal_benchmark: p.internal_benchmark || { enabled: false },
          external_web_benchmark: p.external_web_benchmark || { enabled: false },
          computational_tool: p.computational_tool || { enabled: false },
          output_formats: p.output_formats || { csv_results: true, formatted_txt: true }
        };
      }
      renderStudioCardsPreview(currentStudioBlueprint);

      if (updateBtn) {
        updateBtn.style.display = 'inline-flex';
        updateBtn.disabled = false;
        updateBtn.innerHTML = `
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg>
          <span>تحديث وحفظ كروت هذا المشروع فورياً بالخطة المعدلة ⚡</span>
        `;
      }
      if (applyBtn) {
        applyBtn.style.display = 'inline-flex';
        applyBtn.disabled = false;
        applyBtn.innerHTML = `<span>حفظ التعديلات في هذا المشروع ✅</span>`;
      }
      if (statusBadge) {
        statusBadge.textContent = 'خطة المشروع معتمدة ومحفوظة ✅';
        statusBadge.className = 'p-status-pill active';
      }
    }
  }

  // 2. إذا كان تأسيس مشروع جديد تماماً: مسح الذاكرة بالكامل وتوليد رقم فريد جديد
  if (!loadedFromProject) {
    const newUniqueId = 'proj_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7);
    currentPlanningProjectId = newUniqueId;
    activeProjectId = null; // فك أي ارتباط بالمشاريع السابقة تماماً
    architectHistory = [];
    currentStudioBlueprint = null;

    if (titleEl) titleEl.textContent = 'استوديو تخطيط وهندسة مشروع جديد';
    if (subtitleEl) subtitleEl.innerHTML = `معرّف فريد جديد: <code style="color:var(--accent-clay); font-weight:700;">${newUniqueId}</code>`;

    const cardsStream = document.getElementById('studioCardsStream');
    if (cardsStream) {
      cardsStream.innerHTML = `
        <div class="studio-empty-blueprint" id="studioEmptyBlueprint">
          <div class="empty-icon">🧭</div>
          <h4>غرفة التخطيط والهندسة المفتوحة</h4>
          <p>حاور كبير المهندسين على اليمين؛ وسيقوم باستنباط وتشكيل كروت الوكلاء، وتوجيهات المدير، وأداة التحقق الحسابية، والمقارنة المرجعية وتحديثها لحظياً هنا أمامك.</p>
        </div>
      `;
    }

    if (updateBtn) {
      updateBtn.style.display = 'none'; // إخفاء زر التحديث لأنه لا يوجد مشروع قائم بعد
    }
    if (applyBtn) {
      applyBtn.style.display = 'inline-flex';
      applyBtn.disabled = true;
      applyBtn.innerHTML = `
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
        <span>اعتماد وتأسيس المشروع الجديد 🚀</span>
      `;
    }
    if (statusBadge) {
      statusBadge.textContent = 'بانتظار النقاش ⏳';
      statusBadge.className = 'p-status-pill';
    }

    const welcomeText = `مرحباً بك أستاذنا الباحث الكريم في **استوديو تخطيط وهندسة المشاريع التراثية الكبرى** 🧭.\n\nأنا **كبير المهندسين المعماريين** لمنظومة «المجتهد»، ومهمتي أن أحاورك وأناقشك خطوة بخطوة في فكرة مسألتك أو مشروعك البحثي الجديد (المعرّف الفريد: \`${newUniqueId}\`).\n\nسنحدد سوياً:\n1. 📜 النطاق الزمني والمصادري الدقيق في الشاملة.\n2. 👥 تشكيل كروت الوكلاء المساعدين التخصصيين وتوجيهاتهم الخاصة.\n3. 📐 أداة التحقق والمقارنة الأكاديمية أو الحسابية المطلوبة.\n4. ⚖️ مصفوفة المقارنة المرجعية (Benchmark).\n\n**تفضل بطرح موضوعك أو مسألتك وما تصبو إلى تحقيقه لنبدأ نقاشنا فوراً!**`;
    architectHistory = [{ role: 'assistant', content: welcomeText }];
    renderArchitectChat();
  }

  await populateArchitectModelsList(targetModel);
  if (typeof syncThinkingControls === 'function') syncThinkingControls();
  initStudioBooks();

  if (inputEl) {
    setTimeout(() => inputEl.focus(), 150);
  }
}

function startFreshProjectPlanning() {
  openProjectPlanningModal('new');
  if (typeof showToast === 'function') {
    showToast('✨ تم تفريغ ذاكرة الاستوديو وتوليد رقم فريد لمشروع جديد!');
  }
}

function closeProjectPlanningModal() {
  const modal = document.getElementById('projectPlanningModal');
  if (modal) modal.style.display = 'none';
}

function handleProjectModalClick(e) {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.style.display = 'none';
  }
}

function handleArchitectInputKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendArchitectMessage();
  }
}

function applyQuickStudioPrompt(text) {
  const inputEl = document.getElementById('architectUserInput');
  if (inputEl) {
    inputEl.value = text;
    inputEl.focus();
  }
}

function extractArchitectChoices(text) {
  const match = String(text || '').match(/```choices\s*([\s\S]*?)```/);
  if (!match) return [];
  try {
    const data = JSON.parse(match[1]);
    const questions = Array.isArray(data) ? data : (data.questions || []);
    return questions.filter(question => question && question.prompt && Array.isArray(question.options) && question.options.length);
  } catch (e) {
    return [];
  }
}

function architectChoicesHtml(questions, index) {
  if (!questions.length) return '';
  const blocks = questions.map((question, qIndex) => {
    const inputType = question.multiple ? 'checkbox' : 'radio';
    const options = question.options.map((option, oIndex) => `
      <label class="architect-choice-option">
        <input type="${inputType}" name="architectQ${index}_${qIndex}" value="${escapeHtml(String(option))}">
        <span>${escapeHtml(String(option))}</span>
      </label>
    `).join('');
    return `
      <div class="architect-choice-q" data-prompt="${escapeHtml(question.prompt)}">
        <strong>${escapeHtml(question.prompt)}</strong>
        ${options}
      </div>
    `;
  }).join('');
  return `
    <div class="architect-choices" id="architectChoices${index}">
      ${blocks}
      <label class="architect-choice-extra">إضافة
        <textarea rows="2" placeholder="اكتب ما تريد إضافته، إن رغبت"></textarea>
      </label>
      <button type="button" class="btn-primary-gradient" onclick="submitArchitectChoices(${index})">إرسال الاختيار</button>
    </div>
  `;
}

function submitArchitectChoices(index) {
  const root = document.getElementById(`architectChoices${index}`);
  const input = document.getElementById('architectUserInput');
  if (!root || !input) return;
  const lines = [...root.querySelectorAll('.architect-choice-q')].map(block => {
    const prompt = block.getAttribute('data-prompt') || '';
    const chosen = [...block.querySelectorAll('input:checked')].map(item => item.value);
    return chosen.length ? `${prompt}: ${chosen.join('، ')}` : '';
  }).filter(Boolean);
  const extra = root.querySelector('textarea')?.value.trim() || '';
  if (extra) lines.push(`إضافة: ${extra}`);
  if (!lines.length) {
    if (typeof showToast === 'function') showToast('اختر جواباً أو اكتب إضافة');
    return;
  }
  input.value = lines.join('\n');
  sendArchitectMessage();
}
window.submitArchitectChoices = submitArchitectChoices;

function renderArchitectChat() {
  const container = document.getElementById('architectChatHistory');
  if (!container) return;
  const lastAssistant = architectHistory.reduce((found, message, index) => message.role === 'assistant' ? index : found, -1);

  container.innerHTML = architectHistory.map((m, index) => {
    const isUser = m.role === 'user';
    const avatar = isUser ? '👤' : '🧭';
    let cleanText = (m.content || '').replace(/```json[\s\S]*?```/g, '').replace(/```choices[\s\S]*?```/g, '').trim();
    if (!cleanText && isUser) cleanText = m.content;
    const bodyHtml = (typeof formatMarkdown === 'function') ? formatMarkdown(cleanText) : (typeof marked !== 'undefined' ? marked.parse(cleanText) : cleanText.replace(/\n/g, '<br>'));
    const choices = (!isUser && index === lastAssistant) ? architectChoicesHtml(extractArchitectChoices(m.content), index) : '';

    return `
      <div class="studio-msg ${isUser ? 'user' : 'architect'}">
        <div class="studio-avatar">${avatar}</div>
        <div class="studio-bubble">${bodyHtml}${choices}</div>
      </div>
    `;
  }).join('');

  container.scrollTop = container.scrollHeight;
}

async function sendArchitectMessage() {
  const inputEl = document.getElementById('architectUserInput');
  const userText = (inputEl?.value || '').trim();
  if (!userText) return;

  inputEl.value = '';

  // إضافة رسالة المستخدم إلى سجل المحادثة
  architectHistory.push({ role: 'user', content: userText });
  renderArchitectChat();

  const sendBtn = document.getElementById('btnSendArchitect');
  const modelSelect = document.getElementById('architectModelSelect');
  const chosenModel = modelSelect?.value || 'google/gemini-2.5-flash';
  const thinkingLevel = document.getElementById('architectThinkingSelect')?.value || 'medium';
  const thinkingPhrase = (typeof describeThinking === 'function') ? describeThinking(chosenModel, thinkingLevel) : thinkingLevel;

  if (sendBtn) {
    sendBtn.disabled = true;
    sendBtn.innerHTML = `<span>جارٍ التفكير...</span>`;
  }

  // إضافة فقاعة انتظار مؤقتة
  const tempMsgId = 'temp_waiting_' + Date.now();
  const container = document.getElementById('architectChatHistory');
  if (container) {
    const waitDiv = document.createElement('div');
    waitDiv.id = tempMsgId;
    waitDiv.className = 'studio-msg architect';
    waitDiv.innerHTML = `
      <div class="studio-avatar">🧭</div>
      <div class="studio-bubble" style="color: var(--text-muted); font-style: italic;">
        <span class="status-indicator-spinner" style="display:inline-block; width:13px; height:13px; vertical-align:middle; margin-left:6px;"></span>
        مهندس التخطيط يدرس فكرتك (${escapeHtml(thinkingPhrase)}) ويصيغ المقترحات المعمارية والكروت...
      </div>
    `;
    container.appendChild(waitDiv);
    container.scrollTop = container.scrollHeight;
  }

  let savedKeys = {};
  try {
    savedKeys = readProviderKeys();
  } catch (e) { }
  const apiKey = savedKeys.openrouter || '';

  try {
    const res = await fetch('/api/projects/architect-dialog', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: architectHistory,
        planning_model: chosenModel,
        thinking_level: thinkingLevel,
        tavily_key: (typeof readTavilyKey === 'function' ? readTavilyKey() : '') || (savedKeys.tavily || ''),
        api_key: apiKey
      })
    });

    const waitEl = document.getElementById(tempMsgId);
    if (waitEl) waitEl.remove();

    if (!res.ok) {
      let errMsg = `HTTP ${res.status}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) errMsg = errJson.detail;
        else if (errJson.message) errMsg = errJson.message;
      } catch (e) { }
      throw new Error(errMsg);
    }
    const data = await res.json();

    if (data.status === 'error') {
      throw new Error(data.message || 'تعذر استدعاء مهندس التخطيط');
    }

    if (data.reply) {
      architectHistory.push({ role: 'assistant', content: data.reply });
      renderArchitectChat();

      // حفظ سجل المحادثة ونموذج المهندس فورياً في كائن المشروع المرتبط إذا كان مشروعاً قائماً محفوظاً
      const targetId = currentPlanningProjectId;
      if (targetId) {
        const curProj = projectsList.find(x => x.id === targetId);
        if (curProj) {
          curProj.architect_dialog = [...architectHistory];
          curProj.architect_history = [...architectHistory];
          curProj.architect_model = document.getElementById('architectModelSelect')?.value || curProj.architect_model || 'google/gemini-2.5-flash';
          curProj.architect_thinking = document.getElementById('architectThinkingSelect')?.value || curProj.architect_thinking || 'medium';
          if (data.blueprint) {
            curProj.blueprint = data.blueprint;
          }
          saveProjectToStorage(curProj);
        }
      }
    }

    if (data.explored_books && data.explored_books.length > 0) {
      renderStudioBooksDrawer(data.explored_books);
    }

    if (data.blueprint) {
      currentStudioBlueprint = data.blueprint;
      renderStudioCardsPreview(data.blueprint);
      const applyBtn = document.getElementById('btnApplyStudioBlueprint');
      const statusBadge = document.getElementById('blueprintLiveStatus');
      if (applyBtn) applyBtn.disabled = false;
      if (statusBadge) {
        statusBadge.textContent = 'جاهز للاعتماد ✅';
        statusBadge.className = 'p-status-pill active';
      }
    }

  } catch (err) {
    const waitEl = document.getElementById(tempMsgId);
    if (waitEl) waitEl.remove();
    showToast(`خطأ في استدعاء المهندس: ${err.message}`);
  } finally {
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        <span>إرسال</span>
      `;
    }
  }
}

async function populateOpenRouterModelDropdown(selectEl, selectedVal) {
  if (!selectEl) return;

  const currentVal = selectedVal || selectEl.value || 'google/gemini-2.5-flash';

  const topFive = projectSuggestedModels();

  let allModels = window.openrouterModelsList || [];
  if (allModels.length === 0) {
    try {
      let savedKeys = {};
      try { savedKeys = readProviderKeys(); } catch (e) { }
      const apiKey = savedKeys.openrouter || '';
      const url = `/api/openrouter/models${apiKey ? '?api_key=' + encodeURIComponent(apiKey) : ''}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        allModels = data.models || [];
        window.openrouterModelsList = allModels;
      }
    } catch (e) {
      console.warn('Could not fetch OpenRouter models:', e);
    }
  }

  const topIds = new Set(topFive.map(m => m.id));
  const otherModels = (allModels || []).filter(m => !topIds.has(m.id));
  otherModels.sort((a, b) => (a.name || a.id).localeCompare(b.name || b.id));

  const exists = topFive.some(m => m.id === currentVal) || otherModels.some(m => m.id === currentVal);
  let customOption = '';
  if (!exists && currentVal) {
    customOption = `<option value="${currentVal}" selected>${escapeHtml(currentVal)} (محدد حالياً)</option>`;
  }

  const topHtml = topFive.map(m =>
    `<option value="${m.id}" ${m.id === currentVal ? 'selected' : ''}>${escapeHtml(m.name)}</option>`
  ).join('');

  const otherHtml = otherModels.map(m => {
    const label = m.name ? `${m.name} (${m.id})` : m.id;
    return `<option value="${m.id}" ${m.id === currentVal ? 'selected' : ''}>${escapeHtml(label)}</option>`;
  }).join('');

  selectEl.innerHTML = `
    ${customOption}
    <optgroup label="⭐ النماذج المقترحة">
      ${topHtml}
    </optgroup>
    <optgroup label="🌐 كافة نماذج OpenRouter المتاحة (${otherModels.length} نموذج)">
      ${otherHtml}
    </optgroup>
  `;
  selectEl.value = currentVal;
}

async function populateArchitectModelsList(preferredModel = null) {
  const selectEl = document.getElementById('architectModelSelect');
  if (selectEl) {
    const val = preferredModel || selectEl.value || 'google/gemini-2.5-flash';
    await populateOpenRouterModelDropdown(selectEl, val);
    selectEl.value = val;
  }
}

function renderStudioBooksDrawer(books) {
  const drawer = document.getElementById('studioBooksDrawer');
  const chipsContainer = document.getElementById('studioBooksChips');
  const countBadge = document.getElementById('studioBooksCount');
  if (!drawer || !chipsContainer) return;

  drawer.style.display = 'block';

  if (!books || books.length === 0) {
    chipsContainer.innerHTML = `
      <div style="font-size: 11.5px; color: var(--text-muted); padding: 8px 4px; width: 100%;">
        لم يتم العثور على كتب مطابقة. جرّب البحث برقم الكتاب المعياري مثل <code>#1852</code> أو جزء من العنوان أو اسم المؤلف.
      </div>
    `;
    if (countBadge) countBadge.textContent = '0 كتاب';
    return;
  }

  if (countBadge) countBadge.textContent = `${books.length} كتاب معتمد`;

  chipsContainer.innerHTML = books.map(b => {
    const authorSnippet = b.death && b.death !== '—' ? `${b.author} (${b.death})` : b.author;
    const catName = b.category_name || b.category || 'عام';
    const bid = b.book_id || '';
    const safeTitle = escapeHtml(b.title || '');
    return `
      <div class="studio-book-chip" onclick="insertBookIntoArchitectChat(${bid}, '${escapeHtml(b.title)}')" title="معرّف الشاملة: #${bid} | التصنيف: ${escapeHtml(catName)} | ${escapeHtml(b.betaka_snippet || '')}">
        ${bid ? `<span class="book-id-badge">#${bid}</span>` : ''}
        <span>📖 ${safeTitle}</span>
        <span class="book-author">— ${escapeHtml(authorSnippet)}</span>
      </div>
    `;
  }).join('');
}

function insertBookIntoArchitectChat(bookId, bookTitle) {
  const inputEl = document.getElementById('architectUserInput');
  if (!inputEl) return;
  const current = inputEl.value.trim();
  const addition = `نقترح اعتماد كتاب #${bookId} «${bookTitle}» ضمن مصادر التحقيق.`;
  inputEl.value = current ? `${current}\n${addition}` : addition;
  inputEl.focus();
}

let studioBookSearchDebounceTimer = null;
function handleStudioBookSearch(query) {
  const clearBtn = document.getElementById('studioBookClearBtn');
  if (clearBtn) clearBtn.style.display = (query && query.trim()) ? 'block' : 'none';

  clearTimeout(studioBookSearchDebounceTimer);
  studioBookSearchDebounceTimer = setTimeout(async () => {
    const catSelect = document.getElementById('studioBookCategoryFilter');
    const catId = catSelect ? catSelect.value : '';
    await fetchAndRenderBooks(query, catId);
  }, 220);
}

function clearStudioBookSearch() {
  const input = document.getElementById('studioBookSearchInput');
  if (input) input.value = '';
  const clearBtn = document.getElementById('studioBookClearBtn');
  if (clearBtn) clearBtn.style.display = 'none';
  const catSelect = document.getElementById('studioBookCategoryFilter');
  const catId = catSelect ? catSelect.value : '';
  fetchAndRenderBooks('', catId);
}

function handleStudioBookCatFilter(catId) {
  const input = document.getElementById('studioBookSearchInput');
  const query = input ? input.value : '';
  fetchAndRenderBooks(query, catId);
}

async function fetchAndRenderBooks(query = '', catId = '') {
  try {
    const params = new URLSearchParams();
    if (query && query.trim()) params.append('q', query.trim());
    if (catId) params.append('category_id', catId);
    params.append('limit', '40');

    const res = await fetch(`/api/books/search?${params.toString()}`);
    if (res.ok) {
      const data = await res.json();
      renderStudioBooksDrawer(data.books || []);
    }
  } catch (e) {
    console.error('Error searching studio books:', e);
  }
}

function toggleStudioBooksDrawer() {
  const bar = document.getElementById('studioBooksSearchBar');
  const chips = document.getElementById('studioBooksChips');
  const toggleBtnText = document.getElementById('toggleBooksDrawerText');
  if (!bar || !chips) return;

  const isHidden = chips.style.display === 'none';
  if (isHidden) {
    chips.style.display = 'flex';
    bar.style.display = 'flex';
    if (toggleBtnText) toggleBtnText.textContent = 'إخفاء';
    if (!chips.children.length) fetchAndRenderBooks('', document.getElementById('studioBookCategoryFilter')?.value || '');
  } else {
    chips.style.display = 'none';
    bar.style.display = 'none';
    if (toggleBtnText) toggleBtnText.textContent = 'إظهار الفهرس';
  }
}

async function initStudioBooks() {
  const chipsContainer = document.getElementById('studioBooksChips');
  const searchBar = document.getElementById('studioBooksSearchBar');
  const toggleBtnText = document.getElementById('toggleBooksDrawerText');
  if (chipsContainer) chipsContainer.style.display = 'none';
  if (searchBar) searchBar.style.display = 'none';
  if (toggleBtnText) toggleBtnText.textContent = 'إظهار الفهرس';

  // تحميل كافة التصنيفات الـ 41 المعتمدة ديناميكياً من قاعدة البيانات
  const catSelect = document.getElementById('studioBookCategoryFilter');
  if (catSelect && catSelect.children.length <= 11) {
    try {
      const res = await fetch('/api/categories');
      if (res.ok) {
        const cats = await res.json();
        if (Array.isArray(cats) && cats.length > 0) {
          catSelect.innerHTML = `<option value="">كل التصنيفات (${cats.length} تصنيفاً بالمخزن)</option>` +
            cats.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
        }
      }
    } catch (e) {
      console.warn('Could not load dynamic categories for studio books:', e);
    }
  }
}

function renderStudioCardsPreview(bp) {
  const container = document.getElementById('studioCardsStream');
  if (!container || !bp) return;

  const agentsCount = bp.subagents_group?.agents?.length || 0;

  container.innerHTML = `
    <!-- كرت 1: المدير -->
    <div class="studio-card-preview">
      <div class="scp-header">
        <span class="scp-title">🧠 1. مدير المشروع المقترح</span>
        <span class="scp-badge">${escapeHtml(bp.director?.model || 'Gemini 2.5')}</span>
      </div>
      <div class="scp-body">
        <strong>${escapeHtml(bp.director?.name || 'مدير المشروع')}</strong><br>
        <span style="color: var(--text-muted); font-size: 11.5px;">${escapeHtml(bp.director?.model || '')} · تفكير ${escapeHtml(bp.director?.thinking || 'medium')} · ${escapeHtml(bp.director?.search_mode || 'hybrid')} · ${bp.director?.extract_count || bp.extraction_capacity || 150} نصاً</span><br>
        <span style="color: var(--text-muted); font-size: 11.5px;">التوجيه القيادي التخصصي:</span>
        <div style="background: var(--bg-muted); padding: 6px 8px; border-radius: 4px; margin-top: 4px; font-size: 11.5px; line-height: 1.5;">
          ${escapeHtml(bp.director?.system_prompt || '')}
        </div>
      </div>
    </div>

    <!-- كرت 2: فريق الوكلاء المساعدين -->
    <div class="studio-card-preview">
      <div class="scp-header">
        <span class="scp-title">👥 2. فريق الوكلاء المساعدين المخصص</span>
        <span class="scp-badge">${agentsCount} وكلاء تخصصيون</span>
      </div>
      <div class="scp-body">
        <strong>${escapeHtml(bp.subagents_group?.name || 'فريق التحقيق')}</strong>:
        <span style="color: var(--text-secondary);">${escapeHtml(bp.subagents_group?.desc || '')}</span>
        <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 8px;">
          ${(bp.subagents_group?.agents || []).map((ag, idx) => `
            <div style="background: var(--bg-muted); padding: 6px 10px; border-radius: 4px; border: 1px solid var(--border-subtle); font-size: 12px;">
              <strong>${idx + 1}. ${escapeHtml(ag.name)}:</strong> ${escapeHtml(ag.model || '')} · تفكير ${escapeHtml(ag.thinking || 'medium')} · ${escapeHtml(ag.search_mode || 'hybrid')} · ${ag.extract_count || ag.top_k || 150} نصاً
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${(ag.books || []).join('، ') || 'أمهات كتب التراث'}</div>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">💬 ${escapeHtml(ag.desc || ag.system_prompt || '')}</div>
            </div>
          `).join('')}
        </div>
        <div style="margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--border-subtle); display: flex; justify-content: space-between; align-items: center; font-size: 12px;">
          <span>📊 <strong>سعة الاستخراج المستهدفة:</strong></span>
          <span style="color: var(--accent-clay); font-weight: 700; background: rgba(180, 83, 9, 0.1); padding: 2px 7px; border-radius: 4px;">${bp.extraction_capacity || 150} مقطعاً (قابلة للزيادة)</span>
        </div>
        ${(bp.retrieval_anchors && bp.retrieval_anchors.length > 0) ? `
          <div style="margin-top: 8px; font-size: 11.5px;">
            <div style="font-weight: 600; color: #10b981; margin-bottom: 4px;">⚓ مراسي الاسترجاع الديناميكية المصممة لهذا المشروع:</div>
            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
              ${bp.retrieval_anchors.map(anc => `<span style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); color: var(--text-main); padding: 2px 6px; border-radius: 4px; font-size: 11px;">«${escapeHtml(anc)}»</span>`).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    </div>

    <!-- كرت 3: الأداة المساعدة -->
    <div class="studio-card-preview">
      <div class="scp-header">
        <span class="scp-title">📐 3. الأداة المساعدة المعتمدة</span>
        <span class="scp-badge" style="color: ${bp.computational_tool?.enabled ? '#059669' : '#9ca3af'}; font-weight: 700;">${bp.computational_tool?.enabled ? 'مفعلة' : 'معطلة'}</span>
      </div>
      <div class="scp-body">
        <strong>${escapeHtml(bp.computational_tool?.name || (bp.computational_tool?.enabled ? 'أداة مساعدة متخصصة' : 'بدون أداة مساعدة'))}</strong><br>
        <span style="font-size: 12px; color: var(--text-secondary);">${escapeHtml(bp.computational_tool?.desc || (bp.computational_tool?.enabled ? 'توجيه استخدام الأداة' : 'لا يتطلب البحث أدوات حسابية خارجية'))}</span>
      </div>
    </div>

    <!-- كرت 4: المقارنة المرجعية التراثية -->
    <div class="studio-card-preview">
      <div class="scp-header">
        <span class="scp-title">⚖️ 4. المقارنة المرجعية التراثية (Benchmark)</span>
        <span class="scp-badge">مضاهاة</span>
      </div>
      <div class="scp-body">
        <strong>كتاب المضاهاة:</strong> ${escapeHtml(bp.internal_benchmark?.title || 'دراسة سابقة')}<br>
        <span style="font-size: 12px; color: var(--text-muted);">المؤلف: ${escapeHtml(bp.internal_benchmark?.author || '—')}</span><br>
        <span style="font-size: 11.5px; color: var(--text-secondary);">المنهجية: ${escapeHtml(bp.internal_benchmark?.methodology || 'استخراج الإضافات والاستدراكات')}</span>
      </div>
    </div>

    <!-- كرت 5: المقارنة الخارجية -->
    <div class="studio-card-preview">
      <div class="scp-header">
        <span class="scp-title">🌐 5. استعلام البحث الخارجي (Tavily AI)</span>
        <span class="scp-badge">أكاديمي</span>
      </div>
      <div class="scp-body">
        <code style="font-size: 11px; background: rgba(0,0,0,0.04); padding: 2px 4px; border-radius: 3px;">
          ${escapeHtml(bp.external_web_benchmark?.query || bp.title || '')}
        </code>
      </div>
    </div>
  `;
}

function generateFallbackBlueprintFromContext(ctx) {
  const rawText = (ctx || '').replace(/[\r\n]+/g, ' ').trim();

  // استخراج عنوان المشروع بدقة من أول جملة يطرحها الباحث
  let extractedTitle = rawText.split(/[.؟!؛:]/)[0] || '';
  extractedTitle = extractedTitle.replace(/^(أريد|أود|اقترح|مشروع|بحث|دراسة|مسألة|نود|تحقيق)\s+/i, '').trim();
  if (extractedTitle.length > 60) {
    extractedTitle = extractedTitle.slice(0, 57) + '...';
  }
  if (!extractedTitle || extractedTitle.length < 4) {
    extractedTitle = 'مشروع بحثي تراثي مخصص';
  }

  // الكشف الدقيق عن الفنون المتضمنة في المسألة (دون خلط بين السنة النبوية والسنوات الفلكية)
  const isHadith = /حديث|تخريج|أحاديث|أسانيد|رجال|صحيح|سنن|مسانيد|رواية|علل|طرق|تعديل|جرح/.test(rawText);
  const isFiqh = /فقه|مذاهب|أصول|فروع|حكم|لعان|فراش|نسب|وقف|بيوع|نكاح|طلاق|حدود|جنايات|طهارة|صلاة/.test(rawText);
  const isContemporary = /dna|حمض نووي|بصمة|طب|معاصر|نوازل|قرائن|قيافة/.test(rawText.toLowerCase());
  const isTafsir = /تفسير|قرآن|آية|سورة|قراءات|نزول|غريب/.test(rawText);
  const isTrueAstronomy = /كسوف|خسوف|مذنب|مذنبات|أطوار القمر|اقتران الكواكب/.test(rawText);

  let agents = [];
  let compTool = {
    enabled: true,
    tool_type: 'tavily_academic_verification',
    name: 'أداة التحقق والمقارنة الأكاديمية التخصصية',
    desc: 'البحث في المجلات العلمية المحكمة والمصادر المقارنة'
  };

  if (isTrueAstronomy) {
    agents.push(
      {
        name: 'وكيل حوليات المشرق والمشاهدات الفلكية',
        desc: 'رصد نصوص الكسوف والخسوف في تاريخ الطبري والبداية والنهاية',
        model: 'google/gemini-2.5-flash',
        books: ['تاريخ الطبري', 'البداية والنهاية', 'المنتظم'],
        pool_size: 1500, top_k: 150,
        system_prompt: 'استخرج كافة نصوص حوادث الكسوف والخسوف بدقة مع التاريخ واليوم والمكان.'
      },
      {
        name: 'وكيل حوليات الشام والمغرب',
        desc: 'رصد الكسوفات والمذنبات في الكامل لابن الأثير وتاريخ الإسلام للذهبي',
        model: 'google/gemini-2.5-flash',
        books: ['الكامل في التاريخ', 'تاريخ الإسلام للذهبي'],
        pool_size: 1500, top_k: 150,
        system_prompt: 'استخرج الحوادث الفلكية مع توثيق اسم المراقب والمكان واليوم والشهر والسنة.'
      }
    );
    compTool = {
      enabled: true,
      tool_type: 'astronomy_hijri_sync',
      name: 'محرك التحقق الفلكي ومطابقة أطوار القمر وأيام الأسبوع',
      desc: 'مطابقة التواريخ وأطوار القمر وحسابات الكسوف والخسوف'
    };
  } else {
    // بناء وكلاء مخصصين تماماً لطبيعة المسألة المطروحة
    if (isHadith) {
      agents.push({
        name: 'وكيل دواوين السنة والتخريج الموسع',
        desc: 'تخريج الأحاديث من كتب السنة المسندة والأصول المعتمدة',
        model: 'google/gemini-2.5-flash',
        books: ['صحيح البخاري', 'صحيح مسلم', 'سنن أبي داود', 'جامع الترمذي', 'سنن النسائي', 'سنن ابن ماجه', 'مسند أحمد'],
        pool_size: 1500, top_k: 150,
        system_prompt: 'مهمتك استخراج نصوص الأحاديث والآثار من أصولها المسندة مع بيان موضعها وطرقها وأحكام الأئمة عليها.'
      });
      agents.push({
        name: 'وكيل أحكام الأئمة والعلل والرجال',
        desc: 'تتبع أقوال المتقدمين في التصحيح والتضعيف والعلل',
        model: 'google/gemini-2.5-flash',
        books: ['تهذيب التهذيب', 'الجرح والتعديل لابن أبي حاتم', 'العلل لابن أبي حاتم', 'الكامل في ضعفاء الرجال'],
        pool_size: 1500, top_k: 150,
        system_prompt: 'استخرج أقوال أئمة الحديث ونصوص أحكامهم الصريحة على الحديث ورواته دون تصرف.'
      });
    }

    if (isFiqh || agents.length === 0) {
      agents.push({
        name: 'وكيل المذاهب الفقهية الأربعة والأصول',
        desc: 'تحرير الفروع الفقهية وأقوال الأئمة المعتمدة في المذاهب',
        model: 'google/gemini-2.5-flash',
        books: ['المغني لابن قدامة', 'المجموع للنووي', 'رد المحتار لابن عابدين', 'التاج والإكليل للمواق', 'الإنصاف للمرداوي'],
        pool_size: 1500, top_k: 150,
        system_prompt: 'استخرج نصوص الفقهاء المتقدمين في المسألة مع بيان المعتمد والمآخذ الأصولية ومسالك التعليل.'
      });
    }

    if (isContemporary) {
      agents.push({
        name: 'وكيل النوازل والقيافة والقرائن الطبية المعاصرة',
        desc: 'مضاهاة مسالك القيافة والشبه بالقرائن القطعية المعاصرة (DNA)',
        model: 'google/gemini-2.5-flash',
        books: ['الطرق الحكمية لابن القيم', 'إعلام الموقعين', 'قرارات مجمع الفقه الإسلامي الدولي'],
        pool_size: 1500, top_k: 150,
        system_prompt: 'تخريج نازلة الاعتماد على الحمض النووي على نصوص الفقهاء في نفي الولد والقيافة والشبه وانتفاء الإمكان.'
      });
    }

    if (isTafsir) {
      agents.push({
        name: 'وكيل التفسير وأحكام القرآن',
        desc: 'استخراج دلالات الآيات وتفاسير السلف وأسباب النزول',
        model: 'google/gemini-2.5-flash',
        books: ['جامع البيان للطبري', 'الجامع لأحكام القرآن للقرطبي', 'أحكام القرآن للجصاص', 'أحكام القرآن لابن العربي'],
        pool_size: 1500, top_k: 150,
        system_prompt: 'استخرج تفاسير الآيات المتعلقة بالمسألة من أمهات كتب التفسير بالمأثور وأحكام القرآن.'
      });
    }
  }

  // توليد مراسٍ استرجاع متخصصة بحسب ألفاظ المسألة
  const words = rawText.split(/\s+/).filter(w => w.length > 3);
  const anchors = [
    rawText.slice(0, 80),
    ...words.slice(0, 5).map(w => `مسألة ${w}`)
  ];

  return {
    title: extractedTitle,
    desc: rawText || `دراسة تأصيلية مقارنة في مسألة: ${extractedTitle}`,
    extraction_capacity: 150,
    retrieval_anchors: anchors.slice(0, 6),
    director: {
      name: `مدير مشروع: ${extractedTitle.slice(0, 24)}`,
      model: 'google/gemini-2.5-flash',
      thinking: 'high',
      max_tokens: 262144,
      system_prompt: `أنت مدير هذا المشروع البحثي «${extractedTitle}». تشرف على قيادة الوكلاء، وتخريج الأدلة، وتفريغ النتائج في جداول قياسية محررة، مع الصلاحية العلمية الكاملة لتوجيه إعادة البحث والتحقق حتى 3 مرات قبل اعتماد النتائج.`
    },
    subagents_group: {
      name: `فريق تحقيق: ${extractedTitle.slice(0, 20)}`,
      desc: `مجموعة وكلاء مخصصة لمسألة: ${extractedTitle}`,
      agents: agents
    },
    internal_benchmark: {
      enabled: true,
      title: 'دراسة مرجعية مقارنة سابقة',
      author: 'أحد كبار الأئمة والمحققين',
      methodology: 'المقارنة والمضاهاة لفرز المتطابقات واستخراج الاستدراكات والإضافات الجديدة'
    },
    external_web_benchmark: {
      enabled: true,
      query: extractedTitle,
      domains: ['iifa-aifi.org', 'alukah.net', 'jstor.org'],
      prompt: 'البحث عن القرارات المجمعية والدراسات المعاصرة المقارنة'
    },
    computational_tool: compTool,
    output_formats: {
      csv_results: true,
      csv_benchmark: true,
      formatted_txt: true,
      academic_pdf: true
    }
  };
}

async function applyStudioBlueprint() {
  const applyBtn = document.getElementById('btnApplyStudioBlueprint');
  const origBtnContent = applyBtn ? applyBtn.innerHTML : '';

  if (applyBtn) {
    applyBtn.disabled = true;
    applyBtn.style.opacity = '0.85';
    applyBtn.innerHTML = `
      <svg class="spin-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation: spin 0.8s linear infinite;"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>
      <span style="margin-right: 8px;">جارٍ استخلاص واعتماد كروت المشروع وتأسيسه...</span>
    `;
  }

  try {
    // إذا لم يكن المخطط مستخرجاً كـ JSON بعد، نطلب استخلاصه واعتماده فوراً
    if (!currentStudioBlueprint) {
      let userContext = architectHistory
        .filter(m => m.role === 'user')
        .map(m => m.content)
        .join(' ');

      // إذا لم يتكلم المستخدم بعد، نأخذ ما كتب في حقل الإدخال
      if (!userContext.trim()) {
        const inputVal = (document.getElementById('architectUserInput')?.value || '').trim();
        if (inputVal) userContext = inputVal;
      }

      // محاولة سريعة لطلب الـ Blueprint من الخادم
      let savedKeys = {};
      try {
        savedKeys = readProviderKeys();
      } catch (e) { }
      const apiKey = savedKeys.openrouter || '';
      const chosenModel = document.getElementById('architectModelSelect')?.value || 'google/gemini-2.5-flash';

      const finalizationMessages = [
        ...architectHistory,
        {
          role: 'user',
          content: 'اعتمد الآن ما تم الاتفاق عليه ومناقشته في هذه المحاورة، وأخرج فوراً المخطط التنفيذي الكامل النهائي لجميع كروت المشروع والوكلاء محصوراً ككتلة JSON صحيحة بين ```json و ``` لتأسيس كروت المشروع فوراً.'
        }
      ];

      try {
        const res = await fetch('/api/projects/architect-dialog', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: finalizationMessages,
            planning_model: chosenModel,
            thinking_level: document.getElementById('architectThinkingSelect')?.value || 'medium',
            tavily_key: (typeof readTavilyKey === 'function' ? readTavilyKey() : '') || (savedKeys.tavily || ''),
            api_key: apiKey
          })
        });
        if (res.ok) {
          const data = await res.json();
          if (data.blueprint) {
            currentStudioBlueprint = data.blueprint;
            renderStudioCardsPreview(data.blueprint);
          }
        }
      } catch (callErr) {
        console.warn('Final blueprint fetch error:', callErr);
      }

      // إذا لم يتوفر بعد، نولد مخططاً فورياً تخصصياً فائق الدقة
      if (!currentStudioBlueprint) {
        currentStudioBlueprint = generateFallbackBlueprintFromContext(userContext);
        renderStudioCardsPreview(currentStudioBlueprint);
      }
    }

    const bp = currentStudioBlueprint;

    // فحص ما إذا كان التعديل لمشروع قائم أو لتأسيس مشروع جديد
    const existingProject = (currentPlanningProjectId && projectsList.find(p => p.id === currentPlanningProjectId))
      || (activeProjectId && projectsList.find(p => p.id === activeProjectId))
      || null;

    const targetProjectId = existingProject ? existingProject.id : (currentPlanningProjectId || ('proj_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7)));
    const targetGroupId = (existingProject && existingProject.linked_group_id) ? existingProject.linked_group_id : ('group_' + Date.now());

    // مطابقة أسماء كتب الوكلاء مع العناوين الحرفية في المخزن قبل التأسيس
    let booksToResolve = [];
    (bp.subagents_group?.agents || []).forEach(ag => {
      (ag.books || []).forEach(b => {
        const tr = (b || '').trim();
        if (tr && !booksToResolve.includes(tr)) booksToResolve.push(tr);
      });
    });

    let resolvedBookMap = {};
    if (booksToResolve.length > 0) {
      try {
        const bRes = await fetch('/api/books/resolve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ books: booksToResolve })
        });
        if (bRes.ok) {
          const bData = await bRes.json();
          (bData.results || []).forEach(r => {
            if (r.resolved) resolvedBookMap[r.input] = r.resolved;
          });
        }
      } catch (be) {
        console.warn('Auto book resolve on apply error:', be);
      }
    }

    // 1. تسجيل أو تحديث مجموعة الوكلاء المخصصة في agentGroups
    if (bp.subagents_group?.agents && bp.subagents_group.agents.length > 0) {
      let groups = window.agentGroups || [];
      if (groups.length === 0) {
        try {
          groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
        } catch (e) { }
      }

      const mappedAgents = bp.subagents_group.agents.map((ag, i) => {
        const canonicalBooks = (ag.books || []).map(b => resolvedBookMap[b] || b);
        const prompt = ag.system_prompt || ag.systemPrompt || ag.directive || ag.prompt || ag.desc || 'استخرج نصوص المسألة بدقة مع أرقام الأجزاء والصفحات.';
        return {
          id: ag.id || `agent_${Date.now()}_${i}`,
          name: ag.name || `وكيل ${i + 1}`,
          desc: ag.desc || 'استخراج نصوص الشاملة',
          model: ag.model || 'google/gemini-2.5-flash',
          enabled: true,
          active: true,
          books: canonicalBooks,
          booksScope: canonicalBooks,
          scope_summary: canonicalBooks.join('، ') || 'أمهات كتب التراث',
          pool_size: ag.pool_size || ag.poolSize || 1500,
          poolSize: ag.pool_size || ag.poolSize || 1500,
          top_k: ag.extract_count || ag.top_k || ag.topK || 150,
          topK: ag.extract_count || ag.top_k || ag.topK || 150,
          thinking: ag.thinking || 'medium',
          search_mode: ag.search_mode || 'hybrid',
          use_hybrid: (ag.search_mode || 'hybrid') !== 'semantic',
          temp: 0.2,
          max_tokens: 65536,
          maxTokens: 65536,
          system_prompt: prompt,
          systemPrompt: prompt
        };
      });

      const updatedGroup = {
        id: targetGroupId,
        name: bp.subagents_group.name || `فريق: ${(bp.title || 'المشروع').slice(0, 20)}`,
        desc: bp.subagents_group.desc || 'مجموعة وكلاء مخصصة لهذا المشروع البحثي',
        agents: mappedAgents
      };

      const existingIdx = groups.findIndex(g => g.id === targetGroupId);
      if (existingIdx >= 0) {
        groups[existingIdx] = updatedGroup;
      } else {
        groups.unshift(updatedGroup);
      }
      window.agentGroups = groups;
      localStorage.setItem(ownerStorageKey('almojtahed_agent_groups'), JSON.stringify(groups));
      if (typeof saveAgentGroups === 'function') {
        saveAgentGroups(groups);
      }
    }

    // 2. بناء كائن المشروع أو تحديثه في مكانه دون تكرار
    const directorPrompt = bp.director?.system_prompt || 'أنت مدير هذا المشروع البحثي، تشرف على قيادة الوكلاء وتفريغ النتائج في جداول قياسية. تمتلك الصلاحية العلمية الكاملة لتوجيه إعادة البحث والتحقق من صحة الحديث وتخريجه أو التأكد من نسبة قول أو أثر حتى 3 مرات قبل اعتماد النتائج وإصدار الحكم النهائي.';
    const chosenArchitectModel = document.getElementById('architectModelSelect')?.value || 'google/gemini-2.5-flash';

    let targetProject = existingProject;
    if (targetProject) {
      targetProject.title = bp.title || targetProject.title || 'مشروع بحثي';
      targetProject.desc = bp.desc || targetProject.desc || '';
      targetProject.architect_model = chosenArchitectModel;
      targetProject.architect_thinking = document.getElementById('architectThinkingSelect')?.value || targetProject.architect_thinking || 'medium';
      targetProject.architect_dialog = [...architectHistory];
      targetProject.architect_history = [...architectHistory];
      targetProject.blueprint = bp;
      targetProject.director = {
        name: bp.director?.name || targetProject.director?.name || 'مدير المشروع العام',
        model: bp.director?.model || targetProject.director?.model || 'google/gemini-2.5-flash',
        thinking: bp.director?.thinking || targetProject.director?.thinking || 'high',
        search_mode: bp.director?.search_mode || targetProject.director?.search_mode || 'hybrid',
        extract_count: bp.director?.extract_count || targetProject.director?.extract_count || bp.extraction_capacity || 120,
        max_tokens: bp.director?.max_tokens || targetProject.director?.max_tokens || 262144,
        system_prompt: directorPrompt
      };
      targetProject.use_hybrid = (targetProject.director.search_mode || 'hybrid') !== 'semantic';
      targetProject.linked_group_id = targetGroupId;
      targetProject.subagents_group = {
        id: targetGroupId,
        name: bp.subagents_group?.name || targetProject.subagents_group?.name || `فريق: ${(bp.title || targetProject.title).slice(0, 20)}`,
        desc: bp.subagents_group?.desc || '',
        agents: (bp.subagents_group?.agents && bp.subagents_group.agents.length > 0) ? (window.agentGroups?.find(g => g.id === targetGroupId)?.agents || []) : (targetProject.subagents_group?.agents || [])
      };
      if (bp.extraction_capacity) targetProject.extraction_capacity = bp.extraction_capacity;
      if (bp.retrieval_anchors) targetProject.retrieval_anchors = bp.retrieval_anchors;
      if (bp.internal_benchmark) targetProject.internal_benchmark = bp.internal_benchmark;
      if (bp.external_web_benchmark) targetProject.external_web_benchmark = bp.external_web_benchmark;
      if (bp.computational_tool) targetProject.computational_tool = bp.computational_tool;
      if (bp.output_formats) targetProject.output_formats = bp.output_formats;
    } else {
      targetProject = {
        id: targetProjectId,
        title: bp.title || 'مشروع بحثي جديد',
        desc: bp.desc || `مشروع بحثي: ${bp.title || 'غير معنون'}`,
        status: 'جاهز للتنفيذ',
        created_at: new Date().toISOString().split('T')[0],
        architect_model: chosenArchitectModel,
        architect_thinking: document.getElementById('architectThinkingSelect')?.value || 'medium',
        architect_dialog: [...architectHistory],
        architect_history: [...architectHistory],
        blueprint: bp,
        director: {
          name: bp.director?.name || 'مدير المشروع العام',
          model: bp.director?.model || 'google/gemini-2.5-flash',
          thinking: bp.director?.thinking || 'high',
          search_mode: bp.director?.search_mode || 'hybrid',
          extract_count: bp.director?.extract_count || bp.extraction_capacity || 120,
          max_tokens: bp.director?.max_tokens || 262144,
          system_prompt: directorPrompt
        },
        use_hybrid: (bp.director?.search_mode || 'hybrid') !== 'semantic',
        linked_group_id: targetGroupId,
        subagents_group: {
          id: targetGroupId,
          name: bp.subagents_group?.name || `فريق: ${(bp.title || 'المشروع').slice(0, 20)}`,
          desc: bp.subagents_group?.desc || '',
          agents: (bp.subagents_group?.agents && bp.subagents_group.agents.length > 0) ? (window.agentGroups?.find(g => g.id === targetGroupId)?.agents || []) : []
        },
        extraction_capacity: bp.extraction_capacity || 150,
        retrieval_anchors: bp.retrieval_anchors || [],
        internal_benchmark: bp.internal_benchmark || { enabled: false, title: '', author: '', methodology: '' },
        external_web_benchmark: bp.external_web_benchmark || { enabled: false, query: bp.title || '', domains: [], prompt: '' },
        computational_tool: bp.computational_tool || { enabled: false, tool_type: 'none', name: 'بدون أداة مساعدة', desc: 'لا يتطلب أدوات مساعدة خارجية' },
        output_formats: bp.output_formats || { csv_results: true, csv_benchmark: true, formatted_txt: true, academic_pdf: true }
      };
    }

    await saveProjectToStorage(targetProject);
    closeProjectPlanningModal();
    renderProjectsList();
    openProjectWorkspace(targetProject.id);
    showToast(existingProject ? '⚡ تم تحديث وحفظ بيانات وكروت المشروع بنجاح دون أي تكرار!' : '🎉 تم اعتماد الخطة وتأسيس المشروع الجديد بكافة بطاقاته وأدواته المخصصة بنجاح!');
  } catch (err) {
    console.error('Error applying blueprint:', err);
    showToast(`تعذر اعتماد الخطة: ${err.message}`);
  } finally {
    if (applyBtn) {
      applyBtn.disabled = false;
      applyBtn.style.opacity = '1';
      applyBtn.innerHTML = origBtnContent;
    }
  }
}

// تحديث كروت المشروع الحالي المفتوح فورياً بالخطة المعدلة دون إنشاء مشروع جديد
async function updateActiveProjectCardsFromBlueprint() {
  if (!activeProjectId) {
    return applyStudioBlueprint();
  }
  let bp = currentStudioBlueprint;
  if (!bp) {
    const curP = projectsList.find(p => p.id === activeProjectId);
    if (curP && curP.blueprint) {
      bp = curP.blueprint;
      currentStudioBlueprint = bp;
    }
  }
  if (!bp) {
    showToast('⚠️ لا يوجد مخطط حالي لاعتماده، حاور المهندس أولاً لتوليد الخطة');
    return;
  }
  const project = projectsList.find(p => p.id === activeProjectId);
  if (!project) return;

  // تحديث بيانات المشروع الحالي بالخطة المعدلة فورياً
  if (bp.title) project.title = bp.title;
  if (bp.desc) project.desc = bp.desc;
  if (bp.director) {
    project.director = {
      ...project.director,
      ...bp.director,
      max_tokens: bp.director.max_tokens || project.director?.max_tokens || 262144
    };
  }
  if (bp.extraction_capacity) project.extraction_capacity = bp.extraction_capacity;
  if (bp.retrieval_anchors) project.retrieval_anchors = bp.retrieval_anchors;
  if (bp.internal_benchmark) project.internal_benchmark = bp.internal_benchmark;
  if (bp.external_web_benchmark) project.external_web_benchmark = bp.external_web_benchmark;
  if (bp.computational_tool) project.computational_tool = bp.computational_tool;
  if (bp.output_formats) project.output_formats = bp.output_formats;

  // تحديث وكلاء المجموعة المرتبطة إن وجدت مع مطابقة الكتب وتفعيل الوكلاء فورياً
  if (bp.subagents_group?.agents && bp.subagents_group.agents.length > 0) {
    let booksToResolve = [];
    bp.subagents_group.agents.forEach(ag => {
      (ag.books || []).forEach(b => {
        const tr = (b || '').trim();
        if (tr && !booksToResolve.includes(tr)) booksToResolve.push(tr);
      });
    });

    let resolvedBookMap = {};
    if (booksToResolve.length > 0) {
      try {
        const bRes = await fetch('/api/books/resolve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ books: booksToResolve })
        });
        if (bRes.ok) {
          const bData = await bRes.json();
          (bData.results || []).forEach(r => {
            if (r.resolved) resolvedBookMap[r.input] = r.resolved;
          });
        }
      } catch (be) {
        console.warn('Auto book resolve on update error:', be);
      }
    }

    const mappedAgents = bp.subagents_group.agents.map((ag, i) => {
      const canonicalBooks = (ag.books || []).map(b => resolvedBookMap[b] || b);
      const prompt = ag.system_prompt || ag.systemPrompt || ag.directive || ag.prompt || ag.desc || 'استخرج نصوص المسألة بدقة مع أرقام الأجزاء والصفحات.';
      return {
        id: ag.id || `agent_${Date.now()}_${i}`,
        name: ag.name || `وكيل ${i + 1}`,
        desc: ag.desc || 'استخراج نصوص الشاملة',
        model: ag.model || 'google/gemini-2.5-flash',
        enabled: true,
        active: true,
        books: canonicalBooks,
        booksScope: canonicalBooks,
        scope_summary: canonicalBooks.join('، ') || 'أمهات كتب التراث',
        pool_size: ag.pool_size || ag.poolSize || 1500,
        poolSize: ag.pool_size || ag.poolSize || 1500,
        top_k: ag.extract_count || ag.top_k || ag.topK || 150,
        topK: ag.extract_count || ag.top_k || ag.topK || 150,
        thinking: ag.thinking || 'medium',
        search_mode: ag.search_mode || 'hybrid',
        use_hybrid: (ag.search_mode || 'hybrid') !== 'semantic',
        temp: 0.2,
        max_tokens: 65536,
        maxTokens: 65536,
        system_prompt: prompt,
        systemPrompt: prompt
      };
    });

    let groups = window.agentGroups || [];
    let gid = project.linked_group_id || `group_${project.id}`;
    project.linked_group_id = gid;
    let linkedGroup = groups.find(g => g.id === gid);
    if (!linkedGroup) {
      linkedGroup = {
        id: gid,
        name: bp.subagents_group.name || `فريق: ${(project.title || 'المشروع').slice(0, 20)}`,
        desc: bp.subagents_group.desc || 'مجموعة وكلاء مخصصة لهذا المشروع البحثي',
        agents: mappedAgents
      };
      groups.unshift(linkedGroup);
    } else {
      linkedGroup.name = bp.subagents_group.name || linkedGroup.name;
      linkedGroup.desc = bp.subagents_group.desc || linkedGroup.desc;
      linkedGroup.agents = mappedAgents;
    }

    project.subagents_group = {
      id: gid,
      name: linkedGroup.name,
      desc: linkedGroup.desc,
      agents: mappedAgents
    };

    window.agentGroups = groups;
    localStorage.setItem(ownerStorageKey('almojtahed_agent_groups'), JSON.stringify(groups));
    if (typeof saveAgentGroups === 'function') {
      saveAgentGroups(groups);
    }
  }

  // حفظ نموذج وسجل محادثة المهندس المعماري المحدثة
  project.architect_model = document.getElementById('architectModelSelect')?.value || project.architect_model || 'google/gemini-2.5-flash';
  project.architect_thinking = document.getElementById('architectThinkingSelect')?.value || project.architect_thinking || 'medium';
  project.architect_dialog = [...architectHistory];
  project.architect_history = [...architectHistory];
  project.blueprint = bp;

  await saveProjectToStorage(project);
  openProjectWorkspace(activeProjectId);
  closeProjectPlanningModal();
  showToast('⚡ تم مسح الكروت السابقة وتحديث كروت هذا المشروع فورياً بالخطة المعدلة!');
}

// مسح كروت المعاينة في استوديو التخطيط للبدء من جديد
function clearStudioBlueprintCards() {
  currentStudioBlueprint = null;
  const stream = document.getElementById('studioCardsStream');
  const statusBadge = document.getElementById('blueprintLiveStatus');
  const applyBtn = document.getElementById('btnApplyStudioBlueprint');
  const updateBtn = document.getElementById('btnUpdateActiveProjectCards');
  if (stream) {
    stream.innerHTML = `
      <div class="studio-empty-blueprint" id="studioEmptyBlueprint">
        <div class="empty-icon">🧭</div>
        <h4>غرفة التخطيط والهندسة المفتوحة</h4>
        <p>تم تفريغ ومسح الكروت بنجاح. حاور مهندس التخطيط لبناء خطة كروت جديدة وتحديثها فورياً.</p>
      </div>
    `;
  }
  if (statusBadge) {
    statusBadge.textContent = 'تم المسح 🔄';
    statusBadge.className = 'p-status-pill';
  }
  if (applyBtn) applyBtn.disabled = true;
  if (updateBtn) updateBtn.disabled = true;
  showToast('🗑️ تم مسح كروت المخطط في الاستوديو بنجاح.');
}

// مسح كروت المشروع الحالي المخصصة وتفريغها لتحديثها فورياً
async function resetCurrentProjectCards() {
  if (!activeProjectId) return;
  const project = projectsList.find(p => p.id === activeProjectId);
  if (!project) return;

  const confirmed = await showConfirmDialog({
    title: 'تأكيد مسح وتفريغ كروت المشروع',
    message: 'هل تود مسح كروت هذا المشروع المخصصة لإعادة بنائها فورياً؟\nسيتم تفريغ التخصيصات لتتمكن من إنشاء وضبط الكروت من جديد أو تطبيق خطة المهندس.',
    confirmText: 'نعم، مسح وتفريغ الكروت',
    cancelText: 'تراجع',
    danger: true,
    icon: 'refresh-cw'
  });
  if (!confirmed) return;

  // تفريغ التخصيصات وإعادة تعيين القيم النظيفة
  project.director = {
    name: 'مدير المشروع العام',
    model: 'google/gemini-2.5-flash',
    thinking: 'medium',
    system_prompt: ''
  };
  project.internal_benchmark = { enabled: false, title: '', author: '', methodology: '' };
  project.external_web_benchmark = {
    enabled: true,
    query: `historical solar eclipses NASA ${project.title}`,
    domains: ['nasa.gov', 'eclipse.gsfc.nasa.gov', 'timeanddate.com'],
    prompt: 'التحقق الحي من وقائع الكسوف والخسوف عبر موقع ناسا والمواقع الفلكية العالمية.'
  };
  project.computational_tool = {
    enabled: true,
    tool_type: 'web_nasa_catalog',
    desc: 'التحقق المرجعي الحي عبر موقع ناسا والمواقع المتخصصة بالحساب الفلكي عبر أداة البحث في النت.'
  };

  await saveProjectToStorage(project);
  openProjectWorkspace(activeProjectId);
  showToast('🔄 تم مسح كروت المشروع وتحديث الواجهة فورياً! يمكنك الآن حوار المهندس أو ضبطها.');
}


// =============================================================================
// إدارة المشاريع يدوياً وتصديرها واستيرادها
// =============================================================================

function openNewManualProjectModal() {
  const modal = document.getElementById('projectManualModal');
  if (!modal) return;

  const titleInput = document.getElementById('manualProjectTitle');
  const descInput = document.getElementById('manualProjectDesc');
  if (titleInput) titleInput.value = '';
  if (descInput) descInput.value = '';

  // تعبئة القائمة المنسدلة بالمجموعات المتاحة
  const groupSelect = document.getElementById('manualProjectLinkedGroup');
  if (groupSelect) {
    let groups = window.agentGroups || [];
    if (groups.length === 0) {
      try {
        groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
      } catch (e) { }
    }
    if (groups.length > 0) {
      groupSelect.innerHTML = groups.map(g => {
        const count = g.agents ? g.agents.length : 0;
        return `<option value="${g.id}">${escapeHtml(g.name)} (${count} وكلاء)</option>`;
      }).join('');
    } else {
      groupSelect.innerHTML = '<option value="">المجموعة التراثية الافتراضية</option>';
    }
  }

  modal.style.display = 'flex';
}

function closeManualProjectModal() {
  const modal = document.getElementById('projectManualModal');
  if (modal) modal.style.display = 'none';
}

async function saveNewManualProject() {
  const title = (document.getElementById('manualProjectTitle')?.value || '').trim();
  if (!title) {
    showToast('يرجى كتابة عنوان المشروع أولاً');
    return;
  }
  const desc = (document.getElementById('manualProjectDesc')?.value || '').trim();
  const directorModel = document.getElementById('manualProjectDirectorModel')?.value || 'google/gemini-2.5-flash';
  const linkedGroupId = document.getElementById('manualProjectLinkedGroup')?.value || '';
  const hasInternal = document.getElementById('manualProjectInternalBench')?.checked !== false;
  const hasExternal = document.getElementById('manualProjectExternalBench')?.checked !== false;
  const hasComp = document.getElementById('manualProjectCompTool')?.checked !== false;

  // جلب بيانات المجموعة المرتبطة
  let groups = window.agentGroups || [];
  if (groups.length === 0) {
    try {
      groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
    } catch (e) { }
  }
  const linkedGroup = groups.find(g => g.id === linkedGroupId) || (groups.length > 0 ? groups[0] : null);

  const newProject = {
    id: 'proj_' + Date.now(),
    title: title,
    desc: desc || `مشروع بحثي: ${title}`,
    status: 'جاهز للتنفيذ',
    created_at: new Date().toISOString().split('T')[0],
    director: {
      name: `مدير مشروع: ${title.slice(0, 24)}`,
      model: directorModel,
      thinking: 'high',
      system_prompt: `أنت مدير هذا المشروع البحثي «${title}». دورك الإشراف على عمليات الاستخراج التراثية من الشاملة، ومضاهاة المقارنات المرجعية، وتفريغ النتائج في جداول دقيقة ومحررة.`
    },
    linked_group_id: linkedGroup ? linkedGroup.id : '',
    subagents_group: linkedGroup ? {
      name: linkedGroup.name,
      desc: linkedGroup.desc,
      agents: linkedGroup.agents
    } : { name: 'الفريق العام', agents: [] },
    internal_benchmark: {
      enabled: hasInternal,
      title: 'دراسة مرجعية سابقة',
      author: 'أحد أعلام التراث',
      methodology: 'المقارنة والمضاهاة لفرز المتطابقات والاستدراكات الجديدة'
    },
    external_web_benchmark: {
      enabled: hasExternal,
      query: title,
      domains: ['jstor.org', 'brill.com', 'alukah.net'],
      prompt: 'استخراج الأبحاث والدراسات المعاصرة المقارنة'
    },
    computational_tool: {
      enabled: hasComp,
      tool_type: 'astronomy_hijri_sync',
      desc: 'مطابقة التواريخ الهجرية والحسابات والتقويم'
    },
    output_formats: {
      csv_results: true,
      csv_benchmark: true,
      formatted_txt: true,
      academic_pdf: true
    }
  };

  await saveProjectToStorage(newProject);
  closeManualProjectModal();
  renderProjectsList();
  openProjectWorkspace(newProject.id);
  showToast('🎉 تم تأسيس المشروع وحفظه وفتح مساحة العمل بنجاح!');
}

async function deleteProject(projectId, event) {
  if (event) event.stopPropagation();
  const p = projectsList.find(x => x.id === projectId);
  const name = p ? p.title : 'هذا المشروع';

  const confirmed = await showConfirmDialog({
    title: 'تأكيد حذف المشروع البحثي',
    message: `هل أنت متأكد من رغبتك في حذف المشروع: «${name}»؟ لا يمكن التراجع عن هذا الإجراء وسيتم حذف كافة ملفاته ومحاور بحثه.`,
    confirmText: 'نعم، احذف المشروع',
    cancelText: 'إلغاء',
    danger: true,
    icon: 'folder-x'
  });

  if (!confirmed) {
    return;
  }

  projectsList = projectsList.filter(x => x.id !== projectId);
  safeSaveProjectsLocalStorage();

  // تنظيف أي مخلفات لمجموعات الوكلاء التابعة للمشروع المحذوف
  try {
    const rawGroups = localStorage.getItem(ownerStorageKey('almojtahed_agent_groups'));
    if (rawGroups) {
      let gList = JSON.parse(rawGroups);
      const targetGid = p?.linked_group_id || p?.subagents_group?.id || `group_${projectId}`;
      gList = gList.filter(g => g.id !== targetGid && g.id !== `group_${projectId}`);
      localStorage.setItem(ownerStorageKey('almojtahed_agent_groups'), JSON.stringify(gList));
      if (typeof agentGroups !== 'undefined') agentGroups = gList;
    }
    const currentChatGid = localStorage.getItem('almojtahed_selected_chat_agent_group');
    if (currentChatGid === `group_${projectId}` || (p && (currentChatGid === p.linked_group_id || currentChatGid === p.subagents_group?.id))) {
      localStorage.removeItem('almojtahed_selected_chat_agent_group');
      const chatGroupSelect = document.getElementById('chatAgentGroupSelect');
      if (chatGroupSelect) chatGroupSelect.value = '';
    }
  } catch (e) { }

  try {
    await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });
  } catch (e) { }

  if (typeof loadAgentGroups === 'function') {
    await loadAgentGroups();
  }
  if (typeof populateChatAgentGroupsDropdown === 'function') {
    populateChatAgentGroupsDropdown();
  }

  renderProjectsList();
  showToast('تم حذف المشروع وكافة مخلفاته بنجاح');
}

function exportProjectsData() {
  let groups = window.agentGroups || [];
  if (groups.length === 0) {
    try {
      groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
    } catch (e) { }
  }

  // إذا كان هناك مشروع مفتوح نشط، نقوم بحفظ حالته الحالية مع سجل المحادثة أولاً
  if (activeProjectId) {
    saveCurrentProjectWorkspaceState();
  }

  const exportBundle = {
    app: 'almojtahed_system',
    version: '2.0',
    export_type: 'comprehensive_backup',
    exported_at: new Date().toISOString(),
    projects_count: projectsList.length,
    agent_groups_count: groups.length,
    projects: projectsList.map(p => {
      // التأكد من تضمين كافة معلومات المشروع والوكلاء وسجل المهندس ونموذجه
      return {
        ...p,
        architect_dialog: p.architect_dialog || p.architect_history || (p.id === activeProjectId ? architectHistory : []),
        architect_model: p.architect_model || (p.id === activeProjectId ? document.getElementById('architectModelSelect')?.value : '') || 'google/gemini-2.5-flash'
      };
    }),
    agent_groups: groups
  };

  const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportBundle, null, 2));
  const dlAnchor = document.createElement('a');
  dlAnchor.setAttribute('href', dataStr);
  dlAnchor.setAttribute('download', `almojtahed_complete_projects_backup_${new Date().toISOString().split('T')[0]}.json`);
  dlAnchor.click();
  dlAnchor.remove();
  showToast('💾 تم تصدير حزمة المشاريع الكاملة (المشاريع، الوكلاء، نماذج وسجلات المهندس) بنجاح!');
}

// تصدير مشروع واحد محدد كملف JSON مستقل
function shareActiveProject() {
  const project = projectsList.find(item => item.id === activeProjectId);
  if (!project || typeof openSharePicker !== 'function') {
    if (typeof showToast === 'function') showToast('افتح المشروع أولاً', true);
    return;
  }
  openSharePicker('project', project.id, project.title || 'المشروع');
}

function exportSingleProject(projectId, event) {
  if (event && typeof event.stopPropagation === 'function') {
    event.stopPropagation();
  }
  const p = projectsList.find(item => item.id === projectId);
  if (!p) {
    if (typeof showToast === 'function') showToast('المشروع غير موجود لتصديره', true);
    return;
  }

  // إذا كان هذا المشروع هو المفتوح حالياً، نحفظ حالته أولاً
  if (activeProjectId === projectId && typeof saveCurrentProjectWorkspaceState === 'function') {
    saveCurrentProjectWorkspaceState();
  }

  // نجلب مجموعة الوكلاء المرتبطة بهذا المشروع إن وجدت
  let groups = window.agentGroups || [];
  if (groups.length === 0) {
    try {
      groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
    } catch (e) { }
  }
  const linkedGroupId = p.subagents_group?.id || p.linked_group_id || `group_${p.id}`;
  const linkedGroup = groups.find(g => g.id === linkedGroupId) || p.subagents_group || null;

  const projectData = {
    ...p,
    architect_dialog: p.architect_dialog || p.architect_history || (p.id === activeProjectId ? architectHistory : []),
    architect_model: p.architect_model || (p.id === activeProjectId ? document.getElementById('architectModelSelect')?.value : '') || 'google/gemini-2.5-flash'
  };

  const exportPayload = {
    app: 'almojtahed_system',
    version: '2.0',
    export_type: 'single_project',
    exported_at: new Date().toISOString(),
    project: projectData,
    projects: [projectData],
    agent_groups: linkedGroup ? [linkedGroup] : [],
    // للتوافق المباشر مع استيراد المشروع:
    id: projectData.id,
    title: projectData.title,
    desc: projectData.desc,
    ...projectData
  };

  const cleanTitle = (p.title || 'project').slice(0, 40).replace(/[^a-zA-Z0-9\u0600-\u06FF_-]/g, '_');
  const filename = `project_${cleanTitle}_${new Date().toISOString().split('T')[0]}.json`;

  const jsonStr = JSON.stringify(exportPayload, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  if (typeof showToast === 'function') {
    showToast(`تم حفظ مشروع «${(p.title || '').slice(0, 35)}» في جهازك`);
  }
}

function triggerImportProjectFile() {
  const input = document.getElementById('projectImportFileInput');
  if (input) input.click();
}

async function handleProjectFileImport(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async function (e) {
    try {
      const imported = JSON.parse(e.target.result);
      let projectsToImport = [];
      let groupsToImport = [];

      // 1. التعامل الشامل مع جميع صيغ الملفات (حزمة كاملة، مشروع مفرد، مصفوفة مشاريع)
      if (imported) {
        if (Array.isArray(imported.projects) && imported.projects.length > 0) {
          projectsToImport = imported.projects;
        } else if (imported.project && typeof imported.project === 'object') {
          projectsToImport = [imported.project];
        } else if (Array.isArray(imported)) {
          projectsToImport = imported;
        } else if (imported.id && typeof imported.id === 'string' && (imported.title || imported.director || imported.subagents_group)) {
          projectsToImport = [imported];
        }

        if (Array.isArray(imported.agent_groups)) {
          groupsToImport = imported.agent_groups;
        } else if (imported.agent_group && typeof imported.agent_group === 'object') {
          groupsToImport = [imported.agent_group];
        }
      }

      // 2. استيراد وتثبيت مجموعات الوكلاء أولاً
      let currentGroups = window.agentGroups || [];
      if (currentGroups.length === 0) {
        try {
          currentGroups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
        } catch (err) { }
      }

      groupsToImport.forEach(newG => {
        const idx = currentGroups.findIndex(g => g.id === newG.id);
        if (idx >= 0) {
          currentGroups[idx] = newG;
        } else {
          currentGroups.push(newG);
        }
      });

      // 3. استيراد المشاريع والتأكد من استخراج وتثبيت وكلاء كل مشروع وسجلات المهندس ونموذجه
      for (const proj of projectsToImport) {
        // التأكد من استخراج مجموعة الوكلاء المخصصة لهذا المشروع وتسجيلها
        if (proj.subagents_group && Array.isArray(proj.subagents_group.agents) && proj.subagents_group.agents.length > 0) {
          const gid = proj.linked_group_id || proj.subagents_group.id || `group_${proj.id}`;
          proj.linked_group_id = gid;
          proj.subagents_group.id = gid;

          const gIdx = currentGroups.findIndex(g => g.id === gid);
          const groupObj = {
            id: gid,
            name: proj.subagents_group.name || `فريق: ${proj.title?.slice(0, 20)}`,
            desc: proj.subagents_group.desc || `مجموعة وكلاء مخصصة لمشروع: ${proj.title}`,
            agents: proj.subagents_group.agents
          };

          if (gIdx >= 0) {
            currentGroups[gIdx] = groupObj;
          } else {
            currentGroups.push(groupObj);
          }
        }

        // الحفاظ على سجل المحادثة مع المهندس والنموذج
        if (proj.architect_history && !proj.architect_dialog) {
          proj.architect_dialog = proj.architect_history;
        }

        // معالجة تصحيحية ذكية: إذا كان المشروع يحمل عنوان "رصد الحوادث الفلكية..." ناتجاً عن القالب القديم
        // بينما محادثة المهندس المرفقة معه تناقش موضوعاً آخر (مثل نفي ولد الفراش والحمض النووي)
        if (proj.title && proj.title.includes('رصد الحوادث الفلكية') && Array.isArray(proj.architect_dialog) && proj.architect_dialog.length > 1) {
          const userMsgs = proj.architect_dialog.filter(m => m.role === 'user').map(m => m.content).join(' ');
          if ((userMsgs.includes('الحمض النووي') || userMsgs.includes('ولد الفراش') || userMsgs.includes('اللعان')) && !userMsgs.includes('كسوف') && !userMsgs.includes('خسوف')) {
            proj.title = "نفي ولد الفراش بتحليل الحمض النووي (DNA) دون لعان: دراسة فقهية تأصيلية مقارنة بمصادر ما قبل 1300 هجري";
            proj.desc = "دراسة تأصيلية مقارنة تستقصي نفي ولد الفراش بغير اللعان وتخريج حكم تحليل الحمض النووي مع التحقق من الأحاديث والآثار من مصادرها الأصلية والحكم عليها وبيان درجتها.";
            if (proj.blueprint) {
              proj.blueprint.title = proj.title;
              proj.blueprint.desc = proj.desc;
            }
          }
        }

        await saveProjectToStorage(proj);
      }

      // 4. حفظ وتثبيت المجموعات في التخزين المحلي وخادم المنظومة
      window.agentGroups = currentGroups;
      localStorage.setItem(ownerStorageKey('almojtahed_agent_groups'), JSON.stringify(currentGroups));
      if (typeof saveAgentGroups === 'function') {
        saveAgentGroups(currentGroups);
      }

      renderProjectsList();
      if (typeof renderGroupsTable === 'function') {
        renderGroupsTable();
      }
      if (typeof populateChatAgentGroupsDropdown === 'function') {
        populateChatAgentGroupsDropdown();
      }

      showToast(`🎉 تم استيراد ${projectsToImport.length} مشروعاً بكافة وكلائهم وسجلات مهندس المشروع بنجاح!`);
    } catch (err) {
      console.error('Import error:', err);
      showToast(`خطأ في استيراد الملف: ${err.message}`);
    }
  };
  reader.readAsText(file, 'UTF-8');
}

// =============================================================================
// محرك تشغيل المشروع البحثي (Live Execution Engine)
// =============================================================================

async function runCurrentProjectExecution() {
  if (!activeProjectId) return;
  saveCurrentProjectWorkspaceState();

  const project = projectsList.find(p => p.id === activeProjectId);
  if (!project) return;

  const resultsPanel = document.getElementById('projectRunResultsContainer');
  const spinner = document.getElementById('projectRunSpinner');
  const statusMsg = document.getElementById('projectRunStatusMsg');
  const actionBtns = document.getElementById('projectRunActionBtns');
  const liveContent = document.getElementById('projectRunLiveContent');

  if (resultsPanel) resultsPanel.style.display = 'block';
  if (spinner) spinner.style.display = 'inline-block';
  if (actionBtns) actionBtns.style.display = 'none';
  const timerEl = document.getElementById('projectRunTimer');
  if (timerEl) {
    timerEl.style.display = 'inline-block';
    timerEl.textContent = '⏱️ 00:00';
  }

  let elapsedSec = 0;
  const isDirect = (project.agent_dispatch_mode === 'direct');
  if (statusMsg) {
    statusMsg.textContent = isDirect
      ? 'المرحلة 1: جارٍ مسح نصوص الشاملة وتمريرها مباشرة لمدير المشروع (نمط موحد سريع 🎯)...'
      : 'المرحلة 1: جارٍ مسح نصوص الشاملة وتوجيه الوكلاء المتخصصين (نمط توكيلي موزع ⚡)...';
  }

  const execTimerInterval = setInterval(() => {
    elapsedSec++;
    const mins = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
    const secs = String(elapsedSec % 60).padStart(2, '0');
    if (timerEl) timerEl.textContent = `⏱️ ${mins}:${secs}`;

    if (statusMsg) {
      if (isDirect) {
        if (elapsedSec >= 7 && elapsedSec < 18) {
          statusMsg.textContent = 'المرحلة 2: يقوم مدير المشروع بصياغة التقرير وتفريغ الجداول التراثية...';
        } else if (elapsedSec >= 18) {
          statusMsg.textContent = 'المرحلة 3: استكمال التقرير النهائي وثبت المصادر والمراجع التراثية...';
        }
      } else {
        if (elapsedSec >= 10 && elapsedSec < 35) {
          statusMsg.textContent = 'المرحلة 2: يقوم الوكلاء المساعدون الآن بتلخيص كتبهم عبر نماذجهم المخصصة بالتوازي...';
        } else if (elapsedSec >= 35 && elapsedSec < 65) {
          statusMsg.textContent = 'المرحلة 3: يدمج مدير المشروع خلاصات الوكلاء ويحرر المقارنة وثبت المصادر...';
        } else if (elapsedSec >= 65) {
          statusMsg.textContent = 'المرحلة 4: استكمال توليد الجداول الضخمة وثبت المصادر والمراجع التراثية...';
        }
      }
    }
  }, 1000);

  resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  // 1. استخراج النتائج من الشاملة بموجب توجيه مدير المشروع
  let webBenchmarkResults = [];
  const tavilyKey = readTavilyKey();

  try {
    // التحقق من تفعيل البحث الخارجي
    if (project.external_web_benchmark?.enabled && tavilyKey) {
      statusMsg.textContent = 'المرحلة 2: استرجاع جداول وكتالوجات المقارنة عبر محرك البحث في الويب...';
      const isAstro = project.computational_tool?.enabled && (project.computational_tool?.tool_type === 'astronomy_hijri_sync' || project.computational_tool?.tool_type === 'web_nasa_catalog');
      const defaultQuery = isAstro ? `historical solar eclipse NASA ${project.title}` : `${project.title} دراسة وبحث`;
      const extQuery = project.external_web_benchmark.query || defaultQuery;
      const defaultDomains = isAstro ? ['nasa.gov', 'eclipse.gsfc.nasa.gov', 'timeanddate.com'] : [];
      const extDomains = (project.external_web_benchmark.domains && project.external_web_benchmark.domains.length > 0)
        ? project.external_web_benchmark.domains
        : defaultDomains;

      try {
        const tavilyRes = await fetch('/api/tavily/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: tavilyKey,
            query: extQuery,
            include_domains: extDomains,
            max_results: 5
          })
        });
        if (tavilyRes.ok) {
          const tavilyData = await tavilyRes.json();
          webBenchmarkResults = tavilyData.results || [];
        }
      } catch (we) {
        console.warn('Tavily search error during execution:', we);
      }
    }

    if (statusMsg) {
      statusMsg.textContent = isDirect
        ? 'المرحلة 2: معالجة مدير المشروع للنتائج وصياغة مصفوفة التحقيق (النمط المباشر)...'
        : 'المرحلة 2: معالجة الوكلاء ومدير المشروع للنتائج وصياغة مصفوفة التحقيق والمطابقة...';
    }

    // استدعاء نموذج مدير المشروع لتركيب التقرير والجداول
    let savedKeys = {};
    try {
      savedKeys = readProviderKeys();
    } catch (e) { }
    const apiKey = savedKeys.openrouter || '';

    const directorPrompt = project.director?.system_prompt || 'أنت مدير المشروع البحثي، فرغ النتائج في جدول مرتب دقيق مع أرقام الأجزاء والصفحات والمطابقة.';
    const directorModel = project.director?.model || 'google/gemini-2.5-flash';

    // تجهيز مجموعة الوكلاء المرتبطة لربط استخراج نصوص الشاملة
    let linkedGroupPayload = null;
    let groups = window.agentGroups || [];
    if (groups.length === 0) {
      try {
        groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
      } catch (e) { }
    }
    if (project.linked_group_id) {
      linkedGroupPayload = groups.find(g => g.id === project.linked_group_id) || null;
    }
    if (!linkedGroupPayload || !linkedGroupPayload.agents || linkedGroupPayload.agents.length === 0) {
      linkedGroupPayload = project.subagents_group || null;
    }

    // بناء قسم أدلة الويب المسترجعة من موقع ناسا والمواقع الفلكية
    let webEvidenceSection = '';
    if (webBenchmarkResults && webBenchmarkResults.length > 0) {
      webEvidenceSection = `
═══════════════════════════════════════════════════════════
🌐 [معطيات وأدلة التحقق المباشر من موقع ناسا (NASA) والمواقع المتخصصة بالحساب عبر البحث في الويب]:
${webBenchmarkResults.map((r, i) => `${i + 1}. المصدر: ${r.title}\n   الرابط: ${r.url}\n   المعلومات المستخرجة: ${r.content}`).join('\n\n')}

توجيه قطعي لمدير المشروع:
- اعتمد مباشرة على معطيات موقع ناسا والمواقع الفلكية المتخصصة المسترجعة أعلاه لإثبات واقعة الكسوف أو نفيها في عمود التحقق، مع ذكر الرابط والبيانات الفلكية الموثقة.
═══════════════════════════════════════════════════════════
`;
    }

    const isAstronomy = project.computational_tool?.enabled && (project.computational_tool?.tool_type === 'astronomy_hijri_sync' || project.computational_tool?.tool_type === 'web_nasa_catalog');
    const isCharts = project.computational_tool?.enabled && (project.computational_tool?.tool_type === 'charts_metrics');
    const isIsnad = project.computational_tool?.enabled && (project.computational_tool?.tool_type === 'hadith_isnad_tree');
    const isMarkmap = project.computational_tool?.enabled && (project.computational_tool?.tool_type === 'markmap_mindmap' || project.computational_tool?.tool_type === 'coc_markmap' || project.computational_tool?.category === 'تشجير ومفاهيم');

    let toolDirectives = '';
    if (isAstronomy) {
      toolDirectives = `- [بوابة التحقق الفلكي]: الجدول المطلوب يشمل عمود التحقق الفلكي ومطابقة أطوار القمر وتواريخ ناسا وتفاصيل التصحيف النسخي. يُمنع كتابة عبارات تسويف بل انقل الحكم الحتمي.`;
    } else if (isCharts) {
      toolDirectives = `- [بوابة المؤشرات والشارتات البيانية]: يجب إدراج جدول إحصائي مقارن ومستقل للنسب، يتضمن عموداً صريحاً بالنسب المئوية الرقمية (مثال: | المذهب أو القول | النسبة المئوية (%) | عدد الشواهد | الحكم |) بقيم رقمية واضحة (مثل: 60% أو 30% أو 10%) لتقوم أداة الشارتات بتمثيلها بيانياً وتفاعلياً فوراً، كما يمكنك تضمين كتلة رسم بياني بصيغة chart:
\`\`\`chart
{
  "type": "bar",
  "title": "مؤشر ترجيح الأقوال الفقهية",
  "labels": ["القول بالجواز", "القول بالمنع", "التوقف"],
  "data": [60, 30, 10]
}
\`\`\``;
    } else if (isIsnad) {
      toolDirectives = `- [بوابة دراسة الأسانيد]: وثّق الطرق والمدار، ثم أخرج كتلة \`\`\`force3d لشجرة إسناد فقط. اذكر كل حديث أو أثر في عقدة role حديث أو أثر. role: حديث|أثر|نبي|صحابي|تابعي|تابع التابعين|مدار|طريق|ضعيف|كتاب. السهم من الأدنى إلى الأعلى: source الكتاب أو التلميذ و target الشيخ أو الصحابي أو النبي. المدار عقدة واحدة. لا تخلطها بشجرة أقوال.`;
    } else if (isMarkmap) {
      toolDirectives = `- [بوابة التشجير]: صغ Markmap للأقوال، ثم كتلة \`\`\`force3d لنوع واحد فقط: تشجير إسناد، أو تشجير خلاف علمي (مسألة ثم قول ثم قائل ثم دليل، من أي علم)، أو تشجير استدلال، أو تشجير مناقشة، أو تشجير خلاف عام (مسألة ثم قول ثم دليل ثم مناقشة ثم إشكال ثم جواب أو رد ثم ترجيح). source الأعلى و target الفرع. لا ترسم إسناداً إلا إذا طُلب.`;
    } else {
      toolDirectives = `- [التحقيق العلمي الدقيق]: تفريغ المسائل وأقوال المصنفين ومذاهبهم وأدلتهم مع التوثيق الحرفي بالأجزاء والصفحات من أمهات المصادر، وبيان الراجح والجامع للمسألة.`;
    }

    const execUserPrompt = `
مشروع بحثي: ${project.title}
وصف المشروع: ${project.desc}
الكتاب المرجعي للمقارنة: ${project.internal_benchmark?.enabled ? (project.internal_benchmark?.title || 'دراسة سابقة') : 'بدون كتاب مقارنة مرجعي'}
الأداة المساعدة: ${project.computational_tool?.enabled ? `${project.computational_tool?.name || 'أداة مساعدة'} (${project.computational_tool?.desc || ''})` : 'بدون أداة مساعدة (بحث فقهي/تحليلي بحت)'}

${webEvidenceSection}

توجيهات التحقيق والجدولة الشاملة:
- لقد تم استخراج المقاطع التوثيقية من أمهات المصادر المستهدفة في الشاملة.
- مهمتك كمدير للمشروع: استيعاب كـافـة الشواهد المستخرجة وتفريغ نصوص المسألة كاملة في جدول مفصل وشامل مرتب بالسياق الزمني أو المذهبي أو الموضوعي.
- اعتمد حصراً على أمهات المصادر التراثية. كل إحالة تُكتب بالصيغة القياسية وحدها: اسم الكتاب (الجزء-الصفحة) بأرقام لاتينية. الصحيح: مجموع الفتاوى (2-368). وللكتاب ذي الجزء الواحد: زاد المستقنع ص(50). تُمنع الشرطة المائلة، والأرقام العربية، وتقديم الصفحة على الجزء، ووضع اسم الكتاب داخل القوس.
- أتبعه بجدول مقارنة أو تحرير فقهي/علمي وخاتمة علمية محررة بالنتائج والاستدراكات.
- 🔴 إلـزامـي وحـتـمـي في ختام التقرير: يجب إفراد جدول توثيقي شامل بعنوان «📚 ثبت المصادر والمراجع المعتمدة في المشروع» يستوعب كافة الكتب والمصادر التي استُخرجت منها نصوص المسألة أو عُزيت إليها الأقوال، متضمناً الأعمدة الببليوغرافية الكاملة:
| م | اسم الكتاب المعتمد | المصنف وسنة وفاته الهجرية | المحقق أو الشارح | رقم الطبعة وسنتها | دار النشر والناشر وبياناته | بلد النشر | رقم الكتاب بالشاملة (#BookID) |
يُمنع إغفال أي كتاب نُقلت منه معلومة، مع استيفاء كافة بيانات التوثيق الأكاديمي.
`;

    const chatRes = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: directorModel,
        provider: 'openrouter',
        api_key: apiKey,
        thinking_level: project.director?.thinking || 'medium',
        messages: [
          { role: 'user', content: execUserPrompt }
        ],
        system_prompt: directorPrompt,
        temperature: 0.2,
        top_k: project.extraction_capacity || 150,
        extraction_capacity: project.extraction_capacity || 150,
        retrieval_anchors: (project.retrieval_anchors && Array.isArray(project.retrieval_anchors)) ? project.retrieval_anchors : [],
        max_tokens: project.director?.max_tokens || 65536,
        providers: savedKeys,
        agent_group: linkedGroupPayload,
        agent_dispatch_mode: project.agent_dispatch_mode || 'parallel',
        use_hybrid: (project.use_hybrid !== undefined) ? !!project.use_hybrid : isProjectHybridSearchEnabled,
        computational_tool: project.computational_tool || { enabled: false }
      })
    });

    let executionOutputText = '';
    if (chatRes.ok) {
      const chatData = await chatRes.json();
      executionOutputText = chatData.reply || '';
    } else {
      let errDetail = `HTTP ${chatRes.status}`;
      try {
        const errJson = await chatRes.json();
        errDetail = errJson.detail || errJson.error || errDetail;
      } catch (e) { }
      throw new Error(`تعذر استدعاء النموذج (${errDetail})`);
    }

    // حفظ البيانات المنتجة للجولة 1
    const initialRound = {
      round: 1,
      name: 'المرحلة 1: المسح والتأسيس والجدولة المبدئية',
      output: executionOutputText,
      executedAt: new Date().toLocaleString('ar-SA')
    };

    currentProjectRunData = {
      projectId: project.id,
      projectTitle: project.title,
      executedAt: new Date().toLocaleString('ar-SA'),
      directorModel: directorModel,
      rounds: [initialRound],
      messages: [
        { role: 'user', content: execUserPrompt },
        { role: 'assistant', content: executionOutputText }
      ],
      rawOutput: executionOutputText,
      webBenchmark: webBenchmarkResults
    };

    // حفظ دائم في كائن المشروع وعلى الخادم
    project.execution_data = currentProjectRunData;
    const pIdx = projectsList.findIndex(p => p.id === activeProjectId);
    if (pIdx !== -1) {
      projectsList[pIdx].execution_data = currentProjectRunData;
      await saveProjectToStorage(projectsList[pIdx]);
    }

    if (spinner) spinner.style.display = 'none';
    if (timerEl) {
      const finalMins = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
      const finalSecs = String(elapsedSec % 60).padStart(2, '0');
      timerEl.textContent = `✅ اكتمل في ${finalMins}:${finalSecs}`;
    }
    if (statusMsg) statusMsg.textContent = `✅ اكتملت الجولة الأولى بنجاح عبر «${project.director?.name || 'مدير المشروع'}»`;

    // عرض مخرجات الجولة وأزرار المتابعة
    renderProjectExecutionView();

  } catch (err) {
    if (spinner) spinner.style.display = 'none';
    if (timerEl) timerEl.textContent = `⚠️ توقف`;
    if (statusMsg) statusMsg.textContent = `فشل تشغيل المشروع: ${err.message}`;
    showToast(`خطأ في تنفيذ المشروع: ${err.message}`);
  } finally {
    clearInterval(execTimerInterval);
  }
}

// =============================================================================
// عرض وإدارة جولات تنفيذ المشروع التراكمية (Rounds View & Execution)
// =============================================================================

function renderProjectExecutionView() {
  if (!currentProjectRunData) return;

  const resultsPanel = document.getElementById('projectRunResultsContainer');
  const spinner = document.getElementById('projectRunSpinner');
  const statusMsg = document.getElementById('projectRunStatusMsg');
  const actionBtns = document.getElementById('projectRunActionBtns');
  const liveContent = document.getElementById('projectRunLiveContent');

  if (resultsPanel) resultsPanel.style.display = 'block';
  if (spinner) spinner.style.display = 'none';

  const rounds = (currentProjectRunData.rounds && currentProjectRunData.rounds.length > 0)
    ? currentProjectRunData.rounds
    : [
      {
        round: 1,
        name: 'المرحلة 1: المسح والتأسيس والجدولة المبدئية',
        output: currentProjectRunData.rawOutput,
        executedAt: currentProjectRunData.executedAt
      }
    ];

  const nextRoundNum = rounds.length + 1;

  if (statusMsg) {
    statusMsg.innerHTML = `<span>✅ الجولات المنجزة: <strong>${rounds.length}</strong> جولات عبر «${currentProjectRunData.directorModel || 'مدير المشروع'}»</span>`;
  }

  // عرض أزرار العمليات التفاعلية
  if (actionBtns) {
    actionBtns.style.display = 'flex';
    actionBtns.style.flexWrap = 'wrap';
    actionBtns.style.alignItems = 'center';

    let continueBtnText = `استكمال جولة البحث والتحقيق (الجولة ${nextRoundNum}) ⏩`;
    let continueBtnTitle = `استكمال الجولة رقم ${nextRoundNum} بناءً على مخرجات وتكليفات مدير المشروع والوكلاء في الجولة ${rounds.length}`;
    if (rounds.length >= 3) {
      continueBtnText = `إضافة جولة استدراكية إضافية (الجولة ${nextRoundNum}) ⏩`;
      continueBtnTitle = `تم إنجاز الجولات الثلاث؛ انقر لإضافة جولة استدراكية جديدة`;
    }

    actionBtns.innerHTML = `
      <button type="button" class="btn-primary-gradient" onclick="continueProjectExecutionRound()" id="btnContinueRound" title="${continueBtnTitle}">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/><line x1="19" y1="5" x2="19" y2="19"/></svg>
        <span>${continueBtnText}</span>
      </button>
      <button type="button" class="btn-primary-gradient" onclick="transferProjectResultToChat()" title="نقل نتائج وتفاصيل هذا البحث إلى الشات الذكي لمدارستها ومناقشتها وتطويرها">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span>مدارسة ومناقشة</span>
      </button>
      <button type="button" class="btn-secondary-action" onclick="runCurrentProjectExecution()" title="إعادة تشغيل استخراج وبحث المشروع من البداية (جولة 1 جديدة ومستقلة)">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
        <span>إعادة البدء من جديد</span>
      </button>
      <button type="button" class="btn-primary-action btn-academic-print" onclick="printAcademicPaper()" style="background: linear-gradient(135deg, #B45309, #D97706); color: #fff; font-weight: 700; box-shadow: 0 2px 6px rgba(180, 83, 9, 0.3);" title="طباعة وإخراج البحث الأكاديمي المحكم وفق المعايير الشرعية الفاخرة">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
        <span>🖨️ طباعة البحث المحكم (PDF)</span>
      </button>
      <button type="button" class="btn-secondary-action" onclick="downloadProjectReportHtml()" title="تصدير تقرير كامل بصيغة HTML تفاعلي">
        <span>تصدير HTML</span>
      </button>
      <button type="button" class="btn-secondary-action" onclick="downloadProjectReportPdf()" title="تصدير تقرير PDF أكاديمي">
        <span>تصدير PDF</span>
      </button>
      <button type="button" class="btn-secondary-action" onclick="downloadProjectRunReportTxt()" title="تحميل التقرير بنص ماركداون">
        <span>تقرير Markdown</span>
      </button>
      <button type="button" class="btn-secondary-action" onclick="downloadProjectResultsCsv('results')">
        <span>جدول النتائج CSV</span>
      </button>
      <button type="button" class="btn-secondary-action" onclick="downloadProjectResultsCsv('benchmark')">
        <span>جدول المقارنات CSV</span>
      </button>
    `;
  }

  // تجميع وعرض محتوى الجولات
  let finalHtml = '';
  if (currentProjectRunData.webBenchmark && currentProjectRunData.webBenchmark.length > 0) {
    finalHtml += `
      <div class="web-bench-results-box" style="background: var(--bg-muted); padding: 12px 16px; border-radius: var(--radius-sm); margin-bottom: 16px; border: 1px solid var(--border-subtle);">
        <strong style="color: var(--accent-clay);">🌐 بيانات المقارنة المرجعية المسترجعة من Tavily AI:</strong>
        <ul style="margin: 6px 0 0 20px; font-size: 13px;">
          ${currentProjectRunData.webBenchmark.map(r => `<li><a href="${r.url}" target="_blank" style="color: var(--text-main); font-weight:600;">${escapeHtml(r.title)}</a>: ${escapeHtml(r.content?.slice(0, 160))}...</li>`).join('')}
        </ul>
      </div>
    `;
  }

  rounds.forEach((r, idx) => {
    const isLatest = (idx === rounds.length - 1);
    finalHtml += `
      <div class="execution-round-card" style="margin-bottom: 24px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); overflow: hidden; background: var(--bg-surface); box-shadow: var(--shadow-sm);">
        <div style="background: var(--bg-muted); padding: 12px 18px; border-bottom: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-weight: 700; color: var(--accent-clay); font-size: 15px;">📌 ${escapeHtml(r.name || `الجولة رقم ${r.round}`)}</span>
            <span style="font-size: 12px; color: var(--text-muted);">(${escapeHtml(r.executedAt || '')})</span>
          </div>
          <span class="badge-status" style="background: rgba(16,185,129,0.15); color: #10b981; padding: 3px 12px; border-radius: 12px; font-size: 12px; font-weight: 700;">
            ${isLatest ? 'الجولة الأحدث (مكتملة ✓)' : 'جولة معتمدة وموثقة ✓'}
          </span>
        </div>
        <div class="markdown-body" style="padding: 20px; font-size: 14.5px; line-height: 1.8; direction: rtl; text-align: right;">
          ${(typeof formatMarkdown === 'function') ? formatMarkdown(r.output || '') : (typeof marked !== 'undefined' ? marked.parse(r.output || '') : (r.output || '').replace(/\n/g, '<br>'))}
        </div>
      </div>
    `;
  });

  if (liveContent) liveContent.innerHTML = finalHtml;

  // تفعيل تصدير CSV وضبط اتجاه RTL لكافة جداول الماركداون
  if (liveContent) {
    enhanceChatTablesWithCsvExport(liveContent);
    enhanceProjectCitationsWithBookReader(liveContent);
  }

  // تفعيل استخراج المؤشرات والشارتات البيانية التلقائي من جداول المقارنات
  if (typeof autoRenderProjectResultCharts === 'function' && liveContent) {
    autoRenderProjectResultCharts(liveContent);
  }

  // تفعيل استخراج شجرة الأسانيد وشبكات الرواة التفاعلية
  if (typeof autoRenderProjectIsnadTrees === 'function' && liveContent) {
    autoRenderProjectIsnadTrees(liveContent);
  }

  // تفعيل استخراج ورسم خرائط وتشجير Markmap التفاعلية
  if (typeof autoRenderProjectResultMarkmaps === 'function' && liveContent) {
    autoRenderProjectResultMarkmaps(liveContent);
  }

  if (typeof window.renderForce3dBlocks === 'function' && liveContent) {
    window.renderForce3dBlocks(liveContent);
  }
}

// دالة تغليف وضبط اتجاه الجداول من اليمين لليسار مع إضافة شريط تصدير CSV
function enhanceChatTablesWithCsvExport(container) {
  if (!container) return;
  const tables = container.querySelectorAll('table');
  tables.forEach(table => {
    table.setAttribute('dir', 'rtl');
    table.style.direction = 'rtl';
    table.style.textAlign = 'right';

    // إذا كان الجدول مغلفاً مسبقاً، نكتفي بضبط اتجاهه
    if (table.closest('.chat-table-wrapper')) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'chat-table-wrapper';
    wrapper.setAttribute('dir', 'rtl');

    const header = document.createElement('div');
    header.className = 'chat-table-header';
    header.setAttribute('dir', 'rtl');

    const rowCount = Math.max(0, table.querySelectorAll('tbody tr').length);
    const countBadge = rowCount > 0 ? ` (${rowCount} سجل)` : '';

    header.innerHTML = `
      <span class="chat-table-title" style="direction: rtl;">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3h18v18H3zM3 9h18M3 15h18M9 3v18M15 3v18"/></svg>
        <span>جدول البيانات المستخرجة والمقارنات${countBadge}</span>
      </span>
      <button type="button" class="chat-table-csv-btn" onclick="downloadTableAsCSV(this)" title="تحميل الجدول بصيغة CSV لفتحه في Microsoft Excel">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        <span>تحميل CSV</span>
      </button>
    `;

    const scrollDiv = document.createElement('div');
    scrollDiv.className = 'chat-table-scroll';
    scrollDiv.setAttribute('dir', 'rtl');

    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(header);
    wrapper.appendChild(scrollDiv);
    scrollDiv.appendChild(table);
  });
}
window.enhanceChatTablesWithCsvExport = enhanceChatTablesWithCsvExport;

// =============================================================================
// تفعيل فحص وتصفح النصوص المنقولة في الكتاب الأصلي (Verify Citations with Reader)
// =============================================================================

function openProjectCitationReader(btnEl) {
  if (!btnEl) return;
  const book = (btnEl.getAttribute('data-book') || '').trim();
  const part = (btnEl.getAttribute('data-part') || '').trim();
  const page = (btnEl.getAttribute('data-page') || '').trim();
  const quote = (btnEl.getAttribute('data-quote') || '').trim();

  if (!book && !page) {
    if (typeof showToast === 'function') showToast('تعذر استخراج بيانات الإحالة');
    return;
  }

  // تحويل الأرقام العربية المشرقية إن وجدت
  const convDigits = (str) => {
    if (!str) return '';
    const ar = '٠١٢٣٤٥٦٧٨٩';
    return String(str).replace(/[٠-٩]/g, d => ar.indexOf(d));
  };

  const cleanPart = convDigits(part);
  const cleanPage = parseInt(convDigits(page), 10) || null;

  if (typeof openBookReader === 'function') {
    openBookReader({
      book_title: book,
      part: cleanPart,
      page_num: cleanPage,
      highlight: quote
    });
  } else {
    console.error('openBookReader is not available');
    if (typeof showToast === 'function') showToast('نافذة القارئ غير مهيأة');
  }
}
window.openProjectCitationReader = openProjectCitationReader;

function citationToWesternDigits(value) {
  return String(value || '')
    .replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))
    .replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
}

function cleanCitationBookName(raw) {
  let book = String(raw || '')
    .replace(/\u0640/g, '')
    .replace(/[\u{1F300}-\u{1FAFF}]/gu, ' ')
    .replace(/^(?:ص|صفحة|جـ?|جزء|مجلد)\s*[0-9٠-٩]+\s*[\.،:\-–]*\s*/g, '')
    .replace(/^(?:المصدر|المرجع|انظر|راجع|يُنظر|ينظر|تخريج(?:\s+حديث)?[^:：]*|كتاب|في|جاء\s+في|وجاء\s+في|قال|من)\s*[:：\s\-–]*/g, '')
    .replace(/^[«»"'“”\s،,:：\-–\(\)\[\]]+|[\s،,:：\-–\(\)\[\]]+$/g, '')
    .replace(/\s*\([^)]{0,50}\)?\s*$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  const segments = book.split(/[،,]/).map(part => part.trim()).filter(Boolean);
  if (segments.length > 1 && (segments[0].match(/[\u0600-\u06FF]/g) || []).length >= 6) {
    book = segments[0];
  }
  if (book.length > 90) book = book.slice(0, 90).replace(/\s+\S*$/, '').trim();
  const arabicLetters = (book.match(/[\u0600-\u06FF]/g) || []).length;
  if (arabicLetters < 3 || book.length > 90) return '';
  if (/^(?:ج|ص|جزء|صفحة|الجزء|الصفحة|مجلد)$/.test(book)) return '';
  return book;
}

function parseCitationLocation(rawInside) {
  const text = citationToWesternDigits(rawInside).replace(/\u0640/g, '');
  const vol = '(?:الجزء|جزء|مجلد|مج|ج)';
  const page = '(?:الصفحة|صفحة|ص)';
  const gap = '[\\s\\.\\:：]*';
  const bridge = '[\\s\\.\\:：،,\\/\\-–]*';
  let match = text.match(new RegExp(vol + gap + '(\\d{1,4})' + bridge + page + gap + '(\\d{1,4})'));
  if (match) {
    return { part: match[1], page: match[2], index: match.index };
  }
  match = text.match(/(?:^|[\s،,\-–:])(\d{1,3})\s*\/\s*(\d{1,4})(?!\d)/);
  if (match && /[\u0600-\u06FF]{3,}/.test(text.slice(0, match.index + 1))) {
    return { part: match[1], page: match[2], index: match.index };
  }
  return null;
}

function bookBeforeCitation(text, index) {
  const windowText = text.slice(Math.max(0, index - 260), index);
  const quoted = windowText.match(/[«"“]([^»"”\n]{3,80})[»"”]\s*$/);
  if (quoted) return quoted[1];
  const pieces = windowText.split(/\n|•|(?:المصدر|المرجع)\s*[:：]/);
  return pieces[pieces.length - 1] || '';
}

function nearestCitationQuote(text, index) {
  const before = text.slice(Math.max(0, index - 280), index);
  const match = before.match(/«([^»]{4,150})»|"([^"]{4,150})"|“([^”]{4,150})”/g);
  if (!match) return '';
  const last = match[match.length - 1];
  return last.replace(/^[«"“]|[»"”]$/g, '').trim();
}

function findCanonicalCitationSpans(text) {
  const spans = [];
  const pattern = /«([^»\n]{3,140})»([^\n«]{0,90}?)(?:ص\s*\(\s*([0-9٠-٩۰-۹]{1,4})\s*\)|\(\s*([0-9٠-٩۰-۹]{1,3})\s*[-–]\s*([0-9٠-٩۰-۹]{1,4})\s*\))|([\u0600-\u06FF]{2,}(?:\s+[\u0600-\u06FF]{2,}){0,8}) \(([0-9]{1,3})-([0-9]{1,4})\)|([\u0600-\u06FF]{2,}(?:\s+[\u0600-\u06FF]{2,}){0,8}) ص\(([0-9]{1,4})\)/g;
  let match;
  while ((match = pattern.exec(text))) {
    const book = cleanCitationBookName(match[1] || match[6] || match[9]);
    if (!book) continue;
    const quotedPage = match[3];
    const barePage = match[10];
    const titleSource = match[1] || match[6] || match[9] || '';
    const titleAt = titleSource.lastIndexOf(book);
    const start = match.index + (titleAt > 0 ? titleAt : 0);
    spans.push({
      start,
      end: match.index + match[0].length,
      book,
      part: (quotedPage || barePage) ? '' : citationToWesternDigits(match[4] || match[7]),
      page: citationToWesternDigits(quotedPage || barePage || match[5] || match[8]),
      quote: nearestCitationQuote(text, match.index)
    });
  }
  return spans;
}

function findCitationSpans(text) {
  const spans = [];
  const taken = [];
  const remember = (span) => {
    if (taken.some(item => span.start < item.end && span.end > item.start)) return;
    taken.push(span);
    spans.push(span);
  };
  findCanonicalCitationSpans(text).forEach(remember);

  for (let i = 0; i < text.length; i++) {
    const open = text[i];
    if (open !== '(' && open !== '[' && open !== '（') continue;
    const close = open === '[' ? ']' : (open === '（' ? '）' : ')');
    let depth = 1;
    let end = -1;
    const limit = Math.min(text.length, i + 380);
    for (let j = i + 1; j < limit; j++) {
      if (text[j] === open) depth++;
      else if (text[j] === close || (close === ')' && text[j] === '）')) {
        depth--;
        if (depth === 0) {
          end = j;
          break;
        }
      }
    }
    if (end < 0) continue;
    const inside = text.slice(i + 1, end);
    const location = parseCitationLocation(inside);
    if (!location) {
      i = end;
      continue;
    }
    const insideBook = cleanCitationBookName(inside.slice(0, location.index));
    const book = insideBook || cleanCitationBookName(bookBeforeCitation(text, i));
    if (!book || !location.page) {
      i = end;
      continue;
    }
    remember({
      start: i,
      end: end + 1,
      book,
      part: location.part || '',
      page: location.page,
      quote: nearestCitationQuote(text, i)
    });
    i = end;
  }

  const loose = /(?:الجزء|جزء|مجلد|مج|ج)\u0640?\s*[\.\:：]?\s*[0-9٠-٩۰-۹]{1,4}[\s\.\:：،,\/\-–\u0640]*(?:الصفحة|صفحة|ص)\u0640?\s*[\.\:：]?\s*[0-9٠-٩۰-۹]{1,4}/g;
  let looseMatch;
  while ((looseMatch = loose.exec(text))) {
    const location = parseCitationLocation(looseMatch[0]);
    const book = cleanCitationBookName(bookBeforeCitation(text, looseMatch.index));
    if (!location || !book) continue;
    remember({
      start: looseMatch.index,
      end: looseMatch.index + looseMatch[0].length,
      book,
      part: location.part || '',
      page: location.page,
      quote: nearestCitationQuote(text, looseMatch.index)
    });
  }
  return spans.sort((a, b) => a.start - b.start);
}

function citationVerifyButton(span) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn-verify-citation';
  button.setAttribute('data-book', span.book);
  button.setAttribute('data-part', span.part || '');
  button.setAttribute('data-page', span.page || '');
  button.setAttribute('data-quote', (span.quote || '').slice(0, 100));
  const partLabel = span.part ? `جـ: ${span.part}` : '';
  const pageLabel = span.page ? `ص: ${span.page}` : '';
  const locInfo = [partLabel, pageLabel].filter(Boolean).join(' ');
  button.title = `تصفح في الكتاب الأصلي «${span.book}» ${locInfo} للتحقق من صحة المنقول 📖`;
  button.setAttribute('aria-label', 'تصفح في الكتاب الأصلي');
  button.textContent = '📖';
  button.addEventListener('click', () => openProjectCitationReader(button));
  return button;
}

function citationMcpButton(span) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn-mcp-verify';
  button.setAttribute('data-book', span.book);
  button.setAttribute('data-part', span.part || '');
  button.setAttribute('data-page', span.page || '');
  button.setAttribute('data-quote', (span.quote || '').slice(0, 160));
  const partLabel = span.part ? `جـ: ${span.part}` : '';
  const pageLabel = span.page ? `ص: ${span.page}` : '';
  const locInfo = [partLabel, pageLabel].filter(Boolean).join(' ');
  button.title = `تحقق حرفي (MCP) من «${span.book}» ${locInfo}`;
  button.setAttribute('aria-label', 'تحقق حرفي');
  button.textContent = '🔍';
  button.addEventListener('click', () => {
    if (typeof openMcpLiteralVerify !== 'function') return;
    openMcpLiteralVerify({
      book: button.getAttribute('data-book'),
      part: button.getAttribute('data-part'),
      page: button.getAttribute('data-page'),
      quote: button.getAttribute('data-quote')
    });
  });
  return button;
}

function enhanceProjectCitationsWithBookReader(container) {
  if (!container) return;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const value = node.nodeValue || '';
      if (!/[صججزءصفحةمجلد0-9٠-٩۰-۹]/.test(value)) return NodeFilter.FILTER_REJECT;
      const parent = node.parentElement;
      if (!parent || parent.closest('button, a, script, style, code, pre, .btn-verify-citation, .btn-mcp-verify')) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  const textNodes = [];
  while (walker.nextNode()) textNodes.push(walker.currentNode);

  textNodes.forEach(node => {
    const text = node.nodeValue || '';
    let prefix = '';
    let previous = node.previousSibling;
    while (previous && prefix.length < 180) {
      const chunk = previous.nodeType === Node.TEXT_NODE ? previous.nodeValue : (previous.textContent || '');
      prefix = chunk + prefix;
      previous = previous.previousSibling;
    }
    const spans = findCitationSpans(prefix + text)
      .filter(span => span.end > prefix.length)
      .map(span => ({
        ...span,
        start: Math.max(0, span.start - prefix.length),
        end: span.end - prefix.length
      }));
    if (!spans.length) return;
    if (
      spans.length === 1 &&
      spans[0].end === text.length &&
      node.nextSibling &&
      node.nextSibling.classList &&
      node.nextSibling.classList.contains('btn-verify-citation')
    ) {
      const bookButton = node.nextSibling;
      const magnifier = bookButton.nextSibling;
      if (magnifier && magnifier.classList && magnifier.classList.contains('btn-mcp-verify')) {
        magnifier.remove();
      }
      return;
    }
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    spans.forEach(span => {
      fragment.appendChild(document.createTextNode(text.slice(cursor, span.end)));
      fragment.appendChild(citationVerifyButton(span));
      cursor = span.end;
    });
    if (cursor < text.length) fragment.appendChild(document.createTextNode(text.slice(cursor)));
    node.parentNode.replaceChild(fragment, node);
  });
}
window.enhanceProjectCitationsWithBookReader = enhanceProjectCitationsWithBookReader;

// دالة استكمال الجولة التالية لمدير المشروع
async function continueProjectExecutionRound() {
  if (!activeProjectId || !currentProjectRunData) {
    showToast('يرجى تشغيل الجولة الأولى أولاً');
    return;
  }

  const project = projectsList.find(p => p.id === activeProjectId);
  if (!project) return;

  const spinner = document.getElementById('projectRunSpinner');
  const statusMsg = document.getElementById('projectRunStatusMsg');
  const actionBtns = document.getElementById('projectRunActionBtns');
  const liveContent = document.getElementById('projectRunLiveContent');

  const currentRounds = (currentProjectRunData.rounds && currentProjectRunData.rounds.length > 0)
    ? [...currentProjectRunData.rounds]
    : [
      {
        round: 1,
        name: 'المرحلة 1: المسح والتأسيس والجدولة المبدئية',
        output: currentProjectRunData.rawOutput,
        executedAt: currentProjectRunData.executedAt
      }
    ];

  const currentRoundNum = currentRounds.length;
  const nextRoundNum = currentRoundNum + 1;

  if (spinner) spinner.style.display = 'inline-block';
  if (actionBtns) actionBtns.style.display = 'none';

  const timerEl = document.getElementById('projectRunTimer');
  if (timerEl) {
    timerEl.style.display = 'inline-block';
    timerEl.textContent = '⏱️ 00:00';
  }

  let elapsedSec = 0;
  const isDirect = (project.agent_dispatch_mode === 'direct');
  if (statusMsg) {
    statusMsg.textContent = isDirect
      ? `المرحلة: جارٍ تنفيذ الجولة رقم (${nextRoundNum}) بنمط مباشر سريع 🎯...`
      : `المرحلة: جارٍ تنفيذ الجولة رقم (${nextRoundNum}) واستكمال التكليفات مع الوكلاء بالتوازي ⚡...`;
  }

  const roundTimerInterval = setInterval(() => {
    elapsedSec++;
    const mins = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
    const secs = String(elapsedSec % 60).padStart(2, '0');
    if (timerEl) timerEl.textContent = `⏱️ ${mins}:${secs}`;

    if (statusMsg) {
      if (isDirect) {
        if (elapsedSec >= 7) {
          statusMsg.textContent = `المرحلة: مدير المشروع يحرر مخرجات الجولة رقم (${nextRoundNum}) بنمط مباشر سريع...`;
        }
      } else {
        if (elapsedSec >= 10 && elapsedSec < 35) {
          statusMsg.textContent = `المرحلة: الوكلاء ينفذون تكليفات الجولة (${nextRoundNum}) بالتوازي في OpenRouter...`;
        } else if (elapsedSec >= 35) {
          statusMsg.textContent = `المرحلة: مدير المشروع يستكمل دمج تقارير الوكلاء وصياغة الجولة (${nextRoundNum})...`;
        }
      }
    }
  }, 1000);

  // إضافة فقاعة انتظار تفاعلية في أسفل قائمة المخرجات
  const waitingDivId = 'waiting_round_' + Date.now();
  if (liveContent) {
    const waitEl = document.createElement('div');
    waitEl.id = waitingDivId;
    waitEl.style.cssText = 'padding: 16px; margin-top: 20px; background: var(--bg-muted); border-radius: var(--radius-md); border-right: 4px solid var(--accent-clay);';
    waitEl.innerHTML = `
      <div style="display: flex; align-items: center; gap: 10px; font-weight: 700; color: var(--text-main);">
        <span class="status-indicator-spinner" style="display: inline-block; width: 15px; height: 15px;"></span>
        <span>مدير المشروع ينفذ الجولة رقم (${nextRoundNum}) ويوجه الوكلاء لسد الفجوات التوثيقية والتحقيق في المسائل...</span>
      </div>
    `;
    liveContent.appendChild(waitEl);
    waitEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  try {
    let savedKeys = {};
    try {
      savedKeys = readProviderKeys();
    } catch (e) { }
    const apiKey = savedKeys.openrouter || '';

    const directorPrompt = project.director?.system_prompt || 'أنت مدير المشروع البحثي، فرغ النتائج في جدول مرتب دقيق مع أرقام الأجزاء والصفحات والمطابقة.';
    const directorModel = project.director?.model || 'google/gemini-2.5-flash';

    // تجهيز مجموعة الوكلاء
    let linkedGroupPayload = null;
    let groups = window.agentGroups || [];
    if (groups.length === 0) {
      try {
        groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
      } catch (e) { }
    }
    if (project.linked_group_id) {
      linkedGroupPayload = groups.find(g => g.id === project.linked_group_id) || null;
    }
    if (!linkedGroupPayload || !linkedGroupPayload.agents || linkedGroupPayload.agents.length === 0) {
      linkedGroupPayload = project.subagents_group || null;
    }

    // إعداد سياق الرسائل التراكمي
    let messages = currentProjectRunData.messages ? [...currentProjectRunData.messages] : [];
    if (messages.length === 0) {
      messages = [
        { role: 'user', content: `مشروع بحثي: ${project.title}\nوصف المشروع: ${project.desc}` },
        { role: 'assistant', content: currentProjectRunData.rawOutput }
      ];
    }

    const continueUserPrompt = `
طلب استكمال جولة البحث والتحقيق العلمي [الجولة رقم ${nextRoundNum}]:

أيها المدير التخصصي للمشروع («${project.director?.name || 'مدير المشروع'}»):
استناداً إلى تقريرك ومخرجاتك وتكليفاتك في الجولة السابقة (الجولة ${currentRoundNum})، والمسائل التي أشرت إلى وجوب استكمالها أو التحقق منها والتدقيق فيها فقهياً أو حديثياً أو تاريخياً وفلكياً:

1. باشر فوراً تنفيذ [الجولة التحريرية والتحقيقية رقم ${nextRoundNum}]:
   - وجّه الوكلاء لسد الفجوات التوثيقية، وتخريج الأحاديث وبيان عللها ورجالها، والتثبت من نسبة الأقوال والآثار إلى أصحابها في أمهات المصادر.
   - حقق في التواريخ والوقائع والمطابقات، واستخرج الشواهد الإضافية لتأكيد ما هو متردد أو محتمل.
2. أضف النتائج والاستدراكات الجديدة إلى الجداول المعتمدة مع إبراز ما تم إثباته وحسمه في هذه الجولة.
3. قدّم تقرير الجولة رقم ${nextRoundNum} بصياغة علمية محررة رصينة، واذكر صراحة ما إذا كانت هذه الجولة قد حسمت أهداف المشروع تماماً. كل إحالة في هذه الجولة بالصيغة القياسية وحدها: اسم الكتاب (الجزء-الصفحة) مثل مجموع الفتاوى (2-368)، أو اسم الكتاب ص(50) إن كان جزءاً واحداً. واحرص في الجولة الختامية على استيفاء «📚 ثبت المصادر والمراجع المعتمدة في المشروع» بكافة بيانات الطبعات والمحققين ودور النشر وأرقام الشاملة.
`;

    messages.push({ role: 'user', content: continueUserPrompt });

    const chatRes = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: directorModel,
        provider: 'openrouter',
        api_key: apiKey,
        thinking_level: project.director?.thinking || 'medium',
        messages: messages,
        system_prompt: directorPrompt,
        temperature: 0.2,
        top_k: project.extraction_capacity || 150,
        extraction_capacity: project.extraction_capacity || 150,
        retrieval_anchors: (project.retrieval_anchors && Array.isArray(project.retrieval_anchors)) ? project.retrieval_anchors : [],
        max_tokens: project.director?.max_tokens || 65536,
        providers: savedKeys,
        agent_group: linkedGroupPayload,
        agent_dispatch_mode: project.agent_dispatch_mode || 'parallel',
        use_hybrid: (project.use_hybrid !== undefined) ? !!project.use_hybrid : isProjectHybridSearchEnabled,
        computational_tool: project.computational_tool || { enabled: false }
      })
    });

    const waitEl = document.getElementById(waitingDivId);
    if (waitEl) waitEl.remove();

    if (!chatRes.ok) {
      let errDetail = `HTTP ${chatRes.status}`;
      try {
        const errJson = await chatRes.json();
        errDetail = errJson.detail || errJson.error || errDetail;
      } catch (e) { }
      throw new Error(`تعذر استدعاء النموذج (${errDetail})`);
    }

    const chatData = await chatRes.json();
    const newRoundOutput = chatData.reply || '';

    // تحديث المحادثة
    messages.push({ role: 'assistant', content: newRoundOutput });
    currentProjectRunData.messages = messages;

    // إضافة الجولة
    currentRounds.push({
      round: nextRoundNum,
      name: `المرحلة ${nextRoundNum}: استكمال التحقيق والتثبت التوثيقي والمطابقة`,
      output: newRoundOutput,
      executedAt: new Date().toLocaleString('ar-SA')
    });
    currentProjectRunData.rounds = currentRounds;

    // تحديث النص الخام التراكمي
    currentProjectRunData.rawOutput = currentRounds.map(r => `## 📌 تقرير الجولة رقم ${r.round} (${r.executedAt})\n\n${r.output}`).join('\n\n---\n\n');

    // حفظ دائم في كائن المشروع وعلى الخادم
    project.execution_data = currentProjectRunData;
    saveCurrentProjectWorkspaceState();
    const pIdx = projectsList.findIndex(p => p.id === activeProjectId);
    if (pIdx !== -1) {
      projectsList[pIdx].execution_data = currentProjectRunData;
      await saveProjectToStorage(projectsList[pIdx]);
    }

    if (spinner) spinner.style.display = 'none';
    if (timerEl) {
      const finalMins = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
      const finalSecs = String(elapsedSec % 60).padStart(2, '0');
      timerEl.textContent = `✅ الجولة ${nextRoundNum} (${finalMins}:${finalSecs})`;
    }
    if (statusMsg) statusMsg.textContent = `✅ اكتملت الجولة رقم (${nextRoundNum}) بنجاح عبر «${project.director?.name || 'مدير المشروع'}»`;

    // تحديث العرض والأزرار
    renderProjectExecutionView();
    showToast(`🎉 تم إنجاز الجولة رقم ${nextRoundNum} ودمج استدراكاتها بنجاح!`);

  } catch (err) {
    const waitEl = document.getElementById(waitingDivId);
    if (waitEl) waitEl.remove();
    if (spinner) spinner.style.display = 'none';
    if (timerEl) timerEl.textContent = `⚠️ توقف`;
    if (statusMsg) statusMsg.textContent = `فشل استكمال الجولة: ${err.message}`;
    if (actionBtns) actionBtns.style.display = 'flex';
    showToast(`خطأ في استكمال الجولة: ${err.message}`);
  } finally {
    clearInterval(roundTimerInterval);
  }
}

// =============================================================================
// دوال تصدير الجداول والملفات النصية
// =============================================================================

function downloadProjectResultsCsv(type = 'results') {
  if (!currentProjectRunData || !currentProjectRunData.rawOutput) {
    showToast('لا توجد بيانات مستخرجة لتحميلها');
    return;
  }

  const raw = currentProjectRunData.rawOutput;
  // استخراج أول جدول ماركداون
  const tables = raw.match(/\|(.+)\|[\r\n]+\|[-:| ]+\|[\r\n]+((?:\|.+|[\r\n]+)+)/g);

  if (!tables || tables.length === 0) {
    // في حال تعذر العثور على جدول ماركداون، تصدير نصوص الشواهد كـ CSV
    const csvContent = "\uFEFFالمسألة,التفاصيل,المصدر\n" +
      `"${currentProjectRunData.projectTitle}","تقرير النتائج المستخرجة","المجتهد"`;
    triggerCsvDownload(csvContent, `${type}_results.csv`);
    return;
  }

  const tableMarkdown = (type === 'benchmark' && tables.length > 1) ? tables[1] : tables[0];
  const csvRows = [];
  const lines = tableMarkdown.trim().split(/\r?\n/);

  lines.forEach((line, index) => {
    // تجاهل خط الفواصل |--|--|
    if (index === 1 && line.includes('---')) return;
    const cells = line.split('|').map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
    if (cells.length > 0) {
      const cleanCells = cells.map(c => `"${c.replace(/"/g, '""')}"`);
      csvRows.push(cleanCells.join(','));
    }
  });

  const finalCsv = '\uFEFF' + csvRows.join('\n');
  const filename = `${type}_${activeProjectId || 'project'}_${new Date().toISOString().split('T')[0]}.csv`;
  triggerCsvDownload(finalCsv, filename);
  showToast(`تم تحميل جدول ${type === 'benchmark' ? 'المقارنات' : 'النتائج'} بصيغة CSV`);
}

function triggerCsvDownload(csvString, filename) {
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.setAttribute('href', url);
  a.setAttribute('download', filename);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// =============================================================================
// نقل نتائج البحث إلى الشات الذكي للمدارسة والمناقشة
// =============================================================================
function transferProjectResultToChat() {
  let runData = currentProjectRunData;
  let activeProj = null;
  if (typeof activeProjectId !== 'undefined' && activeProjectId && typeof projectsList !== 'undefined') {
    activeProj = projectsList.find(p => p.id === activeProjectId) || null;
  }
  if (!activeProj && typeof projectsList !== 'undefined' && projectsList.length > 0) {
    activeProj = projectsList[0];
  }

  if (!runData && activeProj) {
    if (activeProj.execution_data) {
      runData = activeProj.execution_data;
    }
  }

  if (!runData || (!runData.rawOutput && (!runData.rounds || runData.rounds.length === 0))) {
    showToast('⚠️ لا توجد نتائج تشغيل متاحة لهذا المشروع بعد. يرجى تشغيل المشروع أولاً للحصول على نتائج ومدارستها.');
    return;
  }

  const title = runData.projectTitle || activeProj?.title || 'بحث علمي';
  const rounds = (runData.rounds && runData.rounds.length > 0)
    ? runData.rounds
    : [{ round: 1, name: 'المرحلة 1: نتائج التحقيق والتأسيس', output: runData.rawOutput, executedAt: runData.executedAt }];

  let fullBody = '';
  rounds.forEach((r, idx) => {
    fullBody += `### 📌 ${r.name || `الجولة رقم ${r.round}`}`;
    if (r.executedAt) fullBody += ` (${r.executedAt})`;
    fullBody += `\n\n${(r.output || '').trim()}\n\n---\n\n`;
  });

  let webBenchText = '';
  if (runData.webBenchmark && runData.webBenchmark.length > 0) {
    webBenchText = `### 🌐 مراجع المقارنة الخارجية المسترجعة (Tavily AI):\n` +
      runData.webBenchmark.map(b => `- **[${b.title}](${b.url})**: ${b.content?.slice(0, 160)}...`).join('\n') + `\n\n---\n\n`;
  }

  const finalPromptText = `## 📚 مدارسة ومناقشة نتائج مشروع: ${title}
**تاريخ التنفيذ:** ${runData.executedAt || new Date().toLocaleString('ar-SA')}
**نموذج التحقيق:** ${runData.directorModel || 'مدير المشروع'}

---

${webBenchText}${fullBody}
ارغب في مدارسة ومناقشة هذا البحث`;

  // الانتقال لتبويب الشات الذكي
  if (typeof switchMainTab === 'function') {
    switchMainTab('chat');
  }

  // إنشاء جلسة شات جديدة خاصة بهذه المدارسة
  try {
    if (typeof createNewChatSession === 'function') {
      createNewChatSession(true);
      if (typeof chatSessions !== 'undefined' && typeof activeSessionId !== 'undefined') {
        const sess = chatSessions.find(s => s.id === activeSessionId);
        if (sess) {
          sess.title = `مدارسة: ${title.slice(0, 32)}`;
          if (typeof saveChatSessions === 'function') saveChatSessions();
          if (typeof renderChatHistorySidebar === 'function') renderChatHistorySidebar();
        }
      }
    }
  } catch (e) {
    console.warn('Chat session init error:', e);
  }

  // ربط وتفعيل مجموعة وكلاء هذا المشروع في الشات الذكي تلقائياً لاستكمال أي نقص أو التحقق
  try {
    const projectGroupId = activeProj?.linked_group_id || activeProj?.subagents_group?.id;
    const groupSelect = document.getElementById('chatAgentGroupSelect');
    const agentGroupCheckbox = document.getElementById('chatUseAgentGroupCheckbox');
    const container = document.getElementById('chatAgentGroupPicker');

    if (groupSelect && projectGroupId) {
      groupSelect.value = projectGroupId;
      localStorage.setItem('almojtahed_selected_chat_agent_group', projectGroupId);
      localStorage.setItem('almojtahed_chat_selected_group_id', projectGroupId);

      // تفعيل خيار مجموعة الوكلاء تلقائياً لتمكين الباحث من توجيه الاستفسارات والتحقق للوكلاء
      if (agentGroupCheckbox) {
        agentGroupCheckbox.checked = true;
        if (container) container.classList.add('active');
        localStorage.setItem('almojtahed_chat_use_agent_group', 'true');
      }

      if (typeof populateSubAgentsDropdown === 'function') {
        populateSubAgentsDropdown(projectGroupId);
      }
    }
  } catch (e) {
    console.warn('Agent group sync error:', e);
  }

  // وضع النص المنظم في صندوق الإدخال وتركيز المؤشر عليه
  setTimeout(() => {
    const input = document.getElementById('chatInputText');
    if (input) {
      input.value = finalPromptText;
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 260) + 'px';
      input.focus();
      input.scrollTop = input.scrollHeight;
    }
  }, 120);

  showToast('💬 تم نقل نتائج البحث كاملة إلى الشات الذكي وجاهزة للمدارسة والمناقشة!');

  // فتح نافذة إعداد وتوجيه مدارسة المشروع تلقائياً
  setTimeout(() => {
    openProjectToChatModal(activeProj, runData);
  }, 200);
}

/* ==========================================================================
   نافذة إعداد وتوجيه مدارسة المشروع في الشات الذكي (Project to Chat Setup Modal)
   ========================================================================== */

const P2C_OUTPUT_TEMPLATES = {
  fiqh: `اذا طلب منك المستخدم إخراج البحث وترتيبه قم بالتالي:
صورة المسألة: بيان واقع المسألة المطروحة.
تحرير محل النزاع: ضبط نقطة الاتفاق والاختلاف بدقة.
الأدلة النقلية: استعراض الآيات والأحاديث المتعلقة بالمسألة.
بيان أسباب الخلاف: ذكر الجذور التي تفرع عنها الخلاف (من كتب أسباب الخلاف).
سرد الأقوال الفقهية بأدلتها: ذكر كل قول بأدلته، مع نسبة كل قول إلى قائليه من المذاهب (من كتب الفقه).
القواعد والأصول الداخلة في المسألة: ربط المسألة بالقواعد الفقهية والأصولية (من كتب القواعد والأصول).
مناقشة الأدلة: استعراض المناقشات والاعتراضات المذكورة في المصادر.
الترجيح: رجّح ما تراه راجحاً مع بيان سبب الترجيح الأصولي والفقهي.
## [1] منهجية الحاشية والإحالات ##

أولًا: خرّج الأحاديث تخريجًا كاملاً وفق قواعد التخريج المذكورة أعلاه، وضعها في الحاشية.
ثانيًا: اذكر مصدر كل قول في الحاشية بذكر: اسم الكتاب، مؤلفه، الجزء، الصفحة.
ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.
رابعًا: استخدم الإحالة الصحيحة:
إذا نقلت نصًا حرفيًا: اذكر (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: اجعل رقم الإحالة في المتن بين قوسين، أصغر من الخط الأساسي بمقاسين ومرتفعة (superscript) هكذا: <sup><small>(١)</small></sup>. ويشمل ذلك: الآيات، تخريج الأحاديث، ونسبة الأقوال.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (القول الأول: / الدليل الأول:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
## [3] سرد المصادر والمراجع ##
اجعل في نهاية البحث قائمة بالمصادر والمراجع على الطريقة الأكاديمية، مرتبة هجائيًا، بذكر: اسم المصدر، مؤلفه، محققه، رقم الطبعة، الناشر، مدينة النشر، سنة الطبع.`,

  tafsir: `اذا طلب منك المستخدم إخراج البحث وترتيبه قم بالتالي:
نص الآية الكريمة وسياقها: إيراد الآيات محل التفسير والبيان وضبط ألفاظها.
سبب النزول وتحقيقه: ذكر الروايات الواردة في سبب النزول والتمييز بين الصحيح والضعيف منها (من كتب أسباب النزول ومصنفات الحديث).
المعنى الإجمالي وغريب الألفاظ: بيان المعنى العام والمدلول اللغوي للألفاظ الغريبة (من كتب معاني القرآن وغريب القرآن والمعاجم).
أقوال السلف من الصحابة والتابعين: سرد المأثور عن ابن عباس، ومجاهد، وقتادة، وسائر أئمة التفسير المتقدمين بأسانيدها المحررة (من تفسير الطبري وابن أبي حاتم وعبد الرزاق).
أقوال المفسرين وتوجيهها: استعراض وجوه التفسير لدى المحققين (القرطبي، وابن كثير، والرازي، والشوكاني) مع المقارنة بين المأثور والرأي.
الوجوه البلاغية والإعرابية: إبراز النكت البلاغية واللطائف البيانية والإعراب المؤثر في المعنى.
الهدايات والأحكام والفوائد: استنباط المقاصد والأحكام والدروس المستفادة من الآية.
الترجيح والاختيار: ترجيح المعنى الأظهر مع بيان القرائن التفسيرية واللغوية والسياقية المعتمدة.
## [1] منهجية الحاشية والإحالات ##

أولًا: خرّج الأحاديث والآثار المروية عن السلف تخريجًا كاملاً مع بيان درجتها في الحاشية.
ثانيًا: اذكر مصدر كل قول وتفسير في الحاشية بذكر: اسم الكتاب، مؤلفه، الجزء، الصفحة.
ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.
رابعًا: استخدم الإحالة الصحيحة:
إذا نقلت نصًا حرفيًا: اذكر (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: اجعل رقم الإحالة في المتن بين قوسين، أصغر من الخط الأساسي بمقاسين ومرتفعة (superscript) هكذا: <sup><small>(١)</small></sup>. ويشمل ذلك: الآيات، تخريج الأحاديث، ونسبة الأقوال.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (الوجه الأول: / القول الثاني:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
## [3] سرد المصادر والمراجع ##
اجعل في نهاية البحث قائمة بالمصادر والمراجع على الطريقة الأكاديمية، مرتبة هجائيًا، بذكر: اسم المصدر، مؤلفه، محققه، رقم الطبعة، الناشر، مدينة النشر، سنة الطبع.`,

  hadith: `اذا طلب منك المستخدم إخراج البحث وترتيبه قم بالتالي:
نص الحديث وألفاظه ورواياته: إيراد متن الحديث مع رصد الفروق اللفظية والزيادات في الروايات.
التخريج الموسع من الدواوين المسندة: عزو الحديث إلى الكتب التسعة والمصنفات والمسانيد والمعاجم مع بيان الكتاب والباب ورقم الحديث.
جمع الطرق ورصد المدار: حصر طرق الحديث وبيان الراوي المدار الذي تلتقي عنده الأسانيد (من كتب الجوامع والأطراف والعلل).
المتابعات والشواهد: استقصاء المتابعات التامة والقاصرة وشواهد الحديث من رواية صحابة آخرين لبيان القوة والاعتبار.
دراسة الإسناد ونقد رجاله: ترجمة موجزة لرجال السند وتحرير مراتبهم من كتب الجرح والتعديل المعتمدة (التهذيب والميزان).
تحرير الاتصال والعلل: بحث اتصال السماع وكشف الإرسال الخفي أو الانقطاع أو التدليس، وبيان الاختلاف رفعاً ووقفاً ووصلاً وإرسالاً.
الحكم النهائي على الحديث: صياغة الحكم النقدي المعلل بعبارات المحدثين المنضبطة (صحيح، حسن، ضعيف، منكر...).
فقه الحديث ودلالته: بيان المسائل الفقهية والأصولية والتربوية المستنبطة من المتن.
## [1] منهجية الحاشية والإحالات ##

أولًا: خرّج الحديث تخريجًا كاملاً بذكر: اسم المصنف، اسم الكتاب، الباب، رقم الحديث، الجزء والصفحة.
ثانيًا: اذكر نقول أئمة الجرح والتعديل في الحاشية معزوّة إلى مصادرها الأصيلة.
ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.
رابعًا: استخدم الإحالة الصحيحة:
إذا نقلت نصًا حرفيًا: اذكر (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: اجعل رقم الإحالة في المتن بين قوسين، أصغر من الخط الأساسي بمقاسين ومرتفعة (superscript) هكذا: <sup><small>(١)</small></sup>. ويشمل ذلك: الآيات، تخريج الأحاديث، ونسبة الأقوال.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (الطريق الأول: / علة الحديث:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
## [3] سرد المصادر والمراجع ##
اجعل في نهاية البحث قائمة بالمصادر والمراجع على الطريقة الأكاديمية، مرتبة هجائيًا، بذكر: اسم المصدر، مؤلفه، محققه، رقم الطبعة، الناشر، مدينة النشر، سنة الطبع.`,

  isnad: `اذا طلب منك المستخدم إخراج البحث وترتيبه قم بالتالي:
توصيف الحديث ومصدره: إيراد الحديث المسند موضوع الدراسة مع ذكر مخرجه وصحابيه.
رسم شبكة الطرق وشجرة الإسناد: تفريغ أسانيد الحديث في هيكل شجري مرئي يوضح طبقات الرواة والمدار ونقاط الافتراق والالتقاء.
تحرير المدار والاختلاف عليه: تحديد الراوي المدار، وفصل وجوه الاختلاف عليه (الرفع مقابل الوقف، الوصل مقابل الإرسال، وتسمية الرواة وإبدالهم).
تراجم رجال الإسناد طبقة طبقة: دراسة كل راوٍ في السلسلة، بذكر: اسمه، طبقته، سنة وفاته، مرتبته التوثيقية، وأهم ما قيل فيه جرحاً وتعديلاً.
تحقيق صيغ الأداء والاتصال: التحقق من اتصال السماع بين كل راوٍ وشيخه، وتدقيق صيغ التحديث، وتفتيش عن مظان التدليس وعنعنة المدلسين.
الموازنة والترجيح بين الوجوه المتعارضة: الموازنة بين الرواة المختلفين وفق قواعد تقديم الأحفظ والأكثر عدداً وملازمة للشيخ.
النتيجة والعلة النهائية: بيان العلة الخفية القادحة في السند إن وجدت، والحكم الجازم على صحة الطريق أو إعلاله.
## [1] منهجية الحاشية والإحالات ##

أولًا: اذكر مصادر تراجم الرواة في الحاشية من كتب الرجال المعتمدة (الجرح والتعديل لابن أبي حاتم، تهذيب الكمال للمزي، ميزان الاعتدال للذهبي، التقريب لابن حجر).
ثانيًا: اذكر نصوص أقوال النقاد ومواضع الاختلاف من كتب العلل (علل الدارقطني، علل ابن أبي حاتم، العلل للترمذي وأحمد).
ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.
رابعًا: استخدم الإحالة الصحيحة:
إذا نقلت نصًا حرفيًا: اذكر (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: اجعل رقم الإحالة في المتن بين قوسين، أصغر من الخط الأساسي بمقاسين ومرتفعة (superscript) هكذا: <sup><small>(١)</small></sup>. ويشمل ذلك: الآيات، تخريج الأحاديث، ونسبة الأقوال.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (الراوي الأول: / المدار:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
## [3] سرد المصادر والمراجع ##
اجعل في نهاية البحث قائمة بالمصادر والمراجع على الطريقة الأكاديمية، مرتبة هجائيًا، بذكر: اسم المصدر، مؤلفه، محققه، رقم الطبعة، الناشر، مدينة النشر، سنة الطبع.`,

  aqeedah: `اذا طلب منك المستخدم إخراج البحث وترتيبه قم بالتالي:
تحرير المسألة العقدية: ضبط عنوان المسألة وبيان محل النزاع العقدي وحقيقة المعتقد فيها.
الأدلة من القرآن الكريم والسنة النبوية: استعراض النصوص النقلية الدالة على الباب وضبط وجه الدلالة منها.
مذهب السلف الصالح وأهل السنة والجماعة: سرد أقوال الصحابة والتابعين والأئمة الأربعة وأعلام السنة بنصوصها الحرفية من المصنفات المسندة وكتب الاعتقاد.
استعراض مقالات الفرق المخالفة: بيان أقوال المخالفين (الجهمية، المعتزلة، الأشاعرة، الماتريدية، وغيرهم) ونسبتها إليهم من كتب المقالات الأصيلة.
شبهات المخالفين ومناقشتها: تفكيك شبهات الفرق واستعراض الردود النقلية والعقلية عليها وفق قواعد السلف ومنهج أهل السنة.
الأصول والقواعد العقدية المتصلة بالمسألة: ربط المسألة بالقواعد الكلية في الأسماء والصفات، أو الإيمان، أو القدر، أو الصحابة والنبوات.
الآثار المترتبة على المعتقد: بيان الأثر الإيماني والعملي والتربوي لتقرير هذا المعتقد وخطورة الانحراف عنه.
الخلاصة والتقرير: صياغة التقرير العقدي الصافي المحرر في المسألة.
## [1] منهجية الحاشية والإحالات ##

أولًا: خرّج الأحاديث والآثار العقدية تخريجًا دقيقًا مع بيان حكم أئمة الشأن عليها في الحاشية.
ثانيًا: اذكر مصدر كل قول ونقل في الحاشية من أمهات كتب السنة والاعتقاد (الرد على الجهمية، شرح أصول اعتقاد أهل السنة للالكائي، الإبانة، الحجة في بيان المحجة، مجموع الفتاوى) بذكر: اسم الكتاب، مؤلفه، الجزء، الصفحة.
ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.
رابعًا: استخدم الإحالة الصحيحة:
إذا نقلت نصًا حرفيًا: اذكر (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
## [2] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:

الإحالات في المتن: اجعل رقم الإحالة في المتن بين قوسين، أصغر من الخط الأساسي بمقاسين ومرتفعة (superscript) هكذا: <sup><small>(١)</small></sup>. ويشمل ذلك: الآيات، تخريج الأحاديث، ونسبة الأقوال.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (المسألة الأولى: / شبهة المخالف:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
## [3] سرد المصادر والمراجع ##
اجعل في نهاية البحث قائمة بالمصادر والمراجع على الطريقة الأكاديمية، مرتبة هجائيًا، بذكر: اسم المصدر، مؤلفه، محققه، رقم الطبعة، الناشر، مدينة النشر، سنة الطبع.`
};

function applyP2COutputTemplate(type) {
  const textarea = document.getElementById('p2cOutputPrompt');
  if (!textarea) return;

  const template = P2C_OUTPUT_TEMPLATES[type];
  if (!template) return;

  textarea.value = template;
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 240) + 'px';
  textarea.focus();

  const labels = {
    fiqh: 'قالب الفقه والمقارنة المذهبية',
    tafsir: 'قالب التفسير وعلوم القرآن',
    hadith: 'قالب الحديث والتخريج الموسع',
    isnad: 'قالب دراسة الأسانيد ونقد الرجال',
    aqeedah: 'قالب العقيدة ومقالات الفرق'
  };
  if (typeof showToast === 'function') {
    showToast(`⚡ تم إدراج «${labels[type] || type}» في توجيه الإخراج بنجاح!`, 2500);
  }
}

let p2cActiveProject = null;
let p2cActiveRunData = null;

function openProjectToChatModal(project, runData) {
  let activeProj = project;
  if (!activeProj && typeof activeProjectId !== 'undefined' && activeProjectId && typeof projectsList !== 'undefined') {
    activeProj = projectsList.find(p => p.id === activeProjectId) || null;
  }
  if (!activeProj && typeof projectsList !== 'undefined' && projectsList.length > 0) {
    activeProj = projectsList[0];
  }

  p2cActiveProject = activeProj;
  p2cActiveRunData = runData || currentProjectRunData || null;

  const modal = document.getElementById('projectToChatModalOverlay');
  if (!modal) {
    console.error('projectToChatModalOverlay not found in DOM');
    return;
  }

  // 1. توجيه النظام (مسحوب تلقائياً من توجيه مدير المشروع)
  const sysInput = document.getElementById('p2cSystemPrompt');
  if (sysInput) {
    sysInput.value = p2cActiveProject?.director?.system_prompt || '';
  }

  // 2. توجيه إضافي (فارغ يمكن للباحث الإضافة عليه)
  const addInput = document.getElementById('p2cAdditionalPrompt');
  if (addInput) {
    addInput.value = '';
  }

  // 3. توجيه إخراج (طريقة الإخراج عند انتهاء المناقشة)
  const outInput = document.getElementById('p2cOutputPrompt');
  if (outInput) {
    outInput.value = '';
  }

  // 4. مجموعة الوكلاء في قائمة منسدلة مع التحديد التلقائي على مجموعة المشروع
  populateP2CGroupsDropdown(p2cActiveProject);

  // 5. تحديد النموذج بنماذج أوبن راوتر
  populateP2CModelsDropdown(p2cActiveProject);

  // 6. عمق التفكير
  const thinkSelect = document.getElementById('p2cThinkingSelect');
  if (thinkSelect) {
    const prefThink = p2cActiveProject?.director?.thinking || (typeof currentThinkingLevel !== 'undefined' ? currentThinkingLevel : 'medium');
    thinkSelect.value = prefThink;
  }

  // 7. عدد التوكن
  const tokensSelect = document.getElementById('p2cTokensSelect');
  if (tokensSelect) {
    const prefTokens = p2cActiveProject?.director?.max_tokens ? String(p2cActiveProject.director.max_tokens) : '262144';
    if (tokensSelect.querySelector(`option[value="${prefTokens}"]`)) {
      tokensSelect.value = prefTokens;
    } else {
      tokensSelect.value = '262144';
    }
  }

  // 8. معلمات النموذج (درجة الحرارة، عقوبة التكرار، Top-K)
  const tempVal = (typeof currentSettings !== 'undefined' && currentSettings.modelParams?.temperature !== undefined) ? currentSettings.modelParams.temperature : 0.2;
  const repVal = (typeof currentSettings !== 'undefined' && currentSettings.modelParams?.repPenalty !== undefined) ? currentSettings.modelParams.repPenalty : 1.1;
  const topKVal = (typeof currentSettings !== 'undefined' && currentSettings.modelParams?.topK !== undefined) ? currentSettings.modelParams.topK : 40;

  const tempInput = document.getElementById('p2cTemperature');
  if (tempInput) {
    tempInput.value = tempVal;
    const badge = document.getElementById('p2cTempVal');
    if (badge) badge.textContent = tempVal;
  }

  const repInput = document.getElementById('p2cRepPenalty');
  if (repInput) {
    repInput.value = repVal;
    const badge = document.getElementById('p2cRepVal');
    if (badge) badge.textContent = repVal;
  }

  const topKInput = document.getElementById('p2cTopK');
  if (topKInput) {
    topKInput.value = topKVal;
    const badge = document.getElementById('p2cTopKVal');
    if (badge) badge.textContent = topKVal;
  }

  modal.classList.add('open');
  modal.style.display = 'flex';
}

function closeProjectToChatModal() {
  const modal = document.getElementById('projectToChatModalOverlay');
  if (modal) {
    modal.classList.remove('open');
    modal.style.display = 'none';
  }
}

function handleProjectToChatModalOverlay(e) {
  if (e.target && e.target.id === 'projectToChatModalOverlay') {
    closeProjectToChatModal();
  }
}

// تعبئة القائمة المنسدلة لمجموعات الوكلاء مع التحديد التلقائي
function populateP2CGroupsDropdown(project) {
  const select = document.getElementById('p2cGroupSelect');
  if (!select) return;

  let groups = window.agentGroups || [];
  if (!groups.length) {
    try {
      groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
    } catch (e) { }
  }

  const targetGroupId = project?.linked_group_id || project?.subagents_group?.id;

  select.innerHTML = '';
  if (!groups || groups.length === 0) {
    if (project?.subagents_group) {
      groups = [project.subagents_group];
    }
  }

  groups.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g.id;
    opt.textContent = `${g.name} (${g.agents?.length || 0} وكلاء)`;
    if (targetGroupId && g.id === targetGroupId) {
      opt.selected = true;
    }
    select.appendChild(opt);
  });

  if (!select.value && select.options.length > 0) {
    select.selectedIndex = 0;
  }

  renderP2CAgentsCheckboxes(select.value);
}

// رسم مربعات تحديد الوكلاء التابعين للمجموعة المختارة
function renderP2CAgentsCheckboxes(groupId, preselectedIds) {
  const container = document.getElementById('p2cAgentsContainer');
  const countBadge = document.getElementById('p2cSelectedAgentsCountBadge');
  if (!container) return;

  let groups = window.agentGroups || [];
  if (!groups.length) {
    try {
      groups = JSON.parse(localStorage.getItem(ownerStorageKey('almojtahed_agent_groups')) || '[]');
    } catch (e) { }
  }

  const grp = groups.find(g => g.id === groupId) || (p2cActiveProject?.subagents_group?.id === groupId ? p2cActiveProject.subagents_group : null);
  const agents = grp?.agents || [];

  container.innerHTML = '';

  if (agents.length === 0) {
    container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); font-size: 12.5px; padding: 18px;">لا يوجد وكلاء متاحون في هذه المجموعة</div>';
    if (countBadge) countBadge.textContent = '٠ وكلاء محددون';
    return;
  }

  agents.forEach(a => {
    const isChecked = !preselectedIds || preselectedIds.includes(a.id);
    const label = document.createElement('label');
    label.className = `p2c-agent-badge-card ${isChecked ? 'active' : ''}`;
    label.id = `p2cAgentCard_${a.id}`;

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'p2c-agent-cb';
    cb.value = a.id;
    cb.checked = isChecked;
    cb.onchange = function () {
      label.classList.toggle('active', this.checked);
      updateP2CAgentsCount();
    };

    const info = document.createElement('div');
    info.className = 'p2c-agent-badge-info';

    const nameSpan = document.createElement('span');
    nameSpan.className = 'p2c-agent-badge-name';
    nameSpan.textContent = a.name || 'وكيل تخصصي';

    const roleSpan = document.createElement('span');
    roleSpan.className = 'p2c-agent-badge-role';
    const booksCount = (a.booksScope && Array.isArray(a.booksScope)) ? a.booksScope.length : (a.scopeBooks?.length || (a.books?.length || 0));
    roleSpan.textContent = a.desc ? a.desc.slice(0, 36) : (booksCount > 0 ? `${booksCount} كتب معتمدة` : 'بحث شامل');

    info.appendChild(nameSpan);
    info.appendChild(roleSpan);

    label.appendChild(cb);
    label.appendChild(info);
    container.appendChild(label);
  });

  updateP2CAgentsCount();
}

function updateP2CAgentsCount() {
  const countBadge = document.getElementById('p2cSelectedAgentsCountBadge');
  const checked = document.querySelectorAll('.p2c-agent-cb:checked');
  if (countBadge) {
    countBadge.textContent = `${checked.length} وكلاء محددون`;
  }
}

function handleP2CGroupChange(groupId) {
  renderP2CAgentsCheckboxes(groupId);
}

function toggleAllP2CAgents(state) {
  const cbs = document.querySelectorAll('.p2c-agent-cb');
  cbs.forEach(cb => {
    cb.checked = !!state;
    const card = document.getElementById(`p2cAgentCard_${cb.value}`);
    if (card) card.classList.toggle('active', !!state);
  });
  updateP2CAgentsCount();
}

// تعبئة قائمة النماذج بنماذج أوبن راوتر
function populateP2CModelsDropdown(project) {
  const select = document.getElementById('p2cModelSelect');
  if (!select) return;

  const chatModelSelect = document.getElementById('chatModelSelect');
  const targetModel = project?.director?.model || chatModelSelect?.value || 'google/gemini-2.5-flash';

  select.innerHTML = '';

  let modelsAdded = 0;
  if (chatModelSelect && chatModelSelect.options && chatModelSelect.options.length > 0) {
    Array.from(chatModelSelect.options).forEach(opt => {
      if (opt.value && opt.value !== 'loading') {
        const option = document.createElement('option');
        option.value = opt.value;
        option.textContent = opt.textContent;
        if (opt.value === targetModel) option.selected = true;
        select.appendChild(option);
        modelsAdded++;
      }
    });
  }

  if (modelsAdded === 0) {
    const fallbackModels = projectSuggestedModels();
    fallbackModels.forEach(m => {
      const option = document.createElement('option');
      option.value = m.id;
      option.textContent = m.name;
      if (m.id === targetModel) option.selected = true;
      select.appendChild(option);
    });
  }

  if (!select.value && select.options.length > 0) {
    select.selectedIndex = 0;
  }
}

// زر الحفظ: يحفظ جميع الإعدادات في إعدادات الشات بقسم إعدادات منظومة المجتهد ويطبقها فوراً
function saveProjectToChatSettingsAndApply() {
  const systemPrompt = document.getElementById('p2cSystemPrompt')?.value.trim() || '';
  const additionalPrompt = document.getElementById('p2cAdditionalPrompt')?.value.trim() || '';
  const outputPrompt = document.getElementById('p2cOutputPrompt')?.value.trim() || '';

  const groupId = document.getElementById('p2cGroupSelect')?.value;
  const selectedAgentCbs = document.querySelectorAll('.p2c-agent-cb:checked');
  const selectedAgentIds = Array.from(selectedAgentCbs).map(cb => cb.value);

  const model = document.getElementById('p2cModelSelect')?.value || 'google/gemini-2.5-flash';
  const thinking = document.getElementById('p2cThinkingSelect')?.value || 'medium';
  const maxTokens = parseInt(document.getElementById('p2cTokensSelect')?.value) || 262144;

  const temp = parseFloat(document.getElementById('p2cTemperature')?.value || 0.2);
  const repPenalty = parseFloat(document.getElementById('p2cRepPenalty')?.value || 1.1);
  const topK = parseInt(document.getElementById('p2cTopK')?.value || 40);

  // 1. صياغة توجيه النظام المتكامل للمدارسة (توجيه النظام + إضافي + إخراج)
  let combinedSystemPrompt = systemPrompt;
  if (additionalPrompt) {
    combinedSystemPrompt += `\n\n### 📌 توجيهات إضافية واستدراكات للمدارسة:\n${additionalPrompt}`;
  }
  if (outputPrompt) {
    combinedSystemPrompt += `\n\n### 📑 توجيه هيكل وصياغة الإخراج النهائي للبحث:\n${outputPrompt}`;
  }

  // 2. الحفظ في إعدادات المنظومة (currentSettings + localStorage)
  if (typeof currentSettings !== 'undefined') {
    if (!currentSettings.modelParams) currentSettings.modelParams = {};
    currentSettings.modelParams.systemPrompt = combinedSystemPrompt;
    currentSettings.modelParams.temperature = temp;
    currentSettings.modelParams.topK = topK;
    currentSettings.modelParams.repPenalty = repPenalty;
    currentSettings.modelParams.maxTokens = maxTokens;

    try {
      localStorage.setItem('almojtahed_settings', JSON.stringify(currentSettings));
    } catch (e) {
      console.warn('Error saving settings to localStorage:', e);
    }
  }

  // 3. تحديث مدخلات نافذة الإعدادات الشاملة (لتبقى متزامنة 100%)
  const mainSysInput = document.getElementById('systemPromptInput');
  if (mainSysInput) mainSysInput.value = combinedSystemPrompt;

  const mainTempInput = document.getElementById('paramTemperature');
  if (mainTempInput) {
    mainTempInput.value = temp;
    const badge = document.getElementById('valTemp');
    if (badge) badge.textContent = temp;
  }

  const mainTopKInput = document.getElementById('paramTopK');
  if (mainTopKInput) {
    mainTopKInput.value = topK;
    const badge = document.getElementById('valTopK');
    if (badge) badge.textContent = topK;
  }

  const mainRepInput = document.getElementById('paramRepPenalty');
  if (mainRepInput) {
    mainRepInput.value = repPenalty;
    const badge = document.getElementById('valRepPenalty');
    if (badge) badge.textContent = repPenalty;
  }

  const mainMaxTokensInput = document.getElementById('paramMaxTokens');
  if (mainMaxTokensInput) {
    mainMaxTokensInput.value = Math.min(maxTokens, 131072);
    const badge = document.getElementById('valMaxTokens');
    if (badge) badge.textContent = Number(maxTokens).toLocaleString() + ' توكن';
  }

  // 4. تطبيق التحديدات على واجهة الشات الذكي الحية
  // أ. النموذج
  const chatModelSelect = document.getElementById('chatModelSelect');
  if (chatModelSelect) {
    chatModelSelect.value = model;
    localStorage.setItem('almojtahed_chat_model', model);
    if (typeof handleChatModelChange === 'function') {
      handleChatModelChange(model);
    }
  }
  const triggerText = document.getElementById('chatCustomModelTriggerText');
  if (triggerText && typeof cleanModelDisplayName === 'function') {
    triggerText.textContent = cleanModelDisplayName(model);
  }

  // ب. عمق التفكير
  const chatThinkSelect = document.getElementById('chatThinkingSelect');
  if (chatThinkSelect) {
    chatThinkSelect.value = thinking;
    if (typeof setThinkingLevel === 'function') {
      setThinkingLevel(thinking);
    }
  }

  // ج. مجموعة الوكلاء والوكلاء المحددين
  const groupSelect = document.getElementById('chatAgentGroupSelect');
  const agentGroupCheckbox = document.getElementById('chatUseAgentGroupCheckbox');
  const groupContainer = document.getElementById('chatAgentGroupPicker');

  if (groupSelect && groupId) {
    groupSelect.value = groupId;
    localStorage.setItem('almojtahed_selected_chat_agent_group', groupId);
    localStorage.setItem('almojtahed_chat_selected_group_id', groupId);

    if (agentGroupCheckbox) {
      agentGroupCheckbox.checked = true;
      if (groupContainer) groupContainer.classList.add('active');
      localStorage.setItem('almojtahed_chat_use_agent_group', 'true');
    }

    if (typeof populateSubAgentsDropdown === 'function') {
      populateSubAgentsDropdown(groupId);
    }

    // حفظ الوكلاء المختارين بعينهم (1 أو 2 أو 3 أو الجميع)
    localStorage.setItem('almojtahed_selected_chat_subagents', JSON.stringify(selectedAgentIds));
  }

  // إغلاق النافذة
  closeProjectToChatModal();

  // إشعار نجاح
  showToast('✅ تم حفظ كافة توجيهات المدارسة والوكلاء في إعدادات المنظومة وتطبيقها على الشات!');

  // تركيز المؤشر على صندوق الإدخال
  setTimeout(() => {
    const input = document.getElementById('chatInputText');
    if (input) input.focus();
  }, 100);
}

window.applyP2COutputTemplate = applyP2COutputTemplate;
window.openProjectToChatModal = openProjectToChatModal;
window.closeProjectToChatModal = closeProjectToChatModal;
window.handleProjectToChatModalOverlay = handleProjectToChatModalOverlay;
window.handleP2CGroupChange = handleP2CGroupChange;
window.toggleAllP2CAgents = toggleAllP2CAgents;
window.saveProjectToChatSettingsAndApply = saveProjectToChatSettingsAndApply;


function downloadProjectRunReportTxt() {
  if (!currentProjectRunData) {
    showToast('لا يوجد تقرير متاح للتحميل');
    return;
  }
  const title = currentProjectRunData.projectTitle || 'تقرير_المشروع';
  const content = `# تقرير تحقيق مشروع: ${title}
تاريخ التنفيذ: ${currentProjectRunData.executedAt}
نموذج القيادة والتحقيق: ${currentProjectRunData.directorModel}
المنظومة: محرك المجتهد للشريعة والتراث الإسلامي

---

${currentProjectRunData.rawOutput}
`;

  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.setAttribute('href', url);
  a.setAttribute('download', `report_${title.replace(/[\s\/\\:*?"<>|]/g, '_')}.md`);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('تم تحميل التقرير العلمي بصيغة Markdown');
}

// =============================================================================
// بناء وثيقة HTML الأكاديمية المستقلة التفاعلية (مع الشارتات والأسانيد و CSS و JS)
// =============================================================================
function buildStandaloneProjectHtml(runData) {
  if (!runData) return '';
  const title = runData.projectTitle || 'تقرير تحقيق وبحث علمي';
  const executedAt = runData.executedAt || new Date().toLocaleString('ar-SA');
  const directorModel = runData.directorModel || 'الذكاء الاصطناعي الأكاديمي';
  const rounds = (runData.rounds && runData.rounds.length > 0)
    ? runData.rounds
    : [{ round: 1, name: 'المرحلة 1: المسح والتأسيس', output: runData.rawOutput, executedAt: executedAt }];

  const roundsHtml = rounds.map(r => `
    <div class="execution-round-card">
      <div class="round-card-header">
        <div class="round-title-box">
          <span class="round-name">📌 ${escapeHtml(r.name || `الجولة رقم ${r.round}`)}</span>
          <span class="round-date">(${escapeHtml(r.executedAt || '')})</span>
        </div>
        <span class="round-badge">جولة معتمدة ومحققة ✓</span>
      </div>
      <div class="markdown-body">
        ${(typeof formatMarkdown === 'function') ? formatMarkdown(r.output || '') : (typeof marked !== 'undefined' ? marked.parse(r.output || '') : (r.output || '').replace(/\n/g, '<br>'))}
      </div>
    </div>
  `).join('');

  return `<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)} - منظومة المجتهد</title>
  
  <!-- خطوط عربية أكاديمية -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Amiri:ital,wght@0,400;0,700;1,400&family=Tajawal:wght@400;500;700;800&display=swap" rel="stylesheet">
  
  <!-- مكتبات الرسوم والشارتات وشبكة الأسانيد والتشجير -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/markmap-view@0.17/dist/browser/index.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/markmap-lib@0.17/dist/browser/index.iife.js"></script>

  <style>
    :root {
      --bg-canvas: #FAF8F5;
      --bg-surface: #FFFFFF;
      --bg-muted: #F3EFEA;
      --text-main: #1F2937;
      --text-secondary: #4B5563;
      --text-muted: #6B7280;
      --accent-gold: #B45309;
      --accent-blue: #1D4ED8;
      --border-subtle: #E5E0D8;
      --border-strong: #D1C7B7;
      --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
      --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
      --font-amiri: 'Amiri', serif;
      --font-tajawal: 'Tajawal', sans-serif;
    }

    [data-theme="dark"] {
      --bg-canvas: #121417;
      --bg-surface: #1A1D23;
      --bg-muted: #22262E;
      --text-main: #F3F4F6;
      --text-secondary: #D1D5DB;
      --text-muted: #9CA3AF;
      --accent-gold: #F59E0B;
      --accent-blue: #3B82F6;
      --border-subtle: #2D333D;
      --border-strong: #3F4654;
      --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
      --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      background-color: var(--bg-canvas);
      color: var(--text-main);
      font-family: var(--font-tajawal);
      line-height: 1.8;
      direction: rtl;
      text-align: right;
      padding: 0;
      transition: background 0.2s, color 0.2s;
    }

    /* الشريط العلوي التفاعلي */
    .top-action-bar {
      position: sticky;
      top: 0;
      z-index: 1000;
      background: var(--bg-surface);
      border-bottom: 1px solid var(--border-subtle);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: var(--shadow-sm);
    }

    .bar-brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
      color: var(--accent-gold);
      font-size: 15px;
    }

    .bar-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .btn-act {
      background: var(--bg-surface);
      color: var(--text-main);
      border: 1px solid var(--border-subtle);
      padding: 6px 14px;
      border-radius: 6px;
      font-family: inherit;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
    }

    .btn-act:hover {
      border-color: var(--accent-gold);
      color: var(--accent-gold);
    }

    .btn-primary {
      background: linear-gradient(135deg, #B45309, #D97706);
      color: #FFFFFF !important;
      border: none;
    }

    .btn-primary:hover {
      opacity: 0.92;
      transform: translateY(-1px);
    }

    /* الحاوية الرئيسية للتقرير الأكاديمي */
    .report-container {
      max-width: 1100px;
      margin: 32px auto;
      padding: 0 20px;
    }

    /* ترويسة التقرير */
    .report-hero-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-top: 5px solid var(--accent-gold);
      border-radius: 12px;
      padding: 32px 36px;
      box-shadow: var(--shadow-md);
      margin-bottom: 28px;
    }

    .report-badge-top {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(180, 83, 9, 0.1);
      color: var(--accent-gold);
      border: 1px solid rgba(180, 83, 9, 0.25);
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 12px;
    }

    .report-hero-title {
      font-family: var(--font-amiri);
      font-size: 32px;
      font-weight: 700;
      color: var(--text-main);
      line-height: 1.4;
      margin-bottom: 16px;
    }

    .report-meta-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 14px;
      padding-top: 16px;
      border-top: 1px dashed var(--border-subtle);
      font-size: 13.5px;
      color: var(--text-secondary);
    }

    .meta-item strong {
      color: var(--text-main);
    }

    /* كروت الجولات */
    .execution-round-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      box-shadow: var(--shadow-sm);
      margin-bottom: 28px;
      overflow: hidden;
    }

    .round-card-header {
      background: var(--bg-muted);
      border-bottom: 1px solid var(--border-subtle);
      padding: 14px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
    }

    .round-name {
      font-family: var(--font-amiri);
      font-size: 18px;
      font-weight: 700;
      color: var(--accent-gold);
    }

    .round-date {
      font-size: 12px;
      color: var(--text-muted);
      margin-right: 8px;
    }

    .round-badge {
      background: rgba(16, 185, 129, 0.12);
      color: #059669;
      border: 1px solid rgba(16, 185, 129, 0.25);
      padding: 3px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 700;
    }

    /* نصوص الماركداون الأكاديمية */
    .markdown-body {
      padding: 28px 32px;
      font-family: var(--font-amiri);
      font-size: 18.5px;
      line-height: 2;
      color: var(--text-main);
    }

    .markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4 {
      font-family: var(--font-amiri);
      color: var(--text-main);
      margin-top: 24px;
      margin-bottom: 12px;
      font-weight: 700;
    }

    .markdown-body h2 {
      font-size: 24px;
      border-bottom: 2px solid var(--border-subtle);
      padding-bottom: 6px;
      color: var(--accent-gold);
    }

    .markdown-body h3 {
      font-size: 20px;
      color: var(--text-main);
    }

    .markdown-body p {
      margin-bottom: 16px;
      text-align: justify;
    }

    .markdown-body blockquote {
      border-right: 4px solid var(--accent-gold);
      background: var(--bg-muted);
      padding: 14px 20px;
      margin: 20px 0;
      border-radius: 0 8px 8px 0;
      font-style: normal;
      color: var(--text-secondary);
    }

    /* الجداول الأكاديمية */
    .markdown-body table {
      width: 100%;
      direction: rtl !important;
      text-align: right !important;
      border-collapse: separate;
      border-spacing: 0;
      margin: 24px 0;
      font-size: 15px;
      font-family: var(--font-tajawal);
      background: var(--bg-surface);
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid var(--border-subtle);
      box-shadow: var(--shadow-sm);
    }

    .markdown-body th {
      background: var(--bg-muted);
      color: var(--text-main);
      font-weight: 700;
      padding: 12px 14px;
      border-bottom: 2px solid var(--border-subtle);
      border-left: 1px solid var(--border-subtle);
      border-right: none !important;
      direction: rtl !important;
      text-align: right !important;
    }

    .markdown-body th:last-child {
      border-left: none;
    }

    .markdown-body td {
      padding: 10px 14px;
      border-bottom: 1px solid var(--border-subtle);
      border-left: 1px solid var(--border-subtle);
      border-right: none !important;
      color: var(--text-secondary);
      line-height: 1.6;
      direction: rtl !important;
      text-align: right !important;
    }

    .markdown-body td:last-child {
      border-left: none;
    }

    .markdown-body tr:nth-child(even) {
      background-color: rgba(0,0,0,0.015);
    }

    [data-theme="dark"] .markdown-body tr:nth-child(even) {
      background-color: rgba(255,255,255,0.02);
    }

    /* كروت الرسوم البيانية والأسانيد */
    .chart-render-wrapper, .isnad-render-wrapper {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 20px;
      margin: 24px 0;
      box-shadow: var(--shadow-sm);
    }

    .chart-render-header, .isnad-render-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
      border-bottom: 1px solid var(--border-subtle);
      padding-bottom: 8px;
    }

    .chart-render-title, .isnad-render-title {
      font-family: var(--font-amiri);
      font-size: 17px;
      font-weight: 700;
      color: var(--accent-gold);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .isnad-canvas-container {
      height: 300px;
      width: 100%;
      border-radius: 6px;
      background: var(--bg-muted);
      border: 1px solid var(--border-subtle);
    }

    .report-footer-seal {
      text-align: center;
      padding: 40px 20px;
      color: var(--text-muted);
      font-size: 13px;
      border-top: 1px solid var(--border-subtle);
      margin-top: 40px;
    }

    /* قواعد الطباعة الأكاديمية (A4 Print Stylesheet) */
    @media print {
      @page {
        size: A4;
        margin: 15mm 12mm 15mm 12mm;
      }
      body {
        background: #FFFFFF !important;
        color: #111827 !important;
      }
      .top-action-bar, button {
        display: none !important;
      }
      .report-container {
        max-width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
      }
      .report-hero-card, .execution-round-card, .chart-render-wrapper, .isnad-render-wrapper, table {
        page-break-inside: avoid !important;
        break-inside: avoid !important;
        box-shadow: none !important;
        border-color: #D1D5DB !important;
      }
      .markdown-body {
        font-size: 15pt !important;
        line-height: 1.8 !important;
      }
      table {
        font-size: 10.5pt !important;
      }
      th {
        background-color: #F3F4F6 !important;
        color: #111827 !important;
      }
      td, th {
        border-color: #D1D5DB !important;
      }
    }
  </style>
</head>
<body>

  <!-- شريط الإجراءات التفاعلي العلوي -->
  <header class="top-action-bar">
    <div class="bar-brand">
      <span>📖</span>
      <span>منظومة المجتهد - تقرير استخراج وتحقيق أكاديمي</span>
    </div>
    <div class="bar-actions">
      <button class="btn-act btn-primary" onclick="window.print()">
        <span>🖨️ طباعة / حفظ كـ PDF</span>
      </button>
      <button class="btn-act" onclick="toggleReportTheme()">
        <span>🌓 تبديل النمط</span>
      </button>
      <button class="btn-act" onclick="adjustReportFontSize(1)">
        <span>A+ تكبير</span>
      </button>
      <button class="btn-act" onclick="adjustReportFontSize(-1)">
        <span>A- تصغير</span>
      </button>
    </div>
  </header>

  <main class="report-container">
    
    <!-- كرت الترويسة الأكاديمية -->
    <section class="report-hero-card">
      <div class="report-badge-top">
        <span>🏛️</span>
        <span>وثيقة علمية رسمية معتمدة عبر الذكاء الاصطناعي والمكتبة الشاملة</span>
      </div>
      <h1 class="report-hero-title">${escapeHtml(title)}</h1>
      
      <div class="report-meta-grid">
        <div class="meta-item">
          <strong>📅 تاريخ الإنجاز:</strong> ${escapeHtml(executedAt)}
        </div>
        <div class="meta-item">
          <strong>🧠 نموذج الإدارة والتحقيق:</strong> ${escapeHtml(directorModel)}
        </div>
        <div class="meta-item">
          <strong>🔄 الجولات التحريرية:</strong> ${rounds.length} جولات منجزة
        </div>
        <div class="meta-item">
          <strong>📚 المستودع المصدري:</strong> الشاملة (8.15M نص)
        </div>
      </div>
    </section>

    <!-- محتوى الجولات -->
    ${roundsHtml}

    <footer class="report-footer-seal">
      تم تحرير وتدقيق هذا التقرير التراثي الأكاديمي آلياً بواسطة منظومة المجتهد المتصلة بالمكتبة الشاملة ووكلاء الذكاء الاصطناعي متعددي الأدوار.
    </footer>

  </main>

  <script>
    function toggleReportTheme() {
      const cur = document.documentElement.getAttribute('data-theme') || 'light';
      const nxt = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', nxt);
    }

    let curFontSize = 18.5;
    function adjustReportFontSize(delta) {
      curFontSize = Math.max(14, Math.min(26, curFontSize + delta));
      document.querySelectorAll('.markdown-body').forEach(el => {
        el.style.fontSize = curFontSize + 'px';
      });
    }

    // دالة استخراج الأرقام بمرونة مع دعم الأرقام المشرقية
    function extractNumericValue(text) {
      if (!text) return NaN;
      let s = String(text).trim();
      s = s.replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
      s = s.replace(/[%٪,،~]/g, ' ');
      const match = s.match(/[-+]?\\d*\\.?\\d+/);
      return match ? parseFloat(match[0]) : NaN;
    }

    const ACADEMIC_COLORS = ['#B45309', '#1D4ED8', '#059669', '#7C3AED', '#DC2626', '#0891B2', '#D97706', '#4F46E5', '#0D9488', '#BE185D'];

    // توليد الشارتات البيانية التلقائية من جداول الماركداون
    document.addEventListener('DOMContentLoaded', () => {
      if (window.Chart) {
        const tables = document.querySelectorAll('.markdown-body table');
        tables.forEach((table, idx) => {
          const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
          const rows = Array.from(table.querySelectorAll('tbody tr'));
          if (rows.length < 2) return;

          let bestNumCol = -1;
          let bestNumCount = 0;
          let bestLblCol = -1;

          for (let c = 0; c < headers.length; c++) {
            let count = 0;
            rows.forEach(r => {
              const cells = r.querySelectorAll('td');
              if (cells[c] && !isNaN(extractNumericValue(cells[c].innerText))) count++;
            });
            const hText = headers[c] || '';
            const isMetric = /نسبة|نسب|أعداد|عدد|مجموع|تكرار|مؤشر|درجة|قيمة|شواهد/i.test(hText);
            const isIdx = /^[#م]$|^الرقم$|^ت$/i.test(hText);
            if (isIdx) continue;
            if (count >= rows.length * 0.4 || isMetric) {
              if (count > bestNumCount || isMetric) {
                bestNumCol = c;
                bestNumCount = count;
              }
            } else if (bestLblCol === -1) {
              bestLblCol = c;
            }
          }

          if (bestNumCol === -1) return;
          if (bestLblCol === -1) bestLblCol = 0;

          const chartLabels = [];
          const chartValues = [];
          rows.forEach(r => {
            const cells = r.querySelectorAll('td');
            if (cells[bestLblCol] && cells[bestNumCol]) {
              const lbl = cells[bestLblCol].innerText.trim();
              const val = extractNumericValue(cells[bestNumCol].innerText);
              if (!isNaN(val) && lbl) {
                chartLabels.push(lbl.length > 28 ? lbl.substring(0, 26) + '..' : lbl);
                chartValues.push(val);
              }
            }
          });

          if (chartLabels.length < 2) return;

          const chartWrapper = document.createElement('div');
          chartWrapper.className = 'chart-render-wrapper';
          const canvasId = 'chart_auto_' + idx;
          chartWrapper.innerHTML = \`
            <div class="chart-render-header">
              <div class="chart-render-title">
                <span>📊</span>
                <span>المؤشرات البيانية المستخرجة: \${headers[bestNumCol] || 'النسب المقارنة'}</span>
              </div>
              <span style="font-size:12px; color:var(--text-muted);">Chart.js</span>
            </div>
            <div style="height: 250px; position: relative;">
              <canvas id="\${canvasId}"></canvas>
            </div>
          \`;
          table.parentNode.insertBefore(chartWrapper, table.nextSibling);

          const canvas = document.getElementById(canvasId);
          if (canvas) {
            const bgColors = chartLabels.map((_, i) => ACADEMIC_COLORS[i % ACADEMIC_COLORS.length]);
            new Chart(canvas, {
              type: 'bar',
              data: {
                labels: chartLabels,
                datasets: [{
                  label: headers[bestNumCol] || 'القيمة',
                  data: chartValues,
                  backgroundColor: bgColors,
                  borderColor: bgColors,
                  borderWidth: 1.5,
                  borderRadius: 6
                }]
              },
              options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: {
                  legend: { display: false },
                  tooltip: { rtl: true }
                }
              }
            });
          }
        });
      }

      // توليد شجرة الأسانيد ورسم شبكة الرواة التفاعلية
      if (window.vis && window.vis.Network) {
        const tables = document.querySelectorAll('.markdown-body table');
        tables.forEach((table, idx) => {
          const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
          const isHadith = headers.some(h => /راوي|الراوي|الشيخ|السند|طريق|المدار|الصحابي|التابعي|الإسناد/i.test(h));
          if (!isHadith) return;

          const rows = Array.from(table.querySelectorAll('tbody tr'));
          if (rows.length < 2) return;

          const nodes = [];
          const edges = [];
          let prev = null;
          rows.forEach((r, rIdx) => {
            const cells = Array.from(r.querySelectorAll('td')).map(td => td.innerText.trim());
            const name = cells[1] || cells[0];
            const info = cells[2] || '';
            if (name && name.length > 2 && !/^\\d+$/.test(name)) {
              const id = rIdx + 1;
              const isMadar = /مدار|أصل/i.test(name) || /مدار/i.test(info);
              const isSahabi = /رضي الله عنه|صحابي/i.test(name) || /صحابي/i.test(info);
              nodes.push({
                id: id,
                label: name.length > 25 ? name.substring(0, 23) + '..' : name,
                shape: isMadar ? 'box' : 'ellipse',
                color: isMadar ? '#B45309' : (isSahabi ? '#1E3A8A' : '#059669'),
                title: info || name
              });
              if (prev !== null) {
                edges.push({ from: prev, to: id, label: 'عن' });
              }
              prev = id;
            }
          });

          if (nodes.length >= 2) {
            const isnadWrapper = document.createElement('div');
            isnadWrapper.className = 'isnad-render-wrapper';
            const treeId = 'isnad_auto_' + idx;
            isnadWrapper.innerHTML = \`
              <div class="isnad-render-header">
                <div class="isnad-render-title">
                  <span>🌳</span>
                  <span>شجرة الأسانيد وشبكة الرواة التفاعلية: \${headers[1] || headers[0] || 'سلسلة الإسناد'}</span>
                </div>
                <span style="font-size:12px; color:var(--text-muted);">Vis.js Network</span>
              </div>
              <div id="\${treeId}" class="isnad-canvas-container" style="height: 280px; width:100%;"></div>
            \`;
            table.parentNode.insertBefore(isnadWrapper, table.nextSibling);

            const cEl = document.getElementById(treeId);
            if (cEl) {
              new vis.Network(cEl, { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) }, {
                layout: { hierarchical: { direction: 'UD', sortMethod: 'directed', levelSeparation: 65, nodeSpacing: 100 } },
                nodes: { font: { face: 'Amiri, Tajawal, sans-serif', size: 13, color: '#FFFFFF' }, borderWidth: 1.5, margin: 6 },
                edges: { arrows: 'to', font: { face: 'Tajawal, sans-serif', size: 10, align: 'middle' }, color: '#B45309' }
              });
            }
          }
        });
      }

      // توليد خرائط وشجرة Markmap التفاعلية
      if (window.markmap && window.markmap.Markmap) {
        document.querySelectorAll('.markdown-body pre code').forEach((codeEl, idx) => {
          if (codeEl.className.includes('markmap') || codeEl.className.includes('mindmap')) {
            const raw = codeEl.innerText.trim();
            const pre = codeEl.closest('pre');
            const svgId = 'markmap_auto_' + idx;
            const w = document.createElement('div');
            w.className = 'isnad-render-wrapper';
            w.innerHTML = \`
              <div class="isnad-render-header">
                <div class="isnad-render-title">
                  <span>🌳</span>
                  <span>الخريطة الذهنية والشجرة التفاعلية (Markmap)</span>
                </div>
                <span style="font-size:12px; color:var(--text-muted);">Markmap D3</span>
              </div>
              <div style="height: 380px; width:100%; border:1px solid var(--border-subtle); border-radius:6px; background:var(--bg-muted); overflow:hidden;">
                <svg id="\${svgId}" style="width:100%; height:100%;"></svg>
              </div>
            \`;
            pre.parentNode.insertBefore(w, pre.nextSibling);
            pre.style.display = 'none';
            try {
              const { Transformer, Markmap } = window.markmap;
              const { root } = new Transformer().transform(raw);
              Markmap.create(document.getElementById(svgId), { autoFit: true }, root);
            } catch (e) { pre.style.display = 'block'; }
          }
        });
      }
    });
  </script>

</body>
</html>`;
}

// =============================================================================
// تصدير وتحميل تقرير HTML تفاعلي متكامل
// =============================================================================
function downloadProjectReportHtml() {
  if (!currentProjectRunData) {
    showToast('لا توجد نتائج تشغيل متاحة لتصدير HTML');
    return;
  }
  const title = currentProjectRunData.projectTitle || 'تقرير_المشروع';
  const htmlContent = buildStandaloneProjectHtml(currentProjectRunData);
  const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.setAttribute('href', url);
  a.setAttribute('download', `report_${title.replace(/[\s\/\\:*?"<>|]/g, '_')}.html`);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('🎉 تم تصدير تقرير HTML التفاعلي المستقل بنجاح!');
}

// =============================================================================
// تصدير وتحميل تقرير PDF أكاديمي عالي الدقة مستخرج من HTML
// =============================================================================
async function downloadProjectReportPdf() {
  if (!currentProjectRunData) {
    showToast('لا توجد نتائج تشغيل متاحة لتصدير PDF');
    return;
  }
  const title = currentProjectRunData.projectTitle || 'تقرير_المشروع';
  const htmlContent = buildAcademicPaperHtml(currentProjectRunData, { toolbar: false, forPdf: true });

  showToast('جارٍ إعداد وتوليد ملف PDF الأكاديمي عالي الدقة... ⏳');

  try {
    const res = await fetch('/api/projects/export-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        html: htmlContent,
        title: title
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'فشل السيرفر في توليد PDF');
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('href', url);
    a.setAttribute('download', `report_${title.replace(/[\s\/\\:*?"<>|]/g, '_')}.pdf`);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('🎉 تم تحميل تقرير PDF الأكاديمي بنجاح!');
  } catch (err) {
    console.warn('Server PDF generation failed, falling back to browser print:', err);
    showToast('تم فتح المعاينة الأكاديمية للطباعة والحفظ المباشر كـ PDF 🖨️');
    const printWin = window.open('', '_blank');
    if (printWin) {
      printWin.document.open();
      printWin.document.write(htmlContent);
      printWin.document.close();
      setTimeout(() => {
        printWin.focus();
        printWin.print();
      }, 500);
    }
  }
}

// =============================================================================
// طباعة وإخراج البحث الأكاديمي الشرعي المحكم وفق الوسوم المعتمدة [6] و [7] و [8]
// =============================================================================
function toArabicIndicDigits(str) {
  if (str === null || str === undefined) return '';
  const arabicDigits = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
  return String(str).replace(/[0-9]/g, w => arabicDigits[+w]);
}

function formatAcademicBody(rawMarkdown) {
  rawMarkdown = (typeof enforceStandardCitations === 'function') ? enforceStandardCitations(rawMarkdown || '') : (rawMarkdown || '');
  if (!rawMarkdown) return '';
  let text = String(rawMarkdown).replace(/\n{3,}/g, '\n\n');
  text = text.replace(/([^\n])[ \t]*(أولًا:|أولاً:|ثانيًا:|ثانياً:|ثالثًا:|ثالثاً:|رابعًا:|رابعاً:|خامسًا:|خامساً:|سادسًا:|سابعًا:|ثامنًا:|تاسعًا:|عاشرًا:)/g, '$1\n$2');
  const footnoteBlocks = [];
  const keptSup = [];
  text = text.replace(/(?:<br\s*\/?>\s*)*<hr\b[^>]*>(?:\s*<br\s*\/?>)*\s*(?=<ol>)/gi, '');
  text = text.replace(/<ol>([\s\S]*?)<\/ol>/gi, (full, inner) => {
    if (!/fn\d+/.test(inner)) return full;
    const flat = inner.replace(/<\/?sup>|<\/?small>/gi, '');
    footnoteBlocks.push(`<ol class="footnote-list">${flat}</ol>`);
    return `\n\nFNBLOCK${footnoteBlocks.length - 1}ENDFN\n\n`;
  });
  text = text.replace(/<sup>\s*<small>\s*\(([^<]{1,16})\)\s*<\/small>\s*<\/sup>/gi, (_, number) => {
    keptSup.push(number);
    return `SUPKEEP${keptSup.length - 1}ENDSUP`;
  });
  text = text.replace(/\[\^?(\d+|[٠-٩]+)\]|\(([\d٠-٩]+)\)/g, (match, first, second) => {
    const num = first || second;
    return `<sup><small>(${toArabicIndicDigits(num)})</small></sup>`;
  });
  text = text.replace(/SUPKEEP(\d+)ENDSUP/g, (_, index) => `<sup><small>(${keptSup[+index] || ''})</small></sup>`);
  text = text.replace(/(^|\n)(\d+)[.-]\s+/g, (match, lead, num) => `${lead}${toArabicIndicDigits(num)}- `);
  text = text.replace(/(القول الأول:|القول الثاني:|القول الثالث:|الدليل الأول:|الدليل الثاني:|الدليل الثالث:|المطلب الأول:|المطلب الثاني:|المسألة الأولى:|المسألة الثانية:)/g, '<b>$1</b>');

  let html = typeof marked !== 'undefined' ? marked.parse(text) : text.replace(/\n/g, '<br>');
  html = html.replace(/<p>\s*FNBLOCK(\d+)ENDFN\s*<\/p>/g, (_, index) => footnoteBlocks[+index] || '');
  html = html.replace(/FNBLOCK(\d+)ENDFN/g, (_, index) => footnoteBlocks[+index] || '');
  html = html.replace(/(?:<br\s*\/?>\s*)*<hr\b[^>]*>(?:\s*<br\s*\/?>)*\s*(?=<ol class="footnote-list">)/gi, '');
  let inBibliography = false;
  html = html.replace(/<(p|h[1-6])([^>]*)>([\s\S]*?)<\/\1>/g, (match, tag, attrs, content) => {
    const plain = content.replace(/<[^>]+>/g, '').trim();
    if (/المصادر والمراجع|ثبت المصادر/.test(plain)) {
      inBibliography = true;
      return `<h2 class="biblio-title">${content}</h2>`;
    }
    if (tag !== 'p') return match;
    const isFootnote = inBibliography
      || /^(<sup>|ينظر:|يُنظر:|أخرجه|رواه)/.test(plain)
      || /^\([\d٠-٩]+\)/.test(plain);
    if (isFootnote) {
      return `<p class="footnote-line">${content}</p>`;
    }
    if (/text-indent/.test(attrs)) return match;
    return `<p class="academic-paragraph">${content}</p>`;
  });
  return html;
}

function buildAcademicPaperHtml(runData, options) {
  const settings = options || {};
  if (!runData) return '';
  const title = runData.projectTitle || 'بحث تحقيقي محكم';
  const rounds = (runData.rounds && runData.rounds.length > 0)
    ? runData.rounds
    : [{ round: 1, name: 'المرحلة التحريرية الكاملة', output: runData.rawOutput }];
  const roundsBodyHtml = rounds.map(r => `
    <section class="academic-round-section">
      <h2 class="academic-round-title">${escapeHtml(r.name || `الجولة رقم ${toArabicIndicDigits(r.round)}`)}</h2>
      <div class="academic-text-content">${formatAcademicBody(r.output || '')}</div>
    </section>
  `).join('');
  const toolbar = settings.toolbar === false ? '' : `
  <div class="no-print-toolbar">
    <div class="toolbar-label">إخراج البحث الأكاديمي المحكم</div>
    <button class="btn-do-print" onclick="window.print()">بدء الطباعة أو الحفظ كـ PDF</button>
  </div>`;
  const pageMargin = settings.forPdf ? '0' : '25mm 20mm 25mm 20mm';

  return `<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Amiri:ital,wght@0,400;0,700;1,400&family=Tajawal:wght@500;700&display=swap" rel="stylesheet">
  <style>
    @page { size: A4 portrait; margin: ${pageMargin}; }
    * { box-sizing: border-box; }
    body {
      background: #FFFFFF;
      color: #111111;
      font-family: 'Amiri', serif;
      font-size: 18pt;
      line-height: 2.1;
      direction: rtl;
      text-align: right;
      margin: 0 auto;
      max-width: 900px;
    }
    .print-cover-header { text-align: center; margin-bottom: 28px; padding-bottom: 18px; border-bottom: 3px double #222; }
    .paper-bismillah { font-size: 24pt; font-weight: 700; margin-bottom: 18px; }
    .paper-main-title { font-size: 25pt; font-weight: 700; line-height: 1.6; margin: 0 0 12px; }
    .paper-sub-meta { font-family: 'Tajawal', sans-serif; font-size: 12pt; color: #475569; }
    .academic-round-title { font-size: 21pt; border-bottom: 2px solid #333; padding-bottom: 6px; margin: 24px 0 12px; text-indent: 0; }
    .academic-paragraph { text-indent: 30px; margin: 0; line-height: 2.1; font-size: 18pt; text-align: justify; }
    .footnote-line, .biblio-title { text-indent: 0 !important; margin: 0; }
    .footnote-line { font-size: 14pt; line-height: 1.7; }
    ol.footnote-list { list-style: none; margin: 16px 0 0; padding: 8px 0 0; }
    ol.footnote-list::before {
      content: "";
      display: block;
      width: 25%;
      border-top: 1px solid #000;
      margin: 0 0 8px;
    }
    ol.footnote-list li { list-style: none; margin: 0; padding: 0; font-size: 14pt; line-height: 1.7; }
    ol.footnote-list sup, ol.footnote-list small { vertical-align: baseline; font-size: inherit; font-weight: 400; }
    .biblio-title { font-size: 20pt; margin-top: 22px; }
    h1, h2, h3, h4 { text-indent: 0; }
    sup small { font-size: 11pt; font-weight: 700; vertical-align: super; }
    b, strong { font-weight: 700; }
    p { margin: 0; }
    table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13pt; }
    th, td { border: 1px solid #444; padding: 8px 12px; text-align: right; text-indent: 0; }
    .no-print-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 18px; }
    .toolbar-label, .btn-do-print { font-family: 'Tajawal', sans-serif; }
    .btn-do-print { background: #B45309; color: #fff; border: none; padding: 8px 16px; font-weight: 700; cursor: pointer; }
    @media print { .no-print-toolbar { display: none !important; } body { max-width: 100%; } }
  </style>
</head>
<body>
  ${toolbar}
  <header class="print-cover-header">
    <div class="paper-bismillah">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</div>
    <h1 class="paper-main-title">${escapeHtml(title)}</h1>
    <div class="paper-sub-meta">بحث علمي محكم مستخرج عبر منظومة المجتهد</div>
  </header>
  <main>${roundsBodyHtml}</main>
</body>
</html>`;
}

function printAcademicPaper() {
  if (!currentProjectRunData) {
    showToast('لا توجد نتائج تشغيل متاحة للطباعة الأكاديمية');
    return;
  }
  const fullPrintHtml = buildAcademicPaperHtml(currentProjectRunData, { toolbar: true });
  const printWin = window.open('', '_blank');
  if (printWin) {
    printWin.document.open();
    printWin.document.write(fullPrintHtml);
    printWin.document.close();
    showToast('تم فتح صفحة البحث الأكاديمي بتنسيق الطباعة المحكم');
    setTimeout(() => { printWin.focus(); }, 400);
  }
}

window.printAcademicPaper = printAcademicPaper;
window.buildAcademicPaperHtml = buildAcademicPaperHtml;

function exportCurrentProjectResultsModal() {
  downloadProjectResultsCsv('results');
}

// دوال مساعدة لضبط الحقول
function getValue(id) {
  return (document.getElementById(id)?.value || '').trim();
}

function setValue(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

function getCheckbox(id) {
  return document.getElementById(id)?.checked || false;
}

function setCheckbox(id, checked) {
  const el = document.getElementById(id);
  if (el) el.checked = Boolean(checked);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// تصدير للدوال العامة
window.initProjectsTab = initProjectsTab;
window.renderProjectsList = renderProjectsList;
window.filterProjectsList = filterProjectsList;
window.openProjectWorkspace = openProjectWorkspace;
window.closeProjectWorkspace = closeProjectWorkspace;
window.toggleComponentCard = toggleComponentCard;
window.syncProjectLinkedGroup = syncProjectLinkedGroup;
window.openProjectPlanningModal = openProjectPlanningModal;
window.closeProjectPlanningModal = closeProjectPlanningModal;
window.backToPlanningStep1 = function () {
  const step2 = document.getElementById('projectPlanningStep2');
  const step1 = document.getElementById('projectPlanningStep1');
  if (step2) step2.style.display = 'none';
  if (step1) step1.style.display = 'block';
};
if (typeof generateProjectBlueprint !== 'undefined') window.generateProjectBlueprint = generateProjectBlueprint;
if (typeof applyGeneratedBlueprintToProject !== 'undefined') window.applyGeneratedBlueprintToProject = applyGeneratedBlueprintToProject;

// تصدير دوال التحكم والضبط بالوكلاء المساعدين للنافذة
window.openProjectSubagentConfigModal = openProjectSubagentConfigModal;
window.closeProjectSubagentConfigModal = closeProjectSubagentConfigModal;
window.handleProjectSubagentModalOverlay = handleProjectSubagentModalOverlay;
window.populateProjectSubagentModelsDropdown = populateProjectSubagentModelsDropdown;
window.filterProjectSubagentModels = filterProjectSubagentModels;
window.clearProjectSubagentModelFilter = clearProjectSubagentModelFilter;
window.onProjectSubagentModelChanged = onProjectSubagentModelChanged;
window.syncSubagentScannedInput = syncSubagentScannedInput;
window.syncSubagentScannedRange = syncSubagentScannedRange;
window.syncSubagentTemp = syncSubagentTemp;
window.syncSubagentTopP = syncSubagentTopP;
window.syncSubagentFreqPen = syncSubagentFreqPen;
window.syncSubagentPresPen = syncSubagentPresPen;
window.renderProjectSubagentBooksChips = renderProjectSubagentBooksChips;
window.removeProjectSubagentBookChip = removeProjectSubagentBookChip;
window.clearProjectSubagentBooksScope = clearProjectSubagentBooksScope;
window.openProjectSubagentScopePicker = openProjectSubagentScopePicker;
window.openProjectSubagentScopePickerFromCard = openProjectSubagentScopePickerFromCard;
window.saveProjectSubagentConfig = saveProjectSubagentConfig;
window.addNewProjectSubagent = addNewProjectSubagent;
window.deleteCurrentProjectSubagent = deleteCurrentProjectSubagent;
window.runProjectSubagentTestLive = runProjectSubagentTestLive;
window.syncSubagentTestContextUI = syncSubagentTestContextUI;

window.openNewManualProjectModal = openNewManualProjectModal;
window.closeManualProjectModal = closeManualProjectModal;
window.saveNewManualProject = saveNewManualProject;
window.deleteProject = deleteProject;
window.exportProjectsData = exportProjectsData;
window.exportSingleProject = exportSingleProject;
window.shareActiveProject = shareActiveProject;
window.triggerImportProjectFile = triggerImportProjectFile;
window.handleProjectFileImport = handleProjectFileImport;
window.runCurrentProjectExecution = runCurrentProjectExecution;
window.downloadProjectResultsCsv = downloadProjectResultsCsv;
window.downloadProjectRunReportTxt = downloadProjectRunReportTxt;
window.downloadProjectReportHtml = downloadProjectReportHtml;
window.downloadProjectReportPdf = downloadProjectReportPdf;
window.buildStandaloneProjectHtml = buildStandaloneProjectHtml;
window.exportCurrentProjectResultsModal = exportCurrentProjectResultsModal;
window.manualSaveProjectWorkspace = manualSaveProjectWorkspace;
window.sendArchitectMessage = sendArchitectMessage;
window.applyStudioBlueprint = applyStudioBlueprint;
window.applyQuickStudioPrompt = applyQuickStudioPrompt;
window.handleArchitectInputKeydown = handleArchitectInputKeydown;
window.renderStudioCardsPreview = renderStudioCardsPreview;
window.updateActiveProjectCardsFromBlueprint = updateActiveProjectCardsFromBlueprint;
window.clearStudioBlueprintCards = clearStudioBlueprintCards;
window.resetCurrentProjectCards = resetCurrentProjectCards;
window.resolveAndVerifyProjectBooks = resolveAndVerifyProjectBooks;
window.handleStudioBookSearch = handleStudioBookSearch;
window.clearStudioBookSearch = clearStudioBookSearch;
window.handleStudioBookCatFilter = handleStudioBookCatFilter;
window.toggleStudioBooksDrawer = toggleStudioBooksDrawer;
window.insertBookIntoArchitectChat = insertBookIntoArchitectChat;
window.renderStudioBooksDrawer = renderStudioBooksDrawer;
window.toggleProjectCard = toggleProjectCard;
window.collapseAllProjectCards = collapseAllProjectCards;
window.expandAllProjectCards = expandAllProjectCards;
window.updateCardQuickSummaries = updateCardQuickSummaries;
window.transferProjectResultToChat = transferProjectResultToChat;
window.toggleProjectHybridSearchMode = toggleProjectHybridSearchMode;
window.updateProjectHybridToggleUI = updateProjectHybridToggleUI;
window.startFreshProjectPlanning = startFreshProjectPlanning;
