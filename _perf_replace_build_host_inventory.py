from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/host_inventory.py')
t=p.read_text(encoding='utf-8')
start=t.index('async def build_host_inventory(')
# find end of function by locating '\n\n' before EOF after '    }\n'
end=t.index('\n\n', start)
# need proper end: first double newline after function may occur in docstring? compute by searching for '\n\n' after '    }\n' near end
ret_idx=t.rfind('    }')
# safer locate end as last occurrence of '\n    }\n' after start, then function ends next newline
end=t.find('\n\n', ret_idx)
if end==-1:
    end=len(t)
new_func='''async def build_host_inventory(hunt_id: str, db: AsyncSession) -> dict:
    """Build a deduplicated host inventory from all datasets in a hunt.

    Returns dict with 'hosts', 'connections', and 'stats'.
    Each host has: id, hostname, fqdn, client_id, ips, os, users, datasets, row_count.
    """
    ds_result = await db.execute(
        select(Dataset).where(Dataset.hunt_id == hunt_id)
    )
    all_datasets = ds_result.scalars().all()

    if not all_datasets:
        return {"hosts": [], "connections": [], "stats": {
            "total_hosts": 0, "total_datasets_scanned": 0,
            "total_rows_scanned": 0,
        }}

    hosts: dict[str, dict] = {}          # fqdn -> host record
    ip_to_host: dict[str, str] = {}      # local-ip -> fqdn
    connections: dict[tuple, int] = defaultdict(int)
    total_rows = 0
    ds_with_hosts = 0
    sampled_dataset_count = 0
    total_row_budget = max(0, int(settings.NETWORK_INVENTORY_MAX_TOTAL_ROWS))
    max_connections = max(0, int(settings.NETWORK_INVENTORY_MAX_CONNECTIONS))
    global_budget_reached = False
    dropped_connections = 0

    for ds in all_datasets:
        if total_row_budget and total_rows >= total_row_budget:
            global_budget_reached = True
            break

        cols = _identify_columns(ds)
        if not cols['fqdn'] and not cols['host_id']:
            continue
        ds_with_hosts += 1

        batch_size = 5000
        max_rows_per_dataset = max(0, int(settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET))
        rows_scanned_this_dataset = 0
        sampled_dataset = False
        last_row_index = -1

        while True:
            if total_row_budget and total_rows >= total_row_budget:
                sampled_dataset = True
                global_budget_reached = True
                break

            rr = await db.execute(
                select(DatasetRow)
                .where(DatasetRow.dataset_id == ds.id)
                .where(DatasetRow.row_index > last_row_index)
                .order_by(DatasetRow.row_index)
                .limit(batch_size)
            )
            rows = rr.scalars().all()
            if not rows:
                break

            for ro in rows:
                if max_rows_per_dataset and rows_scanned_this_dataset >= max_rows_per_dataset:
                    sampled_dataset = True
                    break
                if total_row_budget and total_rows >= total_row_budget:
                    sampled_dataset = True
                    global_budget_reached = True
                    break

                data = ro.data or {}
                total_rows += 1
                rows_scanned_this_dataset += 1

                fqdn = ''
                for c in cols['fqdn']:
                    fqdn = _clean(data.get(c))
                    if fqdn:
                        break
                client_id = ''
                for c in cols['host_id']:
                    client_id = _clean(data.get(c))
                    if client_id:
                        break

                if not fqdn and not client_id:
                    continue

                host_key = fqdn or client_id

                if host_key not in hosts:
                    short = fqdn.split('.')[0] if fqdn and '.' in fqdn else fqdn
                    hosts[host_key] = {
                        'id': host_key,
                        'hostname': short or client_id,
                        'fqdn': fqdn,
                        'client_id': client_id,
                        'ips': set(),
                        'os': '',
                        'users': set(),
                        'datasets': set(),
                        'row_count': 0,
                    }

                h = hosts[host_key]
                h['datasets'].add(ds.name)
                h['row_count'] += 1
                if client_id and not h['client_id']:
                    h['client_id'] = client_id

                for c in cols['username']:
                    u = _extract_username(_clean(data.get(c)))
                    if u:
                        h['users'].add(u)

                for c in cols['local_ip']:
                    ip = _clean(data.get(c))
                    if _is_valid_ip(ip):
                        h['ips'].add(ip)
                        ip_to_host[ip] = host_key

                for c in cols['os']:
                    ov = _clean(data.get(c))
                    if ov and not h['os']:
                        h['os'] = ov

                for c in cols['remote_ip']:
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

            if sampled_dataset:
                sampled_dataset_count += 1
                logger.info(
                    "Host inventory sampling for dataset %s (%d rows scanned)",
                    ds.id,
                    rows_scanned_this_dataset,
                )
                break

            last_row_index = rows[-1].row_index
            if len(rows) < batch_size:
                break

        if global_budget_reached:
            logger.info(
                "Host inventory global row budget reached for hunt %s at %d rows",
                hunt_id,
                total_rows,
            )
            break

    # Post-process hosts
    for h in hosts.values():
        if not h['os'] and h['fqdn']:
            h['os'] = _infer_os(h['fqdn'])
        h['ips'] = sorted(h['ips'])
        h['users'] = sorted(h['users'])
        h['datasets'] = sorted(h['datasets'])

    # Build connections, resolving IPs to host keys
    conn_list = []
    seen = set()
    for (src, dst_ip, dst_port), cnt in connections.items():
        if dst_ip in _IGNORE_IPS:
            continue
        dst_host = ip_to_host.get(dst_ip, '')
        if dst_host == src:
            continue
        key = tuple(sorted([src, dst_host or dst_ip]))
        if key in seen:
            continue
        seen.add(key)
        conn_list.append({
            'source': src,
            'target': dst_host or dst_ip,
            'target_ip': dst_ip,
            'port': dst_port,
            'count': cnt,
        })

    host_list = sorted(hosts.values(), key=lambda x: x['row_count'], reverse=True)

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
            "row_budget_total": settings.NETWORK_INVENTORY_MAX_TOTAL_ROWS,
            "connection_budget": settings.NETWORK_INVENTORY_MAX_CONNECTIONS,
            "sampled_mode": settings.NETWORK_INVENTORY_MAX_ROWS_PER_DATASET > 0 or settings.NETWORK_INVENTORY_MAX_TOTAL_ROWS > 0,
            "sampled_datasets": sampled_dataset_count,
            "global_budget_reached": global_budget_reached,
            "dropped_connections": dropped_connections,
        },
    }
'''
out=t[:start]+new_func+t[end:]
p.write_text(out,encoding='utf-8')
print('replaced build_host_inventory with hard-budget fast mode')
