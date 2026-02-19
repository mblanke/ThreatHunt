/**
 * HuntManager — create, list, and manage hunts.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Button, TextField, Dialog, DialogTitle,
  DialogContent, DialogActions, Chip, Stack, IconButton, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow,
  CircularProgress, Select, MenuItem, FormControl, InputLabel,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import { useSnackbar } from 'notistack';
import { hunts, reports, type Hunt } from '../api/client';

const STATUS_COLORS: Record<string, 'success' | 'default' | 'warning'> = {
  active: 'success', closed: 'default', archived: 'warning',
};

export default function HuntManager() {
  const { enqueueSnackbar } = useSnackbar();
  const [list, setList] = useState<Hunt[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [dlgOpen, setDlgOpen] = useState(false);
  const [editHunt, setEditHunt] = useState<Hunt | null>(null);
  const [form, setForm] = useState({ name: '', description: '', status: 'active' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await hunts.list(0, 100);
      setList(r.hunts); setTotal(r.total);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
    setLoading(false);
  }, [enqueueSnackbar]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setEditHunt(null); setForm({ name: '', description: '', status: 'active' }); setDlgOpen(true); };
  const openEdit = (h: Hunt) => { setEditHunt(h); setForm({ name: h.name, description: h.description || '', status: h.status }); setDlgOpen(true); };

  const handleSave = async () => {
    try {
      if (editHunt) {
        await hunts.update(editHunt.id, form);
        enqueueSnackbar('Hunt updated', { variant: 'success' });
      } else {
        await hunts.create(form.name, form.description || undefined);
        enqueueSnackbar('Hunt created', { variant: 'success' });
      }
      setDlgOpen(false); load();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this hunt?')) return;
    try {
      await hunts.delete(id);
      enqueueSnackbar('Hunt deleted', { variant: 'info' }); load();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleExport = async (id: string, fmt: 'json' | 'html' | 'csv') => {
    try {
      const data = fmt === 'json' ? JSON.stringify(await reports.json(id), null, 2)
        : fmt === 'html' ? await reports.html(id)
        : await reports.csv(id);
      const blob = new Blob([data], { type: fmt === 'json' ? 'application/json' : fmt === 'html' ? 'text/html' : 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = `hunt_${id}.${fmt}`; a.click();
      URL.revokeObjectURL(url);
      enqueueSnackbar(`Report exported as ${fmt.toUpperCase()}`, { variant: 'success' });
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  if (loading) return <Box sx={{ p: 4 }}><CircularProgress /></Box>;

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h5">Hunts ({total})</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>New Hunt</Button>
      </Stack>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Datasets</TableCell>
              <TableCell>Hypotheses</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {list.map(h => (
              <TableRow key={h.id} hover>
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>{h.name}</Typography>
                  {h.description && <Typography variant="caption" color="text.secondary">{h.description}</Typography>}
                </TableCell>
                <TableCell>
                  <Chip label={h.status} size="small" color={STATUS_COLORS[h.status] || 'default'} variant="outlined" />
                </TableCell>
                <TableCell>{h.dataset_count}</TableCell>
                <TableCell>{h.hypothesis_count}</TableCell>
                <TableCell><Typography variant="caption">{new Date(h.created_at).toLocaleDateString()}</Typography></TableCell>
                <TableCell align="right">
                  <IconButton size="small" onClick={() => openEdit(h)}><EditIcon fontSize="small" /></IconButton>
                  <IconButton size="small" onClick={() => handleExport(h.id, 'html')} title="Export HTML"><DownloadIcon fontSize="small" /></IconButton>
                  <IconButton size="small" color="error" onClick={() => handleDelete(h.id)}><DeleteIcon fontSize="small" /></IconButton>
                </TableCell>
              </TableRow>
            ))}
            {list.length === 0 && (
              <TableRow><TableCell colSpan={6} align="center"><Typography color="text.secondary">No hunts yet</Typography></TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create / Edit dialog */}
      <Dialog open={dlgOpen} onClose={() => setDlgOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editHunt ? 'Edit Hunt' : 'New Hunt'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Name" fullWidth value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <TextField label="Description" fullWidth multiline rows={3} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            {editHunt && (
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select label="Status" value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="closed">Closed</MenuItem>
                  <MenuItem value="archived">Archived</MenuItem>
                </Select>
              </FormControl>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDlgOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={!form.name.trim()}>
            {editHunt ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
