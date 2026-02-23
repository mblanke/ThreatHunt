#!/usr/bin/env python3
"""Generate 12 realistic Velociraptor-style CSV test files.

Mock network: 75 hosts, 10 users, 3 subnets.
Sprinkles AUP-triggering keywords across DNS, URL, and process data.
"""

import csv
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

OUT = Path(__file__).parent / "test_csvs"
OUT.mkdir(exist_ok=True)

# ── Shared network inventory ──────────────────────────────────────────

SUBNETS = ["10.10.1", "10.10.2", "10.10.3"]
DEPARTMENTS = ["IT", "HR", "Finance", "Sales", "Engineering", "Legal", "Marketing", "Exec"]
OS_LIST = ["Windows 10 Enterprise", "Windows 11 Enterprise", "Windows Server 2022", "Windows Server 2019"]
DOMAIN = "acme.local"

HOSTS = []
for i in range(1, 76):
    subnet = SUBNETS[i % 3]
    ip = f"{subnet}.{100 + i}"
    dept = DEPARTMENTS[i % len(DEPARTMENTS)]
    prefix = {"IT": "IT-WS", "HR": "HR-WS", "Finance": "FIN-WS", "Sales": "SLS-WS",
              "Engineering": "ENG-WS", "Legal": "LEG-WS", "Marketing": "MKT-WS", "Exec": "EXEC-WS"}
    hostname = f"{prefix.get(dept, 'WS')}-{i:03d}"
    os_ver = OS_LIST[i % len(OS_LIST)]
    mac = f"00:1A:2B:{i:02X}:{(i*3)%256:02X}:{(i*7)%256:02X}"
    HOSTS.append({"hostname": hostname, "ip": ip, "os": os_ver, "mac": mac, "dept": dept})

SERVERS = [
    {"hostname": "DC-01", "ip": "10.10.1.10", "os": "Windows Server 2022", "mac": "00:1A:2B:AA:01:01"},
    {"hostname": "DC-02", "ip": "10.10.2.10", "os": "Windows Server 2022", "mac": "00:1A:2B:AA:02:02"},
    {"hostname": "FILE-01", "ip": "10.10.1.11", "os": "Windows Server 2019", "mac": "00:1A:2B:AA:03:03"},
    {"hostname": "EXCH-01", "ip": "10.10.1.12", "os": "Windows Server 2022", "mac": "00:1A:2B:AA:04:04"},
    {"hostname": "WEB-01", "ip": "10.10.3.10", "os": "Windows Server 2022", "mac": "00:1A:2B:AA:05:05"},
    {"hostname": "SQL-01", "ip": "10.10.2.11", "os": "Windows Server 2019", "mac": "00:1A:2B:AA:06:06"},
    {"hostname": "PROXY-01", "ip": "10.10.1.13", "os": "Windows Server 2022", "mac": "00:1A:2B:AA:07:07"},
]
ALL_HOSTS = HOSTS + SERVERS

USERS = [
    "jsmith", "agarcia", "bwilson", "cjohnson", "dlee",
    "emartinez", "fthompson", "gwhite", "hbrown", "idavis",
    "admin", "svc_backup", "svc_sql", "svc_web",
]

# Base time range: 2-week window
BASE_TIME = datetime(2026, 2, 10, 8, 0, 0)
END_TIME = datetime(2026, 2, 20, 18, 0, 0)

def rand_ts():
    delta = (END_TIME - BASE_TIME).total_seconds()
    return BASE_TIME + timedelta(seconds=random.uniform(0, delta))

def ts_str(dt=None):
    return (dt or rand_ts()).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def rand_host():
    return random.choice(ALL_HOSTS)

def rand_user():
    return random.choice(USERS)

def rand_ext_ip():
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

