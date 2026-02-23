/**
 * ProcessTree — interactive hierarchical process tree view.
 *
 * Key UX improvements:
 *  - Hunt dropdown auto-fetches the full tree to extract hostnames.
 *  - Host dropdown lets the user pick a single host (server-side filter).
 *  - Detail panel is absolutely positioned so it never re-flows the graph.
 *  - ResizeObserver keeps Cytoscape in sync with the container.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Box, Paper, Typography, Stack, Alert, CircularProgress,
  FormControl, InputLabel, Select, MenuItem, Chip, TextField,
  IconButton, Tooltip, Divider, Autocomplete,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RefreshIcon from '@mui/icons-material/Refresh';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong';
import cytoscape, { Core, NodeSingular } from 'cytoscape';
// @ts-ignore
import dagre from 'cytoscape-dagre';
import {
  analysis, hunts, datasets, type Hunt, type DatasetSummary,
  type ProcessNodeData,
} from '../api/client';

cytoscape.use(dagre);

/* ── helpers ───────────────────────────────────────────────────────── */

/** Recursively collect unique hostnames from process tree roots */
function collectHostnames(trees: ProcessNodeData[]): string[] {
  const set = new Set<string>();
  const walk = (n: ProcessNodeData) => {
    if (n.hostname) set.add(n.hostname);
    n.children.forEach(walk);
  };
  trees.forEach(walk);
  return Array.from(set).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
}

/** Recursively count processes */
function countNodes(trees: ProcessNodeData[]): number {
  let c = 0;
  const walk = (n: ProcessNodeData) => { c++; n.children.forEach(walk); };
  trees.forEach(walk);
  return c;
}

/* ── flatten tree for Cytoscape elements ──────────────────────────── */
function flattenTree(
  node: ProcessNodeData,
  parentId: string | null,
  nodes: any[],
  edges: any[],
  idSet: Set<string>,
) {
  let id = `${node.hostname}_${node.pid}`;
  // deduplicate: if PID appears multiple times, append row_index
  if (idSet.has(id)) id = `${id}_${node.row_index}`;
  idSet.add(id);

  const cmd = node.command_line || '';
  const isSuspicious = /powershell\s+-enc|certutil|mimikatz|psexec|mshta|cobalt|meterpreter/i.test(cmd);

  nodes.push({
    data: {
      id,
      label: `${node.name || 'unknown'}\nPID ${node.pid}`,
      pid: node.pid,
      ppid: node.ppid,
      name: node.name,
      command_line: node.command_line,
      username: node.username,
      hostname: node.hostname,
      timestamp: node.timestamp,
      dataset_name: node.dataset_name,
      severity: isSuspicious ? 'high' : 'info',
      extra: node.extra,
    },
  });

  if (parentId) {
    edges.push({
      data: { id: `e_${parentId}_${id}`, source: parentId, target: id },
    });
  }

  for (const child of node.children) {
    flattenTree(child, id, nodes, edges, idSet);
  }
}

/* ── Cytoscape stylesheet ─────────────────────────────────────────── */
const CY_STYLE: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'text-wrap': 'wrap' as any,
      'text-valign': 'center',
      'text-halign': 'center',
      'font-size': '11px',
      color: '#e2e8f0',
      'background-color': '#334155',
      'border-width': 2,
      'border-color': '#475569',
      width: 160,
      height: 50,
      shape: 'roundrectangle',
      'text-max-width': '140px',
    },
  },
  {
    selector: 'node[severity = "high"], node[severity = "critical"]',
    style: {
      'background-color': '#7f1d1d',
      'border-color': '#ef4444',
      'border-width': 3,
    },
  },
  {
    selector: 'node[severity = "medium"]',
    style: {
      'background-color': '#713f12',
      'border-color': '#eab308',
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-color': '#60a5fa',
      'border-width': 3,
      'background-color': '#1e3a5f',
    },
  },
  {
    selector: 'edge',
    style: {
      width: 2,
      'line-color': '#475569',
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'arrow-scale': 0.8,
    },
  },
  { selector: '.dimmed', style: { opacity: 0.15 } },
  { selector: '.highlighted', style: { 'border-color': '#22d3ee', 'border-width': 3 } },
];

