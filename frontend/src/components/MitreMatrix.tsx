/**
 * MitreMatrix  Interactive MITRE ATT&CK technique heat map.
 * Aggregates detected techniques from triage, host profiles, and hypotheses.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Paper, CircularProgress, Alert, Chip, Tooltip,
  FormControl, InputLabel, Select, MenuItem, IconButton, Button, Dialog,
  DialogTitle, DialogContent, List, ListItem, ListItemText, Divider,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import DownloadIcon from '@mui/icons-material/Download';
import { useSnackbar } from 'notistack';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as ReTooltip, ResponsiveContainer, Cell } from 'recharts';
import { mitre, MitreCoverage, MitreTechnique, hunts, Hunt, stixExport } from '../api/client';

const TACTIC_COLORS: Record<string, string> = {
  'Reconnaissance': '#7c3aed',
  'Resource Development': '#6d28d9',
  'Initial Access': '#ef4444',
  'Execution': '#f97316',
  'Persistence': '#f59e0b',
  'Privilege Escalation': '#eab308',
  'Defense Evasion': '#84cc16',
  'Credential Access': '#22c55e',
  'Discovery': '#14b8a6',
  'Lateral Movement': '#06b6d4',
  'Collection': '#3b82f6',
  'Command and Control': '#6366f1',
  'Exfiltration': '#a855f7',
  'Impact': '#ec4899',
};

export default function MitreMatrix() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<MitreCoverage | null>(null);
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [selectedHunt, setSelectedHunt] = useState<string>('');
  const [detailTech, setDetailTech] = useState<MitreTechnique | null>(null);
  const [exporting, setExporting] = useState(false);

  const handleStixExport = async () => {
    if (!selectedHunt) { enqueueSnackbar('Select a hunt to export STIX bundle', { variant: 'info' }); return; }
    setExporting(true);
    try {
      await stixExport.download(selectedHunt);
      enqueueSnackbar('STIX bundle downloaded', { variant: 'success' });
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    } finally {
      setExporting(false);
    }
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [coverage, h] = await Promise.all([
        mitre.coverage(selectedHunt || undefined),
        huntList.length ? Promise.resolve({ hunts: huntList, total: huntList.length }) : hunts.list(0, 100),
      ]);
      setData(coverage);
      if (!huntList.length) setHuntList(h.hunts);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    } finally {
      setLoading(false);
    }
  }, [selectedHunt, huntList, enqueueSnackbar]);

  useEffect(() => { load(); }, [load]);

  const chartData = data ? Object.entries(data.tactic_coverage).map(([tactic, info]) => ({
    tactic: tactic.replace(/ /g, '\n'),
    fullTactic: tactic,
    count: info.count,
    color: TACTIC_COLORS[tactic] || '#64748b',
  })) : [];

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <Typography variant="h5">MITRE ATT&CK Coverage</Typography>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Filter by Hunt</InputLabel>
          <Select value={selectedHunt} onChange={e => setSelectedHunt(e.target.value)} label="Filter by Hunt">
            <MenuItem value="">All Hunts</MenuItem>
            {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
          </Select>
        </FormControl>
        <IconButton onClick={load} disabled={loading}><RefreshIcon /></IconButton>
        <Tooltip title="Export STIX 2.1 bundle for selected hunt"><span><Button size="small" variant="outlined" startIcon={exporting ? <CircularProgress size={16} /> : <DownloadIcon />} onClick={handleStixExport} disabled={!selectedHunt || exporting}>STIX Export</Button></span></Tooltip>
        {data && (
          <>
            <Chip label={`${data.technique_count} techniques`} color="primary" size="small" />
            <Chip label={`${data.detection_count} detections`} color="secondary" size="small" />
          </>
        )}
      </Box>

      {loading && <CircularProgress />}

      {!loading && data && data.technique_count === 0 && (
        <Alert severity="info" sx={{ mt: 2 }}>
          No MITRE techniques detected yet. Run triage, host profiling, or add hypotheses with technique IDs to populate this view.
        </Alert>
      )}

      {!loading && data && data.technique_count > 0 && (
        <>
          {/* Bar chart of technique counts per tactic */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom>Techniques by Tactic</Typography>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData} margin={{ bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="tactic" tick={{ fontSize: 10, fill: '#94a3b8' }} interval={0} angle={-35} textAnchor="end" />
                <YAxis tick={{ fill: '#94a3b8' }} />
                <ReTooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }} />
                <Bar dataKey="count" name="Techniques">
                  {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Paper>

          {/* Heat map grid */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>Technique Matrix</Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 1.5 }}>
              {data.tactics.map(tactic => {
                const info = data.tactic_coverage[tactic];
                const techs = info?.techniques || [];
                return (
                  <Paper key={tactic} sx={{ p: 1.5, bgcolor: techs.length ? 'rgba(96,165,250,0.08)' : 'transparent', border: '1px solid', borderColor: techs.length ? TACTIC_COLORS[tactic] || '#334155' : '#1e293b' }}>
                    <Typography variant="caption" sx={{ color: TACTIC_COLORS[tactic] || '#94a3b8', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.65rem' }}>
                      {tactic}
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                      {techs.map(tech => (
                        <Tooltip key={tech.id} title={`${tech.id}  ${tech.count} detection(s)`}>
                          <Chip
                            label={tech.id}
                            size="small"
                            onClick={() => setDetailTech(tech)}
                            sx={{
                              fontSize: '0.65rem', height: 22,
                              bgcolor: tech.count >= 3 ? 'error.dark' : tech.count >= 2 ? 'warning.dark' : 'primary.dark',
                              cursor: 'pointer', '&:hover': { opacity: 0.8 },
                            }}
                          />
                        </Tooltip>
                      ))}
                      {!techs.length && <Typography variant="caption" color="text.secondary"></Typography>}
                    </Box>
                  </Paper>
                );
              })}
            </Box>
          </Paper>
        </>
      )}

      {/* Detail dialog */}
      <Dialog open={!!detailTech} onClose={() => setDetailTech(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{detailTech?.id}  {detailTech?.tactic}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" gutterBottom>Detected {detailTech?.count} time(s) from:</Typography>
          <List dense>
            {detailTech?.sources.map((s, i) => (
              <React.Fragment key={i}>
                <ListItem>
                  <ListItemText
                    primary={s.type === 'triage' ? `Triage (risk: ${s.risk_score})` : s.type === 'host_profile' ? `Host Profile: ${s.hostname}` : `Hypothesis: ${s.title}`}
                    secondary={`Source: ${s.type}`}
                  />
                </ListItem>
                {i < (detailTech?.sources.length || 0) - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        </DialogContent>
      </Dialog>
    </Box>
  );
}


