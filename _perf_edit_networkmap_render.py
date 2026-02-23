from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/NetworkMap.tsx')
t=p.read_text(encoding='utf-8')
repls={
"const LARGE_HUNT_SUBGRAPH_HOSTS = 350;":"const LARGE_HUNT_SUBGRAPH_HOSTS = 220;",
"const LARGE_HUNT_SUBGRAPH_EDGES = 2500;":"const LARGE_HUNT_SUBGRAPH_EDGES = 1200;",
"const RENDER_SIMPLIFY_NODE_THRESHOLD = 220;":"const RENDER_SIMPLIFY_NODE_THRESHOLD = 120;",
"const RENDER_SIMPLIFY_EDGE_THRESHOLD = 1200;":"const RENDER_SIMPLIFY_EDGE_THRESHOLD = 500;",
"const EDGE_DRAW_TARGET = 1000;":"const EDGE_DRAW_TARGET = 600;"
}
for a,b in repls.items():
    if a not in t:
        raise SystemExit(f'missing constant: {a}')
    t=t.replace(a,b)

old='''  // Then label hit (so clicking text works too)
  for (const n of graph.nodes) {
    if (isPointOnNodeLabel(n, wx, wy, vp)) return n;
  }
'''
new='''  // Then label hit (so clicking text works too on manageable graph sizes)
  if (graph.nodes.length <= 220) {
    for (const n of graph.nodes) {
      if (isPointOnNodeLabel(n, wx, wy, vp)) return n;
    }
  }
'''
if old not in t:
    raise SystemExit('label hit block not found')
t=t.replace(old,new)

old2='simulate(g, w / 2, h / 2, 60);'
if t.count(old2) < 2:
    raise SystemExit('expected two simulate calls')
t=t.replace(old2,'simulate(g, w / 2, h / 2, 20);',1)
t=t.replace(old2,'simulate(g, w / 2, h / 2, 30);',1)

p.write_text(t,encoding='utf-8')
print('tightened network map rendering + load limits')
