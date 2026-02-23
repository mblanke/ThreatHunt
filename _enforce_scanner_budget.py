from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/scanner.py')
t=p.read_text(encoding='utf-8')
if 'from app.config import settings' not in t:
    t=t.replace('from sqlalchemy.ext.asyncio import AsyncSession\n','from sqlalchemy.ext.asyncio import AsyncSession\n\nfrom app.config import settings\n')

old='''        import asyncio

        for ds_id, ds_name in ds_map.items():
            last_id = 0
            while True:
'''
new='''        import asyncio

        max_rows = max(0, int(settings.SCANNER_MAX_ROWS_PER_SCAN))
        budget_reached = False

        for ds_id, ds_name in ds_map.items():
            if max_rows and result.rows_scanned >= max_rows:
                budget_reached = True
                break

            last_id = 0
            while True:
                if max_rows and result.rows_scanned >= max_rows:
                    budget_reached = True
                    break
'''
if old not in t:
    raise SystemExit('scanner loop block not found')
t=t.replace(old,new)

old2='''                if len(rows) < BATCH_SIZE:
                    break

'''
new2='''                if len(rows) < BATCH_SIZE:
                    break

            if budget_reached:
                break

        if budget_reached:
            logger.warning(
                "AUP scan row budget reached (%d rows). Returning partial results.",
                result.rows_scanned,
            )

'''
if old2 not in t:
    raise SystemExit('scanner break block not found')
t=t.replace(old2,new2,1)

p.write_text(t,encoding='utf-8')
print('added scanner global row budget enforcement')
