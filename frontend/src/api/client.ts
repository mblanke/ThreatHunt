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

/** Alias kept for backward-compat with components that import HuntOut */
export type HuntOut = Hunt;

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

// ── Network Picture ──────────────────────────────────────────────────

export interface HostEntry {
  hostname: string;
  ips: string[];
  users: string[];
  os: string[];
  mac_addresses: string[];
  protocols: string[];
  open_ports: string[];
  remote_targets: string[];
  datasets: string[];
  connection_count: number;
  first_seen: string | null;
  last_seen: string | null;
}

export interface PictureSummary {
  total_hosts: number;
  total_connections: number;
  total_unique_ips: number;
  datasets_scanned: number;
}

export interface NetworkPictureResponse {
  hosts: HostEntry[];
  summary: PictureSummary;
}

export const network = {
  picture: (huntId: string) =>
    api<NetworkPictureResponse>(`/api/network/picture?hunt_id=${encodeURIComponent(huntId)}`),
};

// ── Analysis (Process Tree / Storyline / Risk) ───────────────────────

export interface ProcessNodeData {
  pid: string; ppid: string; name: string; command_line: string;
  username: string; hostname: string; timestamp: string;
  dataset_name: string; row_index: number;
  children: ProcessNodeData[]; extra: Record<string, string>;
}

export interface ProcessTreeResponse {
  trees: ProcessNodeData[];
  total_processes: number;
}

export interface StorylineNode {
  data: {
    id: string; label: string; event_type: string; hostname: string;
    timestamp: string; pid: string; ppid: string; process_name: string;
    command_line: string; username: string; src_ip: string; dst_ip: string;
    dst_port: string; file_path: string; severity: string;
    dataset_id: string; row_index: number;
  };
}

export interface StorylineEdge {
  data: {
    id: string; source: string; target: string; relationship: string;
  };
}

export interface StorylineResponse {
  nodes: StorylineNode[];
  edges: StorylineEdge[];
  summary: {
    total_events: number; total_edges: number;
    hosts: string[]; event_types: Record<string, number>;
  };
}

export interface RiskHost {
  hostname: string; score: number; signals: string[];
  event_count: number; process_count: number;
  network_count: number; file_count: number;
}

export interface RiskSummaryResponse {
  hosts: RiskHost[];
  overall_score: number;
  total_events: number;
  severity_breakdown: Record<string, number>;
}

export const analysis = {
  processTree: (params: { dataset_id?: string; hunt_id?: string; hostname?: string }) => {
    const q = new URLSearchParams();
    if (params.dataset_id) q.set('dataset_id', params.dataset_id);
    if (params.hunt_id) q.set('hunt_id', params.hunt_id);
    if (params.hostname) q.set('hostname', params.hostname);
    return api<ProcessTreeResponse>(`/api/analysis/process-tree?${q}`);
  },
  storyline: (params: { dataset_id?: string; hunt_id?: string; hostname?: string }) => {
    const q = new URLSearchParams();
    if (params.dataset_id) q.set('dataset_id', params.dataset_id);
    if (params.hunt_id) q.set('hunt_id', params.hunt_id);
    if (params.hostname) q.set('hostname', params.hostname);
    return api<StorylineResponse>(`/api/analysis/storyline?${q}`);
  },
  riskSummary: (huntId?: string) => {
    const q = huntId ? `?hunt_id=${encodeURIComponent(huntId)}` : '';
    return api<RiskSummaryResponse>(`/api/analysis/risk-summary${q}`);
  },
  llmAnalyze: (params: {
    dataset_id?: string; hunt_id?: string; question?: string;
    mode?: 'quick' | 'deep'; focus?: string;
  }) =>
    api<LLMAnalysisResult>('/api/analysis/llm-analyze', {
      method: 'POST', body: JSON.stringify(params),
    }),

  // Timeline & Search
  timeline: (params: { dataset_id?: string; hunt_id?: string; bins?: number }) => {
    const q = new URLSearchParams();
    if (params.dataset_id) q.set('dataset_id', params.dataset_id);
    if (params.hunt_id) q.set('hunt_id', params.hunt_id);
    if (params.bins) q.set('bins', String(params.bins));
    return api<TimelineBinsResponse>(`/api/analysis/timeline?${q}`);
  },
  fieldStats: (params: { dataset_id?: string; hunt_id?: string; fields?: string; top_n?: number }) => {
    const q = new URLSearchParams();
    if (params.dataset_id) q.set('dataset_id', params.dataset_id);
    if (params.hunt_id) q.set('hunt_id', params.hunt_id);
    if (params.fields) q.set('fields', params.fields);
    if (params.top_n) q.set('top_n', String(params.top_n));
    return api<FieldStatsResponse>(`/api/analysis/field-stats?${q}`);
  },
  searchRows: (params: SearchRowsRequest) =>
    api<SearchRowsResponse>('/api/analysis/search', {
      method: 'POST', body: JSON.stringify(params),
    }),

  // MITRE ATT&CK
  mitreMap: (params: { dataset_id?: string; hunt_id?: string }) => {
    const q = new URLSearchParams();
    if (params.dataset_id) q.set('dataset_id', params.dataset_id);
    if (params.hunt_id) q.set('hunt_id', params.hunt_id);
    return api<MitreMapResponse>(`/api/analysis/mitre-map?${q}`);
  },
  knowledgeGraph: (params: { dataset_id?: string; hunt_id?: string }) => {
    const q = new URLSearchParams();
    if (params.dataset_id) q.set('dataset_id', params.dataset_id);
    if (params.hunt_id) q.set('hunt_id', params.hunt_id);
    return api<KnowledgeGraphResponse>(`/api/analysis/knowledge-graph?${q}`);
  },
};

// ── LLM Analysis types ───────────────────────────────────────────────

export interface LLMAnalysisResult {
  analysis: string;
  confidence: number;
  key_findings: string[];
  iocs_identified: { type: string; value: string; context: string }[];
  recommended_actions: string[];
  mitre_techniques: string[];
  risk_score: number;
  model_used: string;
  node_used: string;
  latency_ms: number;
  rows_analyzed: number;
  dataset_summary: string;
}

// ── Timeline & Search types ──────────────────────────────────────────

export interface TimelineBin {
  start: string;
  end: string;
  count: number;
  types: Record<string, number>;
}
export interface TimelineBinsResponse {
  bins: TimelineBin[];
  total: number;
  time_range: { start: string; end: string };
}

export interface FieldStatEntry {
  value: string;
  count: number;
  pct: number;
}
export interface FieldStatsResponse {
  fields: Record<string, { total: number; unique: number; top: FieldStatEntry[] }>;
  total_rows: number;
}

export interface SearchRowsRequest {
  dataset_id?: string;
  hunt_id?: string;
  query?: string;
  filters?: Record<string, string>;
  time_start?: string;
  time_end?: string;
  limit?: number;
  offset?: number;
}
export interface SearchRowsResponse {
  rows: Record<string, any>[];
  total: number;
  offset: number;
  limit: number;
}

// ── MITRE ATT&CK types ──────────────────────────────────────────────

export interface MitreTechnique {
  id: string;
  name: string;
  count: number;
  evidence: { row_index: number; field: string; value: string; pattern: string }[];
}
export interface MitreTactic {
  id: string;
  name: string;
  techniques: MitreTechnique[];
  total_hits: number;
}
export interface MitreMapResponse {
  tactics: MitreTactic[];
  coverage: {
    tactics_covered: number;
    tactics_total: number;
    techniques_matched: number;
    total_evidence: number;
  };
  total_rows: number;
}

export interface KnowledgeGraphResponse {
  nodes: { data: { id: string; label: string; type: string; color: string; shape: string; tactic?: string } }[];
  edges: { data: { source: string; target: string; weight: number; label: string } }[];
  stats: {
    total_nodes: number;
    total_edges: number;
    entity_counts: Record<string, number>;
    techniques_found: number;
  };
}

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

// ── Case Management ──────────────────────────────────────────────────

// ── Alerts & Analyzers ───────────────────────────────────────────────

