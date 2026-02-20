/**
 * QueryBar — free-text search with field filters, time-range picker,
 * and result DataGrid.  Works across all datasets in a hunt.
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  Box, Typography, Paper, Stack, TextField, Button, IconButton,
  FormControl, InputLabel, Select, MenuItem, CircularProgress,
  Alert, Chip, Tooltip, Collapse,
} from '@mui/material';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import ClearIcon from '@mui/icons-material/Clear';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import {
  hunts, datasets, analysis,
  type HuntOut, type DatasetSummary, type SearchRowsResponse,
} from '../api/client';

interface ActiveFilter { field: string; value: string }

export default function QueryBar() {
  const [huntList, setHuntList] = useState<HuntOut[]>([]);
  const [dsList, setDsList] = useState<DatasetSummary[]>([]);
  const [activeHunt, setActiveHunt] = useState('');
  const [activeDs, setActiveDs] = useState('');
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<ActiveFilter[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  const [timeStart, setTimeStart] = useState('');
  const [timeEnd, setTimeEnd] = useState('');
  const [results, setResults] = useState<SearchRowsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [availableFields, setAvailableFields] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load hunts + datasets
  useEffect(() => {
    hunts.list(0, 200).then(r => {
      setHuntList(r.hunts);
      if (r.hunts.length > 0) setActiveHunt(r.hunts[0].id);
    }).catch(() => {});
    datasets.list(0, 200).then(r => setDsList(r.datasets)).catch(() => {});
  }, []);

  // Load field names from field-stats
  useEffect(() => {
    if (!activeDs && !activeHunt) return;
    analysis.fieldStats({
      dataset_id: activeDs || undefined,
      hunt_id: activeHunt || undefined,
      top_n: 5,
    }).then(r => setAvailableFields(Object.keys(r.fields))).catch(() => {});
  }, [activeDs, activeHunt]);

  const doSearch = useCallback(async (offset = 0) => {
    if (!activeDs && !activeHunt) return;
    setLoading(true);
    setError('');
    try {
      const filterMap: Record<string, string> = {};
      filters.forEach(f => { if (f.field && f.value) filterMap[f.field] = f.value; });
      const r = await analysis.searchRows({
        dataset_id: activeDs || undefined,
        hunt_id: activeHunt || undefined,
        query,
        filters: Object.keys(filterMap).length > 0 ? filterMap : undefined,
        time_start: timeStart || undefined,
        time_end: timeEnd || undefined,
        limit: pageSize,
        offset,
      });
      setResults(r);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }, [activeDs, activeHunt, query, filters, timeStart, timeEnd, pageSize]);

  const handleSearch = () => { setPage(0); doSearch(0); };
  const handlePageChange = (model: { page: number; pageSize: number }) => {
    setPage(model.page);
    setPageSize(model.pageSize);
    doSearch(model.page * model.pageSize);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  // Filter management
  const addFilter = () => setFilters(prev => [...prev, { field: '', value: '' }]);
  const removeFilter = (i: number) => setFilters(prev => prev.filter((_, idx) => idx !== i));
  const updateFilter = (i: number, key: 'field' | 'value', val: string) =>
    setFilters(prev => prev.map((f, idx) => idx === i ? { ...f, [key]: val } : f));

  const clearAll = () => {
    setQuery('');
    setFilters([]);
    setTimeStart('');
    setTimeEnd('');
    setResults(null);
  };

  // Build columns from result rows
  const columns: GridColDef[] = results && results.rows.length > 0
    ? Object.keys(results.rows[0]).filter(k => k !== '__id').map(k => ({
      field: k, headerName: k, flex: 1, minWidth: 120,
    }))
    : [];

  const gridRows = results?.rows.map((r, i) => ({ __id: `r-${page}-${i}`, ...r })) || [];

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Search &amp; Query</Typography>

      {/* Source selectors */}
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
        </Stack>
      </Paper>

      {/* Search bar */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <TextField
            inputRef={inputRef}
            size="small" fullWidth
            placeholder="Free-text search across all fields…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            InputProps={{
              startAdornment: <SearchIcon sx={{ color: 'text.secondary', mr: 0.5 }} />,
            }}
          />
          <Tooltip title="Field filters">
            <IconButton size="small" onClick={() => setShowFilters(s => !s)}
              color={showFilters ? 'primary' : 'default'}>
              <FilterListIcon />
            </IconButton>
          </Tooltip>
          <Button variant="contained" size="small" onClick={handleSearch}
            disabled={loading || (!activeDs && !activeHunt)}>
            Search
          </Button>
          <Tooltip title="Clear all">
            <IconButton size="small" onClick={clearAll}><ClearIcon /></IconButton>
          </Tooltip>
        </Stack>

        {/* Time range */}
        <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
          <TextField
            size="small" label="Time start" type="datetime-local"
            value={timeStart} onChange={e => setTimeStart(e.target.value)}
            InputLabelProps={{ shrink: true }} sx={{ width: 220 }}
          />
          <TextField
            size="small" label="Time end" type="datetime-local"
            value={timeEnd} onChange={e => setTimeEnd(e.target.value)}
            InputLabelProps={{ shrink: true }} sx={{ width: 220 }}
          />
        </Stack>

        {/* Field filters */}
        <Collapse in={showFilters}>
          <Box sx={{ mt: 1.5 }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
              <Typography variant="caption" fontWeight={700}>Field Filters</Typography>
              <IconButton size="small" onClick={addFilter}><AddIcon fontSize="small" /></IconButton>
            </Stack>
            {filters.map((f, i) => (
              <Stack key={i} direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                <FormControl size="small" sx={{ minWidth: 160 }}>
                  <InputLabel>Field</InputLabel>
                  <Select label="Field" value={f.field}
                    onChange={e => updateFilter(i, 'field', e.target.value)}>
                    {availableFields.map(af => (
                      <MenuItem key={af} value={af}>{af}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <TextField size="small" placeholder="Contains…" value={f.value}
                  onChange={e => updateFilter(i, 'value', e.target.value)}
                  sx={{ flex: 1 }} />
                <IconButton size="small" onClick={() => removeFilter(i)}>
                  <DeleteOutlineIcon fontSize="small" />
                </IconButton>
              </Stack>
            ))}
          </Box>
        </Collapse>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading && <CircularProgress sx={{ display: 'block', mx: 'auto', my: 4 }} />}

      {/* Results */}
      {results && (
        <>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
            <Chip label={`${results.total.toLocaleString()} results`} size="small" color="primary" variant="outlined" />
            {query && <Chip label={`"${query}"`} size="small" onDelete={() => setQuery('')} />}
            {filters.filter(f => f.field && f.value).map((f, i) => (
              <Chip key={i} label={`${f.field}: ${f.value}`} size="small"
                onDelete={() => removeFilter(i)} />
            ))}
          </Stack>

          <Paper sx={{ height: 480 }}>
            <DataGrid
              rows={gridRows}
              columns={columns}
              getRowId={r => r.__id}
              rowCount={results.total}
              loading={loading}
              paginationMode="server"
              paginationModel={{ page, pageSize }}
              onPaginationModelChange={handlePageChange}
              pageSizeOptions={[25, 50, 100]}
              density="compact"
              sx={{
                border: 'none',
                '& .MuiDataGrid-cell': { fontSize: '0.8rem' },
                '& .MuiDataGrid-columnHeader': { fontWeight: 700 },
              }}
            />
          </Paper>
        </>
      )}
    </Box>
  );
}