/* ================================================================== */

export default function ProcessTree() {
  /* refs */
  const containerRef = useRef<HTMLDivElement>(null);
  const cyDivRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  /* data */
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [datasetList, setDatasetList] = useState<DatasetSummary[]>([]);

  /* selections */
  const [selectedHunt, setSelectedHunt] = useState('');
  const [selectedDataset, setSelectedDataset] = useState('');
  const [hostnames, setHostnames] = useState<string[]>([]);
  const [selectedHost, setSelectedHost] = useState('');
  const [searchText, setSearchText] = useState('');

  /* ui */
  const [loading, setLoading] = useState(false);
  const [hostsLoading, setHostsLoading] = useState(false);
  const [error, setError] = useState('');
  const [totalProcs, setTotalProcs] = useState(0);
  const [selectedNode, setSelectedNode] = useState<Record<string, any> | null>(null);

  /* ── load hunts + datasets on mount ─────────────────────────────── */
  useEffect(() => {
    (async () => {
      try {
        const [h, d] = await Promise.all([
          hunts.list(0, 100),
          datasets.list(0, 200),
        ]);
        setHuntList(h.hunts);
        setDatasetList(d.datasets);
        if (h.hunts.length > 0) setSelectedHunt(h.hunts[0].id);
      } catch {}
    })();
  }, []);

  /* ── when hunt changes, fetch all trees to extract hostnames ────── */
  useEffect(() => {
    if (!selectedHunt) return;
    let cancelled = false;
    (async () => {
      setHostsLoading(true);
      try {
        const res = await analysis.processTree({ hunt_id: selectedHunt });
        if (cancelled) return;
        const hosts = collectHostnames(res.trees);
        setHostnames(hosts);
        setTotalProcs(res.total_processes);
        // auto-pick first host so the user sees something reasonable
        if (hosts.length > 0) {
          setSelectedHost(hosts[0]);
        } else {
          setSelectedHost('');
        }
      } catch {
        if (!cancelled) setHostnames([]);
      }
      setHostsLoading(false);
    })();
    return () => { cancelled = true; };
  }, [selectedHunt]);

  /* filter datasets when hunt changes */
  const huntDatasets = selectedHunt
    ? datasetList.filter(d => d.hunt_id === selectedHunt)
    : datasetList;

  /* ── fetch tree (per host) ──────────────────────────────────────── */
  const fetchTree = useCallback(async (host?: string) => {
    const huntId = selectedDataset ? undefined : selectedHunt;
    const dsId = selectedDataset || undefined;
    if (!huntId && !dsId) return;

    setLoading(true);
    setError('');
    setSelectedNode(null);

    try {
      const hostname = (host ?? selectedHost) || undefined;
      const res = await analysis.processTree({
        dataset_id: dsId,
        hunt_id: huntId,
        hostname,
      });

      setTotalProcs(res.total_processes);

      /* build Cytoscape elements */
      const nodes: any[] = [];
      const edges: any[] = [];
      const idSet = new Set<string>();
      for (const tree of res.trees) {
        flattenTree(tree, null, nodes, edges, idSet);
      }

      /* init or update Cytoscape */
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
      if (!cyDivRef.current) return;

      /* choose layout based on whether there are actual parent→child edges */
      const hasEdges = edges.length > nodes.length * 0.1; // at least 10% connected
      const layoutConfig = hasEdges
        ? {
            name: 'dagre',
            rankDir: 'TB',
            nodeSep: 40,
            rankSep: 70,
            padding: 40,
          }
        : {
            name: 'grid',
            rows: Math.max(1, Math.ceil(Math.sqrt(nodes.length))),
            cols: Math.max(1, Math.ceil(Math.sqrt(nodes.length))),
            padding: 30,
            avoidOverlap: true,
          };

      const cy = cytoscape({
        container: cyDivRef.current,
        elements: [...nodes, ...edges],
        style: CY_STYLE as any,
        layout: layoutConfig as any,
        minZoom: 0.05,
        maxZoom: 5,
        wheelSensitivity: 0.3,
      });

      /* tap handlers */
      cy.on('tap', 'node', (evt) => {
        const nd = (evt.target as NodeSingular).data();
        setSelectedNode(nd);
      });
      cy.on('tap', (evt) => {
        if (evt.target === cy) setSelectedNode(null);
      });

      cyRef.current = cy;

      /* fit with padding after layout settles */
      requestAnimationFrame(() => {
        cy.resize();
        cy.fit(undefined, 40);
      });
    } catch (e: any) {
      setError(e.message || 'Failed to load process tree');
    }
    setLoading(false);
  }, [selectedHunt, selectedDataset, selectedHost]);

  /* re-fetch when host changes */
  useEffect(() => {
    if (selectedHost) fetchTree(selectedHost);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedHost, selectedDataset]);

  /* ── keep Cytoscape sized correctly ─────────────────────────────── */
  useEffect(() => {
    const el = cyDivRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => cyRef.current?.resize());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* cleanup Cytoscape on unmount */
  useEffect(() => {
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, []);

  /* ── search highlight ───────────────────────────────────────────── */
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass('dimmed highlighted');
    if (!searchText.trim()) return;
    const q = searchText.toLowerCase();
    const matched = cy.nodes().filter(n => {
      const d = n.data();
      return (d.name || '').toLowerCase().includes(q)
        || (d.pid || '').toLowerCase().includes(q)
        || (d.command_line || '').toLowerCase().includes(q)
        || (d.username || '').toLowerCase().includes(q);
    });
    if (matched.length === 0) return;
    cy.elements().addClass('dimmed');
    matched.removeClass('dimmed').addClass('highlighted');
    matched.connectedEdges().removeClass('dimmed');
  }, [searchText]);

  /* controls */
  const zoomIn = () => { const cy = cyRef.current; if (cy) cy.zoom({ level: cy.zoom() * 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); };
  const zoomOut = () => { const cy = cyRef.current; if (cy) cy.zoom({ level: cy.zoom() / 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); };
  const fitAll = () => cyRef.current?.fit(undefined, 40);

  const GRAPH_HEIGHT = 'calc(100vh - 230px)';

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Process Tree</Typography>

      {/* ── Toolbar ──────────────────────────────────────────────── */}
      <Paper sx={{ p: 1.5, mb: 2 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          {/* Hunt */}
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Hunt</InputLabel>
            <Select label="Hunt" value={selectedHunt}
              onChange={e => {
                setSelectedHunt(e.target.value);
                setSelectedDataset('');
                setSelectedHost('');
                setHostnames([]);
              }}>
              {huntList.map(h => (
                <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Dataset (optional) */}
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Dataset (optional)</InputLabel>
            <Select label="Dataset (optional)" value={selectedDataset}
              onChange={e => setSelectedDataset(e.target.value)}>
              <MenuItem value="">All in hunt</MenuItem>
              {huntDatasets.map(d => (
                <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Host dropdown */}
          <Autocomplete
            size="small"
            sx={{ width: 220 }}
            options={hostnames}
            value={selectedHost || null}
            loading={hostsLoading}
            onChange={(_e, v) => setSelectedHost(v || '')}
            renderInput={(params) => (
              <TextField {...params} label="Host" placeholder={hostsLoading ? 'Loading hosts…' : 'Pick a host'} />
            )}
          />

          {/* Search */}
          <TextField size="small" label="Search process…" value={searchText}
            onChange={e => setSearchText(e.target.value)}
            sx={{ width: 170 }}
          />

          <Tooltip title="Refresh"><IconButton onClick={() => fetchTree()}><RefreshIcon /></IconButton></Tooltip>
          <Tooltip title="Zoom In"><IconButton onClick={zoomIn}><ZoomInIcon /></IconButton></Tooltip>
          <Tooltip title="Zoom Out"><IconButton onClick={zoomOut}><ZoomOutIcon /></IconButton></Tooltip>
          <Tooltip title="Fit"><IconButton onClick={fitAll}><CenterFocusStrongIcon /></IconButton></Tooltip>

          <Chip label={`${totalProcs.toLocaleString()} processes`} size="small" color="info" variant="outlined" />
          {hostnames.length > 0 && (
            <Chip label={`${hostnames.length} hosts`} size="small" variant="outlined" />
          )}
        </Stack>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* ── Graph + overlay Detail panel ─────────────────────────── */}
      <Box ref={containerRef} sx={{ position: 'relative', height: GRAPH_HEIGHT, minHeight: 400 }}>
        {/* Cytoscape canvas — dedicated div with NO React children */}
        <div
          ref={cyDivRef}
          style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
            background: '#0f172a', borderRadius: 4,
          }}
        />

        {/* Overlays — sibling elements, not children of Cytoscape div */}
        {loading && (
          <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', zIndex: 5 }}>
            <CircularProgress />
          </Box>
        )}
        {!loading && !selectedHost && hostnames.length > 0 && (
          <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', textAlign: 'center', zIndex: 5 }}>
            <Typography variant="h6" color="text.secondary">
              Select a host from the dropdown to view its process tree
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {hostnames.length} hosts available with {totalProcs.toLocaleString()} total processes
            </Typography>
          </Box>
        )}

        {/* Detail panel — overlays graph on the right, doesn't affect layout */}
        {selectedNode && (
          <Paper sx={{
            position: 'absolute', top: 8, right: 8, bottom: 8,
            width: 340, p: 2, overflow: 'auto', zIndex: 10,
            bgcolor: 'rgba(15,23,42,0.95)', backdropFilter: 'blur(8px)',
            border: '1px solid', borderColor: 'divider',
          }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="h6">
                {selectedNode.name || 'Process'}
              </Typography>
              <IconButton size="small" onClick={() => setSelectedNode(null)}><CloseIcon fontSize="small" /></IconButton>
            </Stack>
            <Divider sx={{ my: 1 }} />
            <Stack spacing={0.5}>
              <DetailRow label="PID" value={selectedNode.pid} />
              <DetailRow label="PPID" value={selectedNode.ppid} />
              <DetailRow label="Host" value={selectedNode.hostname} />
              <DetailRow label="User" value={selectedNode.username} />
              <DetailRow label="Timestamp" value={selectedNode.timestamp} />
              <DetailRow label="Dataset" value={selectedNode.dataset_name} />
            </Stack>
            {selectedNode.command_line && (
              <Box sx={{ mt: 1.5 }}>
                <Typography variant="caption" color="text.secondary">Command Line</Typography>
                <Paper variant="outlined" sx={{ p: 1, mt: 0.5, fontFamily: 'monospace', fontSize: 12,
                  wordBreak: 'break-all', bgcolor: 'background.default' }}>
                  {selectedNode.command_line}
                </Paper>
              </Box>
            )}
            {selectedNode.extra && Object.keys(selectedNode.extra).length > 0 && (
              <Box sx={{ mt: 1.5 }}>
                <Typography variant="caption" color="text.secondary">Extra Fields</Typography>
                <Stack spacing={0.3} sx={{ mt: 0.5 }}>
                  {Object.entries(selectedNode.extra as Record<string, string>).map(([k, v]) => (
                    <DetailRow key={k} label={k} value={v} />
                  ))}
                </Stack>
              </Box>
            )}
            <Chip
              label={selectedNode.severity || 'info'}
              size="small" sx={{ mt: 1.5 }}
              color={
                selectedNode.severity === 'critical' || selectedNode.severity === 'high' ? 'error'
                : selectedNode.severity === 'medium' ? 'warning'
                : 'default'
              }
            />
          </Paper>
        )}
      </Box>
    </Box>
  );
}

function DetailRow({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <Typography variant="body2">
      <strong>{label}:</strong>{' '}
      <span style={{ color: '#94a3b8' }}>{value}</span>
    </Typography>
  );
}
