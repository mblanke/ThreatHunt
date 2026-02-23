from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/api/routes/keywords.py')
t=p.read_text(encoding='utf-8')
old='''    if can_use_cache:
        themes = await scanner._load_themes(body.theme_ids)
        allowed_theme_names = {t.name for t in themes}
        keywords_scanned = sum(len(theme.keywords) for theme in themes)

        cached_entries: list[dict] = []
        missing: list[str] = []
        for dataset_id in (body.dataset_ids or []):
            entry = keyword_scan_cache.get(dataset_id)
            if not entry:
                missing.append(dataset_id)
                continue
            cached_entries.append({"result": entry.result, "built_at": entry.built_at})

        if not missing and cached_entries:
            merged = _merge_cached_results(cached_entries, allowed_theme_names if body.theme_ids else None)
            return {
                "total_hits": merged["total_hits"],
                "hits": merged["hits"],
                "themes_scanned": len(themes),
                "keywords_scanned": keywords_scanned,
                "rows_scanned": merged["rows_scanned"],
                "cache_used": True,
                "cache_status": "hit",
                "cached_at": merged["cached_at"],
            }
'''
new='''    if can_use_cache:
        themes = await scanner._load_themes(body.theme_ids)
        allowed_theme_names = {t.name for t in themes}
        keywords_scanned = sum(len(theme.keywords) for theme in themes)

        cached_entries: list[dict] = []
        missing: list[str] = []
        for dataset_id in (body.dataset_ids or []):
            entry = keyword_scan_cache.get(dataset_id)
            if not entry:
                missing.append(dataset_id)
                continue
            cached_entries.append({"result": entry.result, "built_at": entry.built_at})

        if not missing and cached_entries:
            merged = _merge_cached_results(cached_entries, allowed_theme_names if body.theme_ids else None)
            return {
                "total_hits": merged["total_hits"],
                "hits": merged["hits"],
                "themes_scanned": len(themes),
                "keywords_scanned": keywords_scanned,
                "rows_scanned": merged["rows_scanned"],
                "cache_used": True,
                "cache_status": "hit",
                "cached_at": merged["cached_at"],
            }

        if missing:
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
if old not in t:
    raise SystemExit('cache block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('updated keyword /scan to use partial cache + scan missing datasets only')
