/**
 * KnowledgeGraph — entity-to-technique knowledge graph visualization
 * using Cytoscape.js with cola (force-directed) layout.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Box, Typography, Paper, Stack, FormControl, InputLabel, Select,
  MenuItem, CircularProgress, Alert, Chip, ToggleButton,
  ToggleButtonGroup, IconButton, Tooltip,
} from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import FitScreenIcon from '@mui/icons-material/FitScreen';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import cola from 'cytoscape-cola';
import {
  hunts, datasets, analysis,
  type HuntOut, type DatasetSummary, type KnowledgeGraphResponse,
} from '../api/client';

cytoscape.use(dagre);
cytoscape.use(cola);

const CY_STYLE: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'font-size': 9,
      'text-wrap': 'wrap',
      'text-max-width': '80px',
      color: '#ddd',
      'text-outline-color': '#111',
      'text-outline-width': 1,
      'background-color': 'data(color)',
      shape: 'data(shape)' as any,
      width: 30,
      height: 30,
    },
  },
  {
    selector: 'node[type="technique"]',
    style: {
      width: 40,
      height: 26,
      'font-size': 7,
      'background-color': '#ef4444',
      shape: 'round-tag' as any,
    },
  },
  {
    selector: 'edge',
    style: {
      width: 'mapData(weight, 1, 20, 1, 4)',
      'line-color': 'rgba(150,150,150,0.4)',
      'curve-style': 'bezier',
      'target-arrow-shape': 'none',
      label: 'data(label)',
      'font-size': 7,
      color: '#888',
    },
  },
  {
    selector: 'edge[weight > 3]',
    style: {
      'line-color': 'rgba(239,68,68,0.4)',
    },
  },
  {
    selector: ':selected',
    style: {
      'border-width': 3,
      'border-color': '#f59e0b',
    },
  },
];

export default function KnowledgeGraph() {
  const cyRef = useRef<cytoscape.Core | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [huntList, setHuntList] = useState<HuntOut[]>([]);
  const [dsList, setDsList] = useState<DatasetSummary[]>([]);
  const [activeHunt, setActiveHunt] = useState('');
  const [activeDs, setActiveDs] = useState('');
  const [data, setData] = useState<KnowledgeGraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [layout, setLayout] = useState<'cola' | 'dagre'>('cola');
  const [selectedNode, setSelectedNode] = useState<any>(null);

  useEffect(() => {
    hunts.list(0, 200).then(r => {
      setHuntList(r.hunts);
      if (r.hunts.length > 0) setActiveHunt(r.hunts[0].id);
    }).catch(() => {});
    datasets.list(0, 200).then(r => setDsList(r.datasets)).catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    if (!activeDs && !activeHunt) return;
    setLoading(true);
    setError('');
    try {
      const r = await analysis.knowledgeGraph({
        dataset_id: activeDs || undefined,
        hunt_id: activeHunt || undefined,
      });
      setData(r);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }, [activeDs, activeHunt]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Render Cytoscape
  useEffect(() => {
    if (!data || !containerRef.current) return;
    if (data.nodes.length === 0) return;

    if (cyRef.current) cyRef.current.destroy();
    const cy = cytoscape({
      container: containerRef.current,
      elements: { nodes: data.nodes, edges: data.edges },
      style: CY_STYLE,
      layout: layout === 'cola'
        ? { name: 'cola', animate: false, nodeSpacing: 20, edgeLength: 120 } as any
        : { name: 'dagre', rankDir: 'LR', nodeSep: 40, edgeSep: 10, rankSep: 80 } as any,
    });

    cy.on('tap', 'node', (e) => {
      setSelectedNode(e.target.data());
    });
    cy.on('tap', (e) => {
      if (e.target === cy) setSelectedNode(null);
    });

    cyRef.current = cy;
    return () => { cy.destroy(); };
  }, [data, layout]);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Knowledge Graph</Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Hunt</InputLabel>
            <Select label="Hunt" value={activeHunt}
              onChange={e => { setActiveHunt(e.target.value); setActiveDs(''); }}>
              <MenuItem value="">— none —</MenuItem>
              {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel>Dataset</InputLabel>
            <Select label="Dataset" value={activeDs}
              onChange={e => setActiveDs(e.target.value)}>
              <MenuItem value="">— all datasets —</MenuItem>
              {dsList.map(d => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
            </Select>
          </FormControl>

          <ToggleButtonGroup size="small" exclusive value={layout}
            onChange={(_, v) => { if (v) setLayout(v); }}>
            <ToggleButton value="cola">Force</ToggleButton>
            <ToggleButton value="dagre">Hierarchy</ToggleButton>
          </ToggleButtonGroup>

          {data?.stats && (
            <>
              <Chip label={`${data.stats.total_nodes} nodes`} size="small" color="primary" variant="outlined" />
              <Chip label={`${data.stats.total_edges} edges`} size="small" variant="outlined" />
              <Chip label={`${data.stats.techniques_found} techniques`} size="small" color="error" variant="outlined" />
            </>
          )}
        </Stack>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading && <CircularProgress sx={{ display: 'block', mx: 'auto', my: 4 }} />}

      {!loading && data && data.nodes.length > 0 && (
        <Stack direction="row" spacing={2}>
          <Paper sx={{ flex: 1, position: 'relative' }}>
            {/* Controls */}
            <Stack direction="row" spacing={0.5} sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1 }}>
              <Tooltip title="Zoom in">
                <IconButton size="small" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.2)}>
                  <ZoomInIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Zoom out">
                <IconButton size="small" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() / 1.2)}>
                  <ZoomOutIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Fit">
                <IconButton size="small" onClick={() => cyRef.current?.fit()}>
                  <FitScreenIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Stack>
            <Box ref={containerRef} sx={{ width: '100%', height: 520 }} />
          </Paper>

          {/* Detail panel + Legend */}
          <Paper sx={{ width: 260, p: 2, maxHeight: 560, overflow: 'auto' }}>
            <Typography variant="subtitle2" gutterBottom>Legend</Typography>
            <Stack spacing={0.5} sx={{ mb: 2 }}>
              {[
                { type: 'host', color: '#3b82f6', shape: 'rect' },
                { type: 'user', color: '#10b981', shape: 'circle' },
                { type: 'ip', color: '#8b5cf6', shape: 'diamond' },
                { type: 'process', color: '#f59e0b', shape: 'hexagon' },
                { type: 'technique', color: '#ef4444', shape: 'tag' },
              ].map(e => (
                <Stack key={e.type} direction="row" alignItems="center" spacing={1}>
                  <Box sx={{
                    width: 14, height: 14, borderRadius: e.shape === 'circle' ? '50%' : 2,
                    background: e.color,
                  }} />
                  <Typography variant="caption">{e.type}</Typography>
                </Stack>
              ))}
            </Stack>

            {data.stats.entity_counts && (
              <>
                <Typography variant="subtitle2" gutterBottom>Entity Counts</Typography>
                <Stack spacing={0.3} sx={{ mb: 2 }}>
                  {Object.entries(data.stats.entity_counts).map(([k, v]) => (
                    <Stack key={k} direction="row" justifyContent="space-between">
                      <Typography variant="caption">{k}</Typography>
                      <Typography variant="caption" fontWeight={700}>{v}</Typography>
                    </Stack>
                  ))}
                </Stack>
              </>
            )}

            {selectedNode && (
              <>
                <Typography variant="subtitle2" gutterBottom>Selected</Typography>
                <Stack spacing={0.5}>
                  <Chip label={selectedNode.type} size="small"
                    sx={{ background: selectedNode.color, color: '#fff' }} />
                  <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
                    {selectedNode.label}
                  </Typography>
                  {selectedNode.tactic && (
                    <Typography variant="caption" color="text.secondary">
                      Tactic: {selectedNode.tactic}
                    </Typography>
                  )}
                </Stack>
              </>
            )}
          </Paper>
        </Stack>
      )}

      {!loading && data && data.nodes.length === 0 && (
        <Alert severity="info">No entities or techniques found in the selected data.</Alert>
      )}
      {!loading && !data && !error && (
        <Alert severity="info">Select a hunt or dataset to build the knowledge graph.</Alert>
      )}
    </Box>
  );
}
