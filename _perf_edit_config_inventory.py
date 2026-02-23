from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/config.py')
t=p.read_text(encoding='utf-8')
old='''    NETWORK_INVENTORY_MAX_ROWS_PER_DATASET: int = Field(
        default=25000,
        description="Row budget per dataset when building host inventory (0 = unlimited)",
    )
'''
new='''    NETWORK_INVENTORY_MAX_ROWS_PER_DATASET: int = Field(
        default=5000,
        description="Row budget per dataset when building host inventory (0 = unlimited)",
    )
    NETWORK_INVENTORY_MAX_TOTAL_ROWS: int = Field(
        default=120000,
        description="Global row budget across all datasets for host inventory build (0 = unlimited)",
    )
    NETWORK_INVENTORY_MAX_CONNECTIONS: int = Field(
        default=120000,
        description="Max unique connection tuples retained during host inventory build",
    )
'''
if old not in t:
    raise SystemExit('network inventory block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('updated network inventory budgets in config')
