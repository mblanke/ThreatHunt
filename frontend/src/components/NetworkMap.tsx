/**
 * NetworkMap - interactive hunt-scoped network graph powered by Cytoscape.js.
 *
 * Graph model:
 *  - Host nodes (green) - one per unique hostname, labeled with hostname + local IP
 *  - Remote IP nodes (blue) - external IPs that hosts connect to
 *  - Internal IP nodes (cyan) - internal IPs hosts connect to (lateral movement)
 *  - Domain nodes (yellow) - domains from DNS / proxy / sysmon logs
 *  - URL nodes (purple) - URLs from browser / proxy logs
 *  - Edges = observed connection/co-occurrence between a host and a remote entity
 *
<<<<<<< HEAD
 * Features:
 * - Calls /api/network/host-inventory for clean, deduped host data
 * - HiDPI / Retina canvas rendering
 * - Radial-gradient nodes with neon glow effects
 * - Curved edges with animated flow on active connections
 * - Animated force-directed layout
 * - Node drag with springy neighbor physics
 * - Glassmorphism toolbar + floating legend overlay
 * - Rich popover: hostname, IP, OS, users, datasets
 * - MODULE-LEVEL CACHE: graph survives tab switches
 * - AUTO-LOAD: picks most recent hunt on mount
 * - FULL VIEWPORT canvas: fills available space
 * - Zero extra npm dependencies
=======
 * Layout: cytoscape-cola (constraint-based, non-overlapping)
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
 */

import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Box, Typography, Paper, Stack, Alert, Chip, Button, TextField,
  LinearProgress, FormControl, InputLabel, Select, MenuItem,
  Divider, IconButton,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong';
import cytoscape, { type Core, type ElementDefinition, type StylesheetStyle } from 'cytoscape';
import cola from 'cytoscape-cola';
import { datasets, hunts, type Hunt, type DatasetSummary } from '../api/client';

// Register cola layout once
try { cytoscape.use(cola); } catch { /* already registered */ }

// -- Types --

type NodeKind = 'host' | 'internal_ip' | 'external_ip' | 'domain' | 'url';

interface HostInfo {
  hostname: string;
  localIp: string;
  os: string;
  datasets: Set<string>;
  remoteIps: Map<string, number>;   // remoteIp -> weight
  domains: Map<string, number>;
  urls: Map<string, number>;
  internalIps: Map<string, number>; // lateral connections to other internal IPs
}

<<<<<<< HEAD
type LabelMode = 'all' | 'highlight' | 'none';

const TYPE_COLORS: Record<NodeType, string> = {
  host: '#60a5fa',
  external_ip: '#fbbf24',
};
const GLOW_COLORS: Record<NodeType, string> = {
  host: 'rgba(96,165,250,0.45)',
  external_ip: 'rgba(251,191,36,0.35)',
};

// =========================================================================
// MODULE-LEVEL CACHE - survives unmount/remount on tab switches
// =========================================================================
const graphCache = new Map<string, { graph: Graph; stats: InventoryStats; ts: number }>();
let lastSelectedHuntId = '';
const LARGE_HUNT_HOST_THRESHOLD = 400;
const LARGE_HUNT_SUBGRAPH_HOSTS = 220;
const LARGE_HUNT_SUBGRAPH_EDGES = 1200;
const RENDER_SIMPLIFY_NODE_THRESHOLD = 120;
const RENDER_SIMPLIFY_EDGE_THRESHOLD = 500;
const EDGE_DRAW_TARGET = 600;

// == Build graph from inventory ==========================================

