/**
 * PlaybookManager — Pre-defined investigation playbooks.
 *
 * Features:
 * - Browse built-in playbook templates
 * - Start a playbook run linked to a hunt/case
 * - Step-by-step execution with notes and status tracking
 * - View past runs and their results
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Button, Chip, Stack, Divider,
  Card, CardContent, CardActions, Stepper, Step, StepLabel, StepContent,
  TextField, Dialog, DialogTitle, DialogContent, DialogActions,
  FormControl, InputLabel, Select, MenuItem, Tabs, Tab,
  LinearProgress, IconButton, Tooltip,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import HistoryIcon from '@mui/icons-material/History';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useSnackbar } from 'notistack';
import {
  playbooks, hunts,
  PlaybookTemplate, PlaybookTemplateDetail, PlaybookRunData, Hunt,
} from '../api/client';

const CATEGORY_COLORS: Record<string, 'error' | 'primary' | 'secondary' | 'warning' | 'info' | 'success'> = {
  incident_response: 'error',
  threat_hunting: 'primary',
  compliance: 'info',
};

const STATUS_COLORS: Record<string, 'warning' | 'success' | 'error' | 'default'> = {
  'in-progress': 'warning',
  completed: 'success',
  aborted: 'error',
};

export default function PlaybookManager() {
  const { enqueueSnackbar } = useSnackbar();
  const [tab, setTab] = useState(0);

  // Templates
  const [templates, setTemplates] = useState<PlaybookTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<PlaybookTemplateDetail | null>(null);

  // Runs
  const [runs, setRuns] = useState<PlaybookRunData[]>([]);
  const [activeRun, setActiveRun] = useState<PlaybookRunData | null>(null);

  // Start dialog
  const [startDialog, setStartDialog] = useState(false);
  const [startTemplate, setStartTemplate] = useState('');
  const [startHunt, setStartHunt] = useState('');
  const [huntList, setHuntList] = useState<Hunt[]>([]);

  // Step notes
  const [stepNotes, setStepNotes] = useState('');

  // ── Load ───────────────────────────────────────────────────────────

  const loadTemplates = useCallback(async () => {
    try {
      const res = await playbooks.templates();
      setTemplates(res.templates);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  }, [enqueueSnackbar]);

  const loadRuns = useCallback(async () => {
    try {
      const res = await playbooks.listRuns();
      setRuns(res.runs);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  }, [enqueueSnackbar]);

  useEffect(() => {
    loadTemplates();
    loadRuns();
    hunts.list().then(r => setHuntList(r.hunts)).catch(() => {});
  }, [loadTemplates, loadRuns]);

  // ── Template detail ────────────────────────────────────────────────

  const viewTemplate = async (name: string) => {
    try {
      const detail = await playbooks.templateDetail(name);
      setSelectedTemplate(detail);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  // ── Start run ──────────────────────────────────────────────────────

  const startRun = async () => {
    if (!startTemplate) return;
    try {
      const run = await playbooks.start({
        playbook_name: startTemplate,
        hunt_id: startHunt || undefined,
      });
      enqueueSnackbar('Playbook started!', { variant: 'success' });
      setStartDialog(false);
      setStartTemplate(''); setStartHunt('');
      setActiveRun(run);
      setTab(1);
      loadRuns();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  // ── Open run detail ────────────────────────────────────────────────

  const openRun = async (runId: string) => {
    try {
      const run = await playbooks.getRun(runId);
      setActiveRun(run);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  // ── Complete step ──────────────────────────────────────────────────

  const completeStep = async (status: string = 'completed') => {
    if (!activeRun) return;
    try {
      const run = await playbooks.completeStep(activeRun.id, {
        notes: stepNotes || undefined,
        status,
      });
      setActiveRun(run);
      setStepNotes('');
      loadRuns();
      if (run.status === 'completed') {
        enqueueSnackbar('Playbook completed!', { variant: 'success' });
      }
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const abortRun = async () => {
    if (!activeRun) return;
    try {
      const run = await playbooks.abortRun(activeRun.id);
      setActiveRun(run);
      loadRuns();
      enqueueSnackbar('Playbook aborted', { variant: 'warning' });
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  // ── Active run view ────────────────────────────────────────────────

  if (activeRun) {
    const steps = activeRun.steps || [];
    const currentIdx = activeRun.current_step - 1;
    const isActive = activeRun.status === 'in-progress';

    return (
      <Box>
        <Stack direction="row" alignItems="center" spacing={2} mb={2}>
          <Button onClick={() => setActiveRun(null)}>Back</Button>
          <Typography variant="h5" sx={{ flexGrow: 1 }}>{activeRun.playbook_name}</Typography>
          <Chip label={activeRun.status} color={STATUS_COLORS[activeRun.status] || 'default'} />
          <Typography variant="body2" color="text.secondary">
            Step {activeRun.current_step} / {activeRun.total_steps}
          </Typography>
        </Stack>

        <LinearProgress
          variant="determinate"
          value={(activeRun.step_results.length / activeRun.total_steps) * 100}
          sx={{ mb: 3, height: 8, borderRadius: 4 }}
        />

        <Stepper activeStep={currentIdx} orientation="vertical">
          {steps.map((step, i) => {
            const result = activeRun.step_results.find(r => r.step === step.order);
            const isCurrent = i === currentIdx && isActive;

            return (
              <Step key={step.order} completed={!!result}>
                <StepLabel
                  optional={
                    result ? (
                      <Chip
                        label={result.status}
                        size="small"
                        color={result.status === 'completed' ? 'success' : 'default'}
                      />
                    ) : undefined
                  }
                >
                  <Typography variant="subtitle1" fontWeight={isCurrent ? 'bold' : 'normal'}>
                    {step.title}
                  </Typography>
                </StepLabel>
                <StepContent>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    {step.description}
                  </Typography>

                  <Box sx={{ mt: 1, mb: 1 }}>
                    <Chip label={`Action: ${step.action}`} size="small" variant="outlined" sx={{ mr: 1 }} />
                    <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
                      Expected: {step.expected_outcome}
                    </Typography>
                  </Box>

                  {result?.notes && (
                    <Paper variant="outlined" sx={{ p: 1, mt: 1, bgcolor: 'action.hover' }}>
                      <Typography variant="caption" color="text.secondary">Notes:</Typography>
                      <Typography variant="body2">{result.notes}</Typography>
                    </Paper>
                  )}

                  {isCurrent && (
                    <Box sx={{ mt: 2 }}>
                      <TextField
                        label="Step notes (optional)"
                        multiline rows={2} fullWidth size="small"
                        value={stepNotes}
                        onChange={e => setStepNotes(e.target.value)}
                        sx={{ mb: 1 }}
                      />
                      <Stack direction="row" spacing={1}>
                        <Button
                          variant="contained" size="small"
                          startIcon={<CheckCircleIcon />}
                          onClick={() => completeStep('completed')}
                        >
                          Complete Step
                        </Button>
                        <Button
                          variant="outlined" size="small"
                          startIcon={<SkipNextIcon />}
                          onClick={() => completeStep('skipped')}
                        >
                          Skip
                        </Button>
                        <Button
                          variant="outlined" color="error" size="small"
                          startIcon={<StopIcon />}
                          onClick={abortRun}
                        >
                          Abort
                        </Button>
                      </Stack>
                    </Box>
                  )}
                </StepContent>
              </Step>
            );
          })}
        </Stepper>

        {activeRun.status === 'completed' && (
          <Paper sx={{ p: 2, mt: 2, bgcolor: 'success.dark', color: 'white' }}>
            <Typography variant="h6">Playbook Completed</Typography>
            <Typography variant="body2">
              All {activeRun.total_steps} steps finished at {activeRun.completed_at ? new Date(activeRun.completed_at).toLocaleString() : 'N/A'}
            </Typography>
          </Paper>
        )}
      </Box>
    );
  }

  // ── Main view ──────────────────────────────────────────────────────

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Playbooks</Typography>
        <Button
          variant="contained"
          startIcon={<PlayArrowIcon />}
          onClick={() => setStartDialog(true)}
        >
          Start Playbook
        </Button>
      </Stack>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label={`Templates (${templates.length})`} />
        <Tab label={`Runs (${runs.length})`} icon={<HistoryIcon />} iconPosition="start" />
      </Tabs>

      {/* Templates tab */}
      {tab === 0 && (
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: 2 }}>
          {templates.map(t => (
            <Card key={t.name} variant="outlined">
              <CardContent>
                <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                  <Typography variant="h6">{t.name}</Typography>
                  <Chip
                    label={t.category.replace('_', ' ')}
                    size="small"
                    color={CATEGORY_COLORS[t.category] || 'default'}
                  />
                </Stack>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t.description}
                </Typography>
                <Stack direction="row" spacing={0.5} flexWrap="wrap">
                  <Chip label={`${t.step_count} steps`} size="small" variant="outlined" />
                  {t.tags.map((tag, i) => <Chip key={i} label={tag} size="small" />)}
                </Stack>
              </CardContent>
              <CardActions>
                <Button size="small" onClick={() => viewTemplate(t.name)}>View Steps</Button>
                <Button
                  size="small" variant="contained"
                  startIcon={<PlayArrowIcon />}
                  onClick={() => { setStartTemplate(t.name); setStartDialog(true); }}
                >
                  Start
                </Button>
              </CardActions>
            </Card>
          ))}
        </Box>
      )}

      {/* Runs tab */}
      {tab === 1 && (
        <Box>
          {runs.map(run => (
            <Paper key={run.id} sx={{ p: 2, mb: 1 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography variant="subtitle1" fontWeight="bold">
                    {run.playbook_name}
                    <Chip label={run.status} size="small" color={STATUS_COLORS[run.status] || 'default'} sx={{ ml: 1 }} />
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Step {run.current_step}/{run.total_steps} • Started {new Date(run.created_at).toLocaleString()}
                    {run.started_by && ` by ${run.started_by}`}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1}>
                  <LinearProgress
                    variant="determinate"
                    value={(run.step_results.length / run.total_steps) * 100}
                    sx={{ width: 100, height: 8, borderRadius: 4, alignSelf: 'center' }}
                  />
                  <Tooltip title="Open">
                    <IconButton onClick={() => openRun(run.id)}>
                      <VisibilityIcon />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Stack>
            </Paper>
          ))}
          {runs.length === 0 && (
            <Typography color="text.secondary" textAlign="center" py={4}>
              No playbook runs yet. Start one from the Templates tab.
            </Typography>
          )}
        </Box>
      )}

      {/* Template detail dialog */}
      <Dialog open={!!selectedTemplate} onClose={() => setSelectedTemplate(null)} maxWidth="md" fullWidth>
        {selectedTemplate && (
          <>
            <DialogTitle>
              {selectedTemplate.name}
              <Chip label={selectedTemplate.category.replace('_', ' ')} size="small" color={CATEGORY_COLORS[selectedTemplate.category] || 'default'} sx={{ ml: 1 }} />
            </DialogTitle>
            <DialogContent dividers>
              <Typography variant="body1" gutterBottom>{selectedTemplate.description}</Typography>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" gutterBottom>Steps ({selectedTemplate.steps?.length || 0})</Typography>
              <Stepper orientation="vertical">
                {(selectedTemplate.steps || []).map((step, i) => (
                  <Step key={i} active>
                    <StepLabel>
                      <Typography variant="subtitle2">{step.title}</Typography>
                    </StepLabel>
                    <StepContent>
                      <Typography variant="body2" color="text.secondary">{step.description}</Typography>
                      <Chip label={`Action: ${step.action}`} size="small" variant="outlined" sx={{ mt: 0.5 }} />
                      <Typography variant="caption" display="block" mt={0.5}>
                        Expected: {step.expected_outcome}
                      </Typography>
                    </StepContent>
                  </Step>
                ))}
              </Stepper>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setSelectedTemplate(null)}>Close</Button>
              <Button
                variant="contained"
                startIcon={<PlayArrowIcon />}
                onClick={() => {
                  setStartTemplate(selectedTemplate.name);
                  setSelectedTemplate(null);
                  setStartDialog(true);
                }}
              >
                Start This Playbook
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>

      {/* Start run dialog */}
      <Dialog open={startDialog} onClose={() => setStartDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Start Playbook Run</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <FormControl fullWidth required>
              <InputLabel>Playbook</InputLabel>
              <Select value={startTemplate} label="Playbook" onChange={e => setStartTemplate(e.target.value)}>
                {templates.map(t => <MenuItem key={t.name} value={t.name}>{t.name} ({t.step_count} steps)</MenuItem>)}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Linked Hunt</InputLabel>
              <Select value={startHunt} label="Linked Hunt" onChange={e => setStartHunt(e.target.value)}>
                <MenuItem value="">None</MenuItem>
                {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setStartDialog(false)}>Cancel</Button>
          <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={startRun} disabled={!startTemplate}>
            Start
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
