// مشجرات الأسانيد والأقوال عبر Cytoscape: العقدة والوصلة في رسم واحد
const FORCE3D_COLORS = {
  madar: '#d97706',
  sahabi: '#2563eb',
  weak: '#dc2626',
  issue: '#9a3412',
  opinion: '#7c3aed',
  madhhab: '#1d4ed8',
  evidence: '#0f766e',
  objection: '#b91c1c',
  reply: '#0e7490',
  tarjih: '#b45309',
  usul: '#3f6212',
  book: '#92400e',
  narrator: '#059669',
  hadith: '#1e3a5f',
  prophet: '#7c2d12',
  tabi: '#0f766e',
  taba: '#3f6212'
};

const FORCE3D_EXAMPLES = [
  { id: 'tree', group: 'شجري', label: 'علوي', note: 'الأصل في الأعلى والفروع تحته: شيخ ثم تلميذ، أو مسألة ثم قول ثم دليل.' },
  { id: 'taxi', group: 'شجري', label: 'متعامد', note: 'خطوط قائمة الزاوية حتى لا تتقاطع طرق الإسناد ولا فروع الخلاف.' },
  { id: 'radial', group: 'شجري', label: 'شعاعي', note: 'الأصل في الوسط والحلقات حوله بحسب الطبقة أو قرب القول من المسألة.' },
  { id: 'madar', group: 'شجري', label: 'المركز', note: 'في الوسط المدار، أو المسألة، أو الدليل المشترك بين الأقوال.' },
  { id: 'fixed', group: 'قيود الباحث', label: 'تثبيت الأصل', note: 'يثبت الصحابي أو المسألة أو محل النزاع في الأعلى، وتترتب الفروع تحته مع مراعاة عرض الأسماء.' },
  { id: 'align', group: 'قيود الباحث', label: 'محاذاة الطبقات', note: 'كل طبقة على خط أفقي واحد: الصحابة معاً، ثم التابعون، ثم الكتب. والسهم في الإسناد يصعد من الأدنى إلى الأعلى.' },
  { id: 'sides', group: 'قيود الباحث', label: 'طرفا الخلاف', note: 'يفرّق فرعي الأصل يميناً ويساراً: الجواز والمنع، أو الدعوى ونقيضها، ويُبقي الدليل تحت القول.' },
  { id: 'hybrid', group: 'قيود الباحث', label: 'هجين مقيد', note: 'يجمع تثبيت الأصل ومحاذاة الطبقات وفصل الطرفين في رسم واحد.' },
  { id: 'spring', group: 'قيود الباحث', label: 'توزيع مرن', note: 'توزيع حر بلا صفوف صارمة حين تتكاثر المناقشات ويضيق الشكل الشجري.' },
  { id: 'lib-sample1', group: 'قيود على هذا الرسم', label: 'تثبيت المواضع', note: 'على شجرتك: يثبت الأصل وطرفا الخلاف أو طرفا الإسناد، وتتحرك بقية الأسماء حولها.' },
  { id: 'lib-sample2', group: 'قيود على هذا الرسم', label: 'محاذاة الصفوف والأعمدة', note: 'على شجرتك: كل طبقة في صف، وكل طريق أو مذهب في عمود.' },
  { id: 'lib-sample3', group: 'قيود على هذا الرسم', label: 'ترتيب نسبي', note: 'على شجرتك: الأصل فوق الفرع، والأقوال أو الرواة المتقابلون يميناً ويساراً.' },
  { id: 'lib-sample4', group: 'قيود على هذا الرسم', label: 'قيد مركّب', note: 'على شجرتك: تثبيت الأصل مع صفوف الطبقات وأعمدة الطرق وترتيب الفروع.' },
  { id: 'lib-uwsn', group: 'قيود على هذا الرسم', label: 'صف علوي واسع', note: 'على شجرتك: الأقوال أو الطرق مثبتة في صف علوي، ثم تنزل الأدلة والمناقشة تحتها بمسافات واسعة.' },
  { id: 'lib-callgraph', group: 'قيود على هذا الرسم', label: 'صفوف الأجيال', note: 'على شجرتك: كل جيل في صف، والشيخ فوق التلميذ أو الدليل فوق الاعتراض.' }
];

const FORCE3D_FONTS = [
  ['Amiri', 'أميري'],
  ['Noto Naskh Arabic', 'نسخ نوتو'],
  ['Noto Kufi Arabic', 'كوفي نوتو'],
  ['Noto Sans Arabic', 'نوتو'],
  ['Cairo', 'القاهرة'],
  ['Tajawal', 'تجوال'],
  ['IBM Plex Sans Arabic', 'بلكس عربي'],
  ['Readex Pro', 'ريدكس'],
  ['Scheherazade New', 'شهرزاد'],
  ['Lateef', 'لطيف'],
  ['Aref Ruqaa', 'عارف رقعة'],
  ['El Messiri', 'المسيري'],
  ['Almarai', 'المراعي'],
  ['Markazi Text', 'مركزي'],
  ['Reem Kufi', 'ريم كوفي'],
  ['Changa', 'تشانغا'],
  ['Lemonada', 'ليمونادة'],
  ['Mirza', 'ميرزا'],
  ['Harmattan', 'هرمتان']
];