export interface AlertData {
  id: string;
  title: string;
  description: string | null;
  severity: string;
  status: string;
  analyzer: string;
  score: number;
  evidence: Record<string, any>[];
  mitre_technique: string | null;
  tags: string[];
  hunt_id: string | null;
  dataset_id: string | null;
  case_id: string | null;
  assignee: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertStats {
  total: number;
  severity_counts: Record<string, number>;
  status_counts: Record<string, number>;
  analyzer_counts: Record<string, number>;
  top_mitre: { technique: string; count: number }[];
}

export interface AlertRuleData {
  id: string;
  name: string;
  description: string | null;
  analyzer: string;
  config: Record<string, any> | null;
  severity_override: string | null;
  enabled: boolean;
  hunt_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnalyzerInfo {
  name: string;
  description: string;
}

export interface AnalyzeResult {
  candidates_found: number;
  alerts_created: number;
  alerts: AlertData[];
  summary: {
    by_severity: Record<string, number>;
    by_analyzer: Record<string, number>;
    rows_analyzed: number;
  };
}

export const alerts = {
  list: (opts?: { status?: string; severity?: string; analyzer?: string; hunt_id?: string; dataset_id?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (opts?.status) q.set('status', opts.status);
    if (opts?.severity) q.set('severity', opts.severity);
    if (opts?.analyzer) q.set('analyzer', opts.analyzer);
    if (opts?.hunt_id) q.set('hunt_id', opts.hunt_id);
    if (opts?.dataset_id) q.set('dataset_id', opts.dataset_id);
    if (opts?.limit) q.set('limit', String(opts.limit));
    if (opts?.offset) q.set('offset', String(opts.offset));
    return api<{ alerts: AlertData[]; total: number }>(`/api/alerts?${q}`);
  },
  stats: (huntId?: string) => {
    const q = huntId ? `?hunt_id=${encodeURIComponent(huntId)}` : '';
    return api<AlertStats>(`/api/alerts/stats${q}`);
  },
  get: (id: string) => api<AlertData>(`/api/alerts/${id}`),
  update: (id: string, data: { status?: string; severity?: string; assignee?: string; case_id?: string; tags?: string[] }) =>
    api<AlertData>(`/api/alerts/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) =>
    api(`/api/alerts/${id}`, { method: 'DELETE' }),
  bulkUpdate: (alertIds: string[], status: string) =>
    api<{ updated: number }>(`/api/alerts/bulk-update?status=${encodeURIComponent(status)}`, {
      method: 'POST', body: JSON.stringify(alertIds),
    }),
  analyzers: () =>
    api<{ analyzers: AnalyzerInfo[] }>('/api/alerts/analyzers/list'),
  analyze: (params: { dataset_id?: string; hunt_id?: string; analyzers?: string[]; config?: Record<string, any>; auto_create?: boolean }) =>
    api<AnalyzeResult>('/api/alerts/analyze', {
      method: 'POST', body: JSON.stringify(params),
    }),
  listRules: (enabled?: boolean) => {
    const q = enabled !== undefined ? `?enabled=${enabled}` : '';
    return api<{ rules: AlertRuleData[] }>(`/api/alerts/rules/list${q}`);
  },
  createRule: (data: { name: string; description?: string; analyzer: string; config?: Record<string, any>; severity_override?: string; enabled?: boolean; hunt_id?: string }) =>
    api<AlertRuleData>('/api/alerts/rules', { method: 'POST', body: JSON.stringify(data) }),
  updateRule: (id: string, data: Partial<AlertRuleData>) =>
    api<AlertRuleData>(`/api/alerts/rules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteRule: (id: string) =>
    api(`/api/alerts/rules/${id}`, { method: 'DELETE' }),
};

// ── Case Management (continued) ──────────────────────────────────────

export interface CaseData {
  id: string;
  title: string;
  description: string | null;
  severity: string;
  tlp: string;
  pap: string;
  status: string;
  priority: number;
  assignee: string | null;
  tags: string[];
  hunt_id: string | null;
  owner_id: string | null;
  mitre_techniques: string[];
  iocs: { type: string; value: string; description?: string }[];
  started_at: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  tasks: CaseTaskData[];
}
export interface CaseTaskData {
  id: string;
  case_id: string;
  title: string;
  description: string | null;
  status: string;
  assignee: string | null;
  order: number;
  created_at: string;
  updated_at: string;
}
export interface ActivityLogEntry {
  id: number;
  action: string;
  details: Record<string, any> | null;
  user_id: string | null;
  created_at: string;
}

export const cases = {
  list: (opts?: { status?: string; hunt_id?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (opts?.status) q.set('status', opts.status);
    if (opts?.hunt_id) q.set('hunt_id', opts.hunt_id);
    if (opts?.limit) q.set('limit', String(opts.limit));
    if (opts?.offset) q.set('offset', String(opts.offset));
    return api<{ cases: CaseData[]; total: number }>(`/api/cases?${q}`);
  },
  get: (id: string) => api<CaseData>(`/api/cases/${id}`),
  create: (data: Partial<CaseData>) =>
    api<CaseData>('/api/cases', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<CaseData>) =>
    api<CaseData>(`/api/cases/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) =>
    api(`/api/cases/${id}`, { method: 'DELETE' }),
  addTask: (caseId: string, data: { title: string; description?: string; assignee?: string }) =>
    api<CaseTaskData>(`/api/cases/${caseId}/tasks`, { method: 'POST', body: JSON.stringify(data) }),
  updateTask: (caseId: string, taskId: string, data: Partial<CaseTaskData>) =>
    api<CaseTaskData>(`/api/cases/${caseId}/tasks/${taskId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTask: (caseId: string, taskId: string) =>
    api(`/api/cases/${caseId}/tasks/${taskId}`, { method: 'DELETE' }),
  activity: (caseId: string, limit = 50) =>
    api<{ logs: ActivityLogEntry[] }>(`/api/cases/${caseId}/activity?limit=${limit}`),
};

// ── Notebooks & Playbooks ────────────────────────────────────────────

export interface NotebookCell {
  id: string;
  cell_type: string;
  source: string;
  output: string | null;
  metadata: Record<string, any>;
}
export interface NotebookData {
  id: string;
  title: string;
  description: string | null;
  cells: NotebookCell[];
  hunt_id: string | null;
  case_id: string | null;
  owner_id: string | null;
  tags: string[];
  cell_count: number;
  created_at: string;
  updated_at: string;
}
export interface PlaybookTemplate {
  name: string;
  description: string;
  category: string;
  tags: string[];
  step_count: number;
}
export interface PlaybookStep {
  order: number;
  title: string;
  description: string;
  action: string;
  action_config: Record<string, any>;
  expected_outcome: string;
}
export interface PlaybookTemplateDetail extends PlaybookTemplate {
  steps: PlaybookStep[];
}
export interface PlaybookRunData {
  id: string;
  playbook_name: string;
  status: string;
  current_step: number;
  total_steps: number;
  step_results: { step: number; status: string; notes: string | null; completed_at: string }[];
  hunt_id: string | null;
  case_id: string | null;
  started_by: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  steps?: PlaybookStep[];
}

export const notebooks = {
  list: (opts?: { hunt_id?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (opts?.hunt_id) q.set('hunt_id', opts.hunt_id);
    if (opts?.limit) q.set('limit', String(opts.limit));
    if (opts?.offset) q.set('offset', String(opts.offset));
    return api<{ notebooks: NotebookData[]; total: number }>(`/api/notebooks?${q}`);
  },
  get: (id: string) => api<NotebookData>(`/api/notebooks/${id}`),
  create: (data: { title: string; description?: string; cells?: Partial<NotebookCell>[]; hunt_id?: string; case_id?: string; tags?: string[] }) =>
    api<NotebookData>('/api/notebooks', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: { title?: string; description?: string; cells?: Partial<NotebookCell>[]; tags?: string[] }) =>
    api<NotebookData>(`/api/notebooks/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  upsertCell: (notebookId: string, cell: { cell_id: string; cell_type?: string; source?: string; output?: string; metadata?: Record<string, any> }) =>
    api<NotebookData>(`/api/notebooks/${notebookId}/cells`, { method: 'POST', body: JSON.stringify(cell) }),
  deleteCell: (notebookId: string, cellId: string) =>
    api(`/api/notebooks/${notebookId}/cells/${cellId}`, { method: 'DELETE' }),
  delete: (id: string) =>
    api(`/api/notebooks/${id}`, { method: 'DELETE' }),
};

export const playbooks = {
  templates: () =>
    api<{ templates: PlaybookTemplate[] }>('/api/notebooks/playbooks/templates'),
  templateDetail: (name: string) =>
    api<PlaybookTemplateDetail>(`/api/notebooks/playbooks/templates/${encodeURIComponent(name)}`),
  start: (data: { playbook_name: string; hunt_id?: string; case_id?: string; started_by?: string }) =>
    api<PlaybookRunData>('/api/notebooks/playbooks/start', { method: 'POST', body: JSON.stringify(data) }),
  listRuns: (opts?: { status?: string; hunt_id?: string }) => {
    const q = new URLSearchParams();
    if (opts?.status) q.set('status', opts.status);
    if (opts?.hunt_id) q.set('hunt_id', opts.hunt_id);
    return api<{ runs: PlaybookRunData[] }>(`/api/notebooks/playbooks/runs?${q}`);
  },
  getRun: (runId: string) =>
    api<PlaybookRunData>(`/api/notebooks/playbooks/runs/${runId}`),
  completeStep: (runId: string, data: { notes?: string; status?: string }) =>
    api<PlaybookRunData>(`/api/notebooks/playbooks/runs/${runId}/complete-step`, {
      method: 'POST', body: JSON.stringify(data),
    }),
  abortRun: (runId: string) =>
    api<PlaybookRunData>(`/api/notebooks/playbooks/runs/${runId}/abort`, { method: 'POST' }),
};
