/**
 * AnnotationPanel — create / list / filter annotations on dataset rows.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Stack, Chip, Button, TextField,
  Select, MenuItem, FormControl, InputLabel, CircularProgress,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Dialog, DialogTitle, DialogContent, DialogActions, IconButton,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSnackbar } from 'notistack';
import { annotations, datasets, type AnnotationData, type DatasetSummary } from '../api/client';

const SEVERITIES = ['info', 'low', 'medium', 'high', 'critical'];
const TAGS = ['suspicious', 'benign', 'needs-review'];
const SEV_COLORS: Record<string, 'default' | 'info' | 'success' | 'warning' | 'error'> = {
  info: 'info', low: 'success', medium: 'warning', high: 'error', critical: 'error',
};

export default function AnnotationPanel() {
  const { enqueueSnackbar } = useSnackbar();
  const [list, setList] = useState<AnnotationData[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterTag, setFilterTag] = useState('');
  const [filterDataset, setFilterDataset] = useState('');
  const [datasetList, setDatasetList] = useState<DatasetSummary[]>([]);
  const [dlgOpen, setDlgOpen] = useState(false);
  const [form, setForm] = useState({ text: '', severity: 'info', tag: '', dataset_id: '', row_id: '' });

  useEffect(() => {
    datasets.list(0, 200).then(r => setDatasetList(r.datasets)).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await annotations.list({
        severity: filterSeverity || undefined,
        tag: filterTag || undefined,
        dataset_id: filterDataset || undefined,
        limit: 100,
      });
      setList(r.annotations); setTotal(r.total);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
    setLoading(false);
  }, [filterSeverity, filterTag, filterDataset, enqueueSnackbar]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    try {
      await annotations.create({
        text: form.text,
        severity: form.severity,
        tag: form.tag || undefined,
        dataset_id: form.dataset_id || undefined,
        row_id: form.row_id ? parseInt(form.row_id, 10) : undefined,
      });
      enqueueSnackbar('Annotation created', { variant: 'success' });
      setDlgOpen(false); load();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleDelete = async (id: string) => {
    try {
      await annotations.delete(id);
      enqueueSnackbar('Deleted', { variant: 'info' }); load();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  if (loading) return <Box sx={{ p: 4 }}><CircularProgress /></Box>;

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h5">Annotations ({total})</Typography>
        <Button variant="contained" startIcon={<AddIcon />}
          onClick={() => { setForm({ text: '', severity: 'info', tag: '', dataset_id: '', row_id: '' }); setDlgOpen(true); }}>
          New
        </Button>
      </Stack>

      {/* Filters */}
      <Paper sx={{ p: 1.5, mb: 2 }}>
        <Stack direction="row" spacing={1.5} flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Severity</InputLabel>
            <Select label="Severity" value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)}>
              <MenuItem value="">All</MenuItem>
              {SEVERITIES.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Tag</InputLabel>
            <Select label="Tag" value={filterTag} onChange={e => setFilterTag(e.target.value)}>
              <MenuItem value="">All</MenuItem>
              {TAGS.map(t => <MenuItem key={t} value={t}>{t}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Dataset</InputLabel>
            <Select label="Dataset" value={filterDataset} onChange={e => setFilterDataset(e.target.value)}>
              <MenuItem value="">All</MenuItem>
              {datasetList.map(d => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
            </Select>
          </FormControl>
        </Stack>
      </Paper>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Severity</TableCell>
              <TableCell>Tag</TableCell>
              <TableCell>Text</TableCell>
              <TableCell>Row</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {list.map(a => (
              <TableRow key={a.id} hover>
                <TableCell>
                  <Chip label={a.severity} size="small" color={SEV_COLORS[a.severity] || 'default'} variant="outlined" />
                </TableCell>
                <TableCell>{a.tag || '—'}</TableCell>
                <TableCell><Typography variant="body2" sx={{ maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.text}</Typography></TableCell>
                <TableCell>{a.row_id ?? '—'}</TableCell>
                <TableCell><Typography variant="caption">{new Date(a.created_at).toLocaleString()}</Typography></TableCell>
                <TableCell align="right">
                  <IconButton size="small" color="error" onClick={() => handleDelete(a.id)}><DeleteIcon fontSize="small" /></IconButton>
                </TableCell>
              </TableRow>
            ))}
            {list.length === 0 && (
              <TableRow><TableCell colSpan={6} align="center"><Typography color="text.secondary">No annotations</Typography></TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create dialog */}
      <Dialog open={dlgOpen} onClose={() => setDlgOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New Annotation</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Text" fullWidth multiline rows={3} value={form.text} onChange={e => setForm(f => ({ ...f, text: e.target.value }))} />
            <FormControl fullWidth>
              <InputLabel>Severity</InputLabel>
              <Select label="Severity" value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}>
                {SEVERITIES.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Tag</InputLabel>
              <Select label="Tag" value={form.tag} onChange={e => setForm(f => ({ ...f, tag: e.target.value }))}>
                <MenuItem value="">None</MenuItem>
                {TAGS.map(t => <MenuItem key={t} value={t}>{t}</MenuItem>)}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Dataset</InputLabel>
              <Select label="Dataset" value={form.dataset_id} onChange={e => setForm(f => ({ ...f, dataset_id: e.target.value }))}>
                <MenuItem value="">None</MenuItem>
                {datasetList.map(d => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
              </Select>
            </FormControl>
            <TextField label="Row Index" type="number" value={form.row_id} onChange={e => setForm(f => ({ ...f, row_id: e.target.value }))} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDlgOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate} disabled={!form.text.trim()}>Create</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
