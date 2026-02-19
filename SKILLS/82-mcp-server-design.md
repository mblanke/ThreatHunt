# MCP Server Design (Agent-First)

Build MCP servers like you're designing a UI for a non-human user.

This skill distills Phil Schmid's MCP server best practices into concrete repo rules.
Source: "MCP is Not the Problem, It's your Server" (Jan 21, 2026).

## 1) Outcomes, not operations
- Do **not** wrap REST endpoints 1:1 as tools.
- Expose high-level, outcome-oriented tools.
  - Bad: `get_user`, `list_orders`, `get_order_status`
  - Good: `track_latest_order(email)` (server orchestrates internally)

## 2) Flatten arguments
- Prefer top-level primitives + constrained enums.
- Avoid nested `dict`/config objects (agents hallucinate keys).
- Defaults reduce decision load.

## 3) Instructions are context
- Tool docstrings are *instructions*:
  - when to use the tool
  - argument formatting rules
  - what the return means
- Error strings are also context:
  - return actionable, self-correcting messages (not raw stack traces)

## 4) Curate ruthlessly
- Aim for **5–15 tools** per server.
- One server, one job. Split by persona if needed.
- Delete unused tools. Don't dump raw data into context.

## 5) Name tools for discovery
- Avoid generic names (`create_issue`).
- Prefer `{service}_{action}_{resource}`:
  - `velociraptor_run_hunt`
  - `github_list_prs`
  - `slack_send_message`

## 6) Paginate large results
- Always support `limit` (default ~20–50).
- Return metadata: `has_more`, `next_offset`, `total_count`.
- Never return hundreds of rows unbounded.

## Repo conventions
- Put MCP tool specs in `mcp/` (schemas, examples, fixtures).
- Provide at least 1 "golden path" example call per tool.
- Add an eval that checks:
  - tool names follow discovery convention
  - args are flat + typed
  - responses are concise + stable
  - pagination works
