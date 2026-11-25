/* موقع المغني — تبويبات وكتالوج ملفات وعدّادات محلية تجريبية.
   العدّادات: زيارات وتحميلات هذا المتصفح (localStorage) فوق أرقام
   الكتالوج الأساسية؛ عند الرفع على الاستضافة تُستبدل بمصدر خادمي. */
(function () {
  "use strict";
  var FILE_TABS = {
    projects: "المشاريع",
    chats: "المحادثات",
    manuscripts: "المخطوطات",
    agents: "الوكلاء",
    reading: "قراءة وتحليل",
    tools: "الأدوات",
    patterns: "الأنماط"
  };
  var state = { catalog: null, releases: null, tab: "about", query: "" };

  function $(id) { return document.getElementById(id); }
  function fmt(n) { return Number(n || 0).toLocaleString("ar-EG"); }

  /* ---------- العدّادات المحلية ---------- */
  var LS_V = "almoghni_site_visits", LS_D = "almoghni_site_downloads";
  function visits() {
    var v = parseInt(localStorage.getItem(LS_V) || "0", 10);
    if (!sessionStorage.getItem("almoghni_counted")) {
      v += 1;
      localStorage.setItem(LS_V, String(v));
      sessionStorage.setItem("almoghni_counted", "1");
    }
    return v;
  }
  function localDownloads() {
    try { return JSON.parse(localStorage.getItem(LS_D) || "{}"); } catch (e) { return {}; }
  }
  function bumpDownload(key) {
    var d = localDownloads();
    d[key] = (d[key] || 0) + 1;
    localStorage.setItem(LS_D, JSON.stringify(d));
    renderCounts();
  }
  function downloadsOf(item) {
    return (item.downloads || 0) + (localDownloads()[item.key] || 0);
  }
  function totalDownloads() {
    if (!state.catalog) return 0;
    var total = 0;
    Object.keys(state.catalog.categories || {}).forEach(function (cat) {
      (state.catalog.categories[cat] || []).forEach(function (it) { total += downloadsOf(it); });
    });
    (state.catalog.installers || []).forEach(function (it) { total += downloadsOf(it); });
    return total;
  }
  function totalItems() {
    if (!state.catalog) return 0;
    var n = 0;
    Object.keys(state.catalog.categories || {}).forEach(function (cat) {
      n += (state.catalog.categories[cat] || []).length;
    });
    return n;
  }
  function renderCounts() {
    var v = visits(), d = totalDownloads();
    ["visitorCount", "statVisitors", "footVisitors"].forEach(function (id) { if ($(id)) $(id).textContent = fmt(v); });
    ["statDownloads", "footDownloads"].forEach(function (id) { if ($(id)) $(id).textContent = fmt(d); });
    if ($("statItems")) $("statItems").textContent = fmt(totalItems());
    if (state.catalog) {
      (state.catalog.installers || []).forEach(function (it) {
        var el = $(it.key + "Count");
        if (el) el.textContent = fmt(downloadsOf(it));
      });
    }
  }

  /* ---------- التبويبات ---------- */
  function showTab(tab) {
    state.tab = tab;
    document.querySelectorAll(".tab").forEach(function (b) {
      b.classList.toggle("active", b.dataset.tab === tab);
    });
    document.querySelectorAll(".panel").forEach(function (p) { p.classList.remove("active"); });
    if (tab === "about") $("panel-about").classList.add("active");
    else if (tab === "downloads") $("panel-downloads").classList.add("active");
    else { $("panel-files").classList.add("active"); renderFiles(); }
  }
  document.querySelectorAll(".tab").forEach(function (b) {
    b.addEventListener("click", function () { showTab(b.dataset.tab); });
  });
  document.querySelectorAll("[data-goto]").forEach(function (a) {
    a.addEventListener("click", function (e) { e.preventDefault(); showTab(a.dataset.goto); });
  });
  $("filesSearch").addEventListener("input", function () {
    state.query = this.value.trim();
    renderFiles();
  });

  /* ---------- الملفات ---------- */
  function fileUrl(it) { return it.file || ""; }
  function renderFiles() {
    var cat = state.tab;
    $("filesTitle").textContent = FILE_TABS[cat] || "الملفات";
    var items = (state.catalog && state.catalog.categories[cat]) || [];
    if (state.query) {
      items = items.filter(function (it) {
        return (it.name + " " + (it.desc || "")).indexOf(state.query) >= 0;
      });
    }
    var body = $("filesBody");
    body.innerHTML = "";
    items.forEach(function (it) {
      var tr = document.createElement("tr");
      var dl = document.createElement("a");
      dl.className = "btn btn-sm";
      dl.textContent = "تحميل";
      dl.href = fileUrl(it);
      dl.setAttribute("download", "");
      dl.addEventListener("click", function () { bumpDownload(it.key); });
      tr.innerHTML =
        "<td><b></b></td><td></td><td class='num'></td><td class='num'></td><td class='num'></td><td></td>";
      tr.children[0].querySelector("b").textContent = it.name || "";
      tr.children[1].textContent = it.desc || "";
      tr.children[2].textContent = it.size || "—";
      tr.children[3].textContent = it.date || "—";
      tr.children[4].textContent = fmt(downloadsOf(it));
      tr.children[5].appendChild(dl);
      body.appendChild(tr);
    });
    $("filesEmpty").hidden = items.length > 0;
  }

  /* ---------- الإصدارات ---------- */
  function renderReleases() {
    if (!state.releases || !state.releases.length) return;
    var latest = state.releases[0];
    $("latestVersion").textContent = "آخر إصدار: " + latest.version + " (نسخة تجريبية)";
    if ($("appVersionLabel")) $("appVersionLabel").textContent = "إصدار رقم " + latest.version + " (نسخة تجريبية)";
    $("statVersion").textContent = latest.version;
    var wn = $("whatsNew");
    wn.innerHTML = "";
    var h = document.createElement("h4");
    h.style.cssText = "font-family:var(--font-amiri);margin:0 0 6px;font-size:20px";
    h.textContent = "إصدار " + latest.version;
    var ul = document.createElement("ul");
    ul.style.cssText = "margin:4px 0;padding-inline-start:22px";
    (latest.notes || []).forEach(function (n) {
      var li = document.createElement("li");
      li.textContent = n;
      ul.appendChild(li);
    });
    wn.appendChild(h); wn.appendChild(ul);

    var rel = $("releases");
    rel.innerHTML = "";
    state.releases.forEach(function (r, i) {
      var div = document.createElement("div");
      div.className = "release";
      var head = document.createElement("h4");
      head.textContent = "إصدار " + r.version + " ";
      if (i === 0) {
        var tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = "الأحدث";
        head.appendChild(tag);
      }
      var list = document.createElement("ul");
      (r.notes || []).forEach(function (n) {
        var li = document.createElement("li");
        li.textContent = n;
        list.appendChild(li);
      });
      div.appendChild(head); div.appendChild(list);
      rel.appendChild(div);
    });
  }

  function renderInstallers() {
    if (!state.catalog) return;
    (state.catalog.installers || []).forEach(function (it) {
      var meta = $(it.key + "Meta"), btn = $(it.key + "Btn");
      if (meta) meta.textContent = "إصدار " + (it.version || "—") + (it.size ? " · " + it.size : "") + (it.date ? " · " + it.date : "");
      if (btn) {
        btn.href = it.file;
        btn.addEventListener("click", function () { bumpDownload(it.key); });
        // ملف غير مرفوع بعد محليًا: يُعطَّل الزر بدل رابط مكسور
        fetch(it.file, { method: "HEAD" }).then(function (r) {
          if (!r.ok) { btn.setAttribute("aria-disabled", "true"); btn.textContent = "تتوفر مع رفع الموقع"; }
        }).catch(function () {
          btn.setAttribute("aria-disabled", "true");
          btn.textContent = "تتوفر مع رفع الموقع";
        });
      }
    });
  }

  /* ---------- النوافذ والأنماط ---------- */
  var SITE_THEMES = [
    { id: "muzakhraf", label: "المزخرف (افتراضي الموقع)", dot: "#aa7942" },
    { id: "sand", label: "الرملي", dot: "#B56A4C" },
    { id: "ink", label: "الحبر", dot: "#1E4D78" },
    { id: "oasis", label: "الواحة", dot: "#1E6A49" },
    { id: "silk", label: "الحرير", dot: "#C4A15A" },
    { id: "charcoal", label: "الفحمي", dot: "#D6B56A" },
    { id: "marine", label: "البحري", dot: "#C56B45" },
    { id: "north-sand", label: "رمال الشمال", dot: "#F0C93A" },
    { id: "lilac", label: "ليلك", dot: "#7B5CFA" },
    { id: "marshmallow", label: "مارشملو", dot: "#6B4DFF" }
  ];
  function applySiteTheme(id) {
    var root = document.documentElement;
    if (!id || id === "muzakhraf") root.removeAttribute("data-site-theme");
    else root.setAttribute("data-site-theme", id);
    localStorage.setItem("almoghni_site_theme", id || "muzakhraf");
    document.querySelectorAll(".theme-item").forEach(function (b) {
      b.classList.toggle("active", b.dataset.themeId === (id || "muzakhraf"));
    });
  }
  function buildThemeList() {
    var list = $("themeList");
    if (!list) return;
    SITE_THEMES.forEach(function (t) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "theme-item";
      b.dataset.themeId = t.id;
      var dot = document.createElement("span");
      dot.className = "theme-dot";
      dot.style.background = t.dot;
      b.appendChild(dot);
      b.appendChild(document.createTextNode(t.label));
      b.addEventListener("click", function () {
        applySiteTheme(t.id);
        closeModal($("themeModal"));
      });
      list.appendChild(b);
    });
    applySiteTheme(localStorage.getItem("almoghni_site_theme") || "muzakhraf");
  }
  function openModal(m) { if (m) m.hidden = false; }
  function closeModal(m) { if (m) m.hidden = true; }
  if ($("socialBtn")) $("socialBtn").addEventListener("click", function () { openModal($("socialModal")); });
  if ($("themeBtn")) $("themeBtn").addEventListener("click", function () { openModal($("themeModal")); });
  document.querySelectorAll(".modal-veil").forEach(function (veil) {
    veil.addEventListener("click", function (e) { if (e.target === veil) closeModal(veil); });
    veil.querySelectorAll("[data-close]").forEach(function (b) {
      b.addEventListener("click", function () { closeModal(veil); });
    });
  });
  buildThemeList();

  /* ---------- الإقلاع ---------- */
  Promise.all([
    fetch("data/catalog.json").then(function (r) { return r.json(); }),
    fetch("data/changelog.json").then(function (r) { return r.json(); })
  ]).then(function (res) {
    state.catalog = res[0];
    state.releases = res[1].releases || [];
    renderReleases();
    renderInstallers();
    renderCounts();
  }).catch(function () {
    if ($("whatsNew")) $("whatsNew").innerHTML = "<p class='muted'>تعذّر تحميل بيانات الموقع.</p>";
  });
})();
