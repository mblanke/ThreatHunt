from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/components/NetworkMap.tsx')
t=p.read_text(encoding='utf-8')

# Add label selector in toolbar before refresh button
insert_after="""        <TextField
          size=\"small\"
          placeholder=\"Search hosts, IPs, users\\u2026\"
          value={search}
          onChange={e => setSearch(e.target.value)}
          sx={{ width: 220, '& .MuiInputBase-input': { py: 0.8 } }}
          slotProps={{
            input: {
              startAdornment: <SearchIcon sx={{ mr: 0.5, fontSize: 18, color: 'text.secondary' }} />,
            },
          }}
        />
"""
label_ctrl="""
        <FormControl size=\"small\" sx={{ minWidth: 150 }}>
          <InputLabel id=\"label-mode-selector\">Labels</InputLabel>
          <Select
            labelId=\"label-mode-selector\"
            value={labelMode}
            label=\"Labels\"
            onChange={e => setLabelMode(e.target.value as LabelMode)}
            sx={{ '& .MuiSelect-select': { py: 0.8 } }}
          >
            <MenuItem value=\"none\">None</MenuItem>
            <MenuItem value=\"highlight\">Selected/Search</MenuItem>
            <MenuItem value=\"all\">All</MenuItem>
          </Select>
        </FormControl>
"""
if 'label-mode-selector' not in t:
    if insert_after not in t:
        raise SystemExit('search block not found for label selector insertion')
    t=t.replace(insert_after, insert_after+label_ctrl)

# Fix useCallback dependency for startAnimLoop
old='  }, [canvasSize]);'
new='  }, [canvasSize, labelMode]);'
if old in t:
    t=t.replace(old,new,1)

p.write_text(t,encoding='utf-8')
print('inserted label selector UI and fixed callback dependency')
