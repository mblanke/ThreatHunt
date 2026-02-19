# Performance Profiling (Bun/Node)

Use this skill when:
- a hot path feels slow
- CPU usage is high
- you suspect accidental O(n²) or repeated work
- you need evidence before optimizing

## Bun CPU profiling
Bun supports CPU profiling via `--cpu-prof` (generates a `.cpuprofile` you can open in Chrome DevTools).

Upcoming: `bun --cpu-prof-md <script>` outputs a CPU profile as **Markdown** so LLMs can read/grep it easily.

### Workflow (Bun)
1) Run the workload with profiling enabled
   - Today: `bun --cpu-prof ./path/to/script.ts`
   - Upcoming: `bun --cpu-prof-md ./path/to/script.ts`
2) Save the output (or `.cpuprofile`) into `./profiles/` with a timestamp.
3) Ask the Reviewer agent to:
   - identify the top 5 hottest functions
   - propose the smallest fix
   - add a regression test or benchmark

## Node CPU profiling (fallback)
- `node --cpu-prof ./script.js` writes a `.cpuprofile` file.
- Open in Chrome DevTools → Performance → Load profile.

## Rules
- Optimize based on measured hotspots, not vibes.
- Prefer algorithmic wins (remove repeated work) over micro-optimizations.
- Keep profiling artifacts out of git unless explicitly needed (use `.gitignore`).
