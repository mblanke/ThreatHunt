from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/NetworkMap.tsx')
t=p.read_text(encoding='utf-8')

# constants
if 'RENDER_SIMPLIFY_NODE_THRESHOLD' not in t:
    t=t.replace(
"const LARGE_HUNT_SUBGRAPH_EDGES = 2500;\n",
"const LARGE_HUNT_SUBGRAPH_EDGES = 2500;\nconst RENDER_SIMPLIFY_NODE_THRESHOLD = 220;\nconst RENDER_SIMPLIFY_EDGE_THRESHOLD = 1200;\nconst EDGE_DRAW_TARGET = 1000;\n")

# drawBackground signature
 t_old='''function drawBackground(
  ctx: CanvasRenderingContext2D, w: number, h: number, vp: Viewport, dpr: number,
) {
'''
if t_old in t:
    t=t.replace(t_old,
'''function drawBackground(
  ctx: CanvasRenderingContext2D, w: number, h: number, vp: Viewport, dpr: number,
  simplify: boolean,
) {
''')

# skip grid when simplify
if 'if (!simplify) {' not in t:
    t=t.replace(
'''  ctx.save();
  ctx.translate(vp.x * dpr, vp.y * dpr);
  ctx.scale(vp.scale * dpr, vp.scale * dpr);
  const startX = -vp.x / vp.scale - GRID_SPACING;
  const startY = -vp.y / vp.scale - GRID_SPACING;
  const endX = startX + w / (vp.scale * dpr) + GRID_SPACING * 2;
  const endY = startY + h / (vp.scale * dpr) + GRID_SPACING * 2;
  ctx.fillStyle = GRID_DOT_COLOR;
  for (let gx = Math.floor(startX / GRID_SPACING) * GRID_SPACING; gx < endX; gx += GRID_SPACING) {
    for (let gy = Math.floor(startY / GRID_SPACING) * GRID_SPACING; gy < endY; gy += GRID_SPACING) {
      ctx.beginPath(); ctx.arc(gx, gy, 1, 0, Math.PI * 2); ctx.fill();
    }
  }
  ctx.restore();
''',
'''  if (!simplify) {
    ctx.save();
    ctx.translate(vp.x * dpr, vp.y * dpr);
    ctx.scale(vp.scale * dpr, vp.scale * dpr);
    const startX = -vp.x / vp.scale - GRID_SPACING;
    const startY = -vp.y / vp.scale - GRID_SPACING;
    const endX = startX + w / (vp.scale * dpr) + GRID_SPACING * 2;
    const endY = startY + h / (vp.scale * dpr) + GRID_SPACING * 2;
    ctx.fillStyle = GRID_DOT_COLOR;
    for (let gx = Math.floor(startX / GRID_SPACING) * GRID_SPACING; gx < endX; gx += GRID_SPACING) {
      for (let gy = Math.floor(startY / GRID_SPACING) * GRID_SPACING; gy < endY; gy += GRID_SPACING) {
        ctx.beginPath(); ctx.arc(gx, gy, 1, 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.restore();
  }
''')

# drawEdges signature
 t=t.replace('''function drawEdges(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null,
  nodeMap: Map<string, GNode>, animTime: number,
) {
  for (const e of graph.edges) {
''',
'''function drawEdges(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null,
  nodeMap: Map<string, GNode>, animTime: number,
  simplify: boolean,
) {
  const edgeStep = simplify ? Math.max(1, Math.ceil(graph.edges.length / EDGE_DRAW_TARGET)) : 1;
  for (let ei = 0; ei < graph.edges.length; ei += edgeStep) {
    const e = graph.edges[ei];
''')

# simplify edge path
 t=t.replace('ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(cpx, cpy, b.x, b.y);',
             'ctx.beginPath(); ctx.moveTo(a.x, a.y); if (simplify) { ctx.lineTo(b.x, b.y); } else { ctx.quadraticCurveTo(cpx, cpy, b.x, b.y); }')

t=t.replace('ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(cpx, cpy, b.x, b.y);',
             'ctx.beginPath(); ctx.moveTo(a.x, a.y); if (simplify) { ctx.lineTo(b.x, b.y); } else { ctx.quadraticCurveTo(cpx, cpy, b.x, b.y); }')

# reduce glow when simplify
 t=t.replace('''      ctx.save();
      ctx.shadowColor = 'rgba(96,165,250,0.5)'; ctx.shadowBlur = 8;
      ctx.strokeStyle = 'rgba(96,165,250,0.3)';
      ctx.lineWidth = Math.min(5, 2 + e.weight * 0.2);
      ctx.beginPath(); ctx.moveTo(a.x, a.y); if (simplify) { ctx.lineTo(b.x, b.y); } else { ctx.quadraticCurveTo(cpx, cpy, b.x, b.y); }
      ctx.stroke(); ctx.restore();
''',
'''      if (!simplify) {
        ctx.save();
        ctx.shadowColor = 'rgba(96,165,250,0.5)'; ctx.shadowBlur = 8;
        ctx.strokeStyle = 'rgba(96,165,250,0.3)';
        ctx.lineWidth = Math.min(5, 2 + e.weight * 0.2);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); if (simplify) { ctx.lineTo(b.x, b.y); } else { ctx.quadraticCurveTo(cpx, cpy, b.x, b.y); }
        ctx.stroke(); ctx.restore();
      }
''')