const FORCE3D_BACKGROUNDS = [
  ['#f7f3ec', 'رملي'],
  ['#ffffff', 'أبيض'],
  ['#fbf6ea', 'كريمي'],
  ['#f3e6c8', 'عاجي'],
  ['#efe2c9', 'ورقي'],
  ['#f8efe9', 'زهري'],
  ['#e7f0f6', 'سماوي'],
  ['#e7f3ec', 'نعناعي'],
  ['#f3eef8', 'لافندر'],
  ['#1c1917', 'ليلي'],
  ['#292524', 'فحمي'],
  ['#1e293b', 'كحلي'],
  ['#1c2b24', 'زيتي'],
  ['#3f2e22', 'بني']
];

let force3dLoader = null;

function force3dEscape(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function force3dRoleKey(role) {
  const text = String(role || '');
  if (/حديث|أثر|متن/.test(text)) return 'hadith';
  if (/نبي|رسول/.test(text)) return 'prophet';
  if (/مدار/.test(text)) return 'madar';
  if (/صحاب/.test(text)) return 'sahabi';
  if (/تابع التابعين|أتباع التابعين|تبع الأتباع/.test(text)) return 'taba';
  if (/تابعي|التابعون/.test(text)) return 'tabi';
  if (/ضعيف|معلول|متروك|منكر|كذاب/.test(text)) return 'weak';
  if (/مسألة|محل النزاع|دعوى/.test(text)) return 'issue';
  if (/ترجيح/.test(text)) return 'tarjih';
  if (/اعتراض|مناقشة|شبهة|إشكال/.test(text)) return 'objection';
  if (/جواب|إجابة|رد/.test(text)) return 'reply';
  if (/مذهب|فرقة|مقالة|قائل/.test(text)) return 'madhhab';
  if (/دليل|وجه الدلالة/.test(text)) return 'evidence';
  if (/قول/.test(text)) return 'opinion';
  if (/أصل|قاعدة|سبب الخلاف/.test(text)) return 'usul';
  if (/كتاب|مخرج|مصدر/.test(text)) return 'book';
  return 'narrator';
}

function force3dIsnadRank(node) {
  const role = String((node && node.role) || '');
  const name = String((node && node.name) || '');
  if (/حديث|أثر|متن/.test(role)) return 0;
  if (/نبي|رسول/.test(role) || /^(النبي|رسول الله)/.test(name)) return 1;
  if (/صحاب/.test(role)) return 2;
  if (/تابع التابعين|أتباع التابعين|تبع الأتباع/.test(role)) return 4;
  if (/تابعي|التابعون/.test(role)) return 3;
  if (/مدار/.test(role)) return 5;
  if (/طريق|ضعيف|معلول/.test(role)) return 6;
  if (/كتاب|مخرج|مصدر/.test(role)) return 7;
  return null;
}

function force3dIsnadGraph(data) {
  return (data.nodes || []).some((node) => /صحاب|تابعي|كتاب|حديث|أثر|نبي|مدار/.test(String(node.role || '')));
}

function force3dDisplayLink(link, data) {
  if (!force3dIsnadGraph(data)) return link;
  const byId = new Map(data.nodes.map((node) => [node.id, node]));
  const sourceRank = force3dIsnadRank(byId.get(link.source) || {});
  const targetRank = force3dIsnadRank(byId.get(link.target) || {});
  if (sourceRank == null || targetRank == null || sourceRank === targetRank) return link;
  if (sourceRank < targetRank) {
    return { source: link.target, target: link.source, label: link.label };
  }
  return link;
}

function force3dExample(id) {
  return FORCE3D_EXAMPLES.find((item) => item.id === id) || FORCE3D_EXAMPLES[0];
}

function loadClassicScript(src) {
  return new Promise((resolve, reject) => {
    const found = document.querySelector(`script[data-force3d-src="${src}"]`);
    if (found) {
      if (found.dataset.loaded === '1') resolve();
      else found.addEventListener('load', () => resolve(), { once: true });
      return;
    }
    const script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.dataset.force3dSrc = src;
    script.onload = () => {
      script.dataset.loaded = '1';
      resolve();
    };
    script.onerror = () => reject(new Error(src));
    document.head.appendChild(script);
  });
}

function ensureCytoscape() {
  if (window.cytoscape && window.cytoscapeFcose) return Promise.resolve();
  if (force3dLoader) return force3dLoader;
  force3dLoader = loadClassicScript('/static/js/cytoscape.min.js')
    .then(() => loadClassicScript('/static/js/layout-base.js'))
    .then(() => loadClassicScript('/static/js/cose-base.js'))
    .then(() => loadClassicScript('/static/js/cytoscape-fcose.js'))
    .then(() => {
      if (!window.cytoscape || !window.cytoscapeFcose) throw new Error('fcose missing');
      if (!window._fcoseRegistered) {
        window.cytoscape.use(window.cytoscapeFcose);
        window._fcoseRegistered = true;
      }
    });
  force3dLoader.catch(() => { force3dLoader = null; });
  return force3dLoader;
}

function force3dResolveId(token, nodes) {
  const text = String(token ?? '').trim();
  if (!text) return '';
  if (nodes.some((node) => node.id === text)) return text;
  const byName = nodes.find((node) => node.name === text);
  return byName ? byName.id : '';
}

function force3dFlattenNodes(list, parentId, bucket) {
  (Array.isArray(list) ? list : []).forEach((node) => {
    if (!node || typeof node !== 'object' || Array.isArray(node)) return;
    const id = String(node.id ?? node.name ?? bucket.length + 1).trim();
    const parent = node.parent ?? node.parentId ?? node.parent_id ?? parentId ?? '';
    bucket.push({
      id,
      name: node.name || node.label || node.text || id,
      role: node.role || node.group || '',
      detail: node.detail || node.info || '',
      parent: parent ? String(parent).trim() : ''
    });
    if (Array.isArray(node.children)) force3dFlattenNodes(node.children, id, bucket);
  });
}

function force3dJsonSlice(text) {
  const start = String(text || '').indexOf('{');
  if (start < 0) return String(text || '');
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (inString) {
      if (escape) escape = false;
      else if (ch === '\\') escape = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') {
      inString = true;
      continue;
    }
    if (ch === '{') depth += 1;
    else if (ch === '}') {
      depth -= 1;
      if (depth === 0) return text.slice(start, i + 1);
    }
  }
  return text.slice(start);
}

