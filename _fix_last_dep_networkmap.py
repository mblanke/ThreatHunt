from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/NetworkMap.tsx')
t=p.read_text(encoding='utf-8')
count=t.count('}, [canvasSize]);')
if count:
    t=t.replace('}, [canvasSize]);','}, [canvasSize, labelMode]);')
# In case formatter created spaced variant
t=t.replace('}, [canvasSize ]);','}, [canvasSize, labelMode]);')
p.write_text(t,encoding='utf-8')
print('patched remaining canvasSize callback deps:', count)
