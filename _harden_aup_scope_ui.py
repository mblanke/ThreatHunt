from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/AUPScanner.tsx')
t=p.read_text(encoding='utf-8')

# Auto-select first hunt with datasets after load
old='''      const [tRes, hRes] = await Promise.all([
        keywords.listThemes(),
        hunts.list(0, 200),
      ]);
      setThemes(tRes.themes);
      setHuntList(hRes.hunts);
'''
new='''      const [tRes, hRes] = await Promise.all([
        keywords.listThemes(),
        hunts.list(0, 200),
      ]);
      setThemes(tRes.themes);
      setHuntList(hRes.hunts);
      if (!selectedHuntId && hRes.hunts.length > 0) {
        const best = hRes.hunts.find(h => h.dataset_count > 0) || hRes.hunts[0];
        setSelectedHuntId(best.id);
      }
'''
if old not in t:
    raise SystemExit('loadData block not found')
t=t.replace(old,new)

# Guard runScan
old2='''  const runScan = useCallback(async () => {
    setScanning(true);
    setScanResult(null);
    try {
'''
new2='''  const runScan = useCallback(async () => {
    if (!selectedHuntId) {
      enqueueSnackbar('Please select a hunt before running AUP scan', { variant: 'warning' });
      return;
    }
    if (selectedDs.size === 0) {
      enqueueSnackbar('No datasets selected for this hunt', { variant: 'warning' });
      return;
    }

    setScanning(true);
    setScanResult(null);
    try {
'''
if old2 not in t:
    raise SystemExit('runScan header not found')
t=t.replace(old2,new2)

# update loadData deps
old3='''  }, [enqueueSnackbar]);
'''
new3='''  }, [enqueueSnackbar, selectedHuntId]);
'''
if old3 not in t:
    raise SystemExit('loadData deps not found')
t=t.replace(old3,new3,1)

# disable button if no hunt or no datasets
old4='''                  onClick={runScan} disabled={scanning}
'''
new4='''                  onClick={runScan} disabled={scanning || !selectedHuntId || selectedDs.size === 0}
'''
if old4 not in t:
    raise SystemExit('scan button props not found')
t=t.replace(old4,new4)

p.write_text(t,encoding='utf-8')
print('hardened AUPScanner to require explicit hunt/dataset scope')
