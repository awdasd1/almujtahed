let shareDraft = null;

const shareKindNames = {
  chat: 'المحادثة',
  project: 'المشروع',
  tool: 'الأداة',
  key: 'المفتاح'
};

function openSharePicker(kind, itemId, label, options) {
  shareDraft = {
    kind,
    itemId: String(itemId || ''),
    label: label || '',
    device: options && options.device || '',
    unsaved: !!(options && options.unsaved)
  };
  const modal = document.getElementById('shareModal');
  const title = document.getElementById('shareModalTitle');
  const note = document.getElementById('shareFormNote');
  const filter = document.getElementById('shareMemberFilter');
  const everyone = document.getElementById('shareEveryone');
  const keyOptions = document.getElementById('shareKeyOptions');
  const destination = document.getElementById('shareDestination');
  const newKey = document.getElementById('shareNewKey');
  if (title) title.textContent = `مشاركة ${shareKindNames[kind] || ''}`.trim();
  if (note) note.textContent = '';
  if (filter) filter.value = '';
  if (everyone) everyone.checked = false;
  if (keyOptions) keyOptions.hidden = kind !== 'key';
  if (destination) destination.hidden = kind === 'key';
  const membersMode = document.querySelector('input[name="shareDestination"][value="members"]');
  if (membersMode) membersMode.checked = true;
  const mine = document.querySelector('input[name="shareKeyMode"][value="mine"]');
  if (mine) mine.checked = true;
  if (newKey) newKey.value = '';
  toggleShareKeyMode();
  toggleShareDestination();
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('active', 'open');
  }
  loadShareMembers();
  if (window.lucide && typeof lucide.createIcons === 'function') lucide.createIcons();
}

function shareDestinationMode() {
  if (shareDraft && shareDraft.kind === 'key') return 'members';
  return document.querySelector('input[name="shareDestination"]:checked')?.value || 'members';
}

function toggleShareDestination() {
  const device = shareDestinationMode() === 'device';
  const members = document.getElementById('shareMemberFields');
  const button = document.getElementById('shareSubmitBtn');
  const hint = document.getElementById('shareModalHint');
  if (members) members.hidden = device;
  if (button) button.textContent = device ? 'حفظ في الجهاز' : 'مشاركة';
  if (!hint || !shareDraft) return;
  if (shareDraft.kind === 'key') {
    hint.textContent = 'المفتاح الخاص يبقى لديك. المفتاح الجديد لا يُحفظ في حسابك، ويُضاف عند قبول الطرف الآخر فقط.';
    return;
  }
  const name = shareDraft.label ? `«${shareDraft.label}»` : (shareKindNames[shareDraft.kind] || 'العنصر');
  hint.textContent = device
    ? `${name} يُحفظ ملفاً على جهازك، ولا يُرسل إلى أي عضو.`
    : `${name} يبقى لديك، وتُرسل نسخة إلى الأعضاء الذين تحددهم.`;
}

function toggleShareKeyMode() {
  const mode = document.querySelector('input[name="shareKeyMode"]:checked')?.value || 'mine';
  const wrap = document.getElementById('shareNewKeyWrap');
  const showing = shareDraft && shareDraft.kind === 'key' && mode === 'new';
  if (wrap) wrap.hidden = !showing;
}

