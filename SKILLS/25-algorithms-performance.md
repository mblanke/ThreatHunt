# Algorithms & Performance

Use this skill when performance matters (large inputs, hot paths, or repeated calls).

## Checklist
- Identify the **state** you're recomputing.
- Add **memoization / caching** when the same subproblem repeats.
- Prefer **linear scans** + caches over nested loops when possible.
- If you can write it as a **recurrence**, you can test it.

## Practical heuristics
- Measure first when possible (timing + input sizes).
- Optimize the biggest wins: avoid repeated I/O, repeated parsing, repeated network calls.
- Keep caches bounded (size/TTL) and invalidate safely.
- Choose data structures intentionally: dict/set for membership, heap for top-k, deque for queues.

## Review notes (for PRs)
- Call out accidental O(n²) patterns.
- Suggest table/DP or memoization when repeated work is obvious.
- Add tests that cover base cases + typical cases + worst-case size.