function buildGraphFromInventory(
  hosts: InventoryHost[], connections: InventoryConnection[],
  canvasW: number, canvasH: number,
): Graph {
  const nodeMap = new Map<string, GNode>();
  const cx = canvasW / 2, cy = canvasH / 2;
  const MAX_EXTERNAL_NODES = 30;

  for (const h of hosts) {
    const r = Math.max(8, Math.min(26, 6 + Math.sqrt(h.row_count / 100) * 3));
    nodeMap.set(h.id, {
      id: h.id,
      label: h.hostname || h.fqdn || h.client_id,
      x: cx + (Math.random() - 0.5) * canvasW * 0.75,
      y: cy + (Math.random() - 0.5) * canvasH * 0.65,
      vx: 0, vy: 0, radius: r,
      color: TYPE_COLORS.host,
      count: h.row_count,
      meta: {
        type: 'host' as NodeType,
        hostname: h.hostname, fqdn: h.fqdn, client_id: h.client_id,
        ips: h.ips, os: h.os, users: h.users,
        datasets: h.datasets, row_count: h.row_count,
      },
=======
const KIND_COLORS: Record<NodeKind, string> = {
  host: '#22c55e',
  internal_ip: '#06b6d4',
  external_ip: '#3b82f6',
  domain: '#eab308',
  url: '#8b5cf6',
};

const _JUNK = new Set(['', '-', '0.0.0.0', '::', '0', '127.0.0.1', '::1', 'localhost', 'unknown', 'n/a', 'none']);
function clean(v: any): string {
  const s = (v ?? '').toString().trim();
  return _JUNK.has(s.toLowerCase()) ? '' : s;
}

function isInternalIp(ip: string): boolean {
  return /^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)/.test(ip);
}

// -- Build graph data from API rows --

interface RowBatch {
  rows: Record<string, any>[];
  ds: DatasetSummary;
}

function findColumns(ds: DatasetSummary) {
  const norm = ds.normalized_columns || {};
  const schema = ds.column_schema || {};
  const rawCols = Object.keys(schema).length > 0 ? Object.keys(schema) : Object.keys(norm);

  const hostCols: string[] = [];
  const srcIpCols: string[] = [];
  const dstIpCols: string[] = [];
  const domainCols: string[] = [];
  const urlCols: string[] = [];
  const osCols: string[] = [];

  for (const raw of rawCols) {
    const canon = norm[raw] || '';
    const lc = raw.toLowerCase();
    if (canon === 'hostname' || /^(hostname|host|fqdn|computer_?name|system_?name)$/i.test(lc))
      hostCols.push(raw);
    if (canon === 'src_ip' || /^(source_?ip|src_?ip|laddr\.?ip|local_?address|sourceip)$/i.test(lc))
      srcIpCols.push(raw);
    if (canon === 'dst_ip' || /^(dest_?ip|dst_?ip|raddr\.?ip|remote_?address|destination_?ip|destinationip)$/i.test(lc))
      dstIpCols.push(raw);
    if (canon === 'ip_address' || /^(ip_?address|ip|sourceaddress)$/i.test(lc))
      srcIpCols.push(raw); // generic IP -> treat as source
    if (canon === 'domain' || /^(domain|dns_?name|query_?name|queriedname|destinationhostname)$/i.test(lc))
      domainCols.push(raw);
    if (canon === 'url' || /^(url|uri|request_?url)$/i.test(lc))
      urlCols.push(raw);
    if (canon === 'os' || /^(os|operating_?system)$/i.test(lc))
      osCols.push(raw);
  }
  return { hostCols, srcIpCols, dstIpCols, domainCols, urlCols, osCols };
}

function buildGraphData(batches: RowBatch[]) {
  // Collect host-centric data
  const hostMap = new Map<string, HostInfo>();

  // Also build a map of IP -> hostname for resolving internal connections
  const ipToHost = new Map<string, string>();

  for (const { rows, ds } of batches) {
    const cols = findColumns(ds);
    if (cols.hostCols.length === 0 && cols.srcIpCols.length === 0) continue;

    for (const row of rows) {
      // Resolve hostname
      let hostname = '';
      for (const c of cols.hostCols) { hostname = clean(row[c]); if (hostname) break; }

      // Resolve source IP
      let srcIp = '';
      for (const c of cols.srcIpCols) { srcIp = clean(row[c]); if (srcIp) break; }

      // If no hostname but have srcIp, use IP as hostname
      if (!hostname && srcIp) hostname = srcIp;
      if (!hostname) continue;

      // Get or create host
      let host = hostMap.get(hostname);
      if (!host) {
        host = {
          hostname, localIp: srcIp || '', os: '',
          datasets: new Set(), remoteIps: new Map(),
          domains: new Map(), urls: new Map(), internalIps: new Map(),
        };
        hostMap.set(hostname, host);
      }
      host.datasets.add(ds.name);
      if (srcIp && !host.localIp) host.localIp = srcIp;

      // Register IP->hostname mapping
      if (srcIp && isInternalIp(srcIp)) ipToHost.set(srcIp, hostname);

      // OS
      for (const c of cols.osCols) {
        const os = clean(row[c]);
        if (os) host.os = os;
      }

      // Destination IPs
      for (const c of cols.dstIpCols) {
        const dstIp = clean(row[c]);
        if (!dstIp) continue;
        if (dstIp === srcIp) continue; // skip self
        if (isInternalIp(dstIp)) {
          host.internalIps.set(dstIp, (host.internalIps.get(dstIp) || 0) + 1);
        } else {
          host.remoteIps.set(dstIp, (host.remoteIps.get(dstIp) || 0) + 1);
        }
      }

      // Domains
      for (const c of cols.domainCols) {
        const d = clean(row[c]);
        if (d) host.domains.set(d, (host.domains.get(d) || 0) + 1);
      }

      // URLs
      for (const c of cols.urlCols) {
        const u = clean(row[c]);
        if (u) host.urls.set(u, (host.urls.get(u) || 0) + 1);
      }
    }
  }

  // Now build Cytoscape elements
  const elements: ElementDefinition[] = [];
  const addedNodes = new Set<string>();

  const addNode = (id: string, label: string, kind: NodeKind, extra: Record<string, any> = {}) => {
    if (addedNodes.has(id)) return;
    addedNodes.add(id);
    elements.push({
      data: { id, label, kind, ...extra },
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
    });
  };

<<<<<<< HEAD
  const extIpCounts = new Map<string, number>();
  const extIpLabel = new Map<string, string>();
  for (const c of connections) {
    if (!nodeMap.has(c.target)) {
      extIpCounts.set(c.target, (extIpCounts.get(c.target) || 0) + c.count);
      if (!extIpLabel.has(c.target)) extIpLabel.set(c.target, c.target_ip || c.target);
    }
  }
  const topExternal = new Set(
    [...extIpCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, MAX_EXTERNAL_NODES)
      .map(e => e[0])
  );

  for (const [id, totalCount] of extIpCounts) {
    if (!topExternal.has(id)) continue;
    nodeMap.set(id, {
      id,
      label: extIpLabel.get(id) || id,
      x: cx + (Math.random() - 0.5) * canvasW * 0.75,
      y: cy + (Math.random() - 0.5) * canvasH * 0.65,
      vx: 0, vy: 0, radius: 6,
      color: TYPE_COLORS.external_ip,
      count: totalCount,
      meta: {
        type: 'external_ip' as NodeType,
        hostname: '', fqdn: '', client_id: '',
        ips: [extIpLabel.get(id) || id],
        os: '', users: [], datasets: [], row_count: 0,
      },
    });
  }

  const edges: GEdge[] = [];
  for (const c of connections) {
    if (nodeMap.has(c.source) && nodeMap.has(c.target)) {
      edges.push({ source: c.source, target: c.target, weight: c.count });
    }
  }
=======
  const edgeSet = new Set<string>();
  const addEdge = (src: string, tgt: string, weight: number, edgeKind: string) => {
    const key = `${src}->${tgt}`;
    if (edgeSet.has(key)) return;
    edgeSet.add(key);
    elements.push({
      data: { source: src, target: tgt, weight, edgeKind },
    });
  };
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

  // Cap: top 200 hosts by activity level
  const MAX_HOSTS = 200;
  const sortedHosts = [...hostMap.values()]
    .sort((a, b) => {
      const aScore = a.remoteIps.size + a.domains.size + a.urls.size + a.internalIps.size;
      const bScore = b.remoteIps.size + b.domains.size + b.urls.size + b.internalIps.size;
      return bScore - aScore;
    })
    .slice(0, MAX_HOSTS);

  const keptHostnames = new Set(sortedHosts.map(h => h.hostname));

<<<<<<< HEAD
function simulationStep(graph: Graph, cx: number, cy: number, alpha: number) {
  const { nodes, edges } = graph;
  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  const k = 120;
  const repulsion = 12000;
  const damping = 0.82;
  const N = nodes.length;

  const SAMPLE_THRESHOLD = 150;
  if (N > SAMPLE_THRESHOLD) {
    const sampleSize = Math.min(40, Math.ceil(N * 0.15));
    const scaleFactor = N / sampleSize;
    for (let i = 0; i < N; i++) {
      const a = nodes[i];
      if (a.pinned) continue;
      for (let s = 0; s < sampleSize; s++) {
        const j = Math.floor(Math.random() * N);
        if (j === i) continue;
        const b = nodes[j];
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        if (dist > 600) continue;
        const force = (repulsion * alpha * scaleFactor) / (dist * dist);
        const fx = (dx / dist) * force, fy = (dy / dist) * force;
        a.vx -= fx; a.vy -= fy;
      }
    }
  } else {
    for (let i = 0; i < N; i++) {
      for (let j = i + 1; j < N; j++) {
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
=======
  // Per-host: cap connections to top N by frequency
  const MAX_REMOTE_PER_HOST = 15;
  const MAX_DOMAIN_PER_HOST = 10;
  const MAX_URL_PER_HOST = 5;

  const stats = { hosts: 0, internalIps: 0, externalIps: 0, domains: 0, urls: 0, edges: 0 };
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

  for (const host of sortedHosts) {
    const hostId = `host::${host.hostname}`;
    addNode(hostId, host.localIp
      ? `${host.hostname}\n${host.localIp}`
      : host.hostname, 'host', {
      hostname: host.hostname,
      localIp: host.localIp,
      os: host.os,
      dsNames: [...host.datasets],
      connectionCount: host.remoteIps.size + host.internalIps.size + host.domains.size + host.urls.size,
    });
    stats.hosts++;

<<<<<<< HEAD
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
  simplify: boolean,
) {
  ctx.fillStyle = BG_COLOR;
  ctx.fillRect(0, 0, w, h);
  if (!simplify) {
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
  simplify: boolean,
) {
  const edgeStep = simplify ? Math.max(1, Math.ceil(graph.edges.length / EDGE_DRAW_TARGET)) : 1;
  for (let ei = 0; ei < graph.edges.length; ei += edgeStep) {
    const e = graph.edges[ei];
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

    ctx.beginPath(); ctx.moveTo(a.x, a.y); if (simplify) { ctx.lineTo(b.x, b.y); } else { ctx.quadraticCurveTo(cpx, cpy, b.x, b.y); }

    if (isActive) {
      ctx.strokeStyle = 'rgba(96,165,250,0.8)';
      ctx.lineWidth = Math.min(3.5, 1 + e.weight * 0.15);
      ctx.setLineDash([6, 4]); ctx.lineDashOffset = -animTime * 0.03;
      ctx.stroke(); ctx.setLineDash([]);
      ctx.save();
      ctx.shadowColor = 'rgba(96,165,250,0.5)'; ctx.shadowBlur = 8;
      ctx.strokeStyle = 'rgba(96,165,250,0.3)';
      ctx.lineWidth = Math.min(5, 2 + e.weight * 0.2);
      ctx.beginPath(); ctx.moveTo(a.x, a.y); if (simplify) { ctx.lineTo(b.x, b.y); } else { ctx.quadraticCurveTo(cpx, cpy, b.x, b.y); }
      ctx.stroke(); ctx.restore();
    } else {
      const alpha = Math.min(0.35, 0.08 + e.weight * 0.01);
      ctx.strokeStyle = 'rgba(100,116,139,' + alpha + ')';
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
=======
    // Remote IPs - top N
    const topRemote = [...host.remoteIps.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, MAX_REMOTE_PER_HOST);
    for (const [ip, w] of topRemote) {
      const nid = `extip::${ip}`;
      addNode(nid, ip, 'external_ip');
      addEdge(hostId, nid, w, 'remote');
      stats.externalIps++;
      stats.edges++;
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
    }

    // Internal IP connections (lateral movement) - resolve to host if possible
    const topInternal = [...host.internalIps.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, MAX_REMOTE_PER_HOST);
    for (const [ip, w] of topInternal) {
      const remoteHostname = ipToHost.get(ip);
      if (remoteHostname && keptHostnames.has(remoteHostname) && remoteHostname !== host.hostname) {
        // Link host-to-host (lateral)
        addEdge(hostId, `host::${remoteHostname}`, w, 'lateral');
      } else {
        const nid = `intip::${ip}`;
        addNode(nid, ip, 'internal_ip');
        addEdge(hostId, nid, w, 'internal');
        stats.internalIps++;
      }
      stats.edges++;
    }

    // Domains - top N
    const topDomains = [...host.domains.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, MAX_DOMAIN_PER_HOST);
    for (const [dom, w] of topDomains) {
      const nid = `domain::${dom}`;
      addNode(nid, dom, 'domain');
      addEdge(hostId, nid, w, 'dns');
      stats.domains++;
      stats.edges++;
    }

<<<<<<< HEAD
function drawLabels(
  ctx: CanvasRenderingContext2D, graph: Graph,
  hovered: string | null, selected: string | null,
  search: string, matchSet: Set<string>, vp: Viewport,
  simplify: boolean, labelMode: LabelMode,
) {
  if (labelMode === 'none') return;
  const dimmed = search.length > 0;
  if (labelMode === 'highlight' && !search && !hovered && !selected) return;
  if (simplify && labelMode !== 'all' && !search && !hovered && !selected) {
    return;
  }
  const fontSize = Math.max(9, Math.round(12 / vp.scale));
  ctx.font = '500 ' + fontSize + 'px Inter, system-ui, sans-serif';
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
    const show = labelMode === 'all'
      ? (isHighlight || n.meta.type === 'host' || n.count >= 2)
      : isHighlight;
    if (!show) continue;
    const isDim = dimmed && !matchSet.has(n.id);
    if (isDim) continue;

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

    ctx.fillStyle = isHighlight ? '#ffffff' : n.color;
    ctx.globalAlpha = isHighlight ? 1 : 0.85;
    ctx.fillText(line1, lx, ly - (line2 ? fontSize * 0.5 : 0));
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
  vp: Viewport, animTime: number, dpr: number, labelMode: LabelMode,
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
  const simplify = graph.nodes.length > RENDER_SIMPLIFY_NODE_THRESHOLD || graph.edges.length > RENDER_SIMPLIFY_EDGE_THRESHOLD;
  drawBackground(ctx, w, h, vp, dpr, simplify);
  ctx.save();
  ctx.translate(vp.x * dpr, vp.y * dpr);
  ctx.scale(vp.scale * dpr, vp.scale * dpr);
  drawEdges(ctx, graph, hovered, selected, nodeMap, animTime, simplify);
  drawNodes(ctx, graph, hovered, selected, search, matchSet);
  drawLabels(ctx, graph, hovered, selected, search, matchSet, vp, simplify, labelMode);
  ctx.restore();
=======
    // URLs - top N
    const topUrls = [...host.urls.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, MAX_URL_PER_HOST);
    for (const [url, w] of topUrls) {
      // Shorten URL label
      let label = url;
      try { const u = new URL(url.startsWith('http') ? url : `https://${url}`); label = u.hostname + u.pathname.slice(0, 30); } catch {}
      const nid = `url::${url}`;
      addNode(nid, label, 'url');
      addEdge(hostId, nid, w, 'url');
      stats.urls++;
      stats.edges++;
    }
  }

  return { elements, stats, hostCount: hostMap.size };
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
}

// -- Cytoscape styles --

<<<<<<< HEAD
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

  // Node-circle hit has priority
  for (const n of graph.nodes) {
    const dx = n.x - wx, dy = n.y - wy;
    if (dx * dx + dy * dy < (n.radius + 5) ** 2) return n;
  }

  // Then label hit (so clicking text works too on manageable graph sizes)
  if (graph.nodes.length <= 220) {
    for (const n of graph.nodes) {
      if (isPointOnNodeLabel(n, wx, wy, vp)) return n;
    }
  }

  return null;
}

// == Auto-fit: center graph and zoom to fit all nodes ====================

function fitGraphToCanvas(graph: Graph, canvasW: number, canvasH: number): Viewport {
  if (graph.nodes.length === 0) return { x: 0, y: 0, scale: 1 };
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of graph.nodes) {
    minX = Math.min(minX, n.x - n.radius);
    minY = Math.min(minY, n.y - n.radius);
    maxX = Math.max(maxX, n.x + n.radius);
    maxY = Math.max(maxY, n.y + n.radius);
  }
  const graphW = maxX - minX || 1;
  const graphH = maxY - minY || 1;
  const pad = 80;
  const scaleX = (canvasW - pad * 2) / graphW;
  const scaleY = (canvasH - pad * 2) / graphH;
  const scale = Math.min(scaleX, scaleY, 2.5);
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  return {
    x: canvasW / 2 - cx * scale,
    y: canvasH / 2 - cy * scale,
    scale,
  };
}

// == Component =============================================================
=======
const CY_STYLES: StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'text-valign': 'bottom' as any,
      'text-halign': 'center' as any,
      'font-size': '9px',
      color: '#94a3b8',
      'text-margin-y': 4,
      'background-opacity': 0.9,
      'border-width': 1,
      'border-color': '#1e293b',
      'text-wrap': 'wrap' as any,
      'text-max-width': '120px',
    },
  },
  {
    selector: 'node[kind="host"]',
    style: {
      'background-color': KIND_COLORS.host,
      shape: 'round-rectangle' as any,
      width: 140,
      height: 60,
      'font-size': '14px',
      'font-weight': 'bold' as any,
      color: '#e2e8f0',
      'text-valign': 'center' as any,
      'text-halign': 'center' as any,
      'text-margin-y': 0,
      'text-wrap': 'wrap' as any,
      'text-max-width': '130px',
      'padding': '8px',
    } as any,
  },
  {
    selector: 'node[kind="external_ip"]',
    style: {
      'background-color': KIND_COLORS.external_ip,
      width: 50,
      height: 50,
    },
  },
  {
    selector: 'node[kind="internal_ip"]',
    style: {
      'background-color': KIND_COLORS.internal_ip,
      width: 50,
      height: 50,
    },
  },
  {
    selector: 'node[kind="domain"]',
    style: {
      'background-color': KIND_COLORS.domain,
      shape: 'diamond' as any,
      width: 55,
      height: 55,
    },
  },
  {
    selector: 'node[kind="url"]',
    style: {
      'background-color': KIND_COLORS.url,
      shape: 'triangle' as any,
      width: 45,
      height: 45,
      'font-size': '8px',
    },
  },
  {
    selector: 'edge',
    style: {
      width: 2,
      'line-color': '#334155',
      'curve-style': 'bezier' as any,
      opacity: 0.5,
    } as any,
  },
  {
    selector: 'edge[edgeKind="lateral"]',
    style: {
      'line-color': '#f59e0b',
      'line-style': 'dashed' as any,
      width: 4,
      opacity: 0.8,
    } as any,
  },
  {
    selector: 'edge[edgeKind="remote"]',
    style: {
      'line-color': '#3b82f6',
      opacity: 0.4,
    } as any,
  },
  {
    selector: 'edge[edgeKind="dns"]',
    style: {
      'line-color': '#eab308',
      opacity: 0.35,
    } as any,
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 3,
      'border-color': '#f1f5f9',
      'background-opacity': 1,
    },
  },
  {
    selector: 'node.highlighted',
    style: {
      'border-width': 3,
      'border-color': '#60a5fa',
      'font-size': '11px',
      color: '#f1f5f9',
      'z-index': 999,
    } as any,
  },
  {
    selector: 'edge.highlighted',
    style: {
      width: 2.5,
      opacity: 0.9,
      'z-index': 998,
    } as any,
  },
  {
    selector: 'node.dimmed',
    style: {
      opacity: 0.12,
    },
  },
  {
    selector: 'edge.dimmed',
    style: {
      opacity: 0.05,
    },
  },
];

// -- Component --

interface NodeDetail {
  id: string;
  label: string;
  kind: NodeKind;
  hostname?: string;
  localIp?: string;
  os?: string;
  dsNames?: string[];
  connectionCount?: number;
  neighbors: { id: string; label: string; kind: NodeKind }[];
}
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

export default function NetworkMap() {
  const [huntList, setHuntList] = useState<Hunt[]>([]);
<<<<<<< HEAD
  const [selectedHuntId, setSelectedHuntId] = useState(lastSelectedHuntId);

=======
  const [selectedHuntId, setSelectedHuntId] = useState('');
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
<<<<<<< HEAD
  const [labelMode, setLabelMode] = useState<LabelMode>('highlight');

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [canvasSize, setCanvasSize] = useState({ w: 1200, h: 800 });

  // Ref mirror of canvasSize - lets loadGraph read current size without depending on it
  const canvasSizeRef = useRef({ w: 1200, h: 800 });

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
  const hoverRafRef = useRef<number>(0);

  const [popoverAnchor, setPopoverAnchor] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => { hoveredRef.current = hovered; }, [hovered]);
  useEffect(() => { selectedNodeRef.current = selectedNode; }, [selectedNode]);
  useEffect(() => { searchRef.current = search; }, [search]);
  useEffect(() => { canvasSizeRef.current = canvasSize; }, [canvasSize, labelMode]);

  const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));

  const loadScaleAwareGraph = useCallback(async (huntId: string, forceRefresh = false) => {
    setLoading(true); setError(''); setGraph(null); setStats(null);
    setSelectedNode(null); setPopoverAnchor(null);

    const waitReadyThen = async <T,>(fn: () => Promise<T>): Promise<T> => {
      let delayMs = 1500;
      const startedAt = Date.now();
      for (;;) {
        const out: any = await fn();
        if (out && !out.status) return out as T;
        const st = await network.inventoryStatus(huntId);
        if (st.status === 'ready') {
          const out2: any = await fn();
          if (out2 && !out2.status) return out2 as T;
        }
        if (Date.now() - startedAt > 5 * 60 * 1000) throw new Error('Network data build timed out after 5 minutes');
        const jitter = Math.floor(Math.random() * 250);
        await sleep(delayMs + jitter);
        delayMs = Math.min(10000, Math.floor(delayMs * 1.5));
      }
    };

    try {
      setProgress('Loading network summary');
      const summary: any = await waitReadyThen(() => network.summary(huntId, 20));
      const totalHosts = summary?.stats?.total_hosts || 0;

      if (totalHosts > LARGE_HUNT_HOST_THRESHOLD) {
        setProgress(`Large hunt detected (${totalHosts} hosts). Loading focused subgraph`);
        const sub: any = await waitReadyThen(() => network.subgraph(huntId, LARGE_HUNT_SUBGRAPH_HOSTS, LARGE_HUNT_SUBGRAPH_EDGES));
        if (!sub?.hosts || sub.hosts.length === 0) {
          setError('No hosts found for subgraph.');
          return;
        }
        const { w, h } = canvasSizeRef.current;
        const g = buildGraphFromInventory(sub.hosts, sub.connections || [], w, h);
        simulate(g, w / 2, h / 2, 20);
        simAlphaRef.current = 0.3;
        setStats(summary.stats);
        graphCache.set(huntId, { graph: g, stats: summary.stats, ts: Date.now() });
        setGraph(g);
        return;
      }

      // Small/medium hunts: load full inventory
      setProgress('Loading host inventory');
      const inv: any = await waitReadyThen(() => network.hostInventory(huntId, forceRefresh));
      if (!inv?.hosts || inv.hosts.length === 0) {
        setError('No hosts found. Upload CSV files with host-identifying columns (ClientId, Fqdn, Hostname) to this hunt.');
        return;
      }
      const { w, h } = canvasSizeRef.current;
      const g = buildGraphFromInventory(inv.hosts, inv.connections || [], w, h);
      simulate(g, w / 2, h / 2, 30);
      simAlphaRef.current = 0.3;
      setStats(summary.stats || inv.stats);
      graphCache.set(huntId, { graph: g, stats: summary.stats || inv.stats, ts: Date.now() });
      setGraph(g);
    } catch (e: any) {
      console.error('[NetworkMap] scale-aware load error:', e);
      setError(e.message || 'Failed to load network data');
    } finally {
      setLoading(false);
      setProgress('');
    }
  }, []);

  // Persist selected hunt across tab switches
  useEffect(() => { lastSelectedHuntId = selectedHuntId; }, [selectedHuntId]);

  // Load hunts on mount + auto-select
  useEffect(() => {
    hunts.list(0, 200).then(r => {
      setHuntList(r.hunts);
      // Auto-select: restore last hunt, or pick first with datasets
      if (!selectedHuntId && r.hunts.length > 0) {
        const best = r.hunts.find(h => h.dataset_count > 0) || r.hunts[0];
        setSelectedHuntId(best.id);
      }
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Resize observer - FILL available viewport
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const updateSize = () => {
      const rect = el.getBoundingClientRect();
      const w = Math.round(rect.width);
      // Fill to bottom of viewport with 16px margin
      const h = Math.max(500, Math.round(window.innerHeight - rect.top - 16));
      if (w > 100) setCanvasSize({ w, h });
    };
    updateSize();
    const ro = new ResizeObserver(updateSize);
    ro.observe(el);
    window.addEventListener('resize', updateSize);
    return () => { ro.disconnect(); window.removeEventListener('resize', updateSize); };
  // Re-run when graph or loading changes so we catch the element appearing
  }, [graph, loading]);

  // HiDPI canvas sizing
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvasSize.w * dpr;
    canvas.height = canvasSize.h * dpr;
    canvas.style.width = canvasSize.w + 'px';
    canvas.style.height = canvasSize.h + 'px';
  }, [canvasSize, labelMode]);

  // Load graph data for selected hunt (delegates to scale-aware loader).
  const loadGraph = useCallback(async (huntId: string, forceRefresh = false) => {
    if (!huntId) return;

    // Check module-level cache first (5 min TTL)
    if (!forceRefresh) {
      const cached = graphCache.get(huntId);
      if (cached && Date.now() - cached.ts < 5 * 60 * 1000) {
        setGraph(cached.graph);
        setStats(cached.stats);
        setError('');
        simAlphaRef.current = 0;
        return;
      }
    }

    await loadScaleAwareGraph(huntId, forceRefresh);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);  // Stable - reads canvasSizeRef, no state deps

  // Single master effect: when hunt changes, check backend status, poll if building, then load
  useEffect(() => {
    if (!selectedHuntId) return;
    let cancelled = false;

    const waitUntilReady = async (): Promise<boolean> => {
      // Poll inventory-status with exponential backoff until 'ready' (or cancelled)
      setProgress('Host inventory is being prepared in the background');
      setLoading(true);
      let delayMs = 1500;
      const startedAt = Date.now();
      for (;;) {
        const jitter = Math.floor(Math.random() * 250);
        await sleep(delayMs + jitter);
        if (cancelled) return false;
        try {
          const st = await network.inventoryStatus(selectedHuntId);
          if (cancelled) return false;
          if (st.status === 'ready') return true;
          if (Date.now() - startedAt > 5 * 60 * 1000) {
            setError('Host inventory build timed out. Please retry.');
            return false;
          }
          delayMs = Math.min(10000, Math.floor(delayMs * 1.5));
          // still building or none (job may not have started yet) - keep polling
        } catch {
          if (cancelled) return false;
          delayMs = Math.min(10000, Math.floor(delayMs * 1.5));
        }
      }
    };

    const run = async () => {
      // Check module-level JS cache first (instant)
      const cached = graphCache.get(selectedHuntId);
      if (cached && Date.now() - cached.ts < 5 * 60 * 1000) {
        setGraph(cached.graph);
        setStats(cached.stats);
        setError('');
        simAlphaRef.current = 0;
=======
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [stats, setStats] = useState<{ hosts: number; internalIps: number; externalIps: number; domains: number; urls: number; edges: number } | null>(null);
  const [dsCount, setDsCount] = useState(0);
  const [totalRows, setTotalRows] = useState(0);
  const [layoutRunning, setLayoutRunning] = useState(false);
  const [hiddenKinds, setHiddenKinds] = useState<Set<NodeKind>>(new Set());

  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // Load hunts
  useEffect(() => {
    hunts.list(0, 200).then(r => setHuntList(r.hunts)).catch(() => {});
  }, []);

  // Initialize cytoscape
  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const cy = cytoscape({
      container,
      elements: [],
      style: CY_STYLES,
      layout: { name: 'preset' },
      minZoom: 0.05,
      maxZoom: 5,
      wheelSensitivity: 0.3,
    });

    // Expose for debugging
    (window as any).__cy = cy;

    // Keep Cytoscape in sync with container size at all times
    const ro = new ResizeObserver(() => { cy.resize(); });
    ro.observe(container);
    // Also force an initial resize after a frame
    requestAnimationFrame(() => { cy.resize(); });

    // Single unified tap handler — avoids any race between two handlers
    // Helper: select and show detail for a node
    const selectNode = (node: any) => {
      const data = node.data();
      const neighbors = node.neighborhood('node').map((n: any) => ({
        id: n.id(),
        label: n.data('label'),
        kind: n.data('kind'),
      }));
      setDetail({
        id: node.id(),
        label: data.label,
        kind: data.kind,
        hostname: data.hostname,
        localIp: data.localIp,
        os: data.os,
        dsNames: data.dsNames,
        connectionCount: data.connectionCount,
        neighbors,
      });
      cy.elements().removeClass('highlighted dimmed');
      const connected = node.closedNeighborhood();
      connected.addClass('highlighted');
      cy.elements().difference(connected).addClass('dimmed');
    };

    cy.on('tap', (evt: any) => {
      if (evt.target === cy) {
        // Tapped background — try to find nearest node within 30 rendered px
        const pos = evt.renderedPosition || evt.position;
        if (pos) {
          let bestNode: any = null;
          let bestDist = 30; // max snap distance in rendered pixels
          cy.nodes(':visible').forEach((n: any) => {
            const rp = n.renderedPosition();
            const dx = rp.x - pos.x;
            const dy = rp.y - pos.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < bestDist) {
              bestDist = dist;
              bestNode = n;
            }
          });
          if (bestNode) {
            selectNode(bestNode);
            return;
          }
        }
        setDetail(null);
        cy.elements().removeClass('highlighted dimmed');
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
        return;
      }
      if (evt.target.isNode && evt.target.isNode()) {
        selectNode(evt.target);
      }
    });

    cyRef.current = cy;
    return () => { ro.disconnect(); cy.destroy(); cyRef.current = null; };
  }, []);

  // Search effect
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || cy.elements().length === 0) return;
    cy.elements().removeClass('highlighted dimmed');
    if (!search) return;
    const lc = search.toLowerCase();
    const matched = cy.nodes().filter((n: any) => n.data('label').toLowerCase().includes(lc));
    if (matched.length > 0) {
      const connected = matched.closedNeighborhood();
      connected.addClass('highlighted');
      cy.elements().difference(connected).addClass('dimmed');
      cy.animate({ fit: { eles: matched, padding: 80 } } as any, { duration: 400 });
    }
  }, [search]);

  // Load graph
  const loadGraph = useCallback(async (huntId: string) => {
    if (!huntId || !cyRef.current) return;
    const cy = cyRef.current;
    setLoading(true); setError(''); setDetail(null); setStats(null);
    cy.elements().remove();
    // Ensure Cytoscape knows the container dimensions (fixes click detection
    // when container was previously hidden or resized)
    cy.resize();

    try {
      setProgress('Fetching datasets...');
      const dsRes = await datasets.list(0, 500, huntId);
      const dsList = dsRes.datasets;
      setDsCount(dsList.length);
      if (dsList.length === 0) {
        setError('This hunt has no datasets.'); setLoading(false); setProgress(''); return;
      }

      const batches: RowBatch[] = [];
      let rowTotal = 0;
      for (let i = 0; i < dsList.length; i++) {
        const ds = dsList[i];
        setProgress(`Loading ${ds.name} (${i + 1}/${dsList.length})...`);
        try {
          const detail = await datasets.get(ds.id);
          const r = await datasets.rows(ds.id, 0, 5000);
          batches.push({ rows: r.rows, ds: detail });
          rowTotal += r.rows.length;
        } catch { /* skip */ }
      }
      setTotalRows(rowTotal);

      if (batches.length === 0) {
        setError('No datasets could be loaded.'); setLoading(false); setProgress(''); return;
      }

      setProgress('Building graph model...');
      await new Promise(r => setTimeout(r, 30));
      const { elements, stats: s } = buildGraphData(batches);
      setStats(s);

      if (elements.length === 0) {
        setError('No network data found.'); setLoading(false); setProgress(''); return;
      }

      setProgress(`Laying out ${s.hosts} hosts, ${s.edges} edges...`);
      cy.add(elements);
      cy.resize(); // Ensure hit-testing coordinates are in sync

      // Run layout
      setLayoutRunning(true);
      const layout = cy.layout({
        name: 'cola',
        animate: true,
        maxSimulationTime: 4000,
        nodeSpacing: 25,
        edgeLength: (edge: any) => {
          const kind = edge.data('edgeKind');
          if (kind === 'lateral') return 100;
          if (kind === 'remote') return 180;
          return 150;
        },
        fit: true,
        padding: 40,
        randomize: true,
        convergenceThreshold: 0.01,
      } as any);

      layout.on('layoutstop', () => {
        setLayoutRunning(false);
        cy.resize();
        cy.fit(undefined, 50);
      });
      layout.run();

<<<<<<< HEAD
      try {
        // Ask backend if inventory is ready, building, or cold
        const st = await network.inventoryStatus(selectedHuntId);
        if (cancelled) return;
=======
    } catch (e: any) { setError(e.message); }
    setLoading(false); setProgress('');
  }, []);
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

        if (st.status === 'ready') {
          // Instant load from backend cache
          await loadGraph(selectedHuntId);
          return;
        }

        if (st.status === 'none') {
          // Cold cache: trigger a background build via host-inventory (returns 202)
          try { await network.hostInventory(selectedHuntId); } catch { /* 202 or error, don't care */ }
        }

        // Wait for build to finish (covers both 'building' and 'none' -> just triggered)
        const ready = await waitUntilReady();
        if (cancelled || !ready) return;

        // Now load the freshly cached data
        await loadGraph(selectedHuntId);
      } catch (e: any) {
        if (!cancelled) {
          console.error('[NetworkMap] status/load error:', e);
          setError(e.message || 'Failed to load network inventory');
          setLoading(false);
          setProgress('');
        }
      }
    };

    run();
    return () => { cancelled = true; };
  }, [selectedHuntId, loadGraph]);

