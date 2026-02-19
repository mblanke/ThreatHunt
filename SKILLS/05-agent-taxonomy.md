# Agent Types & Roles (Practical Taxonomy)

Use this skill to choose the *right* kind of agent workflow for the job.

## Common agent "types" (in practice)

### 1) Chat assistant (no tools)
Best for: explanations, brainstorming, small edits.
Risk: can hallucinate; no grounding in repo state.

### 2) Tool-using single agent
Best for: well-scoped tasks where the agent can read/write files and run commands.
Key control: strict DoD gates + minimal permissions.

### 3) Planner + Executor (2-role pattern)
Best for: medium complexity work (multi-file changes, feature work).
Flow: Planner writes plan + acceptance criteria → Executor implements → Reviewer checks.

### 4) Multi-agent (specialists)
Best for: bigger features with separable workstreams (UI, backend, docs, tests).
Rule: isolate context per role; use separate branches/worktrees.

### 5) Supervisor / orchestrator
Best for: long-running workflows with checkpoints (pipelines, report generation, PAD docs).
Rule: supervisor delegates, enforces gates, and composes final output.

## Decision rules (fast)
- If you can describe it in ≤ 5 steps → single tool-using agent.
- If you need tradeoffs/design → Planner + Executor.
- If UI + backend + docs/tests all move → multi-agent specialists.
- If it's a pipeline that runs repeatedly → orchestrator.

## Guardrails (always)
- DoD is the truth gate.
- Separate branches/worktrees for parallel work.
- Log decisions + commands in AGENT_LOG.md.
