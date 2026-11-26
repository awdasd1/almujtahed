const ARCHIVE_SCOPE_NAMES = {
  chats: 'المحادثات',
  projects: 'المشاريع',
  agents: 'الوكلاء',
  tools: 'الإضافات',
  manuscripts: 'المخطوطات',
  reading: 'القراءة والتحليل'
};

function archiveScopeBoxes() {
  return [...document.querySelectorAll('input[name="archiveScope"]')];
}

function selectedArchiveScopes() {
  return archiveScopeBoxes()
    .filter(el => el.checked && el.value !== 'all')
    .map(el => el.value);
}

function updateArchiveSelection(changed) {
  const boxes = archiveScopeBoxes();
  const allBox = boxes.find(el => el.value === 'all');
  const parts = boxes.filter(el => el.value !== 'all');
  if (changed === 'all' && allBox) {
    parts.forEach(el => { el.checked = allBox.checked; });
  } else if (allBox) {
    allBox.checked = parts.length > 0 && parts.every(el => el.checked);
  }
  updateArchiveButtonLabel();
}

function updateArchiveButtonLabel() {
  const scopes = selectedArchiveScopes();
  const button = document.getElementById('btnCreateArchive');
  const hint = document.getElementById('archiveScopeHint');
  const names = scopes.map(scope => ARCHIVE_SCOPE_NAMES[scope]).filter(Boolean);
  if (button) {
    button.disabled = names.length === 0;
    button.textContent = names.length === partsCount() ? 'أرشفة الجميع' : (names.length ? `أرشفة ${names.join(' و')}` : 'أرشفة المحدد');
  }
  if (hint) {
    hint.textContent = names.length
      ? `يُنسخ ما تحدده (${names.join('، ')}) إلى أرشيف بتاريخ اليوم، ثم يُمسح من التطبيق.`
      : 'حدد عنصراً واحداً أو أكثر. يمكن الجمع بين المحادثات والإضافات وغيرهما.';
  }
}

function partsCount() {
  return Object.keys(ARCHIVE_SCOPE_NAMES).length;
}

function loadArchiveCenter() {
  updateArchiveButtonLabel();
  loadArchiveList();
  if (typeof refreshLucideIcons === 'function') refreshLucideIcons();
}

function archiveActionButtons(archiveId) {
  const safeId = String(archiveId).replace(/[^a-zA-Z0-9_]/g, '');
  return `
    <div style="display: flex; gap: 8px; flex-shrink: 0;">
      <button type="button" class="btn-secondary-action" onclick="restoreArchiveCopy('${safeId}')" title="استرجاع" style="display: inline-flex; align-items: center; gap: 6px; font-weight: 700;">
        <i data-lucide="archive-restore" class="icon" aria-hidden="true"></i>
        <span>استرجاع</span>
      </button>
      <button type="button" onclick="confirmDeleteArchive('${safeId}')" title="حذف" style="display: inline-flex; align-items: center; gap: 6px; font-weight: 700; background: #991b1b; color: #fff; border: none; border-radius: 6px; padding: 6px 12px; cursor: pointer;">
        <i data-lucide="trash-2" class="icon" aria-hidden="true"></i>
        <span>حذف</span>
      </button>
    </div>
  `;
}

async function loadArchiveList() {
  const list = document.getElementById('archiveList');
  if (!list) return;
  try {
    const res = await fetch('/api/archives');
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'تعذر جلب الأرشيف');
    const archives = data.archives || [];
    if (!archives.length) {
      list.innerHTML = '<div style="color: var(--text-muted); font-size: 13.5px;">لا توجد نسخ مؤرشفة بعد.</div>';
      return;
    }
    list.innerHTML = archives.map(item => {
      const note = String(item.note || '').trim();
      return `
      <div class="archive-row">
        <div>
          <div style="font-weight: 800; font-size: 14px;">${escapeHtml(note || item.scope_label || '')}</div>
          ${note ? `<div style="font-size: 12.5px; color: var(--text-secondary); margin-top: 3px;">${escapeHtml(item.scope_label || '')}</div>` : ''}
          <div style="font-size: 12.5px; color: var(--text-muted); margin-top: 3px;">تاريخ الأرشفة: <span dir="ltr">${escapeHtml(item.created_at || '')}</span></div>
          <div style="font-size: 12.5px; color: var(--text-secondary); margin-top: 2px;">${escapeHtml(item.summary || '')}</div>
        </div>
        ${archiveActionButtons(item.id)}
      </div>
    `;
    }).join('');
    if (typeof refreshLucideIcons === 'function') refreshLucideIcons();
  } catch (err) {
    list.innerHTML = `<div style="color:#991b1b;">${escapeHtml(err.message)}</div>`;
  }
}