function toggleShareNewKeyVisibility() {
  const input = document.getElementById('shareNewKey');
  if (!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
}

function closeSharePicker() {
  const modal = document.getElementById('shareModal');
  if (!modal) return;
  modal.style.display = 'none';
  modal.classList.remove('active', 'open');
  shareDraft = null;
}

async function loadShareMembers() {
  const picker = document.getElementById('shareMemberPicker');
  if (!picker) return;
  picker.innerHTML = '<div class="share-form-note">جارٍ تحميل الأعضاء...</div>';
  try {
    const res = await fetch('/api/share/members');
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر تحميل الأعضاء');
    const members = Array.isArray(data.members) ? data.members : [];
    if (!members.length) {
      picker.innerHTML = '<div class="share-form-note">لا يوجد أعضاء آخرون للمشاركة معهم.</div>';
      return;
    }
    picker.innerHTML = members.map(member => `
      <label class="notice-member-option" data-share-name="${escapeHtml((member.display_name || '') + ' ' + (member.username || ''))}">
        <input class="share-member-check" type="checkbox" value="${escapeHtml(member.username)}">
        <span>${escapeHtml(member.display_name || 'عضو')}</span>
        <small>${escapeHtml(member.label || 'عضو')}</small>
      </label>
    `).join('');
  } catch (err) {
    picker.innerHTML = `<div class="share-form-note">${escapeHtml(err.message || 'تعذر تحميل الأعضاء')}</div>`;
  }
}

function filterShareMembers() {
  const query = (document.getElementById('shareMemberFilter')?.value || '').trim().toLowerCase();
  document.querySelectorAll('#shareMemberPicker .notice-member-option').forEach(option => {
    const name = (option.dataset.shareName || '').toLowerCase();
    option.style.display = !query || name.includes(query) ? '' : 'none';
  });
}

function toggleShareEveryone() {
  const everyone = document.getElementById('shareEveryone')?.checked;
  document.querySelectorAll('.share-member-check').forEach(box => {
    box.disabled = !!everyone;
    if (everyone) box.checked = false;
  });
}

function saveShareToDevice() {
  if (!shareDraft) return false;
  const kind = shareDraft.kind;
  const itemId = shareDraft.itemId;
  if (kind === 'chat' && typeof exportChatSessionFile === 'function') {
    return exportChatSessionFile(itemId);
  }
  if (kind === 'project' && typeof exportSingleProject === 'function') {
    exportSingleProject(itemId);
    return true;
  }
  if (kind === 'tool' && shareDraft.device === 'editor' && typeof exportCurrentModalTool === 'function') {
    return exportCurrentModalTool() !== false;
  }
  if (kind === 'tool' && typeof exportSingleTool === 'function') {
    exportSingleTool(itemId);
    return true;
  }
  return false;
}

async function submitShare(event) {
  if (event) event.preventDefault();
  const note = document.getElementById('shareFormNote');
  if (!shareDraft) return;
  if (shareDestinationMode() === 'device') {
    const saved = saveShareToDevice();
    if (!saved && note) note.textContent = 'تعذر حفظ الملف في الجهاز';
    if (saved) closeSharePicker();
    return;
  }
  if (shareDraft.unsaved) {
    if (note) note.textContent = 'احفظ الأداة أولاً لمشاركتها مع الأعضاء، أو اختر الحفظ في الجهاز';
    return;
  }
  const everyone = !!document.getElementById('shareEveryone')?.checked;
  const usernames = [...document.querySelectorAll('.share-member-check:checked')].map(box => box.value);
  const payload = {
    kind: shareDraft.kind,
    item_id: shareDraft.itemId,
    everyone,
    usernames
  };
  if (shareDraft.kind === 'key') {
    payload.key_mode = document.querySelector('input[name="shareKeyMode"]:checked')?.value || 'mine';
    if (payload.key_mode === 'new') {
      payload.key = (document.getElementById('shareNewKey')?.value || '').trim();
      if (payload.key.length < 8) {
        if (note) note.textContent = 'اكتب المفتاح الجديد';
        return;
      }
    } else if (shareDraft.itemId === 'tavily') {
      payload.key = (typeof readTavilyKey === 'function' ? readTavilyKey() : '') || (readProviderKeys().tavily || '');
    } else {
      payload.key = readProviderKeys()[shareDraft.itemId] || '';
    }
  }
  const button = document.getElementById('shareSubmitBtn');
  if (button) button.disabled = true;
  try {
    const res = await fetch('/api/shares', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذرت المشاركة');
    const count = Array.isArray(data.sent) ? data.sent.length : 0;
    if (shareDraft.kind === 'key' && payload.key_mode === 'new') {
      showToast(count > 1 ? `أُرسل المفتاح الجديد إلى ${count}` : 'أُرسل المفتاح الجديد، ويُضاف عند القبول');
    } else {
      showToast(count > 1 ? `تمت المشاركة مع ${count}، وبقيت النسخة لديك` : 'تمت المشاركة، وبقيت النسخة لديك');
    }
    closeSharePicker();
  } catch (err) {
    if (note) note.textContent = err.message || 'تعذرت المشاركة';
  } finally {
    if (button) button.disabled = false;
  }
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-share-kind]');
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();
  openSharePicker(button.dataset.shareKind, button.dataset.shareId, button.dataset.shareLabel || '');
});

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('shareForm');
  if (form) form.addEventListener('submit', submitShare);
});