# AUP trigger domains/URLs (will be sprinkled into DNS and proxy logs)
AUP_DOMAINS = [
    "www.bet365.com", "pokerstars.com", "draftkings.com",            # Gambling
    "store.steampowered.com", "steamcommunity.com", "discord.gg",    # Gaming
    "www.netflix.com", "hulu.com", "open.spotify.com",               # Streaming
    "thepiratebay.org", "1337x.to", "fitgirl-repacks.site",         # Piracy
    "www.pornhub.com", "onlyfans.com", "xvideos.com",               # Adult
    "www.facebook.com", "www.tiktok.com", "www.reddit.com",         # Social Media
    "www.indeed.com", "www.glassdoor.com", "www.linkedin.com/jobs", # Job Search
    "www.amazon.com", "www.ebay.com", "www.shein.com",              # Shopping
]

AUP_PROCESSES = [
    "utorrent.exe", "qbittorrent.exe", "steam.exe", "discord.exe",
    "spotify.exe", "epicgameslauncher.exe",
]

LEGIT_DOMAINS = [
    "login.microsoftonline.com", "outlook.office365.com", "teams.microsoft.com",
    "graph.microsoft.com", "update.microsoft.com", "windowsupdate.com",
    "acme.sharepoint.com", "acme.local", "dc-01.acme.local", "dc-02.acme.local",
    "file-01.acme.local", "exch-01.acme.local", "github.com", "stackoverflow.com",
    "cdn.jsdelivr.net", "pypi.org", "npmjs.com", "google.com", "googleapis.com",
    "cloudflare.com", "aws.amazon.com", "akamai.net", "time.windows.com",
]

LEGIT_PROCESSES = [
    "svchost.exe", "explorer.exe", "chrome.exe", "msedge.exe", "outlook.exe",
    "teams.exe", "code.exe", "powershell.exe", "cmd.exe", "notepad.exe",
    "taskhostw.exe", "RuntimeBroker.exe", "SearchHost.exe", "lsass.exe",
    "csrss.exe", "winlogon.exe", "dwm.exe", "System", "smss.exe",
    "services.exe", "spoolsv.exe", "MsMpEng.exe", "OneDrive.exe",
]

STATES = ["ESTABLISHED", "LISTEN", "TIME_WAIT", "CLOSE_WAIT", "SYN_SENT"]
PROTOCOLS = ["TCP", "UDP", "TCP", "TCP", "TCP"]

def write_csv(filename, headers, rows):
    path = OUT / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)
    print(f"  {filename}: {len(rows)} rows")

# ═══════════════════════════════════════════════════════════════════════
# 1. Netstat connections (Velociraptor: Windows.Network.Netstat)
# ═══════════════════════════════════════════════════════════════════════

def gen_netstat():
    rows = []
    for host in ALL_HOSTS:
        n_conns = random.randint(8, 40)
        for _ in range(n_conns):
            proc = random.choice(LEGIT_PROCESSES + (AUP_PROCESSES if random.random() < 0.08 else []))
            state = random.choice(STATES)
            proto = random.choice(PROTOCOLS)
            local_port = random.choice([80, 443, 445, 135, 139, 3389, 5985, 8080, 53, 88, 389, 636,
                                        random.randint(49152, 65535)])
            if state == "LISTEN":
                remote_ip = "0.0.0.0"
                remote_port = 0
            else:
                remote_ip = random.choice([rand_ext_ip(), random.choice(ALL_HOSTS)["ip"]])
                remote_port = random.choice([80, 443, 8080, 3389, 445, 53, 88, 389, 636,
                                             random.randint(1024, 65535)])
            rows.append({
                "Hostname": host["hostname"],
                "Timestamp": ts_str(),
                "Pid": random.randint(100, 65000),
                "Name": proc,
                "Status": state,
                "Protocol": proto,
                "Laddr.IP": host["ip"],
                "Laddr.Port": local_port,
                "Raddr.IP": remote_ip,
                "Raddr.Port": remote_port,
                "Username": rand_user(),
            })
    return rows

