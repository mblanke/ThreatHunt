from pathlib import Path
cfg=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/config.py')
t=cfg.read_text(encoding='utf-8')
if 'NETWORK_INVENTORY_MAX_ROWS_PER_DATASET' not in t:
    t=t.replace(
'''    NETWORK_SUBGRAPH_MAX_EDGES: int = Field(
        default=3000, description="Hard cap for edges returned by network subgraph endpoint"
    )
''',
'''    NETWORK_SUBGRAPH_MAX_EDGES: int = Field(
        default=3000, description="Hard cap for edges returned by network subgraph endpoint"
    )
    NETWORK_INVENTORY_MAX_ROWS_PER_DATASET: int = Field(
        default=200000,
        description="Row budget per dataset when building host inventory (0 = unlimited)",
    )
''')
cfg.write_text(t,encoding='utf-8')

p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/host_inventory.py')
t=p.read_text(encoding='utf-8')
if 'from app.config import settings' not in t:
    t=t.replace('from app.db.models import Dataset, DatasetRow\n','from app.db.models import Dataset, DatasetRow\nfrom app.config import settings\n')

t=t.replace('        batch_size = 5000\n        last_row_index = -1\n        while True:\n',
            '        batch_size = 10000\n        max_rows_per_dataset = max(0, int(settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET))\n        rows_scanned_this_dataset = 0\n        sampled_dataset = False\n        last_row_index = -1\n        while True:\n')

t=t.replace('            for ro in rows:\n                data = ro.data or {}\n                total_rows += 1\n\n',
            '            for ro in rows:\n                if max_rows_per_dataset and rows_scanned_this_dataset >= max_rows_per_dataset:\n                    sampled_dataset = True\n                    break\n\n                data = ro.data or {}\n                total_rows += 1\n                rows_scanned_this_dataset += 1\n\n')

t=t.replace('            last_row_index = rows[-1].row_index\n            if len(rows) < batch_size:\n                break\n',
            '            if sampled_dataset:\n                logger.info(\n                    "Host inventory row budget reached for dataset %s (%d rows)",\n                    ds.id,\n                    rows_scanned_this_dataset,\n                )\n                break\n\n            last_row_index = rows[-1].row_index\n            if len(rows) < batch_size:\n                break\n')

t=t.replace('    return {\n        "hosts": host_list,\n        "connections": conn_list,\n        "stats": {\n            "total_hosts": len(host_list),\n            "total_datasets_scanned": len(all_datasets),\n            "datasets_with_hosts": ds_with_hosts,\n            "total_rows_scanned": total_rows,\n            "hosts_with_ips": sum(1 for h in host_list if h[\'ips\']),\n            "hosts_with_users": sum(1 for h in host_list if h[\'users\']),\n        },\n    }\n',
            '    sampled = settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET > 0\n\n    return {\n        "hosts": host_list,\n        "connections": conn_list,\n        "stats": {\n            "total_hosts": len(host_list),\n            "total_datasets_scanned": len(all_datasets),\n            "datasets_with_hosts": ds_with_hosts,\n            "total_rows_scanned": total_rows,\n            "hosts_with_ips": sum(1 for h in host_list if h[\'ips\']),\n            "hosts_with_users": sum(1 for h in host_list if h[\'users\']),\n            "row_budget_per_dataset": settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET,\n            "sampled_mode": sampled,\n        },\n    }\n')

p.write_text(t,encoding='utf-8')
print('patched backend inventory performance settings')
