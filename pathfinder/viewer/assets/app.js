const state = {
  artifact: null,
  selectedNodeId: null,
  renderedBoxes: new Map(),
};

const palette = ["#38bdf8", "#34d399", "#f59e0b", "#fb7185", "#a78bfa", "#f472b6", "#f87171", "#22c55e"];

const canvas = document.getElementById("graph-canvas");
const context = canvas.getContext("2d");
const statusEl = document.getElementById("status");
const viewMetaEl = document.getElementById("view-meta");
const summaryEl = document.getElementById("summary");
const selectionEl = document.getElementById("selection");
const legendEl = document.getElementById("legend");
const trimIsolatedEl = document.getElementById("trim-isolated");

document.getElementById("load-server-graph").addEventListener("click", () => loadFromServer());
document.getElementById("graph-file").addEventListener("change", onFileSelected);
document.getElementById("search").addEventListener("input", render);
document.getElementById("language-filter").addEventListener("change", render);
document.getElementById("relation-filter").addEventListener("change", render);
trimIsolatedEl.addEventListener("change", render);
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
  populateFilters();
  populateSummary();
  render();
  setStatus(message);
}

function populateFilters() {
  const languageFilter = document.getElementById("language-filter");
  const relationFilter = document.getElementById("relation-filter");
  const summary = state.artifact.summary || {};
  replaceOptions(languageFilter, ["all", ...Object.keys(summary.files_by_language || {})]);
  replaceOptions(relationFilter, ["all", ...Object.keys(summary.edges_by_relationship_type || {})]);
  populateLegend();
}

function replaceOptions(select, values) {
  const current = select.value;
  select.innerHTML = "";
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value === "all"
      ? select.id === "language-filter" ? "All languages" : "All relationships"
      : value;
    select.appendChild(option);
  });
  if (values.includes(current)) {
    select.value = current;
  }
}

function populateLegend() {
  const languages = Object.keys(state.artifact.summary?.files_by_language || {});
  legendEl.innerHTML = "";
  languages.forEach((language, index) => {
    const chip = document.createElement("div");
    chip.className = "legend-chip";
    chip.innerHTML = `<span class="legend-swatch" style="background:${colorForLanguage(language, index)}"></span>${escapeHtml(language)}`;
    legendEl.appendChild(chip);
  });
}

