from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/NetworkMap.tsx')
t=p.read_text(encoding='utf-8')
insert='''
function isPointOnNodeLabel(node: GNode, wx: number, wy: number, vp: Viewport): boolean {
  const fontSize = Math.max(9, Math.round(12 / vp.scale));
  const approxCharW = Math.max(5, fontSize * 0.58);
  const line1 = node.label || '';
  const line2 = node.meta.ips.length > 0 ? node.meta.ips[0] : '';
  const tw = Math.max(line1.length * approxCharW, line2 ? line2.length * approxCharW : 0);
  const px = 5, py = 2;
  const totalH = line2 ? fontSize * 2 + py * 2 : fontSize + py * 2;
  const lx = node.x, ly = node.y - node.radius - 6;
  const rx = lx - tw / 2 - px;
  const ry = ly - totalH;
  const rw = tw + px * 2;
  const rh = totalH;
  return wx >= rx && wx <= (rx + rw) && wy >= ry && wy <= (ry + rh);
}

'''
if 'function isPointOnNodeLabel' not in t:
    t=t.replace('// == Hit-test =============================================================\n', '// == Hit-test =============================================================\n'+insert)

old='''function hitTest(
  graph: Graph, canvas: HTMLCanvasElement, clientX: number, clientY: number, vp: Viewport,
): GNode | null {
  const { wx, wy } = screenToWorld(canvas, clientX, clientY, vp);
  for (const n of graph.nodes) {
    const dx = n.x - wx, dy = n.y - wy;
    if (dx * dx + dy * dy < (n.radius + 5) ** 2) return n;
  }
  return null;
}
'''
new='''function hitTest(
  graph: Graph, canvas: HTMLCanvasElement, clientX: number, clientY: number, vp: Viewport,
): GNode | null {
  const { wx, wy } = screenToWorld(canvas, clientX, clientY, vp);

  // Node-circle hit has priority
  for (const n of graph.nodes) {
    const dx = n.x - wx, dy = n.y - wy;
    if (dx * dx + dy * dy < (n.radius + 5) ** 2) return n;
  }

  // Then label hit (so clicking text works too)
  for (const n of graph.nodes) {
    if (isPointOnNodeLabel(n, wx, wy, vp)) return n;
  }

  return null;
}
'''
if old not in t:
    raise SystemExit('hitTest block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('updated NetworkMap hit-test for labels')
