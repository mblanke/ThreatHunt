/* ====================================================================
   ThreatHunt API Client — mirrors every backend endpoint.
   All requests go through the CRA proxy (see package.json "proxy").
   ==================================================================== */

const BASE = '';  // proxied to http://localhost:8000 by CRA

// ── Helpers ──────────────────────────────────────────────────────────

let authToken: string | null = localStorage.getItem('th_token');

export function setToken(t: string | null) {
  authToken = t;
  if (t) localStorage.setItem('th_token', t);
  else localStorage.removeItem('th_token');
}
export function getToken() { return authToken; }

async function api<T = any>(
  path: string,
  opts: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string> || {}),
  };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  if (!(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';

  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return res.text() as unknown as T;
}

// ── Auth ─────────────────────────────────────────────────────────────

export interface UserPayload {
  id: string; username: string; email: string;
  display_name: string | null; role: string; is_active: boolean; created_at: string;
}
export interface AuthPayload {
  user: UserPayload;
  tokens: { access_token: string; refresh_token: string; token_type: string };
}

export const auth = {
  register: (username: string, email: string, password: string, display_name?: string) =>
    api<AuthPayload>('/api/auth/register', {
      method: 'POST', body: JSON.stringify({ username, email, password, display_name }),
    }),
  login: (username: string, password: string) =>
    api<AuthPayload>('/api/auth/login', {
      method: 'POST', body: JSON.stringify({ username, password }),
    }),
  refresh: (refresh_token: string) =>
    api<AuthPayload>('/api/auth/refresh', {
      method: 'POST', body: JSON.stringify({ refresh_token }),
    }),
  me: () => api<UserPayload>('/api/auth/me'),
};

// ── Hunts ────────────────────────────────────────────────────────────

export interface Hunt {
  id: string; name: string; description: string | null; status: string;
  owner_id: string | null; created_at: string; updated_at: string;
  dataset_count: number; hypothesis_count: number;
}

export const hunts = {
  list: (skip = 0, limit = 50) =>
    api<{ hunts: Hunt[]; total: number }>(`/api/hunts?skip=${skip}&limit=${limit}`),
  get: (id: string) => api<Hunt>(`/api/hunts/${id}`),
  create: (name: string, description?: string) =>
    api<Hunt>('/api/hunts', { method: 'POST', body: JSON.stringify({ name, description }) }),
  update: (id: string, data: Partial<{ name: string; description: string; status: string }>) =>
    api<Hunt>(`/api/hunts/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => api(`/api/hunts/${id}`, { method: 'DELETE' }),
};

// ── Datasets ─────────────────────────────────────────────────────────

export interface DatasetSummary {
  id: string; name: string; filename: string; source_tool: string | null;
  row_count: number; column_schema: Record<string, string> | null;
  normalized_columns: Record<string, string> | null;
  ioc_columns: Record<string, string[]> | null;
  file_size_bytes: number; encoding: string | null; delimiter: string | null;
  time_range_start: string | null; time_range_end: string | null;
  hunt_id: string | null; created_at: string;
}

export interface UploadResult {
  id: string; name: string; row_count: number; columns: string[];
  column_types: Record<string, string>; normalized_columns: Record<string, string>;
  ioc_columns: Record<string, string[]>; message: string;
}

export const datasets = {
  list: (skip = 0, limit = 50, huntId?: string) => {
    let qs = `/api/datasets?skip=${skip}&limit=${limit}`;
    if (huntId) qs += `&hunt_id=${encodeURIComponent(huntId)}`;
    return api<{ datasets: DatasetSummary[]; total: number }>(qs);
  },
  get: (id: string) => api<DatasetSummary>(`/api/datasets/${id}`),
  rows: (id: string, offset = 0, limit = 100) =>
    api<{ rows: Record<string, any>[]; total: number; offset: number; limit: number }>(
      `/api/datasets/${id}/rows?offset=${offset}&limit=${limit}`,
    ),
  upload: (file: File, huntId?: string) => {
    const fd = new FormData();
    fd.append('file', file);
    const qs = huntId ? `?hunt_id=${encodeURIComponent(huntId)}` : '';
    return api<UploadResult>(`/api/datasets/upload${qs}`, { method: 'POST', body: fd });
  },
  /** Upload with real progress percentage via XMLHttpRequest. */
  uploadWithProgress: (
    file: File,
    huntId?: string,
    onProgress?: (pct: number) => void,
  ): Promise<UploadResult> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const fd = new FormData();
      fd.append('file', file);
      const qs = huntId ? `?hunt_id=${encodeURIComponent(huntId)}` : '';

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          try {
            const body = JSON.parse(xhr.responseText);
            reject(new Error(body.detail || `HTTP ${xhr.status}`));
          } catch { reject(new Error(`HTTP ${xhr.status}`)); }
        }
      });
      xhr.addEventListener('error', () => reject(new Error('Network error')));
      xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));

      xhr.open('POST', `${BASE}/api/datasets/upload${qs}`);
      if (authToken) xhr.setRequestHeader('Authorization', `Bearer ${authToken}`);
      xhr.send(fd);
    });
  },
  delete: (id: string) => api(`/api/datasets/${id}`, { method: 'DELETE' }),
};

// ── Agent ────────────────────────────────────────────────────────────

export interface AssistRequest {
  query: string;
  dataset_name?: string; artifact_type?: string; host_identifier?: string;
  data_summary?: string; conversation_history?: { role: string; content: string }[];
  active_hypotheses?: string[]; annotations_summary?: string;
  enrichment_summary?: string; mode?: 'quick' | 'deep' | 'debate';
  model_override?: string; conversation_id?: string; hunt_id?: string;
}

export interface AssistResponse {
  guidance: string; confidence: number; suggested_pivots: string[];
  suggested_filters: string[]; caveats: string | null; reasoning: string | null;
  sans_references: string[]; model_used: string; node_used: string;
  latency_ms: number; perspectives: Record<string, any>[] | null;
  conversation_id: string | null;
}

export interface NodeInfo { url: string; available: boolean }
export interface HealthInfo {
  status: string;
  nodes: { wile: NodeInfo; roadrunner: NodeInfo; cluster: NodeInfo };
  rag: { available: boolean; url: string; model: string };
  default_models: Record<string, string>;
  config: { max_tokens: number; temperature: number };
}

export const agent = {
  assist: (req: AssistRequest) =>
    api<AssistResponse>('/api/agent/assist', { method: 'POST', body: JSON.stringify(req) }),
  health: () => api<HealthInfo>('/api/agent/health'),
  models: () => api<Record<string, any>>('/api/agent/models'),
  /** Returns a ReadableStream for SSE streaming */
  assistStream: async (req: AssistRequest): Promise<Response> => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    return fetch(`${BASE}/api/agent/assist/stream`, {
      method: 'POST', headers, body: JSON.stringify(req),
    });
  },
};

// ── Annotations ──────────────────────────────────────────────────────

export interface AnnotationData {
  id: string; row_id: number | null; dataset_id: string | null;
  author_id: string | null; text: string; severity: string;
  tag: string | null; highlight_color: string | null;
  created_at: string; updated_at: string;
}

export const annotations = {
  list: (params?: { dataset_id?: string; severity?: string; tag?: string; skip?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.dataset_id) q.set('dataset_id', params.dataset_id);
    if (params?.severity) q.set('severity', params.severity);
    if (params?.tag) q.set('tag', params.tag);
    if (params?.skip) q.set('skip', String(params.skip));
    if (params?.limit) q.set('limit', String(params.limit));
    return api<{ annotations: AnnotationData[]; total: number }>(`/api/annotations?${q}`);
  },
  create: (data: { row_id?: number; dataset_id?: string; text: string; severity?: string; tag?: string; highlight_color?: string }) =>
    api<AnnotationData>('/api/annotations', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<{ text: string; severity: string; tag: string; highlight_color: string }>) =>
    api<AnnotationData>(`/api/annotations/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => api(`/api/annotations/${id}`, { method: 'DELETE' }),
};

// ── Hypotheses ───────────────────────────────────────────────────────

export interface HypothesisData {
  id: string; hunt_id: string | null; title: string; description: string | null;
  mitre_technique: string | null; status: string;
  evidence_row_ids: number[] | null; evidence_notes: string | null;
  created_at: string; updated_at: string;
}

export const hypotheses = {
  list: (params?: { hunt_id?: string; status?: string; skip?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.hunt_id) q.set('hunt_id', params.hunt_id);
    if (params?.status) q.set('status', params.status);
    if (params?.skip) q.set('skip', String(params.skip));
    if (params?.limit) q.set('limit', String(params.limit));
    return api<{ hypotheses: HypothesisData[]; total: number }>(`/api/hypotheses?${q}`);
  },
  create: (data: { hunt_id?: string; title: string; description?: string; mitre_technique?: string; status?: string }) =>
    api<HypothesisData>('/api/hypotheses', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<{ title: string; description: string; mitre_technique: string; status: string; evidence_row_ids: number[]; evidence_notes: string }>) =>
    api<HypothesisData>(`/api/hypotheses/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => api(`/api/hypotheses/${id}`, { method: 'DELETE' }),
};

// ── Enrichment ───────────────────────────────────────────────────────

export interface EnrichmentResult {
  ioc_value: string; ioc_type: string; source: string; verdict: string;
  score: number; tags: string[]; country: string; asn: string; org: string;
  last_seen: string; raw_data: Record<string, any>; error: string;
  latency_ms: number;
}

export const enrichment = {
  ioc: (ioc_value: string, ioc_type: string, skip_cache = false) =>
    api<{ ioc_value: string; ioc_type: string; results: EnrichmentResult[]; overall_verdict: string; overall_score: number }>(
      '/api/enrichment/ioc', { method: 'POST', body: JSON.stringify({ ioc_value, ioc_type, skip_cache }) },
    ),
  batch: (iocs: { value: string; type: string }[]) =>
    api<{ results: Record<string, EnrichmentResult[]>; total_enriched: number }>(
      '/api/enrichment/batch', { method: 'POST', body: JSON.stringify({ iocs }) },
    ),
  dataset: (datasetId: string) =>
    api<{ dataset_id: string; iocs_found: number; enriched: number; results: Record<string, any> }>(
      `/api/enrichment/dataset/${datasetId}`, { method: 'POST' },
    ),
  status: () => api<Record<string, any>>('/api/enrichment/status'),
};

// ── Correlation ──────────────────────────────────────────────────────

export interface CorrelationResult {
  hunt_ids: string[]; summary: string; total_correlations: number;
  ioc_overlaps: any[]; time_overlaps: any[]; technique_overlaps: any[];
  host_overlaps: any[];
}

export const correlation = {
  analyze: (hunt_ids: string[]) =>
    api<CorrelationResult>('/api/correlation/analyze', {
      method: 'POST', body: JSON.stringify({ hunt_ids }),
    }),
  all: () => api<CorrelationResult>('/api/correlation/all'),
  ioc: (ioc_value: string) =>
    api<{ ioc_value: string; occurrences: any[]; total: number }>(`/api/correlation/ioc/${encodeURIComponent(ioc_value)}`),
};

// ── Reports ──────────────────────────────────────────────────────────

export const reports = {
  json: (huntId: string) =>
    api<Record<string, any>>(`/api/reports/hunt/${huntId}?format=json`),
  html: (huntId: string) =>
    api<string>(`/api/reports/hunt/${huntId}?format=html`),
  csv: (huntId: string) =>
    api<string>(`/api/reports/hunt/${huntId}?format=csv`),
  summary: (huntId: string) =>
    api<Record<string, any>>(`/api/reports/hunt/${huntId}/summary`),
};

// ── Root / misc ──────────────────────────────────────────────────────

export const misc = {
  root: () => api<{ name: string; version: string; status: string }>('/'),
};

// ── AUP Keywords ─────────────────────────────────────────────────────

export interface KeywordOut {
  id: number; theme_id: string; value: string; is_regex: boolean; created_at: string;
}
export interface ThemeOut {
  id: string; name: string; color: string; enabled: boolean; is_builtin: boolean;
  created_at: string; keyword_count: number; keywords: KeywordOut[];
}
export interface ScanHit {
  theme_name: string; theme_color: string; keyword: string;
  source_type: string; source_id: string | number; field: string;
  matched_value: string; row_index: number | null; dataset_name: string | null;
}
export interface ScanResponse {
  total_hits: number; hits: ScanHit[]; themes_scanned: number;
  keywords_scanned: number; rows_scanned: number;
}

export const keywords = {
  // Theme CRUD
  listThemes: () =>
    api<{ themes: ThemeOut[]; total: number }>('/api/keywords/themes'),
  createTheme: (name: string, color?: string, enabled?: boolean) =>
    api<ThemeOut>('/api/keywords/themes', {
      method: 'POST', body: JSON.stringify({ name, color, enabled }),
    }),
  updateTheme: (id: string, data: Partial<{ name: string; color: string; enabled: boolean }>) =>
    api<ThemeOut>(`/api/keywords/themes/${id}`, {
      method: 'PUT', body: JSON.stringify(data),
    }),
  deleteTheme: (id: string) =>
    api(`/api/keywords/themes/${id}`, { method: 'DELETE' }),

  // Keyword CRUD
  addKeyword: (themeId: string, value: string, is_regex = false) =>
    api<KeywordOut>(`/api/keywords/themes/${themeId}/keywords`, {
      method: 'POST', body: JSON.stringify({ value, is_regex }),
    }),
  addKeywordsBulk: (themeId: string, values: string[], is_regex = false) =>
    api<{ added: number; theme_id: string }>(`/api/keywords/themes/${themeId}/keywords/bulk`, {
      method: 'POST', body: JSON.stringify({ values, is_regex }),
    }),
  deleteKeyword: (keywordId: number) =>
    api(`/api/keywords/keywords/${keywordId}`, { method: 'DELETE' }),

  // Scanning
  scan: (opts: {
    dataset_ids?: string[]; theme_ids?: string[];
    scan_hunts?: boolean; scan_annotations?: boolean; scan_messages?: boolean;
  }) =>
    api<ScanResponse>('/api/keywords/scan', {
      method: 'POST', body: JSON.stringify(opts),
    }),
  quickScan: (datasetId: string) =>
    api<ScanResponse>(`/api/keywords/scan/quick?dataset_id=${encodeURIComponent(datasetId)}`),
};
