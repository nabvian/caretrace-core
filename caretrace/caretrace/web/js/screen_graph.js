/* Evidence graph.

   A force-directed layout drawn on a canvas. Implemented directly rather than
   pulled from a graph library so the whole frontend stays dependency-free and
   runs offline from a file:// URL — a hard requirement for the packaged build.
   Canvas also keeps ~80 nodes and ~140 edges interactive at 60fps, which an
   SVG-per-node approach does not. */

const NODE_STYLE = {
  document:   { fill: '#12566f', stroke: '#0d3b52', label: 'Document', r: 11 },
  fact:       { fill: '#1c88a6', stroke: '#12566f', label: 'Fact', r: 8 },
  claim:      { fill: '#a8620a', stroke: '#7a4a08', label: 'Claim', r: 9 },
  medication: { fill: '#1d7a52', stroke: '#14573a', label: 'Medication', r: 9 },
  event:      { fill: '#6b46a8', stroke: '#4e3280', label: 'Event', r: 8 },
  // An absence, so it is drawn hollow: a dashed outline with no fill reads as
  // "expected here, not found" rather than as another piece of evidence.
  absent_evidence: { fill: '#ffffff', stroke: '#b3261e', label: 'Evidence not located',
                     r: 9, hollow: true },
};

const EDGE_STYLE = {
  CONTAINS:     { color: '#c3ccd5', width: 1,   dash: [],     label: 'Contains' },
  SUPPORTS:     { color: '#1d7a52', width: 1.6, dash: [],     label: 'Supports' },
  CONTRADICTS:  { color: '#b3261e', width: 2.4, dash: [],     label: 'Contradicts' },
  DUPLICATES:   { color: '#93a0ac', width: 1.4, dash: [3, 3], label: 'Duplicates' },
  CHANGED_FROM: { color: '#a8620a', width: 1.4, dash: [5, 3], label: 'Changed from' },
  CHANGED_TO:   { color: '#a8620a', width: 1.4, dash: [5, 3], label: 'Changed to' },
  MENTIONS:     { color: '#c3ccd5', width: 1,   dash: [2, 3], label: 'Mentions' },
  MISSING_SUPPORT: { color: '#6b46a8', width: 1.8, dash: [6, 3], label: 'Missing support' },
  REFERENCES:   { color: '#93a0ac', width: 1.2, dash: [4, 2], label: 'References' },
  SUPERSEDES:   { color: '#4d5b6a', width: 1.4, dash: [],     label: 'Supersedes' },
};
const edgeStyle = t => EDGE_STYLE[t] || { color: '#c3ccd5', width: 1, dash: [], label: titleCase(t) };

