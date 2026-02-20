/**
 * NetworkMap - Host-centric force-directed network graph.
 *
 * Loads a deduplicated host inventory from the backend, showing one node
 * per unique host with hostname, IPs, OS, logged-in users, and network
 * connections. No more duplicated IOC nodes.
 *
 * Features:
 * - Calls /api/network/host-inventory for clean, deduped host data
 * - HiDPI / Retina canvas rendering
 * - Radial-gradient nodes with neon glow effects
 * - Curved edges with animated flow on active connections
 * - Animated force-directed layout
 * - Node drag with springy neighbor physics
 * - Glassmorphism toolbar + floating legend overlay
 * - Rich popover: hostname, IP, OS, users, datasets
 * - Zero extra npm dependencies
 */

import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import {
  Box, Typography, Paper, Stack, Alert, Chip, TextField,
  LinearProgress, FormControl, InputLabel, Select, MenuItem,
  Popover, Divider, IconButton, Tooltip, Fade, useTheme,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import CloseIcon from '@mui/icons-material/Close';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong';
import HubIcon from '@mui/icons-material/Hub';
import SearchIcon from '@mui/icons-material/Search';
import ComputerIcon from '@mui/icons-material/Computer';
import {
  hunts, network,
  type Hunt, type InventoryHost, type InventoryConnection, type InventoryStats,
} from '../api/client';

// == Graph primitives =====================================================

type NodeType = 'host' | 'external_ip';

interface GNode {
  id: string; label: string; x: number; y: number;
  vx: number; vy: number; radius: number; color: string; count: number;
  pinned?: boolean;
  meta: {
    type: NodeType;
    hostname: string;
    fqdn: string;
    client_id: string;
    ips: string[];
    os: string;
    users: string[];
    datasets: string[];
    row_count: number;
  };
}
interface GEdge { source: string; target: string; weight: number }
interface Graph { nodes: GNode[]; edges: GEdge[] }

const TYPE_COLORS: Record<NodeType, string> = {
  host: '#60a5fa',
  external_ip: '#fbbf24',
};
const GLOW_COLORS: Record<NodeType, string> = {
  host: 'rgba(96,165,250,0.45)',
  external_ip: 'rgba(251,191,36,0.35)',
};

// == Build graph from inventory ==========================================

function buildGraphFromInventory(
  hosts: InventoryHost[], connections: InventoryConnection[],
  canvasW: number, canvasH: number,
): Graph {
  const nodeMap = new Map<string, GNode>();

  // Create host nodes
  for (const h of hosts) {
    const r = Math.max(8, Math.min(26, 6 + Math.sqrt(h.row_count / 100) * 3));
    nodeMap.set(h.id, {
      id: h.id,
      label: h.hostname || h.fqdn || h.client_id,
      x: canvasW / 2 + (Math.random() - 0.5) * canvasW * 0.75,
      y: canvasH / 2 + (Math.random() - 0.5) * canvasH * 0.65,
      vx: 0, vy: 0, radius: r,
      color: TYPE_COLORS.host,
      count: h.row_count,
      meta: {
        type: 'host' as NodeType,
        hostname: h.hostname,
        fqdn: h.fqdn,
        client_id: h.client_id,
        ips: h.ips,
        os: h.os,
        users: h.users,
        datasets: h.datasets,
        row_count: h.row_count,
      },
    });
  }

  // Create edges + external IP nodes (for unresolved remote IPs)
  const edges: GEdge[] = [];
  for (const c of connections) {
    if (!nodeMap.has(c.target)) {
      nodeMap.set(c.target, {
        id: c.target,
        label: c.target_ip || c.target,
        x: canvasW / 2 + (Math.random() - 0.5) * canvasW * 0.75,
        y: canvasH / 2 + (Math.random() - 0.5) * canvasH * 0.65,
        vx: 0, vy: 0, radius: 6,
        color: TYPE_COLORS.external_ip,
        count: c.count,
        meta: {
          type: 'external_ip' as NodeType,
          hostname: '', fqdn: '', client_id: '',
          ips: [c.target_ip || c.target],
          os: '', users: [], datasets: [], row_count: 0,
        },
      });
    }
    edges.push({ source: c.source, target: c.target, weight: c.count });
  }

  return { nodes: [...nodeMap.values()], edges };
}

// == Simulation ===========================================================

function simulationStep(graph: Graph, cx: number, cy: number, alpha: number) {
  const { nodes, edges } = graph;
  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  const k = 120;
  const repulsion = 12000;
  const damping = 0.82;

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      if (a.pinned && b.pinned) continue;
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const force = (repulsion * alpha) / (dist * dist);
      const fx = (dx / dist) * force, fy = (dy / dist) * force;
      if (!a.pinned) { a.vx -= fx; a.vy -= fy; }
      if (!b.pinned) { b.vx += fx; b.vy += fy; }
    }
  }
  for (const e of edges) {
    const a = nodeMap.get(e.source), b = nodeMap.get(e.target);
    if (!a || !b) continue;
    const dx = b.x - a.x, dy = b.y - a.y;
    const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
    const force = (dist - k) * 0.06 * alpha;
    const fx = (dx / dist) * force, fy = (dy / dist) * force;
    if (!a.pinned) { a.vx += fx; a.vy += fy; }
    if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
  }
  for (const n of nodes) {
    if (n.pinned) continue;
    n.vx += (cx - n.x) * 0.0012 * alpha;
    n.vy += (cy - n.y) * 0.0012 * alpha;
    n.vx *= damping; n.vy *= damping;
    n.x += n.vx; n.y += n.vy;
  }
}

