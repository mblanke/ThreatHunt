from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/api/client.ts')
t=p.read_text(encoding='utf-8')
old='''export interface ScanHit {
  theme_name: string; theme_color: string; keyword: string;
  source_type: string; source_id: string | number; field: string;
  matched_value: string; row_index: number | null; dataset_name: string | null;
}
'''
new='''export interface ScanHit {
  theme_name: string; theme_color: string; keyword: string;
  source_type: string; source_id: string | number; field: string;
  matched_value: string; row_index: number | null; dataset_name: string | null;
  hostname?: string | null; username?: string | null;
}
'''
if old not in t:
    raise SystemExit('frontend ScanHit interface block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('extended frontend ScanHit type with hostname+username')
