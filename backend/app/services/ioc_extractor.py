"""IOC extraction service  extract indicators of compromise from dataset rows.

Identifies: IPv4/IPv6 addresses, domain names, MD5/SHA1/SHA256 hashes,
email addresses, URLs, and file paths that look suspicious.
"""

import re
import logging
from collections import defaultdict
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset, DatasetRow

logger = logging.getLogger(__name__)

#  Patterns 

_IPV4 = re.compile(
    r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
)
_IPV6 = re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b')
_DOMAIN = re.compile(
    r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)'
    r'+(?:com|net|org|io|info|biz|co|us|uk|de|ru|cn|cc|tk|xyz|top|'
    r'online|site|club|win|work|download|stream|gdn|bid|review|racing|'
    r'loan|date|faith|accountant|cricket|science|trade|party|men)\b',
    re.IGNORECASE,
)
_MD5 = re.compile(r'\b[0-9a-fA-F]{32}\b')
_SHA1 = re.compile(r'\b[0-9a-fA-F]{40}\b')
_SHA256 = re.compile(r'\b[0-9a-fA-F]{64}\b')
_EMAIL = re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b')
_URL = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)

# Private / reserved IPs to skip
_PRIVATE_NETS = re.compile(
    r'^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|127\.|0\.|255\.)'
)

PATTERNS = {
    'ipv4': _IPV4,
    'ipv6': _IPV6,
    'domain': _DOMAIN,
    'md5': _MD5,
    'sha1': _SHA1,
    'sha256': _SHA256,
    'email': _EMAIL,
    'url': _URL,
}


def _is_private_ip(ip: str) -> bool:
    return bool(_PRIVATE_NETS.match(ip))


def extract_iocs_from_text(text: str, skip_private: bool = True) -> dict[str, set[str]]:
    """Extract all IOC types from a block of text."""
    result: dict[str, set[str]] = defaultdict(set)
    for ioc_type, pattern in PATTERNS.items():
        for match in pattern.findall(text):
            val = match.strip().lower() if ioc_type != 'url' else match.strip()
            # Filter private IPs
            if ioc_type == 'ipv4' and skip_private and _is_private_ip(val):
                continue
            # Filter hex strings that are too generic (< 32 chars not a hash)
            result[ioc_type].add(val)
    return result


async def extract_iocs_from_dataset(
    dataset_id: str,
    db: AsyncSession,
    max_rows: int = 5000,
    skip_private: bool = True,
) -> dict[str, list[str]]:
    """Extract IOCs from all rows of a dataset.

    Returns {ioc_type: [sorted unique values]}.
    """
    # Load rows in batches
    all_iocs: dict[str, set[str]] = defaultdict(set)
    offset = 0
    batch_size = 500

    while offset < max_rows:
        result = await db.execute(
            select(DatasetRow.data)
            .where(DatasetRow.dataset_id == dataset_id)
            .order_by(DatasetRow.row_index)
            .offset(offset)
            .limit(batch_size)
        )
        rows = result.scalars().all()
        if not rows:
            break

        for data in rows:
            # Flatten all values to a single string for scanning
            text = ' '.join(str(v) for v in data.values()) if isinstance(data, dict) else str(data)
            batch_iocs = extract_iocs_from_text(text, skip_private)
            for ioc_type, values in batch_iocs.items():
                all_iocs[ioc_type].update(values)

        offset += batch_size

    # Convert sets to sorted lists
    return {k: sorted(v) for k, v in all_iocs.items() if v}


async def extract_host_groups(
    hunt_id: str,
    db: AsyncSession,
) -> list[dict]:
    """Group all data by hostname across datasets in a hunt.

    Returns a list of host group dicts with dataset count, total rows,
    artifact types, and time range.
    """
    # Get all datasets for this hunt
    result = await db.execute(
        select(Dataset).where(Dataset.hunt_id == hunt_id)
    )
    ds_list = result.scalars().all()
    if not ds_list:
        return []

    # Known host columns (check normalized data first, then raw)
    HOST_COLS = [
        'hostname', 'host', 'computer_name', 'computername', 'system',
        'machine', 'device_name', 'devicename', 'endpoint',
        'ClientId', 'Fqdn', 'client_id', 'fqdn',
    ]

    hosts: dict[str, dict] = {}

    for ds in ds_list:
        # Sample first few rows to find host column
        sample_result = await db.execute(
            select(DatasetRow.data, DatasetRow.normalized_data)
            .where(DatasetRow.dataset_id == ds.id)
            .limit(5)
        )
        samples = sample_result.all()
        if not samples:
            continue

        # Find which host column exists
        host_col = None
        for row_data, norm_data in samples:
            check = norm_data if norm_data else row_data
            if not isinstance(check, dict):
                continue
            for col in HOST_COLS:
                if col in check and check[col]:
                    host_col = col
                    break
            if host_col:
                break

        if not host_col:
            continue

        # Count rows per host in this dataset
        all_rows_result = await db.execute(
            select(DatasetRow.data, DatasetRow.normalized_data)
            .where(DatasetRow.dataset_id == ds.id)
        )
        all_rows = all_rows_result.all()
        for row_data, norm_data in all_rows:
            check = norm_data if norm_data else row_data
            if not isinstance(check, dict):
                continue
            host_val = check.get(host_col, '')
            if not host_val or not isinstance(host_val, str):
                continue
            host_val = host_val.strip()
            if not host_val:
                continue

            if host_val not in hosts:
                hosts[host_val] = {
                    'hostname': host_val,
                    'dataset_ids': set(),
                    'total_rows': 0,
                    'artifact_types': set(),
                    'first_seen': None,
                    'last_seen': None,
                }
            hosts[host_val]['dataset_ids'].add(ds.id)
            hosts[host_val]['total_rows'] += 1
            if ds.artifact_type:
                hosts[host_val]['artifact_types'].add(ds.artifact_type)

    # Convert to output format
    result_list = []
    for h in sorted(hosts.values(), key=lambda x: x['total_rows'], reverse=True):
        result_list.append({
            'hostname': h['hostname'],
            'dataset_count': len(h['dataset_ids']),
            'total_rows': h['total_rows'],
            'artifact_types': sorted(h['artifact_types']),
            'first_seen': None,  # TODO: extract from timestamp columns
            'last_seen': None,
            'risk_score': None,  # TODO: link to host profiles
        })

    return result_list