/**
 * StorylineGraph — CrowdStrike-style attack storyline visualization.
 *
 * Renders events as a directed graph using Cytoscape.js with cola layout.
 * Nodes are colour-coded by event type (process/network/file/registry).
 * Edges show spawned (parent→child) and temporal relationships.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Box, Paper, Typography, Stack, Alert, CircularProgress,
  FormControl, InputLabel, Select, MenuItem, Chip, TextField,
  IconButton, Tooltip, Divider, ToggleButton, ToggleButtonGroup,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import TimelineIcon from '@mui/icons-material/Timeline';
import cytoscape, { Core, NodeSingular } from 'cytoscape';
// @ts-ignore
import dagre from 'cytoscape-dagre';
// @ts-ignore
import cola from 'cytoscape-cola';
import {
  analysis, hunts, datasets, type Hunt, type DatasetSummary,
  type StorylineResponse,
} from '../api/client';

cytoscape.use(dagre);
cytoscape.use(cola);

/* ── colour palette by event type ──────────────────────────────────── */
const EVENT_COLORS: Record<string, string> = {
  process: '#3b82f6',
  network: '#8b5cf6',
  file: '#10b981',
  registry: '#f59e0b',
  other: '#6b7280',
};

const SEVERITY_BG: Record<string, string> = {
  critical: '#7f1d1d',
  high: '#7f1d1d',
  medium: '#713f12',
  low: '#1e3a5f',
  info: '#1e293b',
};

const SEVERITY_BORDER: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#3b82f6',
  info: '#475569',
};

/* ── shapes per event type ─────────────────────────────────────────── */
const EVENT_SHAPES: Record<string, string> = {
  process: 'roundrectangle',
  network: 'diamond',
  file: 'hexagon',
  registry: 'octagon',
  other: 'ellipse',
};

/* ── Cytoscape stylesheet ─────────────────────────────────────────── */
const CY_STYLE: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'text-wrap': 'wrap' as any,
      'text-valign': 'center',
      'text-halign': 'center',
      'font-size': '9px',
      color: '#e2e8f0',
      'background-color': '#334155',
      'border-width': 2,
      'border-color': '#475569',
      width: 130,
      height: 45,
      shape: 'roundrectangle',
      'text-max-width': '115px',
    },
  },
  /* per event type colours */
  ...Object.entries(EVENT_COLORS).map(([type, color]) => ({
    selector: `node[event_type = "${type}"]`,
    style: {
      'border-color': color,
      shape: EVENT_SHAPES[type] as any,
    },
  })),
  /* per severity background */
  ...Object.entries(SEVERITY_BG).map(([sev, bg]) => ({
    selector: `node[severity = "${sev}"]`,
    style: {
      'background-color': bg,
      'border-color': SEVERITY_BORDER[sev],
      'border-width': sev === 'critical' || sev === 'high' ? 3 : 2,
    },
  })),
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
      width: 1.5,
      'line-color': '#475569',
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'arrow-scale': 0.7,
    },
  },
  {
    selector: 'edge[relationship = "spawned"]',
    style: {
      'line-color': '#3b82f6',
      'target-arrow-color': '#3b82f6',
      width: 2,
    },
  },
  {
    selector: 'edge[relationship = "temporal"]',
    style: {
      'line-color': '#334155',
      'line-style': 'dashed',
      width: 1,
      'target-arrow-shape': 'vee',
    },
  },
];

type LayoutName = 'dagre' | 'cola';

