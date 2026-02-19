# FastMCP 3 Patterns (Providers + Transforms)

Use this skill when you are building MCP servers in Python and want:
- composable tool sets
- per-user/per-session behavior
- auth, versioning, observability, and long-running tasks

## Mental model (FastMCP 3)
FastMCP 3 treats everything as three composable primitives:
- **Components**: what you expose (tools, resources, prompts)
- **Providers**: where components come from (decorators, files, OpenAPI, remote MCP, etc.)
- **Transforms**: how you reshape what clients see (namespace, filters, auth, versioning, visibility)

## Recommended architecture for Marc's platform
Build a **single "Cyber MCP Gateway"** that composes providers:
- LocalProvider: core cyber tools (run hunt, parse triage, generate report)
- OpenAPIProvider: wrap stable internal APIs (ticketing, asset DB) without 1:1 endpoint exposure
- ProxyProvider/FastMCPProvider: mount sub-servers (e.g., Velociraptor tools, Intel feeds)

Then apply transforms:
- Namespace per domain: `hunt.*`, `intel.*`, `pad.*`
- Visibility per session: hide dangerous tools unless user/role allows
- VersionFilter: keep old clients working while you evolve tools

## Production must-haves
- **Tool timeouts**: never let a tool hang forever
- **Pagination**: all list tools must be bounded
- **Background tasks**: use for long hunts / ingest jobs
- **Tracing**: emit OpenTelemetry traces so you can debug agent/tool behavior

## Auth rules
- Prefer component-level auth for "dangerous" tools.
- Default stance: read-only tools visible; write/execute tools gated.

## Versioning rules
- Version your components when you change schemas or semantics.
- Keep 1 previous version callable during migrations.

## Upgrade guidance
FastMCP 3 is in beta; pin to v2 for stability in production until you've tested.
