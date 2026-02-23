from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/AUPScanner.tsx')
t=p.read_text(encoding='utf-8')
t=t.replace('  const [scanHunts, setScanHunts] = useState(true);','  const [scanHunts, setScanHunts] = useState(false);')
t=t.replace('  const [scanAnnotations, setScanAnnotations] = useState(true);','  const [scanAnnotations, setScanAnnotations] = useState(false);')
t=t.replace('  const [scanMessages, setScanMessages] = useState(true);','  const [scanMessages, setScanMessages] = useState(false);')
t=t.replace('        scan_messages: scanMessages,\n      });','        scan_messages: scanMessages,\n        prefer_cache: true,\n      });')
# add cache chip in summary alert
old='''          {scanResult && (
            <Alert severity={scanResult.total_hits > 0 ? 'warning' : 'success'} sx={{ py: 0.5 }}>
              <strong>{scanResult.total_hits}</strong> hits across{' '}
              <strong>{scanResult.rows_scanned}</strong> rows |{' '}
              {scanResult.themes_scanned} themes, {scanResult.keywords_scanned} keywords scanned
            </Alert>
          )}
'''
new='''          {scanResult && (
            <Alert severity={scanResult.total_hits > 0 ? 'warning' : 'success'} sx={{ py: 0.5 }}>
              <strong>{scanResult.total_hits}</strong> hits across{' '}
              <strong>{scanResult.rows_scanned}</strong> rows |{' '}
              {scanResult.themes_scanned} themes, {scanResult.keywords_scanned} keywords scanned
              {scanResult.cache_status && (
                <Chip
                  size="small"
                  label={scanResult.cache_status === 'hit' ? 'Cached' : 'Live'}
                  sx={{ ml: 1, height: 20 }}
                  color={scanResult.cache_status === 'hit' ? 'success' : 'default'}
                  variant="outlined"
                />
              )}
            </Alert>
          )}
'''
if old in t:
    t=t.replace(old,new)
else:
    print('warning: summary block not replaced')

p.write_text(t,encoding='utf-8')
print('updated AUPScanner.tsx')