<<<<<<< HEAD
  // Auto-fit viewport when graph loads
  useEffect(() => {
    if (graph) {
      const vp = fitGraphToCanvas(graph, canvasSize.w, canvasSize.h);
      vpRef.current = vp;
      setVpScale(vp.scale);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
        simAlphaRef.current *= 0.93;
        if (simAlphaRef.current < 0.01) simAlphaRef.current = 0;
      }
      drawGraph(ctx, g, hoveredRef.current, selectedNodeRef.current?.id ?? null, searchRef.current, vpRef.current, ts, dpr, labelMode);

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
  }, [canvasSize, labelMode]);

  useEffect(() => {
    if (graph) startAnimLoop();
    return () => {
      cancelAnimationFrame(animFrameRef.current);
      cancelAnimationFrame(hoverRafRef.current);
      isAnimatingRef.current = false;
    };
  }, [graph, startAnimLoop]);

  const redraw = useCallback(() => {
    if (!graph || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    if (ctx) drawGraph(ctx, graph, hovered, selectedNode?.id ?? null, search, vpRef.current, animTimeRef.current, dpr, labelMode);
  }, [graph, hovered, selectedNode, search, labelMode]);

  useEffect(() => { if (!isAnimatingRef.current) redraw(); }, [redraw]);

  useEffect(() => { if (!isAnimatingRef.current) redraw(); }, [hovered, selectedNode, search, redraw]);

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
    cancelAnimationFrame(hoverRafRef.current);
    const clientX = e.clientX;
    const clientY = e.clientY;
    hoverRafRef.current = requestAnimationFrame(() => {
      const node = hitTest(graph, canvasRef.current as HTMLCanvasElement, clientX, clientY, vpRef.current);
      setHovered(prev => (prev === (node?.id ?? null) ? prev : (node?.id ?? null)));
    });
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

=======
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
  const zoomBy = useCallback((factor: number) => {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  const fitView = useCallback(() => {
<<<<<<< HEAD
    if (!graph) return;
    const vp = fitGraphToCanvas(graph, canvasSize.w, canvasSize.h);
    vpRef.current = vp; setVpScale(vp.scale); redraw();
  }, [graph, canvasSize, redraw]);
=======
    cyRef.current?.fit(undefined, 50);
  }, []);
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

  // Toggle node kind visibility
  const toggleKind = useCallback((kind: NodeKind) => {
    setHiddenKinds(prev => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind); else next.add(kind);
      return next;
    });
  }, []);