function populateSummary() {
  const summary = state.artifact.summary || {};
  const diagnostics = state.artifact.diagnostics || {};
  summaryEl.innerHTML = "";
  const entries = [
    ["Graph", state.artifact.graph_id || "unknown"],
    ["Files", summary.file_count ?? state.artifact.nodes.length],
    ["Edges", summary.structural_edge_count ?? state.artifact.structural_edges.length],
    ["Evidence", summary.evidence_count ?? 0],
    ["Dropped self-edges", diagnostics.dropped_self_edges ?? 0],
  ];
  entries.forEach(([key, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    summaryEl.append(dt, dd);
  });
}

function render() {
  resizeCanvas();
  context.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
  if (!state.artifact) {
    drawEmptyState("Load a Pathfinder structural graph to begin.");
    return;
  }

  const visibleGraph = getVisibleGraph();
  updateViewMeta(visibleGraph);
  if (!visibleGraph.visibleNodes.some((node) => node.id === state.selectedNodeId)) {
    state.selectedNodeId = null;
  }

  if (!visibleGraph.visibleNodes.length) {
    state.renderedBoxes = new Map();
    drawEmptyState(visibleGraph.emptyMessage);
    updateSelection([]);
    return;
  }

  const screenGraph = layoutGraphToScreen(visibleGraph.visibleNodes, visibleGraph.visibleEdges);
  state.renderedBoxes = screenGraph.boxes;

  screenGraph.edges.forEach((edge) => drawEdge(edge, screenGraph.boxes));
  screenGraph.nodes.forEach((node) => drawNode(node, screenGraph.boxes.get(node.id)));
  updateSelection(visibleGraph.visibleEdges);
}

function getVisibleGraph() {
  const searchTerm = document.getElementById("search").value.trim().toLowerCase();
  const language = document.getElementById("language-filter").value;
  const relation = document.getElementById("relation-filter").value;
  const hideDisconnected = trimIsolatedEl.checked;

  const candidateNodes = state.artifact.nodes
    .filter((node) => (language === "all" || node.language === language) && (!searchTerm || node.path.toLowerCase().includes(searchTerm)))
    .sort(compareNodes);
  const candidateIds = new Set(candidateNodes.map((node) => node.id));

  const visibleEdges = state.artifact.structural_edges
    .filter((edge) => (relation === "all" || edge.relationship_type === relation) && candidateIds.has(edge.source) && candidateIds.has(edge.target))
    .sort(compareEdges);

  const connectedIds = new Set();
  visibleEdges.forEach((edge) => {
    connectedIds.add(edge.source);
    connectedIds.add(edge.target);
  });

  let visibleNodes = candidateNodes;
  let hiddenDisconnectedCount = 0;
  if (hideDisconnected && visibleEdges.length > 0) {
    visibleNodes = candidateNodes.filter((node) => connectedIds.has(node.id));
    hiddenDisconnectedCount = candidateNodes.length - visibleNodes.length;
  } else if (hideDisconnected && !searchTerm && visibleEdges.length === 0) {
    visibleNodes = [];
    hiddenDisconnectedCount = candidateNodes.length;
  }

  const emptyMessage = searchTerm || language !== "all" || relation !== "all"
    ? "No connected files match the current filters. Try relaxing filters or showing disconnected files."
    : "No connected files to render. Turn off the disconnected-file trim if you want to inspect isolated files.";

  return { visibleNodes, visibleEdges, hiddenDisconnectedCount, emptyMessage };
}

function layoutGraphToScreen(nodes, edges) {
  const components = computeConnectedComponents(nodes, edges);
  const layouts = components.map((componentNodes) => layoutComponent(componentNodes, edges));
  const packedLayout = packComponents(layouts);
  const scale = computeScale(packedLayout.bounds);
  const boxes = new Map();

  packedLayout.nodes.forEach((node) => {
    const left = ((node.x - (node.width / 2)) - packedLayout.bounds.left) * scale + packedLayout.offsetX;
    const top = ((node.y - (node.height / 2)) - packedLayout.bounds.top) * scale + packedLayout.offsetY;
    boxes.set(node.id, {
      ...node,
      x: left,
      y: top,
      width: node.width * scale,
      height: node.height * scale,
    });
  });

  return { nodes: nodes.sort(compareNodes), edges, boxes };
}

function computeConnectedComponents(nodes, edges) {
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const adjacency = buildAdjacency(nodes, edges);
  const visited = new Set();
  const components = [];

  nodes.forEach((node) => {
    if (visited.has(node.id)) return;
    const stack = [node.id];
    const component = [];
    visited.add(node.id);

    while (stack.length) {
      const current = stack.pop();
      component.push(nodesById.get(current));
      [...(adjacency.get(current) || [])].sort().forEach((neighborId) => {
        if (visited.has(neighborId)) return;
        visited.add(neighborId);
        stack.push(neighborId);
      });
    }

    components.push(component.sort(compareNodes));
  });

  return components.sort((left, right) => right.length - left.length || compareNodes(left[0], right[0]));
}

function layoutComponent(componentNodes, allEdges) {
  const nodeIds = new Set(componentNodes.map((node) => node.id));
  const componentEdges = allEdges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));
  const adjacency = buildAdjacency(componentNodes, componentEdges);
  const degreeMap = buildDegreeMap(componentEdges);
  const dimensions = new Map(componentNodes.map((node) => [node.id, getNodeDimensions(node)]));
  const root = [...componentNodes].sort((left, right) => {
    const degreeDelta = (degreeMap.get(right.id) || 0) - (degreeMap.get(left.id) || 0);
    return degreeDelta || compareNodes(left, right);
  })[0];
  const layers = assignLayers(root.id, componentNodes, adjacency, degreeMap);
  const groupedLayers = new Map();

  layers.forEach((depth, nodeId) => {
    if (!groupedLayers.has(depth)) groupedLayers.set(depth, []);
    groupedLayers.get(depth).push(componentNodes.find((node) => node.id === nodeId));
  });

  const maxWidth = Math.max(...componentNodes.map((node) => dimensions.get(node.id).width), 150);
  const layerGap = Math.max(220, maxWidth + 72);
  const rowGap = 28;
  const anchors = new Map();
  const positions = new Map();
  const velocities = new Map();

  [...groupedLayers.keys()].sort((left, right) => left - right).forEach((depth) => {
    const layerNodes = groupedLayers.get(depth).sort((left, right) => {
      const degreeDelta = (degreeMap.get(right.id) || 0) - (degreeMap.get(left.id) || 0);
      return degreeDelta || compareNodes(left, right);
    });
    const totalHeight = layerNodes.reduce((sum, node) => sum + dimensions.get(node.id).height, 0) + (Math.max(layerNodes.length - 1, 0) * rowGap);
    let cursor = -(totalHeight / 2);

    layerNodes.forEach((node) => {
      const size = dimensions.get(node.id);
      const x = depth * layerGap;
      const y = cursor + (size.height / 2);
      anchors.set(node.id, { x, y });
      positions.set(node.id, { x, y });
      velocities.set(node.id, { x: 0, y: 0 });
      cursor += size.height + rowGap;
    });
  });

  for (let iteration = 0; iteration < 140; iteration += 1) {
    for (let i = 0; i < componentNodes.length; i += 1) {
      for (let j = i + 1; j < componentNodes.length; j += 1) {
        const leftNode = componentNodes[i];
        const rightNode = componentNodes[j];
        const leftPosition = positions.get(leftNode.id);
        const rightPosition = positions.get(rightNode.id);
        const leftSize = dimensions.get(leftNode.id);
        const rightSize = dimensions.get(rightNode.id);
        const dx = rightPosition.x - leftPosition.x;
        const dy = rightPosition.y - leftPosition.y;
        const distanceSquared = (dx * dx) + (dy * dy) + 1;
        const distance = Math.sqrt(distanceSquared);
        const ux = dx / distance;
        const uy = dy / distance;
        const repulsion = Math.min(18000 / distanceSquared, 20);
        const overlapX = ((leftSize.width + rightSize.width) / 2) + 22 - Math.abs(dx);
        const overlapY = ((leftSize.height + rightSize.height) / 2) + 18 - Math.abs(dy);

        if (overlapX > 0 && overlapY > 0) {
          const pushX = (overlapX * 0.16) * (dx === 0 ? (i % 2 === 0 ? -1 : 1) : Math.sign(dx));
          const pushY = (overlapY * 0.18) * (dy === 0 ? (j % 2 === 0 ? -1 : 1) : Math.sign(dy));
          velocities.get(leftNode.id).x -= pushX;
          velocities.get(rightNode.id).x += pushX;
          velocities.get(leftNode.id).y -= pushY;
          velocities.get(rightNode.id).y += pushY;
        } else {
          velocities.get(leftNode.id).x -= ux * repulsion;
          velocities.get(leftNode.id).y -= uy * repulsion;
          velocities.get(rightNode.id).x += ux * repulsion;
          velocities.get(rightNode.id).y += uy * repulsion;
        }
      }
    }

    componentEdges.forEach((edge) => {
      const sourcePosition = positions.get(edge.source);
      const targetPosition = positions.get(edge.target);
      const sourceSize = dimensions.get(edge.source);
      const targetSize = dimensions.get(edge.target);
      const dx = targetPosition.x - sourcePosition.x;
      const dy = targetPosition.y - sourcePosition.y;
      const distance = Math.sqrt((dx * dx) + (dy * dy)) || 1;
      const idealDistance = ((sourceSize.width + targetSize.width) / 2) + 72;
      const spring = (distance - idealDistance) * 0.025;
      const ux = dx / distance;
      const uy = dy / distance;

      velocities.get(edge.source).x += ux * spring;
      velocities.get(edge.source).y += uy * spring;
      velocities.get(edge.target).x -= ux * spring;
      velocities.get(edge.target).y -= uy * spring;
    });

    componentNodes.forEach((node) => {
      const position = positions.get(node.id);
      const velocity = velocities.get(node.id);
      const anchor = anchors.get(node.id);
      velocity.x += (anchor.x - position.x) * 0.035;
      velocity.y += (anchor.y - position.y) * 0.02;
      velocity.x *= 0.78;
      velocity.y *= 0.78;
      position.x += velocity.x;
      position.y += velocity.y;
    });
  }

  const renderedNodes = componentNodes.map((node) => {
    const position = positions.get(node.id);
    const size = dimensions.get(node.id);
    return { ...node, x: position.x, y: position.y, width: size.width, height: size.height };
  });

  const bounds = getBounds(renderedNodes);
  const centerX = (bounds.left + bounds.right) / 2;
  const centerY = (bounds.top + bounds.bottom) / 2;
  const centeredNodes = renderedNodes.map((node) => ({ ...node, x: node.x - centerX, y: node.y - centerY }));
  const centeredBounds = getBounds(centeredNodes);

  return {
    nodes: centeredNodes,
    width: centeredBounds.right - centeredBounds.left,
    height: centeredBounds.bottom - centeredBounds.top,
  };
}

