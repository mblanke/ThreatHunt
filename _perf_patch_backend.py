from pathlib import Path
# config updates
cfg=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/config.py')
t=cfg.read_text(encoding='utf-8')
anchor='''    NETWORK_SUBGRAPH_MAX_EDGES: int = Field(
        default=3000, description="Hard cap for edges returned by network subgraph endpoint"
    )
'''
ins='''    NETWORK_SUBGRAPH_MAX_EDGES: int = Field(
        default=3000, description="Hard cap for edges returned by network subgraph endpoint"
    )
    NETWORK_INVENTORY_MAX_ROWS_PER_DATASET: int = Field(
        default=200000,
        description="Row budget per dataset when building host inventory (0 = unlimited)",
    )
'''
if 'NETWORK_INVENTORY_MAX_ROWS_PER_DATASET' not in t:
    if anchor not in t:
        raise SystemExit('config network anchor not found')
    t=t.replace(anchor,ins)
cfg.write_text(t,encoding='utf-8')

# host inventory updates
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/host_inventory.py')
t=p.read_text(encoding='utf-8')
if 'from app.config import settings' not in t:
    t=t.replace('from app.db.models import Dataset, DatasetRow\n', 'from app.db.models import Dataset, DatasetRow\nfrom app.config import settings\n')

t=t.replace('        batch_size = 5000\n        last_row_index = -1\n        while True:\n', '        batch_size = 10000\n        max_rows_per_dataset = max(0, int(settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET))\n        rows_scanned_this_dataset = 0\n        sampled_dataset = False\n        last_row_index = -1\n        while True:\n')

old='''            for ro in rows:
                data = ro.data or {}
                total_rows += 1

                fqdn = ''
'''
new='''            for ro in rows:
                if max_rows_per_dataset and rows_scanned_this_dataset >= max_rows_per_dataset:
                    sampled_dataset = True
                    break

                data = ro.data or {}
                total_rows += 1
                rows_scanned_this_dataset += 1

                fqdn = ''
'''
if old not in t:
    raise SystemExit('row loop anchor not found')
t=t.replace(old,new)

old2='''            last_row_index = rows[-1].row_index
            if len(rows) < batch_size:
                break
'''
new2='''            if sampled_dataset:
                logger.info(
                    "Host inventory row budget reached for dataset %s (%d rows)",
                    ds.id,
                    rows_scanned_this_dataset,
                )
                break

            last_row_index = rows[-1].row_index
            if len(rows) < batch_size:
                break
'''
if old2 not in t:
    raise SystemExit('batch loop end anchor not found')
t=t.replace(old2,new2)

old3='''    return {
        "hosts": host_list,
        "connections": conn_list,
        "stats": {
            "total_hosts": len(host_list),
            "total_datasets_scanned": len(all_datasets),
            "datasets_with_hosts": ds_with_hosts,
            "total_rows_scanned": total_rows,
            "hosts_with_ips": sum(1 for h in host_list if h['ips']),
            "hosts_with_users": sum(1 for h in host_list if h['users']),
        },
    }
'''
new3='''    sampled = settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET > 0

    return {
        "hosts": host_list,
        "connections": conn_list,
        "stats": {
            "total_hosts": len(host_list),
            "total_datasets_scanned": len(all_datasets),
            "datasets_with_hosts": ds_with_hosts,
            "total_rows_scanned": total_rows,
            "hosts_with_ips": sum(1 for h in host_list if h['ips']),
            "hosts_with_users": sum(1 for h in host_list if h['users']),
            "row_budget_per_dataset": settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET,
            "sampled_mode": sampled,
        },
    }
'''
if old3 not in t:
    raise SystemExit('return stats anchor not found')
t=t.replace(old3,new3)

p.write_text(t,encoding='utf-8')
print('patched config + host inventory row budget')
