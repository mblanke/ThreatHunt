/**
 * DatasetViewer — list datasets, browse rows with MUI DataGrid.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Stack, Chip, CircularProgress,
  Alert, Button, IconButton, Select, MenuItem, FormControl,
  InputLabel,
} from '@mui/material';
import { DataGrid, type GridColDef, type GridPaginationModel } from '@mui/x-data-grid';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useSnackbar } from 'notistack';
import { datasets, enrichment, type DatasetSummary } from '../api/client';
import ContextMenu, { useContextMenu, type ContextTarget } from './ContextMenu';

export default function DatasetViewer() {
  const { enqueueSnackbar } = useSnackbar();
  const [list, setList] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<DatasetSummary | null>(null);
  const [rows, setRows] = useState<Record<string, any>[]>([]);
  const [rowTotal, setRowTotal] = useState(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({ page: 0, pageSize: 50 });
  const [rowLoading, setRowLoading] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const { menuPos, menuTarget, openMenu, closeMenu } = useContextMenu();

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const r = await datasets.list(0, 200);
      setList(r.datasets);
      if (r.datasets.length > 0 && !selected) setSelected(r.datasets[0]);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
    setLoading(false);
  }, [enqueueSnackbar, selected]);

  const loadRows = useCallback(async () => {
    if (!selected) return;
    setRowLoading(true);
    try {
      const r = await datasets.rows(selected.id, paginationModel.page * paginationModel.pageSize, paginationModel.pageSize);
      setRows(r.rows.map((rw, i) => ({ __id: `${paginationModel.page}-${i}`, ...rw })));
      setRowTotal(r.total);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
    setRowLoading(false);
  }, [selected, paginationModel, enqueueSnackbar]);

  useEffect(() => { loadList(); }, [loadList]);
  useEffect(() => { loadRows(); }, [loadRows]);

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this dataset?')) return;
    try {
      await datasets.delete(id);
      enqueueSnackbar('Dataset deleted', { variant: 'info' });
      if (selected?.id === id) setSelected(null);
      loadList();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleEnrich = async () => {
    if (!selected) return;
    setEnriching(true);
    try {
      const r = await enrichment.dataset(selected.id);
      enqueueSnackbar(`Enriched ${r.enriched} IOCs from ${r.iocs_found} found`, { variant: 'success' });
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
    setEnriching(false);
  };

  // IOC type → colour mapping (matches NetworkMap)
  const IOC_COLORS: Record<string, { bg: string; text: string; header: string }> = {
    ip:       { bg: 'rgba(59,130,246,0.08)', text: '#3b82f6', header: 'rgba(59,130,246,0.18)' },
    hostname: { bg: 'rgba(34,197,94,0.08)',  text: '#22c55e', header: 'rgba(34,197,94,0.18)' },
    domain:   { bg: 'rgba(234,179,8,0.08)',  text: '#eab308', header: 'rgba(234,179,8,0.18)' },
    url:      { bg: 'rgba(139,92,246,0.08)', text: '#8b5cf6', header: 'rgba(139,92,246,0.18)' },
    hash_md5: { bg: 'rgba(244,63,94,0.08)',  text: '#f43f5e', header: 'rgba(244,63,94,0.18)' },
    hash_sha1:{ bg: 'rgba(244,63,94,0.08)',  text: '#f43f5e', header: 'rgba(244,63,94,0.18)' },
    hash_sha256:{ bg: 'rgba(244,63,94,0.08)',text: '#f43f5e', header: 'rgba(244,63,94,0.18)' },
  };
  const DEFAULT_IOC_STYLE = { bg: 'rgba(251,191,36,0.08)', text: '#fbbf24', header: 'rgba(251,191,36,0.18)' };

  // Resolve IOC type for a column (first type in the array)
  const iocMap = selected?.ioc_columns ?? {};
  const iocTypeFor = (col: string): string | null => {
    const types = iocMap[col];
    if (!types || types.length === 0) return null;
    return Array.isArray(types) ? types[0] : (types as any);
  };

  // Build DataGrid columns from the first row, highlighting IOC columns
  const columns: GridColDef[] = rows.length > 0
    ? Object.keys(rows[0]).filter(k => k !== '__id').map(k => {
        const iocType = iocTypeFor(k);
        const style = iocType ? (IOC_COLORS[iocType] || DEFAULT_IOC_STYLE) : null;
        return {
          field: k,
          headerName: iocType ? `${k}  ◆ ${iocType.toUpperCase()}` : k,
          flex: 1,
          minWidth: 120,
          ...(style ? {
            headerClassName: `ioc-header-${iocType}`,
            cellClassName: `ioc-cell-${iocType}`,
          } : {}),
        } as GridColDef;
      })
    : [];

  if (loading) return <Box sx={{ p: 4 }}><CircularProgress /></Box>;

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h5">Datasets ({list.length})</Typography>
        <Stack direction="row" spacing={1}>
          <Button size="small" startIcon={<RefreshIcon />} onClick={loadList}>Refresh</Button>
          {selected && (
            <Button size="small" variant="outlined" onClick={handleEnrich} disabled={enriching}>
              {enriching ? 'Enriching...' : 'Auto-Enrich IOCs'}
            </Button>
          )}
        </Stack>
      </Stack>

      {/* Dataset selector */}
      {list.length > 0 && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
            <FormControl size="small" sx={{ minWidth: 240 }}>
              <InputLabel>Dataset</InputLabel>
              <Select
                label="Dataset"
                value={selected?.id || ''}
                onChange={e => setSelected(list.find(d => d.id === e.target.value) || null)}
              >
                {list.map(d => (
                  <MenuItem key={d.id} value={d.id}>{d.name} ({d.row_count} rows)</MenuItem>
                ))}
              </Select>
            </FormControl>
            {selected && (
              <>
                <Chip label={`${selected.row_count} rows`} size="small" />
                <Chip label={selected.encoding || 'utf-8'} size="small" variant="outlined" />
                {selected.source_tool && <Chip label={selected.source_tool} size="small" color="info" variant="outlined" />}
                {selected.artifact_type && <Chip label={selected.artifact_type} size="small" color="secondary" />}
                {selected.processing_status && selected.processing_status !== 'ready' && (
                  <Chip label={selected.processing_status} size="small"
                    color={selected.processing_status === 'done' ? 'success' : selected.processing_status === 'error' ? 'error' : 'warning'}
                    variant="outlined" />
                )}
                {selected.ioc_columns && Object.keys(selected.ioc_columns).length > 0 && (
                  <Chip label={`${Object.keys(selected.ioc_columns).length} IOC columns`} size="small" color="warning" variant="outlined" />
                )}
                <IconButton size="small" color="error" onClick={() => handleDelete(selected.id)}>
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </>
            )}
          </Stack>
          {selected?.time_range_start && (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              Time range: {selected.time_range_start} — {selected.time_range_end}
            </Typography>
          )}
        </Paper>
      )}

      {/* Data grid */}
      {selected ? (
        <Paper
          sx={{ height: 520 }}
          onContextMenu={e => {
            // Find cell value from the DataGrid event target
            const cell = (e.target as HTMLElement).closest('.MuiDataGrid-cell');
            if (!cell) return;
            const field = cell.getAttribute('data-field') || '';
            const value = cell.textContent || '';
            const rowEl = cell.closest('.MuiDataGrid-row');
            const rowIdx = rowEl ? parseInt(rowEl.getAttribute('data-rowindex') || '0', 10) : undefined;
            openMenu(e, { value, field, datasetId: selected.id, rowIndex: rowIdx });
          }}
        >
          <DataGrid
            rows={rows}
            columns={columns}
            getRowId={r => r.__id}
            rowCount={rowTotal}
            loading={rowLoading}
            paginationMode="server"
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            pageSizeOptions={[25, 50, 100]}
            density="compact"
            sx={{
              border: 'none',
              '& .MuiDataGrid-cell': { fontSize: '0.8rem', cursor: 'context-menu' },
              '& .MuiDataGrid-columnHeader': { fontWeight: 700 },
              // IOC column highlights
              ...Object.fromEntries(
                Object.entries(IOC_COLORS).flatMap(([type, c]) => [
                  [`& .ioc-header-${type}`, { backgroundColor: c.header, '& .MuiDataGrid-columnHeaderTitle': { color: c.text, fontWeight: 800 } }],
                  [`& .ioc-cell-${type}`, { backgroundColor: c.bg, borderLeft: `2px solid ${c.text}` }],
                ]),
              ),
              // Default IOC fallback
              '& [class*="ioc-header-"]': { backgroundColor: DEFAULT_IOC_STYLE.header },
              '& [class*="ioc-cell-"]': { backgroundColor: DEFAULT_IOC_STYLE.bg },
            }}
          />
        </Paper>
      ) : (
        <Alert severity="info">Upload a CSV to get started.</Alert>
      )}

      {/* Right-click context menu */}
      <ContextMenu anchorPosition={menuPos} target={menuTarget} onClose={closeMenu} />
    </Box>
  );
}
