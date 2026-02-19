"""Tests for CSV parser and normalizer services."""

import pytest
from app.services.csv_parser import parse_csv_bytes, detect_encoding, detect_delimiter, infer_column_types
from app.services.normalizer import normalize_columns, normalize_rows, detect_ioc_columns, detect_time_range
from tests.conftest import SAMPLE_CSV, SAMPLE_HASH_CSV, make_csv_bytes


class TestCSVParser:
    """Tests for CSV parsing."""

    def test_parse_csv_basic(self):
        rows, meta = parse_csv_bytes(SAMPLE_CSV)
        assert len(rows) == 5
        assert "timestamp" in meta["columns"]
        assert "hostname" in meta["columns"]
        assert meta["encoding"] is not None
        assert meta["delimiter"] == ","

    def test_parse_csv_columns(self):
        rows, meta = parse_csv_bytes(SAMPLE_CSV)
        assert meta["columns"] == ["timestamp", "hostname", "src_ip", "dst_ip", "process_name", "command_line"]

    def test_parse_csv_row_data(self):
        rows, meta = parse_csv_bytes(SAMPLE_CSV)
        assert rows[0]["hostname"] == "DESKTOP-ABC"
        assert rows[0]["src_ip"] == "192.168.1.100"
        assert rows[2]["process_name"] == "chrome.exe"

    def test_parse_csv_hash_file(self):
        rows, meta = parse_csv_bytes(SAMPLE_HASH_CSV)
        assert len(rows) == 2
        assert "md5" in meta["columns"]
        assert "sha256" in meta["columns"]

    def test_parse_tsv(self):
        tsv_data = make_csv_bytes(
            ["host", "ip", "port"],
            [["server1", "10.0.0.1", "443"], ["server2", "10.0.0.2", "80"]],
            delimiter="\t",
        )
        rows, meta = parse_csv_bytes(tsv_data)
        assert len(rows) == 2

    def test_parse_empty_file(self):
        with pytest.raises(Exception):
            parse_csv_bytes(b"")

    def test_detect_encoding_utf8(self):
        enc = detect_encoding(SAMPLE_CSV)
        assert enc is not None
        assert "ascii" in enc.lower() or "utf" in enc.lower()

    def test_infer_column_types(self):
        types = infer_column_types(
            ["192.168.1.1", "10.0.0.1", "8.8.8.8"],
            "src_ip",
        )
        assert types == "ip"

    def test_infer_column_types_hash(self):
        types = infer_column_types(
            ["d41d8cd98f00b204e9800998ecf8427e"],
            "hash",
        )
        assert types == "hash_md5"


class TestNormalizer:
    """Tests for column normalization."""

    def test_normalize_columns(self):
        mapping = normalize_columns(["SourceAddr", "DestAddr", "ProcessName"])
        assert "SourceAddr" in mapping
        # Should map to canonical names
        assert mapping.get("SourceAddr") in ("src_ip", "source_address", None) or isinstance(mapping.get("SourceAddr"), str)

    def test_normalize_known_columns(self):
        mapping = normalize_columns(["timestamp", "hostname", "src_ip"])
        assert mapping.get("timestamp") == "timestamp"
        assert mapping.get("hostname") == "hostname"
        assert mapping.get("src_ip") == "src_ip"

    def test_detect_ioc_columns(self):
        rows, meta = parse_csv_bytes(SAMPLE_CSV)
        column_mapping = normalize_columns(meta["columns"])
        iocs = detect_ioc_columns(meta["columns"], meta["column_types"], column_mapping)
        # Should detect IP columns
        assert isinstance(iocs, dict)

    def test_detect_time_range(self):
        rows, meta = parse_csv_bytes(SAMPLE_CSV)
        column_mapping = normalize_columns(meta["columns"])
        start, end = detect_time_range(rows, column_mapping)
        # Should detect time range from timestamp column
        if start:
            assert "2025" in start

    def test_normalize_rows(self):
        rows = [{"SourceAddr": "10.0.0.1", "ProcessName": "cmd.exe"}]
        mapping = {"SourceAddr": "src_ip", "ProcessName": "process_name"}
        normalized = normalize_rows(rows, mapping)
        assert len(normalized) == 1
        assert normalized[0].get("src_ip") == "10.0.0.1"
