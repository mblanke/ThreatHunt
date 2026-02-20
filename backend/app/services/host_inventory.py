"""Host Inventory Service - builds a deduplicated host-centric network view.

Scans all datasets in a hunt to identify unique hosts, their IPs, OS,
logged-in users, and network connections between them.
"""

import re
import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset, DatasetRow

logger = logging.getLogger(__name__)

# --- Column-name patterns (Velociraptor + generic forensic tools) ---

_HOST_ID_RE = re.compile(
    r'^(client_?id|clientid|agent_?id|endpoint_?id|host_?id|sensor_?id)$', re.I)
_FQDN_RE = re.compile(
    r'^(fqdn|fully_?qualified|computer_?name|hostname|host_?name|host|'
    r'system_?name|machine_?name|nodename|workstation)$', re.I)
_USERNAME_RE = re.compile(
    r'^(user|username|user_?name|logon_?name|account_?name|owner|'
    r'logged_?in_?user|sam_?account_?name|samaccountname)$', re.I)
_LOCAL_IP_RE = re.compile(
    r'^(laddr\.?ip|laddr|local_?addr(ess)?|src_?ip|source_?ip)$', re.I)
_REMOTE_IP_RE = re.compile(
    r'^(raddr\.?ip|raddr|remote_?addr(ess)?|dst_?ip|dest_?ip)$', re.I)
_REMOTE_PORT_RE = re.compile(
    r'^(raddr\.?port|rport|remote_?port|dst_?port|dest_?port)$', re.I)
_OS_RE = re.compile(
    r'^(os|operating_?system|os_?version|os_?name|platform|os_?type|os_?build)$', re.I)
_IP_VALID_RE = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')

_IGNORE_IPS = frozenset({
    '0.0.0.0', '::', '::1', '127.0.0.1', '', '-', '*', 'None', 'null',
})
_SYSTEM_DOMAINS = frozenset({
    'NT AUTHORITY', 'NT SERVICE', 'FONT DRIVER HOST', 'WINDOW MANAGER',
})
_SYSTEM_USERS = frozenset({
    'SYSTEM', 'LOCAL SERVICE', 'NETWORK SERVICE',
    'UMFD-0', 'UMFD-1', 'DWM-1', 'DWM-2', 'DWM-3',
})


def _is_valid_ip(v: str) -> bool:
    if not v or v in _IGNORE_IPS:
        return False
    return bool(_IP_VALID_RE.match(v))


def _clean(v: Any) -> str:
    s = str(v or '').strip()
    return s if s and s not in ('-', 'None', 'null', '') else ''


_SYSTEM_USER_RE = re.compile(
    r'^(SYSTEM|LOCAL SERVICE|NETWORK SERVICE|DWM-\d+|UMFD-\d+)$', re.I)


def _extract_username(raw: str) -> str:
    """Clean username, stripping domain prefixes and filtering system accounts."""
    if not raw:
        return ''
    name = raw.strip()
    if '\\' in name:
        domain, _, name = name.rpartition('\\')
        name = name.strip()
        if domain.strip().upper() in _SYSTEM_DOMAINS:
            if not name or _SYSTEM_USER_RE.match(name):
                return ''
    if _SYSTEM_USER_RE.match(name):
        return ''
    return name or ''


def _infer_os(fqdn: str) -> str:
    u = fqdn.upper()
    if 'W10-' in u or 'WIN10' in u:
        return 'Windows 10'
    if 'W11-' in u or 'WIN11' in u:
        return 'Windows 11'
    if 'W7-' in u or 'WIN7' in u:
        return 'Windows 7'
    if 'SRV' in u or 'SERVER' in u or 'DC-' in u:
        return 'Windows Server'
    if any(k in u for k in ('LINUX', 'UBUNTU', 'CENTOS', 'RHEL', 'DEBIAN')):
        return 'Linux'
    if 'MAC' in u or 'DARWIN' in u:
        return 'macOS'
    return 'Windows'


def _identify_columns(ds: Dataset) -> dict:
    norm = ds.normalized_columns or {}
    schema = ds.column_schema or {}
    raw_cols = list(schema.keys()) if schema else list(norm.keys())

    result = {
        'host_id': [], 'fqdn': [], 'username': [],
        'local_ip': [], 'remote_ip': [], 'remote_port': [], 'os': [],
    }

    for col in raw_cols:
        canonical = (norm.get(col) or '').lower()
        lower = col.lower()

        if _HOST_ID_RE.match(lower) or (canonical == 'hostname' and lower not in ('hostname', 'host_name', 'host')):
            result['host_id'].append(col)

        if _FQDN_RE.match(lower) or canonical == 'fqdn':
            result['fqdn'].append(col)

        if _USERNAME_RE.match(lower) or canonical in ('username', 'user'):
            result['username'].append(col)

        if _LOCAL_IP_RE.match(lower):
            result['local_ip'].append(col)
        elif _REMOTE_IP_RE.match(lower):
            result['remote_ip'].append(col)

        if _REMOTE_PORT_RE.match(lower):
            result['remote_port'].append(col)

        if _OS_RE.match(lower) or canonical == 'os':
            result['os'].append(col)

    return result


async def build_host_inventory(hunt_id: str, db: AsyncSession) -> dict:
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
    ip_to_host: dict[str, str] = {}       # local-ip -> fqdn
    connections: dict[tuple, int] = defaultdict(int)
    total_rows = 0
    ds_with_hosts = 0

    for ds in all_datasets:
        cols = _identify_columns(ds)
        if not cols['fqdn'] and not cols['host_id']:
            continue
        ds_with_hosts += 1

        batch_size = 5000
        offset = 0
        while True:
            rr = await db.execute(
                select(DatasetRow)
                .where(DatasetRow.dataset_id == ds.id)
                .order_by(DatasetRow.row_index)
                .offset(offset).limit(batch_size)
            )
            rows = rr.scalars().all()
            if not rows:
                break

            for ro in rows:
                data = ro.data or {}
                total_rows += 1

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
                        connections[(host_key, rip, rport)] += 1

            offset += batch_size
            if len(rows) < batch_size:
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
        },
    }