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
