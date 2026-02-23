from pathlib import Path
import re
p=Path(r'd:/Projects/Dev/ThreatHunt/frontend/src/api/client.ts')
t=p.read_text(encoding='utf-8')
# Add HuntProgress interface after Hunt interface
if 'export interface HuntProgress' not in t:
    insert = '''export interface HuntProgress {
  hunt_id: string;
  status: 'idle' | 'processing' | 'ready';
  progress_percent: number;
  dataset_total: number;
  dataset_completed: number;
  dataset_processing: number;
  dataset_errors: number;
  active_jobs: number;
  queued_jobs: number;
  network_status: 'none' | 'building' | 'ready';
  stages: Record<string, any>;
}

'''
    t=t.replace('export interface Hunt {\n  id: string; name: string; description: string | null; status: string;\n  owner_id: string | null; created_at: string; updated_at: string;\n  dataset_count: number; hypothesis_count: number;\n}\n\n', 'export interface Hunt {\n  id: string; name: string; description: string | null; status: string;\n  owner_id: string | null; created_at: string; updated_at: string;\n  dataset_count: number; hypothesis_count: number;\n}\n\n'+insert)

# Add hunts.progress method
if 'progress: (id: string)' not in t:
    t=t.replace("  delete: (id: string) => api(`/api/hunts/${id}`, { method: 'DELETE' }),\n};", "  delete: (id: string) => api(`/api/hunts/${id}`, { method: 'DELETE' }),\n  progress: (id: string) => api<HuntProgress>(`/api/hunts/${id}/progress`),\n};")

# Extend ScanResponse
if 'cache_used?: boolean' not in t:
    t=t.replace('export interface ScanResponse {\n  total_hits: number; hits: ScanHit[]; themes_scanned: number;\n  keywords_scanned: number; rows_scanned: number;\n}\n', 'export interface ScanResponse {\n  total_hits: number; hits: ScanHit[]; themes_scanned: number;\n  keywords_scanned: number; rows_scanned: number;\n  cache_used?: boolean; cache_status?: string; cached_at?: string | null;\n}\n')

# Extend keywords.scan opts
t=t.replace('    scan_hunts?: boolean; scan_annotations?: boolean; scan_messages?: boolean;\n  }) =>', '    scan_hunts?: boolean; scan_annotations?: boolean; scan_messages?: boolean;\n    prefer_cache?: boolean; force_rescan?: boolean;\n  }) =>')

p.write_text(t,encoding='utf-8')
print('updated client.ts')
