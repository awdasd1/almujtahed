function memberTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('ar');
}

function memberEscape(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

async function copyMemberLink(url, button) {
  try {
    await navigator.clipboard.writeText(url);
  } catch (err) {
    const field = document.createElement('textarea');
    field.value = url;
    document.body.appendChild(field);
    field.select();
    document.execCommand('copy');
    field.remove();
  }
  if (button) {
    const previous = button.textContent;
    button.textContent = 'تم النسخ';
    setTimeout(() => { button.textContent = previous; }, 1200);
  }
}

async function loadMembersPanel() {
  const box = document.getElementById('membersList');
  const note = document.getElementById('membersNote');
  if (!box) return;
  box.textContent = 'جارٍ تحميل الأعضاء…';
  try {
    const res = await fetch('/api/members');
    const data = await res.json();
    if (!res.ok) {
      box.textContent = data.detail || 'تعذر تحميل الأعضاء';
      return;
    }
    if (note) note.textContent = `حساب المشرف: ${data.admin_username || ''}. الأعضاء يرون كل التبويبات إلا هذا التبويب.`;
    const invites = (data.invites || []).map((invite) => `
      <div class="member-row">
        <div>
          <strong>${memberEscape(invite.label || 'دعوة بلا ملاحظة')}</strong>
          <div class="member-meta">${invite.used ? `استُخدمت: ${memberEscape(invite.used_by)}` : 'بانتظار التفعيل'} · ${memberEscape(memberTime(invite.created_at))}</div>
          <code class="member-link">${memberEscape(invite.url)}</code>
        </div>
        <div class="member-actions">
          <button type="button" class="btn-chart-type" data-copy-link="${memberEscape(invite.url)}">نسخ الرابط</button>
          ${invite.used ? '' : `<button type="button" class="btn-chart-type" data-cancel-invite="${memberEscape(invite.id)}">إلغاء</button>`}
        </div>
      </div>`).join('');
    const accounts = (data.accounts || []).map((account) => `
      <div class="member-row">
        <div>
          <strong>${memberEscape(account.username)}</strong>
          <div class="member-meta">${account.disabled ? 'معطّل' : 'نشط'} · المعرف ${memberEscape(account.id || '')} · ${memberEscape(memberTime(account.created_at))}</div>
        </div>
        <button type="button" class="btn-chart-type" data-member-user="${memberEscape(account.username)}" data-member-disabled="${account.disabled ? '0' : '1'}">${account.disabled ? 'تفعيل' : 'تعطيل'}</button>
      </div>`).join('');
    box.innerHTML = `
      <h3>روابط الدعوة</h3>
      ${invites || '<p class="member-meta">لا توجد دعوات بعد.</p>'}
      <h3>الحسابات</h3>
      ${accounts || '<p class="member-meta">لم يفعّل أحد حسابه بعد.</p>'}`;
    renderNoticeMemberPicker(data.accounts || []);
    loadAdminNotices();
  } catch (err) {
    box.textContent = 'تعذر تحميل الأعضاء';
  }
}

async function createMemberInvite(event) {
  event.preventDefault();
  const label = document.getElementById('memberInviteLabel');
  const note = document.getElementById('membersNote');
  const res = await fetch('/api/members/invites', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label: label ? label.value.trim() : '' })
  });
  const data = await res.json();
  if (!res.ok) {
    if (note) note.textContent = data.detail || 'تعذر إنشاء الدعوة';
    return;
  }
  if (label) label.value = '';
  if (note && data.invite) note.textContent = `الرابط جاهز: ${data.invite.url}`;
  loadMembersPanel();
}

