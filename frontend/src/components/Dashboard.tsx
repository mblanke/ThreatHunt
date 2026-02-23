/**
 * Dashboard - overview cards with hunt stats, cluster health, recent activity.
 * Symmetrical 4-column grid layout, empty-state onboarding, auto-refresh.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Grid, Paper, Typography, Chip, CircularProgress,
  Stack, Alert, Button, Divider,
} from '@mui/material';
import StorageIcon from '@mui/icons-material/Storage';
import SearchIcon from '@mui/icons-material/Search';
import SecurityIcon from '@mui/icons-material/Security';
import ScienceIcon from '@mui/icons-material/Science';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useNavigate } from 'react-router-dom';
import { hunts, datasets, hypotheses, agent, misc, type Hunt, type DatasetSummary, type HealthInfo } from '../api/client';

const REFRESH_INTERVAL = 30_000; // 30s auto-refresh

/*  Stat Card  */

function StatCard({ title, value, icon, color }: {
  title: string; value: string | number; icon: React.ReactNode; color: string;
}) {
  return (
    <Paper sx={{ p: 2.5, height: '100%', display: 'flex', alignItems: 'center' }}>
      <Stack direction="row" alignItems="center" spacing={2} sx={{ width: '100%' }}>
        <Box sx={{ color, fontSize: 40, display: 'flex', flexShrink: 0 }}>{icon}</Box>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h4" noWrap>{value}</Typography>
          <Typography variant="body2" color="text.secondary" noWrap>{title}</Typography>
        </Box>
      </Stack>
    </Paper>
  );
}

/*  Node Status  */

function NodeStatus({ label, available }: { label: string; available: boolean }) {
  return (
    <Stack direction="row" alignItems="center" spacing={1}>
      {available
        ? <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
        : <ErrorIcon sx={{ color: 'error.main', fontSize: 20 }} />}
      <Typography variant="body2" sx={{ flex: 1 }}>{label}</Typography>
      <Chip label={available ? 'Online' : 'Offline'} size="small"
        color={available ? 'success' : 'error'} variant="outlined" />
    </Stack>
  );
}

/*  Empty State  */

function EmptyOnboarding() {
  const navigate = useNavigate();
  return (
    <Paper sx={{ p: 4, textAlign: 'center', gridColumn: '1 / -1' }}>
      <RocketLaunchIcon sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
      <Typography variant="h5" gutterBottom>Welcome to ThreatHunt</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3, maxWidth: 480, mx: 'auto' }}>
        Get started by creating a hunt, uploading CSV artifacts, and letting the AI assist your investigation.
      </Typography>
      <Stack direction="row" spacing={2} justifyContent="center">
        <Button variant="contained" startIcon={<SearchIcon />} onClick={() => navigate('/hunts')}>
          Create a Hunt
        </Button>
        <Button variant="outlined" startIcon={<UploadFileIcon />} onClick={() => navigate('/upload')}>
          Upload Data
        </Button>
      </Stack>
    </Paper>
  );
}

