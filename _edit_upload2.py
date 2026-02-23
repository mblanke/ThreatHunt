from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/FileUpload.tsx')
t=p.read_text(encoding='utf-8')
marker='''      {/* Per-file progress list */}
'''
add='''      {huntId && huntProgress && (
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

'''
if marker not in t:
    raise SystemExit('marker not found')
t=t.replace(marker, add+marker)
p.write_text(t,encoding='utf-8')
print('inserted master progress block')
