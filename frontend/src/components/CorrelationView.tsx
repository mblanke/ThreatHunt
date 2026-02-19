/**
 * CorrelationView — cross-hunt correlation analysis with IOC, time,
 * technique, and host overlap visualisation.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Stack, Chip, Button, CircularProgress,
  Alert, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField,
} from '@mui/material';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import SearchIcon from '@mui/icons-material/Search';
import { useSnackbar } from 'notistack';
import { correlation, hunts, type Hunt, type CorrelationResult } from '../api/client';

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

      {/* Results */}
      {result && (
        <Box>
          <Alert severity="info" sx={{ mb: 2 }}>
            {result.summary} — {result.total_correlations} total correlation(s) across {result.hunt_ids.length} hunts
          </Alert>

          {/* IOC overlaps */}
          {result.ioc_overlaps.length > 0 && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="h6" gutterBottom>IOC Overlaps ({result.ioc_overlaps.length})</Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>IOC</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Shared Hunts</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {result.ioc_overlaps.map((o: any, i: number) => (
                      <TableRow key={i}>
                        <TableCell><Typography variant="body2" fontFamily="monospace">{o.ioc_value}</Typography></TableCell>
                        <TableCell><Chip label={o.ioc_type || 'unknown'} size="small" /></TableCell>
                        <TableCell>
                          {(o.hunt_ids || []).map((hid: string, j: number) => (
                            <Chip key={j} label={huntList.find(h => h.id === hid)?.name || hid} size="small" sx={{ mr: 0.5 }} />
                          ))}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          )}

          {/* Technique overlaps */}
          {result.technique_overlaps.length > 0 && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="h6" gutterBottom>MITRE Technique Overlaps</Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap">
                {result.technique_overlaps.map((t: any, i: number) => (
                  <Chip key={i} label={t.technique || t.mitre_technique} color="secondary" size="small" />
                ))}
              </Stack>
            </Paper>
          )}

          {/* Time overlaps */}
          {result.time_overlaps.length > 0 && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="h6" gutterBottom>Time Overlaps</Typography>
              {result.time_overlaps.map((t: any, i: number) => (
                <Typography key={i} variant="body2" sx={{ mb: 0.5 }}>
                  {t.hunt_a || 'Hunt A'} ↔ {t.hunt_b || 'Hunt B'}: {t.overlap_start} — {t.overlap_end}
                </Typography>
              ))}
            </Paper>
          )}

          {/* Host overlaps */}
          {result.host_overlaps.length > 0 && (
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>Host Overlaps</Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap">
                {result.host_overlaps.map((h: any, i: number) => (
                  <Chip key={i} label={typeof h === 'string' ? h : h.hostname || JSON.stringify(h)} size="small" variant="outlined" />
                ))}
              </Stack>
            </Paper>
          )}
        </Box>
      )}
    </Box>
  );
}