Router.register('graph', (root) => requireCase(root, async (root) => {
  const data = await State.view('graph');

  const nodeTypes = [...new Set(data.nodes.map(n => n.type))];
  const edgeTypes = [...new Set(data.edges.map(e => e.rel_type))];
  const activeNodes = new Set(nodeTypes);
  // Structural containment edges are dense and drown the semantic ones; the
  // interesting relationships are on by default and CONTAINS is opt-in.
  const activeEdges = new Set(edgeTypes.filter(t => t !== 'CONTAINS'));

  const canvas = el('canvas', { id: 'graph-canvas' });
  const panel = el('div', { class: 'node-panel hidden' });
  const controls = el('div', { class: 'graph-controls' });
  const wrap = el('div', { class: 'graph-wrap' }, canvas, controls, panel,
    el('div', { class: 'graph-zoom' },
      el('button', { class: 'btn sm', onclick: () => zoomBy(1.25), title: 'Zoom in' }, '+'),
      el('button', { class: 'btn sm', onclick: () => zoomBy(0.8), title: 'Zoom out' }, '\u2212'),
      el('button', { class: 'btn sm', onclick: () => fit() }, 'Fit')),
    el('div', { class: 'graph-hint' }, 'Drag to pan \u00B7 scroll to zoom \u00B7 click a node'));

  // ---- simulation state -------------------------------------------------
  const N = data.nodes.map((n, i) => ({
    ...n,
    x: Math.cos(i * 2.399) * (60 + i * 4.2),
    y: Math.sin(i * 2.399) * (60 + i * 4.2),
    vx: 0, vy: 0,
  }));
  const byId = new Map(N.map(n => [n.id, n]));
  const E = data.edges
    .map(e => ({ ...e, s: byId.get(e.source), t: byId.get(e.target) }))
    .filter(e => e.s && e.t);

  let view = { k: 1, x: 0, y: 0 };
  let selected = null, hovered = null;
  let alpha = 1;

  const visibleNode = n => activeNodes.has(n.type);
  const visibleEdge = e => activeEdges.has(e.rel_type) && visibleNode(e.s) && visibleNode(e.t);

  function step() {
    if (alpha < 0.002) return;
    alpha *= 0.985;
    const nodes = N.filter(visibleNode);
    // Repulsion (all pairs — n is small enough that this is exact and stable).
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        let d2 = dx * dx + dy * dy;
        if (d2 < 1) { dx = (Math.random() - 0.5); dy = (Math.random() - 0.5); d2 = 1; }
        const f = 2600 / d2;
        const d = Math.sqrt(d2);
        const fx = (dx / d) * f, fy = (dy / d) * f;
        a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
      }
    }
    // Springs.
    for (const e of E) {
      if (!visibleEdge(e)) continue;
      const rest = e.rel_type === 'CONTAINS' ? 74 : 108;
      const dx = e.t.x - e.s.x, dy = e.t.y - e.s.y;
      const d = Math.hypot(dx, dy) || 1;
      const f = (d - rest) * 0.012;
      const fx = (dx / d) * f, fy = (dy / d) * f;
      e.s.vx += fx; e.s.vy += fy; e.t.vx -= fx; e.t.vy -= fy;
    }
    // Centring + integration.
    for (const n of nodes) {
      n.vx -= n.x * 0.0022; n.vy -= n.y * 0.0022;
      n.vx *= 0.86; n.vy *= 0.86;
      n.x += n.vx * alpha * 2.4; n.y += n.vy * alpha * 2.4;
    }
  }

  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, dpr = window.devicePixelRatio || 1;

  function resize() {
    const r = wrap.getBoundingClientRect();
    W = r.width; H = r.height;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    ctx.translate(W / 2 + view.x, H / 2 + view.y);
    ctx.scale(view.k, view.k);

    const neighbours = new Set();
    if (selected) {
      neighbours.add(selected.id);
      for (const e of E) {
        if (!visibleEdge(e)) continue;
        if (e.s.id === selected.id) neighbours.add(e.t.id);
        if (e.t.id === selected.id) neighbours.add(e.s.id);
      }
    }

    for (const e of E) {
      if (!visibleEdge(e)) continue;
      const st = edgeStyle(e.rel_type);
      const dim = selected && !(neighbours.has(e.s.id) && neighbours.has(e.t.id));
      ctx.globalAlpha = dim ? 0.1 : 0.85;
      ctx.strokeStyle = st.color;
      ctx.lineWidth = st.width / Math.max(view.k, 0.6);
      ctx.setLineDash(st.dash.map(d => d / Math.max(view.k, 0.6)));
      ctx.beginPath();
      ctx.moveTo(e.s.x, e.s.y);
      ctx.lineTo(e.t.x, e.t.y);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    for (const n of N) {
      if (!visibleNode(n)) continue;
      const s = NODE_STYLE[n.type] || NODE_STYLE.fact;
      const dim = selected && !neighbours.has(n.id);
      ctx.globalAlpha = dim ? 0.16 : 1;
      const isFocus = selected?.id === n.id || hovered?.id === n.id;
      ctx.beginPath();
      ctx.arc(n.x, n.y, s.r + (isFocus ? 3 : 0), 0, Math.PI * 2);
      ctx.fillStyle = s.fill;
      ctx.fill();
      ctx.lineWidth = (isFocus ? 3 : 1.5) / Math.max(view.k, 0.6);
      ctx.strokeStyle = isFocus ? '#0f1720' : s.stroke;
      if (s.hollow) ctx.setLineDash([3 / Math.max(view.k, 0.6), 2 / Math.max(view.k, 0.6)]);
      ctx.stroke();
      ctx.setLineDash([]);

      if (view.k > 0.72 && !dim) {
        ctx.globalAlpha = 1;
        ctx.fillStyle = '#33414f';
        ctx.font = `${11 / Math.max(view.k, 0.85)}px ui-monospace, monospace`;
        ctx.textAlign = 'center';
        const short = n.label.length > 22 ? n.label.slice(0, 21) + '\u2026' : n.label;
        ctx.fillText(short, n.x, n.y + s.r + 12 / Math.max(view.k, 0.85));
      }
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  let raf;
  function loop() { step(); draw(); raf = requestAnimationFrame(loop); }

  function toWorld(cx, cy) {
    const r = canvas.getBoundingClientRect();
    return {
      x: (cx - r.left - W / 2 - view.x) / view.k,
      y: (cy - r.top - H / 2 - view.y) / view.k,
    };
  }
  function pick(cx, cy) {
    const p = toWorld(cx, cy);
    let best = null, bd = 1e9;
    for (const n of N) {
      if (!visibleNode(n)) continue;
      const s = NODE_STYLE[n.type] || NODE_STYLE.fact;
      const d = Math.hypot(n.x - p.x, n.y - p.y);
      if (d < s.r + 6 && d < bd) { bd = d; best = n; }
    }
    return best;
  }
  function zoomBy(f) { view.k = Math.max(0.22, Math.min(4, view.k * f)); }
  function fit() {
    const vis = N.filter(visibleNode);
    if (!vis.length) return;
    const xs = vis.map(n => n.x), ys = vis.map(n => n.y);
    const w = Math.max(...xs) - Math.min(...xs) + 120;
    const h = Math.max(...ys) - Math.min(...ys) + 120;
    view.k = Math.max(0.22, Math.min(2.4, Math.min(W / w, H / h)));
    view.x = -((Math.max(...xs) + Math.min(...xs)) / 2) * view.k;
    view.y = -((Math.max(...ys) + Math.min(...ys)) / 2) * view.k;
  }

  // ---- interaction ------------------------------------------------------
  let drag = null;
  canvas.addEventListener('mousedown', (ev) => {
    const hit = pick(ev.clientX, ev.clientY);
    drag = hit
      ? { node: hit, kind: 'node' }
      : { kind: 'pan', x: ev.clientX - view.x, y: ev.clientY - view.y };
  });
  window.addEventListener('mousemove', (ev) => {
    if (drag?.kind === 'pan') { view.x = ev.clientX - drag.x; view.y = ev.clientY - drag.y; }
    else if (drag?.kind === 'node') {
      const p = toWorld(ev.clientX, ev.clientY);
      drag.node.x = p.x; drag.node.y = p.y; drag.node.vx = 0; drag.node.vy = 0;
      drag.moved = true; alpha = Math.max(alpha, 0.25);
    } else {
      const h = pick(ev.clientX, ev.clientY);
      if (h !== hovered) { hovered = h; canvas.style.cursor = h ? 'pointer' : 'grab'; }
    }
  });
  window.addEventListener('mouseup', (ev) => {
    if (drag?.kind === 'node' && !drag.moved) select(drag.node);
    else if (drag?.kind === 'pan') {
      const hit = pick(ev.clientX, ev.clientY);
      if (!hit && Math.abs(ev.clientX - drag.x - view.x) < 3) select(null);
    }
    drag = null;
  });
  canvas.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    zoomBy(ev.deltaY < 0 ? 1.11 : 0.9);
  }, { passive: false });

  function select(n) {
    selected = n;
    if (!n) { panel.classList.add('hidden'); return; }
    const links = E.filter(e => visibleEdge(e) && (e.s.id === n.id || e.t.id === n.id));
    panel.classList.remove('hidden');
    panel.replaceChildren(
      el('div', { class: 'card-head' },
        el('div', {},
          el('div', { class: 'tiny upper muted' }, NODE_STYLE[n.type]?.label || n.type),
          el('h3', { style: 'font-size:13.5px' }, n.label)),
        el('div', { style: 'flex:1' }),
        el('button', { class: 'btn sm ghost', onclick: () => select(null) }, '\u2715')),
      el('div', { class: 'card-body' },
        el('dl', { class: 'kv', style: 'grid-template-columns:88px 1fr' },
          el('dt', {}, 'ID'), el('dd', { class: 'mono' }, n.display_id || n.id.slice(0, 8)),
          n.detail ? el('dt', {}, 'Detail') : null,
          n.detail ? el('dd', {}, n.detail) : null,
          n.date ? el('dt', {}, 'Date') : null,
          n.date ? el('dd', {}, fmtDate(n.date)) : null),
        n.provenance
          ? el('div', { style: 'margin-top:10px' }, prov(n.provenance))
          : el('div', { class: 'tiny muted', style: 'margin-top:10px' },
              'This node is a document; open it from the Documents screen.'),
        n.provenance
          ? el('div', { class: 'source-quote' }, n.provenance.source_text)
          : null,
        el('div', { class: 'tiny upper muted', style: 'margin:14px 0 5px' },
          `${links.length} relationship${links.length === 1 ? '' : 's'}`),
        el('div', { class: 'stack', style: 'gap:4px' },
          ...links.slice(0, 14).map(e => {
            const other = e.s.id === n.id ? e.t : e.s;
            const st = edgeStyle(e.rel_type);
            return el('button', {
              class: 'row', style: 'gap:7px;background:none;border:none;padding:3px 0;cursor:pointer;text-align:left;width:100%',
              onclick: () => select(other),
            },
              el('span', { class: 'tiny strong', style: `color:${st.color};min-width:88px` },
                st.label.toUpperCase()),
              el('span', { class: 'small', style: 'flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' },
                other.label));
          }))));
  }

  // ---- legend / filters -------------------------------------------------
  controls.append(el('div', { class: 'gc-h' }, 'Nodes'));
  for (const t of nodeTypes) {
    const s = NODE_STYLE[t] || NODE_STYLE.fact;
    const cb = el('input', { type: 'checkbox', checked: true, onchange: (e) => {
      e.target.checked ? activeNodes.add(t) : activeNodes.delete(t);
      alpha = Math.max(alpha, 0.4); if (selected && !activeNodes.has(selected.type)) select(null);
    } });
    controls.append(el('label', {}, cb,
      el('span', { class: 'sw', style: `background:${s.fill}` }),
      el('span', {}, s.label || titleCase(t)),
      el('span', { class: 'graph-legend-count' }, data.nodes.filter(n => n.type === t).length)));
  }
  controls.append(el('div', { class: 'gc-h' }, 'Relationships'));
  for (const t of edgeTypes) {
    const s = edgeStyle(t);
    const cb = el('input', { type: 'checkbox', checked: activeEdges.has(t), onchange: (e) => {
      e.target.checked ? activeEdges.add(t) : activeEdges.delete(t);
      alpha = Math.max(alpha, 0.3);
    } });
    controls.append(el('label', {}, cb,
      el('span', { class: 'ln', style: `border-top:2px ${s.dash.length ? 'dashed' : 'solid'} ${s.color}` }),
      el('span', {}, s.label),
      el('span', { class: 'graph-legend-count' }, data.edges.filter(e => e.rel_type === t).length)));
  }

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Evidence graph',
      `${data.nodes.length} nodes \u00B7 ${data.edges.length} relationships. `
      + 'Red edges are contradictions; click any node to see its sources.',
      [el('button', { class: 'btn', onclick: () => {
        activeEdges.clear(); ['CONTRADICTS', 'MISSING_SUPPORT'].forEach(t => {
          if (edgeTypes.includes(t)) activeEdges.add(t);
        });
        $$('.graph-controls input').forEach((cb, i) => {
          const t = [...nodeTypes, ...edgeTypes][i];
          if (edgeTypes.includes(t) && i >= nodeTypes.length) cb.checked = activeEdges.has(t);
        });
        alpha = 0.6;
      } }, 'Show contradictions only')]),
    wrap)));

  resize();
  fit();
  loop();

  const ro = new ResizeObserver(() => { resize(); });
  ro.observe(wrap);
  // Stop the animation loop when the user navigates away.
  window.addEventListener('hashchange', function stop() {
    cancelAnimationFrame(raf); ro.disconnect();
    window.removeEventListener('hashchange', stop);
  });
  setTimeout(fit, 1400);
}));
