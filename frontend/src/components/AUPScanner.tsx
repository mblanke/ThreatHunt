/**
 * AUPScanner — Acceptable Use Policy keyword scanner.
 *
 * Three-panel layout:
 *   Left  — Theme manager (add/delete themes, expand to see/add keywords)
 *   Right — Scan controls + results DataGrid
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Paper, Stack, Button, Chip, TextField, IconButton,
  Accordion, AccordionSummary, AccordionDetails, Switch, FormControlLabel,
  CircularProgress, Alert, 
  Tooltip, Checkbox, FormGroup, LinearProgress,
  FormControl, InputLabel, Select, MenuItem,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { useSnackbar } from 'notistack';
import {
  keywords,
  datasets,
  hunts,
  type Hunt,
  type ThemeOut,
  type ScanResponse,
  type DatasetSummary,
} from '../api/client';

// ── Theme Manager (left panel) ───────────────────────────────────────

interface ThemeManagerProps {
  themes: ThemeOut[];
  onReload: () => void;
}

function ThemeManager({ themes, onReload }: ThemeManagerProps) {
  const { enqueueSnackbar } = useSnackbar();
  const [newThemeName, setNewThemeName] = useState('');
  const [newThemeColor, setNewThemeColor] = useState('#9e9e9e');
  const [newKw, setNewKw] = useState<Record<string, string>>({});

  const addTheme = useCallback(async () => {
    if (!newThemeName.trim()) return;
    try {
      await keywords.createTheme(newThemeName.trim(), newThemeColor);
      enqueueSnackbar(`Theme "${newThemeName}" created`, { variant: 'success' });
      setNewThemeName('');
      setNewThemeColor('#9e9e9e');
      onReload();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  }, [newThemeName, newThemeColor, enqueueSnackbar, onReload]);

  const deleteTheme = useCallback(async (id: string, name: string) => {
    if (!window.confirm(`Delete theme "${name}" and all its keywords?`)) return;
    try {
      await keywords.deleteTheme(id);
      enqueueSnackbar(`Theme "${name}" deleted`, { variant: 'info' });
      onReload();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  }, [enqueueSnackbar, onReload]);

  const toggleTheme = useCallback(async (id: string, enabled: boolean) => {
    try {
      await keywords.updateTheme(id, { enabled });
      onReload();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  }, [enqueueSnackbar, onReload]);

  const addKeyword = useCallback(async (themeId: string) => {
    const val = (newKw[themeId] || '').trim();
    if (!val) return;
    try {
      // Support comma-separated bulk add
      const values = val.split(',').map(v => v.trim()).filter(Boolean);
      if (values.length > 1) {
        await keywords.addKeywordsBulk(themeId, values);
        enqueueSnackbar(`Added ${values.length} keywords`, { variant: 'success' });
      } else {
        await keywords.addKeyword(themeId, values[0]);
        enqueueSnackbar(`Added "${values[0]}"`, { variant: 'success' });
      }
      setNewKw(prev => ({ ...prev, [themeId]: '' }));
      onReload();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  }, [newKw, enqueueSnackbar, onReload]);

  const deleteKeyword = useCallback(async (kwId: number) => {
    try {
      await keywords.deleteKeyword(kwId);
      onReload();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  }, [enqueueSnackbar, onReload]);

  return (
    <Paper sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      <Typography variant="h6" gutterBottom>Keyword Themes</Typography>

      {/* Add new theme */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }} alignItems="center">
        <TextField
          size="small" label="New theme" value={newThemeName}
          onChange={e => setNewThemeName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addTheme()}
          sx={{ flexGrow: 1 }}
        />
        <input
          type="color" value={newThemeColor}
          onChange={e => setNewThemeColor(e.target.value)}
          style={{ width: 36, height: 36, border: 'none', cursor: 'pointer', borderRadius: 4 }}
        />
        <IconButton color="primary" onClick={addTheme} size="small"><AddIcon /></IconButton>
      </Stack>

      {/* Theme list */}
      {themes.map(theme => (
        <Accordion key={theme.id} defaultExpanded={false} disableGutters
          sx={{ '&:before': { display: 'none' }, mb: 0.5 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ width: '100%', pr: 1 }}>
              <Chip
                label={theme.name}
                size="small"
                sx={{ bgcolor: theme.color, color: '#fff', fontWeight: 600 }}
              />
              <Typography variant="caption" color="text.secondary" sx={{ flexGrow: 1 }}>
                {theme.keyword_count} keywords
              </Typography>
              <Switch
                size="small" checked={theme.enabled}
                onClick={e => e.stopPropagation()}
                onChange={(_, checked) => toggleTheme(theme.id, checked)}
              />
              <IconButton
                size="small" color="error"
                onClick={e => { e.stopPropagation(); deleteTheme(theme.id, theme.name); }}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0 }}>
            {/* Keywords list */}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
              {theme.keywords.map(kw => (
                <Chip
                  key={kw.id}
                  label={kw.value}
                  size="small"
                  variant="outlined"
                  onDelete={() => deleteKeyword(kw.id)}
                  sx={{ borderColor: theme.color }}
                />
              ))}
            </Box>
            {/* Add keyword */}
            <Stack direction="row" spacing={1} alignItems="center">
              <TextField
                size="small" fullWidth
                placeholder="Add keyword (comma-separated for bulk)"
                value={newKw[theme.id] || ''}
                onChange={e => setNewKw(prev => ({ ...prev, [theme.id]: e.target.value }))}
                onKeyDown={e => e.key === 'Enter' && addKeyword(theme.id)}
              />
              <IconButton size="small" color="primary" onClick={() => addKeyword(theme.id)}>
                <AddIcon fontSize="small" />
              </IconButton>
            </Stack>
          </AccordionDetails>
        </Accordion>
      ))}
    </Paper>
  );
}