# drawLabels signature and early return
 t=t.replace('''function drawLabels(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null,
  search: string, matchSet: Set<string>, vp: Viewport,
) {
''',
'''function drawLabels(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null,
  search: string, matchSet: Set<string>, vp: Viewport,
  simplify: boolean,
) {
''')

if 'if (simplify && !search && !hovered && !selected) {' not in t:
    t=t.replace('  const dimmed = search.length > 0;\n',
                '  const dimmed = search.length > 0;\n  if (simplify && !search && !hovered && !selected) {\n    return;\n  }\n')

# drawGraph adapt
 t=t.replace('''  drawBackground(ctx, w, h, vp, dpr);
  ctx.save();
  ctx.translate(vp.x * dpr, vp.y * dpr);
  ctx.scale(vp.scale * dpr, vp.scale * dpr);
  drawEdges(ctx, graph, hovered, selected, nodeMap, animTime);
  drawNodes(ctx, graph, hovered, selected, search, matchSet);
  drawLabels(ctx, graph, hovered, selected, search, matchSet, vp);
  ctx.restore();
''',
'''  const simplify = graph.nodes.length > RENDER_SIMPLIFY_NODE_THRESHOLD || graph.edges.length > RENDER_SIMPLIFY_EDGE_THRESHOLD;
  drawBackground(ctx, w, h, vp, dpr, simplify);
  ctx.save();
  ctx.translate(vp.x * dpr, vp.y * dpr);
  ctx.scale(vp.scale * dpr, vp.scale * dpr);
  drawEdges(ctx, graph, hovered, selected, nodeMap, animTime, simplify);
  drawNodes(ctx, graph, hovered, selected, search, matchSet);
  drawLabels(ctx, graph, hovered, selected, search, matchSet, vp, simplify);
  ctx.restore();
''')

# hover RAF ref
if 'const hoverRafRef = useRef<number>(0);' not in t:
    t=t.replace('  const graphRef = useRef<Graph | null>(null);\n', '  const graphRef = useRef<Graph | null>(null);\n  const hoverRafRef = useRef<number>(0);\n')

# throttle hover hit test on mousemove
old_mm='''    const node = hitTest(graph, canvasRef.current, e.clientX, e.clientY, vpRef.current);
    setHovered(node?.id ?? null);
  }, [graph, redraw, startAnimLoop]);
'''
new_mm='''    cancelAnimationFrame(hoverRafRef.current);
    const clientX = e.clientX;
    const clientY = e.clientY;
    hoverRafRef.current = requestAnimationFrame(() => {
      const node = hitTest(graph, canvasRef.current as HTMLCanvasElement, clientX, clientY, vpRef.current);
      setHovered(prev => (prev === (node?.id ?? null) ? prev : (node?.id ?? null)));
    });
  }, [graph, redraw, startAnimLoop]);
'''
if old_mm in t:
    t=t.replace(old_mm,new_mm)

# cleanup hover raf on unmount in existing animation cleanup effect
if 'cancelAnimationFrame(hoverRafRef.current);' not in t:
    t=t.replace('''  useEffect(() => {
    if (graph) startAnimLoop();
    return () => { cancelAnimationFrame(animFrameRef.current); isAnimatingRef.current = false; };
  }, [graph, startAnimLoop]);
''',
'''  useEffect(() => {
    if (graph) startAnimLoop();
    return () => {
      cancelAnimationFrame(animFrameRef.current);
      cancelAnimationFrame(hoverRafRef.current);
      isAnimatingRef.current = false;
    };
  }, [graph, startAnimLoop]);
''')

# connectedNodes optimization map
if 'const nodeById = useMemo(() => {' not in t:
    t=t.replace('''  const connectionCount = selectedNode && graph
    ? graph.edges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id).length
    : 0;

  const connectedNodes = useMemo(() => {
''',
'''  const connectionCount = selectedNode && graph
    ? graph.edges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id).length
    : 0;

  const nodeById = useMemo(() => {
    const m = new Map<string, GNode>();
    if (!graph) return m;
    for (const n of graph.nodes) m.set(n.id, n);
    return m;
  }, [graph]);

  const connectedNodes = useMemo(() => {
''')

 t=t.replace('''        const n = graph.nodes.find(x => x.id === e.target);
        if (n) neighbors.push({ id: n.id, type: n.meta.type, weight: e.weight });
      } else if (e.target === selectedNode.id) {
        const n = graph.nodes.find(x => x.id === e.source);
        if (n) neighbors.push({ id: n.id, type: n.meta.type, weight: e.weight });
''',
'''        const n = nodeById.get(e.target);
        if (n) neighbors.push({ id: n.id, type: n.meta.type, weight: e.weight });
      } else if (e.target === selectedNode.id) {
        const n = nodeById.get(e.source);
        if (n) neighbors.push({ id: n.id, type: n.meta.type, weight: e.weight });
''')

 t=t.replace('  }, [selectedNode, graph]);\n', '  }, [selectedNode, graph, nodeById]);\n')

p.write_text(t,encoding='utf-8')
print('patched NetworkMap adaptive render + hover throttle')
