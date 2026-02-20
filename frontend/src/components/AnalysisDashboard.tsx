/**
 * AnalysisDashboard  -- 6-tab view covering the full AI analysis pipeline:
 * 1. Triage results
 * 2. Host profiles
 * 3. Reports
 * 4. Anomalies
 * 5. Ask Data (natural language query with SSE streaming) -- Phase 9
 * 6. Jobs & Load Balancer status -- Phase 10
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box, Typography, Tabs, Tab, Paper, Button, Chip, Stack, CircularProgress,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Accordion, AccordionSummary, AccordionDetails, Alert, Select, MenuItem,
  FormControl, InputLabel, LinearProgress, Tooltip, IconButton, Divider,
  Card, CardContent, CardActions, Grid, TextField, ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';
import AssessmentIcon from '@mui/icons-material/Assessment';
import SecurityIcon from '@mui/icons-material/Security';
import PersonIcon from '@mui/icons-material/Person';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ShieldIcon from '@mui/icons-material/Shield';
import BubbleChartIcon from '@mui/icons-material/BubbleChart';
import QuestionAnswerIcon from '@mui/icons-material/QuestionAnswer';
import WorkIcon from '@mui/icons-material/Work';
import SendIcon from '@mui/icons-material/Send';
import StopIcon from '@mui/icons-material/Stop';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import CancelIcon from '@mui/icons-material/Cancel';
import { useSnackbar } from 'notistack';
import {
  analysis, hunts, datasets,
  type Hunt, type DatasetSummary,
  type TriageResultData, type HostProfileData, type HuntReportData,
  type AnomalyResultData, type JobData, type JobStats, type LBNodeStatus,
} from '../api/client';

/*  helpers  */

function riskColor(score: number): 'error' | 'warning' | 'info' | 'success' | 'default' {
  if (score >= 8) return 'error';
  if (score >= 5) return 'warning';
  if (score >= 2) return 'info';
  return 'success';
}

function riskLabel(level: string): 'error' | 'warning' | 'info' | 'success' | 'default' {
  if (level === 'critical' || level === 'high') return 'error';
  if (level === 'medium') return 'warning';
  if (level === 'low') return 'success';
  return 'default';
}

function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtTime(ts: number): string {
  if (!ts) return '--';
  return new Date(ts * 1000).toLocaleTimeString();
}

const statusIcon = (s: string) => {
  switch (s) {
    case 'completed': return <CheckCircleIcon color="success" sx={{ fontSize: 18 }} />;
    case 'failed': return <ErrorIcon color="error" sx={{ fontSize: 18 }} />;
    case 'running': return <CircularProgress size={16} />;
    case 'queued': return <HourglassEmptyIcon color="action" sx={{ fontSize: 18 }} />;
    case 'cancelled': return <CancelIcon color="disabled" sx={{ fontSize: 18 }} />;
    default: return null;
  }
};

/*  TabPanel  */

function TabPanel({ children, value, index }: { children: React.ReactNode; value: number; index: number }) {
  return value === index ? <Box sx={{ pt: 2 }}>{children}</Box> : null;
}

/*  Main component  */

