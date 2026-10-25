// =============================================================================
// منظومة المجتهد - إدارة مجموعات الوكلاء المساعدين (agents.js)
// تنظيم الوكلاء في مجموعات، إنشاء وتكرار وحذف المجموعات، وإدارة النماذج بداخلها
// =============================================================================

const AGENT_GROUPS_STORAGE_KEY = 'almojtahed_agent_groups';
const LEGACY_AGENTS_STORAGE_KEY = 'almojtahed_sub_agents';

// قائمة الوكلاء الافتراضية التراثية المتخصصة
const DEFAULT_AGENTS = [
  {
    id: 'agent_fiqh',
    name: 'وكيل الفقه وأصوله',
    desc: 'متخصص في تحرير الفروع الفقهية على المذاهب الأربعة، وتخريج الفروع على الأصول، والقواعد والضوابط الفقهية.',
    enabled: true,
    systemPrompt: 'أنت وكيل الفقه وأصوله في منظومة المجتهد. مهمتك استخراج المسائل الفقهية وتحرير المعتمد في المذاهب الأربعة مع عزو كل قول لكتابه وصفحته بدقة تامة.',
    temp: 0.15,
    topK: 40,
    repPenalty: 1.1,
    maxTokens: 32768,
    poolSize: 300
  },
  {
    id: 'agent_hadith',
    name: 'وكيل الحديث والرجال',
    desc: 'متخصص في تخريج الأحاديث، وتتبع الأسانيد، والحكم على الرواة من كتب الجرح والتعديل وكتب العلل.',
    enabled: true,
    systemPrompt: 'أنت وكيل الحديث والرجال في منظومة المجتهد. مهمتك تخريج الأحاديث النبوية وبيان طرقها وأحكام أئمة الصنعة كالبخاري وأبي حاتم وابن حجر.',
    temp: 0.1,
    topK: 30,
    repPenalty: 1.15,
    maxTokens: 32768,
    poolSize: 400
  },
  {
    id: 'agent_tafsir',
    name: 'وكيل التفسير وعلوم القرآن',
    desc: 'متخصص في تحرير أقوال المفسرين بالمأثور وبالدراية، وأسباب النزول، وغريب القرآن والقراءات.',
    enabled: true,
    systemPrompt: 'أنت وكيل التفسير وعلوم القرآن في منظومة المجتهد. مهمتك جمع تفاسير الآيات من الطبري والقرطبي وابن كثير وغيرهم مع بيان وجوه الإعراب والمعاني.',
    temp: 0.2,
    topK: 40,
    repPenalty: 1.1,
    maxTokens: 32768,
    poolSize: 250
  },
  {
    id: 'agent_history',
    name: 'وكيل التاريخ والتراجم',
    desc: 'متخصص في توثيق وفيات العلماء، وأخبار الأمصار، والأحداث التاريخية وسير الأعلام والملوك.',
    enabled: true,
    systemPrompt: 'أنت وكيل التاريخ والتراجم في منظومة المجتهد. مهمتك استخراج تراجم الأعلام من تاريخ دمشق وسير أعلام النبلاء والبداية والنهاية.',
    temp: 0.25,
    topK: 50,
    repPenalty: 1.05,
    maxTokens: 65536,
    poolSize: 200
  }
];

let agentGroups = [];

// مزامنة قطعية ثنائية الاتجاه بين المتغير الداخلي و window.agentGroups
try {
  Object.defineProperty(window, 'agentGroups', {
    get() { return agentGroups; },
    set(val) { agentGroups = Array.isArray(val) ? val : []; },
    configurable: true
  });
} catch (e) {
  window.agentGroups = agentGroups;
}

let currentActiveGroupId = null;

// التوافقية العكسية للقوائم العامة
let subAgentsList = [];

// دالة حماية النصوص
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', () => {
  loadAgentGroups();
  renderGroupsTable();
});

// =============================================================================
// إدارة المجموعات (Agent Groups Management)
// =============================================================================

// تحميل المجموعات من التخزين المحلي وخادم المنظومة
async function loadAgentGroups() {
  await (window.almujtahedIdentity || Promise.resolve());
  try {
    const rawGroups = localStorage.getItem(ownerStorageKey(AGENT_GROUPS_STORAGE_KEY));
    if (rawGroups) {
      agentGroups = JSON.parse(rawGroups);
    }
  } catch (e) {
    console.error('Error reading local agent groups:', e);
  }

  // ملف الخادم هو المرجع بعد الأرشفة والاسترجاع، بما في ذلك القائمة الفارغة
  let storedOnServer = false;
  try {
    const res = await fetch('/api/agent-groups');
    if (res.ok) {
      const serverGroups = await res.json();
      storedOnServer = res.headers.get('X-Agent-Groups-Stored') === '1';
      if (Array.isArray(serverGroups) && (storedOnServer || serverGroups.length > 0)) {
        agentGroups = serverGroups;
        localStorage.setItem(ownerStorageKey(AGENT_GROUPS_STORAGE_KEY), JSON.stringify(agentGroups));
      }
    }
  } catch (err) {
    console.warn('Could not fetch server agent groups:', err);
  }

  // المجموعة الافتراضية تُنشأ مرة واحدة فقط إذا لم يُحفظ شيء بعد على الخادم
  if ((!agentGroups || agentGroups.length === 0) && !storedOnServer) {
    let initialAgents = [...DEFAULT_AGENTS];
    const legacyRaw = localStorage.getItem(LEGACY_AGENTS_STORAGE_KEY);
    if (legacyRaw) {
      try {
        const parsed = JSON.parse(legacyRaw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          initialAgents = parsed;
        }
      } catch (e) {}
    }

    agentGroups = [
      {
        id: 'group_heritage_default',
        name: 'مجموعة العلوم التراثية الأساسية',
        desc: 'وكلاء الفقه وأصوله، والحديث ورجاله، والتفسير والتاريخ لتحضير مسائل المخزن والربط مع الشاملة.',
        agents: initialAgents
      }
    ];
    saveAgentGroups();
  }

  syncSubAgentsList();
  window.agentGroups = agentGroups;
  if (typeof populateChatAgentGroupsDropdown === 'function') {
    populateChatAgentGroupsDropdown();
  }
  if (typeof renderGroupsTable === 'function') {
    renderGroupsTable();
  }
}