function parseForce3dBlock(raw) {
  let text = force3dJsonSlice(String(raw || '').trim());
  text = text.replace(/,\s*([}\]])/g, '$1');
  const data = JSON.parse(text);
  const seed = Array.isArray(data.nodes) ? data.nodes : (Array.isArray(data.children) ? data.children : []);
  const flat = [];
  force3dFlattenNodes(seed, '', flat);
  const nodes = flat.map((node) => ({
    id: node.id,
    name: String(node.name || '').trim(),
    role: String(node.role || '').trim(),
    detail: String(node.detail || '').trim(),
    parent: node.parent
  })).filter((node) => node.id && node.name);
  const seen = new Set();
  const unique = nodes.filter((node) => {
    if (seen.has(node.id)) return false;
    seen.add(node.id);
    return true;
  });
  const sourceLinks = Array.isArray(data.links) ? data.links : (Array.isArray(data.edges) ? data.edges : []);
  const parentLinks = unique
    .filter((node) => node.parent)
    .map((node) => ({ source: node.parent, target: node.id, label: '' }));
  const links = sourceLinks.concat(parentLinks).map((link) => ({
    source: force3dResolveId(link.source ?? link.from, unique),
    target: force3dResolveId(link.target ?? link.to, unique),
    label: String(link.label || link.title || '').trim()
  })).filter((link) => link.source && link.target && link.source !== link.target);
  const deduped = [];
  const linkSeen = new Set();
  links.forEach((link) => {
    const key = `${link.source}>${link.target}`;
    if (linkSeen.has(key)) return;
    linkSeen.add(key);
    deduped.push(link);
  });
  if (unique.length < 2 || !deduped.length) return null;
  return {
    title: String(data.title || 'مشجر').trim(),
    nodes: unique.map(({ id, name, role, detail }) => ({ id, name, role, detail })),
    links: deduped
  };
}

function isForce3dCode(codeEl) {
  const cls = codeEl.className || '';
  if (/force3d|force-graph|cytoscape/.test(cls)) return true;
  const raw = (codeEl.textContent || '').trim();
  return raw.startsWith('{') && /"nodes"/.test(raw) && (/"links"/.test(raw) || /"edges"/.test(raw));
}

function force3dMadarId(data) {
  let best = data.nodes[0];
  let bestScore = -1;
  data.nodes.forEach((node) => {
    const degree = data.links.filter((link) => link.source === node.id || link.target === node.id).length;
    const key = force3dRoleKey(node.role);
    const score = degree + (key === 'madar' || key === 'issue' || key === 'evidence' ? 100 : 0);
    if (score > bestScore) {
      best = node;
      bestScore = score;
    }
  });
  return best ? best.id : null;
}

function force3dExampleOptions(selected) {
  const groups = [];
  FORCE3D_EXAMPLES.forEach((item) => {
    let group = groups.find((entry) => entry.label === item.group);
    if (!group) {
      group = { label: item.group, items: [] };
      groups.push(group);
    }
    group.items.push(item);
  });
  return groups.map((group) => `
    <optgroup label="${force3dEscape(group.label)}">
      ${group.items.map((item) => `<option value="${item.id}"${item.id === selected ? ' selected' : ''}>${force3dEscape(item.label)}</option>`).join('')}
    </optgroup>
  `).join('');
}

function force3dStructure(data) {
  const children = new Map(data.nodes.map((node) => [node.id, []]));
  const indegree = new Map(data.nodes.map((node) => [node.id, 0]));
  data.links.forEach((link) => {
    children.get(link.source).push(link.target);
    indegree.set(link.target, (indegree.get(link.target) || 0) + 1);
  });
  const roots = data.nodes.filter((node) => !indegree.get(node.id)).map((node) => node.id);
  const preferred = data.nodes.find((node) => roots.includes(node.id) && /مسألة|محل النزاع|صحابي|مدار/.test(node.role));
  const root = (preferred && preferred.id) || roots[0] || force3dMadarId(data);
  const depth = new Map();
  const queue = [];
  (roots.length ? roots : [root]).forEach((id) => {
    if (!id || depth.has(id)) return;
    depth.set(id, 0);
    queue.push(id);
  });
  let guard = 0;
  const limit = data.nodes.length * data.nodes.length + 8;
  while (queue.length && guard < limit) {
    guard += 1;
    const id = queue.shift();
    const nextDepth = depth.get(id) + 1;
    (children.get(id) || []).forEach((child) => {
      if ((depth.get(child) || 0) >= nextDepth) return;
      depth.set(child, nextDepth);
      queue.push(child);
    });
  }
  data.nodes.forEach((node) => {
    if (!depth.has(node.id)) depth.set(node.id, 1);
  });
  return { root, depth, children };
}

function force3dLayers(structure) {
  const groups = new Map();
  structure.depth.forEach((level, id) => {
    if (!groups.has(level)) groups.set(level, []);
    groups.get(level).push(id);
  });
  return [...groups.values()].filter((group) => group.length > 1);
}