print("Generating Velociraptor test CSVs...")
rows = gen_netstat()
write_csv("01_netstat_connections.csv",
          ["Hostname", "Timestamp", "Pid", "Name", "Status", "Protocol",
           "Laddr.IP", "Laddr.Port", "Raddr.IP", "Raddr.Port", "Username"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 2. DNS queries (Velociraptor: Windows.Network.DNS)
# ═══════════════════════════════════════════════════════════════════════

def gen_dns():
    rows = []
    for host in ALL_HOSTS:
        n_queries = random.randint(15, 60)
        for _ in range(n_queries):
            if random.random() < 0.12:
                domain = random.choice(AUP_DOMAINS)
            else:
                domain = random.choice(LEGIT_DOMAINS)
            rows.append({
                "Hostname": host["hostname"],
                "EventTime": ts_str(),
                "QueryName": domain,
                "QueryType": random.choice(["A", "AAAA", "CNAME", "MX", "TXT", "A", "A"]),
                "ResponseCode": random.choice(["NOERROR", "NOERROR", "NOERROR", "NXDOMAIN", "SERVFAIL"]),
                "SourceIP": host["ip"],
                "AnswerIP": rand_ext_ip() if random.random() > 0.2 else "",
            })
    return rows

rows = gen_dns()
write_csv("02_dns_queries.csv",
          ["Hostname", "EventTime", "QueryName", "QueryType", "ResponseCode", "SourceIP", "AnswerIP"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 3. Process listing (Velociraptor: Windows.System.Pslist)
# ═══════════════════════════════════════════════════════════════════════

def gen_pslist():
    rows = []
    for host in ALL_HOSTS:
        user = rand_user()
        for proc in LEGIT_PROCESSES:
            pid = random.randint(100, 65000)
            ppid = random.randint(1, 20) if proc in ("svchost.exe", "csrss.exe", "lsass.exe") else random.randint(100, 60000)
            rows.append({
                "ComputerName": host["hostname"],
                "CreateTime": ts_str(),
                "Pid": pid,
                "PPid": ppid,
                "Name": proc,
                "CommandLine": f"C:\\Windows\\System32\\{proc}" if proc != "System" else "System",
                "Username": f"ACME\\{user}" if proc not in ("System", "smss.exe", "csrss.exe") else "NT AUTHORITY\\SYSTEM",
                "MemoryUsage": random.randint(1024, 500000),
            })
        # Sprinkle AUP processes on ~15% of hosts
        if random.random() < 0.15:
            aup_proc = random.choice(AUP_PROCESSES)
            rows.append({
                "ComputerName": host["hostname"],
                "CreateTime": ts_str(),
                "Pid": random.randint(10000, 65000),
                "PPid": random.randint(100, 60000),
                "Name": aup_proc,
                "CommandLine": f"C:\\Users\\{user}\\AppData\\Local\\{aup_proc.replace('.exe', '')}\\{aup_proc}",
                "Username": f"ACME\\{user}",
                "MemoryUsage": random.randint(50000, 400000),
            })
    return rows

rows = gen_pslist()
write_csv("03_process_listing.csv",
          ["ComputerName", "CreateTime", "Pid", "PPid", "Name", "CommandLine", "Username", "MemoryUsage"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 4. Network interfaces (Velociraptor: Windows.Network.Interfaces)
# ═══════════════════════════════════════════════════════════════════════

def gen_interfaces():
    rows = []
    for host in ALL_HOSTS:
        h = host
        rows.append({
            "Hostname": h["hostname"],
            "Timestamp": ts_str(),
            "Name": "Ethernet0",
            "MacAddress": h.get("mac", f"00:1A:2B:{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}"),
            "IP": h["ip"],
            "Netmask": "255.255.255.0",
            "Gateway": h["ip"].rsplit(".", 1)[0] + ".1",
            "DNSServer": "10.10.1.10",
            "DHCPEnabled": random.choice(["True", "False"]),
            "Status": "Up",
        })
        # Some hosts have a secondary NIC
        if random.random() < 0.15:
            rows.append({
                "Hostname": h["hostname"],
                "Timestamp": ts_str(),
                "Name": "WiFi",
                "MacAddress": f"00:1A:2B:{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}",
                "IP": f"192.168.1.{random.randint(100,254)}",
                "Netmask": "255.255.255.0",
                "Gateway": "192.168.1.1",
                "DNSServer": "192.168.1.1",
                "DHCPEnabled": "True",
                "Status": "Up",
            })
    return rows

rows = gen_interfaces()
write_csv("04_network_interfaces.csv",
          ["Hostname", "Timestamp", "Name", "MacAddress", "IP", "Netmask", "Gateway", "DNSServer", "DHCPEnabled", "Status"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 5. Logged-in users (Velociraptor: Windows.Sys.Users)
# ═══════════════════════════════════════════════════════════════════════

def gen_logged_users():
    rows = []
    for host in ALL_HOSTS:
        n_users = random.randint(1, 3)
        used = set()
        for _ in range(n_users):
            u = rand_user()
            while u in used:
                u = rand_user()
            used.add(u)
            logon_ts = rand_ts()
            rows.append({
                "ComputerName": host["hostname"],
                "SourceIP": host["ip"],
                "User": f"ACME\\{u}",
                "LogonType": random.choice([2, 3, 10, 10, 2]),  # 2=Interactive, 3=Network, 10=RDP
                "LogonTime": ts_str(logon_ts),
                "LogoffTime": ts_str(logon_ts + timedelta(hours=random.uniform(0.5, 10))) if random.random() > 0.3 else "",
                "OS": host.get("os", "Windows 10 Enterprise"),
            })
    return rows

rows = gen_logged_users()
write_csv("05_logged_in_users.csv",
          ["ComputerName", "SourceIP", "User", "LogonType", "LogonTime", "LogoffTime", "OS"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 6. Scheduled tasks (Velociraptor: Windows.System.TaskScheduler)
# ═══════════════════════════════════════════════════════════════════════

SCHED_TASKS = [
    ("\\Microsoft\\Windows\\UpdateOrchestrator\\Schedule Scan", "C:\\Windows\\System32\\usoclient.exe StartScan"),
    ("\\Microsoft\\Windows\\Defrag\\ScheduledDefrag", "C:\\Windows\\System32\\defrag.exe -c -h -o"),
    ("\\Microsoft\\Windows\\WindowsUpdate\\Automatic App Update", "C:\\Windows\\System32\\UsoClient.exe"),
    ("\\ACME\\Backup", "C:\\Tools\\backup.ps1"),
    ("\\ACME\\Inventory", "C:\\Tools\\inventory.exe --scan"),
]

def gen_sched_tasks():
    rows = []
    for host in ALL_HOSTS:
        for task_name, cmd in SCHED_TASKS:
            rows.append({
                "Hostname": host["hostname"],
                "IP": host["ip"],
                "TaskName": task_name,
                "CommandLine": cmd,
                "Enabled": random.choice(["True", "True", "True", "False"]),
                "LastRunTime": ts_str(),
                "NextRunTime": ts_str(),
                "Username": "NT AUTHORITY\\SYSTEM" if "Microsoft" in task_name else f"ACME\\svc_backup",
            })
    return rows

rows = gen_sched_tasks()
write_csv("06_scheduled_tasks.csv",
          ["Hostname", "IP", "TaskName", "CommandLine", "Enabled", "LastRunTime", "NextRunTime", "Username"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 7. Browser history (Velociraptor: Windows.Application.Chrome.History)
# ═══════════════════════════════════════════════════════════════════════

def gen_browser_history():
    rows = []
    for host in HOSTS:  # only workstations
        user = rand_user()
        n_entries = random.randint(10, 35)
        for _ in range(n_entries):
            if random.random() < 0.15:
                domain = random.choice(AUP_DOMAINS)
                url = f"https://{domain}/{random.choice(['', 'home', 'watch', 'play', 'search?q=free+movies', 'category/popular'])}"
                title_map = {
                    "bet365": "Bet365 - Sports Betting",
                    "pokerstars": "PokerStars - Online Poker",
                    "netflix": "Netflix - Watch TV Shows",
                    "steam": "Steam Store",
                    "piratebay": "The Pirate Bay",
                    "pornhub": "Pornhub",
                    "facebook": "Facebook - Log In",
                    "tiktok": "TikTok - Make Your Day",
                    "indeed": "Indeed - Job Search",
                    "amazon": "Amazon.com - Shopping",
                }
                title = next((v for k, v in title_map.items() if k in domain), domain)
            else:
                domain = random.choice(LEGIT_DOMAINS)
                url = f"https://{domain}/{random.choice(['', 'docs', 'api', 'search', 'dashboard', 'inbox'])}"
                title = domain
            rows.append({
                "ComputerName": host["hostname"],
                "SourceAddress": host["ip"],
                "User": user,
                "URL": url,
                "Title": title,
                "VisitTime": ts_str(),
                "VisitCount": random.randint(1, 20),
                "Browser": random.choice(["Chrome", "Edge", "Chrome", "Chrome"]),
            })
    return rows

rows = gen_browser_history()
write_csv("07_browser_history.csv",
          ["ComputerName", "SourceAddress", "User", "URL", "Title", "VisitTime", "VisitCount", "Browser"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 8. Sysmon network connections (Sysmon Event ID 3)
# ═══════════════════════════════════════════════════════════════════════

def gen_sysmon_network():
    rows = []
    for host in ALL_HOSTS:
        n_events = random.randint(10, 50)
        user = rand_user()
        for _ in range(n_events):
            proc = random.choice(LEGIT_PROCESSES + (["chrome.exe", "msedge.exe"] * 3))
            dst_ip = random.choice([rand_ext_ip(), random.choice(ALL_HOSTS)["ip"]])
            rows.append({
                "Hostname": host["hostname"],
                "EventTime": ts_str(),
                "EventID": 3,
                "Image": f"C:\\Windows\\System32\\{proc}" if proc not in ("chrome.exe", "msedge.exe") else f"C:\\Program Files\\{proc}",
                "User": f"ACME\\{user}",
                "Protocol": random.choice(["tcp", "udp"]),
                "SourceIp": host["ip"],
                "SourcePort": random.randint(49152, 65535),
                "DestinationIp": dst_ip,
                "DestinationPort": random.choice([80, 443, 53, 445, 389, 3389, 8080]),
                "DestinationHostname": random.choice(LEGIT_DOMAINS + AUP_DOMAINS[:3]) if random.random() < 0.1 else "",
            })
    return rows

rows = gen_sysmon_network()
write_csv("08_sysmon_network.csv",
          ["Hostname", "EventTime", "EventID", "Image", "User", "Protocol",
           "SourceIp", "SourcePort", "DestinationIp", "DestinationPort", "DestinationHostname"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 9. Autoruns (Velociraptor: Windows.Sys.AutoRuns)
# ═══════════════════════════════════════════════════════════════════════

AUTORUN_ENTRIES = [
    ("MicrosoftEdgeAutoLaunch", "C:\\Program Files\\Microsoft\\Edge\\msedge.exe --no-startup-window"),
    ("SecurityHealth", "C:\\Windows\\System32\\SecurityHealthSystray.exe"),
    ("OneDrive", "C:\\Users\\{user}\\AppData\\Local\\Microsoft\\OneDrive\\OneDrive.exe /background"),
    ("WindowsDefender", "C:\\ProgramData\\Microsoft\\Windows Defender\\MsMpEng.exe"),
]

AUP_AUTORUNS = [
    ("Steam", "C:\\Program Files (x86)\\Steam\\steam.exe -silent"),
    ("Discord", "C:\\Users\\{user}\\AppData\\Local\\Discord\\Update.exe --processStart Discord.exe"),
    ("Spotify", "C:\\Users\\{user}\\AppData\\Roaming\\Spotify\\Spotify.exe /minimized"),
    ("uTorrent", "C:\\Users\\{user}\\AppData\\Roaming\\uTorrent\\uTorrent.exe /minimized"),
]

def gen_autoruns():
    rows = []
    for host in ALL_HOSTS:
        user = rand_user()
        for name, cmd in AUTORUN_ENTRIES:
            rows.append({
                "Hostname": host["hostname"],
                "IP": host["ip"],
                "EntryName": name,
                "EntryPath": cmd.replace("{user}", user),
                "Category": "Logon",
                "Enabled": "True",
                "Signer": "Microsoft Corporation" if "Microsoft" in cmd or "Windows" in cmd else "(Not Signed)",
                "MD5": f"{random.randint(0, 2**128):032x}",
                "Timestamp": ts_str(),
            })
        # ~20% of workstations have AUP autoruns
        if host in HOSTS and random.random() < 0.20:
            entry = random.choice(AUP_AUTORUNS)
            rows.append({
                "Hostname": host["hostname"],
                "IP": host["ip"],
                "EntryName": entry[0],
                "EntryPath": entry[1].replace("{user}", user),
                "Category": "Logon",
                "Enabled": "True",
                "Signer": "(Not Signed)",
                "MD5": f"{random.randint(0, 2**128):032x}",
                "Timestamp": ts_str(),
            })
    return rows

rows = gen_autoruns()
write_csv("09_autoruns.csv",
          ["Hostname", "IP", "EntryName", "EntryPath", "Category", "Enabled", "Signer", "MD5", "Timestamp"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 10. Windows Event Logs — Logon events (Event IDs 4624/4625)
# ═══════════════════════════════════════════════════════════════════════

def gen_logon_events():
    rows = []
    for host in ALL_HOSTS:
        n_events = random.randint(8, 30)
        for _ in range(n_events):
            event_id = random.choice([4624, 4624, 4624, 4624, 4625])
            logon_type = random.choice([2, 3, 7, 10, 3, 3])
            user = rand_user()
            src_ip = random.choice([host["ip"], random.choice(ALL_HOSTS)["ip"], "127.0.0.1"])
            rows.append({
                "ComputerName": host["hostname"],
                "System.TimeCreated": ts_str(),
                "EventID": event_id,
                "LogonType": logon_type,
                "SubjectUserName": user,
                "SubjectUserSid": f"S-1-5-21-{random.randint(1000000,9999999)}-{random.randint(1000,9999)}",
                "SourceAddress": src_ip,
                "SourcePort": random.randint(1024, 65535),
                "Status": "0x0" if event_id == 4624 else "0xC000006D",
                "FailureReason": "" if event_id == 4624 else "Unknown user name or bad password",
            })
    return rows

rows = gen_logon_events()
write_csv("10_logon_events.csv",
          ["ComputerName", "System.TimeCreated", "EventID", "LogonType",
           "SubjectUserName", "SubjectUserSid", "SourceAddress", "SourcePort",
           "Status", "FailureReason"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 11. Proxy / web filter logs
# ═══════════════════════════════════════════════════════════════════════

def gen_proxy_logs():
    rows = []
    for host in HOSTS:  # workstations only
        n_entries = random.randint(15, 50)
        user = rand_user()
        for _ in range(n_entries):
            if random.random() < 0.10:
                dom = random.choice(AUP_DOMAINS)
                url = f"https://{dom}/"
                action = random.choice(["BLOCKED", "ALLOWED", "ALLOWED"])
                category = random.choice(["Gambling", "Gaming", "Streaming", "Adult", "Social Media", "Shopping", "Piracy"])
            else:
                dom = random.choice(LEGIT_DOMAINS)
                url = f"https://{dom}/api/v1/resource"
                action = "ALLOWED"
                category = random.choice(["Business", "Technology", "Cloud Services", "Productivity"])
            rows.append({
                "Timestamp": ts_str(),
                "Hostname": host["hostname"],
                "SourceIP": host["ip"],
                "Username": f"ACME\\{user}",
                "URL": url,
                "Domain": dom,
                "Action": action,
                "Category": category,
                "Method": random.choice(["GET", "POST", "GET", "GET"]),
                "ResponseCode": random.choice([200, 200, 200, 301, 403, 404]) if action == "ALLOWED" else 403,
                "BytesSent": random.randint(100, 50000),
                "BytesReceived": random.randint(500, 500000),
            })
    return rows

rows = gen_proxy_logs()
write_csv("11_proxy_logs.csv",
          ["Timestamp", "Hostname", "SourceIP", "Username", "URL", "Domain",
           "Action", "Category", "Method", "ResponseCode", "BytesSent", "BytesReceived"], rows)

# ═══════════════════════════════════════════════════════════════════════
# 12. File listing — suspicious downloads (Velociraptor: Windows.Search.FileFinder)
# ═══════════════════════════════════════════════════════════════════════

DOWNLOAD_FILES = [
    ("Q1_Budget_2026.xlsx", 245000, "a3f1b2c4d5e6f7a8b9c0d1e2f3a4b5c6"),
    ("meeting_notes.docx", 89000, "b4c2d3e5f6a7b8c9d0e1f2a3b4c5d6e7"),
    ("vpn_config.ovpn", 1200, "c5d3e4f6a7b8c9d0e1f2a3b4c5d6e7f8"),
    ("project_plan.pptx", 1500000, "d6e4f5a7b8c9d0e1f2a3b4c5d6e7f8a9"),
    ("setup.exe", 45000000, "e7f5a6b8c9d0e1f2a3b4c5d6e7f8a9b0"),
    ("crack_photoshop.exe", 12000000, "f8a6b7c9d0e1f2a3b4c5d6e7f8a9b0c1"),  # AUP
    ("keygen_v2.exe", 500000, "a9b7c8d0e1f2a3b4c5d6e7f8a9b0c1d2"),          # AUP
    ("steam_installer.exe", 3500000, "b0c8d9e1f2a3b4c5d6e7f8a9b0c1d2e3"),   # AUP
    ("free_movie_2026.torrent", 45000, "c1d9e0f2a3b4c5d6e7f8a9b0c1d2e3f4"), # AUP
    ("salary_comparison.pdf", 320000, "d2e0f1a3b4c5d6e7f8a9b0c1d2e3f4a5"),
]

def gen_file_listing():
    rows = []
    for host in HOSTS:
        user = rand_user()
        n_files = random.randint(3, 8)
        selected = random.sample(DOWNLOAD_FILES, min(n_files, len(DOWNLOAD_FILES)))
        for fname, size, md5 in selected:
            rows.append({
                "Hostname": host["hostname"],
                "SourceIP": host["ip"],
                "FullPath": f"C:\\Users\\{user}\\Downloads\\{fname}",
                "FileName": fname,
                "Size": size,
                "MD5": md5,
                "SHA256": f"{random.randint(0, 2**256):064x}",
                "MTime": ts_str(),
                "CTime": ts_str(),
                "Username": f"ACME\\{user}",
                "OS": host.get("os", "Windows 10 Enterprise"),
            })
    return rows

rows = gen_file_listing()
write_csv("12_file_listing.csv",
          ["Hostname", "SourceIP", "FullPath", "FileName", "Size", "MD5", "SHA256",
           "MTime", "CTime", "Username", "OS"], rows)

# ═══════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════

total = sum(len(list((OUT / f).open())) - 1 for f in os.listdir(OUT) if f.endswith(".csv"))
print(f"\nDone! 12 CSV files in {OUT}")
print(f"Network: {len(ALL_HOSTS)} hosts, {len(USERS)} users, {len(SUBNETS)} subnets")
print(f"AUP triggers in: DNS, browser history, proxy logs, autoruns, file listing, process list, sysmon")