function simulate(graph: Graph, cx: number, cy: number, steps = 150) {
  for (let i = 0; i < steps; i++) {
    const alpha = 1 - i / steps;
    simulationStep(graph, cx, cy, Math.max(0.05, alpha));
  }
}

// == Viewport =============================================================

interface Viewport { x: number; y: number; scale: number }
const MIN_ZOOM = 0.08;
const MAX_ZOOM = 10;

// == Canvas renderer =====================================================

const BG_COLOR = '#0a101e';
const GRID_DOT_COLOR = 'rgba(148,163,184,0.04)';
const GRID_SPACING = 32;

function drawBackground(
  ctx: CanvasRenderingContext2D, w: number, h: number, vp: Viewport, dpr: number,
) {
  ctx.fillStyle = BG_COLOR;
  ctx.fillRect(0, 0, w, h);
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
  const vignette = ctx.createRadialGradient(w / 2, h / 2, w * 0.2, w / 2, h / 2, w * 0.7);
  vignette.addColorStop(0, 'rgba(10,16,30,0)');
  vignette.addColorStop(1, 'rgba(10,16,30,0.55)');
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, w, h);
}

function drawEdges(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null,
  nodeMap: Map<string, GNode>, animTime: number,
) {
  for (const e of graph.edges) {
    const a = nodeMap.get(e.source), b = nodeMap.get(e.target);
    if (!a || !b) continue;
    const isActive = (hovered && (e.source === hovered || e.target === hovered))
      || (selected && (e.source === selected || e.target === selected));
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    const dx = b.x - a.x, dy = b.y - a.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    const perpScale = Math.min(20, len * 0.08);
    const cpx = mx + (-dy / (len || 1)) * perpScale;
    const cpy = my + (dx / (len || 1)) * perpScale;

    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(cpx, cpy, b.x, b.y);

    if (isActive) {
      ctx.strokeStyle = 'rgba(96,165,250,0.8)';
      ctx.lineWidth = Math.min(3.5, 1 + e.weight * 0.15);
      ctx.setLineDash([6, 4]); ctx.lineDashOffset = -animTime * 0.03;
      ctx.stroke(); ctx.setLineDash([]);
      ctx.save();
      ctx.shadowColor = 'rgba(96,165,250,0.5)'; ctx.shadowBlur = 8;
      ctx.strokeStyle = 'rgba(96,165,250,0.3)';
      ctx.lineWidth = Math.min(5, 2 + e.weight * 0.2);
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(cpx, cpy, b.x, b.y);
      ctx.stroke(); ctx.restore();
    } else {
      const alpha = Math.min(0.35, 0.08 + e.weight * 0.01);
      ctx.strokeStyle = `rgba(100,116,139,${alpha})`;
      ctx.lineWidth = Math.min(2.5, 0.4 + e.weight * 0.08);
      ctx.stroke();
    }
  }
}