function force3dReachable(structure, origin) {
  const seen = new Set();
  const queue = [origin];
  let guard = 0;
  while (queue.length && guard < 500) {
    guard += 1;
    const id = queue.shift();
    (structure.children.get(id) || []).forEach((child) => {
      if (seen.has(child)) return;
      seen.add(child);
      queue.push(child);
    });
  }
  return seen;
}

function force3dSideConstraints(data, structure) {
  const kids = [...new Set(structure.children.get(structure.root) || [])];
  const ranked = kids.filter((id) => {
    const node = data.nodes.find((item) => item.id === id);
    const key = force3dRoleKey(node && node.role);
    return key === 'opinion' || key === 'madhhab' || key === 'issue';
  });
  const chosen = ranked.length >= 2 ? ranked : kids;
  const constraints = [];
  for (let index = 0; index < chosen.length - 1; index += 1) {
    constraints.push({ left: chosen[index], right: chosen[index + 1], gap: 240 });
  }
  if (chosen.length < 2) return constraints;
  const leftNodes = force3dReachable(structure, chosen[0]);
  const rightNodes = force3dReachable(structure, chosen[chosen.length - 1]);
  leftNodes.add(chosen[0]);
  rightNodes.add(chosen[chosen.length - 1]);
  const layers = new Map();
  structure.depth.forEach((level, id) => {
    if (!layers.has(level)) layers.set(level, []);
    layers.get(level).push(id);
  });
  layers.forEach((ids) => {
    const left = ids.filter((id) => leftNodes.has(id) && !rightNodes.has(id));
    const right = ids.filter((id) => rightNodes.has(id) && !leftNodes.has(id));
    const shared = ids.filter((id) => leftNodes.has(id) && rightNodes.has(id));
    const ordered = left.concat(shared, right);
    for (let index = 0; index < ordered.length - 1; index += 1) {
      constraints.push({ left: ordered[index], right: ordered[index + 1], gap: 190 });
    }
  });
  return constraints;
}

function force3dBranchColumns(structure) {
  const kids = [...new Set(structure.children.get(structure.root) || [])];
  const columns = [];
  if (kids.length < 2) {
    const chain = [];
    const seen = new Set([structure.root]);
    let id = kids[0] || null;
    while (id && !seen.has(id) && chain.length < 16) {
      seen.add(id);
      chain.push(id);
      id = (structure.children.get(id) || []).find((child) => !seen.has(child)) || null;
    }
    if (chain.length > 1) columns.push([structure.root].concat(chain));
    return columns;
  }
  const reached = new Map(kids.map((id) => {
    const set = force3dReachable(structure, id);
    set.add(id);
    return [id, set];
  }));
  kids.forEach((id) => {
    const own = new Set(reached.get(id));
    kids.forEach((other) => {
      if (other === id) return;
      reached.get(other).forEach((nodeId) => own.delete(nodeId));
    });
    const column = [...own].sort((a, b) => (structure.depth.get(a) || 0) - (structure.depth.get(b) || 0));
    if (column.length > 1) columns.push(column);
  });
  return columns;
}

function force3dFixedAnchors(structure) {
  const kids = [...new Set(structure.children.get(structure.root) || [])];
  const pins = [];
  const used = new Set();
  const pin = (id, x, y) => {
    if (!id || used.has(id)) return;
    used.add(id);
    pins.push({ nodeId: id, position: { x, y } });
  };
  pin(structure.root, 0, -220);
  if (kids.length >= 2) {
    pin(kids[0], -260, 40);
    pin(kids[kids.length - 1], 260, 40);
    return pins;
  }
  const column = force3dBranchColumns(structure)[0] || [];
  const chain = column.filter((id) => id !== structure.root);
  if (chain.length) {
    pin(chain[Math.floor((chain.length - 1) / 2)], 0, 80);
    pin(chain[chain.length - 1], 0, 300);
  }
  return pins;
}

function force3dBuoyPins(structure) {
  const kids = [...new Set(structure.children.get(structure.root) || [])];
  const pins = [{ nodeId: structure.root, position: { x: 0, y: -300 } }];
  kids.forEach((id, index) => {
    const x = (index - (kids.length - 1) / 2) * 340;
    pins.push({ nodeId: id, position: { x, y: 0 } });
  });
  return pins;
}

function force3dVerticalConstraints(data, structure) {
  return data.links
    .filter((link) => (structure.depth.get(link.source) || 0) < (structure.depth.get(link.target) || 0))
    .map((link) => ({ top: link.source, bottom: link.target, gap: 130 }));
}

function force3dDistance(data, originId) {
  const next = new Map(data.nodes.map((node) => [node.id, []]));
  data.links.forEach((link) => {
    next.get(link.source).push(link.target);
    next.get(link.target).push(link.source);
  });
  const dist = new Map();
  if (!originId) return dist;
  const queue = [originId];
  dist.set(originId, 0);
  while (queue.length) {
    const id = queue.shift();
    (next.get(id) || []).forEach((child) => {
      if (dist.has(child)) return;
      dist.set(child, dist.get(id) + 1);
      queue.push(child);
    });
  }
  return dist;
}

function cytoscapeElements(data) {
  const nodes = data.nodes.map((node) => ({
    data: {
      id: node.id,
      name: node.name,
      role: node.role,
      detail: node.detail
    },
    classes: `role-${force3dRoleKey(node.role)}`
  }));
  const edges = data.links.map((link, index) => {
    const shown = force3dDisplayLink(link, data);
    return {
      data: {
        id: `e${index}-${shown.source}-${shown.target}`,
        source: shown.source,
        target: shown.target,
        label: shown.label
      }
    };
  });
  return nodes.concat(edges);
}

