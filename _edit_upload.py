from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/FileUpload.tsx')
t=p.read_text(encoding='utf-8')
# import useEffect
t=t.replace("import React, { useState, useCallback, useRef } from 'react';","import React, { useState, useCallback, useRef, useEffect } from 'react';")
# import HuntProgress type
t=t.replace("import { datasets, hunts, type UploadResult, type Hunt } from '../api/client';","import { datasets, hunts, type UploadResult, type Hunt, type HuntProgress } from '../api/client';")
# add state
if 'const [huntProgress, setHuntProgress]' not in t:
    t=t.replace("  const [huntList, setHuntList] = useState<Hunt[]>([]);\n  const [huntId, setHuntId] = useState('');","  const [huntList, setHuntList] = useState<Hunt[]>([]);\n  const [huntId, setHuntId] = useState('');\n  const [huntProgress, setHuntProgress] = useState<HuntProgress | null>(null);")
# add polling effect after hunts list effect
marker="  React.useEffect(() => {\n    hunts.list(0, 100).then(r => setHuntList(r.hunts)).catch(() => {});\n  }, []);\n"
if marker in t and 'setInterval' not in t.split(marker,1)[1][:500]:
    add='''\n  useEffect(() => {\n    let timer: any = null;\n    let cancelled = false;\n\n    const pull = async () => {\n      if (!huntId) {\n        if (!cancelled) setHuntProgress(null);\n        return;\n      }\n      try {\n        const p = await hunts.progress(huntId);\n        if (!cancelled) setHuntProgress(p);\n      } catch {\n        if (!cancelled) setHuntProgress(null);\n      }\n    };\n\n    pull();\n    if (huntId) timer = setInterval(pull, 2000);\n    return () => { cancelled = true; if (timer) clearInterval(timer); };\n  }, [huntId, jobs.length]);\n'''
    t=t.replace(marker, marker+add)

# insert master progress UI after overall summary
insert_after='''      {overallTotal > 0 && (\n        <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 2 }}>\n          <Typography variant="body2" color="text.secondary">\n            {overallDone + overallErr} / {overallTotal} files processed\n            {overallErr > 0 && ` ({overallErr} failed)`}\n          </Typography>\n          <Box sx={{ flexGrow: 1 }} />\n          {overallDone + overallErr === overallTotal && overallTotal > 0 && (\n            <Tooltip title="Clear completed">\n              <IconButton size="small" onClick={clearCompleted}><ClearIcon fontSize="small" /></IconButton>\n            </Tooltip>\n          )}\n        </Stack>\n      )}\n'''
add_block='''\n      {huntId && huntProgress && (\n        <Paper sx={{ p: 1.5, mt: 1.5 }}>\n          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.8 }}>\n            <Typography variant="body2" sx={{ fontWeight: 600 }}>\n              Master Processing Progress\n            </Typography>\n            <Chip\n              size="small"\n              label={huntProgress.status.toUpperCase()}\n              color={huntProgress.status === 'ready' ? 'success' : huntProgress.status === 'processing' ? 'warning' : 'default'}\n              variant="outlined"\n            />\n            <Box sx={{ flexGrow: 1 }} />\n            <Typography variant="caption" color="text.secondary">\n              {huntProgress.progress_percent.toFixed(1)}%\n            </Typography>\n          </Stack>\n          <LinearProgress\n            variant="determinate"\n            value={Math.max(0, Math.min(100, huntProgress.progress_percent))}\n            sx={{ height: 8, borderRadius: 4 }}\n          />\n          <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>\n            <Chip size="small" label={`Datasets ${huntProgress.dataset_completed}/${huntProgress.dataset_total}`} variant="outlined" />\n            <Chip size="small" label={`Active jobs ${huntProgress.active_jobs}`} variant="outlined" />\n            <Chip size="small" label={`Queued jobs ${huntProgress.queued_jobs}`} variant="outlined" />\n            <Chip size="small" label={`Network ${huntProgress.network_status}`} variant="outlined" />\n          </Stack>\n        </Paper>\n      )}\n'''
if insert_after in t:
    t=t.replace(insert_after, insert_after+add_block)
else:
    print('warning: summary block not found')

p.write_text(t,encoding='utf-8')
print('updated FileUpload.tsx')
