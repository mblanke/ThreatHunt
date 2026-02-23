/**
 * CaseManager — case management with Kanban task board, TLP/PAP badges,
 * activity timeline, MITRE technique tags, and IOC lists.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Stack, Chip, Button, TextField,
  FormControl, InputLabel, Select, MenuItem, CircularProgress,
  Alert, IconButton, Dialog, DialogTitle, DialogContent,
  DialogActions, Divider, Tooltip, Card, CardContent, CardActions,
  Grid, Badge,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useSnackbar } from 'notistack';
import {
  cases, type CaseData, type CaseTaskData, type ActivityLogEntry,
} from '../api/client';

const STATUSES = ['open', 'in-progress', 'resolved', 'closed'];
const SEVERITIES = ['info', 'low', 'medium', 'high', 'critical'];
const TLPS = ['white', 'green', 'amber', 'red'];
const PRIORITIES = [
  { value: 1, label: 'P1 — Urgent' },
  { value: 2, label: 'P2 — High' },
  { value: 3, label: 'P3 — Medium' },
  { value: 4, label: 'P4 — Low' },
];

const SEV_COLORS: Record<string, 'default' | 'info' | 'success' | 'warning' | 'error'> = {
  info: 'info', low: 'success', medium: 'warning', high: 'error', critical: 'error',
};
const TLP_COLORS: Record<string, string> = {
  white: '#fff', green: '#22c55e', amber: '#f59e0b', red: '#ef4444',
};
const TASK_COLUMNS = ['todo', 'in-progress', 'done'];
const TASK_COL_LABELS: Record<string, string> = { 'todo': 'To Do', 'in-progress': 'In Progress', 'done': 'Done' };

export default function CaseManager() {
  const { enqueueSnackbar } = useSnackbar();
  const [caseList, setCaseList] = useState<CaseData[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [selectedCase, setSelectedCase] = useState<CaseData | null>(null);
  const [activityLog, setActivityLog] = useState<ActivityLogEntry[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [taskDlgOpen, setTaskDlgOpen] = useState(false);
  const [form, setForm] = useState({
    title: '', description: '', severity: 'medium', tlp: 'amber', pap: 'amber', priority: 2,
    assignee: '', tags: '',
  });
  const [taskForm, setTaskForm] = useState({ title: '', description: '', assignee: '' });

  const loadCases = useCallback(async () => {
    setLoading(true);
    try {
      const r = await cases.list({ status: filterStatus || undefined, limit: 100 });
      setCaseList(r.cases);
      setTotal(r.total);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
    setLoading(false);
  }, [filterStatus, enqueueSnackbar]);

  useEffect(() => { loadCases(); }, [loadCases]);

  const loadCaseDetail = async (id: string) => {
    try {
      const [c, a] = await Promise.all([cases.get(id), cases.activity(id)]);
      setSelectedCase(c);
      setActivityLog(a.logs);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleCreate = async () => {
    try {
      const tags = form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [];
      await cases.create({
        title: form.title,
        description: form.description || undefined,
        severity: form.severity,
        tlp: form.tlp,
        pap: form.pap,
        priority: form.priority,
        assignee: form.assignee || undefined,
        tags,
      } as any);
      enqueueSnackbar('Case created', { variant: 'success' });
      setCreateOpen(false);
      loadCases();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleStatusChange = async (caseId: string, newStatus: string) => {
    try {
      await cases.update(caseId, { status: newStatus } as any);
      enqueueSnackbar(`Status → ${newStatus}`, { variant: 'info' });
      if (selectedCase?.id === caseId) loadCaseDetail(caseId);
      loadCases();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this case?')) return;
    try {
      await cases.delete(id);
      enqueueSnackbar('Case deleted', { variant: 'info' });
      if (selectedCase?.id === id) setSelectedCase(null);
      loadCases();
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleAddTask = async () => {
    if (!selectedCase) return;
    try {
      await cases.addTask(selectedCase.id, {
        title: taskForm.title,
        description: taskForm.description || undefined,
        assignee: taskForm.assignee || undefined,
      });
      enqueueSnackbar('Task added', { variant: 'success' });
      setTaskDlgOpen(false);
      loadCaseDetail(selectedCase.id);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleTaskStatusChange = async (taskId: string, newStatus: string) => {
    if (!selectedCase) return;
    try {
      await cases.updateTask(selectedCase.id, taskId, { status: newStatus } as any);
      loadCaseDetail(selectedCase.id);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  const handleDeleteTask = async (taskId: string) => {
    if (!selectedCase) return;
    try {
      await cases.deleteTask(selectedCase.id, taskId);
      loadCaseDetail(selectedCase.id);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  };

  if (loading) return <Box sx={{ p: 4 }}><CircularProgress /></Box>;

  // ── Case Detail View ───────────────────────────────────────────────

  if (selectedCase) {
    return (
      <Box>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
          <IconButton onClick={() => setSelectedCase(null)}><ArrowBackIcon /></IconButton>
          <Typography variant="h5">{selectedCase.title}</Typography>
          <Chip label={selectedCase.severity} size="small" color={SEV_COLORS[selectedCase.severity] || 'default'} />
          <Chip label={`TLP:${selectedCase.tlp.toUpperCase()}`} size="small"
            sx={{ background: TLP_COLORS[selectedCase.tlp], color: selectedCase.tlp === 'white' ? '#000' : '#fff' }} />
          <Chip label={selectedCase.status} size="small" variant="outlined" />
        </Stack>

        {selectedCase.description && (
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="body2" color="text.secondary">{selectedCase.description}</Typography>
          </Paper>
        )}

        {/* Status control */}
        <Paper sx={{ p: 1.5, mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="caption" fontWeight={700}>Status:</Typography>
            {STATUSES.map(s => (
              <Button key={s} size="small"
                variant={selectedCase.status === s ? 'contained' : 'outlined'}
                onClick={() => handleStatusChange(selectedCase.id, s)}>
                {s}
              </Button>
            ))}
            <Box sx={{ flex: 1 }} />
            {selectedCase.assignee && (
              <Chip label={`Assigned: ${selectedCase.assignee}`} size="small" variant="outlined" />
            )}
            <Chip label={`P${selectedCase.priority}`} size="small" />
          </Stack>
        </Paper>

        {/* Tags + MITRE */}
        {(selectedCase.tags.length > 0 || selectedCase.mitre_techniques.length > 0) && (
          <Paper sx={{ p: 1.5, mb: 2 }}>
            <Stack direction="row" spacing={0.5} flexWrap="wrap">
              {selectedCase.tags.map(t => <Chip key={t} label={t} size="small" variant="outlined" />)}
              {selectedCase.mitre_techniques.map(t => (
                <Chip key={t} label={t} size="small" color="error" variant="outlined" />
              ))}
            </Stack>
          </Paper>
        )}

        {/* Kanban Task Board */}
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
          <Typography variant="h6">Tasks</Typography>
          <IconButton size="small" onClick={() => {
            setTaskForm({ title: '', description: '', assignee: '' });
            setTaskDlgOpen(true);
          }}><AddIcon /></IconButton>
        </Stack>

        <Grid container spacing={2} sx={{ mb: 2 }}>
          {TASK_COLUMNS.map(col => {
            const colTasks = (selectedCase.tasks || []).filter(t => t.status === col);
            return (
              <Grid key={col} size={{ xs: 12, md: 4 }}>
                <Paper sx={{ p: 1, minHeight: 200, background: 'rgba(255,255,255,0.02)' }}>
                  <Typography variant="subtitle2" sx={{ mb: 1, textAlign: 'center' }}>
                    {TASK_COL_LABELS[col]}
                    <Badge badgeContent={colTasks.length} color="primary" sx={{ ml: 1 }} />
                  </Typography>
                  <Stack spacing={1}>
                    {colTasks.map(task => (
                      <Card key={task.id} variant="outlined" sx={{ position: 'relative' }}>
                        <CardContent sx={{ py: 1, px: 1.5, '&:last-child': { pb: 1 } }}>
                          <Typography variant="body2" fontWeight={600}>{task.title}</Typography>
                          {task.description && (
                            <Typography variant="caption" color="text.secondary">{task.description}</Typography>
                          )}
                          {task.assignee && (
                            <Chip label={task.assignee} size="small" sx={{ mt: 0.5 }} />
                          )}
                        </CardContent>
                        <CardActions sx={{ py: 0, px: 1 }}>
                          {col !== 'todo' && (
                            <Button size="small" onClick={() =>
                              handleTaskStatusChange(task.id, col === 'done' ? 'in-progress' : 'todo')}>
                              ←
                            </Button>
                          )}
                          {col !== 'done' && (
                            <Button size="small" onClick={() =>
                              handleTaskStatusChange(task.id, col === 'todo' ? 'in-progress' : 'done')}>
                              →
                            </Button>
                          )}
                          <Box sx={{ flex: 1 }} />
                          <IconButton size="small" color="error" onClick={() => handleDeleteTask(task.id)}>
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </CardActions>
                      </Card>
                    ))}
                  </Stack>
                </Paper>
              </Grid>
            );
          })}
        </Grid>

        {/* Activity Log */}
        {activityLog.length > 0 && (
          <>
            <Typography variant="h6" sx={{ mb: 1 }}>Activity</Typography>
            <Paper sx={{ p: 1.5, maxHeight: 200, overflow: 'auto' }}>
              {activityLog.map(l => (
                <Stack key={l.id} direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ minWidth: 140 }}>
                    {l.created_at ? new Date(l.created_at).toLocaleString() : ''}
                  </Typography>
                  <Chip label={l.action} size="small" variant="outlined" />
                  {l.details && (
                    <Typography variant="caption" color="text.secondary">
                      {JSON.stringify(l.details).slice(0, 100)}
                    </Typography>
                  )}
                </Stack>
              ))}
            </Paper>
          </>
        )}

        {/* Task create dialog */}
        <Dialog open={taskDlgOpen} onClose={() => setTaskDlgOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>New Task</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField label="Title" fullWidth value={taskForm.title}
                onChange={e => setTaskForm(f => ({ ...f, title: e.target.value }))} />
              <TextField label="Description" fullWidth multiline rows={2} value={taskForm.description}
                onChange={e => setTaskForm(f => ({ ...f, description: e.target.value }))} />
              <TextField label="Assignee" fullWidth value={taskForm.assignee}
                onChange={e => setTaskForm(f => ({ ...f, assignee: e.target.value }))} />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setTaskDlgOpen(false)}>Cancel</Button>
            <Button variant="contained" onClick={handleAddTask} disabled={!taskForm.title.trim()}>Create</Button>
          </DialogActions>
        </Dialog>
      </Box>
    );
  }

  // ── Case List View ─────────────────────────────────────────────────

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h5">Cases ({total})</Typography>
        <Button variant="contained" startIcon={<AddIcon />}
          onClick={() => {
            setForm({ title: '', description: '', severity: 'medium', tlp: 'amber', pap: 'amber', priority: 2, assignee: '', tags: '' });
            setCreateOpen(true);
          }}>New Case</Button>
      </Stack>

      <Paper sx={{ p: 1.5, mb: 2 }}>
        <Stack direction="row" spacing={1.5}>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Status</InputLabel>
            <Select label="Status" value={filterStatus}
              onChange={e => setFilterStatus(e.target.value)}>
              <MenuItem value="">All</MenuItem>
              {STATUSES.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
            </Select>
          </FormControl>
        </Stack>
      </Paper>

      <Stack spacing={1}>
        {caseList.map(c => (
          <Paper key={c.id} sx={{ p: 1.5, cursor: 'pointer', '&:hover': { borderColor: 'primary.main' } }}
            variant="outlined"
            onClick={() => loadCaseDetail(c.id)}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Typography variant="body1" fontWeight={600} sx={{ flex: 1 }}>{c.title}</Typography>
              <Chip label={c.severity} size="small" color={SEV_COLORS[c.severity] || 'default'} />
              <Chip label={`TLP:${c.tlp.toUpperCase()}`} size="small"
                sx={{ background: TLP_COLORS[c.tlp], color: c.tlp === 'white' ? '#000' : '#fff', fontSize: '0.65rem' }} />
              <Chip label={c.status} size="small" variant="outlined" />
              <Chip label={`P${c.priority}`} size="small" />
              {c.assignee && <Chip label={c.assignee} size="small" variant="outlined" />}
              <Typography variant="caption" color="text.secondary">
                {c.tasks.length} tasks
              </Typography>
              <IconButton size="small" color="error" onClick={e => { e.stopPropagation(); handleDelete(c.id); }}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>
          </Paper>
        ))}
        {caseList.length === 0 && (
          <Alert severity="info">No cases found. Create one to get started.</Alert>
        )}
      </Stack>

      {/* Create case dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New Case</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Title" fullWidth value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
            <TextField label="Description" fullWidth multiline rows={3} value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            <Stack direction="row" spacing={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Severity</InputLabel>
                <Select label="Severity" value={form.severity}
                  onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}>
                  {SEVERITIES.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
                </Select>
              </FormControl>
              <FormControl fullWidth size="small">
                <InputLabel>Priority</InputLabel>
                <Select label="Priority" value={form.priority}
                  onChange={e => setForm(f => ({ ...f, priority: Number(e.target.value) }))}>
                  {PRIORITIES.map(p => <MenuItem key={p.value} value={p.value}>{p.label}</MenuItem>)}
                </Select>
              </FormControl>
            </Stack>
            <Stack direction="row" spacing={2}>
              <FormControl fullWidth size="small">
                <InputLabel>TLP</InputLabel>
                <Select label="TLP" value={form.tlp}
                  onChange={e => setForm(f => ({ ...f, tlp: e.target.value }))}>
                  {TLPS.map(t => <MenuItem key={t} value={t}>{t.toUpperCase()}</MenuItem>)}
                </Select>
              </FormControl>
              <FormControl fullWidth size="small">
                <InputLabel>PAP</InputLabel>
                <Select label="PAP" value={form.pap}
                  onChange={e => setForm(f => ({ ...f, pap: e.target.value }))}>
                  {TLPS.map(t => <MenuItem key={t} value={t}>{t.toUpperCase()}</MenuItem>)}
                </Select>
              </FormControl>
            </Stack>
            <TextField label="Assignee" fullWidth value={form.assignee}
              onChange={e => setForm(f => ({ ...f, assignee: e.target.value }))} />
            <TextField label="Tags (comma-separated)" fullWidth value={form.tags}
              onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate} disabled={!form.title.trim()}>Create</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
