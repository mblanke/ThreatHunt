from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/AUPScanner.tsx')
t=p.read_text(encoding='utf-8')

# default selection when hunt changes: first 3 datasets instead of all
old='''    datasets.list(0, 500, selectedHuntId).then(res => {
      if (cancelled) return;
      setDsList(res.datasets);
      setSelectedDs(new Set(res.datasets.map(d => d.id)));
    }).catch(() => {});
'''
new='''    datasets.list(0, 500, selectedHuntId).then(res => {
      if (cancelled) return;
      setDsList(res.datasets);
      setSelectedDs(new Set(res.datasets.slice(0, 3).map(d => d.id)));
    }).catch(() => {});
'''
if old not in t:
    raise SystemExit('hunt-change dataset init block not found')
t=t.replace(old,new)

# insert dataset scope multi-select under hunt info
anchor='''                {!selectedHuntId && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                    All datasets will be scanned if no hunt is selected
                  </Typography>
                )}
              </Box>

              {/* Theme selector */}
'''
insert='''                {!selectedHuntId && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                    Select a hunt to enable scoped scanning
                  </Typography>
                )}

                <FormControl size="small" fullWidth sx={{ mt: 1.2 }} disabled={!selectedHuntId || dsList.length === 0}>
                  <InputLabel id="aup-dataset-label">Datasets</InputLabel>
                  <Select
                    labelId="aup-dataset-label"
                    multiple
                    value={Array.from(selectedDs)}
                    label="Datasets"
                    renderValue={(selected) => `${(selected as string[]).length} selected`}
                    onChange={(e) => setSelectedDs(new Set(e.target.value as string[]))}
                  >
                    {dsList.map(d => (
                      <MenuItem key={d.id} value={d.id}>
                        <Checkbox size="small" checked={selectedDs.has(d.id)} />
                        <Typography variant="body2" sx={{ ml: 0.5 }}>
                          {d.name} ({d.row_count.toLocaleString()} rows)
                        </Typography>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                {selectedHuntId && dsList.length > 0 && (
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <Button size="small" onClick={() => setSelectedDs(new Set(dsList.slice(0, 3).map(d => d.id)))}>Top 3</Button>
                    <Button size="small" onClick={() => setSelectedDs(new Set(dsList.map(d => d.id)))}>All</Button>
                    <Button size="small" onClick={() => setSelectedDs(new Set())}>Clear</Button>
                  </Stack>
                )}
              </Box>

              {/* Theme selector */}
'''
if anchor not in t:
    raise SystemExit('dataset scope anchor not found')
t=t.replace(anchor,insert)

p.write_text(t,encoding='utf-8')
print('added AUP dataset multi-select scoping and safer defaults')
