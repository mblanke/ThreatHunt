
# Testing & Quality

## Strategy
- If behavior changes: add/update tests.
- Unit tests for logic; integration tests for boundaries; E2E only where needed.

## Minimum for every PR
- A test plan in the PR summary (even if "existing tests cover this").
- Run DoD.

## Flaky tests
- Capture repro steps.
- Quarantine only with justification + follow-up issue.
