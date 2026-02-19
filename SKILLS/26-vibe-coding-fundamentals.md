# Vibe Coding With Fundamentals (Safety Rails)

Use this skill when you're using "vibe coding" (fast, conversational building) but want production-grade outcomes.

## The good
- Rapid scaffolding and iteration
- Fast UI prototypes
- Quick exploration of architectures and options

## The failure mode
- "It works on my machine" code with weak tests
- Security foot-guns (auth, input validation, secrets)
- Performance cliffs (accidental O(n²), repeated I/O)
- Unmaintainable abstractions

## Safety rails (apply every time)
- Always start with acceptance criteria (what "done" means).
- Prefer small PRs; never dump a huge AI diff.
- Require DoD gates (lint/test/build) before merge.
- Write tests for behavior changes.
- For anything security/data related: do a Reviewer pass.

## When to slow down
- Auth/session/token work
- Anything touching payments, PII, secrets
- Data migrations/schema changes
- Performance-critical paths
- "It's flaky" or "it only fails in CI"

## Practical prompt pattern (use in PLAN)
- "State assumptions, list files to touch, propose tests, and include rollback steps."
