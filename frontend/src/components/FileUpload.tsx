/**
 * FileUpload — multi-file drag-and-drop CSV upload with per-file progress bars.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  Box, Typography, Paper, Stack, Chip, LinearProgress,
  Select, MenuItem, FormControl, InputLabel, IconButton, Tooltip,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import ClearIcon from '@mui/icons-material/Clear';
import { useSnackbar } from 'notistack';
import { datasets, hunts, type UploadResult, type Hunt, type HuntProgress } from '../api/client';

interface FileJob {
  file: File;
  status: 'queued' | 'uploading' | 'done' | 'error';
  progress: number;       // 0–100
  result?: UploadResult;
  error?: string;
}

export default function FileUpload() {
  const { enqueueSnackbar } = useSnackbar();
  const [dragOver, setDragOver] = useState(false);
  const [jobs, setJobs] = useState<FileJob[]>([]);
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [huntId, setHuntId] = useState('');
  const [huntProgress, setHuntProgress] = useState<HuntProgress | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const busyRef = useRef(false);

  React.useEffect(() => {
    hunts.list(0, 100).then(r => setHuntList(r.hunts)).catch(() => {});
  }, []);

  useEffect(() => {
    let timer: any = null;
    let cancelled = false;

    const pull = async () => {
      if (!huntId) {
        if (!cancelled) setHuntProgress(null);
        return;
      }
      try {
        const p = await hunts.progress(huntId);
        if (!cancelled) setHuntProgress(p);
      } catch {
        if (!cancelled) setHuntProgress(null);
      }
    };

    pull();
    if (huntId) timer = setInterval(pull, 2000);
    return () => { cancelled = true; if (timer) clearInterval(timer); };
  }, [huntId, jobs.length]);

  // Process the queue sequentially
  const processQueue = useCallback(async (queue: FileJob[]) => {
    if (busyRef.current) return;
    busyRef.current = true;

    for (let i = 0; i < queue.length; i++) {
      if (queue[i].status !== 'queued') continue;

      // Mark uploading
      setJobs(prev => prev.map((j, idx) =>
        idx === i ? { ...j, status: 'uploading' as const, progress: 0 } : j
      ));

      try {
        const result = await datasets.uploadWithProgress(
          queue[i].file,
          huntId || undefined,
          (pct) => {
            setJobs(prev => prev.map((j, idx) =>
              idx === i ? { ...j, progress: pct } : j
            ));
          },
        );
        setJobs(prev => prev.map((j, idx) =>
          idx === i ? { ...j, status: 'done' as const, progress: 100, result } : j
        ));
        enqueueSnackbar(
          `${queue[i].file.name}: ${result.row_count} rows, ${result.columns.length} columns`,
          { variant: 'success' },
        );
      } catch (e: any) {
        setJobs(prev => prev.map((j, idx) =>
          idx === i ? { ...j, status: 'error' as const, error: e.message } : j
        ));
        enqueueSnackbar(`${queue[i].file.name}: ${e.message}`, { variant: 'error' });
      }
    }
    busyRef.current = false;
  }, [huntId, enqueueSnackbar]);

  const enqueueFiles = useCallback((files: FileList | File[]) => {
    const newJobs: FileJob[] = Array.from(files).map(file => ({
      file, status: 'queued' as const, progress: 0,
    }));
    setJobs(prev => {
      const merged = [...prev, ...newJobs];
      // kick off processing with the full merged list
      setTimeout(() => processQueue(merged), 0);
      return merged;
    });
  }, [processQueue]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    if (e.dataTransfer.files.length > 0) enqueueFiles(e.dataTransfer.files);
  }, [enqueueFiles]);

  const onFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      enqueueFiles(e.target.files);
      e.target.value = '';  // reset so same file can be re-selected
    }
  }, [enqueueFiles]);

  const clearCompleted = useCallback(() => {
    setJobs(prev => prev.filter(j => j.status === 'queued' || j.status === 'uploading'));
  }, []);

  const overallDone = jobs.filter(j => j.status === 'done').length;
  const overallErr = jobs.filter(j => j.status === 'error').length;
  const overallTotal = jobs.length;

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Upload Datasets</Typography>

      {/* Hunt association */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <FormControl size="small" sx={{ minWidth: 300 }}>
          <InputLabel>Associate with Hunt (optional)</InputLabel>
          <Select label="Associate with Hunt (optional)" value={huntId}
            onChange={e => setHuntId(e.target.value)}>
            <MenuItem value="">None</MenuItem>
            {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
          </Select>
        </FormControl>
      </Paper>

      {/* Drop zone */}
      <Paper
        sx={{
          p: 6, textAlign: 'center', cursor: 'pointer',
          border: '2px dashed',
          borderColor: dragOver ? 'primary.main' : 'divider',
          bgcolor: dragOver ? 'action.hover' : 'background.paper',
          transition: 'all 0.2s',
        }}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
      >
        <input ref={fileRef} type="file" accept=".csv,.tsv,.txt" hidden multiple onChange={onFileChange} />
        <CloudUploadIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 1 }} />
        <Typography variant="h6" color="text.secondary">
          Drag & drop CSV / TSV files here
        </Typography>
        <Typography variant="body2" color="text.secondary">
          or click to browse — multiple files supported — max 100 MB each
        </Typography>
      </Paper>

      {/* Overall progress summary */}
      {overallTotal > 0 && (
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            {overallDone + overallErr} / {overallTotal} files processed
            {overallErr > 0 && ` (${overallErr} failed)`}
          </Typography>
          <Box sx={{ flexGrow: 1 }} />
          {overallDone + overallErr === overallTotal && overallTotal > 0 && (
            <Tooltip title="Clear completed">
              <IconButton size="small" onClick={clearCompleted}><ClearIcon fontSize="small" /></IconButton>
            </Tooltip>
          )}
        </Stack>
      )}

      {huntId && huntProgress && (
        <Paper sx={{ p: 1.5, mt: 1.5 }}>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.8 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              Master Processing Progress
            </Typography>
            <Chip
              size="small"
              label={huntProgress.status.toUpperCase()}
              color={huntProgress.status === 'ready' ? 'success' : huntProgress.status === 'processing' ? 'warning' : 'default'}
              variant="outlined"
            />
            <Box sx={{ flexGrow: 1 }} />
            <Typography variant="caption" color="text.secondary">
              {huntProgress.progress_percent.toFixed(1)}%
            </Typography>
          </Stack>
          <LinearProgress
            variant="determinate"
            value={Math.max(0, Math.min(100, huntProgress.progress_percent))}
            sx={{ height: 8, borderRadius: 4 }}
          />
          <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
            <Chip size="small" label={`Datasets ${huntProgress.dataset_completed}/${huntProgress.dataset_total}`} variant="outlined" />
            <Chip size="small" label={`Active jobs ${huntProgress.active_jobs}`} variant="outlined" />
            <Chip size="small" label={`Queued jobs ${huntProgress.queued_jobs}`} variant="outlined" />
            <Chip size="small" label={`Network ${huntProgress.network_status}`} variant="outlined" />
          </Stack>
        </Paper>
      )}

      {/* Per-file progress list */}
      {jobs.map((job, i) => (
        <Paper key={`${job.file.name}-${i}`} sx={{ p: 2, mt: 1 }}>
          <Stack direction="row" alignItems="center" spacing={1.5}>
            {job.status === 'done' && <CheckCircleIcon color="success" fontSize="small" />}
            {job.status === 'error' && <ErrorIcon color="error" fontSize="small" />}
            {(job.status === 'queued' || job.status === 'uploading') && (
              <Box sx={{ width: 20, height: 20 }} />
            )}
            <Box sx={{ minWidth: 0, flexGrow: 1 }}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>
                  {job.file.name}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  ({(job.file.size / 1024 / 1024).toFixed(1)} MB)
                </Typography>
                {job.status === 'queued' && (
                  <Chip label="Queued" size="small" variant="outlined" />
                )}
              </Stack>

              {/* Progress bar */}
              {job.status === 'uploading' && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                  <LinearProgress
                    variant="determinate" value={job.progress}
                    sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
                  />
                  <Typography variant="caption" sx={{ minWidth: 36 }}>
                    {job.progress}%
                  </Typography>
                </Box>
              )}

              {/* Error */}
              {job.status === 'error' && (
                <Typography variant="caption" color="error">{job.error}</Typography>
              )}

              {/* Success details */}
              {job.status === 'done' && job.result && (
                <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mt: 0.5 }}>
                  <Chip label={`${job.result.row_count} rows`} size="small" color="primary" />
                  <Chip label={`${job.result.columns.length} cols`} size="small" />
                  {Object.keys(job.result.ioc_columns).length > 0 && (
                    <Chip label={`${Object.keys(job.result.ioc_columns).length} IOC cols`}
                      size="small" color="warning" />
                  )}
                </Stack>
              )}
            </Box>
          </Stack>
        </Paper>
      ))}
    </Box>
  );
}
