import json, urllib.request

def get(path):
    return json.loads(urllib.request.urlopen("http://localhost:8000" + path).read())

# Check ip_to_hostname_mapping
ds_list = get("/api/datasets?skip=0&limit=20&hunt_id=fd8ba3fb45de4d65bea072f73d80544d")
for d in ds_list["datasets"]:
    if d["name"] == "ip_to_hostname_mapping":
        rows = get(f"/api/datasets/{d['id']}/rows?offset=0&limit=5")
        print("=== ip_to_hostname_mapping ===")
        for r in rows["rows"]:
            print(r)
    if d["name"] == "Netstat":
        rows = get(f"/api/datasets/{d['id']}/rows?offset=0&limit=3")
        print("=== Netstat ===")
        for r in rows["rows"]:
            print(r)
    if d["name"] == "netstat_enrich2":
        rows = get(f"/api/datasets/{d['id']}/rows?offset=0&limit=3")
        print("=== netstat_enrich2 ===")
        for r in rows["rows"]:
            print(r)