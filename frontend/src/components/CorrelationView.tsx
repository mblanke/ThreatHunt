/**
 * CorrelationView - cross-hunt correlation analysis with recharts visualizations.
 * IOC overlap bar chart, technique overlap heat chips, time/host overlap display.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Stack, Chip, Button, CircularProgress,
  Alert, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField, Grid, Divider,
} from '@mui/material';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import SearchIcon from '@mui/icons-material/Search';
import { useSnackbar } from 'notistack';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as ReTooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts';
import { correlation, hunts, type Hunt, type CorrelationResult } from '../api/client';

const PIE_COLORS = ['#60a5fa', '#f472b6', '#34d399', '#fbbf24', '#a78bfa', '#f87171', '#38bdf8', '#fb923c'];

export default function CorrelationView() {
  const { enqueueSnackbar } = useSnackbar();
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [result, setResult] = useState<CorrelationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [iocSearch, setIocSearch] = useState('');
  const [iocHits, setIocHits] = useState<any[] | null>(null);

  useEffect(() => {
    hunts.list(0, 100).then(r => setHuntList(r.hunts)).catch(() => {});
  }, []);

  const toggleHunt = (id: string) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
    );
  };

  const runAnalysis = useCallback(async () => {
    setLoading(true);
    try {
      const r = selectedIds.length >= 2
        ? await correlation.analyze(selectedIds)
        : await correlation.all();
      setResult(r);
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
    setLoading(false);
  }, [selectedIds, enqueueSnackbar]);

  const searchIoc = useCallback(async () => {
    if (!iocSearch.trim()) return;
    try {
      const r = await correlation.ioc(iocSearch.trim());
      setIocHits(r.occurrences);
      if (r.occurrences.length === 0) enqueueSnackbar('No occurrences found', { variant: 'info' });
    } catch (e: any) { enqueueSnackbar(e.message, { variant: 'error' }); }
  }, [iocSearch, enqueueSnackbar]);

  // Build chart data from results
  const iocChartData = (result?.ioc_overlaps || []).slice(0, 20).map((o: any) => ({
    name: String(o.ioc_value).length > 20 ? String(o.ioc_value).slice(0, 20) + '...' : o.ioc_value,
    hunts: (o.hunt_ids || []).length,
    type: o.ioc_type || 'unknown',
  }));

  const techniqueChartData = (result?.technique_overlaps || []).map((t: any) => ({
    name: t.technique || t.mitre_technique || 'unknown',
    value: (t.hunt_ids || []).length || 1,
  }));

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Cross-Hunt Correlation</Typography>

      {/* Hunt selector */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>Select hunts to correlate (min 2, or leave empty for all):</Typography>
        <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mb: 1.5 }}>
          {huntList.map(h => (
            <Chip
              key={h.id} label={h.name} size="small"
              color={selectedIds.includes(h.id) ? 'primary' : 'default'}
              onClick={() => toggleHunt(h.id)}
              variant={selectedIds.includes(h.id) ? 'filled' : 'outlined'}
              sx={{ mb: 0.5 }}
            />
          ))}
        </Stack>
        <Button
          variant="contained" startIcon={loading ? <CircularProgress size={16} /> : <CompareArrowsIcon />}
          onClick={runAnalysis} disabled={loading}
        >
          {selectedIds.length >= 2 ? `Correlate ${selectedIds.length} Hunts` : 'Correlate All'}
        </Button>
      </Paper>

      {/* IOC Search */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>Search IOC across all hunts:</Typography>
        <Stack direction="row" spacing={1}>
          <TextField size="small" fullWidth placeholder="e.g. 192.168.1.100" value={iocSearch}
            onChange={e => setIocSearch(e.target.value)} onKeyDown={e => e.key === 'Enter' && searchIoc()} />
          <Button variant="outlined" startIcon={<SearchIcon />} onClick={searchIoc}>Search</Button>
        </Stack>
        {iocHits && iocHits.length > 0 && (
          <Box sx={{ mt: 1.5 }}>
            <Typography variant="body2" fontWeight={600}>Found in {iocHits.length} location(s):</Typography>
            {iocHits.map((hit: any, i: number) => (
              <Chip key={i} label={`${hit.hunt_name || hit.hunt_id} / ${hit.dataset_name || hit.dataset_id}`}
                size="small" sx={{ mr: 0.5, mt: 0.5 }} />
            ))}
          </Box>
        )}
      </Paper>

      {/* Results with charts */}
      {result && (
        <Box>
          <Alert severity="info" sx={{ mb: 2 }}>
            {result.summary}  {result.total_correlations} correlation(s) across {result.hunt_ids.length} hunts
          </Alert>

          {/* Symmetrical 2-column: IOC chart | Technique chart */}
          <Grid container spacing={2} sx={{ mb: 2 }} columns={12}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2, height: '100%' }}>
                <Typography variant="h6" gutterBottom>IOC Overlaps ({result.ioc_overlaps.length})</Typography>
                <Divider sx={{ mb: 1 }} />
                {iocChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={iocChartData} layout="vertical" margin={{ left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                      <YAxis dataKey="name" type="category" tick={{ fill: '#94a3b8', fontSize: 10 }} width={120} />
                      <ReTooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', fontSize: 12 }} />
                      <Bar dataKey="hunts" name="Shared Hunts" fill="#60a5fa" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <Typography variant="body2" color="text.secondary">No IOC overlaps found.</Typography>
                )}
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2, height: '100%' }}>
                <Typography variant="h6" gutterBottom>Technique Overlaps ({result.technique_overlaps.length})</Typography>
                <Divider sx={{ mb: 1 }} />
                {techniqueChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie data={techniqueChartData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                        outerRadius={80} label={({ name }) => name}>
                        {techniqueChartData.map((_: any, i: number) => (
                          <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <ReTooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', fontSize: 12 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <Typography variant="body2" color="text.secondary">No technique overlaps found.</Typography>
                )}
              </Paper>
            </Grid>
          </Grid>

          {/* IOC detail table */}
          {result.ioc_overlaps.length > 0 && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" gutterBottom>IOC Detail</Typography>
              <TableContainer sx={{ maxHeight: 300 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>IOC</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Shared Hunts</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {result.ioc_overlaps.map((o: any, i: number) => (
                      <TableRow key={i} hover>
                        <TableCell><Typography variant="body2" fontFamily="monospace">{o.ioc_value}</Typography></TableCell>
                        <TableCell><Chip label={o.ioc_type || 'unknown'} size="small" /></TableCell>
                        <TableCell>
                          {(o.hunt_ids || []).map((hid: string, j: number) => (
                            <Chip key={j} label={huntList.find(h => h.id === hid)?.name || hid.slice(0, 8)}
                              size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                          ))}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          )}

          {/* Symmetrical 2-column: Time overlaps | Host overlaps */}
          <Grid container spacing={2} columns={12}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2, height: '100%' }}>
                <Typography variant="h6" gutterBottom>Time Overlaps ({result.time_overlaps.length})</Typography>
                <Divider sx={{ mb: 1 }} />
                {result.time_overlaps.length > 0 ? (
                  <Stack spacing={1}>
                    {result.time_overlaps.map((t: any, i: number) => (
                      <Stack key={i} direction="row" alignItems="center" spacing={1}>
                        <Chip label={t.hunt_a || 'Hunt A'} size="small" color="primary" variant="outlined" />
                        <Typography variant="body2"></Typography>
                        <Chip label={t.hunt_b || 'Hunt B'} size="small" color="secondary" variant="outlined" />
                        <Typography variant="caption" color="text.secondary">
                          {t.overlap_start}  {t.overlap_end}
                        </Typography>
                      </Stack>
                    ))}
                  </Stack>
                ) : (
                  <Typography variant="body2" color="text.secondary">No time overlaps found.</Typography>
                )}
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2, height: '100%' }}>
                <Typography variant="h6" gutterBottom>Host Overlaps ({result.host_overlaps.length})</Typography>
                <Divider sx={{ mb: 1 }} />
                {result.host_overlaps.length > 0 ? (
                  <Stack direction="row" spacing={0.5} flexWrap="wrap">
                    {result.host_overlaps.map((h: any, i: number) => (
                      <Chip key={i} label={typeof h === 'string' ? h : h.hostname || JSON.stringify(h)}
                        size="small" variant="outlined" sx={{ mb: 0.5 }} />
                    ))}
                  </Stack>
                ) : (
                  <Typography variant="body2" color="text.secondary">No host overlaps found.</Typography>
                )}
              </Paper>
            </Grid>
          </Grid>
        </Box>
      )}
    </Box>
  );
}
