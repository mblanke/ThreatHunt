/**
 * SavedSearches - Manage bookmarked queries and recurring scans.
 * Supports IOC, keyword, NLP, and correlation search types with delta tracking.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Paper, CircularProgress, Alert, Button, Chip,
  Table, TableHead, TableRow, TableCell, TableBody, TableContainer,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, FormControl, InputLabel, Select, MenuItem,
  IconButton, Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import EditIcon from '@mui/icons-material/Edit';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import { useSnackbar } from 'notistack';
import { savedSearches, SavedSearchData, SearchRunResult } from '../api/client';

const SEARCH_TYPES = [
  { value: 'ioc_search', label: 'IOC Search' },
  { value: 'keyword_scan', label: 'Keyword Scan' },
  { value: 'nlp_query', label: 'NLP Query' },
  { value: 'correlation', label: 'Correlation' },
];

function typeColor(t: string): 'primary' | 'secondary' | 'warning' | 'info' {
  switch (t) {
    case 'ioc_search': return 'primary';
    case 'keyword_scan': return 'warning';
    case 'nlp_query': return 'info';
    case 'correlation': return 'secondary';
    default: return 'primary';
  }
}

export default function SavedSearchesView() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<SavedSearchData[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<SavedSearchData | null>(null);
  const [runResult, setRunResult] = useState<SearchRunResult | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState('');
  const [searchType, setSearchType] = useState('ioc_search');
  const [queryParams, setQueryParams] = useState('');
  const [huntId, setHuntId] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await savedSearches.list();
      setItems(data.searches);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    } finally {
      setLoading(false);
    }
  }, [enqueueSnackbar]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing(null);
    setName('');
    setSearchType('ioc_search');
    setQueryParams('');
    setHuntId('');
    setShowForm(true);
  };

  const openEdit = (item: SavedSearchData) => {
    setEditing(item);
    setName(item.name);
    setSearchType(item.search_type);
    setQueryParams(JSON.stringify(item.query_params, null, 2));
    setHuntId((item.query_params as any)?.hunt_id || '');
    setShowForm(true);
  };

  const save = async () => {
    if (!name.trim()) return;
    let params: Record<string, any> = {};
    try {
      params = JSON.parse(queryParams || '{}');
    } catch {
      enqueueSnackbar('Invalid JSON in query parameters', { variant: 'error' });
      return;
    }
    try {
      if (editing) {
        await savedSearches.update(editing.id, {
          name, search_type: searchType, query_params: params,
          hunt_id: huntId || undefined,
        });
        enqueueSnackbar('Search updated', { variant: 'success' });
      } else {
        await savedSearches.create({
          name, search_type: searchType, query_params: params,
          hunt_id: huntId || undefined,
        });
        enqueueSnackbar('Search saved', { variant: 'success' });
      }
      setShowForm(false);
      load();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const remove = async (id: string) => {
    try {
      await savedSearches.delete(id);
      enqueueSnackbar('Deleted', { variant: 'success' });
      load();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const runSearch = async (id: string) => {
    setRunning(id);
    try {
      const result = await savedSearches.run(id);
      setRunResult(result);
      setRunId(id);
      load(); // refresh last_run times
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    } finally {
      setRunning(null);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <BookmarkIcon color="primary" />
        <Typography variant="h5">Saved Searches</Typography>
        <Button startIcon={<AddIcon />} variant="contained" size="small" onClick={openCreate}>New Search</Button>
      </Box>

      {loading && <CircularProgress />}

      {!loading && items.length === 0 && (
        <Alert severity="info">
          No saved searches yet. Create one to bookmark frequently-used queries for quick re-execution.
        </Alert>
      )}

      {items.length > 0 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Hunt ID</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Last Run</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Last Count</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map(item => (
                <TableRow key={item.id} hover>
                  <TableCell sx={{ fontWeight: 500 }}>{item.name}</TableCell>
                  <TableCell>
                    <Chip label={SEARCH_TYPES.find(t => t.value === item.search_type)?.label || item.search_type}
                      color={typeColor(item.search_type)} size="small" sx={{ fontSize: '0.7rem' }} />
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>
                    {(item.query_params as any)?.hunt_id ? String((item.query_params as any).hunt_id).slice(0, 8) + '...' : 'All'}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.75rem' }}>
                    {item.last_run_at ? new Date(item.last_run_at).toLocaleString() : 'Never'}
                  </TableCell>
                  <TableCell>
                    {item.last_result_count != null ? (
                      <Chip label={item.last_result_count} size="small" color={item.last_result_count > 0 ? 'warning' : 'default'} />
                    ) : ''}
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Run now">
                      <IconButton size="small" color="success" onClick={() => runSearch(item.id)}
                        disabled={running === item.id}>
                        {running === item.id ? <CircularProgress size={16} /> : <PlayArrowIcon fontSize="small" />}
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEdit(item)}><EditIcon fontSize="small" /></IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => remove(item.id)}><DeleteIcon fontSize="small" /></IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Run result dialog */}
      <Dialog open={runResult !== null} onClose={() => setRunResult(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Search Results</DialogTitle>
        <DialogContent>
          {runResult && (
            <Box>
              <Typography variant="body2" gutterBottom>
                Search: <strong>{items.find(i => i.id === runId)?.name}</strong>
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                <Chip label={`${runResult.result_count} results`} color={runResult.result_count > 0 ? 'warning' : 'success'} />
                {runResult.delta !== undefined && runResult.delta !== null && (
                  <Chip label={`${runResult.delta >= 0 ? '+' : ''}${runResult.delta} since last run`}
                    color={runResult.delta > 0 ? 'error' : 'default'} variant="outlined" />
                )}
              </Box>
              {runResult.results && runResult.results.length > 0 && (
                <Paper variant="outlined" sx={{ p: 1, maxHeight: 300, overflow: 'auto' }}>
                  <Typography variant="caption" color="text.secondary">Preview (first {runResult.results.length} results):</Typography>
                  {runResult.results.map((item: any, i: number) => (
                    <Box key={i} sx={{ p: 0.5, borderBottom: '1px solid', borderColor: 'divider', fontSize: '0.75rem', fontFamily: 'monospace' }}>
                      {typeof item === 'string' ? item : JSON.stringify(item, null, 1)}
                    </Box>
                  ))}
                </Paper>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRunResult(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Create/Edit dialog */}
      <Dialog open={showForm} onClose={() => setShowForm(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? 'Edit Search' : 'Create Saved Search'}</DialogTitle>
        <DialogContent>
          <TextField label="Name" fullWidth value={name} onChange={e => setName(e.target.value)} sx={{ mt: 1, mb: 2 }} />
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Search Type</InputLabel>
            <Select value={searchType} onChange={e => setSearchType(e.target.value)} label="Search Type">
              {SEARCH_TYPES.map(t => <MenuItem key={t.value} value={t.value}>{t.label}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField label="Hunt ID (optional)" fullWidth value={huntId} onChange={e => setHuntId(e.target.value)} sx={{ mb: 2 }}
            placeholder="Leave empty to search all hunts" />
          <TextField label="Query Parameters (JSON)" fullWidth multiline rows={4}
            value={queryParams} onChange={e => setQueryParams(e.target.value)}
            placeholder='{"keywords": ["mimikatz", "lsass"]}'
            helperText="JSON object with search-specific parameters" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowForm(false)}>Cancel</Button>
          <Button variant="contained" onClick={save} disabled={!name.trim()}>
            {editing ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