function cytoscapeStyles() {
  const nodeStyle = {
    selector: 'node',
    style: {
      shape: 'round-rectangle',
      label: 'data(name)',
      'background-color': FORCE3D_COLORS.narrator,
      color: '#ffffff',
      'font-family': 'Amiri, Tajawal, serif',
      'font-size': 15,
      'font-weight': 700,
      'text-valign': 'center',
      'text-halign': 'center',
      'text-wrap': 'wrap',
      'text-max-width': 150,
      width: 'label',
      height: 'label',
      padding: '12px',
      'border-width': 0,
      'text-outline-width': 0
    }
  };
  const roles = Object.entries(FORCE3D_COLORS).map(([role, color]) => ({
    selector: `node.role-${role}`,
    style: { 'background-color': color }
  }));
  return [nodeStyle].concat(roles, [
    {
      selector: 'edge',
      style: {
        'curve-style': 'bezier',
        width: 2.2,
        'line-color': '#b45309',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#b45309',
        'arrow-scale': 1.15,
        label: 'data(label)',
        'font-family': 'Tajawal, Amiri, sans-serif',
        'font-size': 12,
        color: '#44403c',
        'text-background-color': '#f7f3ec',
        'text-background-opacity': 1,
        'text-background-padding': '3px',
        'text-background-shape': 'roundrectangle'
      }
    },
    {
      selector: 'edge[label = ""]',
      style: {
        label: '',
        'text-background-opacity': 0
      }
    },
    {
      selector: 'edge.taxi',
      style: {
        'curve-style': 'taxi',
        'taxi-direction': 'downward',
        'taxi-turn': 20,
        'taxi-turn-min-distance': 12
      }
    },
    {
      selector: 'node:selected',
      style: { 'border-width': 3, 'border-color': '#1c1917' }
    }
  ]);
}

function force3dFcoseOptions(extra) {
  return Object.assign({
    name: 'fcose',
    quality: 'proof',
    randomize: true,
    animate: false,
    fit: true,
    padding: 42,
    nodeDimensionsIncludeLabels: true,
    uniformNodeDimensions: false,
    packComponents: true,
    nodeSeparation: 110,
    idealEdgeLength: () => 170,
    edgeElasticity: () => 0.4,
    nodeRepulsion: () => 8500,
    gravity: 0.22,
    numIter: 2500,
    tile: true,
    tilingPaddingVertical: 28,
    tilingPaddingHorizontal: 28
  }, extra);
}

function applyFcoseLayout(cy, data, exampleId) {
  const structure = force3dStructure(data);
  const vertical = force3dVerticalConstraints(data, structure);
  const wideVertical = vertical.map((item) => Object.assign({}, item, { gap: 220 }));
  const layers = force3dLayers(structure);
  const columns = force3dBranchColumns(structure);
  const sides = force3dSideConstraints(data, structure);
  const anchors = force3dFixedAnchors(structure);
  const buoys = force3dBuoyPins(structure);
  const options = {};
  if (exampleId === 'fixed' || exampleId === 'sides' || exampleId === 'hybrid') {
    options.fixedNodeConstraint = [{ nodeId: structure.root, position: { x: 0, y: 0 } }];
  }
  if (exampleId === 'lib-sample1') options.fixedNodeConstraint = anchors;
  if (exampleId === 'lib-uwsn') options.fixedNodeConstraint = buoys;
  if (exampleId === 'align' || exampleId === 'hybrid') {
    if (layers.length) options.alignmentConstraint = { horizontal: layers };
  } else if (exampleId === 'lib-callgraph') {
    if (layers.length) options.alignmentConstraint = { horizontal: layers };
  } else if (exampleId === 'lib-sample2' || exampleId === 'lib-sample4' || exampleId === 'lib-uwsn') {
    const spec = {};
    if (layers.length) spec.horizontal = layers;
    if (columns.length) spec.vertical = columns;
    if (spec.horizontal || spec.vertical) options.alignmentConstraint = spec;
  }
  if (exampleId === 'fixed' || exampleId === 'align') options.relativePlacementConstraint = vertical;
  if (exampleId === 'sides' || exampleId === 'hybrid' || exampleId === 'lib-sample3' || exampleId === 'lib-sample4') {
    options.relativePlacementConstraint = vertical.concat(sides);
  }
  if (exampleId === 'lib-callgraph') options.relativePlacementConstraint = vertical;
  if (exampleId === 'lib-uwsn') options.relativePlacementConstraint = wideVertical;
  if (exampleId === 'lib-sample4') options.fixedNodeConstraint = anchors;
  cy.layout(force3dFcoseOptions(options)).run();
  if (exampleId === 'align' || exampleId === 'hybrid' || exampleId === 'lib-callgraph' || exampleId === 'lib-sample2') {
    force3dSnapLayers(cy, data);
  }
}

function force3dSnapLayers(cy, data) {
  const isnad = force3dIsnadGraph(data);
  const groups = new Map();
  data.nodes.forEach((node) => {
    const key = isnad ? force3dIsnadRank(node) : force3dRoleKey(node.role);
    if (key == null) return;
    const bucket = String(key);
    if (!groups.has(bucket)) groups.set(bucket, []);
    groups.get(bucket).push(node.id);
  });
  groups.forEach((ids) => {
    if (ids.length < 2) return;
    const nodes = ids.map((id) => cy.getElementById(id)).filter((node) => node && node.length);
    if (nodes.length < 2) return;
    const ys = nodes.map((node) => node.position('y')).sort((a, b) => a - b);
    const y = ys[Math.floor((ys.length - 1) / 2)];
    nodes.sort((a, b) => a.position('x') - b.position('x'));
    nodes.forEach((node) => node.position({ x: node.position('x'), y }));
    for (let index = 1; index < nodes.length; index += 1) {
      const previous = nodes[index - 1];
      const current = nodes[index];
      const needed = (previous.outerWidth() + current.outerWidth()) / 2 + 36;
      if (current.position('x') - previous.position('x') < needed) {
        current.position({ x: previous.position('x') + needed, y });
      }
    }
  });
}

