from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/api/routes/keywords.py')
t=p.read_text(encoding='utf-8')

# add fast guard against unscoped global dataset scans
insert_after='''async def run_scan(body: ScanRequest, db: AsyncSession = Depends(get_db)):\n    scanner = KeywordScanner(db)\n\n'''
if insert_after not in t:
    raise SystemExit('run_scan header block not found')
if 'Select at least one dataset' not in t:
    guard='''    if not body.dataset_ids and not body.scan_hunts and not body.scan_annotations and not body.scan_messages:\n        raise HTTPException(400, "Select at least one dataset or enable additional sources (hunts/annotations/messages)")\n\n'''
    t=t.replace(insert_after, insert_after+guard)

old='''        if missing:
            missing_entries: list[dict] = []
            for dataset_id in missing:
                partial = await scanner.scan(dataset_ids=[dataset_id], theme_ids=body.theme_ids)
                keyword_scan_cache.put(dataset_id, partial)
                missing_entries.append({"result": partial, "built_at": None})

            merged = _merge_cached_results(
                cached_entries + missing_entries,
                allowed_theme_names if body.theme_ids else None,
            )
            return {
                "total_hits": merged["total_hits"],
                "hits": merged["hits"],
                "themes_scanned": len(themes),
                "keywords_scanned": keywords_scanned,
                "rows_scanned": merged["rows_scanned"],
                "cache_used": len(cached_entries) > 0,
                "cache_status": "partial" if cached_entries else "miss",
                "cached_at": merged["cached_at"],
            }
'''
new='''        if missing:
            partial = await scanner.scan(dataset_ids=missing, theme_ids=body.theme_ids)
            merged = _merge_cached_results(
                cached_entries + [{"result": partial, "built_at": None}],
                allowed_theme_names if body.theme_ids else None,
            )
            return {
                "total_hits": merged["total_hits"],
                "hits": merged["hits"],
                "themes_scanned": len(themes),
                "keywords_scanned": keywords_scanned,
                "rows_scanned": merged["rows_scanned"],
                "cache_used": len(cached_entries) > 0,
                "cache_status": "partial" if cached_entries else "miss",
                "cached_at": merged["cached_at"],
            }
'''
if old not in t:
    raise SystemExit('partial-cache missing block not found')
t=t.replace(old,new)

p.write_text(t,encoding='utf-8')
print('hardened keywords scan scope + optimized missing-cache path')
