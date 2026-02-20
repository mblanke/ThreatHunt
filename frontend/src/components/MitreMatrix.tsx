/**
 * MitreMatrix — ATT&CK heat-map matrix + evidence drill-down.
 * Shows tactics as columns, techniques as cells with hit-count heat coloring.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Stack, FormControl, InputLabel, Select,
  MenuItem, CircularProgress, Alert, Chip, Tooltip, Dialog,
  DialogTitle, DialogContent, DialogActions, Button, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow,
  LinearProgress,
} from '@mui/material';
import {
  hunts, datasets, analysis,
  type HuntOut, type DatasetSummary, type MitreMapResponse,
  type MitreTactic, type MitreTechnique,
} from '../api/client';

function heatColor(count: number, max: number): string {
  if (count === 0) return 'transparent';
  const ratio = Math.min(count / Math.max(max, 1), 1);
  if (ratio > 0.7) return 'rgba(239,68,68,0.7)';     // red
  if (ratio > 0.4) return 'rgba(249,115,22,0.6)';     // orange
  if (ratio > 0.15) return 'rgba(234,179,8,0.5)';     // yellow
  return 'rgba(59,130,246,0.4)';                        // blue
}

export default function MitreMatrix() {
  const [huntList, setHuntList] = useState<HuntOut[]>([]);
  const [dsList, setDsList] = useState<DatasetSummary[]>([]);
  const [activeHunt, setActiveHunt] = useState('');
  const [activeDs, setActiveDs] = useState('');
  const [data, setData] = useState<MitreMapResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedTech, setSelectedTech] = useState<MitreTechnique | null>(null);

  useEffect(() => {
    hunts.list(0, 200).then(r => {
      setHuntList(r.hunts);
      if (r.hunts.length > 0) setActiveHunt(r.hunts[0].id);
    }).catch(() => {});
    datasets.list(0, 200).then(r => setDsList(r.datasets)).catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    if (!activeDs && !activeHunt) return;
    setLoading(true);
    setError('');
    try {
      const r = await analysis.mitreMap({
        dataset_id: activeDs || undefined,
        hunt_id: activeHunt || undefined,
      });
      setData(r);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }, [activeDs, activeHunt]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const maxHits = data ? Math.max(...data.tactics.flatMap(t => t.techniques.map(te => te.count)), 1) : 1;

  return (
    <Box>
      <Typography variant="h5" gutterBottom>MITRE ATT&amp;CK Matrix</Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Hunt</InputLabel>
            <Select label="Hunt" value={activeHunt}
              onChange={e => { setActiveHunt(e.target.value); setActiveDs(''); }}>
              <MenuItem value="">— none —</MenuItem>
              {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel>Dataset</InputLabel>
            <Select label="Dataset" value={activeDs}
              onChange={e => setActiveDs(e.target.value)}>
              <MenuItem value="">— all datasets —</MenuItem>
              {dsList.map(d => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
            </Select>
          </FormControl>
          {data && (
            <>
              <Chip label={`${data.coverage.tactics_covered}/${data.coverage.tactics_total} tactics`} size="small" color="info" variant="outlined" />
              <Chip label={`${data.coverage.techniques_matched} techniques`} size="small" color="warning" variant="outlined" />
              <Chip label={`${data.coverage.total_evidence} evidence hits`} size="small" color="error" variant="outlined" />
              <Chip label={`${data.total_rows.toLocaleString()} rows scanned`} size="small" variant="outlined" />
            </>
          )}
        </Stack>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading && <CircularProgress sx={{ display: 'block', mx: 'auto', my: 4 }} />}

      {/* ATT&CK Matrix Grid */}
      {data && !loading && (
        <Paper sx={{ p: 1, overflow: 'auto' }}>
          <Stack direction="row" spacing={0.5} sx={{ minWidth: data.tactics.length * 140 }}>
            {data.tactics.map(tactic => (
              <Box key={tactic.id} sx={{ flex: '0 0 140px', minWidth: 140 }}>
                {/* Tactic header */}
                <Paper
                  elevation={0}
                  sx={{
                    p: 0.5,
                    mb: 0.5,
                    background: tactic.total_hits > 0
                      ? 'rgba(99,102,241,0.2)'
                      : 'rgba(100,100,100,0.1)',
                    textAlign: 'center',
                    borderBottom: '2px solid',
                    borderColor: tactic.total_hits > 0 ? 'primary.main' : 'divider',
                  }}
                >
                  <Typography variant="caption" fontWeight={700} sx={{ fontSize: '0.65rem', lineHeight: 1.2 }}>
                    {tactic.name}
                  </Typography>
                  {tactic.total_hits > 0 && (
                    <Typography variant="caption" display="block" color="warning.main" sx={{ fontSize: '0.6rem' }}>
                      {tactic.total_hits} hits
                    </Typography>
                  )}
                </Paper>

                {/* Technique cells */}
                <Stack spacing={0.3}>
                  {tactic.techniques.map(tech => (
                    <Tooltip
                      key={tech.id}
                      title={`${tech.id}: ${tech.name} — ${tech.count} matches`}
                      arrow
                    >
                      <Paper
                        elevation={0}
                        onClick={() => setSelectedTech(tech)}
                        sx={{
                          p: 0.5,
                          cursor: 'pointer',
                          background: heatColor(tech.count, maxHits),
                          border: '1px solid',
                          borderColor: 'divider',
                          '&:hover': {
                            borderColor: 'primary.main',
                            transform: 'scale(1.02)',
                          },
                          transition: 'all 0.15s',
                        }}
                      >
                        <Typography variant="caption" fontWeight={600}
                          sx={{ fontSize: '0.6rem', lineHeight: 1.1, display: 'block' }}>
                          {tech.id}
                        </Typography>
                        <Typography variant="caption" color="text.secondary"
                          sx={{ fontSize: '0.55rem', lineHeight: 1.1 }}>
                          {tech.name}
                        </Typography>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min((tech.count / maxHits) * 100, 100)}
                          sx={{ height: 2, mt: 0.3, borderRadius: 1 }}
                          color={tech.count > maxHits * 0.5 ? 'error' : 'primary'}
                        />
                      </Paper>
                    </Tooltip>
                  ))}
                  {tactic.techniques.length === 0 && (
                    <Typography variant="caption" color="text.disabled"
                      sx={{ fontSize: '0.6rem', textAlign: 'center', py: 1 }}>
                      No matches
                    </Typography>
                  )}
                </Stack>
              </Box>
            ))}
          </Stack>
        </Paper>
      )}

      {!loading && !data && !error && (
        <Alert severity="info">Select a hunt or dataset to map to MITRE ATT&amp;CK.</Alert>
      )}

      {/* Evidence drill-down dialog */}
      <Dialog open={!!selectedTech} onClose={() => setSelectedTech(null)} maxWidth="md" fullWidth>
        <DialogTitle>
          {selectedTech?.id}: {selectedTech?.name}
          <Chip label={`${selectedTech?.count} hits`} size="small" color="warning" sx={{ ml: 1 }} />
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Evidence samples (up to 5 shown)
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Row</TableCell>
                  <TableCell>Field</TableCell>
                  <TableCell>Value</TableCell>
                  <TableCell>Pattern</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {selectedTech?.evidence.map((ev, i) => (
                  <TableRow key={i} hover>
                    <TableCell>{ev.row_index}</TableCell>
                    <TableCell><Chip label={ev.field || '—'} size="small" /></TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ maxWidth: 300, wordBreak: 'break-all' }}>
                        {ev.value}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" fontFamily="monospace">{ev.pattern}</Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedTech(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
