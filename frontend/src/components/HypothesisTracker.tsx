/**
 * HypothesisTracker — create, track status, link MITRE techniques.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Stack, Chip, Button, TextField,
  Select, MenuItem, FormControl, InputLabel, CircularProgress,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions,
  Card, CardContent, CardActions, Grid,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSnackbar } from 'notistack';
import { hypotheses, hunts, type HypothesisData, type Hunt } from '../api/client';

const STATUSES = ['draft', 'active', 'confirmed', 'rejected'];
const STATUS_COLORS: Record<string, 'default' | 'info' | 'success' | 'error'> = {
  draft: 'default', active: 'info', confirmed: 'success', rejected: 'error',
};

export default function HypothesisTracker() {
  const { enqueueSnackbar } = useSnackbar();
  const [list, setList] = useState<HypothesisData[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [filterHunt, setFilterHunt] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [dlgOpen, setDlgOpen] = useState(false);
  const [editItem, setEditItem] = useState<HypothesisData | null>(null);
  const [form, setForm] = useState({
    title: '', description: '', mitre_technique: '', status: 'draft',
    hunt_id: '', evidence_notes: '',
  });

  useEffect(() => {
    hunts.list(0, 100).then(r => setHuntList(r.hunts)).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await hypotheses.list({
        hunt_id: filterHunt || undefined,
        status: filterStatus || undefined,
        limit: 100,
      });
      setList(r.hypotheses); setTotal(r.total);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
    setLoading(false);
  }, [filterHunt, filterStatus, enqueueSnackbar]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditItem(null);
    setForm({ title: '', description: '', mitre_technique: '', status: 'draft', hunt_id: '', evidence_notes: '' });
    setDlgOpen(true);
  };

  const openEdit = (h: HypothesisData) => {
    setEditItem(h);
    setForm({
      title: h.title, description: h.description || '', mitre_technique: h.mitre_technique || '',
      status: h.status, hunt_id: h.hunt_id || '', evidence_notes: h.evidence_notes || '',
    });
    setDlgOpen(true);
  };

  const handleSave = async () => {
    try {
      if (editItem) {
        await hypotheses.update(editItem.id, {
          title: form.title, description: form.description || undefined,
          mitre_technique: form.mitre_technique || undefined, status: form.status,
          evidence_notes: form.evidence_notes || undefined,
        });
        enqueueSnackbar('Hypothesis updated', { variant: 'success' });
      } else {
        await hypotheses.create({
          title: form.title, description: form.description || undefined,
          mitre_technique: form.mitre_technique || undefined,
          hunt_id: form.hunt_id || undefined, status: form.status,
        });
        enqueueSnackbar('Hypothesis created', { variant: 'success' });
      }
      setDlgOpen(false); load();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this hypothesis?')) return;
    try {
      await hypotheses.delete(id);
      enqueueSnackbar('Deleted', { variant: 'info' }); load();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  if (loading) return <Box sx={{ p: 4 }}><CircularProgress /></Box>;

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h5">Hypotheses ({total})</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>New Hypothesis</Button>
      </Stack>

      <Paper sx={{ p: 1.5, mb: 2 }}>
        <Stack direction="row" spacing={1.5}>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Hunt</InputLabel>
            <Select label="Hunt" value={filterHunt} onChange={e => setFilterHunt(e.target.value)}>
              <MenuItem value="">All</MenuItem>
              {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Status</InputLabel>
            <Select label="Status" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
              <MenuItem value="">All</MenuItem>
              {STATUSES.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
            </Select>
          </FormControl>
        </Stack>
      </Paper>

      <Grid container spacing={2}>
        {list.map(h => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={h.id}>
            <Card variant="outlined">
              <CardContent>
                <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                  <Chip label={h.status} size="small" color={STATUS_COLORS[h.status] || 'default'} />
                  {h.mitre_technique && <Chip label={h.mitre_technique} size="small" variant="outlined" color="info" />}
                </Stack>
                <Typography variant="subtitle1" fontWeight={600}>{h.title}</Typography>
                {h.description && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{h.description}</Typography>}
                {h.evidence_notes && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    Evidence: {h.evidence_notes}
                  </Typography>
                )}
              </CardContent>
              <CardActions>
                <IconButton size="small" onClick={() => openEdit(h)}><EditIcon fontSize="small" /></IconButton>
                <IconButton size="small" color="error" onClick={() => handleDelete(h.id)}><DeleteIcon fontSize="small" /></IconButton>
              </CardActions>
            </Card>
          </Grid>
        ))}
        {list.length === 0 && (
          <Grid size={12}>
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="text.secondary" gutterBottom>No hypotheses yet. Create one to track your investigation.</Typography>
              <Typography variant="body2" color="text.secondary">
                Hypotheses let you document what you think is happening (e.g. "Attacker used T1059.001 PowerShell
                to exfiltrate data"), link them to a hunt and MITRE ATT&CK technique, then update their status
                as evidence confirms or rejects them.
              </Typography>
            </Paper>
          </Grid>
        )}
      </Grid>

      {/* Dialog */}
      <Dialog open={dlgOpen} onClose={() => setDlgOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editItem ? 'Edit Hypothesis' : 'New Hypothesis'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Title" fullWidth value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
            <TextField label="Description" fullWidth multiline rows={3} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            <TextField label="MITRE Technique" fullWidth placeholder="e.g. T1059.001" value={form.mitre_technique} onChange={e => setForm(f => ({ ...f, mitre_technique: e.target.value }))} />
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select label="Status" value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
                {STATUSES.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
              </Select>
            </FormControl>
            {!editItem && (
              <FormControl fullWidth>
                <InputLabel>Hunt</InputLabel>
                <Select label="Hunt" value={form.hunt_id} onChange={e => setForm(f => ({ ...f, hunt_id: e.target.value }))}>
                  <MenuItem value="">None</MenuItem>
                  {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
                </Select>
              </FormControl>
            )}
            <TextField label="Evidence Notes" fullWidth multiline rows={2} value={form.evidence_notes} onChange={e => setForm(f => ({ ...f, evidence_notes: e.target.value }))} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDlgOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={!form.title.trim()}>
            {editItem ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
