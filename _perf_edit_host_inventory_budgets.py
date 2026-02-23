from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/host_inventory.py')
t=p.read_text(encoding='utf-8')

# insert budget vars near existing counters
old='''    connections: dict[tuple, int] = defaultdict(int)
    total_rows = 0
    ds_with_hosts = 0
'''
new='''    connections: dict[tuple, int] = defaultdict(int)
    total_rows = 0
    ds_with_hosts = 0
    sampled_dataset_count = 0
    total_row_budget = max(0, int(settings.NETWORK_INVENTORY_MAX_TOTAL_ROWS))
    max_connections = max(0, int(settings.NETWORK_INVENTORY_MAX_CONNECTIONS))
    global_budget_reached = False
    dropped_connections = 0
'''
if old not in t:
    raise SystemExit('counter block not found')
t=t.replace(old,new)

# update batch size and sampled count increments + global budget checks
old2='''        batch_size = 10000
        max_rows_per_dataset = max(0, int(settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET))
        rows_scanned_this_dataset = 0
        sampled_dataset = False
        last_row_index = -1
        while True:
'''
new2='''        batch_size = 5000
        max_rows_per_dataset = max(0, int(settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET))
        rows_scanned_this_dataset = 0
        sampled_dataset = False
        last_row_index = -1
        while True:
            if total_row_budget and total_rows >= total_row_budget:
                global_budget_reached = True
                break
'''
if old2 not in t:
    raise SystemExit('batch block not found')
t=t.replace(old2,new2)

old3='''                if max_rows_per_dataset and rows_scanned_this_dataset >= max_rows_per_dataset:
                    sampled_dataset = True
                    break

                data = ro.data or {}
                total_rows += 1
                rows_scanned_this_dataset += 1
'''
new3='''                if max_rows_per_dataset and rows_scanned_this_dataset >= max_rows_per_dataset:
                    sampled_dataset = True
                    break
                if total_row_budget and total_rows >= total_row_budget:
                    sampled_dataset = True
                    global_budget_reached = True
                    break

                data = ro.data or {}
                total_rows += 1
                rows_scanned_this_dataset += 1
'''
if old3 not in t:
    raise SystemExit('row scan block not found')
t=t.replace(old3,new3)

# cap connection map growth
old4='''                for c in cols['remote_ip']:
                    rip = _clean(data.get(c))
                    if _is_valid_ip(rip):
                        rport = ''
                        for pc in cols['remote_port']:
                            rport = _clean(data.get(pc))
                            if rport:
                                break
                        connections[(host_key, rip, rport)] += 1
'''
new4='''                for c in cols['remote_ip']:
                    rip = _clean(data.get(c))
                    if _is_valid_ip(rip):
                        rport = ''
                        for pc in cols['remote_port']:
                            rport = _clean(data.get(pc))
                            if rport:
                                break
                        conn_key = (host_key, rip, rport)
                        if max_connections and len(connections) >= max_connections and conn_key not in connections:
                            dropped_connections += 1
                            continue
                        connections[conn_key] += 1
'''
if old4 not in t:
    raise SystemExit('connection block not found')
t=t.replace(old4,new4)

# sampled_dataset counter
old5='''            if sampled_dataset:
                logger.info(
                    "Host inventory row budget reached for dataset %s (%d rows)",
                    ds.id,
                    rows_scanned_this_dataset,
                )
                break
'''
new5='''            if sampled_dataset:
                sampled_dataset_count += 1
                logger.info(
                    "Host inventory row budget reached for dataset %s (%d rows)",
                    ds.id,
                    rows_scanned_this_dataset,
                )
                break
'''
if old5 not in t:
    raise SystemExit('sampled block not found')
t=t.replace(old5,new5)

# break dataset loop if global budget reached
old6='''            if len(rows) < batch_size:
                break

    # Post-process hosts
'''
new6='''            if len(rows) < batch_size:
                break

        if global_budget_reached:
            logger.info(
                "Host inventory global row budget reached for hunt %s at %d rows",
                hunt_id,
                total_rows,
            )
            break

    # Post-process hosts
'''
if old6 not in t:
    raise SystemExit('post-process boundary block not found')
t=t.replace(old6,new6)

# add stats
old7='''            "row_budget_per_dataset": settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET,
            "sampled_mode": settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET > 0,
        },
    }
'''
new7='''            "row_budget_per_dataset": settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET,
            "row_budget_total": settings.NETWORK_INVENTORY_MAX_TOTAL_ROWS,
            "connection_budget": settings.NETWORK_INVENTORY_MAX_CONNECTIONS,
            "sampled_mode": settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET > 0 or settings.NETWORK_INVENTORY_MAX_TOTAL_ROWS > 0,
            "sampled_datasets": sampled_dataset_count,
            "global_budget_reached": global_budget_reached,
            "dropped_connections": dropped_connections,
        },
    }
'''
if old7 not in t:
    raise SystemExit('stats block not found')
t=t.replace(old7,new7)

p.write_text(t,encoding='utf-8')
print('updated host inventory with global row and connection budgets')
