/**
 * Dashboard — CrowdScore-style triage overview with risk scoring,
 * severity breakdown, top riskiest hosts, node health, and recent hunts.
 */

import React, { useEffect, useState } from 'react';
import {
  Box, Grid, Paper, Typography, Chip, CircularProgress,
  Stack, Alert, LinearProgress, Divider,
} from '@mui/material';
import StorageIcon from '@mui/icons-material/Storage';
import SearchIcon from '@mui/icons-material/Search';
import SecurityIcon from '@mui/icons-material/Security';
import ScienceIcon from '@mui/icons-material/Science';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ShieldIcon from '@mui/icons-material/Shield';
import {
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip as RechartsTooltip, Legend,
} from 'recharts';
import {
  hunts, datasets, hypotheses, agent, misc, analysis,
  type Hunt, type DatasetSummary, type HealthInfo, type RiskSummaryResponse,
} from '../api/client';

/* ── Severity palette ─────────────────────────────────────────────── */
const SEV_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#3b82f6',
  info: '#6b7280',
};

/* ── CrowdScore gauge component ───────────────────────────────────── */
function CrowdScore({ score }: { score: number }) {
  const color = score >= 75 ? '#ef4444' : score >= 50 ? '#f97316' : score >= 25 ? '#eab308' : '#10b981';
  const label = score >= 75 ? 'CRITICAL' : score >= 50 ? 'HIGH' : score >= 25 ? 'MODERATE' : 'LOW';

  return (
    <Box sx={{ textAlign: 'center', py: 2 }}>
      <Box sx={{ position: 'relative', display: 'inline-flex' }}>
        <CircularProgress
          variant="determinate" value={score} size={140}
          thickness={6} sx={{ color, '& .MuiCircularProgress-circle': { strokeLinecap: 'round' } }}
        />
        <Box sx={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        }}>
          <Typography variant="h3" sx={{ fontWeight: 700, color, lineHeight: 1 }}>
            {score}
          </Typography>
          <Typography variant="caption" sx={{ color, fontWeight: 600, mt: 0.5 }}>
            {label}
          </Typography>
        </Box>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        Overall Threat Score
      </Typography>
    </Box>
  );
}

/* ── Stat card ────────────────────────────────────────────────────── */
function StatCard({ title, value, icon, color }: { title: string; value: string | number; icon: React.ReactNode; color: string }) {
  return (
    <Paper sx={{ p: 2 }}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Box sx={{ color, fontSize: 36, display: 'flex' }}>{icon}</Box>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 600 }}>{value}</Typography>
          <Typography variant="body2" color="text.secondary">{title}</Typography>
        </Box>
      </Stack>
    </Paper>
  );
}