function assignLayers(rootId, nodes, adjacency, degreeMap) {
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const layers = new Map([[rootId, 0]]);
  const queue = [rootId];

  while (queue.length) {
    const current = queue.shift();
    const depth = layers.get(current);
    [...(adjacency.get(current) || [])]
      .sort((left, right) => (degreeMap.get(right) || 0) - (degreeMap.get(left) || 0) || compareNodes(nodesById.get(left), nodesById.get(right)))
      .forEach((neighborId) => {
        if (layers.has(neighborId)) return;
        layers.set(neighborId, depth + 1);
        queue.push(neighborId);
      });
  }

  nodes.forEach((node) => {
    if (!layers.has(node.id)) {
      layers.set(node.id, Math.max(...layers.values()) + 1);
    }
  });
  return layers;
}

function packComponents(layouts) {
  const gapX = 110;
  const gapY = 120;
  const totalArea = layouts.reduce((sum, layout) => sum + (layout.width * layout.height), 0);
  const aspect = canvas.clientWidth / Math.max(canvas.clientHeight, 1);
  const targetRowWidth = Math.max(460, Math.sqrt(totalArea * Math.max(aspect, 0.8)));
  const rows = [];
  let currentRow = { layouts: [], width: 0, height: 0 };

  layouts.forEach((layout) => {
    const projectedWidth = currentRow.layouts.length ? currentRow.width + gapX + layout.width : layout.width;
    if (currentRow.layouts.length && projectedWidth > targetRowWidth) {
      rows.push(currentRow);
      currentRow = { layouts: [], width: 0, height: 0 };
    }
    currentRow.layouts.push(layout);
    currentRow.width = currentRow.layouts.length === 1 ? layout.width : currentRow.width + gapX + layout.width;
    currentRow.height = Math.max(currentRow.height, layout.height);
  });
  if (currentRow.layouts.length) rows.push(currentRow);

  const totalHeight = rows.reduce((sum, row) => sum + row.height, 0) + (Math.max(rows.length - 1, 0) * gapY);
  let cursorY = -(totalHeight / 2);
  const packedNodes = [];

  rows.forEach((row) => {
    let cursorX = -(row.width / 2);
    row.layouts.forEach((layout) => {
      const centerX = cursorX + (layout.width / 2);
      const centerY = cursorY + (row.height / 2);
      layout.nodes.forEach((node) => {
        packedNodes.push({ ...node, x: node.x + centerX, y: node.y + centerY });
      });
      cursorX += layout.width + gapX;
    });
    cursorY += row.height + gapY;
  });

  const bounds = getBounds(packedNodes);
  return {
    nodes: packedNodes,
    bounds,
    offsetX: Math.max((canvas.clientWidth - ((bounds.right - bounds.left) * computeScale(bounds))) / 2, 24),
    offsetY: Math.max((canvas.clientHeight - ((bounds.bottom - bounds.top) * computeScale(bounds))) / 2, 24),
  };
}

