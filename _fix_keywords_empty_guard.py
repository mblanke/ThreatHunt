from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/api/routes/keywords.py')
t=p.read_text(encoding='utf-8')
old='''    if not body.dataset_ids and not body.scan_hunts and not body.scan_annotations and not body.scan_messages:
        raise HTTPException(400, "Select at least one dataset or enable additional sources (hunts/annotations/messages)")

'''
new='''    if not body.dataset_ids and not body.scan_hunts and not body.scan_annotations and not body.scan_messages:
        return {
            "total_hits": 0,
            "hits": [],
            "themes_scanned": 0,
            "keywords_scanned": 0,
            "rows_scanned": 0,
            "cache_used": False,
            "cache_status": "miss",
            "cached_at": None,
        }

'''
if old not in t:
    raise SystemExit('scope guard block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('adjusted empty scan guard to return fast empty result (200)')