/* ── Node status chip ─────────────────────────────────────────────── */
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
  const [apiInfo, setApiInfo] = useState<{ name?: string; version?: string; status?: string } | null>(null);
  const [risk, setRisk] = useState<RiskSummaryResponse | null>(null);
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

        // Fetch risk for the first active hunt
        const activeHunt = ht.hunts.find((h: Hunt) => h.status === 'active');
        if (activeHunt) {
          const riskData = await analysis.riskSummary(activeHunt.id).catch(() => null);
          setRisk(riskData);
        }
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

  /* severity pie data */
  const sevData = risk?.severity_breakdown
    ? Object.entries(risk.severity_breakdown)
        .filter(([_, v]) => v > 0)
        .map(([name, value]) => ({ name, value }))
    : [];

  /* top 10 riskiest hosts */
  const topHosts = risk?.hosts?.slice(0, 10) || [];

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Dashboard</Typography>

      {/* Row 1: CrowdScore + stats */}
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper sx={{ height: '100%' }}>
            <CrowdScore score={risk?.overall_score || 0} />
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 9 }}>
          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 3 }}>
              <StatCard title="Active Hunts" value={activeHunts} icon={<SearchIcon fontSize="inherit" />} color="#60a5fa" />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <StatCard title="Datasets" value={datasetList.length} icon={<StorageIcon fontSize="inherit" />} color="#f472b6" />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <StatCard title="Total Rows" value={totalRows.toLocaleString()} icon={<SecurityIcon fontSize="inherit" />} color="#10b981" />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <StatCard title="Hypotheses" value={hypoCount} icon={<ScienceIcon fontSize="inherit" />} color="#f59e0b" />
            </Grid>
          </Grid>

          {/* Alert signal summary */}
          {risk && risk.hosts.length > 0 && (
            <Paper sx={{ p: 2, mt: 2 }}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                <WarningAmberIcon sx={{ color: '#f97316' }} />
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {risk.hosts.filter(h => h.score >= 50).length} high-risk hosts
                </Typography>
                <Divider orientation="vertical" flexItem />
                <Typography variant="body2" color="text.secondary">
                  {risk.total_events.toLocaleString()} events analyzed
                </Typography>
                {risk.hosts.slice(0, 3).flatMap(h => h.signals.slice(0, 2)).filter((v, i, a) => a.indexOf(v) === i).map(s => (
                  <Chip key={s} label={s} size="small" color="warning" variant="outlined" />
                ))}
              </Stack>
            </Paper>
          )}
        </Grid>
      </Grid>

      {/* Row 2: Severity pie + Top riskiest hosts */}
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ p: 2, height: 320 }}>
            <Typography variant="h6" gutterBottom>Severity Breakdown</Typography>
            {sevData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={sevData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                    outerRadius={90} innerRadius={45} paddingAngle={2} label={({ name, value }) => `${name}: ${value}`}>
                    {sevData.map((entry) => (
                      <Cell key={entry.name} fill={SEV_COLORS[entry.name] || '#6b7280'} />
                    ))}
                  </Pie>
                  <RechartsTooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 250 }}>
                <Typography color="text.secondary">No data</Typography>
              </Box>
            )}
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 8 }}>
          <Paper sx={{ p: 2, height: 320 }}>
            <Typography variant="h6" gutterBottom>Top 10 Riskiest Hosts</Typography>
            {topHosts.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={topHosts} layout="vertical" margin={{ left: 80 }}>
                  <XAxis type="number" domain={[0, 100]} />
                  <YAxis type="category" dataKey="hostname" width={70} tick={{ fontSize: 11 }} />
                  <RechartsTooltip
                    formatter={(value: any, name: any) => [`${value}/100`, 'Risk Score']}
                    labelFormatter={(label: any) => `Host: ${label}`}
                  />
                  <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                    {topHosts.map((entry, idx) => (
                      <Cell key={idx}
                        fill={entry.score >= 75 ? '#ef4444' : entry.score >= 50 ? '#f97316'
                              : entry.score >= 25 ? '#eab308' : '#10b981'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 250 }}>
                <Typography color="text.secondary">No risk data — select a hunt with datasets</Typography>
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Row 3: Node health + Recent hunts */}
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h6" gutterBottom>LLM Cluster Health</Typography>
            <Stack spacing={1.5}>
              <NodeStatus label="Wile (100.110.190.12)" available={health?.nodes?.wile?.available ?? false} />
              <NodeStatus label="Roadrunner (100.110.190.11)" available={health?.nodes?.roadrunner?.available ?? false} />
              <NodeStatus label="SANS RAG (Open WebUI)" available={health?.rag?.available ?? false} />
            </Stack>
            <Divider sx={{ my: 2 }} />
            <Typography variant="body2" color="text.secondary">
              {apiInfo ? `${apiInfo.name || 'ThreatHunt'} v${apiInfo.version || '?'}` : 'API unreachable'} — {apiInfo?.status ?? 'unknown'}
            </Typography>
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h6" gutterBottom>Recent Hunts</Typography>
            {huntList.length > 0 ? (
              <Stack spacing={1}>
                {huntList.slice(0, 6).map(h => (
                  <Stack key={h.id} direction="row" alignItems="center" spacing={1}>
                    <Chip label={h.status} size="small"
                      color={h.status === 'active' ? 'success' : h.status === 'closed' ? 'default' : 'warning'}
                      variant="outlined" />
                    <Typography variant="body2" sx={{ fontWeight: 600, flex: 1 }}>{h.name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {h.dataset_count}ds · {h.hypothesis_count}hyp
                    </Typography>
                  </Stack>
                ))}
              </Stack>
            ) : (
              <Typography color="text.secondary">No hunts yet</Typography>
            )}
          </Paper>
        </Grid>

        {/* Risk signal details for top hosts */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ p: 2.5 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
              <ShieldIcon sx={{ color: '#60a5fa' }} />
              <Typography variant="h6">Risk Signals</Typography>
            </Stack>
            {topHosts.filter(h => h.signals.length > 0).slice(0, 5).map(h => (
              <Box key={h.hostname} sx={{ mb: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" sx={{ fontWeight: 600, minWidth: 100 }}>
                    {h.hostname}
                  </Typography>
                  <LinearProgress
                    variant="determinate" value={h.score}
                    sx={{ flex: 1, height: 6, borderRadius: 3,
                      '& .MuiLinearProgress-bar': {
                        bgcolor: h.score >= 75 ? '#ef4444' : h.score >= 50 ? '#f97316'
                                : h.score >= 25 ? '#eab308' : '#10b981' } }}
                  />
                  <Typography variant="caption" sx={{ fontWeight: 600, minWidth: 30 }}>
                    {h.score}
                  </Typography>
                </Stack>
                <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }} flexWrap="wrap">
                  {h.signals.map(s => (
                    <Chip key={s} label={s} size="small" variant="outlined"
                      sx={{ fontSize: 10, height: 20 }} />
                  ))}
                </Stack>
              </Box>
            ))}
            {topHosts.filter(h => h.signals.length > 0).length === 0 && (
              <Typography color="text.secondary" variant="body2">No risk signals detected</Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
