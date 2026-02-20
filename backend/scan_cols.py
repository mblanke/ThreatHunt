import json, urllib.request
url = "http://localhost:8000/api/datasets?skip=0&limit=20&hunt_id=fd8ba3fb45de4d65bea072f73d80544d"
data = json.loads(urllib.request.urlopen(url).read())
for d in data["datasets"]:
    ioc = list((d["ioc_columns"] or {}).items())
    norm = d.get("normalized_columns") or {}
    hc = {k: v for k, v in norm.items() if v in ("hostname", "fqdn", "username", "src_ip", "dst_ip", "ip_address", "os")}
    print(d["name"], "|", d["row_count"], "|", ioc, "|", hc)