function applyCytoscapeLayout(cy, data, exampleId) {
  cy.edges().toggleClass('taxi', exampleId === 'taxi');
  if (exampleId === 'fixed' || exampleId === 'align' || exampleId === 'sides' || exampleId === 'hybrid' || exampleId === 'spring' || exampleId.indexOf('lib-') === 0) {
    try {
      applyFcoseLayout(cy, data, exampleId);
      return;
    } catch (err) {
      console.warn('fcose layout error:', err);
    }
  }
  const common = {
    animate: false,
    fit: true,
    padding: 28,
    avoidOverlap: true,
    nodeDimensionsIncludeLabels: true,
    spacingFactor: 1.45
  };
  if (exampleId === 'radial') {
    cy.layout(Object.assign({}, common, {
      name: 'breadthfirst',
      directed: true,
      circle: true,
      spacingFactor: 1.65
    })).run();
    return;
  }
  if (exampleId === 'madar') {
    const dist = force3dDistance(data, force3dMadarId(data));
    cy.layout({
      name: 'concentric',
      fit: true,
      padding: 28,
      avoidOverlap: true,
      nodeDimensionsIncludeLabels: true,
      minNodeSpacing: 36,
      spacingFactor: 1.35,
      concentric: (node) => 80 - (dist.has(node.id()) ? dist.get(node.id()) : 6) * 16,
      levelWidth: () => 16
    }).run();
    return;
  }
  cy.layout(Object.assign({}, common, {
    name: 'breadthfirst',
    directed: true,
    circle: false,
    grid: exampleId === 'taxi',
    spacingFactor: exampleId === 'taxi' ? 1.25 : 1.5
  })).run();
}

function mountCytoscape(wrapper, data, exampleId) {
  const stage = wrapper.querySelector('.force3d-stage');
  const detail = wrapper.querySelector('.force3d-detail');
  const example = force3dExample(exampleId || 'tree');
  if (wrapper._cy) {
    try { wrapper._cy.destroy(); } catch (e) {}
    wrapper._cy = null;
  }
  stage.innerHTML = '';
  const cy = window.cytoscape({
    container: stage,
    elements: cytoscapeElements(data),
    style: cytoscapeStyles(),
    wheelSensitivity: 0.25,
    minZoom: 0.2,
    maxZoom: 3
  });
  wrapper._cy = cy;
  wrapper._forceData = data;
  wrapper._libraryMode = false;
  wrapper._example = example.id;
  cy.on('tap', 'node', (event) => {
    const node = event.target;
    if (!detail) return;
    detail.textContent = [node.data('name'), node.data('role'), node.data('detail')].filter(Boolean).join(' — ');
  });
  applyCytoscapeLayout(cy, data, example.id);
  if (detail) detail.textContent = `${example.note} الوصلات: ${data.links.length}.`;
  const select = wrapper.querySelector('[data-force3d-example]');
  if (select) select.value = example.id;
  rememberForce3dPositions(wrapper);
  applyForce3dBackground(wrapper);
  requestAnimationFrame(() => {
    if (!stage.isConnected) return;
    cy.resize();
    cy.fit(undefined, 28);
  });
}