async function onMembersClick(event) {
  const copy = event.target.closest('[data-copy-link]');
  if (copy) {
    copyMemberLink(copy.getAttribute('data-copy-link'), copy);
    return;
  }
  const cancel = event.target.closest('[data-cancel-invite]');
  if (cancel) {
    await fetch('/api/members/invites/' + encodeURIComponent(cancel.getAttribute('data-cancel-invite')), { method: 'DELETE' });
    loadMembersPanel();
    return;
  }
  const toggle = event.target.closest('[data-member-user]');
  if (toggle) {
    await fetch('/api/members/' + encodeURIComponent(toggle.getAttribute('data-member-user')) + '/disabled', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ disabled: toggle.getAttribute('data-member-disabled') === '1' })
    });
    loadMembersPanel();
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const box = document.getElementById('membersList');
  if (box) box.addEventListener('click', onMembersClick);
  const form = document.getElementById('memberInviteForm');
  if (form) form.addEventListener('submit', createMemberInvite);
  const noticeForm = document.getElementById('memberNoticeForm');
  if (noticeForm) noticeForm.addEventListener('submit', sendMemberNotice);
  const adminList = document.getElementById('adminNoticesList');
  if (adminList) adminList.addEventListener('click', onAdminNoticeClick);
  const noticesBody = document.getElementById('noticesModalBody');
  if (noticesBody) noticesBody.addEventListener('click', onNoticeReadClick);
  refreshNoticeBell();
  setInterval(refreshNoticeBell, 20000);
  try {
    const res = await fetch('/api/auth/status');
    const data = await res.json();
    const admin = data.role === 'admin';
    document.body.classList.toggle('is-admin', admin);
    if (!admin && document.getElementById('paneMembers')?.classList.contains('active') && typeof switchMainTab === 'function') {
      switchMainTab('search');
    }
    const saved = (location.hash || '').replace('#', '') || localStorage.getItem('almojtahed_active_tab');
    if (admin && saved === 'members' && typeof switchMainTab === 'function') switchMainTab('members');
  } catch (err) {}
});

function renderNoticeMemberPicker(accounts) {
  const picker = document.getElementById('noticeMemberPicker');
  if (!picker) return;
  const active = (accounts || []).filter((account) => !account.disabled);
  window._noticeMembers = active;
  if (!active.length) {
    picker.innerHTML = '<p class="member-meta">لا يوجد أعضاء نشطون بعد.</p>';
    return;
  }
  picker.innerHTML = active.map((account) => `
    <label class="notice-member-option" data-notice-name="${memberEscape(account.username)}">
      <input class="notice-member-check" type="checkbox" value="${memberEscape(account.username)}">
      <span>${memberEscape(account.username)}</span>
    </label>`).join('');
  filterNoticeMembers(document.getElementById('noticeMemberFilter')?.value || '');
}

function filterNoticeMembers(query) {
  const needle = String(query || '').trim().toLowerCase();
  document.querySelectorAll('#noticeMemberPicker .notice-member-option').forEach((row) => {
    const name = (row.getAttribute('data-notice-name') || '').toLowerCase();
    row.style.display = !needle || name.includes(needle) ? 'flex' : 'none';
  });
}

function toggleNoticeEveryone(checked) {
  document.querySelectorAll('.notice-member-check').forEach((input) => {
    input.disabled = checked;
    if (checked) input.checked = false;
  });
}

async function sendMemberNotice(event) {
  event.preventDefault();
  const note = document.getElementById('noticeSendNote');
  const title = document.getElementById('noticeTitle')?.value.trim() || '';
  const body = document.getElementById('noticeBody')?.value.trim() || '';
  const everyone = !!document.getElementById('noticeEveryone')?.checked;
  const usernames = [...document.querySelectorAll('.notice-member-check:checked')].map((input) => input.value);
  if (note) note.textContent = '';
  const res = await fetch('/api/notices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, body, everyone, usernames })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (note) note.textContent = data.detail || 'تعذر إرسال الرسالة';
    return;
  }
  if (note) note.textContent = `أُرسلت إلى ${data.recipients} عضواً`;
  const titleInput = document.getElementById('noticeTitle');
  const bodyInput = document.getElementById('noticeBody');
  if (titleInput) titleInput.value = '';
  if (bodyInput) bodyInput.value = '';
  document.querySelectorAll('.notice-member-check').forEach((input) => { input.checked = false; });
  const everyoneBox = document.getElementById('noticeEveryone');
  if (everyoneBox) everyoneBox.checked = false;
  toggleNoticeEveryone(false);
  loadAdminNotices();
  refreshNoticeBell();
}