function drawNodes(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null,
  search: string, matchSet: Set<string>,
) {
  const dimmed = search.length > 0;
  for (const n of graph.nodes) {
    const isHighlight = hovered === n.id || selected === n.id || (search && matchSet.has(n.id));
    const isDim = dimmed && !matchSet.has(n.id);
    ctx.save();
    ctx.globalAlpha = isDim ? 0.12 : 1;

    if (isHighlight && !isDim) {
      ctx.save();
      ctx.shadowColor = GLOW_COLORS[n.meta.type] || 'rgba(96,165,250,0.4)';
      ctx.shadowBlur = 18;
      ctx.beginPath(); ctx.arc(n.x, n.y, n.radius + 4, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0,0,0,0)'; ctx.fill();
      ctx.restore();
    }

    const grad = ctx.createRadialGradient(
      n.x - n.radius * 0.3, n.y - n.radius * 0.3, n.radius * 0.1, n.x, n.y, n.radius,
    );
    if (isHighlight && !isDim) {
      grad.addColorStop(0, '#ffffff');
      grad.addColorStop(0.4, n.color);
      grad.addColorStop(1, n.color);
    } else {
      grad.addColorStop(0, n.color + 'cc');
      grad.addColorStop(0.5, n.color);
      grad.addColorStop(1, n.color + '88');
    }
    ctx.beginPath(); ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
    ctx.fillStyle = grad; ctx.fill();
    ctx.strokeStyle = isHighlight ? '#ffffff' : (n.color + '55');
    ctx.lineWidth = isHighlight ? 2 : 1;
    ctx.stroke();

    if (n.pinned) {
      ctx.beginPath(); ctx.arc(n.x, n.y, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff'; ctx.fill();
    }
    ctx.restore();
  }
}

function drawLabels(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null,
  search: string, matchSet: Set<string>, vp: Viewport,
) {
  const dimmed = search.length > 0;
  const fontSize = Math.max(9, Math.round(12 / vp.scale));
  ctx.font = `500 ${fontSize}px Inter, system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'bottom';

  const sorted = [...graph.nodes].sort((a, b) => {
    const aH = hovered === a.id || selected === a.id || matchSet.has(a.id) ? 1 : 0;
    const bH = hovered === b.id || selected === b.id || matchSet.has(b.id) ? 1 : 0;
    if (aH !== bH) return aH - bH;
    return b.count - a.count;
  });

  for (const n of sorted) {
    const isHighlight = hovered === n.id || selected === n.id || matchSet.has(n.id);
    // Always show labels for hosts (since they're deduped and fewer)
    const show = isHighlight || n.meta.type === 'host' || n.count >= 2;
    if (!show) continue;
    const isDim = dimmed && !matchSet.has(n.id);
    if (isDim) continue;

    // Two-line label: hostname + IP (if available)
    const line1 = n.label;
    const line2 = n.meta.ips.length > 0 ? n.meta.ips[0] : '';
    const tw = Math.max(ctx.measureText(line1).width, line2 ? ctx.measureText(line2).width : 0);
    const px = 5, py = 2;
    const totalH = line2 ? fontSize * 2 + py * 2 : fontSize + py * 2;
    const lx = n.x, ly = n.y - n.radius - 6;

    const rx = lx - tw / 2 - px;
    const ry = ly - totalH;
    const rw = tw + px * 2;
    const rh = totalH;
    const cr = 4;

    ctx.save();
    ctx.globalAlpha = isHighlight ? 0.92 : 0.75;
    ctx.fillStyle = 'rgba(10,16,30,0.80)';
    ctx.beginPath();
    ctx.moveTo(rx + cr, ry); ctx.lineTo(rx + rw - cr, ry);
    ctx.arcTo(rx + rw, ry, rx + rw, ry + cr, cr);
    ctx.lineTo(rx + rw, ry + rh - cr);
    ctx.arcTo(rx + rw, ry + rh, rx + rw - cr, ry + rh, cr);
    ctx.lineTo(rx + cr, ry + rh);
    ctx.arcTo(rx, ry + rh, rx, ry + rh - cr, cr);
    ctx.lineTo(rx, ry + cr);
    ctx.arcTo(rx, ry, rx + cr, ry, cr);
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = isHighlight ? n.color + 'aa' : 'rgba(148,163,184,0.15)';
    ctx.lineWidth = 0.8; ctx.stroke();
    ctx.restore();

    // Hostname line
    ctx.fillStyle = isHighlight ? '#ffffff' : n.color;
    ctx.globalAlpha = isHighlight ? 1 : 0.85;
    ctx.fillText(line1, lx, ly - (line2 ? fontSize * 0.5 : 0));
    // IP line (smaller, dimmer)
    if (line2) {
      ctx.fillStyle = 'rgba(148,163,184,0.6)';
      ctx.fillText(line2, lx, ly + fontSize * 0.5);
    }
    ctx.globalAlpha = 1;
  }
}

function drawGraph(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null, search: string,
  vp: Viewport, animTime: number, dpr: number,
) {
  const w = ctx.canvas.width, h = ctx.canvas.height;
  const nodeMap = new Map(graph.nodes.map(n => [n.id, n]));
  const matchSet = new Set<string>();
  if (search) {
    const lc = search.toLowerCase();
    for (const n of graph.nodes) {
      if (n.label.toLowerCase().includes(lc)
        || n.meta.ips.some(ip => ip.includes(lc))
        || n.meta.users.some(u => u.toLowerCase().includes(lc))
        || n.meta.os.toLowerCase().includes(lc)
      ) matchSet.add(n.id);
    }
  }
  drawBackground(ctx, w, h, vp, dpr);
  ctx.save();
  ctx.translate(vp.x * dpr, vp.y * dpr);
  ctx.scale(vp.scale * dpr, vp.scale * dpr);
  drawEdges(ctx, graph, hovered, selected, nodeMap, animTime);
  drawNodes(ctx, graph, hovered, selected, search, matchSet);
  drawLabels(ctx, graph, hovered, selected, search, matchSet, vp);
  ctx.restore();
}

// == Hit-test =============================================================

function screenToWorld(
  canvas: HTMLCanvasElement, clientX: number, clientY: number, vp: Viewport,
): { wx: number; wy: number } {
  const rect = canvas.getBoundingClientRect();
  return { wx: (clientX - rect.left - vp.x) / vp.scale, wy: (clientY - rect.top - vp.y) / vp.scale };
}

function hitTest(
  graph: Graph, canvas: HTMLCanvasElement, clientX: number, clientY: number, vp: Viewport,
): GNode | null {
  const { wx, wy } = screenToWorld(canvas, clientX, clientY, vp);
  for (const n of graph.nodes) {
    const dx = n.x - wx, dy = n.y - wy;
    if (dx * dx + dy * dy < (n.radius + 5) ** 2) return n;
  }
  return null;
}
// == Component =============================================================

export default function NetworkMap() {
  const theme = useTheme();

  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [selectedHuntId, setSelectedHuntId] = useState('');

  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [graph, setGraph] = useState<Graph | null>(null);
  const [stats, setStats] = useState<InventoryStats | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GNode | null>(null);
  const [search, setSearch] = useState('');

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [canvasSize, setCanvasSize] = useState({ w: 900, h: 600 });

  const vpRef = useRef<Viewport>({ x: 0, y: 0, scale: 1 });
  const [vpScale, setVpScale] = useState(1);
  const isPanning = useRef(false);
  const panStart = useRef({ x: 0, y: 0 });
  const dragNode = useRef<GNode | null>(null);

  const animFrameRef = useRef<number>(0);
  const animTimeRef = useRef<number>(0);
  const simAlphaRef = useRef<number>(0);
  const isAnimatingRef = useRef(false);
  const hoveredRef = useRef<string | null>(null);
  const selectedNodeRef = useRef<GNode | null>(null);
  const searchRef = useRef('');
  const graphRef = useRef<Graph | null>(null);

  const [popoverAnchor, setPopoverAnchor] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => { hoveredRef.current = hovered; }, [hovered]);
  useEffect(() => { selectedNodeRef.current = selectedNode; }, [selectedNode]);
  useEffect(() => { searchRef.current = search; }, [search]);

  // Load hunts on mount
  useEffect(() => {
    hunts.list(0, 200).then(r => setHuntList(r.hunts)).catch(() => {});
  }, []);

  // Resize observer
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        const w = Math.round(entry.contentRect.width);
        if (w > 100) setCanvasSize({ w, h: Math.max(500, Math.round(w * 0.56)) });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // HiDPI canvas sizing
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvasSize.w * dpr;
    canvas.height = canvasSize.h * dpr;
    canvas.style.width = canvasSize.w + 'px';
    canvas.style.height = canvasSize.h + 'px';
  }, [canvasSize]);

  // Load host inventory for selected hunt
  const loadGraph = useCallback(async (huntId: string) => {
    if (!huntId) return;
    setLoading(true); setError(''); setGraph(null); setStats(null);
    setSelectedNode(null); setPopoverAnchor(null);
    try {
      setProgress('Building host inventory (scanning all datasets)\u2026');
      const inv = await network.hostInventory(huntId);
      setStats(inv.stats);

      if (inv.hosts.length === 0) {
        setError('No hosts found. Upload CSV files with host-identifying columns (ClientId, Fqdn, Hostname) to this hunt.');
        setLoading(false); setProgress('');
        return;
      }

      setProgress(`Building graph for ${inv.stats.total_hosts} hosts\u2026`);
      const g = buildGraphFromInventory(inv.hosts, inv.connections, canvasSize.w, canvasSize.h);
      simulate(g, canvasSize.w / 2, canvasSize.h / 2, 30);
      simAlphaRef.current = 0.8;
      setGraph(g);
    } catch (e: any) { setError(e.message); }
    setLoading(false); setProgress('');
  }, [canvasSize]);

  useEffect(() => {
    if (selectedHuntId) loadGraph(selectedHuntId);
  }, [selectedHuntId, loadGraph]);

  useEffect(() => {
    vpRef.current = { x: 0, y: 0, scale: 1 };
    setVpScale(1);
  }, [graph]);

  useEffect(() => { graphRef.current = graph; }, [graph]);

  // Animation loop
  const startAnimLoop = useCallback(() => {
    if (isAnimatingRef.current) return;
    isAnimatingRef.current = true;
    const tick = (ts: number) => {
      animTimeRef.current = ts;
      const canvas = canvasRef.current;
      const g = graphRef.current;
      if (!canvas || !g) { isAnimatingRef.current = false; return; }
      const dpr = window.devicePixelRatio || 1;
      const ctx = canvas.getContext('2d');
      if (!ctx) { isAnimatingRef.current = false; return; }

      if (simAlphaRef.current > 0.01) {
        simulationStep(g, canvasSize.w / 2, canvasSize.h / 2, simAlphaRef.current);
        simAlphaRef.current *= 0.97;
        if (simAlphaRef.current < 0.01) simAlphaRef.current = 0;
      }
      drawGraph(ctx, g, hoveredRef.current, selectedNodeRef.current?.id ?? null, searchRef.current, vpRef.current, ts, dpr);

      const needsAnim = simAlphaRef.current > 0.01
        || hoveredRef.current !== null
        || selectedNodeRef.current !== null
        || dragNode.current !== null;
      if (needsAnim) {
        animFrameRef.current = requestAnimationFrame(tick);
      } else {
        isAnimatingRef.current = false;
      }
    };
    animFrameRef.current = requestAnimationFrame(tick);
  }, [canvasSize]);

  useEffect(() => {
    if (graph) startAnimLoop();
    return () => { cancelAnimationFrame(animFrameRef.current); isAnimatingRef.current = false; };
  }, [graph, startAnimLoop]);

  useEffect(() => { startAnimLoop(); }, [hovered, selectedNode, search, startAnimLoop]);

  const redraw = useCallback(() => {
    if (!graph || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    if (ctx) drawGraph(ctx, graph, hovered, selectedNode?.id ?? null, search, vpRef.current, animTimeRef.current, dpr);
  }, [graph, hovered, selectedNode, search]);

  useEffect(() => { if (!isAnimatingRef.current) redraw(); }, [redraw]);

  // Mouse wheel -> zoom
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const vp = vpRef.current;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const zoomFactor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const newScale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, vp.scale * zoomFactor));
      vp.x = mx - (mx - vp.x) * (newScale / vp.scale);
      vp.y = my - (my - vp.y) * (newScale / vp.scale);
      vp.scale = newScale;
      setVpScale(newScale);
      startAnimLoop();
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, [graph, startAnimLoop]);

  // Mouse handlers
  const onMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!graph || !canvasRef.current) return;
    const node = hitTest(graph, canvasRef.current, e.clientX, e.clientY, vpRef.current);
    if (node) { dragNode.current = node; node.pinned = true; startAnimLoop(); }
    else { isPanning.current = true; panStart.current = { x: e.clientX, y: e.clientY }; }
  }, [graph, startAnimLoop]);

  const onMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!graph || !canvasRef.current) return;
    if (dragNode.current) {
      const { wx, wy } = screenToWorld(canvasRef.current, e.clientX, e.clientY, vpRef.current);
      dragNode.current.x = wx; dragNode.current.y = wy;
      dragNode.current.vx = 0; dragNode.current.vy = 0;
      if (simAlphaRef.current < 0.15) simAlphaRef.current = 0.15;
      startAnimLoop(); return;
    }
    if (isPanning.current) {
      const vp = vpRef.current;
      vp.x += e.clientX - panStart.current.x;
      vp.y += e.clientY - panStart.current.y;
      panStart.current = { x: e.clientX, y: e.clientY };
      redraw(); return;
    }
    const node = hitTest(graph, canvasRef.current, e.clientX, e.clientY, vpRef.current);
    setHovered(node?.id ?? null);
  }, [graph, redraw, startAnimLoop]);

  const onMouseUp = useCallback(() => { dragNode.current = null; isPanning.current = false; }, []);

  const onClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!graph || !canvasRef.current) return;
    const node = hitTest(graph, canvasRef.current, e.clientX, e.clientY, vpRef.current);
    if (node) { setSelectedNode(node); setPopoverAnchor({ top: e.clientY, left: e.clientX }); }
    else { setSelectedNode(null); setPopoverAnchor(null); }
  }, [graph]);

  const onDoubleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!graph || !canvasRef.current) return;
    const node = hitTest(graph, canvasRef.current, e.clientX, e.clientY, vpRef.current);
    if (node && node.pinned) {
      node.pinned = false; simAlphaRef.current = Math.max(simAlphaRef.current, 0.3); startAnimLoop();
    }
  }, [graph, startAnimLoop]);

  const closePopover = () => { setSelectedNode(null); setPopoverAnchor(null); };

  const zoomBy = useCallback((factor: number) => {
    const vp = vpRef.current;
    const cw = canvasSize.w, ch = canvasSize.h;
    const newScale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, vp.scale * factor));
    vp.x = cw / 2 - (cw / 2 - vp.x) * (newScale / vp.scale);
    vp.y = ch / 2 - (ch / 2 - vp.y) * (newScale / vp.scale);
    vp.scale = newScale; setVpScale(newScale); redraw();
  }, [canvasSize, redraw]);

  const resetView = useCallback(() => {
    vpRef.current = { x: 0, y: 0, scale: 1 }; setVpScale(1); redraw();
  }, [redraw]);

  const connectionCount = selectedNode && graph
    ? graph.edges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id).length
    : 0;

  const connectedNodes = useMemo(() => {
    if (!selectedNode || !graph) return [];
    const neighbors: { id: string; type: NodeType; weight: number }[] = [];
    for (const e of graph.edges) {
      if (e.source === selectedNode.id) {
        const n = graph.nodes.find(x => x.id === e.target);
        if (n) neighbors.push({ id: n.id, type: n.meta.type, weight: e.weight });
      } else if (e.target === selectedNode.id) {
        const n = graph.nodes.find(x => x.id === e.source);
        if (n) neighbors.push({ id: n.id, type: n.meta.type, weight: e.weight });
      }
    }
    return neighbors.sort((a, b) => b.weight - a.weight).slice(0, 12);
  }, [selectedNode, graph]);

  const hostCount = graph ? graph.nodes.filter(n => n.meta.type === 'host').length : 0;
  const extCount = graph ? graph.nodes.filter(n => n.meta.type === 'external_ip').length : 0;

  const getCursor = () => {
    if (dragNode.current) return 'grabbing';
    if (isPanning.current) return 'grabbing';
    if (hovered) return 'pointer';
    return 'grab';
  };
  // == Render ==============================================================
  return (
    <Box>
      {/* Glassmorphism toolbar */}
      <Paper
        elevation={0}
        sx={{
          mb: 2, p: 1.5, display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1.5,
          background: 'rgba(30,41,59,0.65)', backdropFilter: 'blur(16px)',
          borderColor: 'rgba(148,163,184,0.12)',
        }}
      >
        <Stack direction="row" alignItems="center" spacing={1}>
          <HubIcon sx={{ color: theme.palette.primary.main, fontSize: 28 }} />
          <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
            Network Map
          </Typography>
        </Stack>

        <Box sx={{ flex: 1 }} />

        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel id="hunt-selector-label">Hunt</InputLabel>
          <Select
            labelId="hunt-selector-label"
            value={selectedHuntId}
            label="Hunt"
            onChange={e => setSelectedHuntId(e.target.value)}
            sx={{ '& .MuiSelect-select': { py: 0.8 } }}
          >
            {huntList.map(h => (
              <MenuItem key={h.id} value={h.id}>
                {h.name} ({h.dataset_count} datasets)
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <TextField
          size="small"
          placeholder="Search hosts, IPs, users\u2026"
          value={search}
          onChange={e => setSearch(e.target.value)}
          sx={{ width: 200, '& .MuiInputBase-input': { py: 0.8 } }}
          slotProps={{
            input: {
              startAdornment: <SearchIcon sx={{ mr: 0.5, fontSize: 18, color: 'text.secondary' }} />,
            },
          }}
        />

        <Tooltip title="Refresh inventory">
          <span>
            <IconButton
              onClick={() => loadGraph(selectedHuntId)}
              disabled={loading || !selectedHuntId}
              size="small"
              sx={{ bgcolor: 'rgba(96,165,250,0.1)', '&:hover': { bgcolor: 'rgba(96,165,250,0.2)' } }}
            >
              <RefreshIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      </Paper>

      {/* Stats summary cards */}
      {stats && !loading && (
        <Stack direction="row" spacing={1.5} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
          {[
            { label: 'Hosts', value: stats.total_hosts, color: TYPE_COLORS.host },
            { label: 'With IPs', value: stats.hosts_with_ips, color: '#34d399' },
            { label: 'With Users', value: stats.hosts_with_users, color: '#a78bfa' },
            { label: 'Datasets Scanned', value: stats.total_datasets_scanned, color: '#fbbf24' },
            { label: 'Rows Scanned', value: stats.total_rows_scanned.toLocaleString(), color: '#f87171' },
          ].map(s => (
            <Paper key={s.label} sx={{
              px: 2, py: 1, background: 'rgba(30,41,59,0.5)',
              borderColor: 'rgba(148,163,184,0.08)', borderRadius: 2,
            }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {s.label}
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 700, color: s.color, lineHeight: 1.2 }}>
                {s.value}
              </Typography>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Loading indicator */}
      <Fade in={loading}>
        <Paper sx={{ p: 2, mb: 2, background: 'rgba(30,41,59,0.65)', backdropFilter: 'blur(12px)' }}>
          <Stack direction="row" alignItems="center" spacing={2}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>{progress}</Typography>
              <LinearProgress sx={{
                borderRadius: 1,
                '& .MuiLinearProgress-bar': {
                  background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.info.main})`,
                },
              }} />
            </Box>
          </Stack>
        </Paper>
      </Fade>

      {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Canvas area */}
      {graph && (
        <Paper
          ref={wrapperRef}
          sx={{
            position: 'relative', overflow: 'hidden',
            backgroundColor: BG_COLOR,
            borderColor: 'rgba(148,163,184,0.08)', borderRadius: 2,
          }}
        >
          <canvas
            ref={canvasRef}
            style={{ display: 'block', cursor: getCursor() }}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={() => { isPanning.current = false; dragNode.current = null; setHovered(null); }}
            onClick={onClick}
            onDoubleClick={onDoubleClick}
          />

          {/* Legend overlay - bottom left */}
          <Stack
            direction="row" spacing={0.5} flexWrap="wrap" gap={0.5}
            sx={{
              position: 'absolute', bottom: 12, left: 12, zIndex: 2,
              p: 0.8, px: 1.2, borderRadius: 2,
              background: 'rgba(10,16,30,0.75)', backdropFilter: 'blur(10px)',
              border: '1px solid rgba(148,163,184,0.1)',
            }}
          >
            <Chip
              icon={<ComputerIcon sx={{ fontSize: 14 }} />}
              label={`Hosts (${hostCount})`}
              size="small"
              sx={{
                bgcolor: TYPE_COLORS.host + '22', color: TYPE_COLORS.host,
                border: `1.5px solid ${TYPE_COLORS.host}88`,
                fontWeight: 600, fontSize: 11,
              }}
            />
            {extCount > 0 && (
              <Chip
                label={`External IPs (${extCount})`}
                size="small"
                sx={{
                  bgcolor: TYPE_COLORS.external_ip + '22', color: TYPE_COLORS.external_ip,
                  border: `1.5px solid ${TYPE_COLORS.external_ip}88`,
                  fontWeight: 600, fontSize: 11,
                }}
              />
            )}
          </Stack>

          {/* Stats badge - bottom right */}
          <Stack
            direction="row" spacing={0.8} alignItems="center"
            sx={{
              position: 'absolute', bottom: 12, right: 12, zIndex: 2,
              px: 1.2, py: 0.5, borderRadius: 2,
              background: 'rgba(10,16,30,0.75)', backdropFilter: 'blur(10px)',
              border: '1px solid rgba(148,163,184,0.1)',
            }}
          >
            <Typography variant="caption" sx={{ color: TYPE_COLORS.host, fontWeight: 600 }}>
              {graph.nodes.length} nodes
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(148,163,184,0.4)' }}>{'\u00B7'}</Typography>
            <Typography variant="caption" sx={{ color: theme.palette.secondary.main, fontWeight: 600 }}>
              {graph.edges.length} connections
            </Typography>
          </Stack>

          {/* Zoom controls - top right */}
          <Stack direction="column" spacing={0.5} sx={{ position: 'absolute', top: 12, right: 12, zIndex: 2 }}>
            {[
              { tip: 'Zoom in', icon: <ZoomInIcon fontSize="small" />, fn: () => zoomBy(1.3) },
              { tip: 'Zoom out', icon: <ZoomOutIcon fontSize="small" />, fn: () => zoomBy(1 / 1.3) },
              { tip: 'Reset view', icon: <CenterFocusStrongIcon fontSize="small" />, fn: resetView },
            ].map(z => (
              <Tooltip key={z.tip} title={z.tip} placement="left">
                <IconButton size="small" onClick={z.fn}
                  sx={{
                    bgcolor: 'rgba(10,16,30,0.75)', backdropFilter: 'blur(10px)',
                    color: theme.palette.text.primary,
                    border: '1px solid rgba(148,163,184,0.1)',
                    '&:hover': { bgcolor: 'rgba(30,41,59,0.9)', borderColor: theme.palette.primary.main + '44' },
                  }}
                >{z.icon}</IconButton>
              </Tooltip>
            ))}
            <Chip
              label={`${Math.round(vpScale * 100)}%`}
              size="small"
              sx={{
                bgcolor: 'rgba(10,16,30,0.75)', color: theme.palette.text.secondary,
                fontSize: 11, height: 24, fontWeight: 600,
                border: '1px solid rgba(148,163,184,0.1)',
              }}
            />
          </Stack>

          {/* Drag hint */}
          <Fade in timeout={2000}>
            <Typography variant="caption" sx={{
              position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
              color: 'rgba(148,163,184,0.4)', fontSize: 11, pointerEvents: 'none', userSelect: 'none',
            }}>
              Drag nodes to reposition {'\u00B7'} Double-click to unpin {'\u00B7'} Scroll to zoom
            </Typography>
          </Fade>
        </Paper>
      )}
      {/* Node detail popover */}
      <Popover
        open={Boolean(selectedNode && popoverAnchor)}
        anchorReference="anchorPosition"
        anchorPosition={popoverAnchor ?? undefined}
        onClose={closePopover}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{ paper: { sx: {
          minWidth: 320, maxWidth: 440, overflow: 'hidden',
          border: '1px solid rgba(148,163,184,0.12)', borderRadius: 2,
        }}}}
      >
        {selectedNode && (
          <Box>
            <Box sx={{ height: 3, background: `linear-gradient(90deg, ${TYPE_COLORS[selectedNode.meta.type]}, ${TYPE_COLORS[selectedNode.meta.type]}44)` }} />
            <Box sx={{ p: 2 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <ComputerIcon sx={{ color: TYPE_COLORS[selectedNode.meta.type], fontSize: 20 }} />
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, fontFamily: 'monospace', fontSize: 14 }}>
                    {selectedNode.meta.hostname || selectedNode.label}
                  </Typography>
                  <Chip
                    label={selectedNode.meta.type === 'host' ? 'HOST' : 'EXT IP'}
                    size="small"
                    sx={{
                      bgcolor: TYPE_COLORS[selectedNode.meta.type] + '22',
                      color: TYPE_COLORS[selectedNode.meta.type],
                      fontWeight: 700, fontSize: 10, height: 22,
                      border: `1px solid ${TYPE_COLORS[selectedNode.meta.type]}44`,
                    }}
                  />
                </Stack>
                <IconButton size="small" onClick={closePopover}><CloseIcon fontSize="small" /></IconButton>
              </Stack>

              <Divider sx={{ mb: 1.5, borderColor: 'rgba(148,163,184,0.1)' }} />

              <Stack spacing={1}>
                {selectedNode.meta.fqdn && (
                  <Box>
                    <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
                      FQDN
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: 13 }}>
                      {selectedNode.meta.fqdn}
                    </Typography>
                  </Box>
                )}

                <Box>
                  <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
                    IP Address
                  </Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: 13 }}>
                    {selectedNode.meta.ips.length > 0 ? selectedNode.meta.ips.join(', ') : <em style={{ opacity: 0.4 }}>No IP detected</em>}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
                    Operating System
                  </Typography>
                  <Typography variant="body2" sx={{ fontSize: 13 }}>
                    {selectedNode.meta.os || <em style={{ opacity: 0.4 }}>Unknown</em>}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
                    Logged-In Users
                  </Typography>
                  {selectedNode.meta.users.length > 0 ? (
                    <Stack direction="row" spacing={0.4} flexWrap="wrap" gap={0.4} sx={{ mt: 0.3 }}>
                      {selectedNode.meta.users.map(u => (
                        <Chip key={u} label={u} size="small" sx={{
                          fontSize: 11, height: 22, fontFamily: 'monospace',
                          bgcolor: 'rgba(167,139,250,0.15)', color: '#a78bfa',
                          border: '1px solid rgba(167,139,250,0.25)',
                        }} />
                      ))}
                    </Stack>
                  ) : (
                    <Typography variant="body2" sx={{ fontSize: 13 }}>
                      <em style={{ opacity: 0.4 }}>No user data</em>
                    </Typography>
                  )}
                </Box>

                {selectedNode.meta.client_id && (
                  <Box>
                    <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
                      Client ID
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: 12, color: 'text.secondary' }}>
                      {selectedNode.meta.client_id}
                    </Typography>
                  </Box>
                )}
              </Stack>

              <Divider sx={{ my: 1.5, borderColor: 'rgba(148,163,184,0.1)' }} />

              <Stack direction="row" spacing={0.8} flexWrap="wrap" gap={0.5}>
                <Chip label={`${selectedNode.meta.row_count.toLocaleString()} rows`} size="small"
                  sx={{ fontWeight: 600, fontSize: 11, bgcolor: 'rgba(96,165,250,0.1)', color: theme.palette.primary.main, border: '1px solid rgba(96,165,250,0.2)' }} />
                <Chip label={`${connectionCount} connections`} size="small"
                  sx={{ fontWeight: 600, fontSize: 11, bgcolor: 'rgba(244,114,182,0.1)', color: theme.palette.secondary.main, border: '1px solid rgba(244,114,182,0.2)' }} />
                <Chip label={`${selectedNode.meta.datasets.length} datasets`} size="small"
                  sx={{ fontWeight: 600, fontSize: 11, bgcolor: 'rgba(251,191,36,0.1)', color: '#fbbf24', border: '1px solid rgba(251,191,36,0.2)' }} />
              </Stack>

              {connectedNodes.length > 0 && (
                <Box sx={{ mt: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
                    Connected To
                  </Typography>
                  <Stack direction="row" spacing={0.4} flexWrap="wrap" gap={0.4} sx={{ mt: 0.5 }}>
                    {connectedNodes.map(cn => (
                      <Chip key={cn.id} label={cn.id.length > 30 ? cn.id.slice(0, 28) + '\u2026' : cn.id} size="small"
                        sx={{
                          fontSize: 10, height: 22, fontFamily: 'monospace',
                          bgcolor: TYPE_COLORS[cn.type] + '15', color: TYPE_COLORS[cn.type],
                          border: `1px solid ${TYPE_COLORS[cn.type]}33`, cursor: 'pointer',
                          '&:hover': { bgcolor: TYPE_COLORS[cn.type] + '30' },
                        }}
                        onClick={() => { setSearch(cn.id); closePopover(); }}
                      />
                    ))}
                  </Stack>
                </Box>
              )}

              {selectedNode.meta.datasets.length > 0 && (
                <Box sx={{ mt: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
                    Seen In Datasets
                  </Typography>
                  <Stack direction="row" spacing={0.4} flexWrap="wrap" gap={0.4} sx={{ mt: 0.5 }}>
                    {selectedNode.meta.datasets.map(d => (
                      <Chip key={d} label={d} size="small" variant="outlined" sx={{ fontSize: 10, height: 22 }} />
                    ))}
                  </Stack>
                </Box>
              )}
            </Box>
          </Box>
        )}
      </Popover>

      {/* Empty states */}
      {!selectedHuntId && !loading && (
        <Paper ref={wrapperRef} sx={{
          p: 6, textAlign: 'center',
          background: 'rgba(30,41,59,0.4)', borderColor: 'rgba(148,163,184,0.08)',
        }}>
          <HubIcon sx={{ fontSize: 56, color: 'rgba(96,165,250,0.2)', mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom sx={{ fontWeight: 600 }}>
            Select a hunt to visualize its network
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 480, mx: 'auto' }}>
            Choose a hunt from the dropdown above. The map builds a clean,
            deduplicated host inventory showing each endpoint with its hostname,
            IP address, OS, and logged-in users.
          </Typography>
        </Paper>
      )}

      {selectedHuntId && !graph && !loading && !error && (
        <Paper sx={{
          p: 6, textAlign: 'center',
          background: 'rgba(30,41,59,0.4)', borderColor: 'rgba(148,163,184,0.08)',
        }}>
          <Typography color="text.secondary">
            No host data to display. Upload datasets with host-identifying columns (ClientId, Fqdn, Hostname).
          </Typography>
        </Paper>
      )}
    </Box>
  );
}