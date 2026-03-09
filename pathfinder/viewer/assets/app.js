const state = {
  artifact: null,
  positions: new Map(),
  selectedNodeId: null,
};

const palette = ["#38bdf8", "#34d399", "#f59e0b", "#fb7185", "#a78bfa", "#f472b6", "#f87171", "#22c55e"];

const canvas = document.getElementById("graph-canvas");
const context = canvas.getContext("2d");
const statusEl = document.getElementById("status");
const summaryEl = document.getElementById("summary");
const selectionEl = document.getElementById("selection");
const legendEl = document.getElementById("legend");

document.getElementById("load-server-graph").addEventListener("click", () => loadFromServer());
document.getElementById("graph-file").addEventListener("change", onFileSelected);
document.getElementById("search").addEventListener("input", render);
document.getElementById("language-filter").addEventListener("change", render);
document.getElementById("relation-filter").addEventListener("change", render);
window.addEventListener("resize", render);
canvas.addEventListener("click", onCanvasClick);

async function loadFromServer() {
  try {
    setStatus("Loading server graph...");
    const response = await fetch("/api/graph");
    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }
    const artifact = await response.json();
    applyArtifact(artifact, "Loaded graph from server.");
  } catch (error) {
    setStatus(`Unable to load server graph: ${error.message}`);
  }
}

function onFileSelected(event) {
  const [file] = event.target.files || [];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const artifact = JSON.parse(String(reader.result));
      applyArtifact(artifact, `Loaded ${file.name}`);
    } catch (error) {
      setStatus(`Unable to parse JSON: ${error.message}`);
    }
  };
  reader.readAsText(file);
}

function applyArtifact(artifact, message) {
  if (!artifact || !Array.isArray(artifact.nodes) || !Array.isArray(artifact.structural_edges)) {
    throw new Error("Artifact does not look like a Pathfinder structural graph.");
  }
  state.artifact = artifact;
  state.selectedNodeId = null;
  computeLayout();
  populateFilters();
  populateSummary();
  render();
  setStatus(message);
}

function populateFilters() {
  const languageFilter = document.getElementById("language-filter");
  const relationFilter = document.getElementById("relation-filter");
  replaceOptions(languageFilter, ["all", ...Object.keys(state.artifact.summary.files_by_language || {})]);
  replaceOptions(relationFilter, ["all", ...Object.keys(state.artifact.summary.edges_by_relationship_type || {})]);
  populateLegend();
}

function replaceOptions(select, values) {
  const current = select.value;
  select.innerHTML = "";
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value === "all" ? select.id === "language-filter" ? "All languages" : "All relationships" : value;
    select.appendChild(option);
  });
  if (values.includes(current)) select.value = current;
}

function populateLegend() {
  const languages = Object.keys(state.artifact.summary.files_by_language || {});
  legendEl.innerHTML = "";
  languages.forEach((language, index) => {
    const chip = document.createElement("div");
    chip.className = "legend-chip";
    chip.innerHTML = `<span class="legend-swatch" style="background:${colorForLanguage(language, index)}"></span>${language}`;
    legendEl.appendChild(chip);
  });
}

function populateSummary() {
  const summary = state.artifact.summary;
  const diagnostics = state.artifact.diagnostics;
  summaryEl.innerHTML = "";
  const entries = [
    ["Graph", state.artifact.graph_id],
    ["Files", summary.file_count],
    ["Edges", summary.structural_edge_count],
    ["Evidence", summary.evidence_count],
    ["Dropped self-edges", diagnostics.dropped_self_edges],
  ];
  entries.forEach(([key, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    summaryEl.append(dt, dd);
  });
}

function computeLayout() {
  const nodes = state.artifact.nodes;
  const edges = state.artifact.structural_edges;
  const positions = new Map();
  const radius = Math.max(220, nodes.length * 8);
  nodes.forEach((node, index) => {
    const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2;
    positions.set(node.id, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius, vx: 0, vy: 0 });
  });

  for (let iteration = 0; iteration < 180; iteration += 1) {
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = positions.get(nodes[i].id);
        const b = positions.get(nodes[j].id);
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distanceSquared = (dx * dx) + (dy * dy) + 0.01;
        const force = 2500 / distanceSquared;
        const ux = dx / Math.sqrt(distanceSquared);
        const uy = dy / Math.sqrt(distanceSquared);
        a.vx -= ux * force;
        a.vy -= uy * force;
        b.vx += ux * force;
        b.vy += uy * force;
      }
    }

    edges.forEach((edge) => {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      if (!source || !target) return;
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.sqrt((dx * dx) + (dy * dy)) || 1;
      const spring = (distance - 90) * 0.0018;
      const ux = dx / distance;
      const uy = dy / distance;
      source.vx += ux * spring;
      source.vy += uy * spring;
      target.vx -= ux * spring;
      target.vy -= uy * spring;
    });

    positions.forEach((position) => {
      position.vx *= 0.82;
      position.vy *= 0.82;
      position.x += position.vx;
      position.y += position.vy;
    });
  }

  state.positions = positions;
}

function render() {
  resizeCanvas();
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!state.artifact) {
    drawEmptyState();
    return;
  }

  const { visibleNodes, visibleEdges } = getVisibleGraph();
  const screenPositions = projectToScreen(visibleNodes);

  visibleEdges.forEach((edge) => drawEdge(edge, screenPositions));
  visibleNodes.forEach((node, index) => drawNode(node, screenPositions.get(node.id), index));
  updateSelection(visibleEdges);
}

