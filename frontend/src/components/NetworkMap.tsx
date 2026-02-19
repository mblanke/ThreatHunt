/**
 * NetworkMap — interactive hunt-scoped force-directed network graph.
 *
 * • Select a hunt → loads only that hunt's datasets
 * • Nodes = unique IPs / hostnames / domains pulled from IOC columns
 * • Edges = "seen together in the same row" co-occurrence
 * • Click a node → popover showing hostname, IP, OS, dataset sources, connections
 * • Responsive canvas with ResizeObserver
 * • Zero extra npm dependencies
 */

import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import {
  Box, Typography, Paper, Stack, Alert, Chip, Button, TextField,
  LinearProgress, FormControl, InputLabel, Select, MenuItem,
  Popover, Divider, IconButton,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import CloseIcon from '@mui/icons-material/Close';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong';
import { datasets, hunts, type Hunt, type DatasetSummary } from '../api/client';

// ── Graph primitives ─────────────────────────────────────────────────

type NodeType = 'ip' | 'hostname' | 'domain' | 'url';

interface NodeMeta {
  hostnames: Set<string>;
  ips: Set<string>;
  os: Set<string>;
  datasets: Set<string>;
  type: NodeType;
}

interface GNode {
  id: string; label: string; x: number; y: number;
  vx: number; vy: number; radius: number; color: string; count: number;
  meta: { hostnames: string[]; ips: string[]; os: string[]; datasets: string[]; type: NodeType };
}
interface GEdge { source: string; target: string; weight: number }
interface Graph { nodes: GNode[]; edges: GEdge[] }

const TYPE_COLORS: Record<NodeType, string> = {
  ip: '#3b82f6', hostname: '#22c55e', domain: '#eab308', url: '#8b5cf6',
};

// ── Helpers: find context columns from dataset schema ────────────────

/** Best-effort detection of hostname, IP, and OS columns from raw column names + normalized mapping. */
function findContextColumns(ds: DatasetSummary) {
  const norm = ds.normalized_columns || {};
  const schema = ds.column_schema || {};
  const rawCols = Object.keys(schema).length > 0 ? Object.keys(schema) : Object.keys(norm);

  const hostCols: string[] = [];
  const ipCols: string[] = [];
  const osCols: string[] = [];

  for (const raw of rawCols) {
    const canonical = norm[raw] || '';
    const lower = raw.toLowerCase();
    // Hostname columns
    if (canonical === 'hostname' || /^(hostname|host|fqdn|computer_?name|system_?name|machinename)$/i.test(lower)) {
      hostCols.push(raw);
    }
    // IP columns
    if (['src_ip', 'dst_ip', 'ip_address'].includes(canonical) || /^(ip|ip_?address|src_?ip|dst_?ip|source_?ip|dest_?ip)$/i.test(lower)) {
      ipCols.push(raw);
    }
    // OS columns (best-effort — raw name scan + normalized canonical)
    if (canonical === 'os' || /^(os|operating_?system|os_?version|os_?name|platform|os_?type)$/i.test(lower)) {
      osCols.push(raw);
    }
  }
  return { hostCols, ipCols, osCols };
}

function cleanVal(v: any): string {
  const s = (v ?? '').toString().trim();
  return (s && s !== '-' && s !== '0.0.0.0' && s !== '::') ? s : '';
}

// ── Build graph with per-node metadata ───────────────────────────────

interface RowBatch {
  rows: Record<string, any>[];
  iocColumns: Record<string, any>;
  dsName: string;
  ds: DatasetSummary;
}

function buildGraph(allBatches: RowBatch[], canvasW: number, canvasH: number): Graph {
  const countMap = new Map<string, number>();
  const edgeMap = new Map<string, number>();
  const metaMap = new Map<string, NodeMeta>();

  const getOrCreateMeta = (id: string, type: NodeType): NodeMeta => {
    let m = metaMap.get(id);
    if (!m) { m = { hostnames: new Set(), ips: new Set(), os: new Set(), datasets: new Set(), type }; metaMap.set(id, m); }
    return m;
  };

  for (const { rows, iocColumns, dsName, ds } of allBatches) {
    // IOC columns that produce graph nodes
    const iocEntries = Object.entries(iocColumns).filter(([, t]) => {
      const typ = Array.isArray(t) ? t[0] : t;
      return typ === 'ip' || typ === 'hostname' || typ === 'domain' || typ === 'url';
    }).map(([col, t]) => {
      const typ = (Array.isArray(t) ? t[0] : t) as NodeType;
      return { col, typ };
    });

    if (iocEntries.length === 0) continue;

    // Context columns for enrichment
    const ctx = findContextColumns(ds);

    for (const row of rows) {
      // Collect IOC values for this row (nodes + edges)
      const vals: { v: string; typ: NodeType }[] = [];
      for (const { col, typ } of iocEntries) {
        const v = cleanVal(row[col]);
        if (v) vals.push({ v, typ });
      }
      const unique = [...new Map(vals.map(x => [x.v, x])).values()];

      // Count occurrences
      for (const { v } of unique) countMap.set(v, (countMap.get(v) ?? 0) + 1);

      // Create edges (co-occurrence)
      for (let i = 0; i < unique.length; i++) {
        for (let j = i + 1; j < unique.length; j++) {
          const key = [unique[i].v, unique[j].v].sort().join('||');
          edgeMap.set(key, (edgeMap.get(key) ?? 0) + 1);
        }
      }

      // Extract context values from this row
      const rowHosts = ctx.hostCols.map(c => cleanVal(row[c])).filter(Boolean);
      const rowIps = ctx.ipCols.map(c => cleanVal(row[c])).filter(Boolean);
      const rowOs = ctx.osCols.map(c => cleanVal(row[c])).filter(Boolean);

      // Attach context to each node in this row
      for (const { v, typ } of unique) {
        const meta = getOrCreateMeta(v, typ);
        meta.datasets.add(dsName);
        for (const h of rowHosts) meta.hostnames.add(h);
        for (const ip of rowIps) meta.ips.add(ip);
        for (const o of rowOs) meta.os.add(o);
      }
    }
  }

  const nodes: GNode[] = [...countMap.entries()].map(([id, count]) => {
    const raw = metaMap.get(id);
    const type: NodeType = raw?.type || 'ip';
    return {
      id, label: id, count,
      x: canvasW / 2 + (Math.random() - 0.5) * canvasW * 0.75,
      y: canvasH / 2 + (Math.random() - 0.5) * canvasH * 0.65,
      vx: 0, vy: 0,
      radius: Math.max(5, Math.min(18, 4 + Math.sqrt(count) * 1.6)),
      color: TYPE_COLORS[type],
      meta: {
        hostnames: [...(raw?.hostnames ?? [])],
        ips: [...(raw?.ips ?? [])],
        os: [...(raw?.os ?? [])],
        datasets: [...(raw?.datasets ?? [])],
        type,
      },
    };
  });

  const edges: GEdge[] = [...edgeMap.entries()].map(([key, weight]) => {
    const [source, target] = key.split('||');
    return { source, target, weight };
  });

  return { nodes, edges };
}

// ── Force simulation ─────────────────────────────────────────────────

function simulate(graph: Graph, cx: number, cy: number, steps = 120) {
  const { nodes, edges } = graph;
  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  const k = 80;
  const repulsion = 6000;
  const damping = 0.85;

  for (let step = 0; step < steps; step++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const force = repulsion / (dist * dist);
        const fx = (dx / dist) * force, fy = (dy / dist) * force;
        a.vx -= fx; a.vy -= fy;
        b.vx += fx; b.vy += fy;
      }
    }
    for (const e of edges) {
      const a = nodeMap.get(e.source), b = nodeMap.get(e.target);
      if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const force = (dist - k) * 0.05;
      const fx = (dx / dist) * force, fy = (dy / dist) * force;
      a.vx += fx; a.vy += fy;
      b.vx -= fx; b.vy -= fy;
    }
    for (const n of nodes) {
      n.vx += (cx - n.x) * 0.001;
      n.vy += (cy - n.y) * 0.001;
      n.vx *= damping; n.vy *= damping;
      n.x += n.vx; n.y += n.vy;
    }
  }
}