export default function StorylineGraph() {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [datasetList, setDatasetList] = useState<DatasetSummary[]>([]);
  const [selectedHunt, setSelectedHunt] = useState('');
  const [selectedDataset, setSelectedDataset] = useState('');
  const [hostFilter, setHostFilter] = useState('');
  const [layout, setLayout] = useState<LayoutName>('dagre');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [storyline, setStoryline] = useState<StorylineResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<Record<string, any> | null>(null);

  /* load hunts + datasets */
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

  const huntDatasets = selectedHunt
    ? datasetList.filter(d => d.hunt_id === selectedHunt)
    : datasetList;

  /* fetch storyline */
  const fetchStoryline = useCallback(async () => {
    if (!selectedHunt && !selectedDataset) return;
    setLoading(true);
    setError('');
    setSelectedNode(null);

    try {
      const res = await analysis.storyline({
        dataset_id: selectedDataset || undefined,
        hunt_id: selectedDataset ? undefined : selectedHunt,
        hostname: hostFilter || undefined,
      });
      setStoryline(res);
      renderGraph(res);
    } catch (e: any) {
      setError(e.message || 'Failed to load storyline');
    }
    setLoading(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedHunt, selectedDataset, hostFilter, layout]);

  /* render Cytoscape */
  const renderGraph = useCallback((data: StorylineResponse) => {
    if (cyRef.current) cyRef.current.destroy();
    if (!containerRef.current) return;

    const elements = [...data.nodes, ...data.edges];

    const layoutConfig: any = layout === 'dagre'
      ? { name: 'dagre', rankDir: 'LR', nodeSep: 25, rankSep: 50, padding: 30 }
      : { name: 'cola', nodeSpacing: 40, edgeLength: 120, animate: false, padding: 30, maxSimulationTime: 3000 };

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: CY_STYLE as any,
      layout: layoutConfig,
      minZoom: 0.05,
      maxZoom: 4,
      wheelSensitivity: 0.3,
    });

    cy.on('tap', 'node', (evt) => {
      setSelectedNode((evt.target as NodeSingular).data());
    });
    cy.on('tap', (evt) => {
      if (evt.target === cy) setSelectedNode(null);
    });

    cyRef.current = cy;
  }, [layout]);

  /* refetch on param change */
  useEffect(() => {
    if (selectedHunt || selectedDataset) fetchStoryline();
  }, [selectedHunt, selectedDataset, fetchStoryline]);

  /* re-render on layout change */
  useEffect(() => {
    if (storyline) renderGraph(storyline);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout]);

  /* controls */
  const zoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.3);
  const zoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() / 1.3);
  const fitAll = () => cyRef.current?.fit(undefined, 40);

  const summary = storyline?.summary;

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Storyline Attack Graph</Typography>

      {/* Controls */}
      <Paper sx={{ p: 1.5, mb: 2 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Hunt</InputLabel>
            <Select label="Hunt" value={selectedHunt}
              onChange={e => { setSelectedHunt(e.target.value); setSelectedDataset(''); }}>
              {huntList.map(h => (
                <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>
              ))}
            </Select>
          </FormControl>

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

          <TextField size="small" label="Hostname" value={hostFilter}
            onChange={e => setHostFilter(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && fetchStoryline()}
            sx={{ width: 160 }}
          />

          <ToggleButtonGroup size="small" value={layout} exclusive
            onChange={(_, v) => v && setLayout(v)}>
            <ToggleButton value="dagre"><Tooltip title="Hierarchical"><AccountTreeIcon fontSize="small" /></Tooltip></ToggleButton>
            <ToggleButton value="cola"><Tooltip title="Force-directed"><TimelineIcon fontSize="small" /></Tooltip></ToggleButton>
          </ToggleButtonGroup>

          <Tooltip title="Refresh"><IconButton onClick={fetchStoryline}><RefreshIcon /></IconButton></Tooltip>
          <Tooltip title="Zoom In"><IconButton onClick={zoomIn}><ZoomInIcon /></IconButton></Tooltip>
          <Tooltip title="Zoom Out"><IconButton onClick={zoomOut}><ZoomOutIcon /></IconButton></Tooltip>
          <Tooltip title="Fit"><IconButton onClick={fitAll}><CenterFocusStrongIcon /></IconButton></Tooltip>
        </Stack>

        {/* Legend + stats */}
        {summary && (
          <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap" alignItems="center">
            <Chip label={`${summary.total_events} events`} size="small" variant="outlined" />
            <Chip label={`${summary.total_edges} edges`} size="small" variant="outlined" />
            <Chip label={`${summary.hosts?.length || 0} hosts`} size="small" variant="outlined" />
            <Divider orientation="vertical" flexItem />
            {Object.entries(EVENT_COLORS).map(([type, color]) => (
              <Chip
                key={type}
                label={`${type} (${summary.event_types?.[type] || 0})`}
                size="small"
                sx={{ borderColor: color, color }}
                variant="outlined"
              />
            ))}
          </Stack>
        )}
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Graph + Detail */}
      <Stack direction="row" spacing={2}>
        <Paper
          ref={containerRef}
          sx={{
            flex: 1,
            height: 'calc(100vh - 280px)',
            minHeight: 400,
            bgcolor: '#0f172a',
            position: 'relative',
          }}
        >
          {loading && (
            <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)' }}>
              <CircularProgress />
            </Box>
          )}
        </Paper>

        {selectedNode && (
          <Paper sx={{ width: 340, p: 2, maxHeight: 'calc(100vh - 280px)', overflow: 'auto' }}>
            <Typography variant="h6" gutterBottom>
              {selectedNode.process_name || selectedNode.label || 'Event'}
            </Typography>
            <Chip
              label={selectedNode.event_type}
              size="small"
              sx={{ borderColor: EVENT_COLORS[selectedNode.event_type] || '#6b7280',
                    color: EVENT_COLORS[selectedNode.event_type] || '#6b7280', mb: 1 }}
              variant="outlined"
            />
            <Chip
              label={selectedNode.severity}
              size="small"
              sx={{ ml: 0.5, mb: 1 }}
              color={
                selectedNode.severity === 'critical' || selectedNode.severity === 'high' ? 'error'
                : selectedNode.severity === 'medium' ? 'warning'
                : 'default'
              }
            />
            <Divider sx={{ my: 1 }} />
            <Stack spacing={0.5}>
              <DetailRow label="Hostname" value={selectedNode.hostname} />
              <DetailRow label="PID" value={selectedNode.pid} />
              <DetailRow label="PPID" value={selectedNode.ppid} />
              <DetailRow label="User" value={selectedNode.username} />
              <DetailRow label="Timestamp" value={selectedNode.timestamp} />
              <DetailRow label="Src IP" value={selectedNode.src_ip} />
              <DetailRow label="Dst IP" value={selectedNode.dst_ip} />
              <DetailRow label="Dst Port" value={selectedNode.dst_port} />
              <DetailRow label="File" value={selectedNode.file_path} />
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
          </Paper>
        )}
      </Stack>
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