async function createSelectedArchive() {
  const scopes = selectedArchiveScopes();
  if (!scopes.length) {
    showToast('حدد ما تريد أرشفته');
    return;
  }
  const note = (document.getElementById('archiveNote')?.value || '').trim();
  if (!note) {
    showToast('اكتب وصفاً يذكّرك بهذه الأرشفة');
    document.getElementById('archiveNote')?.focus();
    return;
  }
  const names = scopes.map(scope => ARCHIVE_SCOPE_NAMES[scope]).join(' و');
  const confirmed = await showConfirmDialog({
    title: scopes.length === partsCount() ? 'أرشفة الجميع' : 'أرشفة المحدد',
    message: `«${note}»\nستُنقل ${names} إلى الأرشيف وتُمسح من التطبيق. يمكنك إرجاعها لاحقاً من قسم الاسترجاع.`,
    confirmText: 'نعم، أرشف وامسح من التطبيق',
    cancelText: 'إلغاء',
    danger: true,
    icon: 'archive'
  });
  if (!confirmed) return;
  const button = document.getElementById('btnCreateArchive');
  if (button) button.disabled = true;
  try {
    const payload = { scopes, note };
    if (scopes.includes('agents') && Array.isArray(window.agentGroups)) {
      payload.agent_groups = window.agentGroups;
    }
    const res = await fetch('/api/archives', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'تعذرت الأرشفة');
    if (scopes.includes('chats') && typeof initChatHistory === 'function') await initChatHistory();
    if (scopes.includes('projects') && typeof loadProjectsData === 'function') await loadProjectsData();
    if (scopes.includes('agents')) {
      if (typeof clearAgentGroupsFromApp === 'function') clearAgentGroupsFromApp();
      if (typeof loadAgentGroups === 'function') await loadAgentGroups();
    }
    if (scopes.includes('tools') && typeof loadToolsList === 'function') await loadToolsList();
    if (scopes.includes('manuscripts') && typeof msReloadProjects === 'function') await msReloadProjects();
    if (scopes.includes('reading') && typeof initReadingTab === 'function') await initReadingTab();
    const noteBox = document.getElementById('archiveNote');
    if (noteBox) noteBox.value = '';
    await loadArchiveList();
    showToast(`تمت الأرشفة بتاريخ ${data.created_at || ''} ومُسحت من التطبيق`);
  } catch (err) {
    showToast(err.message);
  } finally {
    updateArchiveButtonLabel();
  }
}

async function _afterArchiveRestore(data) {
  if (data.restored_chats && typeof initChatHistory === 'function') await initChatHistory();
  if (data.restored_projects && typeof loadProjectsData === 'function') await loadProjectsData();
  if (data.restored_agents && typeof loadAgentGroups === 'function') await loadAgentGroups();
  else if (data.restored_projects && typeof renderGroupsTable === 'function') renderGroupsTable();
  if (data.restored_tools && typeof loadToolsList === 'function') await loadToolsList();
  if (typeof msReloadProjects === 'function') await msReloadProjects();
  if (typeof initReadingTab === 'function') await initReadingTab();
}

