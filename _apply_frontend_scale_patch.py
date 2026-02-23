from pathlib import Path

root = Path(r"d:\Projects\Dev\ThreatHunt")

# -------- client.ts --------
client = root / "frontend/src/api/client.ts"
text = client.read_text(encoding="utf-8")

if "export interface NetworkSummary" not in text:
    insert_after = "export interface InventoryStatus {\n  hunt_id: string;\n  status: 'ready' | 'building' | 'none';\n}\n"
    addition = insert_after + "\nexport interface NetworkSummaryHost {\n  id: string;\n  hostname: string;\n  row_count: number;\n  ip_count: number;\n  user_count: number;\n}\n\nexport interface NetworkSummary {\n  stats: InventoryStats;\n  top_hosts: NetworkSummaryHost[];\n  top_edges: InventoryConnection[];\n  status?: 'building' | 'deferred';\n  message?: string;\n}\n"
    text = text.replace(insert_after, addition)

net_old = """export const network = {\n  hostInventory: (huntId: string, force = false) =>\n    api<HostInventory>(`/api/network/host-inventory?hunt_id=${encodeURIComponent(huntId)}${force ? '&force=true' : ''}`),\n  inventoryStatus: (huntId: string) =>\n    api<InventoryStatus>(`/api/network/inventory-status?hunt_id=${encodeURIComponent(huntId)}`),\n  rebuildInventory: (huntId: string) =>\n    api<{ job_id: string; status: string }>(`/api/network/rebuild-inventory?hunt_id=${encodeURIComponent(huntId)}`, { method: 'POST' }),\n};"""
net_new = """export const network = {\n  hostInventory: (huntId: string, force = false) =>\n    api<HostInventory | { status: 'building' | 'deferred'; message?: string }>(`/api/network/host-inventory?hunt_id=${encodeURIComponent(huntId)}${force ? '&force=true' : ''}`),\n  summary: (huntId: string, topN = 20) =>\n    api<NetworkSummary | { status: 'building' | 'deferred'; message?: string }>(`/api/network/summary?hunt_id=${encodeURIComponent(huntId)}&top_n=${topN}`),\n  subgraph: (huntId: string, maxHosts = 250, maxEdges = 1500, nodeId?: string) => {\n    let qs = `/api/network/subgraph?hunt_id=${encodeURIComponent(huntId)}&max_hosts=${maxHosts}&max_edges=${maxEdges}`;\n    if (nodeId) qs += `&node_id=${encodeURIComponent(nodeId)}`;\n    return api<HostInventory | { status: 'building' | 'deferred'; message?: string }>(qs);\n  },\n  inventoryStatus: (huntId: string) =>\n    api<InventoryStatus>(`/api/network/inventory-status?hunt_id=${encodeURIComponent(huntId)}`),\n  rebuildInventory: (huntId: string) =>\n    api<{ job_id: string; status: string }>(`/api/network/rebuild-inventory?hunt_id=${encodeURIComponent(huntId)}`, { method: 'POST' }),\n};"""
if net_old in text:
    text = text.replace(net_old, net_new)

client.write_text(text, encoding="utf-8")

# -------- NetworkMap.tsx --------
nm = root / "frontend/src/components/NetworkMap.tsx"
text = nm.read_text(encoding="utf-8")

# add constants
if "LARGE_HUNT_HOST_THRESHOLD" not in text:
    text = text.replace("let lastSelectedHuntId = '';\n", "let lastSelectedHuntId = '';\nconst LARGE_HUNT_HOST_THRESHOLD = 400;\nconst LARGE_HUNT_SUBGRAPH_HOSTS = 350;\nconst LARGE_HUNT_SUBGRAPH_EDGES = 2500;\n")

# inject helper in component after sleep
marker = "  const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));\n"
if "loadScaleAwareGraph" not in text:
    helper = marker + "\n  const loadScaleAwareGraph = useCallback(async (huntId: string, forceRefresh = false) => {\n    setLoading(true); setError(''); setGraph(null); setStats(null);\n    setSelectedNode(null); setPopoverAnchor(null);\n\n    const waitReadyThen = async <T,>(fn: () => Promise<T>): Promise<T> => {\n      let delayMs = 1500;\n      const startedAt = Date.now();\n      for (;;) {\n        const out: any = await fn();\n        if (out && !out.status) return out as T;\n        const st = await network.inventoryStatus(huntId);\n        if (st.status === 'ready') {\n          const out2: any = await fn();\n          if (out2 && !out2.status) return out2 as T;\n        }\n        if (Date.now() - startedAt > 5 * 60 * 1000) throw new Error('Network data build timed out after 5 minutes');\n        const jitter = Math.floor(Math.random() * 250);\n        await sleep(delayMs + jitter);\n        delayMs = Math.min(10000, Math.floor(delayMs * 1.5));\n      }\n    };\n\n    try {\n      setProgress('Loading network summary');\n      const summary: any = await waitReadyThen(() => network.summary(huntId, 20));\n      const totalHosts = summary?.stats?.total_hosts || 0;\n\n      if (totalHosts > LARGE_HUNT_HOST_THRESHOLD) {\n        setProgress(`Large hunt detected (${totalHosts} hosts). Loading focused subgraph`);\n        const sub: any = await waitReadyThen(() => network.subgraph(huntId, LARGE_HUNT_SUBGRAPH_HOSTS, LARGE_HUNT_SUBGRAPH_EDGES));\n        if (!sub?.hosts || sub.hosts.length === 0) {\n          setError('No hosts found for subgraph.');\n          return;\n        }\n        const { w, h } = canvasSizeRef.current;\n        const g = buildGraphFromInventory(sub.hosts, sub.connections || [], w, h);\n        simulate(g, w / 2, h / 2, 60);\n        simAlphaRef.current = 0.3;\n        setStats(summary.stats);\n        graphCache.set(huntId, { graph: g, stats: summary.stats, ts: Date.now() });\n        setGraph(g);\n        return;\n      }\n\n      // Small/medium hunts: load full inventory\n      setProgress('Loading host inventory');\n      const inv: any = await waitReadyThen(() => network.hostInventory(huntId, forceRefresh));\n      if (!inv?.hosts || inv.hosts.length === 0) {\n        setError('No hosts found. Upload CSV files with host-identifying columns (ClientId, Fqdn, Hostname) to this hunt.');\n        return;\n      }\n      const { w, h } = canvasSizeRef.current;\n      const g = buildGraphFromInventory(inv.hosts, inv.connections || [], w, h);\n      simulate(g, w / 2, h / 2, 60);\n      simAlphaRef.current = 0.3;\n      setStats(summary.stats || inv.stats);\n      graphCache.set(huntId, { graph: g, stats: summary.stats || inv.stats, ts: Date.now() });\n      setGraph(g);\n    } catch (e: any) {\n      console.error('[NetworkMap] scale-aware load error:', e);\n      setError(e.message || 'Failed to load network data');\n    } finally {\n      setLoading(false);\n      setProgress('');\n    }\n  }, []);\n"
    text = text.replace(marker, helper)

# simplify existing loadGraph function body to delegate
pattern_start = text.find("  // Load host inventory for selected hunt (with cache).")
if pattern_start != -1:
    # replace the whole loadGraph useCallback block by simple delegator
    import re
    block_re = re.compile(r"  // Load host inventory for selected hunt \(with cache\)\.[\s\S]*?\n  \}, \[\]\);  // Stable - reads canvasSizeRef, no state deps\n", re.M)
    repl = "  // Load graph data for selected hunt (delegates to scale-aware loader).\n  const loadGraph = useCallback(async (huntId: string, forceRefresh = false) => {\n    if (!huntId) return;\n\n    // Check module-level cache first (5 min TTL)\n    if (!forceRefresh) {\n      const cached = graphCache.get(huntId);\n      if (cached && Date.now() - cached.ts < 5 * 60 * 1000) {\n        setGraph(cached.graph);\n        setStats(cached.stats);\n        setError('');\n        simAlphaRef.current = 0;\n        return;\n      }\n    }\n\n    await loadScaleAwareGraph(huntId, forceRefresh);\n  // eslint-disable-next-line react-hooks/exhaustive-deps\n  }, []);  // Stable - reads canvasSizeRef, no state deps\n"
    text = block_re.sub(repl, text, count=1)

nm.write_text(text, encoding="utf-8")

print("Patched frontend client + NetworkMap for scale-aware loading")