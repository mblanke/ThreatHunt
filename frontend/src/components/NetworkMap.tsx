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
 * Layout: cytoscape-cola (constraint-based, non-overlapping)
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
    });
  };

  const edgeSet = new Set<string>();
  const addEdge = (src: string, tgt: string, weight: number, edgeKind: string) => {
    const key = `${src}->${tgt}`;
    if (edgeSet.has(key)) return;
    edgeSet.add(key);
    elements.push({
      data: { source: src, target: tgt, weight, edgeKind },
    });
  };

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

  // Per-host: cap connections to top N by frequency
  const MAX_REMOTE_PER_HOST = 15;
  const MAX_DOMAIN_PER_HOST = 10;
  const MAX_URL_PER_HOST = 5;

  const stats = { hosts: 0, internalIps: 0, externalIps: 0, domains: 0, urls: 0, edges: 0 };

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
}

// -- Cytoscape styles --

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

export default function NetworkMap() {
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [selectedHuntId, setSelectedHuntId] = useState('');
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
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

    } catch (e: any) { setError(e.message); }
    setLoading(false); setProgress('');
  }, []);

  useEffect(() => {
    if (selectedHuntId) loadGraph(selectedHuntId);
  }, [selectedHuntId, loadGraph]);

  const zoomBy = useCallback((factor: number) => {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  const fitView = useCallback(() => {
    cyRef.current?.fit(undefined, 50);
  }, []);

  // Toggle node kind visibility
  const toggleKind = useCallback((kind: NodeKind) => {
    setHiddenKinds(prev => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind); else next.add(kind);
      return next;
    });
  }, []);

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

  // Resize Cytoscape when the detail panel opens/closes (changes flex width)
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const timer = setTimeout(() => { cy.resize(); }, 50);
    return () => clearTimeout(timer);
  }, [detail]);

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
                </Stack>
              </Box>
            )}

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
        )}
      </Stack>

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
          </Typography>
        </Paper>
      )}
    </Box>
  );
}
