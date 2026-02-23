/**
 * TimelineView - Forensic event timeline with zoomable chart.
 * Plots dataset rows on a time axis, color-coded by artifact type and risk.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Paper, CircularProgress, Alert, Chip,
  FormControl, InputLabel, Select, MenuItem, IconButton,
  Table, TableHead, TableRow, TableCell, TableBody, TableContainer,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useSnackbar } from 'notistack';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as ReTooltip,
  ResponsiveContainer,
} from 'recharts';
import { timeline, TimelineData, TimelineEvent, hunts, Hunt } from '../api/client';

const ARTIFACT_COLORS: Record<string, string> = {
  'Windows.System.Pslist': '#60a5fa',
  'Windows.Network.Netstat': '#f472b6',
  'Windows.System.Services': '#34d399',
  'Windows.Forensics.Prefetch': '#fbbf24',
  'Windows.EventLogs.EvtxHunter': '#a78bfa',
  'Windows.Sys.Autoruns': '#f87171',
  'Unknown': '#64748b',
};

function getColor(artifact: string): string {
  return ARTIFACT_COLORS[artifact] || ARTIFACT_COLORS['Unknown'];
}

function bucketEvents(events: TimelineEvent[], buckets = 50): { time: string; count: number; artifacts: Record<string, number> }[] {
  if (!events.length) return [];
  const sorted = [...events].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  const start = new Date(sorted[0].timestamp).getTime();
  const end = new Date(sorted[sorted.length - 1].timestamp).getTime();
  const span = Math.max(end - start, 1);
  const bucketSize = span / buckets;
  const result: { time: string; count: number; artifacts: Record<string, number> }[] = [];
  for (let i = 0; i < buckets; i++) {
    const bStart = start + i * bucketSize;
    const bEnd = bStart + bucketSize;
    const inBucket = sorted.filter(e => {
      const t = new Date(e.timestamp).getTime();
      return t >= bStart && t < bEnd;
    });
    const artifacts: Record<string, number> = {};
    inBucket.forEach(e => { artifacts[e.artifact_type] = (artifacts[e.artifact_type] || 0) + 1; });
    result.push({
      time: new Date(bStart).toISOString().slice(0, 16).replace('T', ' '),
      count: inBucket.length,
      artifacts,
    });
  }
  return result;
}

export default function TimelineView() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<TimelineData | null>(null);
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [selectedHunt, setSelectedHunt] = useState<string>('');
  const [filterArtifact, setFilterArtifact] = useState<string>('');

  const load = useCallback(async () => {
    if (!selectedHunt) return;
    setLoading(true);
    try {
      const d = await timeline.getHuntTimeline(selectedHunt);
      setData(d);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    } finally {
      setLoading(false);
    }
  }, [selectedHunt, enqueueSnackbar]);

  useEffect(() => {
    hunts.list(0, 100).then(r => setHuntList(r.hunts)).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  const filteredEvents = data?.events.filter(e => !filterArtifact || e.artifact_type === filterArtifact) || [];
  const buckets = bucketEvents(filteredEvents);
  const artifactTypes = [...new Set(data?.events.map(e => e.artifact_type) || [])];

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Typography variant="h5">Forensic Timeline</Typography>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Hunt</InputLabel>
          <Select value={selectedHunt} onChange={e => setSelectedHunt(e.target.value)} label="Hunt">
            <MenuItem value="">Select a hunt...</MenuItem>
            {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Artifact Type</InputLabel>
          <Select value={filterArtifact} onChange={e => setFilterArtifact(e.target.value)} label="Artifact Type">
            <MenuItem value="">All Types</MenuItem>
            {artifactTypes.map(a => <MenuItem key={a} value={a}>{a}</MenuItem>)}
          </Select>
        </FormControl>
        <IconButton onClick={load} disabled={loading || !selectedHunt}><RefreshIcon /></IconButton>
        {data && <Chip label={`${filteredEvents.length} events`} color="primary" size="small" />}
      </Box>

      {!selectedHunt && (
        <Alert severity="info">Select a hunt to view its forensic timeline.</Alert>
      )}

      {loading && <CircularProgress />}

      {!loading && data && filteredEvents.length === 0 && (
        <Alert severity="warning">No timestamped events found in this hunt's datasets.</Alert>
      )}

      {!loading && data && filteredEvents.length > 0 && (
        <>
          {/* Activity histogram */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom>Activity Over Time</Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap' }}>
              {artifactTypes.map(a => (
                <Chip key={a} label={a} size="small" sx={{ bgcolor: getColor(a), color: '#fff', fontSize: '0.7rem' }}
                  onClick={() => setFilterArtifact(filterArtifact === a ? '' : a)} variant={filterArtifact === a ? 'filled' : 'outlined'} />
              ))}
            </Box>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={buckets}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#94a3b8' }} interval={Math.floor(buckets.length / 8)} angle={-30} textAnchor="end" />
                <YAxis tick={{ fill: '#94a3b8' }} />
                <ReTooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', fontSize: 12 }} />
                <Bar dataKey="count" name="Events" fill="#60a5fa" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>

          {/* Event table */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>Events ({filteredEvents.length})</Typography>
            <TableContainer sx={{ maxHeight: 400 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Time</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Hostname</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Artifact</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Process</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Summary</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredEvents.slice(0, 500).map((e, i) => (
                    <TableRow key={i} hover>
                      <TableCell sx={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>{e.timestamp.replace('T', ' ').slice(0, 19)}</TableCell>
                      <TableCell sx={{ fontSize: '0.75rem' }}>{e.hostname || ''}</TableCell>
                      <TableCell>
                        <Chip label={e.artifact_type} size="small" sx={{ bgcolor: getColor(e.artifact_type), color: '#fff', fontSize: '0.65rem', height: 20 }} />
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.75rem' }}>{e.process || ''}</TableCell>
                      <TableCell sx={{ fontSize: '0.75rem', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.summary || ''}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </>
      )}
    </Box>
  );
}