// ── Viewport (zoom / pan) ────────────────────────────────────────────

interface Viewport { x: number; y: number; scale: number }

const MIN_ZOOM = 0.1;
const MAX_ZOOM = 8;

// ── Canvas renderer ──────────────────────────────────────────────────

function drawGraph(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null, search: string,
  vp: Viewport,
) {
  const { nodes, edges } = graph;
  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  const matchSet = new Set<string>();
  if (search) {
    const lc = search.toLowerCase();
    for (const n of nodes) if (n.label.toLowerCase().includes(lc)) matchSet.add(n.id);
  }

  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  ctx.save();
  ctx.translate(vp.x, vp.y);
  ctx.scale(vp.scale, vp.scale);

  // Edges
  for (const e of edges) {
    const a = nodeMap.get(e.source), b = nodeMap.get(e.target);
    if (!a || !b) continue;
    const isActive = (hovered && (e.source === hovered || e.target === hovered))
      || (selected && (e.source === selected || e.target === selected));
    ctx.beginPath();
    ctx.strokeStyle = isActive ? 'rgba(96,165,250,0.7)' : 'rgba(100,116,139,0.25)';
    ctx.lineWidth = Math.min(4, 0.5 + e.weight * 0.3) / vp.scale;
    ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  }

  // Nodes
  for (const n of nodes) {
    const highlighted = hovered === n.id || selected === n.id || (search && matchSet.has(n.id));
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
    ctx.fillStyle = highlighted ? '#fff' : n.color;
    ctx.globalAlpha = (search && !matchSet.has(n.id)) ? 0.15 : 1;
    ctx.fill();
    ctx.globalAlpha = 1;
    if (highlighted) { ctx.strokeStyle = n.color; ctx.lineWidth = 2.5 / vp.scale; ctx.stroke(); }
  }

  // Labels — show more labels when zoomed in
  const labelThreshold = Math.max(1, Math.round(3 / vp.scale));
  const fontSize = Math.max(8, Math.round(11 / vp.scale));
  ctx.font = `${fontSize}px Inter, sans-serif`;
  ctx.textAlign = 'center';
  for (const n of nodes) {
    const show = hovered === n.id || selected === n.id
      || (search && matchSet.has(n.id)) || n.count >= labelThreshold;
    if (!show) continue;
    ctx.fillStyle = (search && !matchSet.has(n.id)) ? 'rgba(241,245,249,0.15)' : '#f1f5f9';
    ctx.fillText(n.label, n.x, n.y - n.radius - 5);
  }

  ctx.restore();
}