async function restoreArchiveCopy(archiveId) {
  const confirmed = await showConfirmDialog({
    title: 'استرجاع الأرشفة',
    message: 'سيعود محتوى هذه النسخة إلى التطبيق مكان البيانات الحالية من النوع نفسه.',
    confirmText: 'استرجاع',
    cancelText: 'إلغاء',
    icon: 'archive-restore'
  });
  if (!confirmed) return;
  try {
    const res = await fetch('/api/archives/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ archive_id: archiveId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'تعذر الاسترجاع');
    await _afterArchiveRestore(data);
    showToast('تمت استعادة النسخة المؤرشفة');
  } catch (err) {
    showToast(err.message);
  }
}

async function pickExternalArchiveFolder() {
  const input = document.getElementById('externalArchivePath');
  const msg = document.getElementById('externalArchiveMsg');
  try {
    let picked = null;
    if (typeof _pickFolderViaHost === 'function') {
      picked = await _pickFolderViaHost('اختر مجلد النسخة المؤرشفة (الذي يحتوي ملف وصفها)');
    }
    if (picked === null) {
      const res = await fetch('/api/workspace/pick', { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'تعذر اختيار المجلد');
      picked = data.path || '';
    }
    if (picked) {
      if (input) input.value = picked;
      if (msg) { msg.style.color = '#166534'; msg.textContent = `المجلد المحدد: ${picked} — اضغط «معاينة واسترجاع».`; }
    }
  } catch (err) {
    if (msg) { msg.style.color = '#991b1b'; msg.textContent = err.message; }
  }
}

async function restoreExternalArchive() {
  const input = document.getElementById('externalArchivePath');
  const msg = document.getElementById('externalArchiveMsg');
  const path = (input?.value || '').trim();
  if (!path) {
    if (msg) { msg.style.color = '#991b1b'; msg.textContent = 'حدّد مجلد النسخة المؤرشفة أولًا أو اكتب مساره.'; }
    input?.focus();
    return;
  }
  const say = (text, ok) => {
    if (msg) { msg.style.color = ok ? '#166534' : '#991b1b'; msg.textContent = text; }
  };
  try {
    say('جارٍ فحص المجلد...', true);
    const pv = await fetch('/api/archives/restore-path/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    const info = await pv.json().catch(() => ({}));
    if (!pv.ok) throw new Error(info.detail || 'تعذّر فحص المجلد');
    say('', true);
    const lines = [
      info.note ? `الوصف: ${info.note}` : '',
      info.scope_label ? `المحتوى: ${info.scope_label}` : '',
      info.summary ? `التفاصيل: ${info.summary}` : '',
      info.created_at ? `تاريخ الأرشفة: ${info.created_at}` : ''
    ].filter(Boolean).join('\n');
    const confirmed = await showConfirmDialog({
      title: 'استرجاع نسخة من مجلد خارجي',
      message: `${lines}\n\nسيعود هذا المحتوى إلى التطبيق مكان البيانات الحالية من النوع نفسه.`,
      confirmText: 'استرجاع النسخة',
      cancelText: 'إلغاء',
      icon: 'archive-restore'
    });
    if (!confirmed) return;
    say('جارٍ الاسترجاع...', true);
    const res = await fetch('/api/archives/restore-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر الاسترجاع');
    await _afterArchiveRestore(data);
    await loadArchiveList();
    say(`تمت استعادة النسخة من: ${path}`, true);
    showToast('تمت استعادة النسخة المؤرشفة من المجلد الخارجي');
  } catch (err) {
    say(err.message, false);
  }
}

async function confirmDeleteArchive(archiveId) {
  const confirmed = await showConfirmDialog({
    title: 'حذف الأرشيف',
    message: 'سيتم حذف هذا الارشيف نهائيا ولا يمكن استرجاعه',
    confirmText: 'حذف نهائي',
    cancelText: 'إلغاء',
    danger: true,
    icon: 'trash-2'
  });
  if (!confirmed) return;
  try {
    const res = await fetch('/api/archives/' + encodeURIComponent(archiveId), { method: 'DELETE' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر حذف الأرشيف');
    await loadArchiveList();
    showToast('حُذف الأرشيف نهائياً');
  } catch (err) {
    showToast(err.message);
  }
}

async function confirmDeleteAllArchives() {
  const confirmed = await showConfirmDialog({
    title: 'حذف كل الأرشيف',
    message: 'سيتم حذف كل الأرشيف نهائيا ولا يمكن استرجاعه',
    confirmText: 'حذف الجميع',
    cancelText: 'إلغاء',
    danger: true,
    icon: 'trash-2'
  });
  if (!confirmed) return;
  try {
    const res = await fetch('/api/archives', { method: 'DELETE' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر حذف الأرشيف');
    await loadArchiveList();
    showToast('حُذفت كل النسخ المؤرشفة');
  } catch (err) {
    showToast(err.message);
  }
}