function renderForce3dBlocks(container) {
  if (!container) return;
  const blocks = [];
  container.querySelectorAll('pre code').forEach((codeEl) => {
    const pre = codeEl.closest('pre');
    if (!pre || pre.dataset.renderedForce3d === '1' || !isForce3dCode(codeEl)) return;
    blocks.push({ pre, raw: codeEl.textContent || '' });
  });
  if (!blocks.length) return;
  const ready = (document.fonts && document.fonts.load)
    ? document.fonts.load('700 16px Amiri').catch(() => {}).then(() => ensureCytoscape())
    : ensureCytoscape();
  ready.then(() => {
    blocks.forEach(({ pre, raw }) => {
      if (!pre.isConnected || pre.dataset.renderedForce3d === '1') return;
      let data = null;
      try { data = parseForce3dBlock(raw); } catch (e) { data = null; }
      pre.dataset.renderedForce3d = '1';
      const wrapper = document.createElement('div');
      wrapper.className = 'force3d-render-wrapper isnad-render-wrapper';
      const title = data ? data.title : 'مشجر الإسناد';
      wrapper.innerHTML = `
        <div class="isnad-render-header">
          <div class="isnad-render-title">
            <span>🌳</span>
            <span>${force3dEscape(title)}</span>
          </div>
          <div class="force3d-tools">
            <label class="force3d-example-label">
              <span>المثال</span>
              <select data-force3d-example dir="rtl">
                ${force3dExampleOptions('tree')}
              </select>
            </label>
            <label class="force3d-example-label">
              <span>الخط</span>
              <select data-force3d-font dir="rtl">
                ${FORCE3D_FONTS.map(([name, label]) => `<option value="${force3dEscape(name)}"${name === 'Amiri' ? ' selected' : ''}>${force3dEscape(label)}</option>`).join('')}
              </select>
            </label>
            <label class="force3d-example-label">
              <span>الحجم</span>
              <select data-force3d-size dir="rtl">
                ${[12, 14, 16, 18, 20, 24, 28, 32].map((size) => `<option value="${size}"${size === 16 ? ' selected' : ''}>${size}</option>`).join('')}
              </select>
            </label>
            <label class="force3d-example-label">
              <span>المقاس</span>
              <select data-force3d-weight dir="rtl">
                <option value="300">نحيف</option>
                <option value="400">عادي</option>
                <option value="500">متوسط</option>
                <option value="700" selected>عريض</option>
                <option value="800">ثقيل</option>
              </select>
            </label>
            <label class="force3d-example-label">
              <span>الخلفية</span>
              <select data-force3d-bg dir="rtl">
                ${FORCE3D_BACKGROUNDS.map(([color, label]) => `<option value="${color}" style="background:${color}"${color === '#f7f3ec' ? ' selected' : ''}>${force3dEscape(label)}</option>`).join('')}
              </select>
            </label>
            <button type="button" class="btn-chart-type" data-force3d-fit="1">ملاءمة</button>
            <button type="button" class="btn-chart-type" data-force3d-reset="1">إعادة</button>
            <button type="button" class="btn-chart-type force3d-shot" data-force3d-shot="1" title="لقطة للمشجر">
              <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M9.2 4.5 10.6 6h2.8l1.4-1.5H17a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-11a2 2 0 0 1 2-2h2.2ZM12 8.2A3.8 3.8 0 1 0 15.8 12 3.8 3.8 0 0 0 12 8.2Zm0 1.6A2.2 2.2 0 1 1 9.8 12 2.2 2.2 0 0 1 12 9.8Z"/></svg>
              <span>لقطة</span>
            </button>
            <button type="button" class="btn-chart-type" data-force3d-expand="1">تكبير</button>
            <button type="button" class="btn-chart-type force3d-close" data-force3d-close="1">إغلاق</button>
            <button type="button" class="btn-chart-type" data-force3d-code="1">الكود</button>
          </div>
        </div>
        <div class="force3d-stage"></div>
        <div class="force3d-detail"></div>
        <div class="force3d-code" hidden></div>
      `;
      pre.parentNode.insertBefore(wrapper, pre);
      wrapper.querySelector('.force3d-code').appendChild(pre);
      if (!data || !window.cytoscape) {
        const detail = wrapper.querySelector('.force3d-detail');
        if (detail) detail.textContent = 'تعذر رسم هذه الكتلة. تحقق أن JSON يحوي عقدتين ووصلة واحدة على الأقل.';
        return;
      }
      try {
        mountCytoscape(wrapper, data, 'tree');
      } catch (err) {
        console.warn('cytoscape render error:', err);
        const detail = wrapper.querySelector('.force3d-detail');
        if (detail) detail.textContent = 'تعذر تشغيل مشجر Cytoscape في هذه الصفحة.';
      }
    });
  }).catch((err) => {
    console.warn('cytoscape library load error:', err);
  });
}

function onForce3dExampleChange(event) {
  const select = event.target.closest('[data-force3d-example]');
  if (!select) return;
  const wrapper = select.closest('.force3d-render-wrapper');
  if (!wrapper || !wrapper._forceData) return;
  const example = force3dExample(select.value);
  wrapper._example = example.id;
  const detail = wrapper.querySelector('.force3d-detail');
  if (wrapper._libraryMode || !wrapper._cy) {
    mountCytoscape(wrapper, wrapper._forceData, example.id);
    return;
  }
  applyCytoscapeLayout(wrapper._cy, wrapper._forceData, example.id);
  if (detail) detail.textContent = `${example.note} الوصلات: ${wrapper._forceData.links.length}.`;
  rememberForce3dPositions(wrapper);
  applyForce3dType(wrapper).then(() => {
    if (!wrapper._cy) return;
    wrapper._cy.resize();
    wrapper._cy.fit(undefined, 28);
  });
}

function rememberForce3dPositions(wrapper) {
  const cy = wrapper && wrapper._cy;
  if (!cy) return;
  const positions = {};
  cy.nodes().forEach((node) => {
    const point = node.position();
    positions[node.id()] = { x: point.x, y: point.y };
  });
  wrapper._homePositions = positions;
}

function restoreForce3dPositions(wrapper) {
  const cy = wrapper && wrapper._cy;
  const positions = wrapper && wrapper._homePositions;
  if (!cy || !positions) return;
  cy.nodes().forEach((node) => {
    const point = positions[node.id()];
    if (point) node.position(point);
  });
  cy.resize();
  cy.fit(undefined, 28);
}

function graphFontWeights(name) {
  const limited = {
    Amiri: '400;700',
    'Aref Ruqaa': '400;700',
    Almarai: '300;400;700;800',
    'Scheherazade New': '400;700',
    Harmattan: '400;700',
    'Markazi Text': '400;500;600;700',
    'El Messiri': '400;500;600;700',
    'Reem Kufi': '400;500;600;700',
    Mirza: '400;500;600;700',
    Lemonada: '300;400;500;600;700',
    'IBM Plex Sans Arabic': '300;400;500;600;700',
    'Readex Pro': '300;400;500;600;700',
    'Noto Naskh Arabic': '400;500;600;700',
    Lateef: '300;400;500;700;800'
  };
  return limited[name] || '300;400;500;700;800';
}