function computeScale(bounds) {
  const padding = 54;
  const width = Math.max(bounds.right - bounds.left, 1);
  const height = Math.max(bounds.bottom - bounds.top, 1);
  return Math.min(
    (Math.max(canvas.clientWidth - (padding * 2), 120)) / width,
    (Math.max(canvas.clientHeight - (padding * 2), 120)) / height,
    1.18,
  );
}

function buildAdjacency(nodes, edges) {
  const adjacency = new Map(nodes.map((node) => [node.id, new Set()]));
  edges.forEach((edge) => {
    if (!adjacency.has(edge.source) || !adjacency.has(edge.target)) return;
    adjacency.get(edge.source).add(edge.target);
    adjacency.get(edge.target).add(edge.source);
  });
  return adjacency;
}

function buildDegreeMap(edges) {
  const degrees = new Map();
  edges.forEach((edge) => {
    degrees.set(edge.source, (degrees.get(edge.source) || 0) + 1);
    degrees.set(edge.target, (degrees.get(edge.target) || 0) + 1);
  });
  return degrees;
}

function drawEdge(edge, boxes) {
  const source = boxes.get(edge.source);
  const target = boxes.get(edge.target);
  if (!source || !target) return;
  const start = getBoxAnchor(source, target);
  const end = getBoxAnchor(target, source);

  context.beginPath();
  context.moveTo(start.x, start.y);
  context.lineTo(end.x, end.y);
  context.strokeStyle = edge.relationship_type === "calls"
    ? "rgba(248, 113, 113, 0.55)"
    : edge.relationship_type === "references"
      ? "rgba(168, 85, 247, 0.5)"
      : "rgba(56, 189, 248, 0.38)";
  context.lineWidth = edge.relationship_type === "calls" ? 2.4 : 1.6;
  context.stroke();
}