function getVisibleGraph() {
  const searchTerm = document.getElementById("search").value.trim().toLowerCase();
  const language = document.getElementById("language-filter").value;
  const relation = document.getElementById("relation-filter").value;
  const nodeMatches = new Set(
    state.artifact.nodes
      .filter((node) => (language === "all" || node.language === language) && (!searchTerm || node.path.toLowerCase().includes(searchTerm)))
      .map((node) => node.id),
  );
  const visibleEdges = state.artifact.structural_edges.filter((edge) => {
    if (relation !== "all" && edge.relationship_type !== relation) return false;
    return nodeMatches.has(edge.source) && nodeMatches.has(edge.target);
  });
  const connectedNodeIds = new Set([...nodeMatches]);
  visibleEdges.forEach((edge) => {
    connectedNodeIds.add(edge.source);
    connectedNodeIds.add(edge.target);
  });
  const visibleNodes = state.artifact.nodes.filter((node) => connectedNodeIds.has(node.id));
  return { visibleNodes, visibleEdges };
}

function projectToScreen(nodes) {
  const positions = new Map();
  if (!nodes.length) return positions;
  const coords = nodes.map((node) => state.positions.get(node.id));
  const xs = coords.map((point) => point.x);
  const ys = coords.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const padding = 80;
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);
  const scale = Math.min((canvas.width - (padding * 2)) / spanX, (canvas.height - (padding * 2)) / spanY);
  nodes.forEach((node) => {
    const point = state.positions.get(node.id);
    positions.set(node.id, {
      x: ((point.x - minX) * scale) + padding,
      y: ((point.y - minY) * scale) + padding,
    });
  });
  return positions;
}

function drawEdge(edge, positions) {
  const source = positions.get(edge.source);
  const target = positions.get(edge.target);
  if (!source || !target) return;
  context.beginPath();
  context.moveTo(source.x, source.y);
  context.lineTo(target.x, target.y);
  context.strokeStyle = edge.relationship_type === "calls" ? "rgba(248, 113, 113, 0.55)" : edge.relationship_type === "references" ? "rgba(168, 85, 247, 0.5)" : "rgba(56, 189, 248, 0.35)";
  context.lineWidth = edge.relationship_type === "calls" ? 1.8 : 1.2;
  context.stroke();
}

function drawNode(node, point, index) {
  if (!point) return;
  const selected = node.id === state.selectedNodeId;
  context.beginPath();
  context.arc(point.x, point.y, selected ? 8 : 5, 0, Math.PI * 2);
  context.fillStyle = colorForLanguage(node.language, index);
  context.fill();
  if (selected) {
    context.beginPath();
    context.arc(point.x, point.y, 13, 0, Math.PI * 2);
    context.strokeStyle = "rgba(255,255,255,0.85)";
    context.lineWidth = 2;
    context.stroke();
  }
}

function updateSelection(edges) {
  if (!state.selectedNodeId) {
    selectionEl.className = "selection-empty";
    selectionEl.innerHTML = "Click a node to inspect it.";
    return;
  }

  const node = state.artifact.nodes.find((item) => item.id === state.selectedNodeId);
  if (!node) return;
  const outgoing = edges.filter((edge) => edge.source === node.id).slice(0, 8);
  const incoming = edges.filter((edge) => edge.target === node.id).slice(0, 8);
  selectionEl.className = "";
  selectionEl.innerHTML = `
    <strong>${escapeHtml(node.path)}</strong>
    <p class="muted">language: ${escapeHtml(node.language)} · in: ${node.in_degree_structural} · out: ${node.out_degree_structural}</p>
    <p class="muted">imports: ${node.import_count}</p>
    <h3>Outgoing</h3>
    <ul class="selection-list">${renderEdgeList(outgoing, "target")}</ul>
    <h3>Incoming</h3>
    <ul class="selection-list">${renderEdgeList(incoming, "source")}</ul>
  `;
}

function renderEdgeList(edges, key) {
  if (!edges.length) return "<li>None</li>";
  return edges.map((edge) => `<li><code>${escapeHtml(edge[key])}</code> <span class="muted">(${escapeHtml(edge.relationship_type)} · evidence ${edge.evidence_count})</span></li>`).join("");
}

function onCanvasClick(event) {
  if (!state.artifact) return;
  const rect = canvas.getBoundingClientRect();
  const x = (event.clientX - rect.left) * (canvas.width / rect.width);
  const y = (event.clientY - rect.top) * (canvas.height / rect.height);
  const { visibleNodes } = getVisibleGraph();
  const positions = projectToScreen(visibleNodes);
  let best = null;
  let bestDistance = 18;
  visibleNodes.forEach((node) => {
    const point = positions.get(node.id);
    const distance = Math.hypot(point.x - x, point.y - y);
    if (distance < bestDistance) {
      best = node.id;
      bestDistance = distance;
    }
  });
  state.selectedNodeId = best;
  render();
}

function resizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
}

function drawEmptyState() {
  context.fillStyle = "#94a3b8";
  context.font = "16px sans-serif";
  context.fillText("Load a Pathfinder structural graph to begin.", 30, 40);
}

function setStatus(message) {
  statusEl.textContent = message;
}

function colorForLanguage(language, index) {
  let hash = 0;
  for (let i = 0; i < language.length; i += 1) hash = ((hash << 5) - hash) + language.charCodeAt(i);
  return palette[Math.abs(hash + index) % palette.length];
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadFromServer();