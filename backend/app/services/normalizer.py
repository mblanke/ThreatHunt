"""Artifact normalizer — maps Velociraptor and common tool columns to canonical schema.

The canonical schema provides consistent field names regardless of which tool
exported the CSV (Velociraptor, OSQuery, Sysmon, etc.).
"""

import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ── Column mapping: source_column_pattern → canonical_name ─────────────
# Patterns are case-insensitive regexes matched against column names.

COLUMN_MAPPINGS: list[tuple[str, str]] = [
    # Timestamps
    (r"^(timestamp|time|event_?time|date_?time|created?_?(at|time|date)|modified_?(at|time|date)|mtime|ctime|atime|start_?time|end_?time)$", "timestamp"),
    (r"^(eventtime|system\.timecreated)$", "timestamp"),
    # Host identifiers
    (r"^(hostname|host|fqdn|computer_?name|system_?name|machinename|clientid)$", "hostname"),
    # Operating system
    (r"^(os|operating_?system|os_?version|os_?name|platform|os_?type)$", "os"),
    # Source / destination IPs
    (r"^(source_?ip|src_?ip|srcaddr|local_?address|sourceaddress|sourceip|laddr\.?ip)$", "src_ip"),
    (r"^(dest_?ip|dst_?ip|dstaddr|remote_?address|destinationaddress|destaddress|destination_?ip|destinationip|raddr\.?ip)$", "dst_ip"),
    (r"^(ip_?address|ipaddress|ip)$", "ip_address"),
    # Ports
    (r"^(source_?port|src_?port|localport|laddr\.?port)$", "src_port"),
    (r"^(dest_?port|dst_?port|remoteport|destinationport|raddr\.?port)$", "dst_port"),
    # Process info
    (r"^(process_?name|name|image|exe|executable|binary)$", "process_name"),
    (r"^(pid|process_?id)$", "pid"),
    (r"^(ppid|parent_?pid|parentprocessid)$", "ppid"),
    (r"^(command_?line|cmdline|commandline|cmd)$", "command_line"),
    (r"^(parent_?command_?line|parentcommandline)$", "parent_command_line"),
    # User info
    (r"^(user|username|user_?name|account_?name|subjectusername)$", "username"),
    (r"^(user_?id|uid|sid|subjectusersid)$", "user_id"),
    # File info
    (r"^(file_?path|fullpath|full_?name|path|filepath)$", "file_path"),
    (r"^(file_?name|filename|name)$", "file_name"),
    (r"^(file_?size|size|bytes|length)$", "file_size"),
    (r"^(extension|file_?ext)$", "file_extension"),
    # Hashes
    (r"^(md5|md5hash|hash_?md5)$", "hash_md5"),
    (r"^(sha1|sha1hash|hash_?sha1)$", "hash_sha1"),
    (r"^(sha256|sha256hash|hash_?sha256|hash|filehash)$", "hash_sha256"),
    # Network
    (r"^(protocol|proto)$", "protocol"),
    (r"^(domain|dns_?name|query_?name|queriedname)$", "domain"),
    (r"^(url|uri|request_?url)$", "url"),
    # MAC address
    (r"^(mac|mac_?address|physical_?address|mac_?addr|hw_?addr|ethernet)$", "mac_address"),
    # Connection state (netstat)
    (r"^(state|status|tcp_?state|conn_?state)$", "connection_state"),
    # Event info
    (r"^(event_?id|eventid|eid)$", "event_id"),
    (r"^(event_?type|eventtype|category|action)$", "event_type"),
    (r"^(description|message|msg|detail)$", "description"),
    (r"^(severity|level|priority)$", "severity"),
    # Registry
    (r"^(reg_?key|registry_?key|targetobject)$", "registry_key"),
    (r"^(reg_?value|registry_?value)$", "registry_value"),
]


def normalize_columns(columns: list[str]) -> dict[str, str]:
    """Map raw column names to canonical names.

    Returns:
        Dict of {raw_column_name: canonical_column_name}.
        Columns with no match map to themselves (lowered + underscored).
    """
    mapping: dict[str, str] = {}
    used_canonical: set[str] = set()

    for col in columns:
        col_lower = col.strip().lower()
        matched = False
        for pattern, canonical in COLUMN_MAPPINGS:
            if re.match(pattern, col_lower, re.IGNORECASE):
                # Avoid duplicate canonical names
                if canonical not in used_canonical:
                    mapping[col] = canonical
                    used_canonical.add(canonical)
                    matched = True
                    break
        if not matched:
            # Produce a clean snake_case version
            clean = re.sub(r"[^a-z0-9]+", "_", col_lower).strip("_")
            mapping[col] = clean or col

    return mapping


def normalize_row(row: dict[str, Any], column_mapping: dict[str, str]) -> dict[str, Any]:
    """Apply column mapping to a single row."""
    return {column_mapping.get(k, k): v for k, v in row.items()}


def normalize_rows(rows: list[dict], column_mapping: dict[str, str]) -> list[dict]:
    """Apply column mapping to all rows."""
    return [normalize_row(row, column_mapping) for row in rows]


def detect_ioc_columns(
    columns: list[str],
    column_types: dict[str, str],
    column_mapping: dict[str, str],
) -> dict[str, str]:
    """Detect which columns contain IOCs (IPs, hashes, domains).

    Returns:
        Dict of {column_name: ioc_type}.
    """
    ioc_columns: dict[str, str] = {}
    ioc_type_map = {
        "ip": "ip",
        "hash_md5": "hash_md5",
        "hash_sha1": "hash_sha1",
        "hash_sha256": "hash_sha256",
        "domain": "domain",
    }

    # Canonical names that should NEVER be treated as IOCs even if values
    # match a pattern (e.g. process_name "svchost.exe" matching domain regex).
    _non_ioc_canonicals = frozenset({
        "process_name", "file_name", "file_path", "command_line",
        "parent_command_line", "description", "event_type", "registry_key",
        "registry_value", "severity", "os",
        "title", "netmask", "gateway", "connection_state",
    })

    for col in columns:
        canonical = column_mapping.get(col, "")

        # Skip columns whose canonical meaning is obviously not an IOC
        if canonical in _non_ioc_canonicals:
            continue

        col_type = column_types.get(col)
        if col_type in ioc_type_map:
            ioc_columns[col] = ioc_type_map[col_type]

        # Also check canonical name
        if canonical in ("src_ip", "dst_ip", "ip_address"):
            ioc_columns[col] = "ip"
        elif canonical == "hash_md5":
            ioc_columns[col] = "hash_md5"
        elif canonical == "hash_sha1":
            ioc_columns[col] = "hash_sha1"
        elif canonical in ("hash_sha256",):
            ioc_columns[col] = "hash_sha256"
        elif canonical == "domain":
            ioc_columns[col] = "domain"
        elif canonical == "url":
            ioc_columns[col] = "url"
        elif canonical == "hostname":
            ioc_columns[col] = "hostname"

    return ioc_columns


def detect_time_range(
    rows: list[dict],
    column_mapping: dict[str, str],
) -> tuple[datetime | None, datetime | None]:
    """Find the earliest and latest timestamps in the dataset."""
    ts_col = None
    for raw_col, canonical in column_mapping.items():
        if canonical == "timestamp":
            ts_col = raw_col
            break

    if not ts_col:
        return None, None

    timestamps: list[datetime] = []
    for row in rows:
        val = row.get(ts_col)
        if not val:
            continue
        try:
            dt = _parse_timestamp(str(val))
            if dt:
                timestamps.append(dt)
        except (ValueError, TypeError):
            continue

    if not timestamps:
        return None, None

    return min(timestamps), max(timestamps)


def _parse_timestamp(value: str) -> datetime | None:
    """Try multiple timestamp formats."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None
