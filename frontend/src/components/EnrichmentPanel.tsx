/**
 * EnrichmentPanel — manual IOC lookup + batch enrichment results.
 */

import React, { useState, useCallback } from 'react';
import {
  Box, Typography, Paper, TextField, Stack, Button, Chip,
  Select, MenuItem, FormControl, InputLabel, CircularProgress,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Alert,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useSnackbar } from 'notistack';
import { enrichment, type EnrichmentResult } from '../api/client';

const IOC_TYPES = ['ip', 'domain', 'hash_md5', 'hash_sha1', 'hash_sha256', 'url'];

const VERDICT_COLORS: Record<string, 'error' | 'warning' | 'success' | 'default' | 'info'> = {
  malicious: 'error', suspicious: 'warning', clean: 'success', unknown: 'default', error: 'info',
};

export default function EnrichmentPanel() {
  const { enqueueSnackbar } = useSnackbar();
  const [iocValue, setIocValue] = useState('');
  const [iocType, setIocType] = useState('ip');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<EnrichmentResult[]>([]);
  const [overallVerdict, setOverallVerdict] = useState('');
  const [overallScore, setOverallScore] = useState(0);

  const lookup = useCallback(async () => {
    if (!iocValue.trim()) return;
    setLoading(true);
    try {
      const r = await enrichment.ioc(iocValue.trim(), iocType);
      setResults(r.results);
      setOverallVerdict(r.overall_verdict);
      setOverallScore(r.overall_score);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
    setLoading(false);
  }, [iocValue, iocType, enqueueSnackbar]);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>IOC Enrichment</Typography>

      {/* Lookup form */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Type</InputLabel>
            <Select label="Type" value={iocType} onChange={e => setIocType(e.target.value)}>
              {IOC_TYPES.map(t => <MenuItem key={t} value={t}>{t}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField
            size="small" fullWidth label="IOC Value"
            placeholder="e.g. 1.2.3.4 or evil.com"
            value={iocValue}
            onChange={e => setIocValue(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && lookup()}
          />
          <Button variant="contained" startIcon={loading ? <CircularProgress size={16} /> : <SearchIcon />}
            onClick={lookup} disabled={loading || !iocValue.trim()}>
            Lookup
          </Button>
        </Stack>
      </Paper>

      {/* Overall verdict */}
      {overallVerdict && (
        <Alert severity={overallVerdict === 'malicious' ? 'error' : overallVerdict === 'suspicious' ? 'warning' : 'info'} sx={{ mb: 2 }}>
          Overall verdict: <strong>{overallVerdict}</strong> — Score: {overallScore.toFixed(1)}
        </Alert>
      )}

      {/* Results table */}
      {results.length > 0 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Source</TableCell>
                <TableCell>Verdict</TableCell>
                <TableCell>Score</TableCell>
                <TableCell>Country</TableCell>
                <TableCell>Org</TableCell>
                <TableCell>Tags</TableCell>
                <TableCell>Latency</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {results.map((r, i) => (
                <TableRow key={i}>
                  <TableCell>{r.source}</TableCell>
                  <TableCell>
                    <Chip label={r.verdict} size="small"
                      color={VERDICT_COLORS[r.verdict] || 'default'} variant="outlined" />
                  </TableCell>
                  <TableCell>{r.score.toFixed(1)}</TableCell>
                  <TableCell>{r.country || '—'}</TableCell>
                  <TableCell>{r.org || '—'}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap">
                      {r.tags.slice(0, 5).map((t, j) => <Chip key={j} label={t} size="small" />)}
                    </Stack>
                  </TableCell>
                  <TableCell>{r.latency_ms}ms</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
