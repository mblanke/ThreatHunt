/**
 * AnalysisPanel — LLM-powered threat analysis of datasets.
 *
 * Replaces the old EnrichmentPanel (which required VT/AbuseIPDB/Shodan API
 * keys).  Uses Wile (70B) and Roadrunner (fast) to perform deep threat analysis
 * of uploaded forensic data, returning structured findings, IOCs, MITRE
 * techniques, and actionable recommendations — all rendered in markdown.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Paper, Typography, Stack, Alert, CircularProgress, Chip,
  FormControl, InputLabel, Select, MenuItem, TextField, Button,
  Divider, LinearProgress, Grid, ToggleButton, ToggleButtonGroup,
  Tooltip,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import SpeedIcon from '@mui/icons-material/Speed';
import PsychologyIcon from '@mui/icons-material/Psychology';
import SecurityIcon from '@mui/icons-material/Security';
import BugReportIcon from '@mui/icons-material/BugReport';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSnackbar } from 'notistack';
import {
  analysis, hunts, datasets, type Hunt, type DatasetSummary,
  type LLMAnalysisResult,
} from '../api/client';

const FOCUS_OPTIONS = [
  { value: '', label: 'General', icon: <SecurityIcon fontSize="small" /> },
  { value: 'threats', label: 'Threats', icon: <BugReportIcon fontSize="small" /> },
  { value: 'anomalies', label: 'Anomalies', icon: <TravelExploreIcon fontSize="small" /> },
  { value: 'lateral_movement', label: 'Lateral Mvmt', icon: <SecurityIcon fontSize="small" /> },
  { value: 'exfil', label: 'Exfiltration', icon: <SecurityIcon fontSize="small" /> },
  { value: 'persistence', label: 'Persistence', icon: <SecurityIcon fontSize="small" /> },
  { value: 'recon', label: 'Recon', icon: <TravelExploreIcon fontSize="small" /> },
];

const SEV_COLORS: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#3b82f6', info: '#6b7280',
};

function RiskGauge({ score }: { score: number }) {
  const color = score >= 75 ? '#ef4444' : score >= 50 ? '#f97316' : score >= 25 ? '#eab308' : '#10b981';
  return (
    <Box sx={{ textAlign: 'center' }}>
      <Box sx={{ position: 'relative', display: 'inline-flex' }}>
        <CircularProgress variant="determinate" value={score} size={80}
          thickness={5} sx={{ color }} />
        <Box sx={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Typography variant="h5" sx={{ fontWeight: 700, color }}>{score}</Typography>
        </Box>
      </Box>
      <Typography variant="caption" display="block" color="text.secondary">Risk Score</Typography>
    </Box>
  );
}

export default function AnalysisPanel() {
  const { enqueueSnackbar } = useSnackbar();

  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [datasetList, setDatasetList] = useState<DatasetSummary[]>([]);
  const [selectedHunt, setSelectedHunt] = useState('');
  const [selectedDataset, setSelectedDataset] = useState('');
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<'quick' | 'deep'>('deep');
  const [focus, setFocus] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<LLMAnalysisResult | null>(null);

  /* load hunts + datasets */
  useEffect(() => {
    (async () => {
      try {
        const [h, d] = await Promise.all([
          hunts.list(0, 100),
          datasets.list(0, 200),
        ]);
        setHuntList(h.hunts);
        setDatasetList(d.datasets);
        if (h.hunts.length > 0) setSelectedHunt(h.hunts[0].id);
      } catch {}
    })();
  }, []);

  const huntDatasets = selectedHunt
    ? datasetList.filter(d => d.hunt_id === selectedHunt)
    : datasetList;

  const runAnalysis = useCallback(async () => {
    if (!selectedHunt && !selectedDataset) {
      enqueueSnackbar('Select a hunt or dataset', { variant: 'warning' });
      return;
    }
    setLoading(true);
    try {
      const res = await analysis.llmAnalyze({
        dataset_id: selectedDataset || undefined,
        hunt_id: selectedDataset ? undefined : selectedHunt,
        question: question || undefined,
        mode,
        focus: focus || undefined,
      });
      setResult(res);
      enqueueSnackbar(`Analysis complete in ${(res.latency_ms / 1000).toFixed(1)}s`, { variant: 'success' });
    } catch (e: any) {
      enqueueSnackbar(e.message || 'Analysis failed', { variant: 'error' });
    }
    setLoading(false);
  }, [selectedHunt, selectedDataset, question, mode, focus, enqueueSnackbar]);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>LLM Threat Analysis</Typography>

      {/* Controls */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack spacing={2}>
          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Hunt</InputLabel>
              <Select label="Hunt" value={selectedHunt}
                onChange={e => { setSelectedHunt(e.target.value); setSelectedDataset(''); }}>
                {huntList.map(h => (
                  <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel>Dataset</InputLabel>
              <Select label="Dataset" value={selectedDataset}
                onChange={e => setSelectedDataset(e.target.value)}>
                <MenuItem value="">All in hunt</MenuItem>
                {huntDatasets.map(d => (
                  <MenuItem key={d.id} value={d.id}>
                    {d.name} ({d.row_count} rows)
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <ToggleButtonGroup size="small" value={mode} exclusive
              onChange={(_, v) => v && setMode(v)}>
              <ToggleButton value="quick">
                <Tooltip title="Quick (Roadrunner fast model)"><SpeedIcon fontSize="small" /></Tooltip>
              </ToggleButton>
              <ToggleButton value="deep">
                <Tooltip title="Deep (Wile 70B model)"><PsychologyIcon fontSize="small" /></Tooltip>
              </ToggleButton>
            </ToggleButtonGroup>

            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Focus</InputLabel>
              <Select label="Focus" value={focus} onChange={e => setFocus(e.target.value)}>
                {FOCUS_OPTIONS.map(f => (
                  <MenuItem key={f.value} value={f.value}>{f.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>

          <Stack direction="row" spacing={1.5} alignItems="center">
            <TextField
              size="small" fullWidth
              label="Ask a specific question (optional)"
              placeholder="e.g. Is there evidence of lateral movement via PsExec?"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && runAnalysis()}
            />
            <Button
              variant="contained" startIcon={loading ? <CircularProgress size={16} /> : <PlayArrowIcon />}
              onClick={runAnalysis} disabled={loading || (!selectedHunt && !selectedDataset)}
              sx={{ minWidth: 140 }}
            >
              {loading ? 'Analyzing...' : 'Analyze'}
            </Button>
          </Stack>
        </Stack>

        {loading && <LinearProgress sx={{ mt: 1 }} />}
      </Paper>

      {/* Results */}
      {result && (
        <Grid container spacing={2}>
          {/* Left: main analysis */}
          <Grid size={{ xs: 12, md: 8 }}>
            <Paper sx={{ p: 2.5, maxHeight: 'calc(100vh - 320px)', overflow: 'auto' }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                <RiskGauge score={result.risk_score} />
                <Box sx={{ flex: 1, ml: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    {result.rows_analyzed.toLocaleString()} rows analyzed • {result.model_used} on {result.node_used}
                    • {(result.latency_ms / 1000).toFixed(1)}s
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Confidence: {(result.confidence * 100).toFixed(0)}%
                  </Typography>
                </Box>
              </Stack>

              <Divider sx={{ mb: 2 }} />

              <Box sx={{
                '& h1': { fontSize: '1.4rem', mt: 2, mb: 1 },
                '& h2': { fontSize: '1.2rem', mt: 2, mb: 1 },
                '& h3': { fontSize: '1rem', mt: 1.5, mb: 0.5 },
                '& p': { mb: 1 },
                '& ul, & ol': { pl: 3, mb: 1 },
                '& code': { bgcolor: 'action.hover', px: 0.5, borderRadius: 0.5, fontFamily: 'monospace', fontSize: '0.85em' },
                '& pre': { bgcolor: 'background.default', p: 1.5, borderRadius: 1, overflow: 'auto' },
                '& table': { width: '100%', borderCollapse: 'collapse', mb: 2 },
                '& th, & td': { border: '1px solid', borderColor: 'divider', p: 0.5, fontSize: '0.85rem' },
              }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result.analysis}
                </ReactMarkdown>
              </Box>
            </Paper>
          </Grid>

          {/* Right: structured findings */}
          <Grid size={{ xs: 12, md: 4 }}>
            <Stack spacing={2}>
              {/* Key findings */}
              {result.key_findings.length > 0 && (
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>Key Findings</Typography>
                  <Stack spacing={0.5}>
                    {result.key_findings.map((f, i) => (
                      <Alert key={i} severity="warning" variant="outlined" sx={{ py: 0 }}>
                        <Typography variant="body2">{f}</Typography>
                      </Alert>
                    ))}
                  </Stack>
                </Paper>
              )}

              {/* IOCs identified */}
              {result.iocs_identified.length > 0 && (
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>IOCs Identified</Typography>
                  <Stack spacing={0.5}>
                    {result.iocs_identified.map((ioc, i) => (
                      <Stack key={i} direction="row" spacing={0.5} alignItems="center">
                        <Chip label={ioc.type} size="small" color="error" variant="outlined" />
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                          {ioc.value}
                        </Typography>
                        {ioc.context && (
                          <Typography variant="caption" color="text.secondary">
                            — {ioc.context}
                          </Typography>
                        )}
                      </Stack>
                    ))}
                  </Stack>
                </Paper>
              )}

              {/* MITRE techniques */}
              {result.mitre_techniques.length > 0 && (
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>MITRE ATT&CK</Typography>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {result.mitre_techniques.map((t, i) => (
                      <Chip key={i} label={t} size="small" color="info" variant="outlined"
                        sx={{ fontSize: 11 }} />
                    ))}
                  </Stack>
                </Paper>
              )}

              {/* Recommended actions */}
              {result.recommended_actions.length > 0 && (
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>Recommended Actions</Typography>
                  <Stack spacing={0.5}>
                    {result.recommended_actions.map((a, i) => (
                      <Typography key={i} variant="body2">
                        {i + 1}. {a}
                      </Typography>
                    ))}
                  </Stack>
                </Paper>
              )}
            </Stack>
          </Grid>
        </Grid>
      )}

      {/* Empty state */}
      {!result && !loading && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <PsychologyIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            Select a dataset and click Analyze
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Uses Wile (70B) or Roadrunner for AI-powered threat analysis of your forensic data.
            No external API keys required.
          </Typography>
        </Paper>
      )}
    </Box>
  );
}
