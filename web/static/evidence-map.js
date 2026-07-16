/* Evidence map: a tiny Obsidian-style graph.
 * - Force-directed layout (repulsion + edge springs + centering), computed
 *   client-side and run for a short settle budget rather than forever.
 * - Node radius scales with degree (more co-citations = bigger node).
 * - Nodes are draggable; dragging wakes the simulation so others react.
 * - Hovering (or clicking, for touch) a node/marker/reference highlights
 *   that paper's direct neighborhood and dims everything else.
 */

const SVG_NS = "http://www.w3.org/2000/svg";
const WIDTH = 300;
const HEIGHT = 300;
const MAX_SETTLE_FRAMES = 240; // ~4s at 60fps

function buildEvidenceGraph(root) {
  const dataEl = root.querySelector(".evidence-graph-data");
  const svg = root.querySelector(".evidence-svg");
  if (!dataEl || !svg) return null;

  const graph = JSON.parse(dataEl.textContent);
  if (!graph.nodes || graph.nodes.length < 2) return null;

  const degree = {};
  graph.nodes.forEach(function (n) {
    degree[n.citation_number] = 0;
  });
  graph.edges.forEach(function (e) {
    degree[e.a] = (degree[e.a] || 0) + 1;
    degree[e.b] = (degree[e.b] || 0) + 1;
  });

  const physics = graph.nodes.map(function (n, i) {
    const angle = (2 * Math.PI * i) / graph.nodes.length;
    return {
      n: n.citation_number,
      x: WIDTH / 2 + 50 * Math.cos(angle) + (Math.random() - 0.5) * 10,
      y: HEIGHT / 2 + 50 * Math.sin(angle) + (Math.random() - 0.5) * 10,
      vx: 0,
      vy: 0,
      r: Math.min(26, 13 + (degree[n.citation_number] || 0) * 3),
      fixed: false,
    };
  });
  const byNumber = {};
  physics.forEach(function (p) {
    byNumber[p.n] = p;
  });

  const edgeEls = graph.edges.map(function (e) {
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("class", "evidence-edge");
    svg.appendChild(line);
    return { e: e, el: line };
  });

  const nodeEls = physics.map(function (p) {
    const g = document.createElementNS(SVG_NS, "g");
    g.setAttribute("class", "evidence-node");
    g.dataset.node = p.n;

    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("r", p.r);
    g.appendChild(circle);

    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("dy", "0.35em");
    text.textContent = p.n;
    g.appendChild(text);

    svg.appendChild(g);
    return { p: p, el: g };
  });

  function render() {
    nodeEls.forEach(function (item) {
      const circle = item.el.querySelector("circle");
      const text = item.el.querySelector("text");
      circle.setAttribute("cx", item.p.x);
      circle.setAttribute("cy", item.p.y);
      text.setAttribute("x", item.p.x);
      text.setAttribute("y", item.p.y);
    });
    edgeEls.forEach(function (item) {
      const a = byNumber[item.e.a];
      const b = byNumber[item.e.b];
      item.el.setAttribute("x1", a.x);
      item.el.setAttribute("y1", a.y);
      item.el.setAttribute("x2", b.x);
      item.el.setAttribute("y2", b.y);
    });
  }

  function step() {
    for (let i = 0; i < physics.length; i++) {
      for (let j = i + 1; j < physics.length; j++) {
        const a = physics[i];
        const b = physics[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const distSq = Math.max(1, dx * dx + dy * dy);
        const dist = Math.sqrt(distSq);
        const force = 900 / distSq;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        if (!a.fixed) {
          a.vx += fx;
          a.vy += fy;
        }
        if (!b.fixed) {
          b.vx -= fx;
          b.vy -= fy;
        }
      }
    }

    graph.edges.forEach(function (e) {
      const a = byNumber[e.a];
      const b = byNumber[e.b];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const force = (dist - 90) * 0.02;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      if (!a.fixed) {
        a.vx += fx;
        a.vy += fy;
      }
      if (!b.fixed) {
        b.vx -= fx;
        b.vy -= fy;
      }
    });

    let moving = false;
    physics.forEach(function (p) {
      if (p.fixed) return;
      p.vx += (WIDTH / 2 - p.x) * 0.002;
      p.vy += (HEIGHT / 2 - p.y) * 0.002;
      p.vx *= 0.85;
      p.vy *= 0.85;
      p.x += p.vx;
      p.y += p.vy;
      const margin = p.r + 4;
      p.x = Math.max(margin, Math.min(WIDTH - margin, p.x));
      p.y = Math.max(margin, Math.min(HEIGHT - margin, p.y));
      if (Math.abs(p.vx) > 0.05 || Math.abs(p.vy) > 0.05) moving = true;
    });

    render();
    return moving;
  }

  let rafId = null;
  let frameCount = 0;

  function loop() {
    const moving = step();
    frameCount++;
    const anyFixed = physics.some(function (p) {
      return p.fixed;
    });
    if (anyFixed || (moving && frameCount < MAX_SETTLE_FRAMES)) {
      rafId = requestAnimationFrame(loop);
    } else {
      rafId = null;
    }
  }

  function wake() {
    frameCount = 0;
    if (!rafId) rafId = requestAnimationFrame(loop);
  }

  wake();

  // Mouse + touch (not Pointer Events) for dragging: broader compatibility
  // across browsers/input sources, and listening on window for move/up
  // means a fast drag that leaves the SVG's bounds still tracks correctly
  // without needing pointer capture.
  let dragging = null;

  function clientXY(evt) {
    if (evt.touches && evt.touches.length) {
      return { x: evt.touches[0].clientX, y: evt.touches[0].clientY };
    }
    return { x: evt.clientX, y: evt.clientY };
  }

  function toSvgPoint(clientX, clientY) {
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    return {
      x: ((clientX - rect.left) / rect.width) * WIDTH,
      y: ((clientY - rect.top) / rect.height) * HEIGHT,
    };
  }

  // A real mouse/trackpad click routinely fires at least one mousemove
  // between mousedown and mouseup even with no perceptible movement (hand
  // tremor, coalesced events, etc.) - only counting it as an actual drag
  // once the pointer has moved past this threshold keeps a plain click from
  // being silently swallowed as a "drag" and having its selection toggle
  // suppressed below.
  const DRAG_THRESHOLD = 3;

  nodeEls.forEach(function (item) {
    function onDown(evt) {
      dragging = item.p;
      dragging.fixed = true;
      dragging.moved = false;
      const xy = clientXY(evt);
      const pt = toSvgPoint(xy.x, xy.y);
      dragging.dragStartX = pt ? pt.x : item.p.x;
      dragging.dragStartY = pt ? pt.y : item.p.y;
      wake();
      evt.preventDefault();
    }
    item.el.addEventListener("mousedown", onDown);
    item.el.addEventListener("touchstart", onDown, { passive: false });
  });

  function onMove(evt) {
    if (!dragging) return;
    const xy = clientXY(evt);
    const pt = toSvgPoint(xy.x, xy.y);
    if (!pt) return;
    dragging.x = pt.x;
    dragging.y = pt.y;
    dragging.vx = 0;
    dragging.vy = 0;
    const dx = pt.x - dragging.dragStartX;
    const dy = pt.y - dragging.dragStartY;
    if (Math.sqrt(dx * dx + dy * dy) > DRAG_THRESHOLD) {
      dragging.moved = true;
    }
    wake();
  }

  function onUp() {
    if (!dragging) return;
    const node = dragging;
    node.fixed = false;
    dragging = null;
    if (node.moved) {
      const item = nodeEls.find(function (i) {
        return i.p === node;
      });
      if (item) item.el._suppressClick = true;
    }
    wake();
  }

  window.addEventListener("mousemove", onMove);
  window.addEventListener("touchmove", onMove, { passive: false });
  window.addEventListener("mouseup", onUp);
  window.addEventListener("touchend", onUp);

  render();
  return { graph: graph, nodeEls: nodeEls, edgeEls: edgeEls };
}

function setupHighlighting(root, evidenceGraph) {
  const adjacency = {};
  if (evidenceGraph) {
    evidenceGraph.graph.nodes.forEach(function (n) {
      adjacency[n.citation_number] = new Set();
    });
    evidenceGraph.graph.edges.forEach(function (e) {
      adjacency[e.a].add(e.b);
      adjacency[e.b].add(e.a);
    });
  }

  function neighborhoodOf(n) {
    const set = new Set([n]);
    if (adjacency[n]) adjacency[n].forEach(function (m) { set.add(m); });
    return set;
  }

  function toggle(el, active, related) {
    if (active === null) {
      el.classList.remove("highlighted", "dimmed");
      return;
    }
    el.classList.toggle("highlighted", !!related);
    el.classList.toggle("dimmed", !related);
  }

  function apply(n) {
    const active = n === null ? null : neighborhoodOf(n);

    root.querySelectorAll(".cite-marker").forEach(function (el) {
      const cn = parseInt(el.dataset.cite, 10);
      toggle(el, active, active && active.has(cn));
    });

    if (evidenceGraph) {
      evidenceGraph.nodeEls.forEach(function (item) {
        toggle(item.el, active, active && active.has(item.p.n));
      });
      evidenceGraph.edgeEls.forEach(function (item) {
        const related = active && active.has(item.e.a) && active.has(item.e.b);
        toggle(item.el, active, related);
      });
    }

    const refs = root.querySelectorAll(".references ol > li");
    refs.forEach(function (li, idx) {
      const cn = idx + 1;
      const related = active && active.has(cn);
      toggle(li, active, related);
      if (n !== null && cn === n) {
        li.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    });
  }

  let locked = null;

  function citationNumberFor(el) {
    if (el.dataset.cite) return parseInt(el.dataset.cite, 10);
    if (el.dataset.node) return parseInt(el.dataset.node, 10);
    return null;
  }

  const targets = Array.from(root.querySelectorAll(".cite-marker"));
  if (evidenceGraph) {
    evidenceGraph.nodeEls.forEach(function (item) {
      targets.push(item.el);
    });
  }
  root.querySelectorAll(".references ol > li").forEach(function (li, idx) {
    li.dataset.node = String(idx + 1);
    targets.push(li);
  });

  targets.forEach(function (el) {
    el.addEventListener("mouseenter", function () {
      if (locked === null) apply(citationNumberFor(el));
    });
    el.addEventListener("mouseleave", function () {
      if (locked === null) apply(null);
    });
    el.addEventListener("click", function () {
      if (el._suppressClick) {
        el._suppressClick = false;
        return;
      }
      const n = citationNumberFor(el);
      if (locked === n) {
        locked = null;
        apply(null);
      } else {
        locked = n;
        apply(n);
      }
    });
  });
}

function initEvidenceMap() {
  const root = document.getElementById("result");
  if (!root) return;

  const evidenceGraph = buildEvidenceGraph(root);
  setupHighlighting(root, evidenceGraph);
}

window.initEvidenceMap = initEvidenceMap;
document.addEventListener("DOMContentLoaded", initEvidenceMap);
