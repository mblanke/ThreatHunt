"""CSV parsing engine with encoding detection, delimiter sniffing, and streaming.

Handles large Velociraptor CSV exports with resilience to encoding issues,
varied delimiters, and malformed rows.
"""

import csv
import io
import logging
from pathlib import Path
from typing import AsyncIterator

import chardet

logger = logging.getLogger(__name__)

# Reasonable defaults
MAX_FIELD_SIZE = 1024 * 1024  # 1 MB per field
csv.field_size_limit(MAX_FIELD_SIZE)


def detect_encoding(file_bytes: bytes, sample_size: int = 65536) -> str:
    """Detect file encoding from a sample of bytes."""
    result = chardet.detect(file_bytes[:sample_size])
    encoding = result.get("encoding", "utf-8") or "utf-8"
    confidence = result.get("confidence", 0)
    logger.info(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")
    # Fall back to utf-8 if confidence is very low
    if confidence < 0.5:
        encoding = "utf-8"
    return encoding


def detect_delimiter(text_sample: str) -> str:
    """Sniff the CSV delimiter from a text sample."""
    try:
        dialect = csv.Sniffer().sniff(text_sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return ","


def infer_column_types(rows: list[dict], sample_size: int = 100) -> dict[str, str]:
    """Infer column types from a sample of rows.

    Returns a mapping of column_name → type_hint where type_hint is one of:
    timestamp, integer, float, ip, hash_md5, hash_sha1, hash_sha256, domain, path, string
    """
    import re

    type_map: dict[str, dict[str, int]] = {}
    sample = rows[:sample_size]

    patterns = {
        "ip": re.compile(
            r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
        ),
        "hash_md5": re.compile(r"^[a-fA-F0-9]{32}$"),
        "hash_sha1": re.compile(r"^[a-fA-F0-9]{40}$"),
        "hash_sha256": re.compile(r"^[a-fA-F0-9]{64}$"),
        "integer": re.compile(r"^-?\d+$"),
        "float": re.compile(r"^-?\d+\.\d+$"),
        "timestamp": re.compile(
            r"^\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}"
        ),
        "domain": re.compile(
            r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"
        ),
        "path": re.compile(r"^([A-Z]:\\|/)", re.IGNORECASE),
    }

    for row in sample:
        for col, val in row.items():
            if col not in type_map:
                type_map[col] = {}
            val_str = str(val).strip()
            if not val_str:
                continue
            matched = False
            for type_name, pattern in patterns.items():
                if pattern.match(val_str):
                    type_map[col][type_name] = type_map[col].get(type_name, 0) + 1
                    matched = True
                    break
            if not matched:
                type_map[col]["string"] = type_map[col].get("string", 0) + 1

    result: dict[str, str] = {}
    for col, counts in type_map.items():
        if counts:
            result[col] = max(counts, key=counts.get)  # type: ignore[arg-type]
        else:
            result[col] = "string"

    return result


def parse_csv_bytes(
    raw_bytes: bytes,
    max_rows: int | None = None,
) -> tuple[list[dict], dict]:
    """Parse a CSV file from raw bytes.

    Returns:
        (rows, metadata) where metadata contains encoding, delimiter, columns, etc.
    """
    encoding = detect_encoding(raw_bytes)

    try:
        text = raw_bytes.decode(encoding, errors="replace")
    except (UnicodeDecodeError, LookupError):
        text = raw_bytes.decode("utf-8", errors="replace")
        encoding = "utf-8"

    # Detect delimiter from first few KB
    delimiter = detect_delimiter(text[:8192])

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    columns = reader.fieldnames or []

    rows: list[dict] = []
    for i, row in enumerate(reader):
        if max_rows is not None and i >= max_rows:
            break
        rows.append(dict(row))

    column_types = infer_column_types(rows) if rows else {}

    metadata = {
        "encoding": encoding,
        "delimiter": delimiter,
        "columns": columns,
        "column_types": column_types,
        "row_count": len(rows),
        "total_rows_in_file": len(rows),  # same when no max_rows
    }

    return rows, metadata


async def parse_csv_streaming(
    file_path: Path,
    chunk_size: int = 8192,
) -> AsyncIterator[tuple[int, dict]]:
    """Stream-parse a CSV file yielding (row_index, row_dict) tuples.

    Memory-efficient for large files.
    """
    import aiofiles  # type: ignore[import-untyped]

    # Read a sample for encoding/delimiter detection
    with open(file_path, "rb") as f:
        sample_bytes = f.read(65536)

    encoding = detect_encoding(sample_bytes)
    text_sample = sample_bytes.decode(encoding, errors="replace")
    delimiter = detect_delimiter(text_sample[:8192])

    # Now stream-read
    async with aiofiles.open(file_path, mode="r", encoding=encoding, errors="replace") as f:
        content = await f.read()  # For DictReader compatibility

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    for i, row in enumerate(reader):
        yield i, dict(row)