// حفظ المجموعات في التخزين المحلي وخادم المنظومة
function saveAgentGroups(updatedGroups = null) {
  try {
    if (updatedGroups && Array.isArray(updatedGroups)) {
      agentGroups = updatedGroups;
    } else if (window.agentGroups && Array.isArray(window.agentGroups) && window.agentGroups.length > 0) {
      agentGroups = window.agentGroups;
    }
    window.agentGroups = agentGroups;
    localStorage.setItem(ownerStorageKey(AGENT_GROUPS_STORAGE_KEY), JSON.stringify(agentGroups));
    syncSubAgentsList();
    if (typeof populateChatAgentGroupsDropdown === 'function') {
      populateChatAgentGroupsDropdown();
    }
    if (typeof renderGroupsTable === 'function') {
      renderGroupsTable();
    }
    // حفظ دائم في ملف خادم المنظومة لحماية البيانات عند مسح الكاش
    fetch('/api/agent-groups', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(agentGroups)
    }).catch(err => console.warn('Sync agent groups to server error:', err));
  } catch (e) {
    console.error('Error saving agent groups:', e);
  }
}

// مزامنة قائمة subAgentsList لضمان توافق الشات وإعدادات النماذج
function clearAgentGroupsFromApp() {
  agentGroups = [];
  currentActiveGroupId = null;
  subAgentsList = [];
  try {
    localStorage.setItem(ownerStorageKey(AGENT_GROUPS_STORAGE_KEY), '[]');
    localStorage.removeItem(LEGACY_AGENTS_STORAGE_KEY);
  } catch (e) {}
  window.agentGroups = [];
  if (typeof populateChatAgentGroupsDropdown === 'function') populateChatAgentGroupsDropdown();
  if (typeof renderGroupsTable === 'function') renderGroupsTable();
}

function syncSubAgentsList() {
  if (currentActiveGroupId) {
    const curGroup = agentGroups.find(g => g.id === currentActiveGroupId);
    subAgentsList = curGroup && curGroup.agents ? curGroup.agents : [];
  } else if (agentGroups.length > 0 && agentGroups[0].agents) {
    subAgentsList = agentGroups[0].agents;
  } else {
    subAgentsList = [];
  }
  // حفظ نسخة متوافقة
  try {
    localStorage.setItem(LEGACY_AGENTS_STORAGE_KEY, JSON.stringify(subAgentsList));
  } catch (e) {}
}