function ensureGraphFont(name) {
  const id = `force3d-font-${name.replace(/\s+/g, '-')}`;
  if (!document.getElementById(id)) {
    const link = document.createElement('link');
    link.id = id;
    link.rel = 'stylesheet';
    link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(name)}:wght@${graphFontWeights(name)}&display=swap`;
    document.head.appendChild(link);
  }
  const spec = `400 16px "${name}"`;
  return (document.fonts && document.fonts.load) ? document.fonts.load(spec).catch(() => {}) : Promise.resolve();
}

function force3dInk(color) {
  const hex = String(color || '').replace('#', '');
  if (hex.length < 6) return '#44403c';
  const red = parseInt(hex.slice(0, 2), 16);
  const green = parseInt(hex.slice(2, 4), 16);
  const blue = parseInt(hex.slice(4, 6), 16);
  const light = (0.299 * red + 0.587 * green + 0.114 * blue) / 255;
  return light > 0.62 ? '#44403c' : '#f5f5f4';
}

function applyForce3dBackground(wrapper) {
  if (!wrapper) return;
  const select = wrapper.querySelector('[data-force3d-bg]');
  const color = (select && select.value) || '#f7f3ec';
  const ink = force3dInk(color);
  wrapper._bg = color;
  const stage = wrapper.querySelector('.force3d-stage');
  if (stage) stage.style.background = color;
  if (select) {
    select.style.background = color;
    select.style.color = ink;
  }
  const cy = wrapper._cy;
  if (!cy) return;
  cy.style().selector('edge').style({
    'text-background-color': color,
    color: ink
  }).update();
}

function applyForce3dType(wrapper) {
  const cy = wrapper && wrapper._cy;
  if (!cy) return Promise.resolve();
  const font = wrapper.querySelector('[data-force3d-font]');
  const sizeEl = wrapper.querySelector('[data-force3d-size]');
  const weightEl = wrapper.querySelector('[data-force3d-weight]');
  const family = font ? font.value : 'Amiri';
  const size = Number(sizeEl && sizeEl.value) || 16;
  const weight = Number(weightEl && weightEl.value) || 700;
  return ensureGraphFont(family).then(() => {
    if (!wrapper.isConnected || wrapper._cy !== cy) return;
    cy.style()
      .selector('node')
      .style({ 'font-family': `"${family}", Amiri, serif`, 'font-size': size, 'font-weight': weight })
      .selector('edge')
      .style({ 'font-family': `"${family}", Amiri, serif`, 'font-size': Math.max(11, size - 3), 'font-weight': weight })
      .update();
  });
}

function downloadForce3dShot(wrapper) {
  const cy = wrapper && wrapper._cy;
  if (!cy) return;
  const titleNode = wrapper.querySelector('.isnad-render-title span:last-child');
  const title = (titleNode && titleNode.textContent || 'مشجر').trim() || 'مشجر';
  const shot = cy.png({ output: 'blob-promise', bg: wrapper._bg || '#f7f3ec', full: true, scale: 2 });
  Promise.resolve(shot).then((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${title}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }).catch((err) => console.warn('graph shot error:', err));
}

function setForce3dExpanded(wrapper, expanded) {
  const cy = wrapper._cy;
  const stage = wrapper.querySelector('.force3d-stage');
  if (expanded) {
    if (!wrapper.classList.contains('is-expanded')) {
      wrapper._homeParent = wrapper.parentNode;
      wrapper._homeNext = wrapper.nextSibling;
      document.body.appendChild(wrapper);
    }
    wrapper.classList.add('is-expanded');
  } else {
    wrapper.classList.remove('is-expanded');
    if (wrapper._homeParent) wrapper._homeParent.insertBefore(wrapper, wrapper._homeNext);
  }
  requestAnimationFrame(() => {
    if (!cy || !stage || !stage.isConnected) return;
    cy.resize();
    cy.fit(undefined, 28);
  });
}

function onForce3dStyleChange(event) {
  const control = event.target.closest('[data-force3d-font], [data-force3d-size], [data-force3d-weight], [data-force3d-bg]');
  if (!control) return;
  const wrapper = control.closest('.force3d-render-wrapper');
  if (!wrapper) return;
  if (control.matches('[data-force3d-bg]')) {
    applyForce3dBackground(wrapper);
    return;
  }
  applyForce3dType(wrapper);
}

function onForce3dClick(event) {
  const button = event.target.closest('[data-force3d-fit], [data-force3d-expand], [data-force3d-close], [data-force3d-code], [data-force3d-reset], [data-force3d-shot]');
  if (!button) return;
  const wrapper = button.closest('.force3d-render-wrapper');
  if (!wrapper) return;
  event.preventDefault();
  const cy = wrapper._cy;
  if (button.dataset.force3dFit && cy) {
    cy.resize();
    cy.fit(undefined, 28);
    return;
  }
  if (button.dataset.force3dReset) {
    restoreForce3dPositions(wrapper);
    return;
  }
  if (button.dataset.force3dShot) {
    downloadForce3dShot(wrapper);
    return;
  }
  if (button.dataset.force3dExpand) {
    setForce3dExpanded(wrapper, !wrapper.classList.contains('is-expanded'));
    return;
  }
  if (button.dataset.force3dClose) {
    setForce3dExpanded(wrapper, false);
    return;
  }
  if (button.dataset.force3dCode) {
    const box = wrapper.querySelector('.force3d-code');
    if (box) box.hidden = !box.hidden;
  }
}

if (!window._force3dClicksBound) {
  window._force3dClicksBound = true;
  document.addEventListener('click', onForce3dClick);
  document.addEventListener('change', (event) => {
    onForce3dExampleChange(event);
    onForce3dStyleChange(event);
  });
}

window.renderForce3dBlocks = renderForce3dBlocks;
window.parseForce3dBlock = parseForce3dBlock;
