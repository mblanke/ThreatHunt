from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/AUPScanner.tsx')
t=p.read_text(encoding='utf-8')
old='''const RESULT_COLUMNS: GridColDef[] = [
  {
    field: 'theme_name', headerName: 'Theme', width: 140,
    renderCell: (params) => (
      <Chip label={params.value} size="small"
        sx={{ bgcolor: params.row.theme_color, color: '#fff', fontWeight: 600 }} />
    ),
  },
  { field: 'keyword', headerName: 'Keyword', width: 140 },
  { field: 'source_type', headerName: 'Source', width: 120 },
  { field: 'dataset_name', headerName: 'Dataset', width: 150 },
  { field: 'field', headerName: 'Field', width: 130 },
  { field: 'matched_value', headerName: 'Matched Value', flex: 1, minWidth: 200 },
  { field: 'row_index', headerName: 'Row #', width: 80, type: 'number' },
];
'''
new='''const RESULT_COLUMNS: GridColDef[] = [
  {
    field: 'theme_name', headerName: 'Theme', width: 140,
    renderCell: (params) => (
      <Chip label={params.value} size="small"
        sx={{ bgcolor: params.row.theme_color, color: '#fff', fontWeight: 600 }} />
    ),
  },
  { field: 'keyword', headerName: 'Keyword', width: 140 },
  { field: 'dataset_name', headerName: 'Dataset', width: 170 },
  { field: 'hostname', headerName: 'Hostname', width: 170, valueGetter: (v, row) => row.hostname || '' },
  { field: 'username', headerName: 'User', width: 160, valueGetter: (v, row) => row.username || '' },
  { field: 'matched_value', headerName: 'Matched Value', flex: 1, minWidth: 220 },
  { field: 'field', headerName: 'Field', width: 130 },
  { field: 'source_type', headerName: 'Source', width: 120 },
  { field: 'row_index', headerName: 'Row #', width: 90, type: 'number' },
];
'''
if old not in t:
    raise SystemExit('RESULT_COLUMNS block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('updated AUP results grid columns with dataset/hostname/user/matched value focus')