<<<<<<< HEAD
  const nodeById = useMemo(() => {
    const m = new Map<string, GNode>();
    if (!graph) return m;
    for (const n of graph.nodes) m.set(n.id, n);
    return m;
  }, [graph]);

  const connectedNodes = useMemo(() => {
    if (!selectedNode || !graph) return [];
    const neighbors: { id: string; type: NodeType; weight: number }[] = [];
    for (const e of graph.edges) {
      if (e.source === selectedNode.id) {
        const n = nodeById.get(e.target);
        if (n) neighbors.push({ id: n.id, type: n.meta.type, weight: e.weight });
      } else if (e.target === selectedNode.id) {
        const n = nodeById.get(e.source);
        if (n) neighbors.push({ id: n.id, type: n.meta.type, weight: e.weight });
      }
    }
    return neighbors.sort((a, b) => b.weight - a.weight).slice(0, 12);
  }, [selectedNode, graph, nodeById]);
=======
  // Apply hidden kinds to cytoscape
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const allKinds: NodeKind[] = ['host', 'internal_ip', 'external_ip', 'domain', 'url'];
    for (const k of allKinds) {
      const sel = cy.nodes(`[kind="${k}"]`);
      if (hiddenKinds.has(k)) {
        sel.style('display', 'none');
        // Also hide edges connected only to hidden nodes
        sel.connectedEdges().forEach((edge: any) => {
          const srcKind = edge.source().data('kind');
          const tgtKind = edge.target().data('kind');
          if (hiddenKinds.has(srcKind) || hiddenKinds.has(tgtKind)) {
            edge.style('display', 'none');
          }
        });
      } else {
        sel.style('display', 'element');
        sel.connectedEdges().forEach((edge: any) => {
          const srcKind = edge.source().data('kind');
          const tgtKind = edge.target().data('kind');
          if (!hiddenKinds.has(srcKind) && !hiddenKinds.has(tgtKind)) {
            edge.style('display', 'element');
          }
        });
      }
    }
  }, [hiddenKinds]);
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

  // Resize Cytoscape when the detail panel opens/closes (changes flex width)
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const timer = setTimeout(() => { cy.resize(); }, 50);
    return () => clearTimeout(timer);
  }, [detail]);

