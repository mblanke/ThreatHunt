/**
 * Dashboard — overview cards with hunt stats, node health, recent activity.
 */

import React, { useEffect, useState } from 'react';
import {
  Box, Grid, Paper, Typography, Chip, CircularProgress,
  Stack, Alert,
} from '@mui/material';
import StorageIcon from '@mui/icons-material/Storage';
import SearchIcon from '@mui/icons-material/Search';
import SecurityIcon from '@mui/icons-material/Security';
import ScienceIcon from '@mui/icons-material/Science';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import { hunts, datasets, hypotheses, agent, misc, type Hunt, type DatasetSummary, type HealthInfo } from '../api/client';

function StatCard({ title, value, icon, color }: { title: string; value: string | number; icon: React.ReactNode; color: string }) {
  return (
    <Paper sx={{ p: 2.5 }}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Box sx={{ color, fontSize: 40, display: 'flex' }}>{icon}</Box>
        <Box>
          <Typography variant="h4">{value}</Typography>
          <Typography variant="body2" color="text.secondary">{title}</Typography>
        </Box>
      </Stack>
    </Paper>
  );
}

function NodeStatus({ label, available }: { label: string; available: boolean }) {
  return (
    <Stack direction="row" alignItems="center" spacing={1}>
      {available
        ? <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
        : <ErrorIcon sx={{ color: 'error.main', fontSize: 20 }} />
      }
      <Typography variant="body2">{label}</Typography>
      <Chip label={available ? 'Online' : 'Offline'} size="small"
        color={available ? 'success' : 'error'} variant="outlined" />
    </Stack>
  );
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [huntList, setHunts] = useState<Hunt[]>([]);
  const [datasetList, setDatasets] = useState<DatasetSummary[]>([]);
  const [hypoCount, setHypoCount] = useState(0);
  const [apiInfo, setApiInfo] = useState<{ name: string; version: string; status: string } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
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
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <Box sx={{ p: 4 }}><CircularProgress /></Box>;
  if (error) return <Alert severity="error">{error}</Alert>;

  const activeHunts = huntList.filter(h => h.status === 'active').length;
  const totalRows = datasetList.reduce((s, d) => s + d.row_count, 0);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Dashboard</Typography>

      {/* Stat cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Active Hunts" value={activeHunts} icon={<SearchIcon fontSize="inherit" />} color="#60a5fa" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Datasets" value={datasetList.length} icon={<StorageIcon fontSize="inherit" />} color="#f472b6" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Total Rows" value={totalRows.toLocaleString()} icon={<SecurityIcon fontSize="inherit" />} color="#10b981" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Hypotheses" value={hypoCount} icon={<ScienceIcon fontSize="inherit" />} color="#f59e0b" />
        </Grid>
      </Grid>

      {/* Node health + API info */}
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h6" gutterBottom>LLM Cluster Health</Typography>
            <Stack spacing={1.5}>
              <NodeStatus label="Wile (100.110.190.12)" available={health?.nodes?.wile?.available ?? false} />
              <NodeStatus label="Roadrunner (100.110.190.11)" available={health?.nodes?.roadrunner?.available ?? false} />
              <NodeStatus label="SANS RAG (Open WebUI)" available={health?.rag?.available ?? false} />
            </Stack>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h6" gutterBottom>API Status</Typography>
            <Stack spacing={1}>
              <Typography variant="body2" color="text.secondary">
                {apiInfo ? `${apiInfo.name} — ${apiInfo.version}` : 'Unreachable'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Status: {apiInfo?.status ?? 'unknown'}
              </Typography>
            </Stack>
          </Paper>
        </Grid>
      </Grid>

      {/* Recent hunts */}
      {huntList.length > 0 && (
        <Paper sx={{ p: 2.5, mt: 2 }}>
          <Typography variant="h6" gutterBottom>Recent Hunts</Typography>
          <Stack spacing={1}>
            {huntList.slice(0, 5).map(h => (
              <Stack key={h.id} direction="row" alignItems="center" spacing={1}>
                <Chip label={h.status} size="small"
                  color={h.status === 'active' ? 'success' : h.status === 'closed' ? 'default' : 'warning'}
                  variant="outlined" />
                <Typography variant="body2" sx={{ fontWeight: 600 }}>{h.name}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {h.dataset_count} datasets · {h.hypothesis_count} hypotheses
                </Typography>
              </Stack>
            ))}
          </Stack>
        </Paper>
      )}
    </Box>
  );
}
