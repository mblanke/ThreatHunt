from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/host_inventory.py')
t=p.read_text(encoding='utf-8')
needle='            "hosts_with_users": sum(1 for h in host_list if h[\'users\']),\n'
if '"row_budget_per_dataset"' not in t:
    if needle not in t:
        raise SystemExit('needle not found')
    t=t.replace(needle, needle + '            "row_budget_per_dataset": settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET,\n            "sampled_mode": settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET > 0,\n')
p.write_text(t,encoding='utf-8')
print('inserted inventory budget stats lines')
