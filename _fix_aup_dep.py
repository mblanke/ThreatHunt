from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/AUPScanner.tsx')
t=p.read_text(encoding='utf-8')
old='''  }, [selectedDs, selectedThemes, scanHunts, scanAnnotations, scanMessages, enqueueSnackbar]);
'''
new='''  }, [selectedHuntId, selectedDs, selectedThemes, scanHunts, scanAnnotations, scanMessages, enqueueSnackbar]);
'''
if old not in t:
    raise SystemExit('runScan deps block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('fixed AUPScanner runScan dependency list')
