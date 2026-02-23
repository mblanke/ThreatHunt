from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/config.py')
t=p.read_text(encoding='utf-8')
old='''    SCANNER_MAX_ROWS_PER_SCAN: int = Field(
        default=300000,
        description="Global row budget for a single AUP scan request (0 = unlimited)",
    )
'''
new='''    SCANNER_MAX_ROWS_PER_SCAN: int = Field(
        default=120000,
        description="Global row budget for a single AUP scan request (0 = unlimited)",
    )
'''
if old not in t:
    raise SystemExit('SCANNER_MAX_ROWS_PER_SCAN block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('reduced SCANNER_MAX_ROWS_PER_SCAN default to 120000')
