"""Network Picture — deduplicated host inventory built from dataset rows.

Scans all datasets in a hunt, extracts host-identifying fields from
normalized data, and groups by hostname (or src_ip fallback) to produce
a clean one-row-per-host inventory.  Uses sets for deduplication —
if an IP appears 900 times, it shows once.
"""

import logging
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset, DatasetRow

logger = logging.getLogger(__name__)

# Canonical column names we extract per row
_HOST_KEYS = ("hostname",)
_IP_KEYS = ("src_ip", "dst_ip", "ip_address")
_USER_KEYS = ("username",)
_OS_KEYS = ("os",)
_MAC_KEYS = ("mac_address",)
_PORT_SRC_KEYS = ("src_port",)
_PORT_DST_KEYS = ("dst_port",)
_PROTO_KEYS = ("protocol",)
_STATE_KEYS = ("connection_state",)
_TS_KEYS = ("timestamp",)

# Junk values to skip
_JUNK = frozenset({"", "-", "0.0.0.0", "::", "0", "127.0.0.1", "::1", "localhost", "unknown", "n/a", "none", "null"})

ROW_BATCH = 1000  # rows fetched per DB query
MAX_HOSTS = 1000  # hard cap on returned hosts


def _clean(val: Any) -> str:
    """Normalise a cell value to a clean string or empty."""
    s = (val if isinstance(val, str) else str(val) if val is not None else "").strip()
    return "" if s.lower() in _JUNK else s


def _try_parse_ts(val: str) -> datetime | None:
    """Best-effort timestamp parse (subset of common formats)."""
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(val.strip(), fmt)
        except ValueError:
            continue
    return None


class _HostBucket:
    """Mutable accumulator for a single host."""

    __slots__ = (
        "hostname", "ips", "users", "os_versions", "mac_addresses",
        "protocols", "open_ports", "remote_targets", "datasets",
        "connection_count", "first_seen", "last_seen",
    )

    def __init__(self, hostname: str):
        self.hostname = hostname
        self.ips: set[str] = set()
        self.users: set[str] = set()
        self.os_versions: set[str] = set()
        self.mac_addresses: set[str] = set()
        self.protocols: set[str] = set()
        self.open_ports: set[str] = set()
        self.remote_targets: set[str] = set()
        self.datasets: set[str] = set()
        self.connection_count: int = 0
        self.first_seen: datetime | None = None
        self.last_seen: datetime | None = None

    def ingest(self, row: dict[str, Any], ds_name: str) -> None:
        """Merge one normalised row into this bucket."""
        self.connection_count += 1
        self.datasets.add(ds_name)

        for k in _IP_KEYS:
            v = _clean(row.get(k))
            if v:
                self.ips.add(v)

        for k in _USER_KEYS:
            v = _clean(row.get(k))
            if v:
                self.users.add(v)

        for k in _OS_KEYS:
            v = _clean(row.get(k))
            if v:
                self.os_versions.add(v)

        for k in _MAC_KEYS:
            v = _clean(row.get(k))
            if v:
                self.mac_addresses.add(v)

        for k in _PROTO_KEYS:
            v = _clean(row.get(k))
            if v:
                self.protocols.add(v.upper())

        # Open ports = local (src) ports
        for k in _PORT_SRC_KEYS:
            v = _clean(row.get(k))
            if v and v != "0":
                self.open_ports.add(v)

        # Remote targets = dst IPs
        dst = _clean(row.get("dst_ip"))
        if dst:
            self.remote_targets.add(dst)

        # Timestamps
        for k in _TS_KEYS:
            v = _clean(row.get(k))
            if v:
                ts = _try_parse_ts(v)
                if ts:
                    if self.first_seen is None or ts < self.first_seen:
                        self.first_seen = ts
                    if self.last_seen is None or ts > self.last_seen:
                        self.last_seen = ts

    def to_dict(self) -> dict[str, Any]:
        return {
            "hostname": self.hostname,
            "ips": sorted(self.ips),
            "users": sorted(self.users),
            "os": sorted(self.os_versions),
            "mac_addresses": sorted(self.mac_addresses),
            "protocols": sorted(self.protocols),
            "open_ports": sorted(self.open_ports, key=lambda p: int(p) if p.isdigit() else 0),
            "remote_targets": sorted(self.remote_targets),
            "datasets": sorted(self.datasets),
            "connection_count": self.connection_count,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


async def build_network_picture(
    db: AsyncSession,
    hunt_id: str,
) -> dict[str, Any]:
    """Build a deduplicated host inventory for all datasets in a hunt.

    Returns:
        {
            "hosts": [ {hostname, ips[], users[], os[], ...}, ... ],
            "summary": { total_hosts, total_connections, total_unique_ips, datasets_scanned }
        }
    """
    # 1. Get all datasets in this hunt
    ds_result = await db.execute(
        select(Dataset)
        .where(Dataset.hunt_id == hunt_id)
        .order_by(Dataset.created_at)
    )
    ds_list: Sequence[Dataset] = ds_result.scalars().all()

    if not ds_list:
        return {
            "hosts": [],
            "summary": {
                "total_hosts": 0,
                "total_connections": 0,
                "total_unique_ips": 0,
                "datasets_scanned": 0,
            },
        }

    # 2. Stream rows and aggregate into host buckets
    buckets: dict[str, _HostBucket] = {}  # key = uppercase hostname or IP

    for ds in ds_list:
        ds_name = ds.name or ds.filename
        offset = 0
        while True:
            stmt = (
                select(DatasetRow)
                .where(DatasetRow.dataset_id == ds.id)
                .order_by(DatasetRow.row_index)
                .limit(ROW_BATCH)
                .offset(offset)
            )
            result = await db.execute(stmt)
            rows: Sequence[DatasetRow] = result.scalars().all()
            if not rows:
                break

            for dr in rows:
                norm = dr.normalized_data or dr.data or {}

                # Determine grouping key: hostname preferred, else src_ip/ip_address
                host_val = ""
                for k in _HOST_KEYS:
                    host_val = _clean(norm.get(k))
                    if host_val:
                        break
                if not host_val:
                    for k in ("src_ip", "ip_address"):
                        host_val = _clean(norm.get(k))
                        if host_val:
                            break
                if not host_val:
                    # Row has no host identifier — skip
                    continue

                bucket_key = host_val.upper()
                if bucket_key not in buckets:
                    buckets[bucket_key] = _HostBucket(host_val)

                buckets[bucket_key].ingest(norm, ds_name)

            offset += ROW_BATCH

    # 3. Convert to sorted list (by connection count descending)
    hosts_raw = sorted(buckets.values(), key=lambda b: b.connection_count, reverse=True)
    if len(hosts_raw) > MAX_HOSTS:
        hosts_raw = hosts_raw[:MAX_HOSTS]

    hosts = [b.to_dict() for b in hosts_raw]

    # 4. Summary stats
    all_ips: set[str] = set()
    total_conns = 0
    for b in hosts_raw:
        all_ips.update(b.ips)
        total_conns += b.connection_count

    return {
        "hosts": hosts,
        "summary": {
            "total_hosts": len(hosts),
            "total_connections": total_conns,
            "total_unique_ips": len(all_ips),
            "datasets_scanned": len(ds_list),
        },
    }
