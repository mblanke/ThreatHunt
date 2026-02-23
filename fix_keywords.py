import re

path = "backend/app/api/routes/keywords.py"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

# Fix POST /scan - remove dedicated session, use injected db
old1 = '    """Run AUP keyword scan across selected data sources.\n    \n    Uses a dedicated DB session separate from the request session\n    to avoid blocking other API requests on SQLite.\n    """\n    from app.db import async_session_factory\n    async with async_session_factory() as scan_db:\n        scanner = KeywordScanner(scan_db)\n        result = await scanner.scan(\n            dataset_ids=body.dataset_ids,\n            theme_ids=body.theme_ids,\n            scan_hunts=body.scan_hunts,\n            scan_annotations=body.scan_annotations,\n            scan_messages=body.scan_messages,\n        )\n    return result'

new1 = '    """Run AUP keyword scan across selected data sources."""\n    scanner = KeywordScanner(db)\n    result = await scanner.scan(\n        dataset_ids=body.dataset_ids,\n        theme_ids=body.theme_ids,\n        scan_hunts=body.scan_hunts,\n        scan_annotations=body.scan_annotations,\n        scan_messages=body.scan_messages,\n    )\n    return result'

if old1 in c:
    c = c.replace(old1, new1, 1)
    print("OK: reverted POST /scan")
else:
    print("SKIP: POST /scan not found")

# Fix GET /scan/quick
old2 = '    """Quick scan a single dataset with all enabled themes."""\n    from app.db import async_session_factory\n    async with async_session_factory() as scan_db:\n        scanner = KeywordScanner(scan_db)\n        result = await scanner.scan(dataset_ids=[dataset_id])\n    return result'

new2 = '    """Quick scan a single dataset with all enabled themes."""\n    scanner = KeywordScanner(db)\n    result = await scanner.scan(dataset_ids=[dataset_id])\n    return result'

if old2 in c:
    c = c.replace(old2, new2, 1)
    print("OK: reverted GET /scan/quick")
else:
    print("SKIP: GET /scan/quick not found")

with open(path, "w", encoding="utf-8") as f:
    f.write(c)