// ── Hit-test helper (viewport-aware) ─────────────────────────────────

function screenToWorld(
  canvas: HTMLCanvasElement, clientX: number, clientY: number, vp: Viewport,
): { wx: number; wy: number } {
  const rect = canvas.getBoundingClientRect();
  const cssToCanvas_x = canvas.width / rect.width;
  const cssToCanvas_y = canvas.height / rect.height;
  const cx = (clientX - rect.left) * cssToCanvas_x;
  const cy = (clientY - rect.top) * cssToCanvas_y;
  return { wx: (cx - vp.x) / vp.scale, wy: (cy - vp.y) / vp.scale };
}

function hitTest(
  graph: Graph, canvas: HTMLCanvasElement, clientX: number, clientY: number,
  vp: Viewport,
): GNode | null {
  const { wx, wy } = screenToWorld(canvas, clientX, clientY, vp);
  for (const n of graph.nodes) {
    const dx = n.x - wx, dy = n.y - wy;
    if (dx * dx + dy * dy < (n.radius + 4) ** 2) return n;
  }
  return null;
}

// ── Component ────────────────────────────────────────────────────────

export default function NetworkMap() {
  // Hunt selector
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [selectedHuntId, setSelectedHuntId] = useState('');

  // Graph state
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [graph, setGraph] = useState<Graph | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GNode | null>(null);
  const [search, setSearch] = useState('');
  const [dsCount, setDsCount] = useState(0);
  const [totalRows, setTotalRows] = useState(0);

  // Node type filters
  const [visibleTypes, setVisibleTypes] = useState<Set<NodeType>>(
    new Set<NodeType>(['ip', 'hostname', 'domain', 'url']),
  );

  // Canvas sizing
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [canvasSize, setCanvasSize] = useState({ w: 900, h: 600 });

  // Viewport (zoom / pan)
  const vpRef = useRef<Viewport>({ x: 0, y: 0, scale: 1 });
  const [vpScale, setVpScale] = useState(1);  // for UI display only
  const isPanning = useRef(false);
  const panStart = useRef({ x: 0, y: 0 });

  // Popover anchor
  const [popoverAnchor, setPopoverAnchor] = useState<{ top: number; left: number } | null>(null);

  // ── Load hunts on mount ────────────────────────────────────────────
  useEffect(() => {
    hunts.list(0, 200).then(r => setHuntList(r.hunts)).catch(() => {});
  }, []);

  // ── Resize observer ────────────────────────────────────────────────
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        const w = Math.round(entry.contentRect.width);
        if (w > 100) setCanvasSize({ w, h: Math.max(450, Math.round(w * 0.55)) });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ── Load graph for selected hunt ──────────────────────────────────
  const loadGraph = useCallback(async (huntId: string) => {
    if (!huntId) return;
    setLoading(true); setError(''); setGraph(null);
    setSelectedNode(null); setPopoverAnchor(null);
    try {
      setProgress('Fetching datasets for hunt…');
      const dsRes = await datasets.list(0, 500, huntId);
      const dsList = dsRes.datasets;
      setDsCount(dsList.length);

      if (dsList.length === 0) {
        setError('This hunt has no datasets. Upload CSV files to this hunt first.');
        setLoading(false); setProgress('');
        return;
      }

      const allBatches: RowBatch[] = [];
      let rowTotal = 0;

      for (let i = 0; i < dsList.length; i++) {
        const ds = dsList[i];
        setProgress(`Loading ${ds.name} (${i + 1}/${dsList.length})…`);
        try {
          const detail = await datasets.get(ds.id);
          const ioc = detail.ioc_columns || {};
          const hasIoc = Object.values(ioc).some(t => {
            const typ = Array.isArray(t) ? t[0] : t;
            return typ === 'ip' || typ === 'hostname' || typ === 'domain' || typ === 'url';
          });
          if (hasIoc) {
            const r = await datasets.rows(ds.id, 0, 5000);
            allBatches.push({ rows: r.rows, iocColumns: ioc, dsName: ds.name, ds: detail });
            rowTotal += r.rows.length;
          }
        } catch { /* skip failed datasets */ }
      }

      setTotalRows(rowTotal);

      if (allBatches.length === 0) {
        setError('No datasets in this hunt contain IP/hostname/domain IOC columns.');
        setLoading(false); setProgress('');
        return;
      }

      setProgress('Building graph…');
      const g = buildGraph(allBatches, canvasSize.w, canvasSize.h);
      if (g.nodes.length === 0) {
        setError('No network nodes found in the data.');
      } else {
        simulate(g, canvasSize.w / 2, canvasSize.h / 2);
        setGraph(g);
      }
    } catch (e: any) { setError(e.message); }
    setLoading(false); setProgress('');
  }, [canvasSize]);

  // When hunt changes, load graph
  useEffect(() => {
    if (selectedHuntId) loadGraph(selectedHuntId);
  }, [selectedHuntId, loadGraph]);

  // Reset viewport when graph changes
  useEffect(() => {
    vpRef.current = { x: 0, y: 0, scale: 1 };
    setVpScale(1);
  }, [graph]);

  // Filtered graph — only visible node types + edges between them
  const filteredGraph = useMemo<Graph | null>(() => {
    if (!graph) return null;
    const nodes = graph.nodes.filter(n => visibleTypes.has(n.meta.type));
    const nodeIds = new Set(nodes.map(n => n.id));
    const edges = graph.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target));
    return { nodes, edges };
  }, [graph, visibleTypes]);

  // Toggle a node type filter
  const toggleType = useCallback((t: NodeType) => {
    setVisibleTypes(prev => {
      const next = new Set(prev);
      if (next.has(t)) {
        // Don't allow all to be hidden
        if (next.size > 1) next.delete(t);
      } else {
        next.add(t);
      }
      return next;
    });
  }, []);

  // Redraw helper — uses filteredGraph
  const redraw = useCallback(() => {
    if (!filteredGraph || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext('2d');
    if (ctx) drawGraph(ctx, filteredGraph, hovered, selectedNode?.id ?? null, search, vpRef.current);
  }, [filteredGraph, hovered, selectedNode, search]);

  // Redraw on every render-affecting state change
  useEffect(() => { redraw(); }, [redraw]);

  // ── Mouse wheel → zoom ─────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const vp = vpRef.current;
      const rect = canvas.getBoundingClientRect();
      const cssToCanvasX = canvas.width / rect.width;
      const cssToCanvasY = canvas.height / rect.height;
      // Mouse position in canvas pixel coords
      const mx = (e.clientX - rect.left) * cssToCanvasX;
      const my = (e.clientY - rect.top) * cssToCanvasY;

      const zoomFactor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      const newScale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, vp.scale * zoomFactor));
      // Zoom toward cursor: adjust offset so world-point under cursor stays fixed
      vp.x = mx - (mx - vp.x) * (newScale / vp.scale);
      vp.y = my - (my - vp.y) * (newScale / vp.scale);
      vp.scale = newScale;
      setVpScale(newScale);
      // Immediate redraw (bypass React state for smoothness)
      const ctx = canvas.getContext('2d');
      if (ctx && filteredGraph) drawGraph(ctx, filteredGraph, hovered, selectedNode?.id ?? null, search, vp);
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, [filteredGraph, hovered, selectedNode, search]);

  // ── Mouse drag → pan ───────────────────────────────────────────────
  const onMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!filteredGraph || !canvasRef.current) return;
    const node = hitTest(filteredGraph, canvasRef.current, e.clientX, e.clientY, vpRef.current);
    if (!node) {
      isPanning.current = true;
      panStart.current = { x: e.clientX, y: e.clientY };
    }
  }, [filteredGraph]);

  const onMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!filteredGraph || !canvasRef.current) return;

    if (isPanning.current) {
      const vp = vpRef.current;
      const rect = canvasRef.current.getBoundingClientRect();
      const cssToCanvasX = canvasRef.current.width / rect.width;
      const cssToCanvasY = canvasRef.current.height / rect.height;
      vp.x += (e.clientX - panStart.current.x) * cssToCanvasX;
      vp.y += (e.clientY - panStart.current.y) * cssToCanvasY;
      panStart.current = { x: e.clientX, y: e.clientY };
      redraw();
      return;
    }

    const node = hitTest(filteredGraph, canvasRef.current, e.clientX, e.clientY, vpRef.current);
    setHovered(node?.id ?? null);
  }, [filteredGraph, redraw]);

  const onMouseUp = useCallback(() => {
    isPanning.current = false;
  }, []);

  // ── Mouse click → select node + show popover ─────────────────────
  const onClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!filteredGraph || !canvasRef.current) return;
    const node = hitTest(filteredGraph, canvasRef.current, e.clientX, e.clientY, vpRef.current);
    if (node) {
      setSelectedNode(node);
      setPopoverAnchor({ top: e.clientY, left: e.clientX });
    } else {
      setSelectedNode(null);
      setPopoverAnchor(null);
    }
  }, [filteredGraph]);

  const closePopover = () => { setSelectedNode(null); setPopoverAnchor(null); };

  // ── Zoom controls ──────────────────────────────────────────────────
  const zoomBy = useCallback((factor: number) => {
    const vp = vpRef.current;
    const cw = canvasSize.w, ch = canvasSize.h;
    const newScale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, vp.scale * factor));
    // Zoom toward canvas center
    vp.x = cw / 2 - (cw / 2 - vp.x) * (newScale / vp.scale);
    vp.y = ch / 2 - (ch / 2 - vp.y) * (newScale / vp.scale);
    vp.scale = newScale;
    setVpScale(newScale);
    redraw();
  }, [canvasSize, redraw]);

  const resetView = useCallback(() => {
    vpRef.current = { x: 0, y: 0, scale: 1 };
    setVpScale(1);
    redraw();
  }, [redraw]);

  // Count connections for selected node
  const connectionCount = selectedNode && filteredGraph
    ? filteredGraph.edges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id).length
    : 0;

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <Box>
      {/* Header row */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }} flexWrap="wrap" gap={1}>
        <Typography variant="h5">Network Map</Typography>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel id="hunt-selector-label">Hunt</InputLabel>
            <Select
              labelId="hunt-selector-label"
              value={selectedHuntId}
              label="Hunt"
              onChange={e => setSelectedHuntId(e.target.value)}
            >
              {huntList.map(h => (
                <MenuItem key={h.id} value={h.id}>
                  {h.name} ({h.dataset_count} datasets)
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField size="small" placeholder="Search node…" value={search}
            onChange={e => setSearch(e.target.value)} sx={{ width: 200 }} />
          <Button variant="outlined" startIcon={<RefreshIcon />}
            onClick={() => loadGraph(selectedHuntId)}
            disabled={loading || !selectedHuntId} size="small">
            Refresh
          </Button>
        </Stack>
      </Stack>

      {/* Loading indicator */}
      {loading && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>{progress}</Typography>
          <LinearProgress />
        </Paper>
      )}

      {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Legend — clickable type filters */}
      {graph && filteredGraph && (
        <Stack direction="row" spacing={1} sx={{ mb: 1 }} flexWrap="wrap" gap={0.5} alignItems="center">
          <Chip label={`${dsCount} datasets`} size="small" variant="outlined" />
          <Chip label={`${totalRows.toLocaleString()} rows`} size="small" variant="outlined" />
          <Chip label={`${filteredGraph.nodes.length} nodes`} size="small" color="primary" variant="outlined" />
          <Chip label={`${filteredGraph.edges.length} edges`} size="small" color="secondary" variant="outlined" />
          <Divider orientation="vertical" flexItem />
          {([['ip', 'IP'], ['hostname', 'Host'], ['domain', 'Domain'], ['url', 'URL']] as [NodeType, string][]).map(([type, label]) => {
            const active = visibleTypes.has(type);
            const count = graph.nodes.filter(n => n.meta.type === type).length;
            return (
              <Chip
                key={type}
                label={`${label} (${count})`}
                size="small"
                onClick={() => toggleType(type)}
                sx={{
                  bgcolor: active ? TYPE_COLORS[type] : 'transparent',
                  color: active ? '#fff' : TYPE_COLORS[type],
                  border: `2px solid ${TYPE_COLORS[type]}`,
                  fontWeight: 600,
                  cursor: 'pointer',
                  opacity: active ? 1 : 0.5,
                  transition: 'all 0.15s ease',
                  '&:hover': { opacity: 1 },
                }}
              />
            );
          })}
        </Stack>
      )}

      {/* Canvas */}
      {filteredGraph && (
        <Paper ref={wrapperRef} sx={{ p: 1, position: 'relative', backgroundColor: '#0f172a' }}>
          <canvas
            ref={canvasRef}
            width={canvasSize.w} height={canvasSize.h}
            style={{
              width: '100%', height: canvasSize.h,
              cursor: isPanning.current ? 'grabbing' : hovered ? 'pointer' : 'grab',
            }}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={() => { isPanning.current = false; setHovered(null); }}
            onClick={onClick}
          />
          {/* Zoom controls overlay */}
          <Stack
            direction="column" spacing={0.5}
            sx={{ position: 'absolute', top: 12, right: 12, zIndex: 2 }}
          >
            <IconButton size="small" onClick={() => zoomBy(1.3)}
              sx={{ bgcolor: 'rgba(30,41,59,0.85)', color: '#f1f5f9', '&:hover': { bgcolor: 'rgba(51,65,85,0.95)' } }}
              aria-label="Zoom in"><ZoomInIcon fontSize="small" /></IconButton>
            <IconButton size="small" onClick={() => zoomBy(1 / 1.3)}
              sx={{ bgcolor: 'rgba(30,41,59,0.85)', color: '#f1f5f9', '&:hover': { bgcolor: 'rgba(51,65,85,0.95)' } }}
              aria-label="Zoom out"><ZoomOutIcon fontSize="small" /></IconButton>
            <IconButton size="small" onClick={resetView}
              sx={{ bgcolor: 'rgba(30,41,59,0.85)', color: '#f1f5f9', '&:hover': { bgcolor: 'rgba(51,65,85,0.95)' } }}
              aria-label="Reset view"><CenterFocusStrongIcon fontSize="small" /></IconButton>
            <Chip label={`${Math.round(vpScale * 100)}%`} size="small"
              sx={{ bgcolor: 'rgba(30,41,59,0.85)', color: '#94a3b8', fontSize: 11, height: 22 }} />
          </Stack>
        </Paper>
      )}

      {/* Node detail popover */}
      <Popover
        open={Boolean(selectedNode && popoverAnchor)}
        anchorReference="anchorPosition"
        anchorPosition={popoverAnchor ?? undefined}
        onClose={closePopover}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{ paper: { sx: { p: 2, minWidth: 280, maxWidth: 400 } } }}
      >
        {selectedNode && (
          <Box>
            <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography variant="subtitle1" fontWeight={700}>{selectedNode.label}</Typography>
                <Chip label={selectedNode.meta.type.toUpperCase()} size="small"
                  sx={{ bgcolor: TYPE_COLORS[selectedNode.meta.type], color: '#fff', fontWeight: 600, fontSize: 11 }} />
              </Stack>
              <IconButton size="small" onClick={closePopover} aria-label="close"><CloseIcon fontSize="small" /></IconButton>
            </Stack>
            <Divider sx={{ mb: 1.5 }} />

            {/* Hostnames */}
            <Typography variant="caption" color="text.secondary" fontWeight={600}>Hostname</Typography>
            <Typography variant="body2" sx={{ mb: 1 }}>
              {selectedNode.meta.hostnames.length > 0
                ? selectedNode.meta.hostnames.join(', ')
                : <em>Unknown</em>}
            </Typography>

            {/* IPs */}
            <Typography variant="caption" color="text.secondary" fontWeight={600}>IP Address</Typography>
            <Typography variant="body2" sx={{ mb: 1, fontFamily: 'monospace' }}>
              {selectedNode.meta.ips.length > 0
                ? selectedNode.meta.ips.join(', ')
                : (selectedNode.meta.type === 'ip' ? selectedNode.label : <em>Unknown</em>)}
            </Typography>

            {/* OS */}
            <Typography variant="caption" color="text.secondary" fontWeight={600}>Operating System</Typography>
            <Typography variant="body2" sx={{ mb: 1 }}>
              {selectedNode.meta.os.length > 0
                ? selectedNode.meta.os.join(', ')
                : <em>Unknown</em>}
            </Typography>

            <Divider sx={{ my: 1 }} />

            {/* Stats */}
            <Stack direction="row" spacing={1} flexWrap="wrap" gap={0.5}>
              <Chip label={`${selectedNode.count} occurrences`} size="small" variant="outlined" />
              <Chip label={`${connectionCount} connections`} size="small" variant="outlined" />
            </Stack>

            {/* Datasets */}
            {selectedNode.meta.datasets.length > 0 && (
              <Box sx={{ mt: 1.5 }}>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>Seen in datasets</Typography>
                <Stack direction="row" spacing={0.5} flexWrap="wrap" gap={0.5} sx={{ mt: 0.5 }}>
                  {selectedNode.meta.datasets.map(d => (
                    <Chip key={d} label={d} size="small" variant="outlined" />
                  ))}
                </Stack>
              </Box>
            )}
          </Box>
        )}
      </Popover>

      {/* Empty states */}
      {!selectedHuntId && !loading && (
        <Paper ref={wrapperRef} sx={{ p: 6, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Select a hunt to visualize its network
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Choose a hunt from the dropdown above. The map will display IP addresses,
            hostnames, and domains found across the hunt's datasets, with connections
            showing co-occurrence in the same log rows.
          </Typography>
        </Paper>
      )}

      {selectedHuntId && !graph && !loading && !error && (
        <Paper sx={{ p: 6, textAlign: 'center' }}>
          <Typography color="text.secondary">
            No network data to display. Upload datasets with IP/hostname columns to this hunt.
          </Typography>
        </Paper>
      )}
    </Box>
  );
}
