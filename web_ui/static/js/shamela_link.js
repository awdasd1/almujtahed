// ربط المكتبة الشاملة المحلية: كشف، إحصاء، استيراد بخلفية وتقدّم.
let _shamelaPoll = null;

async function loadShamelaStatus() {
  const badge = document.getElementById('shamelaLinkBadge');
  const text = document.getElementById('shamelaLinkText');
  const btn = document.getElementById('shamelaImportBtn');
  const prog = document.getElementById('shamelaImportProgress');
  if (!badge) return;
  try {
    const r = await fetch('/api/shamela/status');
    const st = await r.json();
    _applyShamelaPathUi(st);
    if (!st.found) {
      badge.textContent = 'غير موجود';
      text.textContent = st.message || 'لم يُعثر على تطبيق المكتبة الشاملة الجديد على هذا الجهاز. تبقى مكتبة المجتهد المدمجة هي المصدر.';
      btn.style.display = 'none';
      return;
    }
    badge.textContent = 'موجود ✓';
    const lines = [
      st.shamela_root ? `<span dir="ltr" style="unicode-bidi: embed;">📂 ${st.shamela_root}</span>` : '',
      st.library_source === 'shamela'
        ? '📚 مصدر مكتبة البحث الحالي: <b>الشاملة المثبتة على جهازك</b> (النسخ المستوردة منها) — والنسخة المدمجة محفوظة احتياطًا للرجوع.'
        : '📚 مصدر مكتبة البحث الحالي: النسخة المدمجة في التطبيق.',
      `تطبيق الشاملة مثبّت: كتالوجه ${Number(st.catalog_total).toLocaleString('ar')} كتابًا، المنزّل منه فعليًا ${Number(st.downloaded).toLocaleString('ar')} كتابًا${st.downloaded < st.catalog_total ? ' (ينزّل الباقي عند الطلب)' : ''}.`,
      `من المنزّل: ${Number(st.downloaded_in_our_library).toLocaleString('ar')} موجود أصلًا في مكتبة المجتهد، و${Number(st.importable_new).toLocaleString('ar')} جديد قابل للاستيراد، والمستورَد سابقًا ${Number(st.imported).toLocaleString('ar')}.`
    ];
    if (st.downloaded < st.catalog_total) {
      lines.push(`المكتبة عندك في الشاملة ناقصة (${Number(st.missing_from_shamela_downloads).toLocaleString('ar')} كتاب غير منزّل): الأفضل إكمال تنزيل ما تحتاجه داخل تطبيق الشاملة ثم استيراده هنا، أو الاعتماد على مكتبة المجتهد المدمجة الكاملة.`);
    } else {
      lines.push('مكتبة الشاملة عندك مكتملة التنزيل — كل كتاب فيها متاح للاستيراد فورًا.');
    }
    if (st.advice) lines.push(st.advice);
    text.innerHTML = lines.map((s) => `<div>${s}</div>`).join('');
    btn.style.display = st.importable_new > 0 ? '' : 'none';
    const cbtn = document.getElementById('shamelaCompleteBtn');
    if (cbtn) cbtn.style.display = st.missing_from_shamela_downloads > 0 ? '' : 'none';
    const job = st.job || {};
    if (job.watching && !job.running) {
      prog.style.display = '';
      prog.textContent = '👀 نراقب تطبيق الشاملة: نزّل الكتب الناقصة هناك وستُستورد هنا تلقائيًا فور وصولها.';
      _startShamelaPoll();
    }
    if (job.running) {
      prog.style.display = '';
      const elapsed = job.started_at ? Math.max(0, Math.round(Date.now() / 1000 - job.started_at)) : 0;
      const el = elapsed >= 60 ? `${Math.floor(elapsed / 60)} د ${elapsed % 60} ث` : `${elapsed} ث`;
      let msg;
      if (job.stage === 'scan' && job.of) {
        const pct = Math.min(100, Math.round(100 * job.i / job.of));
        msg = `جارٍ الاستيراد — فحص فهرس الشاملة: ${Number(job.i).toLocaleString('ar')} من ${Number(job.of).toLocaleString('ar')} صفحة (${pct}٪) · منذ ${el}`;
      } else if (job.stage === 'book' && job.of) {
        msg = `جارٍ الاستيراد — تحويل كتاب ${job.i} من ${job.of}: ${job.title || ''} · منذ ${el}`;
      } else if (job.stage === 'register') {
        msg = 'جارٍ تسجيل كتب الشاملة الجديدة في المكتبة (بلا تحويل — تُستخرج عند أول لمس)…';
      } else if (job.stage === 'install_jpype') {
        msg = 'جارٍ الاستيراد — تجهيز قارئ فهرس الشاملة (مرة واحدة)…';
      } else if (job.stage === 'indexed') {
        msg = 'جارٍ الاستيراد — اكتمل الفحص، يبدأ التحويل…';
      } else {
        msg = `جارٍ الاستيراد — يبدأ فحص فهرس الشاملة عندك… · منذ ${el}`;
      }
      prog.innerHTML = `<div>${msg}</div><div style="height:6px;background:var(--border-subtle,#ddd);border-radius:4px;margin-top:6px;overflow:hidden;"><div style="height:100%;width:${job.of ? Math.min(100, Math.round(100 * job.i / job.of)) : 4}%;background:#0e7a5f;transition:width .6s;"></div></div>`;
      _startShamelaPoll();
    } else if (job.stage === 'done' && job.report) {
      prog.style.display = '';
      const rep = job.report;
      prog.textContent = rep.registered !== undefined
        ? `اكتمل تسجيل كتب الشاملة الجديدة: ${Number(rep.registered || 0).toLocaleString('ar')} كتابًا — تُستخرج نصوصها تلقائيًا عند أول بحث أو قراءة فيها.`
        : `اكتمل آخر استيراد: ${rep.converted ? rep.converted.length : 0} كتابًا (${Number(rep.pages || 0).toLocaleString('ar')} صفحة).`;
    } else if (job.stage === 'error') {
      prog.style.display = '';
      prog.textContent = 'تعذّر الاستيراد: ' + (job.error || '');
    } else if (!job.watching) {
      prog.style.display = 'none';
    }
  } catch (e) {
    badge.textContent = 'تعذّر الفحص';
  }
}