// رسم جدول المجموعات
function renderGroupsTable() {
  const tbody = document.getElementById('agentGroupsTableBody');
  if (!tbody) return;

  if (agentGroups.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="4" class="groups-empty-state">
          <p style="font-size: 14px; margin-bottom: 12px;">لا توجد مجموعات حالياً. ابدأ بإنشاء أول مجموعة لتنظيم وكلائك المساعدين.</p>
          <button type="button" class="btn-flat-primary" onclick="openCreateGroupModal()" style="margin: 0 auto;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
            <span>إنشاء مجموعة جديدة</span>
          </button>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = agentGroups.map((group) => {
    const count = group.agents ? group.agents.length : 0;
    return `
      <tr id="row_${group.id}">
        <td>
          <div class="group-name-cell" onclick="openGroupAgents('${group.id}')" title="انقر لعرض وتحرير وكلاء هذه المجموعة">
            <span class="group-icon-avatar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>
            </span>
            <span>${escapeHtml(group.name)}</span>
          </div>
        </td>
        <td>
          <div class="group-desc-cell">${escapeHtml(group.desc)}</div>
        </td>
        <td style="text-align: center;">
          <span class="group-badge-count">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>
            <span>${count} وكيل</span>
          </span>
        </td>
        <td style="text-align: center;">
          <div class="group-actions-cell">
            <!-- زر تحرير (أيقونة): يفتح صفحة إدارة الوكلاء بداخلها وهي الصفحة الحالية -->
            <button type="button" class="action-icon-btn btn-edit-group" onclick="openGroupAgents('${group.id}')" title="تحرير المجموعة وإنشاء النماذج بداخلها">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>

            <!-- زر تكرار المجموعة (أيقونة) -->
            <button type="button" class="action-icon-btn btn-duplicate-group" onclick="duplicateGroup('${group.id}')" title="تكرار المجموعة مع كافة وكلائها">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="13" height="13" x="9" y="9" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>

            <!-- زر تصدير المجموعة (أيقونة) -->
            <button type="button" class="action-icon-btn btn-export-group" onclick="exportSingleGroup('${group.id}')" title="تصدير هذه المجموعة مع كافة وكلائها كملف JSON">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            </button>

            <!-- زر حذف المجموعة (أيقونة) -->
            <button type="button" class="action-icon-btn btn-delete-group" onclick="deleteGroup('${group.id}')" title="حذف المجموعة">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/></svg>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

// فتح نافذة إنشاء مجموعة جديدة
function openCreateGroupModal() {
  document.getElementById('editGroupId').value = '';
  document.getElementById('groupModalTitle').textContent = 'إنشاء مجموعة وكلاء جديدة';
  document.getElementById('groupNameInput').value = '';
  document.getElementById('groupDescInput').value = '';
  document.getElementById('groupModalSubmitBtn').textContent = 'إنشاء';
  document.getElementById('agentGroupModalOverlay').classList.add('open');
  
  setTimeout(() => {
    document.getElementById('groupNameInput')?.focus();
  }, 100);
}

// إغلاق نافذة المجموعة
function closeGroupModal() {
  document.getElementById('agentGroupModalOverlay').classList.remove('open');
}

function handleGroupModalOverlayClick(e) {
  if (e.target.id === 'agentGroupModalOverlay') {
    closeGroupModal();
  }
}

// حفظ أو إنشاء المجموعة من النافذة
function saveGroupFromModal() {
  const id = document.getElementById('editGroupId').value;
  const name = document.getElementById('groupNameInput').value.trim();
  const desc = document.getElementById('groupDescInput').value.trim();

  if (!name) {
    showToast('يرجى تحديد اسم المجموعة');
    document.getElementById('groupNameInput')?.focus();
    return;
  }

  if (!desc) {
    showToast('يرجى كتابة وصف المجموعة');
    document.getElementById('groupDescInput')?.focus();
    return;
  }

  if (id) {
    // تعديل مجموعة قائمة
    const idx = agentGroups.findIndex(g => g.id === id);
    if (idx !== -1) {
      agentGroups[idx].name = name;
      agentGroups[idx].desc = desc;
      showToast(`تم تحديث مجموعة "${name}" بنجاح`);
    }
  } else {
    // إنشاء مجموعة جديدة
    const newGroup = {
      id: 'group_' + Date.now(),
      name: name,
      desc: desc,
      agents: []
    };
    agentGroups.push(newGroup);
    showToast(`تم إنشاء مجموعة "${name}" بنجاح`);
  }

  saveAgentGroups();
  renderGroupsTable();
  closeGroupModal();
}

// تكرار مجموعة
function duplicateGroup(groupId) {
  const original = agentGroups.find(g => g.id === groupId);
  if (!original) return;

  const cloned = JSON.parse(JSON.stringify(original));
  cloned.id = 'group_' + Date.now();
  cloned.name = original.name + ' (نسخة)';
  
  // تجديد معرفات الوكلاء المنسوخين لتفادي التكرار
  if (cloned.agents && Array.isArray(cloned.agents)) {
    cloned.agents.forEach(a => {
      a.id = 'agent_' + Date.now() + '_' + Math.random().toString(36).substring(2, 6);
    });
  }

  agentGroups.push(cloned);
  saveAgentGroups();
  renderGroupsTable();
  showToast(`تم تكرار مجموعة "${cloned.name}" بنجاح`);
}

// حذف مجموعة
async function deleteGroup(groupId) {
  const group = agentGroups.find(g => g.id === groupId);
  if (!group) return;

  const agentCount = group.agents ? group.agents.length : 0;
  const msg = agentCount > 0 
    ? `هل أنت متأكد من حذف مجموعة «${group.name}»؟ سيتم حذف كافة الوكلاء (${agentCount} وكيل) التابعين لها نهائياً.`
    : `هل أنت متأكد من حذف مجموعة «${group.name}» نهائياً؟`;

  const confirmed = await showConfirmDialog({
    title: 'تأكيد حذف مجموعة الوكلاء',
    message: msg,
    confirmText: 'نعم، احذف المجموعة',
    cancelText: 'إلغاء',
    danger: true,
    icon: 'trash-2'
  });

  if (confirmed) {
    agentGroups = agentGroups.filter(g => g.id !== groupId);
    if (currentActiveGroupId === groupId) {
      showAgentGroupsView();
    }
    saveAgentGroups();
    renderGroupsTable();
    showToast(`تم حذف مجموعة "${group.name}" بنجاح`);
  }
}

// دالة مساعدة لتنزيل ملفات JSON
function downloadAgentJsonFile(filename, dataObj) {
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

// 1. تصدير مجموعة وكلاء كاملة كملف JSON
function exportSingleGroup(groupId) {
  const group = agentGroups.find(g => g.id === groupId);
  if (!group) {
    if (typeof showToast === 'function') showToast('المجموعة غير موجودة لتصديرها', true);
    return;
  }
  const cleanName = (group.name || 'group').slice(0, 40).replace(/[^a-zA-Z0-9\u0600-\u06FF_-]/g, '_');
  const filename = `agent_group_${cleanName}_${new Date().toISOString().split('T')[0]}.json`;
  const exportPayload = {
    app: 'almojtahed_system',
    version: '2.0',
    type: 'almojtahed_agent_group',
    exported_at: new Date().toISOString(),
    group: group,
    id: group.id,
    name: group.name,
    desc: group.desc,
    agents: group.agents || []
  };
  downloadAgentJsonFile(filename, exportPayload);
  if (typeof showToast === 'function') {
    showToast(`📤 تم تصدير مجموعة «${group.name}» (${(group.agents || []).length} وكلاء) بنجاح!`);
  }
}

// 2. تصدير المجموعة النشطة حالياً
function exportCurrentActiveGroup() {
  if (!currentActiveGroupId) {
    const first = agentGroups[0];
    if (first) exportSingleGroup(first.id);
    return;
  }
  exportSingleGroup(currentActiveGroupId);
}

// 3. تصدير وكيل مفرد كملف JSON
function exportSingleAgent(agentId) {
  const currentGroup = agentGroups.find(g => g.id === currentActiveGroupId) || agentGroups[0];
  const agents = currentGroup && currentGroup.agents ? currentGroup.agents : subAgentsList;
  const agent = agents.find(a => a.id === agentId);
  if (!agent) {
    if (typeof showToast === 'function') showToast('الوكيل غير موجود لتصديره', true);
    return;
  }
  const cleanName = (agent.name || 'agent').slice(0, 40).replace(/[^a-zA-Z0-9\u0600-\u06FF_-]/g, '_');
  const filename = `agent_${cleanName}_${new Date().toISOString().split('T')[0]}.json`;
  const exportPayload = {
    app: 'almojtahed_system',
    version: '2.0',
    type: 'almojtahed_single_agent',
    exported_at: new Date().toISOString(),
    agent: agent,
    ...agent
  };
  downloadAgentJsonFile(filename, exportPayload);
  if (typeof showToast === 'function') {
    showToast(`📤 تم تصدير الوكيل «${agent.name}» كملف JSON بنجاح!`);
  }
}

// 4. استيراد مجموعة وكلاء أو وكيل مفرد
function triggerImportAgentFile() {
  const input = document.getElementById('agentImportFileInput');
  if (input) {
    input.value = '';
    input.click();
  }
}

async function handleAgentFileImport(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async function (e) {
    try {
      const imported = JSON.parse(e.target.result);
      if (!imported) throw new Error('الملف فارغ');

      // أ) استيراد مجموعة كاملة
      if (imported.type === 'almojtahed_agent_group' || (imported.agents && Array.isArray(imported.agents) && imported.name)) {
        const groupData = imported.group || imported;
        const newGroup = {
          id: groupData.id || `group_${Date.now()}`,
          name: groupData.name || 'مجموعة وكلاء مستوردة',
          desc: groupData.desc || 'مجموعة مستوردة من ملف JSON',
          agents: Array.isArray(groupData.agents) ? groupData.agents : []
        };
        const existingIdx = agentGroups.findIndex(g => g.id === newGroup.id);
        if (existingIdx !== -1) {
          agentGroups[existingIdx] = newGroup;
        } else {
          agentGroups.push(newGroup);
        }
        saveAgentGroups();
        renderGroupsTable();
        if (typeof showToast === 'function') {
          showToast(`📥 تم استيراد مجموعة «${newGroup.name}» بنجاح!`);
        }
        return;
      }

      // ب) استيراد وكيل مفرد
      if (imported.type === 'almojtahed_single_agent' || imported.systemPrompt || imported.system_prompt || imported.role) {
        const agentData = imported.agent || imported;
        const currentGroup = agentGroups.find(g => g.id === currentActiveGroupId) || agentGroups[0];
        if (!currentGroup) {
          throw new Error('لا توجد مجموعة نشطة لإضافة الوكيل إليها');
        }
        if (!currentGroup.agents) currentGroup.agents = [];

        const newAgent = {
          ...agentData,
          id: agentData.id || `agent_${Date.now()}`,
          name: agentData.name || 'وكيل مستورد'
        };

        const existingAgentIdx = currentGroup.agents.findIndex(a => a.id === newAgent.id);
        if (existingAgentIdx !== -1) {
          currentGroup.agents[existingAgentIdx] = newAgent;
        } else {
          currentGroup.agents.push(newAgent);
        }
        saveAgentGroups();
        renderAgentsGrid();
        renderGroupsTable();
        if (typeof showToast === 'function') {
          showToast(`📥 تم استيراد الوكيل «${newAgent.name}» إلى مجموعة «${currentGroup.name}» بنجاح!`);
        }
        return;
      }

      // ج) مصفوفة مجموعات أو وكلاء
      if (Array.isArray(imported)) {
        let importedCount = 0;
        imported.forEach(item => {
          if (item && item.agents && Array.isArray(item.agents)) {
            agentGroups.push(item);
            importedCount++;
          }
        });
        if (importedCount > 0) {
          saveAgentGroups();
          renderGroupsTable();
          if (typeof showToast === 'function') {
            showToast(`📥 تم استيراد ${importedCount} مجموعات بنجاح!`);
          }
          return;
        }
      }

      throw new Error('صيغة الملف غير مدعومة');
    } catch (err) {
      console.error('Import error:', err);
      if (typeof showToast === 'function') {
        showToast('تعذر استيراد الملف: ' + (err.message || 'صيغة غير صالحة'), true);
      }
    }
  };
  reader.readAsText(file, 'utf-8');
}

// =============================================================================
// فتح صفحة وكلاء المجموعة (الصفحة الحالية لإنشاء النماذج)
// =============================================================================

function openGroupAgents(groupId) {
  const group = agentGroups.find(g => g.id === groupId);
  if (!group) return;

  currentActiveGroupId = groupId;
  subAgentsList = group.agents || [];

  // إخفاء جدول المجموعات وعرض صفحة الوكلاء
  document.getElementById('agentGroupsSection').style.display = 'none';
  document.getElementById('groupAgentsDetailSection').style.display = 'block';

  // تحديث عناوين وبيانات المجموعة
  const titleEl = document.getElementById('currentGroupTitle');
  const descEl = document.getElementById('currentGroupDesc');
  const breadcrumbEl = document.getElementById('currentGroupBreadcrumb');

  if (titleEl) titleEl.textContent = `وكلاء: ${group.name}`;
  if (descEl) descEl.textContent = group.desc;
  if (breadcrumbEl) breadcrumbEl.textContent = `مجموعة: ${group.name}`;

  renderAgentsGrid();
}

// العودة إلى جدول المجموعات
function showAgentGroupsView() {
  currentActiveGroupId = null;
  document.getElementById('groupAgentsDetailSection').style.display = 'none';
  document.getElementById('agentGroupsSection').style.display = 'block';
  renderGroupsTable();
}

// =============================================================================
// إدارة الوكلاء داخل المجموعة الحالية (Agent Cards Grid)
// =============================================================================

function cleanAgentModelTitle(modelId) {
  if (!modelId) return 'النموذج الافتراضي';
  if (modelId.includes('sonnet')) return 'Claude Sonnet';
  if (modelId.includes('deepseek-r1')) return 'DeepSeek R1';
  if (modelId.includes('gemini-2.5-pro')) return 'Gemini 2.5 Pro';
  if (modelId.includes('gpt-4o-mini')) return 'GPT-4o Mini';
  if (modelId.includes('gpt-4o')) return 'GPT-4o';
  if (modelId.includes('o3-mini')) return 'o3-mini';
  if (modelId.includes('local')) return 'المحلي (Offline)';
  const parts = modelId.split('/');
  return parts[parts.length - 1];
}

function getThinkingText(level) {
  if (level === 'low') return 'منخفض';
  if (level === 'high') return 'عالي (عميق)';
  return 'متوسط';
}

function renderAgentsGrid() {
  const grid = document.getElementById('agentsCardsGrid');
  if (!grid) return;

  const currentGroup = agentGroups.find(g => g.id === currentActiveGroupId);
  const agents = currentGroup && currentGroup.agents ? currentGroup.agents : subAgentsList;

  if (agents.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 48px 20px; background: var(--bg-surface); border: 1px dashed var(--border-subtle); border-radius: var(--radius-md);">
        <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 14px;">لا يوجد وكلاء في هذه المجموعة بعد.</p>
        <button type="button" class="btn-flat-primary" onclick="openAddAgentModal()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
          <span>إضافة وكيل مساعد جديد لهذه المجموعة</span>
        </button>
      </div>
    `;
    return;
  }

  grid.innerHTML = agents.map((agent) => {
    const booksList = (agent.booksScope && Array.isArray(agent.booksScope)) ? agent.booksScope : (agent.books && Array.isArray(agent.books)) ? agent.books : [];
    const scopeCount = booksList.length;
    const scopeLabel = scopeCount > 0 ? `نطاق: ${scopeCount} كتب` : 'نطاق: جميع كتب الشاملة';
    const isEnabled = agent.enabled !== false && agent.active !== false;
    const promptText = agent.systemPrompt || agent.system_prompt || '';
    const maxTokensVal = agent.maxTokens || agent.max_tokens || 65536;

    return `
      <div class="agent-card" id="card_${agent.id}">
        <div class="agent-card-header">
          <div class="agent-title-row">
            <span class="agent-name">${escapeHtml(agent.name)}</span>
          </div>
          <!-- زر التفعيل / التعطيل التفاعلي Flat Toggle -->
          <label class="switch-toggle" title="${isEnabled ? 'تعطيل الوكيل' : 'تفعيل الوكيل'}">
            <input type="checkbox" ${isEnabled ? 'checked' : ''} onchange="toggleAgentActive('${agent.id}', this.checked)">
            <span class="slider-toggle"></span>
          </label>
        </div>

        <p class="agent-desc">${escapeHtml(agent.desc || 'وكيل استخراج نصوص الشاملة')}</p>

        <!-- شبكة شارات المعلمات والنماذج والنطاق المخصص -->
        <div class="agent-params-badge-grid">
          <span class="param-badge" style="color: var(--accent-clay); border-color: rgba(197, 160, 89, 0.4); font-weight: 600;">
            🤖 ${cleanAgentModelTitle(agent.model)}
          </span>
          <span class="param-badge">
            🧠 تفكير: ${getThinkingText(agent.thinking || 'medium')}
          </span>
          <span class="param-badge" style="${scopeCount > 0 ? 'color: #3b82f6; border-color: rgba(59, 130, 246, 0.4); font-weight: 600;' : ''}">
            📚 ${scopeLabel}
          </span>
          <span class="param-badge">حرارة: ${agent.temp ?? 0.2}</span>
          <span class="param-badge">Top-K: ${agent.topK ?? agent.top_k ?? 40}</span>
          <span class="param-badge">توكن: ${Number(maxTokensVal).toLocaleString()}</span>
          <span class="param-badge" style="color: var(--accent-clay); border-color: var(--accent-clay);">
            استرجاع دلالي مباشر (${agent.topK ?? agent.top_k ?? 40} نص)
          </span>
        </div>

        <!-- التوجيه التخصصي المحدد من المهندس -->
        <div style="font-size: 12px; color: var(--text-light); background: var(--bg-canvas); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px dashed var(--border-subtle); margin-top: 6px; line-height: 1.5; max-height: 64px; overflow-y: auto;">
          <strong style="color: var(--accent-clay);">💬 التوجيه:</strong> ${escapeHtml(promptText || 'استخراج نصوص المسألة بدقة مع أرقام الأجزاء والصفحات.')}
        </div>

        ${scopeCount > 0 ? `
          <div style="font-size: 11.5px; color: var(--text-secondary); background: rgba(59, 130, 246, 0.05); border: 1px solid rgba(59, 130, 246, 0.18); padding: 6px 10px; border-radius: var(--radius-sm); margin-top: 6px; max-height: 52px; overflow-y: auto;">
            <strong style="color: #2563eb;">📚 الكتب المحددة (${scopeCount}):</strong> ${escapeHtml(booksList.join('، '))}
          </div>
        ` : ''}

        <div class="agent-card-footer">
          <div style="display: flex; gap: 6px; align-items: center;">
            <button type="button" class="btn-flat-secondary" onclick="editAgent('${agent.id}')" style="font-size: 12.5px; padding: 4px 12px;">
              تعديل
            </button>
            <button type="button" class="btn-flat-secondary" onclick="exportSingleAgent('${agent.id}')" style="font-size: 12.5px; padding: 4px 10px;" title="تصدير هذا الوكيل كملف JSON">
              <span>تصدير 📤</span>
            </button>
          </div>
          <button type="button" class="btn-flat-secondary" onclick="deleteAgent('${agent.id}')" style="font-size: 12.5px; padding: 4px 10px; color: #c0392b;" title="حذف الوكيل">
            حذف
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// تفعيل أو تعطيل وكيل معين داخل المجموعة الحالية
function toggleAgentActive(id, isChecked) {
  const currentGroup = agentGroups.find(g => g.id === currentActiveGroupId) || agentGroups[0];
  if (!currentGroup || !currentGroup.agents) return;

  const agent = currentGroup.agents.find(a => a.id === id);
  if (agent) {
    agent.enabled = isChecked;
    agent.active = isChecked;
    saveAgentGroups();
    showToast(`تم ${isChecked ? 'تفعيل' : 'تعطيل'} ${agent.name}`);
  }
}

// حذف وكيل من المجموعة الحالية
async function deleteAgent(id) {
  const currentGroup = agentGroups.find(g => g.id === currentActiveGroupId) || agentGroups[0];
  if (!currentGroup || !currentGroup.agents) return;

  const agent = currentGroup.agents.find(a => a.id === id);
  if (!agent) return;

  const confirmed = await showConfirmDialog({
    title: 'تأكيد حذف الوكيل',
    message: `هل أنت متأكد من رغبتك في حذف الوكيل «${agent.name}» من هذه المجموعة؟`,
    confirmText: 'نعم، احذف الوكيل',
    cancelText: 'إلغاء',
    danger: true,
    icon: 'user-x'
  });

  if (confirmed) {
    currentGroup.agents = currentGroup.agents.filter(a => a.id !== id);
    saveAgentGroups();
    renderAgentsGrid();
    showToast('تم حذف الوكيل بنجاح');
  }
}

// =============================================================================
// إدارة قائمة النماذج في نافذة إنشاء / تعديل الوكيل
// =============================================================================

function populateAgentModelDropdown(targetModelId = null) {
  const customListEl = document.getElementById('agentCustomModelOptionsList');
  const triggerTextEl = document.getElementById('agentCustomModelTriggerText');
  const hiddenInput = document.getElementById('agentSelectedModelId');
  if (!customListEl) return;

  const activeProvider = localStorage.getItem(ownerStorageKey('almojtahed_active_provider')) || 'openrouter';
  const selectedModelId = targetModelId || hiddenInput?.value || 'anthropic/claude-3.7-sonnet';

  const groups = [];

  if (activeProvider === 'openrouter') {
    const modelsList = (window.openrouterModelsList && window.openrouterModelsList.length > 0) 
      ? window.openrouterModelsList 
      : ((typeof openrouterModelsList !== 'undefined' && openrouterModelsList.length > 0) ? openrouterModelsList : []);

    if (modelsList.length > 0) {
      const priorityIds = [
        'anthropic/claude-3.7-sonnet',
        'anthropic/claude-3.5-haiku',
        'google/gemini-2.5-flash',
        'google/gemini-3.8-flash',
        'google/gemini-2.5-pro',
        'deepseek/deepseek-r1',
        'deepseek/deepseek-chat',
        'openai/o3-mini',
        'openai/gpt-4o',
        'openai/gpt-4o-mini',
        'meta-llama/llama-3.3-70b-instruct',
        'qwen/qwen-2.5-72b-instruct'
      ];
      const priorityModels = [];
      const otherModels = [];

      priorityIds.forEach(pid => {
        const found = modelsList.find(m => m.id === pid || m.id.includes(pid));
        if (found && !priorityModels.some(p => p.id === found.id)) {
          priorityModels.push(found);
        }
      });

      modelsList.forEach(m => {
        if (!priorityModels.some(p => p.id === m.id)) {
          otherModels.push(m);
        }
      });

      groups.push({
        title: '⭐ نماذج OpenRouter الموصى بها للأبحاث',
        models: priorityModels
      });

      if (otherModels.length > 0) {
        groups.push({
          title: `📋 كافة نماذج OpenRouter المتاحة (${otherModels.length} نموذج)`,
          models: otherModels
        });
      }
    } else {
      // جلب النماذج الحية في الخلفية تلقائياً إذا لم تكن محملة بعد
      fetch('/api/openrouter/models')
        .then(res => res.json())
        .then(data => {
          if (data && data.models && data.models.length > 0) {
            window.openrouterModelsList = data.models;
            if (typeof openrouterModelsList !== 'undefined') openrouterModelsList = data.models;
            populateAgentModelDropdown(targetModelId || document.getElementById('agentSelectedModelId')?.value);
          }
        })
        .catch(e => console.warn('Background models fetch:', e));

      groups.push({
        title: 'نماذج OpenRouter الرائدة',
        models: [
          { id: 'anthropic/claude-3.7-sonnet', name: 'Claude 3.7 Sonnet (Thinking)' },
          { id: 'google/gemini-2.5-flash', name: 'Gemini 2.5 Flash (سريع وفائق الاستدلال)' },
          { id: 'google/gemini-2.5-pro', name: 'Gemini 2.5 Pro (Long-Context)' },
          { id: 'deepseek/deepseek-r1', name: 'DeepSeek R1 (Reasoning)' },
          { id: 'openai/gpt-4o', name: 'GPT-4o (Omni)' },
          { id: 'openai/o3-mini', name: 'o3-mini (High Reasoning)' },
          { id: 'openai/gpt-4o-mini', name: 'GPT-4o Mini (سريع واقتصادي)' }
        ]
      });
    }
  } else {
    const presets = (typeof PROVIDER_MODELS_PRESETS !== 'undefined' && PROVIDER_MODELS_PRESETS[activeProvider]) || [];
    const providerTitle = typeof getProviderLabel === 'function' ? getProviderLabel(activeProvider) : activeProvider;
    groups.push({
      title: `نماذج ${providerTitle}`,
      models: presets
    });
  }

  groups.push({
    title: 'المحلي (Offline)',
    models: [
      { id: 'local-almojtahed-8b', name: 'Al-Mojtahed 8B (المحلي المكمم - بدون إنترنت)' }
    ]
  });

  let selectedName = '';
  let customListHtml = '';

  groups.forEach(g => {
    customListHtml += `<div class="model-group-title">${g.title}</div>`;
    g.models.forEach(m => {
      const isSelected = m.id === selectedModelId;
      const modelDisplayName = m.name || m.id;
      if (isSelected) {
        selectedName = modelDisplayName;
      }
      const tag = typeof getModelTag === 'function' ? getModelTag(m.id) : '';

      customListHtml += `
        <div class="custom-model-item ${isSelected ? 'active' : ''}" 
             data-model-id="${m.id}" 
             data-model-name="${modelDisplayName.replace(/"/g, '&quot;')}"
             data-model-tag="${tag}"
             onclick="selectCustomAgentModel('${m.id}', '${modelDisplayName.replace(/'/g, "\\'")}')">
          <span class="custom-model-item-name" title="${m.id}">${modelDisplayName}</span>
          ${tag ? `<span class="custom-model-item-tag">${tag}</span>` : ''}
        </div>
      `;
    });
  });

  customListEl.innerHTML = customListHtml;

  if (hiddenInput) {
    hiddenInput.value = selectedModelId;
  }
  if (triggerTextEl) {
    triggerTextEl.textContent = selectedName || selectedModelId || 'اختر نموذجاً...';
    triggerTextEl.title = selectedModelId;
  }
}

// فتح وإغلاق قائمة نماذج الوكيل
function toggleAgentModelDropdown(event) {
  if (event) event.stopPropagation();
  const wrapper = document.getElementById('agentCustomModelWrapper');
  if (!wrapper) return;

  const isOpen = wrapper.classList.toggle('open');
  if (isOpen) {
    const input = document.getElementById('agentModelSearchInput');
    if (input) {
      setTimeout(() => {
        input.focus();
        input.select();
      }, 50);
    }
  }
}

function closeAgentModelDropdown() {
  const wrapper = document.getElementById('agentCustomModelWrapper');
  if (wrapper) wrapper.classList.remove('open');
  if (typeof hideModelHoverCard === 'function') hideModelHoverCard();
}

function clearAgentModelSearch() {
  const input = document.getElementById('agentModelSearchInput');
  if (input) {
    input.value = '';
    filterAgentCustomModels('');
    input.focus();
  }
}

function filterAgentCustomModels(query) {
  const container = document.getElementById('agentCustomModelOptionsList');
  if (!container) return;

  const q = (query || '').trim().toLowerCase();
  const items = container.querySelectorAll('.custom-model-item');
  const groups = container.querySelectorAll('.model-group-title');

  let visibleCount = 0;
  items.forEach(item => {
    const id = (item.getAttribute('data-model-id') || '').toLowerCase();
    const name = (item.getAttribute('data-model-name') || '').toLowerCase();
    const tag = (item.getAttribute('data-model-tag') || '').toLowerCase();
    const match = !q || id.includes(q) || name.includes(q) || tag.includes(q);
    item.style.display = match ? 'flex' : 'none';
    if (match) visibleCount++;
  });

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
}

function selectCustomAgentModel(modelId, modelName) {
  const hiddenInput = document.getElementById('agentSelectedModelId');
  if (hiddenInput) hiddenInput.value = modelId;

  const triggerText = document.getElementById('agentCustomModelTriggerText');
  if (triggerText) {
    triggerText.textContent = modelName;
    triggerText.title = modelId;
  }

  const container = document.getElementById('agentCustomModelOptionsList');
  if (container) {
    container.querySelectorAll('.custom-model-item').forEach(el => {
      if (el.getAttribute('data-model-id') === modelId) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    });
  }

  closeAgentModelDropdown();
}

// إغلاق قائمة نماذج الوكيل عند النقر خارجها
document.addEventListener('click', function(e) {
  const wrapper = document.getElementById('agentCustomModelWrapper');
  if (wrapper && wrapper.classList.contains('open')) {
    if (!wrapper.contains(e.target)) {
      closeAgentModelDropdown();
    }
  }
});

// =============================================================================
// فتح نافذة إضافة / تعديل وكيل
// =============================================================================

function openAddAgentModal() {
  document.getElementById('editAgentId').value = '';
  document.getElementById('agentModalTitle').textContent = 'إضافة وكيل مساعد جديد';
  document.getElementById('agentNameInput').value = '';
  document.getElementById('agentDescInput').value = '';
  document.getElementById('agentPromptInput').value = '';
  document.getElementById('agentTempInput').value = '0.2';
  document.getElementById('agentTopKInput').value = '40';
  document.getElementById('agentRepInput').value = '1.1';
  document.getElementById('agentTokensInput').value = '16384';
  document.getElementById('agentPoolInput').value = '250';
  document.getElementById('agentTopRerankInput').value = '40';

  // تعيين النموذج الافتراضي وقائمة النماذج والتفكير
  document.getElementById('agentSelectedModelId').value = 'anthropic/claude-3.7-sonnet';
  document.getElementById('agentThinkingSelect').value = 'medium';
  populateAgentModelDropdown('anthropic/claude-3.7-sonnet');

  // تعيين نطاق الكتب لجميع كتب الشاملة
  window._currentAgentBooks = [];
  const label = document.getElementById('agentScopeSelectorLabel');
  const badge = document.getElementById('agentScopeSelectedBadge');
  const clearBtn = document.getElementById('btnClearAgentScope');
  if (label) label.textContent = 'جميع كتب الشاملة (8,589 كتاباً)';
  if (badge) badge.style.display = 'none';
  if (clearBtn) clearBtn.style.display = 'none';

  document.getElementById('agentModalOverlay').classList.add('open');
}

function handleAgentRerankCheckChange() {
  // دالة متوافقة لا تقوم بشيء بعد إزالة Reranker
}

function editAgent(id) {
  const currentGroup = agentGroups.find(g => g.id === currentActiveGroupId) || agentGroups[0];
  if (!currentGroup || !currentGroup.agents) return;

  const agent = currentGroup.agents.find(a => a.id === id);
  if (!agent) return;

  document.getElementById('editAgentId').value = agent.id;
  document.getElementById('agentModalTitle').textContent = `تعديل ${agent.name}`;
  document.getElementById('agentNameInput').value = agent.name;
  document.getElementById('agentDescInput').value = agent.desc;
  document.getElementById('agentPromptInput').value = agent.systemPrompt || agent.system_prompt || '';
  document.getElementById('agentTempInput').value = agent.temp ?? 0.2;
  document.getElementById('agentTopKInput').value = agent.topK ?? agent.top_k ?? 40;
  document.getElementById('agentRepInput').value = agent.repPenalty ?? 1.1;
  document.getElementById('agentTokensInput').value = agent.maxTokens || agent.max_tokens || 65536;
  document.getElementById('agentPoolInput').value = agent.poolSize || agent.pool_size || 250;
  document.getElementById('agentTopRerankInput').value = agent.topK || agent.top_k || agent.topRerank || agent.top_rerank || 40;

  // تعيين النموذج ومستوى التفكير المخزنين
  const modelToSet = agent.model || 'anthropic/claude-3.7-sonnet';
  document.getElementById('agentSelectedModelId').value = modelToSet;
  document.getElementById('agentThinkingSelect').value = agent.thinking || 'medium';
  populateAgentModelDropdown(modelToSet);

  // تعيين نطاق الكتب المخزن مع فحص البدائل
  const currentBooks = (agent.booksScope && Array.isArray(agent.booksScope)) ? agent.booksScope : (agent.books && Array.isArray(agent.books)) ? agent.books : [];
  window._currentAgentBooks = [...currentBooks];
  const label = document.getElementById('agentScopeSelectorLabel');
  const badge = document.getElementById('agentScopeSelectedBadge');
  const clearBtn = document.getElementById('btnClearAgentScope');

  if (window._currentAgentBooks.length === 0) {
    if (label) label.textContent = 'جميع كتب الشاملة (8,589 كتاباً)';
    if (badge) badge.style.display = 'none';
    if (clearBtn) clearBtn.style.display = 'none';
  } else if (window._currentAgentBooks.length === 1) {
    if (label) label.textContent = window._currentAgentBooks[0];
    if (badge) {
      badge.textContent = '1';
      badge.style.display = 'inline-block';
    }
    if (clearBtn) clearBtn.style.display = 'inline-block';
  } else {
    if (label) label.textContent = `محدد: ${window._currentAgentBooks.length} كتب`;
    if (badge) {
      badge.textContent = window._currentAgentBooks.length;
      badge.style.display = 'inline-block';
    }
    if (clearBtn) clearBtn.style.display = 'inline-block';
  }

  document.getElementById('agentModalOverlay').classList.add('open');
}

function closeAgentModal() {
  document.getElementById('agentModalOverlay').classList.remove('open');
}

function handleAgentModalOverlayClick(e) {
  if (e.target.id === 'agentModalOverlay') {
    closeAgentModal();
  }
}

// حفظ الوكيل داخل المجموعة المحددة
function saveAgentFromModal() {
  const currentGroup = agentGroups.find(g => g.id === currentActiveGroupId) || agentGroups[0];
  if (!currentGroup) return;
  if (!currentGroup.agents) currentGroup.agents = [];

  const id = document.getElementById('editAgentId').value;
  const name = document.getElementById('agentNameInput').value.trim();
  const desc = document.getElementById('agentDescInput').value.trim();
  const prompt = document.getElementById('agentPromptInput').value.trim();
  const model = document.getElementById('agentSelectedModelId')?.value || 'anthropic/claude-3.7-sonnet';
  const thinking = document.getElementById('agentThinkingSelect')?.value || 'medium';
  const booksScope = [...(window._currentAgentBooks || [])];

  if (!name) {
    showToast('يرجى تحديد اسم الوكيل');
    return;
  }

  const agentData = {
    id: id || ('agent_' + Date.now()),
    name: name,
    desc: desc || 'وكيل تراثي مساعد',
    model: model,
    thinking: thinking,
    books: booksScope,
    booksScope: booksScope,
    scope_summary: booksScope.join('، ') || 'كامل مصادر الشاملة',
    enabled: true,
    active: true,
    systemPrompt: prompt,
    system_prompt: prompt,
    temp: parseFloat(document.getElementById('agentTempInput').value || 0.2),
    topK: parseInt(document.getElementById('agentTopKInput').value || 40),
    top_k: parseInt(document.getElementById('agentTopKInput').value || 40),
    repPenalty: parseFloat(document.getElementById('agentRepInput').value || 1.1),
    maxTokens: parseInt(document.getElementById('agentTokensInput').value || 65536),
    max_tokens: parseInt(document.getElementById('agentTokensInput').value || 65536),
    poolSize: parseInt(document.getElementById('agentPoolInput').value || 250),
    pool_size: parseInt(document.getElementById('agentPoolInput').value || 250),
    topK: parseInt(document.getElementById('agentTopRerankInput').value || document.getElementById('agentTopKInput').value || 40),
    top_k: parseInt(document.getElementById('agentTopRerankInput').value || document.getElementById('agentTopKInput').value || 40)
  };

  if (id) {
    const idx = currentGroup.agents.findIndex(a => a.id === id);
    if (idx !== -1) {
      currentGroup.agents[idx] = { ...currentGroup.agents[idx], ...agentData };
    }
  } else {
    currentGroup.agents.push(agentData);
  }

  saveAgentGroups();
  renderAgentsGrid();
  closeAgentModal();
  showToast('تم حفظ إعدادات الوكيل المساعد بنجاح');
}

// =============================================================================
// تصدير للدوال العامة
// =============================================================================
window.loadAgentGroups = loadAgentGroups;
window.saveAgentGroups = saveAgentGroups;
window.renderGroupsTable = renderGroupsTable;
window.openCreateGroupModal = openCreateGroupModal;
window.closeGroupModal = closeGroupModal;
window.handleGroupModalOverlayClick = handleGroupModalOverlayClick;
window.saveGroupFromModal = saveGroupFromModal;
window.duplicateGroup = duplicateGroup;
window.deleteGroup = deleteGroup;
window.openGroupAgents = openGroupAgents;
window.showAgentGroupsView = showAgentGroupsView;
window.renderAgentsGrid = renderAgentsGrid;
window.toggleAgentActive = toggleAgentActive;
window.deleteAgent = deleteAgent;
window.openAddAgentModal = openAddAgentModal;
window.editAgent = editAgent;
window.closeAgentModal = closeAgentModal;
window.handleAgentModalOverlayClick = handleAgentModalOverlayClick;
window.handleAgentRerankCheckChange = handleAgentRerankCheckChange;
// فتح نافذة تحديد نطاق كتب الوكيل
function openAgentSearchScopeModal() {
  if (typeof openSearchScopeModal === 'function') {
    openSearchScopeModal('agent');
  } else if (window.openSearchScopeModal) {
    window.openSearchScopeModal('agent');
  } else {
    const modal = document.getElementById('searchScopeModal');
    if (modal) {
      modal.style.zIndex = '3000';
      modal.style.display = 'flex';
      modal.classList.add('open');
    }
  }
}

// إلغاء نطاق كتب الوكيل والعودة لجميع الكتب
function resetAgentSearchScope(event) {
  if (event) event.stopPropagation();
  window._currentAgentBooks = [];
  const label = document.getElementById('agentScopeSelectorLabel');
  const badge = document.getElementById('agentScopeSelectedBadge');
  const clearBtn = document.getElementById('btnClearAgentScope');
  if (label) label.textContent = 'جميع كتب الشاملة (8,589 كتاباً)';
  if (badge) badge.style.display = 'none';
  if (clearBtn) clearBtn.style.display = 'none';
  showToast('تمت إعادة نطاق الوكيل إلى جميع كتب الشاملة');
}

window.openAgentSearchScopeModal = openAgentSearchScopeModal;
window.resetAgentSearchScope = resetAgentSearchScope;
window.populateAgentModelDropdown = populateAgentModelDropdown;
window.toggleAgentModelDropdown = toggleAgentModelDropdown;
window.closeAgentModelDropdown = closeAgentModelDropdown;
window.clearAgentModelSearch = clearAgentModelSearch;
window.filterAgentCustomModels = filterAgentCustomModels;
window.selectCustomAgentModel = selectCustomAgentModel;
window.exportSingleGroup = exportSingleGroup;
window.exportCurrentActiveGroup = exportCurrentActiveGroup;
window.exportSingleAgent = exportSingleAgent;
window.triggerImportAgentFile = triggerImportAgentFile;
window.handleAgentFileImport = handleAgentFileImport;