export default function AnalysisDashboard() {
  const { enqueueSnackbar } = useSnackbar();
  const [tab, setTab] = useState(0);

  // Selectors
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [dsList, setDsList] = useState<DatasetSummary[]>([]);
  const [huntId, setHuntId] = useState('');
  const [dsId, setDsId] = useState('');

  // Data tabs 0-3
  const [triageResults, setTriageResults] = useState<TriageResultData[]>([]);
  const [profiles, setProfiles] = useState<HostProfileData[]>([]);
  const [reports, setReports] = useState<HuntReportData[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyResultData[]>([]);

  // Loading states
  const [loadingTriage, setLoadingTriage] = useState(false);
  const [loadingProfiles, setLoadingProfiles] = useState(false);
  const [loadingReports, setLoadingReports] = useState(false);
  const [loadingAnomalies, setLoadingAnomalies] = useState(false);
  const [triggering, setTriggering] = useState(false);

  // Phase 9: Ask Data
  const [queryText, setQueryText] = useState('');
  const [queryMode, setQueryMode] = useState<string>('quick');
  const [queryAnswer, setQueryAnswer] = useState('');
  const [queryStreaming, setQueryStreaming] = useState(false);
  const [queryMeta, setQueryMeta] = useState<Record<string, any> | null>(null);
  const [queryDone, setQueryDone] = useState<Record<string, any> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const answerRef = useRef<HTMLDivElement>(null);

  // Phase 10: Jobs
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [jobStats, setJobStats] = useState<JobStats | null>(null);
  const [lbStatus, setLbStatus] = useState<Record<string, LBNodeStatus> | null>(null);
  const [loadingJobs, setLoadingJobs] = useState(false);

  // Load hunts and datasets
  useEffect(() => {
    hunts.list(0, 200).then(r => setHuntList(r.hunts)).catch(() => {});
    datasets.list(0, 200).then(r => setDsList(r.datasets)).catch(() => {});
  }, []);

  useEffect(() => {
    if (huntList.length > 0 && !huntId) setHuntId(huntList[0].id);
  }, [huntList, huntId]);

  useEffect(() => {
    if (dsList.length > 0 && !dsId) setDsId(dsList[0].id);
  }, [dsList, dsId]);

  /*  Fetch triage results  */
  const fetchTriage = useCallback(async () => {
    if (!dsId) return;
    setLoadingTriage(true);
    try {
      const data = await analysis.triageResults(dsId);
      setTriageResults(data);
    } catch (e: any) {
      enqueueSnackbar(`Triage fetch failed: ${e.message}`, { variant: 'error' });
    } finally { setLoadingTriage(false); }
  }, [dsId, enqueueSnackbar]);

  const fetchProfiles = useCallback(async () => {
    if (!huntId) return;
    setLoadingProfiles(true);
    try {
      const data = await analysis.hostProfiles(huntId);
      setProfiles(data);
    } catch (e: any) {
      enqueueSnackbar(`Profiles fetch failed: ${e.message}`, { variant: 'error' });
    } finally { setLoadingProfiles(false); }
  }, [huntId, enqueueSnackbar]);

  const fetchReports = useCallback(async () => {
    if (!huntId) return;
    setLoadingReports(true);
    try {
      const data = await analysis.listReports(huntId);
      setReports(data);
    } catch (e: any) {
      enqueueSnackbar(`Reports fetch failed: ${e.message}`, { variant: 'error' });
    } finally { setLoadingReports(false); }
  }, [huntId, enqueueSnackbar]);

  const fetchAnomalies = useCallback(async () => {
    if (!dsId) return;
    setLoadingAnomalies(true);
    try {
      const data = await analysis.anomalies(dsId);
      setAnomalies(data);
    } catch (e: any) {
      enqueueSnackbar('Anomaly fetch failed: ' + e.message, { variant: 'error' });
    } finally { setLoadingAnomalies(false); }
  }, [dsId, enqueueSnackbar]);

  const fetchJobs = useCallback(async () => {
    setLoadingJobs(true);
    try {
      const data = await analysis.listJobs();
      setJobs(data.jobs);
      setJobStats(data.stats);
    } catch (e: any) {
      enqueueSnackbar('Jobs fetch failed: ' + e.message, { variant: 'error' });
    } finally { setLoadingJobs(false); }
  }, [enqueueSnackbar]);

  const fetchLbStatus = useCallback(async () => {
    try {
      const data = await analysis.lbStatus();
      setLbStatus(data);
    } catch {}
  }, []);

  // Load data when selectors change
  useEffect(() => { if (dsId) fetchTriage(); }, [dsId, fetchTriage]);
  useEffect(() => { if (huntId) { fetchProfiles(); fetchReports(); } }, [huntId, fetchProfiles, fetchReports]);

  // Auto-refresh jobs when on jobs tab
  useEffect(() => {
    if (tab === 5) {
      fetchJobs();
      fetchLbStatus();
      const iv = setInterval(() => { fetchJobs(); fetchLbStatus(); }, 5000);
      return () => clearInterval(iv);
    }
  }, [tab, fetchJobs, fetchLbStatus]);

  /*  Trigger actions  */
  const doTriggerTriage = useCallback(async () => {
    if (!dsId) return;
    setTriggering(true);
    try {
      await analysis.triggerTriage(dsId);
      enqueueSnackbar('Triage started', { variant: 'info' });
      setTimeout(fetchTriage, 5000);
    } catch (e: any) {
      enqueueSnackbar(`Triage trigger failed: ${e.message}`, { variant: 'error' });
    } finally { setTriggering(false); }
  }, [dsId, enqueueSnackbar, fetchTriage]);

  const doTriggerProfiles = useCallback(async () => {
    if (!huntId) return;
    setTriggering(true);
    try {
      await analysis.triggerAllProfiles(huntId);
      enqueueSnackbar('Host profiling started', { variant: 'info' });
      setTimeout(fetchProfiles, 10000);
    } catch (e: any) {
      enqueueSnackbar(`Profile trigger failed: ${e.message}`, { variant: 'error' });
    } finally { setTriggering(false); }
  }, [huntId, enqueueSnackbar, fetchProfiles]);

  const doGenerateReport = useCallback(async () => {
    if (!huntId) return;
    setTriggering(true);
    try {
      await analysis.generateReport(huntId);
      enqueueSnackbar('Report generation started', { variant: 'info' });
      setTimeout(fetchReports, 15000);
    } catch (e: any) {
      enqueueSnackbar(`Report generation failed: ${e.message}`, { variant: 'error' });
    } finally { setTriggering(false); }
  }, [huntId, enqueueSnackbar, fetchReports]);

  const doTriggerAnomalies = useCallback(async () => {
    if (!dsId) return;
    setTriggering(true);
    try {
      await analysis.triggerAnomalyDetection(dsId);
      enqueueSnackbar('Anomaly detection started', { variant: 'info' });
      setTimeout(fetchAnomalies, 20000);
    } catch (e: any) {
      enqueueSnackbar('Anomaly trigger failed: ' + e.message, { variant: 'error' });
    } finally { setTriggering(false); }
  }, [dsId, enqueueSnackbar, fetchAnomalies]);

  /*  Phase 9: Streaming data query  */
  const doQuery = useCallback(async () => {
    if (!dsId || !queryText.trim()) return;
    setQueryStreaming(true);
    setQueryAnswer('');
    setQueryMeta(null);
    setQueryDone(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const resp = await analysis.queryStream(dsId, queryText.trim(), queryMode);
      if (!resp.body) throw new Error('No response body');

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        const lines = buf.split('\n');
        buf = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            switch (evt.type) {
              case 'token':
                setQueryAnswer(prev => prev + evt.content);
                if (answerRef.current) {
                  answerRef.current.scrollTop = answerRef.current.scrollHeight;
                }
                break;
              case 'metadata':
                setQueryMeta(evt.dataset);
                break;
              case 'done':
                setQueryDone(evt);
                break;
              case 'error':
                enqueueSnackbar(`Query error: ${evt.message}`, { variant: 'error' });
                break;
            }
          } catch {}
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        enqueueSnackbar('Query failed: ' + e.message, { variant: 'error' });
      }
    } finally {
      setQueryStreaming(false);
      abortRef.current = null;
    }
  }, [dsId, queryText, queryMode, enqueueSnackbar]);

  const stopQuery = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      setQueryStreaming(false);
    }
  }, []);

  /*  Phase 10: Cancel job  */
  const doCancelJob = useCallback(async (jobId: string) => {
    try {
      await analysis.cancelJob(jobId);
      enqueueSnackbar('Job cancelled', { variant: 'info' });
      fetchJobs();
    } catch (e: any) {
      enqueueSnackbar('Cancel failed: ' + e.message, { variant: 'error' });
    }
  }, [enqueueSnackbar, fetchJobs]);

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 2 }}>
        <AssessmentIcon color="primary" sx={{ fontSize: 32 }} />
        <Typography variant="h5">AI Analysis</Typography>
        {triggering && <CircularProgress size={20} />}
      </Stack>

      {/* Selectors */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" spacing={2} flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 260 }}>
            <InputLabel>Hunt</InputLabel>
            <Select label="Hunt" value={huntId} onChange={e => setHuntId(e.target.value)}>
              {huntList.map(h => (
                <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 260 }}>
            <InputLabel>Dataset</InputLabel>
            <Select label="Dataset" value={dsId} onChange={e => setDsId(e.target.value)}>
              {dsList.map(d => (
                <MenuItem key={d.id} value={d.id}>{d.name} ({d.row_count} rows)</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
      </Paper>

      {/* Tabs */}
      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto" sx={{ mb: 1 }}>
        <Tab icon={<SecurityIcon />} iconPosition="start" label={`Triage (${triageResults.length})`} />
        <Tab icon={<PersonIcon />} iconPosition="start" label={`Host Profiles (${profiles.length})`} />
        <Tab icon={<AssessmentIcon />} iconPosition="start" label={`Reports (${reports.length})`} />
        <Tab icon={<BubbleChartIcon />} iconPosition="start" label={`Anomalies (${anomalies.filter(a => a.is_outlier).length})`} />
        <Tab icon={<QuestionAnswerIcon />} iconPosition="start" label="Ask Data" />
        <Tab icon={<WorkIcon />} iconPosition="start" label={`Jobs${jobStats ? ` (${jobStats.active_workers})` : ''}`} />
      </Tabs>

      {/*  Tab 0: Triage  */}
      <TabPanel value={tab} index={0}>
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={doTriggerTriage}
            disabled={!dsId || triggering} size="small">Run Triage</Button>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchTriage}
            disabled={!dsId || loadingTriage} size="small">Refresh</Button>
        </Stack>
        {loadingTriage && <LinearProgress sx={{ mb: 1 }} />}
        {triageResults.length === 0 && !loadingTriage ? (
          <Alert severity="info">No triage results yet. Select a dataset and click "Run Triage".</Alert>
        ) : (
          <TableContainer component={Paper} sx={{ maxHeight: 500 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Rows</TableCell><TableCell>Risk</TableCell><TableCell>Verdict</TableCell>
                  <TableCell>Findings</TableCell><TableCell>MITRE</TableCell><TableCell>Model</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {triageResults.map(tr => (
                  <TableRow key={tr.id} hover>
                    <TableCell>{tr.row_start}-{tr.row_end}</TableCell>
                    <TableCell><Chip label={tr.risk_score.toFixed(1)} size="small" color={riskColor(tr.risk_score)} /></TableCell>
                    <TableCell><Chip label={tr.verdict} size="small" variant="outlined" /></TableCell>
                    <TableCell sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {tr.findings?.join('; ') || ''}
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5} flexWrap="wrap">
                        {tr.mitre_techniques?.map((t: string, i: number) => (
                          <Chip key={i} label={t} size="small" variant="outlined" color="warning" />
                        ))}
                      </Stack>
                    </TableCell>
                    <TableCell><Typography variant="caption">{tr.model_used || ''}</Typography></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </TabPanel>

      {/*  Tab 1: Host Profiles  */}
      <TabPanel value={tab} index={1}>
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={doTriggerProfiles}
            disabled={!huntId || triggering} size="small">Profile All Hosts</Button>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchProfiles}
            disabled={!huntId || loadingProfiles} size="small">Refresh</Button>
        </Stack>
        {loadingProfiles && <LinearProgress sx={{ mb: 1 }} />}
        {profiles.length === 0 && !loadingProfiles ? (
          <Alert severity="info">No host profiles yet. Select a hunt and click "Profile All Hosts".</Alert>
        ) : (
          <Grid container spacing={2}>
            {profiles.map(hp => (
              <Grid size={{ xs: 12, md: 6, lg: 4 }} key={hp.id}>
                <Card variant="outlined" sx={{
                  borderLeft: 4,
                  borderLeftColor: hp.risk_level === 'critical' ? 'error.main'
                    : hp.risk_level === 'high' ? 'error.light'
                    : hp.risk_level === 'medium' ? 'warning.main' : 'success.main',
                }}>
                  <CardContent>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="h6">{hp.hostname}</Typography>
                      <Chip label={`${hp.risk_score.toFixed(1)} ${hp.risk_level}`}
                        size="small" color={riskLabel(hp.risk_level)} />
                    </Stack>
                    {hp.fqdn && <Typography variant="caption" color="text.secondary">{hp.fqdn}</Typography>}
                    <Divider sx={{ my: 1 }} />
                    {hp.timeline_summary && (
                      <Typography variant="body2" sx={{ mb: 1, whiteSpace: 'pre-wrap' }}>
                        {hp.timeline_summary.slice(0, 300)}{hp.timeline_summary.length > 300 ? '...' : ''}
                      </Typography>
                    )}
                    {hp.suspicious_findings && hp.suspicious_findings.length > 0 && (
                      <Box sx={{ mb: 1 }}>
                        <Typography variant="caption" color="warning.main">
                          <WarningAmberIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                          {hp.suspicious_findings.length} suspicious finding(s)
                        </Typography>
                      </Box>
                    )}
                    {hp.mitre_techniques && hp.mitre_techniques.length > 0 && (
                      <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mb: 1 }}>
                        {hp.mitre_techniques.map((t: string, i: number) => (
                          <Chip key={i} label={t} size="small" variant="outlined" color="warning" />
                        ))}
                      </Stack>
                    )}
                  </CardContent>
                  <CardActions>
                    <Typography variant="caption" color="text.secondary">Model: {hp.model_used || 'N/A'}</Typography>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </TabPanel>

      {/*  Tab 2: Reports  */}
      <TabPanel value={tab} index={2}>
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={doGenerateReport}
            disabled={!huntId || triggering} size="small">Generate Report</Button>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchReports}
            disabled={!huntId || loadingReports} size="small">Refresh</Button>
        </Stack>
        {loadingReports && <LinearProgress sx={{ mb: 1 }} />}
        {reports.length === 0 && !loadingReports ? (
          <Alert severity="info">No reports yet. Select a hunt and click "Generate Report".</Alert>
        ) : (
          reports.map(rpt => (
            <Accordion key={rpt.id} defaultExpanded={reports.length === 1}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <ShieldIcon color="primary" />
                  <Typography>Report - {rpt.status}</Typography>
                  {rpt.generation_time_ms && (
                    <Chip label={fmtMs(rpt.generation_time_ms)} size="small" variant="outlined" />
                  )}
                </Stack>
              </AccordionSummary>
              <AccordionDetails>
                {rpt.exec_summary && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="primary">Executive Summary</Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{rpt.exec_summary}</Typography>
                  </Box>
                )}
                {rpt.findings && rpt.findings.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="warning.main">Findings</Typography>
                    <ul style={{ margin: 0, paddingLeft: 20 }}>
                      {rpt.findings.map((f: any, i: number) => (
                        <li key={i}><Typography variant="body2">
                          {typeof f === 'string' ? f : JSON.stringify(f)}
                        </Typography></li>
                      ))}
                    </ul>
                  </Box>
                )}
                {rpt.recommendations && rpt.recommendations.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="success.main">Recommendations</Typography>
                    <ul style={{ margin: 0, paddingLeft: 20 }}>
                      {rpt.recommendations.map((r: any, i: number) => (
                        <li key={i}><Typography variant="body2">
                          {typeof r === 'string' ? r : JSON.stringify(r)}
                        </Typography></li>
                      ))}
                    </ul>
                  </Box>
                )}
                {rpt.ioc_table && rpt.ioc_table.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2">IOC Table</Typography>
                    <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 300 }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            {Object.keys(rpt.ioc_table[0]).map(k => (
                              <TableCell key={k}>{k}</TableCell>
                            ))}
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {rpt.ioc_table.map((row: any, i: number) => (
                            <TableRow key={i}>
                              {Object.values(row).map((v: any, j: number) => (
                                <TableCell key={j}><Typography variant="caption">{String(v)}</Typography></TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Box>
                )}
                {rpt.full_report && (
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="body2">Full Report</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12 }}>
                        {rpt.full_report}
                      </Typography>
                    </AccordionDetails>
                  </Accordion>
                )}
                <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                  {rpt.models_used?.map((m: string, i: number) => (
                    <Chip key={i} label={m} size="small" variant="outlined" />
                  ))}
                </Stack>
              </AccordionDetails>
            </Accordion>
          ))
        )}
      </TabPanel>

      {/*  Tab 3: Anomalies  */}
      <TabPanel value={tab} index={3}>
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={doTriggerAnomalies}
            disabled={!dsId || triggering} size="small">Detect Anomalies</Button>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchAnomalies}
            disabled={!dsId || loadingAnomalies} size="small">Refresh</Button>
        </Stack>
        {loadingAnomalies && <LinearProgress sx={{ mb: 1 }} />}
        {anomalies.length === 0 && !loadingAnomalies ? (
          <Alert severity="info">No anomaly results yet. Select a dataset and click "Detect Anomalies".</Alert>
        ) : (
          <>
            <Alert severity="warning" sx={{ mb: 1 }}>
              {anomalies.filter(a => a.is_outlier).length} outlier(s) detected out of {anomalies.length} rows
            </Alert>
            <TableContainer component={Paper} sx={{ maxHeight: 500 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Row</TableCell><TableCell>Score</TableCell>
                    <TableCell>Distance</TableCell><TableCell>Cluster</TableCell><TableCell>Outlier</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {anomalies.filter(a => a.is_outlier).concat(anomalies.filter(a => !a.is_outlier).slice(0, 20)).map((a, i) => (
                    <TableRow key={a.id || i} hover sx={a.is_outlier ? { bgcolor: 'rgba(244,63,94,0.08)' } : {}}>
                      <TableCell>{a.row_id ?? ''}</TableCell>
                      <TableCell>
                        <Chip label={a.anomaly_score.toFixed(4)} size="small"
                          color={a.anomaly_score > 0.5 ? 'error' : a.anomaly_score > 0.35 ? 'warning' : 'success'} />
                      </TableCell>
                      <TableCell>{a.distance_from_centroid?.toFixed(4) ?? ''}</TableCell>
                      <TableCell><Chip label={`C${a.cluster_id}`} size="small" variant="outlined" /></TableCell>
                      <TableCell>
                        {a.is_outlier
                          ? <Chip label="OUTLIER" size="small" color="error" />
                          : <Chip label="Normal" size="small" color="success" variant="outlined" />}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        )}
      </TabPanel>

      {/*  Tab 4: Ask Data (Phase 9)  */}
      <TabPanel value={tab} index={4}>
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Ask a question about the selected dataset in plain English
          </Typography>
          <Stack direction="row" spacing={1} alignItems="flex-end">
            <TextField
              fullWidth size="small" multiline maxRows={3}
              placeholder="e.g., Are there any suspicious processes running at unusual hours?"
              value={queryText}
              onChange={e => setQueryText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doQuery(); } }}
              disabled={queryStreaming}
            />
            <ToggleButtonGroup
              value={queryMode} exclusive size="small"
              onChange={(_, v) => { if (v) setQueryMode(v); }}
            >
              <ToggleButton value="quick">
                <Tooltip title="Fast (Roadrunner)"><Typography variant="caption">Quick</Typography></Tooltip>
              </ToggleButton>
              <ToggleButton value="deep">
                <Tooltip title="Deep (Wile 70B)"><Typography variant="caption">Deep</Typography></Tooltip>
              </ToggleButton>
            </ToggleButtonGroup>
            {queryStreaming ? (
              <IconButton color="error" onClick={stopQuery}><StopIcon /></IconButton>
            ) : (
              <IconButton color="primary" onClick={doQuery} disabled={!dsId || !queryText.trim()}>
                <SendIcon />
              </IconButton>
            )}
          </Stack>
        </Paper>

        {queryMeta && (
          <Alert severity="info" sx={{ mb: 1 }}>
            Querying <strong>{queryMeta.name}</strong> ({queryMeta.row_count} rows,{' '}
            {queryMeta.sample_rows_shown} sampled) | Mode: {queryMode}
          </Alert>
        )}

        {queryStreaming && <LinearProgress sx={{ mb: 1 }} />}

        {queryAnswer && (
          <Paper
            ref={answerRef}
            sx={{
              p: 2, maxHeight: 500, overflow: 'auto',
              bgcolor: 'grey.900', color: 'grey.100',
              fontFamily: 'monospace', fontSize: 13, whiteSpace: 'pre-wrap',
              borderRadius: 2,
            }}
          >
            {queryAnswer}
          </Paper>
        )}

        {queryDone && (
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Chip label={`${queryDone.tokens} tokens`} size="small" variant="outlined" />
            <Chip label={fmtMs(queryDone.elapsed_ms)} size="small" variant="outlined" />
            <Chip label={queryDone.model} size="small" />
            <Chip label={queryDone.node} size="small" color={queryDone.node === 'wile' ? 'secondary' : 'primary'} />
          </Stack>
        )}
      </TabPanel>

      {/*  Tab 5: Jobs & Load Balancer (Phase 10)  */}
      <TabPanel value={tab} index={5}>
        {/* LB Status Cards */}
        {lbStatus && (
          <Grid container spacing={2} sx={{ mb: 2 }}>
            {Object.entries(lbStatus).map(([name, st]) => (
              <Grid size={{ xs: 12, sm: 6 }} key={name}>
                <Card variant="outlined" sx={{
                  borderLeft: 4,
                  borderLeftColor: st.healthy ? 'success.main' : 'error.main',
                }}>
                  <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="h6" sx={{ textTransform: 'capitalize' }}>{name}</Typography>
                      <Chip label={st.healthy ? 'HEALTHY' : 'DOWN'} size="small"
                        color={st.healthy ? 'success' : 'error'} />
                    </Stack>
                    <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
                      <Typography variant="body2">Active: <strong>{st.active_jobs}</strong></Typography>
                      <Typography variant="body2">Done: <strong>{st.total_completed}</strong></Typography>
                      <Typography variant="body2">Errors: <strong>{st.total_errors}</strong></Typography>
                      <Typography variant="body2">Avg: <strong>{st.avg_latency_ms.toFixed(0)}ms</strong></Typography>
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}

        {/* Job queue stats */}
        {jobStats && (
          <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
            <Chip label={`Workers: ${jobStats.active_workers}/${jobStats.workers}`} size="small" />
            <Chip label={`Queued: ${jobStats.queued}`} size="small" color="info" />
            {Object.entries(jobStats.by_status).map(([s, c]) => (
              <Chip key={s} label={`${s}: ${c}`} size="small" variant="outlined" />
            ))}
          </Stack>
        )}

        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchJobs}
            disabled={loadingJobs} size="small">Refresh</Button>
        </Stack>

        {loadingJobs && <LinearProgress sx={{ mb: 1 }} />}

        {jobs.length === 0 && !loadingJobs ? (
          <Alert severity="info">No jobs yet. Jobs appear here when you trigger triage, profiling, reports, anomaly detection, or data queries.</Alert>
        ) : (
          <TableContainer component={Paper} sx={{ maxHeight: 500 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Status</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Progress</TableCell>
                  <TableCell>Message</TableCell>
                  <TableCell>Time</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {jobs.map(j => (
                  <TableRow key={j.id} hover
                    sx={j.status === 'failed' ? { bgcolor: 'rgba(244,63,94,0.06)' }
                      : j.status === 'running' ? { bgcolor: 'rgba(59,130,246,0.06)' } : {}}>
                    <TableCell>
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        {statusIcon(j.status)}
                        <Typography variant="caption">{j.status}</Typography>
                      </Stack>
                    </TableCell>
                    <TableCell><Chip label={j.job_type} size="small" variant="outlined" /></TableCell>
                    <TableCell>
                      {j.status === 'running' ? (
                        <LinearProgress variant="determinate" value={j.progress}
                          sx={{ width: 80, height: 6, borderRadius: 3 }} />
                      ) : j.status === 'completed' ? (
                        <Typography variant="caption" color="success.main">100%</Typography>
                      ) : null}
                    </TableCell>
                    <TableCell sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      <Typography variant="caption">{j.error || j.message}</Typography>
                    </TableCell>
                    <TableCell><Typography variant="caption">{fmtMs(j.elapsed_ms)}</Typography></TableCell>
                    <TableCell><Typography variant="caption">{fmtTime(j.created_at)}</Typography></TableCell>
                    <TableCell>
                      {(j.status === 'queued' || j.status === 'running') && (
                        <IconButton size="small" color="error" onClick={() => doCancelJob(j.id)}>
                          <CancelIcon fontSize="small" />
                        </IconButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </TabPanel>
    </Box>
  );
}