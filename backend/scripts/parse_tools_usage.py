import csv
import re
import os
from glob import glob

# 1. Extract tool/process names from the Markdown file
def extract_tools(md_path):
    tools = set()
    with open(md_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip headers and empty lines
            if not line or line.endswith(':') or line.startswith('<!--'):
                continue
            # Only keep lines that look like process/tool names
            if re.match(r'^[\w\-.@]+(\.exe|\.dll|\.sys)?$', line, re.IGNORECASE):
                tools.add(line.lower())
    return tools

# 2. Parse the CSV file and build mapping
def parse_csv(csv_path, tools):
    tool_hosts = {}
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            host = row.get('host') or row.get('hostname')
            proc = row.get('process') or row.get('process_name') or row.get('image')
            if not host or not proc:
                continue
            proc = proc.lower()
            if proc in tools:
                tool_hosts.setdefault(proc, set()).add(host)
    return tool_hosts

# 3. Output the breakdown
def main():
    md_path = r'd:\Dev\ThreatHunt\backend\lists\security-tools.md'
    upload_dir = r'd:\Dev\ThreatHunt\uploaded'
    tools = extract_tools(md_path)
    csv_files = glob(os.path.join(upload_dir, '*.csv'))

    for csv_path in csv_files:
        print(f"\nResults for: {os.path.basename(csv_path)}")
        tool_hosts = parse_csv(csv_path, tools)
        if not tool_hosts:
            print("  No known tools found.")
            continue
        for tool, hosts in sorted(tool_hosts.items()):
            print(f"  {tool}: {', '.join(sorted(hosts))}")

if __name__ == '__main__':
    main()
