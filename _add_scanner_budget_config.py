from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/config.py')
t=p.read_text(encoding='utf-8')
old='''    # -- Scanner settings -----------------------------------------------
    SCANNER_BATCH_SIZE: int = Field(default=500, description="Rows per scanner batch")
'''
new='''    # -- Scanner settings -----------------------------------------------
    SCANNER_BATCH_SIZE: int = Field(default=500, description="Rows per scanner batch")
    SCANNER_MAX_ROWS_PER_SCAN: int = Field(
        default=300000,
        description="Global row budget for a single AUP scan request (0 = unlimited)",
    )
'''
if old not in t:
    raise SystemExit('scanner settings block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('added SCANNER_MAX_ROWS_PER_SCAN config')
