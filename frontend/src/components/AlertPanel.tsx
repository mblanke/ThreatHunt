/**
 * AlertPanel — Security alert management with analyzer controls.
 *
 * Features:
 * - Alert list with severity/status filtering and sorting
 * - Run analyzers on demand against datasets/hunts
 * - Alert detail drill-down with evidence viewer
 * - Bulk acknowledge/resolve/false-positive actions
 * - Alert rules management (auto-trigger analyzers)
 * - Stats dashboard (severity/status/analyzer breakdowns)
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Button, Chip, IconButton, Tooltip,
  Select, MenuItem, FormControl, InputLabel, Stack, Divider,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  LinearProgress, Alert as MuiAlert, Card, CardContent, Tabs, Tab,
  Checkbox, FormControlLabel, Switch, Badge,
} from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ReportProblemIcon from '@mui/icons-material/ReportProblem';
import DeleteIcon from '@mui/icons-material/Delete';
import RuleIcon from '@mui/icons-material/Rule';
import BarChartIcon from '@mui/icons-material/BarChart';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useSnackbar } from 'notistack';
import {
  alerts, hunts, datasets,
  AlertData, AlertStats, AlertRuleData, AnalyzerInfo,
  Hunt, DatasetSummary,
} from '../api/client';

const SEV_COLORS: Record<string, 'error' | 'warning' | 'info' | 'success' | 'default'> = {
  critical: 'error', high: 'warning', medium: 'info', low: 'success', info: 'default',
};
const STATUS_COLORS: Record<string, 'error' | 'warning' | 'info' | 'success' | 'default'> = {
  new: 'error', acknowledged: 'warning', 'in-progress': 'info',
  resolved: 'success', 'false-positive': 'default',
};

export default function AlertPanel() {
  const { enqueueSnackbar } = useSnackbar();

  // Tab state
  const [tab, setTab] = useState(0);

  // Alerts list
  const [alertList, setAlertList] = useState<AlertData[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [sevFilter, setSevFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [selected, setSelected] = useState<string[]>([]);

  // Stats
  const [stats, setStats] = useState<AlertStats | null>(null);

  // Hunt/dataset selectors
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [dsList, setDsList] = useState<DatasetSummary[]>([]);
  const [huntId, setHuntId] = useState('');
  const [datasetId, setDatasetId] = useState('');

  // Analyzers
  const [analyzerList, setAnalyzerList] = useState<AnalyzerInfo[]>([]);
  const [analyzing, setAnalyzing] = useState(false);

  // Rules
  const [rules, setRules] = useState<AlertRuleData[]>([]);
  const [ruleDialog, setRuleDialog] = useState(false);
  const [ruleForm, setRuleForm] = useState({ name: '', description: '', analyzer: '', enabled: true });

  // Detail dialog
  const [detailAlert, setDetailAlert] = useState<AlertData | null>(null);

  // ── Load data ──────────────────────────────────────────────────────

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const opts: any = { limit: 200 };
      if (sevFilter) opts.severity = sevFilter;
      if (statusFilter) opts.status = statusFilter;
      if (huntId) opts.hunt_id = huntId;
      if (datasetId) opts.dataset_id = datasetId;
      const res = await alerts.list(opts);
      setAlertList(res.alerts);
      setTotal(res.total);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    } finally {
      setLoading(false);
    }
  }, [sevFilter, statusFilter, huntId, datasetId, enqueueSnackbar]);

  const loadStats = useCallback(async () => {
    try {
      const s = await alerts.stats(huntId || undefined);
      setStats(s);
    } catch {}
  }, [huntId]);

  const loadRules = useCallback(async () => {
    try {
      const res = await alerts.listRules();
      setRules(res.rules);
    } catch {}
  }, []);

  useEffect(() => {
    hunts.list().then(r => setHuntList(r.hunts)).catch(() => {});
    datasets.list(0, 500).then(r => setDsList(r.datasets)).catch(() => {});
    alerts.analyzers().then(r => setAnalyzerList(r.analyzers)).catch(() => {});
  }, []);

  useEffect(() => { loadAlerts(); loadStats(); }, [loadAlerts, loadStats]);
  useEffect(() => { loadRules(); }, [loadRules]);

  // ── Analyze ────────────────────────────────────────────────────────

  const runAnalysis = async () => {
    if (!datasetId && !huntId) {
      enqueueSnackbar('Select a hunt or dataset first', { variant: 'warning' });
      return;
    }
    setAnalyzing(true);
    try {
      const res = await alerts.analyze({
        dataset_id: datasetId || undefined,
        hunt_id: huntId || undefined,
        auto_create: true,
      });
      enqueueSnackbar(
        `Analysis complete: ${res.candidates_found} findings, ${res.alerts_created} alerts created`,
        { variant: 'success' },
      );
      loadAlerts();
      loadStats();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    } finally {
      setAnalyzing(false);
    }
  };

  // ── Bulk actions ───────────────────────────────────────────────────

  const bulkAction = async (status: string) => {
    if (!selected.length) return;
    try {
      await alerts.bulkUpdate(selected, status);
      enqueueSnackbar(`${selected.length} alerts → ${status}`, { variant: 'success' });
      setSelected([]);
      loadAlerts();
      loadStats();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  // ── Single alert actions ───────────────────────────────────────────

  const updateStatus = async (id: string, status: string) => {
    try {
      await alerts.update(id, { status });
      loadAlerts();
      loadStats();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const deleteAlert = async (id: string) => {
    try {
      await alerts.delete(id);
      loadAlerts();
      loadStats();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  // ── Rules ──────────────────────────────────────────────────────────

  const createRule = async () => {
    if (!ruleForm.name || !ruleForm.analyzer) return;
    try {
      await alerts.createRule({
        name: ruleForm.name,
        description: ruleForm.description,
        analyzer: ruleForm.analyzer,
        enabled: ruleForm.enabled,
      });
      enqueueSnackbar('Rule created', { variant: 'success' });
      setRuleDialog(false);
      setRuleForm({ name: '', description: '', analyzer: '', enabled: true });
      loadRules();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const toggleRule = async (rule: AlertRuleData) => {
    try {
      await alerts.updateRule(rule.id, { enabled: !rule.enabled } as any);
      loadRules();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const deleteRule = async (id: string) => {
    try {
      await alerts.deleteRule(id);
      loadRules();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  // ── DataGrid columns ──────────────────────────────────────────────

  const columns: GridColDef[] = [
    {
      field: 'severity', headerName: 'Sev', width: 90,
      renderCell: (p) => <Chip label={p.value} size="small" color={SEV_COLORS[p.value] || 'default'} />,
    },
    {
      field: 'status', headerName: 'Status', width: 110,
      renderCell: (p) => <Chip label={p.value} size="small" color={STATUS_COLORS[p.value] || 'default'} variant="outlined" />,
    },
    { field: 'title', headerName: 'Title', flex: 1, minWidth: 250 },
    { field: 'analyzer', headerName: 'Analyzer', width: 140 },
    {
      field: 'score', headerName: 'Score', width: 80, type: 'number',
      renderCell: (p) => <Typography variant="body2" fontWeight="bold">{Math.round(p.value)}</Typography>,
    },
    { field: 'mitre_technique', headerName: 'MITRE', width: 90 },
    {
      field: 'created_at', headerName: 'Created', width: 150,
      valueFormatter: (value: string) => value ? new Date(value).toLocaleString() : '',
    },
    {
      field: 'actions', headerName: '', width: 160, sortable: false,
      renderCell: (p) => (
        <Stack direction="row" spacing={0.5}>
          <Tooltip title="View"><IconButton size="small" onClick={() => setDetailAlert(p.row)}><VisibilityIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="Acknowledge"><IconButton size="small" color="warning" onClick={() => updateStatus(p.row.id, 'acknowledged')}><CheckCircleIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="Resolve"><IconButton size="small" color="success" onClick={() => updateStatus(p.row.id, 'resolved')}><CheckCircleIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="Delete"><IconButton size="small" color="error" onClick={() => deleteAlert(p.row.id)}><DeleteIcon fontSize="small" /></IconButton></Tooltip>
        </Stack>
      ),
    },
  ];

  // ── Stats cards ────────────────────────────────────────────────────

  const StatsView = () => {
    if (!stats) return <Typography color="text.secondary">No stats available</Typography>;
    return (
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 2 }}>
        <Card><CardContent>
          <Typography variant="subtitle2" color="text.secondary">Total Alerts</Typography>
          <Typography variant="h3">{stats.total}</Typography>
        </CardContent></Card>

        {['critical', 'high', 'medium', 'low', 'info'].map(sev => (
          <Card key={sev}><CardContent>
            <Typography variant="subtitle2" color="text.secondary">{sev.toUpperCase()}</Typography>
            <Typography variant="h4" color={SEV_COLORS[sev] === 'error' ? 'error' : SEV_COLORS[sev] === 'warning' ? 'warning.main' : 'text.primary'}>
              {stats.severity_counts[sev] || 0}
            </Typography>
          </CardContent></Card>
        ))}

        <Card sx={{ gridColumn: 'span 2' }}><CardContent>
          <Typography variant="subtitle2" gutterBottom>By Status</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            {Object.entries(stats.status_counts).map(([s, c]) => (
              <Chip key={s} label={`${s}: ${c}`} color={STATUS_COLORS[s] || 'default'} size="small" />
            ))}
          </Stack>
        </CardContent></Card>

        <Card sx={{ gridColumn: 'span 2' }}><CardContent>
          <Typography variant="subtitle2" gutterBottom>By Analyzer</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            {Object.entries(stats.analyzer_counts).map(([a, c]) => (
              <Chip key={a} label={`${a}: ${c}`} size="small" variant="outlined" />
            ))}
          </Stack>
        </CardContent></Card>

        {stats.top_mitre.length > 0 && (
          <Card sx={{ gridColumn: 'span 2' }}><CardContent>
            <Typography variant="subtitle2" gutterBottom>Top MITRE Techniques</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {stats.top_mitre.map(m => (
                <Chip key={m.technique} label={`${m.technique} (${m.count})`} size="small" color="error" variant="outlined" />
              ))}
            </Stack>
          </CardContent></Card>
        )}
      </Box>
    );
  };

  // ── Rules view ─────────────────────────────────────────────────────

  const RulesView = () => (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">Alert Rules ({rules.length})</Typography>
        <Button variant="contained" startIcon={<RuleIcon />} onClick={() => setRuleDialog(true)}>
          New Rule
        </Button>
      </Stack>

      {rules.map(rule => (
        <Paper key={rule.id} sx={{ p: 2, mb: 1 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Box>
              <Typography variant="subtitle1" fontWeight="bold">
                {rule.name}
                <Chip label={rule.analyzer} size="small" sx={{ ml: 1 }} />
                {rule.severity_override && <Chip label={rule.severity_override} size="small" color={SEV_COLORS[rule.severity_override] || 'default'} sx={{ ml: 0.5 }} />}
              </Typography>
              {rule.description && <Typography variant="body2" color="text.secondary">{rule.description}</Typography>}
            </Box>
            <Stack direction="row" spacing={1} alignItems="center">
              <Switch checked={rule.enabled} onChange={() => toggleRule(rule)} size="small" />
              <IconButton size="small" color="error" onClick={() => deleteRule(rule.id)}><DeleteIcon fontSize="small" /></IconButton>
            </Stack>
          </Stack>
        </Paper>
      ))}

      {rules.length === 0 && (
        <Typography color="text.secondary" textAlign="center" py={4}>
          No alert rules configured. Create a rule to auto-trigger analyzers.
        </Typography>
      )}
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Header */}
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h5">
          <Badge badgeContent={stats?.severity_counts?.critical || 0} color="error" sx={{ mr: 2 }}>
            <ReportProblemIcon />
          </Badge>
          Alerts & Analyzers
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => { loadAlerts(); loadStats(); }}>
            Refresh
          </Button>
        </Stack>
      </Stack>

      {/* Selector bar */}
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Hunt</InputLabel>
            <Select value={huntId} label="Hunt" onChange={e => { setHuntId(e.target.value); setDatasetId(''); }}>
              <MenuItem value="">All hunts</MenuItem>
              {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Dataset</InputLabel>
            <Select value={datasetId} label="Dataset" onChange={e => setDatasetId(e.target.value)}>
              <MenuItem value="">All datasets</MenuItem>
              {dsList.map(d => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
            </Select>
          </FormControl>

          <Button
            variant="contained"
            color="warning"
            startIcon={<PlayArrowIcon />}
            onClick={runAnalysis}
            disabled={analyzing || (!huntId && !datasetId)}
          >
            {analyzing ? 'Analyzing…' : 'Run Analyzers'}
          </Button>

          <Divider orientation="vertical" flexItem />

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Severity</InputLabel>
            <Select value={sevFilter} label="Severity" onChange={e => setSevFilter(e.target.value)}>
              <MenuItem value="">All</MenuItem>
              {['critical', 'high', 'medium', 'low', 'info'].map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Status</InputLabel>
            <Select value={statusFilter} label="Status" onChange={e => setStatusFilter(e.target.value)}>
              <MenuItem value="">All</MenuItem>
              {['new', 'acknowledged', 'in-progress', 'resolved', 'false-positive'].map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
            </Select>
          </FormControl>
        </Stack>
        {analyzing && <LinearProgress sx={{ mt: 1 }} />}
      </Paper>

      {/* Tabs */}
      <Tabs value={tab} onChange={(_, v) => setTab(v)}>
        <Tab label={`Alerts (${total})`} />
        <Tab icon={<BarChartIcon />} label="Stats" />
        <Tab icon={<RuleIcon />} label={`Rules (${rules.length})`} />
      </Tabs>

      {/* Tab panels */}
      {tab === 0 && (
        <Box>
          {/* Bulk actions */}
          {selected.length > 0 && (
            <Paper sx={{ p: 1, mb: 1, bgcolor: 'action.hover' }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="body2">{selected.length} selected</Typography>
                <Button size="small" onClick={() => bulkAction('acknowledged')}>Acknowledge</Button>
                <Button size="small" onClick={() => bulkAction('resolved')}>Resolve</Button>
                <Button size="small" color="error" onClick={() => bulkAction('false-positive')}>False Positive</Button>
              </Stack>
            </Paper>
          )}

          <Paper sx={{ height: 600 }}>
            {loading && <LinearProgress />}
            <DataGrid
              rows={alertList}
              columns={columns}
              density="compact"
              checkboxSelection
              onRowSelectionModelChange={(model) => setSelected(Array.from(model.ids) as string[])}
              pageSizeOptions={[25, 50, 100]}
              initialState={{ pagination: { paginationModel: { pageSize: 50 } } }}
              sx={{ border: 'none' }}
            />
          </Paper>
        </Box>
      )}

      {tab === 1 && <StatsView />}
      {tab === 2 && <RulesView />}

      {/* Detail dialog */}
      <Dialog open={!!detailAlert} onClose={() => setDetailAlert(null)} maxWidth="md" fullWidth>
        {detailAlert && (
          <>
            <DialogTitle>
              <Chip label={detailAlert.severity} color={SEV_COLORS[detailAlert.severity] || 'default'} size="small" sx={{ mr: 1 }} />
              {detailAlert.title}
            </DialogTitle>
            <DialogContent dividers>
              <Typography variant="body1" gutterBottom>{detailAlert.description}</Typography>
              <Divider sx={{ my: 2 }} />

              <Stack direction="row" spacing={2} mb={2}>
                <Chip label={`Analyzer: ${detailAlert.analyzer}`} variant="outlined" />
                <Chip label={`Score: ${Math.round(detailAlert.score)}`} variant="outlined" />
                {detailAlert.mitre_technique && <Chip label={detailAlert.mitre_technique} color="error" variant="outlined" />}
                <Chip label={detailAlert.status} color={STATUS_COLORS[detailAlert.status] || 'default'} />
              </Stack>

              {detailAlert.tags?.length > 0 && (
                <Stack direction="row" spacing={0.5} mb={2}>
                  {detailAlert.tags.map((t, i) => <Chip key={i} label={t} size="small" />)}
                </Stack>
              )}

              <Typography variant="subtitle2" gutterBottom>Evidence</Typography>
              <Paper variant="outlined" sx={{ p: 2, maxHeight: 300, overflow: 'auto' }}>
                <pre style={{ margin: 0, fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(detailAlert.evidence, null, 2)}
                </pre>
              </Paper>

              <Stack direction="row" spacing={2} mt={2}>
                <Typography variant="caption" color="text.secondary">
                  Created: {new Date(detailAlert.created_at).toLocaleString()}
                </Typography>
                {detailAlert.acknowledged_at && (
                  <Typography variant="caption" color="text.secondary">
                    Acknowledged: {new Date(detailAlert.acknowledged_at).toLocaleString()}
                  </Typography>
                )}
                {detailAlert.resolved_at && (
                  <Typography variant="caption" color="text.secondary">
                    Resolved: {new Date(detailAlert.resolved_at).toLocaleString()}
                  </Typography>
                )}
              </Stack>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => { updateStatus(detailAlert.id, 'acknowledged'); setDetailAlert(null); }}>
                Acknowledge
              </Button>
              <Button onClick={() => { updateStatus(detailAlert.id, 'resolved'); setDetailAlert(null); }} color="success">
                Resolve
              </Button>
              <Button onClick={() => { updateStatus(detailAlert.id, 'false-positive'); setDetailAlert(null); }}>
                False Positive
              </Button>
              <Button onClick={() => setDetailAlert(null)}>Close</Button>
            </DialogActions>
          </>
        )}
      </Dialog>

      {/* Create rule dialog */}
      <Dialog open={ruleDialog} onClose={() => setRuleDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create Alert Rule</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField
              label="Rule Name" fullWidth required
              value={ruleForm.name} onChange={e => setRuleForm(f => ({ ...f, name: e.target.value }))}
            />
            <TextField
              label="Description" fullWidth multiline rows={2}
              value={ruleForm.description} onChange={e => setRuleForm(f => ({ ...f, description: e.target.value }))}
            />
            <FormControl fullWidth required>
              <InputLabel>Analyzer</InputLabel>
              <Select value={ruleForm.analyzer} label="Analyzer" onChange={e => setRuleForm(f => ({ ...f, analyzer: e.target.value }))}>
                {analyzerList.map(a => <MenuItem key={a.name} value={a.name}>{a.name} — {a.description}</MenuItem>)}
              </Select>
            </FormControl>
            <FormControlLabel
              control={<Switch checked={ruleForm.enabled} onChange={e => setRuleForm(f => ({ ...f, enabled: e.target.checked }))} />}
              label="Enabled"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRuleDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={createRule} disabled={!ruleForm.name || !ruleForm.analyzer}>
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
