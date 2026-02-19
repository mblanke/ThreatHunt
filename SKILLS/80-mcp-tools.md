
# MCP Tools Skill (Optional)

If this repo defines MCP servers/tools:

Rules:
- Tool calls must be explicit and logged.
- Maintain an allowlist of tools; deny by default.
- Every tool must have: purpose, inputs/outputs schema, examples, and tests.
- Prefer idempotent tool operations.
- Never add tools that can exfiltrate secrets without strict guards.