function _startShamelaPoll() {
  if (_shamelaPoll) return;
  _shamelaPoll = setInterval(async () => {
    await loadShamelaStatus();
    const r = await fetch('/api/shamela/status');
    const st = await r.json();
    if (!st.job || !st.job.running) {
      clearInterval(_shamelaPoll);
      _shamelaPoll = null;
      loadShamelaStatus();
    }
  }, 4000);
}

async function startShamelaImport() {
  const btn = document.getElementById('shamelaImportBtn');
  btn.disabled = true;
  try {
    const r = await fetch('/api/shamela/import', { method: 'POST' });
    const st = await r.json();
    if (!st.ok) alert(st.message || 'تعذّر بدء الاستيراد');
    else _startShamelaPoll();
  } catch (e) {
    alert('تعذّر بدء الاستيراد');
  } finally {
    btn.disabled = false;
  }
}

async function startShamelaComplete() {
  try {
    const r = await fetch('/api/shamela/complete', { method: 'POST' });
    const st = await r.json();
    alert(st.message || 'فُتح تطبيق الشاملة.');
    _startShamelaPoll();
    loadShamelaStatus();
  } catch (e) {
    alert('تعذّر فتح الشاملة — افتحها يدويًا ونزّل ما تحتاجه، ثم اضغط «استيراد الكتب المنزّلة».');
  }
}

function _applyShamelaPathUi(st) {
  const input = document.getElementById('shamelaPathInput');
  const clearBtn = document.getElementById('shamelaPathClearBtn');
  if (!input) return;
  if (document.activeElement !== input) {
    input.value = st.custom_root || st.shamela_root || '';
  }
  if (clearBtn) clearBtn.style.display = st.custom_root ? '' : 'none';
}

function _pickFolderNative(promptText) {
  /* منتقي مجلد أصلي: جسر الماك الجاهز، أو جسر ويندوز (WebView2)،
     وnull إن فتح المستخدم الواجهة من متصفح عادي بلا جسر. */
  if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.almujtahed
      && typeof chooseNativeFolder === 'function') {
    return chooseNativeFolder(promptText);
  }
  if (window.chrome && window.chrome.webview) {
    return new Promise((resolve) => {
      const handler = (e) => {
        try {
          const d = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
          if (d && 'almujtahedFolder' in d) {
            window.chrome.webview.removeEventListener('message', handler);
            resolve(d.almujtahedFolder || '');
          }
        } catch (_) { /* رسائل أخرى */ }
      };
      window.chrome.webview.addEventListener('message', handler);
      window.chrome.webview.postMessage(JSON.stringify({ action: 'chooseFolder', prompt: promptText }));
      setTimeout(() => {
        window.chrome.webview.removeEventListener('message', handler);
        resolve('');
      }, 180000);
    });
  }
  return Promise.resolve(null);
}

async function browseShamelaPath() {
  const input = document.getElementById('shamelaPathInput');
  const picked = await _pickFolderNative('اختر مجلد المكتبة الشاملة — المجلد الذي يحتوي مجلد database');
  if (picked === null) {
    if (input) { input.focus(); input.select(); }
    if (typeof showToast === 'function') showToast('الاستعراض الأصلي متاح داخل التطبيق؛ هنا الصق المسار يدويًا');
    return;
  }
  if (!picked) return; // ألغي الاختيار
  if (input) input.value = picked;
  saveShamelaPath();
}

async function saveShamelaPath() {
  const input = document.getElementById('shamelaPathInput');
  const note = document.getElementById('shamelaPathNote');
  const path = (input?.value || '').trim();
  if (!path) { alert('الصق مسار مجلد الشاملة أولًا.'); return; }
  try {
    const r = await fetch('/api/shamela/path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    const res = await r.json();
    if (!res.ok) { alert(res.message || 'المسار غير صالح.'); return; }
    if (note) note.textContent = `✅ ${res.message} — أعدنا الفحص والمزامنة على هذا الأساس.`;
    if (typeof showToast === 'function') showToast('تم حفظ مسار الشاملة والتحقق منه');
    loadShamelaStatus();
  } catch (e) {
    alert('تعذّر حفظ المسار.');
  }
}

async function clearShamelaPath() {
  try {
    await fetch('/api/shamela/path', { method: 'DELETE' });
    const input = document.getElementById('shamelaPathInput');
    if (input) input.value = '';
    if (typeof showToast === 'function') showToast('أُلغي المسار اليدوي — عاد الكشف الافتراضي');
    loadShamelaStatus();
  } catch (e) { /* تجاهل */ }
}

document.addEventListener('DOMContentLoaded', () => { loadShamelaStatus(); });