// ── Scan Controls + Results (right panel) ────────────────────────────

const RESULT_COLUMNS: GridColDef[] = [
  {
    field: 'theme_name', headerName: 'Theme', width: 140,
    renderCell: (params) => (
      <Chip label={params.value} size="small"
        sx={{ bgcolor: params.row.theme_color, color: '#fff', fontWeight: 600 }} />
    ),
  },
  { field: 'keyword', headerName: 'Keyword', width: 140 },
  { field: 'dataset_name', headerName: 'Dataset', width: 170 },
  { field: 'hostname', headerName: 'Hostname', width: 170, valueGetter: (v, row) => row.hostname || '' },
  { field: 'username', headerName: 'User', width: 160, valueGetter: (v, row) => row.username || '' },
  { field: 'matched_value', headerName: 'Matched Value', flex: 1, minWidth: 220 },
  { field: 'field', headerName: 'Field', width: 130 },
  { field: 'source_type', headerName: 'Source', width: 120 },
  { field: 'row_index', headerName: 'Row #', width: 90, type: 'number' },
];

export default function AUPScanner() {
  const { enqueueSnackbar } = useSnackbar();

  // State
  const [themes, setThemes] = useState<ThemeOut[]>([]);
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [selectedHuntId, setSelectedHuntId] = useState('');
  const [dsList, setDsList] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null);

  // Scan options
  const [selectedDs, setSelectedDs] = useState<Set<string>>(new Set());
  const [selectedThemes, setSelectedThemes] = useState<Set<string>>(new Set());
  const [scanHunts, setScanHunts] = useState(false);
  const [scanAnnotations, setScanAnnotations] = useState(false);
  const [scanMessages, setScanMessages] = useState(false);

  // Load themes + hunts
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [tRes, hRes] = await Promise.all([
        keywords.listThemes(),
        hunts.list(0, 200),
      ]);
      setThemes(tRes.themes);
      setHuntList(hRes.hunts);
      if (!selectedHuntId && hRes.hunts.length > 0) {
        const best = hRes.hunts.find(h => h.dataset_count > 0) || hRes.hunts[0];
        setSelectedHuntId(best.id);
      }
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
    setLoading(false);
  }, [enqueueSnackbar, selectedHuntId]);

  useEffect(() => { loadData(); }, [loadData]);

  // When hunt changes, load its datasets and auto-select all
  useEffect(() => {
    if (!selectedHuntId) { setDsList([]); setSelectedDs(new Set()); return; }
    let cancelled = false;
    datasets.list(0, 500, selectedHuntId).then(res => {
      if (cancelled) return;
      setDsList(res.datasets);
      setSelectedDs(new Set(res.datasets.slice(0, 3).map(d => d.id)));
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [selectedHuntId]);

  // Toggle helpers
  const toggleThemeSelect = (id: string) => setSelectedThemes(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  // Run scan
  const runScan = useCallback(async () => {
    if (!selectedHuntId) {
      enqueueSnackbar('Please select a hunt before running AUP scan', { variant: 'warning' });
      return;
    }
    if (selectedDs.size === 0) {
      enqueueSnackbar('No datasets selected for this hunt', { variant: 'warning' });
      return;
    }

    setScanning(true);
    setScanResult(null);
    try {
      const res = await keywords.scan({
        dataset_ids: selectedDs.size > 0 ? Array.from(selectedDs) : undefined,
        theme_ids: selectedThemes.size > 0 ? Array.from(selectedThemes) : undefined,
        scan_hunts: scanHunts,
        scan_annotations: scanAnnotations,
        scan_messages: scanMessages,
        prefer_cache: true,
      });
      setScanResult(res);
      enqueueSnackbar(`Scan complete — ${res.total_hits} hits found`, {
        variant: res.total_hits > 0 ? 'warning' : 'success',
      });
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
    setScanning(false);
  }, [selectedHuntId, selectedDs, selectedThemes, scanHunts, scanAnnotations, scanMessages, enqueueSnackbar]);

  if (loading) return <Box sx={{ p: 4, textAlign: 'center' }}><CircularProgress /></Box>;

  return (
    <Box>
      <Typography variant="h5" gutterBottom>AUP Keyword Scanner</Typography>

      <Box sx={{ display: 'flex', gap: 2, height: 'calc(100vh - 140px)' }}>
        {/* Left — Theme Manager */}
        <Box sx={{ width: 380, minWidth: 320, flexShrink: 0, overflow: 'auto' }}>
          <ThemeManager themes={themes} onReload={loadData} />
        </Box>

        {/* Right — Controls + Results */}
        <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
          {/* Scan controls */}
          <Paper sx={{ p: 2 }}>
            <Stack direction="row" spacing={3} alignItems="flex-start" flexWrap="wrap">
              {/* Hunt → Dataset selector */}
              <Box sx={{ minWidth: 220 }}>
                <Typography variant="subtitle2" gutterBottom>Hunt</Typography>
                <FormControl size="small" fullWidth>
                  <InputLabel id="aup-hunt-label">Select hunt</InputLabel>
                  <Select
                    labelId="aup-hunt-label"
                    value={selectedHuntId}
                    label="Select hunt"
                    onChange={e => setSelectedHuntId(e.target.value)}
                  >
                    {huntList.map(h => (
                      <MenuItem key={h.id} value={h.id}>
                        {h.name} ({h.dataset_count} datasets)
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                {selectedHuntId && dsList.length > 0 && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                    {dsList.length} datasets &middot; {dsList.reduce((sum, d) => sum + d.row_count, 0).toLocaleString()} rows
                  </Typography>
                )}
                {selectedHuntId && dsList.length === 0 && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                    No datasets in this hunt
                  </Typography>
                )}
                {!selectedHuntId && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                    Select a hunt to enable scoped scanning
                  </Typography>
                )}

                <FormControl size="small" fullWidth sx={{ mt: 1.2 }} disabled={!selectedHuntId || dsList.length === 0}>
                  <InputLabel id="aup-dataset-label">Datasets</InputLabel>
                  <Select
                    labelId="aup-dataset-label"
                    multiple
                    value={Array.from(selectedDs)}
                    label="Datasets"
                    renderValue={(selected) => `${(selected as string[]).length} selected`}
                    onChange={(e) => setSelectedDs(new Set(e.target.value as string[]))}
                  >
                    {dsList.map(d => (
                      <MenuItem key={d.id} value={d.id}>
                        <Checkbox size="small" checked={selectedDs.has(d.id)} />
                        <Typography variant="body2" sx={{ ml: 0.5 }}>
                          {d.name} ({d.row_count.toLocaleString()} rows)
                        </Typography>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                {selectedHuntId && dsList.length > 0 && (
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <Button size="small" onClick={() => setSelectedDs(new Set(dsList.slice(0, 3).map(d => d.id)))}>Top 3</Button>
                    <Button size="small" onClick={() => setSelectedDs(new Set(dsList.map(d => d.id)))}>All</Button>
                    <Button size="small" onClick={() => setSelectedDs(new Set())}>Clear</Button>
                  </Stack>
                )}
              </Box>

              {/* Theme selector */}
              <Box sx={{ minWidth: 200 }}>
                <Stack direction="row" alignItems="center" justifyContent="space-between">
                  <Typography variant="subtitle2">Themes</Typography>
                  {(() => { const enabled = themes.filter(t => t.enabled); return (
                    <Button size="small" sx={{ textTransform: 'none', minWidth: 0, px: 0.5, fontSize: '0.7rem' }}
                      onClick={() => {
                        if (selectedThemes.size === enabled.length) setSelectedThemes(new Set());
                        else setSelectedThemes(new Set(enabled.map(t => t.id)));
                      }}>
                      {selectedThemes.size === enabled.length && enabled.length > 0 ? 'Clear all' : 'Select all'}
                    </Button>
                  ); })()}
                </Stack>
                <FormGroup sx={{ maxHeight: 120, overflow: 'auto' }}>
                  {themes.filter(t => t.enabled).map(t => (
                    <FormControlLabel key={t.id} control={
                      <Checkbox size="small" checked={selectedThemes.has(t.id)}
                        onChange={() => toggleThemeSelect(t.id)} />
                    } label={
                      <Chip label={t.name} size="small"
                        sx={{ bgcolor: t.color, color: '#fff', fontSize: '0.75rem' }} />
                    } />
                  ))}
                </FormGroup>
                <Typography variant="caption" color="text.secondary">
                  {selectedThemes.size === 0 ? 'All enabled themes' : `${selectedThemes.size} selected`}
                </Typography>
              </Box>

              {/* Extra sources */}
              <Box>
                <Typography variant="subtitle2" gutterBottom>Also scan</Typography>
                <FormGroup>
                  <FormControlLabel control={
                    <Checkbox size="small" checked={scanHunts} onChange={(_, c) => setScanHunts(c)} />
                  } label={<Typography variant="body2">Hunts</Typography>} />
                  <FormControlLabel control={
                    <Checkbox size="small" checked={scanAnnotations} onChange={(_, c) => setScanAnnotations(c)} />
                  } label={<Typography variant="body2">Annotations</Typography>} />
                  <FormControlLabel control={
                    <Checkbox size="small" checked={scanMessages} onChange={(_, c) => setScanMessages(c)} />
                  } label={<Typography variant="body2">Messages</Typography>} />
                </FormGroup>
              </Box>

              {/* Scan button */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pt: 2 }}>
                <Button
                  variant="contained" color="warning" size="large"
                  startIcon={scanning ? <CircularProgress size={20} color="inherit" /> : <PlayArrowIcon />}
                  onClick={runScan} disabled={scanning || !selectedHuntId || selectedDs.size === 0}
                >
                  {scanning ? 'Scanning…' : 'Run Scan'}
                </Button>
                <Tooltip title="Reload themes & datasets">
                  <IconButton onClick={loadData}><RefreshIcon /></IconButton>
                </Tooltip>
              </Box>
            </Stack>
          </Paper>

          {/* Scan progress */}
          {scanning && <LinearProgress color="warning" />}

          {/* Results summary */}
          {scanResult && (
            <Alert severity={scanResult.total_hits > 0 ? 'warning' : 'success'} sx={{ py: 0.5 }}>
              <strong>{scanResult.total_hits}</strong> hits across{' '}
              <strong>{scanResult.rows_scanned}</strong> rows |{' '}
              {scanResult.themes_scanned} themes, {scanResult.keywords_scanned} keywords scanned
              {scanResult.cache_status && (
                <Chip
                  size="small"
                  label={scanResult.cache_status === 'hit' ? 'Cached' : 'Live'}
                  sx={{ ml: 1, height: 20 }}
                  color={scanResult.cache_status === 'hit' ? 'success' : 'default'}
                  variant="outlined"
                />
              )}
            </Alert>
          )}

          {/* Results DataGrid */}
          {scanResult && (
            <Paper sx={{ flexGrow: 1, minHeight: 300 }}>
              <DataGrid
                rows={scanResult.hits.map((h, i) => ({ id: i, ...h }))}
                columns={RESULT_COLUMNS}
                pageSizeOptions={[25, 50, 100]}
                initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
                density="compact"
                sx={{
                  border: 0,
                  '& .MuiDataGrid-cell': { fontSize: '0.8rem' },
                  '& .MuiDataGrid-columnHeader': { fontWeight: 700 },
                }}
              />
            </Paper>
          )}

          {/* Empty state */}
          {!scanResult && !scanning && (
            <Paper sx={{ p: 4, textAlign: 'center', flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Box>
                <Typography variant="h6" color="text.secondary">No scan results yet</Typography>
                <Typography variant="body2" color="text.secondary">
                  Select datasets and themes, then click "Run Scan" to check for AUP violations.
                </Typography>
              </Box>
            </Paper>
          )}
        </Box>
      </Box>
    </Box>
  );
}
