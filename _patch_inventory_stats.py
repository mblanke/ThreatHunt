from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/host_inventory.py')
t=p.read_text(encoding='utf-8')
old='''    return {
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
new='''    return {
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
            "sampled_mode": settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET > 0,
        },
    }
'''
if old not in t:
    raise SystemExit('return block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('patched inventory stats metadata')
