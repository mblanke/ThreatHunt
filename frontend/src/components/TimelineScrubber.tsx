/**
 * TimelineScrubber — interactive temporal histogram with brush selection,
 * event-type stacking, and field-stats sidebar.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Box, Typography, Paper, Stack, FormControl, InputLabel, Select,
  MenuItem, CircularProgress, Alert, Chip, Tooltip, IconButton,
  ToggleButton, ToggleButtonGroup, Slider, List, ListItem,
  ListItemText, LinearProgress,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import BarChartIcon from '@mui/icons-material/BarChart';
import StackedBarChartIcon from '@mui/icons-material/StackedBarChart';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
  ResponsiveContainer, Brush, BarChart, Bar, Legend,
} from 'recharts';
import {
  hunts, datasets, analysis,
  type HuntOut, type DatasetSummary, type TimelineBin,
} from '../api/client';

const EVENT_COLORS: Record<string, string> = {
  process: '#3b82f6',
  network: '#8b5cf6',
  file: '#10b981',
  registry: '#f59e0b',
  authentication: '#ef4444',
  dns: '#06b6d4',
  other: '#6b7280',
};

function shortTime(iso: string) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 19);
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function TimelineScrubber() {
  const [huntList, setHuntList] = useState<HuntOut[]>([]);
  const [dsList, setDsList] = useState<DatasetSummary[]>([]);
  const [activeHunt, setActiveHunt] = useState<string>('');
  const [activeDs, setActiveDs] = useState<string>('');
  const [bins, setBins] = useState<TimelineBin[]>([]);
  const [fieldStats, setFieldStats] = useState<Record<string, { total: number; unique: number; top: { value: string; count: number; pct: number }[] }>>({});
  const [totalRows, setTotalRows] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [chartType, setChartType] = useState<'area' | 'bar'>('area');
  const [numBins, setNumBins] = useState(80);
  const [playing, setPlaying] = useState(false);
  const [playIdx, setPlayIdx] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load hunts and datasets
  useEffect(() => {
    hunts.list(0, 200).then(r => {
      setHuntList(r.hunts);
      if (r.hunts.length > 0) setActiveHunt(r.hunts[0].id);
    }).catch(() => {});
    datasets.list(0, 200).then(r => {
      setDsList(r.datasets);
    }).catch(() => {});
  }, []);

  // Fetch timeline bins
  const fetchData = useCallback(async () => {
    if (!activeDs && !activeHunt) return;
    setLoading(true);
    setError('');
    try {
      const [tl, fs] = await Promise.all([
        analysis.timeline({ dataset_id: activeDs || undefined, hunt_id: activeHunt || undefined, bins: numBins }),
        analysis.fieldStats({ dataset_id: activeDs || undefined, hunt_id: activeHunt || undefined }),
      ]);
      setBins(tl.bins);
      setTotalRows(tl.total);
      setFieldStats(fs.fields);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }, [activeDs, activeHunt, numBins]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Playback animation
  useEffect(() => {
    if (playing && bins.length > 0) {
      timerRef.current = setInterval(() => {
        setPlayIdx(prev => {
          if (prev >= bins.length - 1) {
            setPlaying(false);
            return 0;
          }
          return prev + 1;
        });
      }, 200);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [playing, bins.length]);

  // Collect all event types across bins
  const eventTypes = Array.from(new Set(bins.flatMap(b => Object.keys(b.types || {}))));

  // Transform bins for recharts
  const chartData = bins.map((b, i) => ({
    name: shortTime(b.start),
    total: b.count,
    ...b.types,
    _idx: i,
  }));

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Timeline Scrubber</Typography>

      {/* Selectors */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Hunt</InputLabel>
            <Select
              label="Hunt" value={activeHunt}
              onChange={e => { setActiveHunt(e.target.value); setActiveDs(''); }}
            >
              <MenuItem value="">— none —</MenuItem>
              {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel>Dataset</InputLabel>
            <Select
              label="Dataset" value={activeDs}
              onChange={e => setActiveDs(e.target.value)}
            >
              <MenuItem value="">— all datasets —</MenuItem>
              {dsList.map(d => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
            </Select>
          </FormControl>

          <Box sx={{ width: 140, px: 1 }}>
            <Typography variant="caption" color="text.secondary">Bins: {numBins}</Typography>
            <Slider size="small" min={20} max={200} step={10} value={numBins}
              onChange={(_, v) => setNumBins(v as number)} />
          </Box>

          <ToggleButtonGroup size="small" exclusive value={chartType}
            onChange={(_, v) => { if (v) setChartType(v); }}>
            <ToggleButton value="area"><BarChartIcon fontSize="small" /></ToggleButton>
            <ToggleButton value="bar"><StackedBarChartIcon fontSize="small" /></ToggleButton>
          </ToggleButtonGroup>

          <Chip label={`${totalRows.toLocaleString()} events`} size="small" color="primary" variant="outlined" />
        </Stack>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading && <CircularProgress sx={{ display: 'block', mx: 'auto', my: 4 }} />}

      {!loading && bins.length > 0 && (
        <Stack direction="row" spacing={2}>
          {/* Main chart */}
          <Paper sx={{ flex: 1, p: 2 }}>
            {/* Playback controls */}
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
              <Tooltip title={playing ? 'Pause' : 'Play animation'}>
                <IconButton size="small" onClick={() => setPlaying(p => !p)}>
                  {playing ? <PauseIcon /> : <PlayArrowIcon />}
                </IconButton>
              </Tooltip>
              <Tooltip title="Reset">
                <IconButton size="small" onClick={() => { setPlaying(false); setPlayIdx(0); }}>
                  <RestartAltIcon />
                </IconButton>
              </Tooltip>
              {playing && (
                <Typography variant="caption" color="text.secondary">
                  Bin {playIdx + 1} / {bins.length}
                </Typography>
              )}
            </Stack>

            <ResponsiveContainer width="100%" height={320}>
              {chartType === 'area' ? (
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10 }} />
                  <RTooltip
                    contentStyle={{ background: '#1e1e1e', border: '1px solid #444', fontSize: 12 }}
                    labelStyle={{ color: '#aaa' }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {eventTypes.map(t => (
                    <Area
                      key={t} type="monotone" dataKey={t} stackId="1"
                      fill={EVENT_COLORS[t] || EVENT_COLORS.other}
                      stroke={EVENT_COLORS[t] || EVENT_COLORS.other}
                      fillOpacity={0.6}
                    />
                  ))}
                  <Brush
                    dataKey="name" height={28} stroke="#666"
                    startIndex={0}
                    endIndex={playing ? Math.min(playIdx, bins.length - 1) : undefined}
                    fill="#1a1a1a"
                    travellerWidth={8}
                  />
                </AreaChart>
              ) : (
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10 }} />
                  <RTooltip
                    contentStyle={{ background: '#1e1e1e', border: '1px solid #444', fontSize: 12 }}
                    labelStyle={{ color: '#aaa' }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {eventTypes.map(t => (
                    <Bar
                      key={t} dataKey={t} stackId="1"
                      fill={EVENT_COLORS[t] || EVENT_COLORS.other}
                    />
                  ))}
                  <Brush dataKey="name" height={28} stroke="#666" fill="#1a1a1a" />
                </BarChart>
              )}
            </ResponsiveContainer>
          </Paper>

          {/* Field stats sidebar */}
          <Paper sx={{ width: 320, p: 2, maxHeight: 440, overflow: 'auto' }}>
            <Typography variant="subtitle2" gutterBottom>Field Statistics</Typography>
            {Object.entries(fieldStats).slice(0, 12).map(([field, stat]) => (
              <Box key={field} sx={{ mb: 1.5 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="caption" fontWeight={700}>{field}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {stat.unique} unique
                  </Typography>
                </Stack>
                <List dense disablePadding>
                  {stat.top.slice(0, 5).map(v => (
                    <ListItem key={v.value} disablePadding sx={{ py: 0 }}>
                      <ListItemText
                        primary={
                          <Stack direction="row" alignItems="center" spacing={1}>
                            <Typography variant="caption" noWrap sx={{ maxWidth: 140 }}>
                              {v.value || '(empty)'}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {v.count}
                            </Typography>
                          </Stack>
                        }
                        secondary={
                          <LinearProgress
                            variant="determinate" value={v.pct}
                            sx={{ height: 3, borderRadius: 1, mt: 0.3 }}
                          />
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              </Box>
            ))}
          </Paper>
        </Stack>
      )}

      {!loading && bins.length === 0 && !error && (
        <Alert severity="info">Select a hunt or dataset to view the timeline.</Alert>
      )}
    </Box>
  );
}