function drawNode(node, box) {
  if (!box) return;
  const selected = node.id === state.selectedNodeId;
  const fill = colorForLanguage(node.language, 0);
  const label = getNodeLabel(node);
  const radius = Math.min(box.height / 3.6, 18);

  context.fillStyle = hexToRgba(fill, selected ? 0.34 : 0.24);
  context.strokeStyle = selected ? "rgba(255,255,255,0.92)" : hexToRgba(fill, 0.72);
  context.lineWidth = selected ? 2.5 : 1.5;
  drawRoundedRect(box.x, box.y, box.width, box.height, radius);
  context.fill();
  context.stroke();

  context.fillStyle = "#f8fafc";
  context.font = `${Math.max(Math.min(box.height * 0.26, 16), 11)}px Inter, system-ui, sans-serif`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(label.primary, box.x + (box.width / 2), box.y + (box.height * 0.42), box.width - 20);

  context.fillStyle = "rgba(226,232,240,0.72)";
  context.font = `${Math.max(Math.min(box.height * 0.16, 11), 9)}px Inter, system-ui, sans-serif`;
  context.fillText(label.secondary, box.x + (box.width / 2), box.y + (box.height * 0.72), box.width - 20);
}

function drawRoundedRect(x, y, width, height, radius) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.lineTo(x + width - radius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + radius);
  context.lineTo(x + width, y + height - radius);
  context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  context.lineTo(x + radius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - radius);
  context.lineTo(x, y + radius);
  context.quadraticCurveTo(x, y, x + radius, y);
  context.closePath();
}

