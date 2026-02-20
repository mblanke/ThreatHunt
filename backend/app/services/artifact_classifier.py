"""Artifact classifier - identify Velociraptor artifact types from CSV headers."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# (required_columns, artifact_type)
FINGERPRINTS: list[tuple[set[str], str]] = [
    ({"Pid", "Name", "CommandLine", "Exe"}, "Windows.System.Pslist"),
    ({"Pid", "Name", "Ppid", "CommandLine"}, "Windows.System.Pslist"),
    ({"Laddr.IP", "Raddr.IP", "Status", "Pid"}, "Windows.Network.Netstat"),
    ({"Laddr", "Raddr", "Status", "Pid"}, "Windows.Network.Netstat"),
    ({"FamilyString", "TypeString", "Status", "Pid"}, "Windows.Network.Netstat"),
    ({"ServiceName", "DisplayName", "StartMode", "PathName"}, "Windows.System.Services"),
    ({"DisplayName", "PathName", "ServiceDll", "StartMode"}, "Windows.System.Services"),
    ({"OSPath", "Size", "Mtime", "Hash"}, "Windows.Search.FileFinder"),
    ({"FullPath", "Size", "Mtime"}, "Windows.Search.FileFinder"),
    ({"PrefetchFileName", "RunCount", "LastRunTimes"}, "Windows.Forensics.Prefetch"),
    ({"Executable", "RunCount", "LastRunTimes"}, "Windows.Forensics.Prefetch"),
    ({"KeyPath", "Type", "Data"}, "Windows.Registry.Finder"),
    ({"Key", "Type", "Value"}, "Windows.Registry.Finder"),
    ({"EventTime", "Channel", "EventID", "EventData"}, "Windows.EventLogs.EvtxHunter"),
    ({"TimeCreated", "Channel", "EventID", "Provider"}, "Windows.EventLogs.EvtxHunter"),
    ({"Entry", "Category", "Profile", "Launch String"}, "Windows.Sys.Autoruns"),
    ({"Entry", "Category", "LaunchString"}, "Windows.Sys.Autoruns"),
    ({"Name", "Record", "Type", "TTL"}, "Windows.Network.DNS"),
    ({"QueryName", "QueryType", "QueryResults"}, "Windows.Network.DNS"),
    ({"Path", "MD5", "SHA1", "SHA256"}, "Windows.Analysis.Hash"),
    ({"Md5", "Sha256", "FullPath"}, "Windows.Analysis.Hash"),
    ({"Name", "Actions", "NextRunTime", "Path"}, "Windows.System.TaskScheduler"),
    ({"Name", "Uid", "Gid", "Description"}, "Windows.Sys.Users"),
    ({"os_info.hostname", "os_info.system"}, "Server.Information.Client"),
    ({"ClientId", "os_info.fqdn"}, "Server.Information.Client"),
    ({"Pid", "Name", "Cmdline", "Exe"}, "Linux.Sys.Pslist"),
    ({"Laddr", "Raddr", "Status", "FamilyString"}, "Linux.Network.Netstat"),
    ({"Namespace", "ClassName", "PropertyName"}, "Windows.System.WMI"),
    ({"RemoteAddress", "RemoteMACAddress", "InterfaceAlias"}, "Windows.Network.ArpCache"),
    ({"URL", "Title", "VisitCount", "LastVisitTime"}, "Windows.Applications.BrowserHistory"),
    ({"Url", "Title", "Visits"}, "Windows.Applications.BrowserHistory"),
]

VELOCIRAPTOR_META = {"_Source", "ClientId", "FlowId", "Fqdn", "HuntId"}

CATEGORY_MAP = {
    "Pslist": "process",
    "Netstat": "network",
    "Services": "persistence",
    "FileFinder": "filesystem",
    "Prefetch": "execution",
    "Registry": "persistence",
    "EvtxHunter": "eventlog",
    "EventLogs": "eventlog",
    "Autoruns": "persistence",
    "DNS": "network",
    "Hash": "filesystem",
    "TaskScheduler": "persistence",
    "Users": "account",
    "Client": "system",
    "WMI": "persistence",
    "ArpCache": "network",
    "BrowserHistory": "application",
}


def classify_artifact(columns: list[str]) -> str:
    col_set = set(columns)
    for required, artifact_type in FINGERPRINTS:
        if required.issubset(col_set):
            return artifact_type
    if VELOCIRAPTOR_META.intersection(col_set):
        return "Velociraptor.Unknown"
    return "Unknown"


def get_artifact_category(artifact_type: str) -> str:
    for key, category in CATEGORY_MAP.items():
        if key.lower() in artifact_type.lower():
            return category
    return "unknown"