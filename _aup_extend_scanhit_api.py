from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/api/routes/keywords.py')
t=p.read_text(encoding='utf-8')
old='''class ScanHit(BaseModel):
    theme_name: str
    theme_color: str
    keyword: str
    source_type: str
    source_id: str | int
    field: str
    matched_value: str
    row_index: int | None = None
    dataset_name: str | None = None
'''
new='''class ScanHit(BaseModel):
    theme_name: str
    theme_color: str
    keyword: str
    source_type: str
    source_id: str | int
    field: str
    matched_value: str
    row_index: int | None = None
    dataset_name: str | None = None
    hostname: str | None = None
    username: str | None = None
'''
if old not in t:
    raise SystemExit('ScanHit pydantic model block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('extended API ScanHit model with hostname+username')
