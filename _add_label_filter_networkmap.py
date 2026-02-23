from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/NetworkMap.tsx')
t=p.read_text(encoding='utf-8')

# 1) Add label mode type near graph types
marker="interface GEdge { source: string; target: string; weight: number }\ninterface Graph { nodes: GNode[]; edges: GEdge[] }\n"
if marker in t and "type LabelMode" not in t:
    t=t.replace(marker, marker+"\ntype LabelMode = 'all' | 'highlight' | 'none';\n")

# 2) extend drawLabels signature
old_sig="""function drawLabels(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null,
  search: string, matchSet: Set<string>, vp: Viewport,
  simplify: boolean,
) {
"""
new_sig="""function drawLabels(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null,
  search: string, matchSet: Set<string>, vp: Viewport,
  simplify: boolean, labelMode: LabelMode,
) {
"""
if old_sig in t:
    t=t.replace(old_sig,new_sig)

# 3) label mode guards inside drawLabels
old_guard="""  const dimmed = search.length > 0;
  if (simplify && !search && !hovered && !selected) {
    return;
  }
"""
new_guard="""  if (labelMode === 'none') return;
  const dimmed = search.length > 0;
  if (labelMode === 'highlight' && !search && !hovered && !selected) return;
  if (simplify && labelMode !== 'all' && !search && !hovered && !selected) {
    return;
  }
"""
if old_guard in t:
    t=t.replace(old_guard,new_guard)

old_show="""    const isHighlight = hovered === n.id || selected === n.id || matchSet.has(n.id);
    const show = isHighlight || n.meta.type === 'host' || n.count >= 2;
    if (!show) continue;
"""
new_show="""    const isHighlight = hovered === n.id || selected === n.id || matchSet.has(n.id);
    const show = labelMode === 'all'
      ? (isHighlight || n.meta.type === 'host' || n.count >= 2)
      : isHighlight;
    if (!show) continue;
"""
if old_show in t:
    t=t.replace(old_show,new_show)

# 4) drawGraph signature and call site
old_graph_sig="""function drawGraph(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null, search: string,
  vp: Viewport, animTime: number, dpr: number,
) {
"""
new_graph_sig="""function drawGraph(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null, search: string,
  vp: Viewport, animTime: number, dpr: number, labelMode: LabelMode,
) {
"""
if old_graph_sig in t:
    t=t.replace(old_graph_sig,new_graph_sig)

old_drawlabels_call="drawLabels(ctx, graph, hovered, selected, search, matchSet, vp, simplify);"
new_drawlabels_call="drawLabels(ctx, graph, hovered, selected, search, matchSet, vp, simplify, labelMode);"
if old_drawlabels_call in t:
    t=t.replace(old_drawlabels_call,new_drawlabels_call)

# 5) state for label mode
state_anchor="  const [selectedNode, setSelectedNode] = useState<GNode | null>(null);\n  const [search, setSearch] = useState('');\n"
state_new="  const [selectedNode, setSelectedNode] = useState<GNode | null>(null);\n  const [search, setSearch] = useState('');\n  const [labelMode, setLabelMode] = useState<LabelMode>('highlight');\n"
if state_anchor in t:
    t=t.replace(state_anchor,state_new)

# 6) pass labelMode in draw calls
old_tick_draw="drawGraph(ctx, g, hoveredRef.current, selectedNodeRef.current?.id ?? null, searchRef.current, vpRef.current, ts, dpr);"
new_tick_draw="drawGraph(ctx, g, hoveredRef.current, selectedNodeRef.current?.id ?? null, searchRef.current, vpRef.current, ts, dpr, labelMode);"
if old_tick_draw in t:
    t=t.replace(old_tick_draw,new_tick_draw)

old_redraw_draw="if (ctx) drawGraph(ctx, graph, hovered, selectedNode?.id ?? null, search, vpRef.current, animTimeRef.current, dpr);"
new_redraw_draw="if (ctx) drawGraph(ctx, graph, hovered, selectedNode?.id ?? null, search, vpRef.current, animTimeRef.current, dpr, labelMode);"
if old_redraw_draw in t:
    t=t.replace(old_redraw_draw,new_redraw_draw)

# 7) include labelMode in redraw deps
old_redraw_dep="] , [graph, hovered, selectedNode, search]);"
if old_redraw_dep in t:
    t=t.replace(old_redraw_dep, "] , [graph, hovered, selectedNode, search, labelMode]);")
else:
    t=t.replace("  }, [graph, hovered, selectedNode, search]);","  }, [graph, hovered, selectedNode, search, labelMode]);")

# 8) Add toolbar selector after search field
search_block="""        <TextField
          size="small"
          placeholder="Search hosts, IPs, users\u2026"
          value={search}
          onChange={e => setSearch(e.target.value)}
          sx={{ width: 220, '& .MuiInputBase-input': { py: 0.8 } }}
          slotProps={{
            input: {
              startAdornment: <SearchIcon sx={{ mr: 0.5, fontSize: 18, color: 'text.secondary' }} />,
            },
          }}
        />
"""
label_block="""        <TextField
          size="small"
          placeholder="Search hosts, IPs, users\u2026"
          value={search}
          onChange={e => setSearch(e.target.value)}
          sx={{ width: 220, '& .MuiInputBase-input': { py: 0.8 } }}
          slotProps={{
            input: {
              startAdornment: <SearchIcon sx={{ mr: 0.5, fontSize: 18, color: 'text.secondary' }} />,
            },
          }}
        />

        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel id="label-mode-selector">Labels</InputLabel>
          <Select
            labelId="label-mode-selector"
            value={labelMode}
            label="Labels"
            onChange={e => setLabelMode(e.target.value as LabelMode)}
            sx={{ '& .MuiSelect-select': { py: 0.8 } }}
          >
            <MenuItem value="none">None</MenuItem>
            <MenuItem value="highlight">Selected/Search</MenuItem>
            <MenuItem value="all">All</MenuItem>
          </Select>
        </FormControl>
"""
if search_block in t:
    t=t.replace(search_block,label_block)

p.write_text(t,encoding='utf-8')
print('added network map label filter control and renderer modes')
