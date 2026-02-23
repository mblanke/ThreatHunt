/**
 * PlaybookManager - Investigation playbook workflow wizard.
 * Create/load playbooks from templates, track step completion, navigate to target views.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Paper, CircularProgress, Alert, Button, Chip,
  List, ListItem, ListItemButton, ListItemIcon, ListItemText,
  Checkbox, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, LinearProgress, IconButton, Divider, Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useSnackbar } from 'notistack';
import {
  playbooks, PlaybookSummary, PlaybookDetail, PlaybookTemplate,
} from '../api/client';

export default function PlaybookManager() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(false);
  const [pbList, setPbList] = useState<PlaybookSummary[]>([]);
  const [active, setActive] = useState<PlaybookDetail | null>(null);
  const [templates, setTemplates] = useState<PlaybookTemplate[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await playbooks.list();
      setPbList(data.playbooks);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    } finally {
      setLoading(false);
    }
  }, [enqueueSnackbar]);

  const loadTemplates = useCallback(async () => {
    try {
      const data = await playbooks.templates();
      setTemplates(data.templates);
    } catch {}
  }, []);

  useEffect(() => { loadList(); loadTemplates(); }, [loadList, loadTemplates]);

  const selectPlaybook = async (id: string) => {
    try {
      const d = await playbooks.get(id);
      setActive(d);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const toggleStep = async (stepId: number, current: boolean) => {
    if (!active) return;
    try {
      await playbooks.updateStep(stepId, { is_completed: !current });
      const d = await playbooks.get(active.id);
      setActive(d);
      loadList();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const createFromTemplate = async (tpl: PlaybookTemplate) => {
    try {
      const pb = await playbooks.create({
        name: tpl.name,
        description: tpl.description,
        steps: tpl.steps.map((s, i) => ({
          title: s.title,
          description: s.description,
          step_type: 'task',
          target_route: s.target_route || undefined,
        })),
      });
      enqueueSnackbar('Playbook created from template', { variant: 'success' });
      loadList();
      setActive(pb);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const createCustom = async () => {
    if (!newName.trim()) return;
    try {
      const pb = await playbooks.create({
        name: newName,
        description: newDesc,
        steps: [{ title: 'First step', description: 'Describe what to do' }],
      });
      enqueueSnackbar('Playbook created', { variant: 'success' });
      setShowCreate(false);
      setNewName('');
      setNewDesc('');
      loadList();
      setActive(pb);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const deletePlaybook = async (id: string) => {
    try {
      await playbooks.delete(id);
      enqueueSnackbar('Playbook deleted', { variant: 'success' });
      if (active?.id === id) setActive(null);
      loadList();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const completedCount = active?.steps.filter(s => s.is_completed).length || 0;
  const totalSteps = active?.steps.length || 1;
  const progress = Math.round((completedCount / totalSteps) * 100);

  return (
    <Box sx={{ display: 'flex', gap: 3, minHeight: 500 }}>
      {/* Left sidebar - playbook list */}
      <Paper sx={{ width: 320, p: 2, flexShrink: 0 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Playbooks</Typography>
          <IconButton size="small" color="primary" onClick={() => setShowCreate(true)}><AddIcon /></IconButton>
        </Box>

        {/* Templates section */}
        <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>TEMPLATES</Typography>
        <List dense>
          {templates.map(t => (
            <ListItemButton key={t.name} onClick={() => createFromTemplate(t)} sx={{ borderRadius: 1, mb: 0.5 }}>
              <ListItemIcon sx={{ minWidth: 32 }}><PlaylistAddCheckIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t.name} secondary={`${t.steps.length} steps`} primaryTypographyProps={{ fontSize: '0.85rem' }} />
            </ListItemButton>
          ))}
        </List>

        <Divider sx={{ my: 1 }} />
        <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>MY PLAYBOOKS</Typography>
        {loading && <CircularProgress size={20} sx={{ display: 'block', mx: 'auto', my: 2 }} />}
        <List dense>
          {pbList.map(p => (
            <ListItemButton key={p.id} selected={active?.id === p.id} onClick={() => selectPlaybook(p.id)} sx={{ borderRadius: 1, mb: 0.5 }}>
              <ListItemText
                primary={p.name}
                secondary={`${p.completed_steps}/${p.total_steps} done`}
                primaryTypographyProps={{ fontSize: '0.85rem', fontWeight: active?.id === p.id ? 600 : 400 }}
              />
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Chip label={`${Math.round((p.completed_steps / Math.max(p.total_steps, 1)) * 100)}%`}
                  size="small" color={p.completed_steps === p.total_steps ? 'success' : 'default'}
                  sx={{ fontSize: '0.7rem', height: 20 }} />
                <IconButton size="small" onClick={e => { e.stopPropagation(); deletePlaybook(p.id); }}><DeleteIcon fontSize="small" /></IconButton>
              </Box>
            </ListItemButton>
          ))}
          {!loading && pbList.length === 0 && (
            <Alert severity="info" sx={{ mt: 1 }}>No playbooks yet. Start from a template or create one.</Alert>
          )}
        </List>
      </Paper>

      {/* Right panel - active playbook */}
      <Box sx={{ flex: 1 }}>
        {!active ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <PlaylistAddCheckIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h6" color="text.secondary">Select or create a playbook</Typography>
            <Typography variant="body2" color="text.secondary">
              Use templates for common investigation workflows, or build your own step-by-step checklist.
            </Typography>
          </Paper>
        ) : (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h5" gutterBottom>{active.name}</Typography>
            {active.description && <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{active.description}</Typography>}

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
              <LinearProgress variant="determinate" value={progress} sx={{ flex: 1, height: 8, borderRadius: 4 }} />
              <Typography variant="body2" fontWeight={600}>{progress}%</Typography>
              <Chip label={`${completedCount}/${totalSteps} steps`} size="small" color={progress === 100 ? 'success' : 'primary'} />
            </Box>

            <List>
              {active.steps
                .sort((a, b) => a.order_index - b.order_index)
                .map(step => (
                  <ListItem key={step.id} disablePadding sx={{ mb: 1 }}>
                    <ListItemButton onClick={() => toggleStep(step.id, step.is_completed)} sx={{ borderRadius: 1, border: '1px solid', borderColor: step.is_completed ? 'success.main' : 'divider', bgcolor: step.is_completed ? 'success.main' : 'transparent', opacity: step.is_completed ? 0.7 : 1 }}>
                      <ListItemIcon sx={{ minWidth: 40 }}>
                        <Checkbox edge="start" checked={step.is_completed} disableRipple />
                      </ListItemIcon>
                      <ListItemText
                        primary={step.title}
                        secondary={step.description}
                        slotProps={{ primary: { sx: { textDecoration: step.is_completed ? 'line-through' : 'none', fontWeight: 500 } } }}
                      />
                      {step.target_route && (
                        <Tooltip title={`Go to ${step.target_route}`}>
                          <IconButton size="small" onClick={e => { e.stopPropagation(); window.location.hash = step.target_route!; }}>
                            <OpenInNewIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </ListItemButton>
                  </ListItem>
                ))}
            </List>
          </Paper>
        )}
      </Box>

      {/* Create dialog */}
      <Dialog open={showCreate} onClose={() => setShowCreate(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create Custom Playbook</DialogTitle>
        <DialogContent>
          <TextField label="Name" fullWidth value={newName} onChange={e => setNewName(e.target.value)} sx={{ mt: 1, mb: 2 }} />
          <TextField label="Description" fullWidth multiline rows={2} value={newDesc} onChange={e => setNewDesc(e.target.value)} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCreate(false)}>Cancel</Button>
          <Button variant="contained" onClick={createCustom} disabled={!newName.trim()}>Create</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