/*  Main Dashboard  */

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [huntList, setHunts] = useState<Hunt[]>([]);
  const [datasetList, setDatasets] = useState<DatasetSummary[]>([]);
  const [hypoCount, setHypoCount] = useState(0);
  const [apiInfo, setApiInfo] = useState<{ name?: string; version?: string; status?: string; service?: string } | null>(null);
  const [error, setError] = useState('');
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const refresh = useCallback(async () => {
    try {
      const [h, ht, ds, hy, info] = await Promise.all([
        agent.health().catch(() => null),
        hunts.list(0, 100).catch(() => ({ hunts: [], total: 0 })),
        datasets.list(0, 100).catch(() => ({ datasets: [], total: 0 })),
        hypotheses.list({ limit: 1 }).catch(() => ({ hypotheses: [], total: 0 })),
        misc.root().catch(() => null),
      ]);
      setHealth(h);
      setHunts(ht.hunts);
      setDatasets(ds.datasets);
      setHypoCount(hy.total);
      setApiInfo(info);
      setLastRefresh(new Date());
      setError('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => { refresh(); }, [refresh]);

  // Auto-refresh
  useEffect(() => {
    const timer = setInterval(refresh, REFRESH_INTERVAL);
    return () => clearInterval(timer);
  }, [refresh]);

  if (loading) return <Box sx={{ p: 4 }}><CircularProgress /></Box>;
  if (error) return <Alert severity="error">{error}</Alert>;

  const activeHunts = huntList.filter(h => h.status === 'active').length;
  const totalRows = datasetList.reduce((s, d) => s + d.row_count, 0);
  const isEmpty = huntList.length === 0 && datasetList.length === 0;

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h5">Dashboard</Typography>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="caption" color="text.secondary">
            Updated {lastRefresh.toLocaleTimeString()}
          </Typography>
          <Button size="small" startIcon={<RefreshIcon />} onClick={refresh}>Refresh</Button>
        </Stack>
      </Stack>

      {/* Stat cards - symmetrical 4-column */}
      <Grid container spacing={2} sx={{ mb: 3 }} columns={12}>
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <StatCard title="Active Hunts" value={activeHunts} icon={<SearchIcon fontSize="inherit" />} color="#60a5fa" />
        </Grid>
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <StatCard title="Datasets" value={datasetList.length} icon={<StorageIcon fontSize="inherit" />} color="#f472b6" />
        </Grid>
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <StatCard title="Total Rows" value={totalRows.toLocaleString()} icon={<SecurityIcon fontSize="inherit" />} color="#10b981" />
        </Grid>
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <StatCard title="Hypotheses" value={hypoCount} icon={<ScienceIcon fontSize="inherit" />} color="#f59e0b" />
        </Grid>
      </Grid>

      {/* Empty state or content */}
      {isEmpty ? (
        <EmptyOnboarding />
      ) : (
        <>
          {/* Symmetrical 2-column: Cluster Health | API Status */}
          <Grid container spacing={2} sx={{ mb: 3 }} columns={12}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2.5, height: '100%' }}>
                <Typography variant="h6" gutterBottom>LLM Cluster Health</Typography>
                <Divider sx={{ mb: 1.5 }} />
                <Stack spacing={1.5}>
                  <NodeStatus label="Wile (Heavy Models)" available={health?.nodes?.wile?.available ?? false} />
                  <NodeStatus label="Roadrunner (Fast Models)" available={health?.nodes?.roadrunner?.available ?? false} />
                  <NodeStatus label="SANS RAG (Open WebUI)" available={health?.rag?.available ?? false} />
                </Stack>
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2.5, height: '100%' }}>
                <Typography variant="h6" gutterBottom>API Status</Typography>
                <Divider sx={{ mb: 1.5 }} />
                <Stack spacing={1}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2" color="text.secondary">Service</Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {apiInfo?.service || apiInfo?.name || 'ThreatHunt API'}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2" color="text.secondary">Version</Typography>
                    <Chip label={apiInfo?.version || 'unknown'} size="small" variant="outlined" />
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2" color="text.secondary">Status</Typography>
                    <Chip label={apiInfo?.status || 'unknown'} size="small"
                      color={apiInfo?.status === 'running' ? 'success' : 'warning'} variant="outlined" />
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2" color="text.secondary">Hunts</Typography>
                    <Typography variant="body2">{huntList.length} total ({activeHunts} active)</Typography>
                  </Stack>
                </Stack>
              </Paper>
            </Grid>
          </Grid>

          {/* Symmetrical 2-column: Recent Hunts | Recent Datasets */}
          <Grid container spacing={2} columns={12}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2.5, height: '100%' }}>
                <Typography variant="h6" gutterBottom>Recent Hunts</Typography>
                <Divider sx={{ mb: 1.5 }} />
                {huntList.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">No hunts yet.</Typography>
                ) : (
                  <Stack spacing={1}>
                    {huntList.slice(0, 5).map(h => (
                      <Stack key={h.id} direction="row" alignItems="center" spacing={1}>
                        <Chip label={h.status} size="small"
                          color={h.status === 'active' ? 'success' : h.status === 'closed' ? 'default' : 'warning'}
                          variant="outlined" sx={{ minWidth: 64, justifyContent: 'center' }} />
                        <Typography variant="body2" sx={{ fontWeight: 600, flex: 1, minWidth: 0 }} noWrap>{h.name}</Typography>
                        <Typography variant="caption" color="text.secondary" noWrap>
                          {h.dataset_count}ds  {h.hypothesis_count}hyp
                        </Typography>
                      </Stack>
                    ))}
                  </Stack>
                )}
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2.5, height: '100%' }}>
                <Typography variant="h6" gutterBottom>Recent Datasets</Typography>
                <Divider sx={{ mb: 1.5 }} />
                {datasetList.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">No datasets yet.</Typography>
                ) : (
                  <Stack spacing={1}>
                    {datasetList.slice(0, 5).map(d => (
                      <Stack key={d.id} direction="row" alignItems="center" spacing={1}>
                        <Chip label={d.source_tool || 'CSV'} size="small" variant="outlined"
                          sx={{ minWidth: 64, justifyContent: 'center' }} />
                        <Typography variant="body2" sx={{ fontWeight: 600, flex: 1, minWidth: 0 }} noWrap>{d.name}</Typography>
                        <Typography variant="caption" color="text.secondary" noWrap>
                          {d.row_count.toLocaleString()} rows
                        </Typography>
                      </Stack>
                    ))}
                  </Stack>
                )}
              </Paper>
            </Grid>
          </Grid>
        </>
      )}
    </Box>
  );
}
