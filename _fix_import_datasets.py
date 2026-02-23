from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/api/routes/datasets.py')
t=p.read_text(encoding='utf-8')
if 'from app.db.models import ProcessingTask' not in t:
    t=t.replace('from app.db import get_db\n', 'from app.db import get_db\nfrom app.db.models import ProcessingTask\n')
p.write_text(t, encoding='utf-8')
print('added ProcessingTask import')