window.openSharePicker = openSharePicker;
window.closeSharePicker = closeSharePicker;
window.filterShareMembers = filterShareMembers;
window.toggleShareEveryone = toggleShareEveryone;
window.toggleShareKeyMode = toggleShareKeyMode;
window.toggleShareDestination = toggleShareDestination;

async function revealSharedKey(uiName) {
  switchMainTab('providers');
  try {
    const res = await fetch('/api/config/providers');
    if (res.ok) {
      const data = await res.json();
      if (data.keys && typeof data.keys === 'object') {
        writeProviderKeys(data.keys);
        if (typeof writeTavilyKey === 'function') writeTavilyKey(data.keys.tavily || '');
      }
    }
  } catch (err) {}
  if (uiName === 'tavily') {
    if (typeof switchProviderSubtab === 'function') switchProviderSubtab('web');
    if (typeof initTavilyConfig === 'function') initTavilyConfig();
    return;
  }
  if (typeof switchProviderSubtab === 'function') switchProviderSubtab('models');
  const select = document.getElementById('providerSelect');
  if (select && uiName) select.value = uiName;
  if (typeof handleProviderChange === 'function' && uiName) handleProviderChange(uiName);
}

const shareKindWords = { chat: 'محادثة', project: 'مشروع', tool: 'إضافة' };
let shareGiftInvite = null;
let shareGiftBusy = false;

function showShareGift(invite) {
  if (!invite || shareGiftInvite) return;
  shareGiftInvite = invite;
  const modal = document.getElementById('shareGiftModal');
  const name = document.getElementById('shareGiftName');
  const kind = document.getElementById('shareGiftKind');
  const title = document.getElementById('shareGiftTitle');
  if (name) name.textContent = invite.from_name || 'عضو';
  if (kind) kind.textContent = invite.kind_label || shareKindWords[invite.kind] || 'عنصر';
  if (title) title.textContent = invite.title || '';
  document.querySelectorAll('#shareGiftModal button').forEach(button => { button.disabled = false; });
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('active', 'open');
  }
  if (window.lucide && typeof lucide.createIcons === 'function') lucide.createIcons();
}

function hideShareGift() {
  const modal = document.getElementById('shareGiftModal');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active', 'open');
  }
  shareGiftInvite = null;
  shareGiftBusy = false;
}

async function pollIncomingShares() {
  if (shareGiftInvite) return;
  try {
    const res = await fetch('/api/shares/incoming');
    if (!res.ok) return;
    const data = await res.json();
    const first = (data.invites || [])[0];
    if (first) showShareGift(first);
  } catch (err) {}
}

async function respondShareGift(action) {
  if (!shareGiftInvite || shareGiftBusy) return;
  shareGiftBusy = true;
  const invite = shareGiftInvite;
  const buttons = document.querySelectorAll('#shareGiftModal button');
  buttons.forEach(button => { button.disabled = true; });
  try {
    const res = await fetch(`/api/shares/incoming/${encodeURIComponent(invite.id)}/${action}`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'تعذر تنفيذ الاختيار');
    hideShareGift();
    if (action === 'accept') {
      if (data.kind === 'chat' && typeof revealSharedChat === 'function') {
        await revealSharedChat(data.item_id);
      } else if (data.kind === 'project') {
        window._openSharedProjectId = data.item_id;
        switchMainTab('projects');
      } else if (data.kind === 'tool') {
        window._openSharedToolId = data.item_id;
        switchMainTab('tools');
      } else if (data.kind === 'key') {
        await revealSharedKey(data.item_id);
      }
      showToast('قُبلت المشاركة، وأُرسل الشكر');
    } else {
      showToast('أُرسل الاعتذار إلى المشارك');
    }
    if (typeof refreshNoticeBell === 'function') refreshNoticeBell();
    setTimeout(pollIncomingShares, 400);
  } catch (err) {
    shareGiftBusy = false;
    buttons.forEach(button => { button.disabled = false; });
    showToast(err.message || 'تعذر تنفيذ الاختيار');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  pollIncomingShares();
  setInterval(pollIncomingShares, 4000);
});

window.showShareGift = showShareGift;
window.respondShareGift = respondShareGift;