function getBoxAnchor(source, target) {
  const sourceCenter = { x: source.x + (source.width / 2), y: source.y + (source.height / 2) };
  const targetCenter = { x: target.x + (target.width / 2), y: target.y + (target.height / 2) };
  const dx = targetCenter.x - sourceCenter.x;
  const dy = targetCenter.y - sourceCenter.y;
  const halfWidth = source.width / 2;
  const halfHeight = source.height / 2;

  if (dx === 0 && dy === 0) return sourceCenter;
  const scale = 1 / Math.max(Math.abs(dx) / halfWidth, Math.abs(dy) / halfHeight);
  return {
    x: sourceCenter.x + (dx * scale),
    y: sourceCenter.y + (dy * scale),
  };
}

function getNodeDimensions(node) {
  const label = getNodeLabel(node);
  const primaryWidth = estimateTextWidth(label.primary, 14);
  const secondaryWidth = estimateTextWidth(label.secondary, 10);
  return {
    width: Math.max(Math.min(Math.max(primaryWidth, secondaryWidth) + 36, 260), 132),
    height: 66,
  };
}

function getNodeLabel(node) {
  const parts = node.path.split("/");
  const primary = truncateMiddle(parts[parts.length - 1] || node.path, 24);
  const secondarySource = parts.length > 1 ? parts.slice(0, -1).join("/") : node.language;
  return {
    primary,
    secondary: truncateMiddle(secondarySource || node.language, 26),
  };
}

function estimateTextWidth(text, fontSize) {
  return text.length * fontSize * 0.58;
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
    <h3 class="selection-subheading">Outgoing</h3>
    <ul class="selection-list">${renderEdgeList(outgoing, "target")}</ul>
    <h3 class="selection-subheading">Incoming</h3>
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
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const clicked = [...state.renderedBoxes.values()].find((box) => pointInBox(x, y, box));
  state.selectedNodeId = clicked ? clicked.id : null;
  render();
}

function pointInBox(x, y, box) {
  return x >= box.x && x <= box.x + box.width && y >= box.y && y <= box.y + box.height;
}

function updateViewMeta(visibleGraph) {
  const visibleFiles = visibleGraph.visibleNodes.length;
  const visibleEdges = visibleGraph.visibleEdges.length;
  const hidden = visibleGraph.hiddenDisconnectedCount;
  const hiddenSuffix = hidden ? ` · ${hidden} disconnected hidden` : "";
  viewMetaEl.textContent = `Showing ${visibleFiles} files · ${visibleEdges} edges${hiddenSuffix}`;
}

function resizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
}

function drawEmptyState(message) {
  context.fillStyle = "#94a3b8";
  context.font = "16px Inter, system-ui, sans-serif";
  context.fillText(message, 30, 40);
}

function getBounds(nodes) {
  return nodes.reduce((bounds, node) => ({
    left: Math.min(bounds.left, node.x - (node.width / 2)),
    right: Math.max(bounds.right, node.x + (node.width / 2)),
    top: Math.min(bounds.top, node.y - (node.height / 2)),
    bottom: Math.max(bounds.bottom, node.y + (node.height / 2)),
  }), { left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity });
}

function setStatus(message) {
  statusEl.textContent = message;
}

function compareNodes(left, right) {
  return left.path.localeCompare(right.path);
}

function compareEdges(left, right) {
  return left.source.localeCompare(right.source)
    || left.target.localeCompare(right.target)
    || left.relationship_type.localeCompare(right.relationship_type);
}

function colorForLanguage(language, index) {
  let hash = 0;
  for (let i = 0; i < language.length; i += 1) hash = ((hash << 5) - hash) + language.charCodeAt(i);
  return palette[Math.abs(hash + index) % palette.length];
}

function hexToRgba(hex, alpha) {
  const normalized = hex.replace("#", "");
  const red = parseInt(normalized.substring(0, 2), 16);
  const green = parseInt(normalized.substring(2, 4), 16);
  const blue = parseInt(normalized.substring(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function truncateMiddle(text, maxLength) {
  if (text.length <= maxLength) return text;
  const left = Math.ceil((maxLength - 1) / 2);
  const right = Math.floor((maxLength - 1) / 2);
  return `${text.slice(0, left)}…${text.slice(text.length - right)}`;
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