<<<<<<< HEAD
  const getCursor = () => {
    if (dragNode.current) return 'grabbing';
    if (isPanning.current) return 'grabbing';
    if (hovered) return 'pointer';
    return 'grab';
  };

  // == Render ==============================================================
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* Glassmorphism toolbar */}
      <Paper
        elevation={0}
        sx={{
          mb: 1, p: 1.5, display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1.5,
          background: 'rgba(30,41,59,0.65)', backdropFilter: 'blur(16px)',
          borderColor: 'rgba(148,163,184,0.12)', flexShrink: 0,
        }}
      >
        <Stack direction="row" alignItems="center" spacing={1}>
          <HubIcon sx={{ color: theme.palette.primary.main, fontSize: 28 }} />
          <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
            Network Map
          </Typography>
        </Stack>

        <Box sx={{ flex: 1 }} />

        <FormControl size="small" sx={{ minWidth: 220 }}>
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
          sx={{ width: 220, '& .MuiInputBase-input': { py: 0.8 } }}
          slotProps={{
            input: {
              startAdornment: <SearchIcon sx={{ mr: 0.5, fontSize: 18, color: 'text.secondary' }} />,
            },
          }}
        />

        <FormControl size="small" sx={{ minWidth: 150 }}>
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

        <Tooltip title="Force refresh (ignore cache)">
          <span>
            <IconButton
              onClick={() => loadGraph(selectedHuntId, true)}
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
        <Stack direction="row" spacing={1.5} sx={{ mb: 1, flexShrink: 0 }} flexWrap="wrap" useFlexGap>
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
        <Paper sx={{ p: 2, mb: 1, background: 'rgba(30,41,59,0.65)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
          <Stack direction="row" alignItems="center" spacing={2}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>{progress}</Typography>
              <LinearProgress sx={{
                borderRadius: 1,
                '& .MuiLinearProgress-bar': {
                  background: 'linear-gradient(90deg, ' + theme.palette.primary.main + ', ' + theme.palette.info.main + ')',
                },
              }} />
            </Box>
          </Stack>
        </Paper>
      </Fade>

      {error && <Alert severity="warning" sx={{ mb: 1, flexShrink: 0 }}>{error}</Alert>}

      {/* Canvas area - takes ALL remaining space */}
      <Box ref={wrapperRef} sx={{ flex: 1, minHeight: 500, display: 'flex', flexDirection: 'column' }}>
      {graph && (
        <Paper
          sx={{
            position: 'relative', overflow: 'hidden',
            backgroundColor: BG_COLOR,
            borderColor: 'rgba(148,163,184,0.08)', borderRadius: 2,
            flex: 1, minHeight: 500,
          }}
        >
          <canvas
            ref={canvasRef}
            style={{ display: 'block', cursor: getCursor(), width: '100%', height: '100%' }}
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
              label={'Hosts (' + hostCount + ')'}
              size="small"
              sx={{
                bgcolor: TYPE_COLORS.host + '22', color: TYPE_COLORS.host,
                border: '1.5px solid ' + TYPE_COLORS.host + '88',
                fontWeight: 600, fontSize: 11,
              }}
            />
            {extCount > 0 && (
              <Chip
                label={'External IPs (' + extCount + ')'}
                size="small"
                sx={{
                  bgcolor: TYPE_COLORS.external_ip + '22', color: TYPE_COLORS.external_ip,
                  border: '1.5px solid ' + TYPE_COLORS.external_ip + '88',
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
              { tip: 'Fit to view', icon: <CenterFocusStrongIcon fontSize="small" />, fn: fitView },
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
              label={Math.round(vpScale * 100) + '%'}
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
            <Box sx={{ height: 3, background: 'linear-gradient(90deg, ' + TYPE_COLORS[selectedNode.meta.type] + ', ' + TYPE_COLORS[selectedNode.meta.type] + '44)' }} />
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
                      border: '1px solid ' + TYPE_COLORS[selectedNode.meta.type] + '44',
                    }}
                  />
=======
  return (
    <Box>
      {/* Header */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }} flexWrap="wrap" gap={1}>
        <Typography variant="h5">Network Map</Typography>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel id="hunt-sel">Hunt</InputLabel>
            <Select labelId="hunt-sel" value={selectedHuntId} label="Hunt"
              onChange={e => setSelectedHuntId(e.target.value)}>
              {huntList.map(h => (
                <MenuItem key={h.id} value={h.id}>{h.name} ({h.dataset_count} datasets)</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField size="small" placeholder="Search node..." value={search}
            onChange={e => setSearch(e.target.value)} sx={{ width: 200 }} />
          <Button variant="outlined" startIcon={<RefreshIcon />}
            onClick={() => loadGraph(selectedHuntId)} disabled={loading || !selectedHuntId} size="small">
            Refresh
          </Button>
        </Stack>
      </Stack>

      {/* Loading */}
      {(loading || layoutRunning) && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {layoutRunning ? 'Running layout...' : progress}
          </Typography>
          <LinearProgress />
        </Paper>
      )}
      {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Stats bar */}
      {stats && (
        <Stack direction="row" spacing={1} sx={{ mb: 1 }} flexWrap="wrap" gap={0.5} alignItems="center">
          <Chip label={`${dsCount} datasets`} size="small" variant="outlined" />
          <Chip label={`${totalRows.toLocaleString()} rows`} size="small" variant="outlined" />
          <Divider orientation="vertical" flexItem />
          <Chip label={`Hosts: ${stats.hosts}`} size="small" clickable
            onClick={() => toggleKind('host')}
            sx={{ bgcolor: hiddenKinds.has('host') ? 'transparent' : KIND_COLORS.host, color: '#fff', fontWeight: 600,
              border: hiddenKinds.has('host') ? `2px solid ${KIND_COLORS.host}` : 'none', opacity: hiddenKinds.has('host') ? 0.5 : 1, cursor: 'pointer' }} />
          <Chip label={`Internal: ${stats.internalIps}`} size="small" clickable
            onClick={() => toggleKind('internal_ip')}
            sx={{ bgcolor: hiddenKinds.has('internal_ip') ? 'transparent' : KIND_COLORS.internal_ip, color: '#fff', fontWeight: 600,
              border: hiddenKinds.has('internal_ip') ? `2px solid ${KIND_COLORS.internal_ip}` : 'none', opacity: hiddenKinds.has('internal_ip') ? 0.5 : 1, cursor: 'pointer' }} />
          <Chip label={`External: ${stats.externalIps}`} size="small" clickable
            onClick={() => toggleKind('external_ip')}
            sx={{ bgcolor: hiddenKinds.has('external_ip') ? 'transparent' : KIND_COLORS.external_ip, color: '#fff', fontWeight: 600,
              border: hiddenKinds.has('external_ip') ? `2px solid ${KIND_COLORS.external_ip}` : 'none', opacity: hiddenKinds.has('external_ip') ? 0.5 : 1, cursor: 'pointer' }} />
          <Chip label={`Domains: ${stats.domains}`} size="small" clickable
            onClick={() => toggleKind('domain')}
            sx={{ bgcolor: hiddenKinds.has('domain') ? 'transparent' : KIND_COLORS.domain, color: hiddenKinds.has('domain') ? '#fff' : '#000', fontWeight: 600,
              border: hiddenKinds.has('domain') ? `2px solid ${KIND_COLORS.domain}` : 'none', opacity: hiddenKinds.has('domain') ? 0.5 : 1, cursor: 'pointer' }} />
          <Chip label={`URLs: ${stats.urls}`} size="small" clickable
            onClick={() => toggleKind('url')}
            sx={{ bgcolor: hiddenKinds.has('url') ? 'transparent' : KIND_COLORS.url, color: '#fff', fontWeight: 600,
              border: hiddenKinds.has('url') ? `2px solid ${KIND_COLORS.url}` : 'none', opacity: hiddenKinds.has('url') ? 0.5 : 1, cursor: 'pointer' }} />
          <Chip label={`${stats.edges} edges`} size="small" variant="outlined" />
        </Stack>
      )}

      {/* Graph container + detail panel side-by-side */}
      <Stack direction="row" spacing={2} sx={{ position: 'relative' }}>
        {/* Cytoscape canvas */}
        <Paper sx={{
          flex: 1, minHeight: 550, position: 'relative',
          bgcolor: '#0f172a', overflow: 'hidden',
        }}>
          <Box ref={containerRef} sx={{ width: '100%', height: 550 }} />
          {/* Zoom controls */}
          <Stack direction="column" spacing={0.5}
            sx={{ position: 'absolute', top: 12, right: 12, zIndex: 2 }}>
            <IconButton size="small" onClick={() => zoomBy(1.4)} aria-label="Zoom in"
              sx={{ bgcolor: 'rgba(30,41,59,0.9)', color: '#f1f5f9', '&:hover': { bgcolor: 'rgba(51,65,85,0.95)' } }}>
              <ZoomInIcon fontSize="small" />
            </IconButton>
            <IconButton size="small" onClick={() => zoomBy(1 / 1.4)} aria-label="Zoom out"
              sx={{ bgcolor: 'rgba(30,41,59,0.9)', color: '#f1f5f9', '&:hover': { bgcolor: 'rgba(51,65,85,0.95)' } }}>
              <ZoomOutIcon fontSize="small" />
            </IconButton>
            <IconButton size="small" onClick={fitView} aria-label="Fit view"
              sx={{ bgcolor: 'rgba(30,41,59,0.9)', color: '#f1f5f9', '&:hover': { bgcolor: 'rgba(51,65,85,0.95)' } }}>
              <CenterFocusStrongIcon fontSize="small" />
            </IconButton>
          </Stack>

          {/* Legend */}
          <Stack direction="row" spacing={1} sx={{ position: 'absolute', bottom: 10, left: 12, zIndex: 2 }}>
            {([
              ['Host', KIND_COLORS.host, String.fromCharCode(9632)],
              ['Internal IP', KIND_COLORS.internal_ip, String.fromCharCode(9679)],
              ['External IP', KIND_COLORS.external_ip, String.fromCharCode(9679)],
              ['Domain', KIND_COLORS.domain, String.fromCharCode(9670)],
              ['URL', KIND_COLORS.url, String.fromCharCode(9650)],
              ['Lateral', '#f59e0b', '- -'],
            ] as [string, string, string][]).map(([label, color, icon]) => (
              <Typography key={label} variant="caption" sx={{ color, fontWeight: 600, opacity: 0.8 }}>
                {icon} {label}
              </Typography>
            ))}
          </Stack>
        </Paper>

        {/* Detail panel */}
        {detail && (
          <Paper sx={{ width: 300, p: 2, flexShrink: 0, maxHeight: 550, overflow: 'auto' }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
              <Chip label={detail.kind.replace('_', ' ').toUpperCase()} size="small"
                sx={{ bgcolor: KIND_COLORS[detail.kind], color: detail.kind === 'domain' ? '#000' : '#fff', fontWeight: 700, fontSize: 11 }} />
              <IconButton size="small" onClick={() => { setDetail(null); cyRef.current?.elements().removeClass('highlighted dimmed'); }}>
                <Typography variant="caption" color="text.secondary">X</Typography>
              </IconButton>
            </Stack>

            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1, wordBreak: 'break-all' }}>
              {detail.hostname || detail.label}
            </Typography>

            {detail.localIp && (
              <>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>IP Address</Typography>
                <Typography variant="body2" sx={{ mb: 1, fontFamily: 'monospace' }}>{detail.localIp}</Typography>
              </>
            )}

            {detail.os && (
              <>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>Operating System</Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>{detail.os}</Typography>
              </>
            )}

            {detail.connectionCount != null && (
              <>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>Total Connections</Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>{detail.connectionCount}</Typography>
              </>
            )}

            {detail.dsNames && detail.dsNames.length > 0 && (
              <Box sx={{ mb: 1.5 }}>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>Seen in datasets</Typography>
                <Stack direction="row" spacing={0.5} flexWrap="wrap" gap={0.5} sx={{ mt: 0.5 }}>
                  {detail.dsNames.map(d => <Chip key={d} label={d} size="small" variant="outlined" />)}
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
                </Stack>
              </Box>
            )}

<<<<<<< HEAD
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
                    {selectedNode.meta.ips.length > 0 ? selectedNode.meta.ips.join(', ') : 'No IP detected'}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
                    Operating System
                  </Typography>
                  <Typography variant="body2" sx={{ fontSize: 13 }}>
                    {selectedNode.meta.os || 'Unknown'}
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
                    <Typography variant="body2" sx={{ fontSize: 13 }}>No user data</Typography>
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
                <Chip label={selectedNode.meta.row_count.toLocaleString() + ' rows'} size="small"
                  sx={{ fontWeight: 600, fontSize: 11, bgcolor: 'rgba(96,165,250,0.1)', color: theme.palette.primary.main, border: '1px solid rgba(96,165,250,0.2)' }} />
                <Chip label={connectionCount + ' connections'} size="small"
                  sx={{ fontWeight: 600, fontSize: 11, bgcolor: 'rgba(244,114,182,0.1)', color: theme.palette.secondary.main, border: '1px solid rgba(244,114,182,0.2)' }} />
                <Chip label={selectedNode.meta.datasets.length + ' datasets'} size="small"
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
                          border: '1px solid ' + TYPE_COLORS[cn.type] + '33', cursor: 'pointer',
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
=======
            {detail.neighbors.length > 0 && (
              <>
                <Divider sx={{ my: 1 }} />
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  Connections ({detail.neighbors.length})
                </Typography>
                <Box sx={{ mt: 0.5, maxHeight: 250, overflow: 'auto' }}>
                  {detail.neighbors.slice(0, 50).map(n => (
                    <Stack key={n.id} direction="row" spacing={0.5} alignItems="center" sx={{ py: 0.3 }}>
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: KIND_COLORS[n.kind], flexShrink: 0 }} />
                      <Typography variant="caption" sx={{ wordBreak: 'break-all', fontFamily: 'monospace' }}>
                        {n.label.split('\n')[0]}
                      </Typography>
                    </Stack>
                  ))}
                  {detail.neighbors.length > 50 && (
                    <Typography variant="caption" color="text.secondary">
                      ...and {detail.neighbors.length - 50} more
                    </Typography>
                  )}
                </Box>
              </>
            )}
          </Paper>
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
        )}
      </Stack>

<<<<<<< HEAD
      {/* Empty states - also fill remaining space */}
      {!selectedHuntId && !loading && (
        <Paper sx={{
          flex: 1, minHeight: 500, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(30,41,59,0.4)', borderColor: 'rgba(148,163,184,0.08)',
        }}>
          <Box sx={{ textAlign: 'center' }}>
            <HubIcon sx={{ fontSize: 56, color: 'rgba(96,165,250,0.2)', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom sx={{ fontWeight: 600 }}>
              Select a hunt to visualize its network
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 480, mx: 'auto' }}>
              Choose a hunt from the dropdown above. The map builds a clean,
              deduplicated host inventory showing each endpoint with its hostname,
              IP address, OS, and logged-in users.
            </Typography>
          </Box>
        </Paper>
      )}

      {selectedHuntId && !graph && !loading && !error && (
        <Paper sx={{
          flex: 1, minHeight: 500, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(30,41,59,0.4)', borderColor: 'rgba(148,163,184,0.08)',
        }}>
          <Typography color="text.secondary">
            No host data to display. Upload datasets with host-identifying columns (ClientId, Fqdn, Hostname).
=======
      {/* Empty state */}
      {!selectedHuntId && !loading && (
        <Paper sx={{ p: 6, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Select a hunt to visualize its network
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Choose a hunt from the dropdown above. The map shows hosts as green rectangles
            connected to external IPs (blue), internal IPs (cyan), domains (yellow), and URLs (purple).
            Lateral connections between hosts are shown as dashed amber lines.
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
          </Typography>
        </Paper>
      )}
      </Box>
    </Box>
  );
}