async function loadAdminNotices() {
  const box = document.getElementById('adminNoticesList');
  if (!box || !document.body.classList.contains('is-admin')) return;
  const res = await fetch('/api/notices/admin');
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    box.textContent = data.detail || 'تعذر تحميل الرسائل';
    return;
  }
  const notices = data.notices || [];
  if (!notices.length) {
    box.innerHTML = '<p class="member-meta">لا رسائل بعد.</p>';
    return;
  }
  box.innerHTML = notices.map((notice) => {
    const readers = (notice.readers || []).map((item) => `<li>${memberEscape(item.username)} · ${memberEscape(memberTime(item.read_at))}</li>`).join('') || '<li>لا أحد بعد</li>';
    const pending = (notice.pending || []).map((name) => `<li>${memberEscape(name)}</li>`).join('') || '<li>لا أحد</li>';
    return `
      <article class="admin-notice-card">
        <h4>${memberEscape(notice.title)}</h4>
        <p class="notice-card-text">${memberEscape(notice.body)}</p>
        <div class="member-meta">${notice.audience === 'all' ? 'الجميع' : 'أعضاء محددون'} · ${memberEscape(memberTime(notice.created_at))}</div>
        <div class="notice-read-columns">
          <div><h5>قرؤوها</h5><ul>${readers}</ul></div>
          <div><h5>لم يقرؤوها</h5><ul>${pending}</ul></div>
        </div>
        <div class="notice-card-footer">
          <button type="button" class="btn-chart-type" data-delete-notice="${memberEscape(notice.id)}">حذف</button>
        </div>
      </article>`;
  }).join('');
}

async function onAdminNoticeClick(event) {
  const button = event.target.closest('[data-delete-notice]');
  if (!button) return;
  await fetch('/api/notices/' + encodeURIComponent(button.getAttribute('data-delete-notice')), { method: 'DELETE' });
  loadAdminNotices();
  refreshNoticeBell();
}

function paintNoticeBadge(count) {
  const badge = document.getElementById('noticeBadge');
  if (!badge) return;
  const unread = Number(count) || 0;
  badge.hidden = unread < 1;
  badge.textContent = unread > 9 ? '9+' : String(unread);
}

async function refreshNoticeBell() {
  try {
    const res = await fetch('/api/notices');
    if (!res.ok) return;
    const data = await res.json();
    window._myNotices = data.notices || [];
    paintNoticeBadge(data.unread || 0);
    if (document.getElementById('noticesModal')?.classList.contains('open')) renderMyNotices();
  } catch (err) {}
}

function renderMyNotices() {
  const body = document.getElementById('noticesModalBody');
  if (!body) return;
  const notices = window._myNotices || [];
  if (!notices.length) {
    body.innerHTML = '<p class="member-meta">لا رسائل موجهة إليك.</p>';
    return;
  }
  body.innerHTML = notices.map((notice) => `
    <article class="notice-card">
      <div class="notice-card-body">
        <h3 class="notice-card-title">${memberEscape(notice.title)}</h3>
        <p class="notice-card-text">${memberEscape(notice.body)}</p>
      </div>
      <div class="notice-card-footer">
        <span class="notice-card-time">${memberEscape(memberTime(notice.created_at))}</span>
        ${notice.read
          ? `<span class="member-meta">تم الاطلاع</span>`
          : `<button type="button" class="btn-flat-primary" data-read-notice="${memberEscape(notice.id)}">تم الاطلاع</button>`}
      </div>
    </article>`).join('');
}

function openNoticesModal() {
  const modal = document.getElementById('noticesModal');
  if (!modal) return;
  modal.classList.add('open');
  renderMyNotices();
  refreshNoticeBell();
}

function closeNoticesModal() {
  document.getElementById('noticesModal')?.classList.remove('open');
}

async function onNoticeReadClick(event) {
  const button = event.target.closest('[data-read-notice]');
  if (!button) return;
  button.disabled = true;
  await fetch('/api/notices/' + encodeURIComponent(button.getAttribute('data-read-notice')) + '/read', { method: 'POST' });
  await refreshNoticeBell();
}

window.openNoticesModal = openNoticesModal;
window.closeNoticesModal = closeNoticesModal;
window.filterNoticeMembers = filterNoticeMembers;
window.toggleNoticeEveryone = toggleNoticeEveryone;
window.loadAdminNotices = loadAdminNotices;
