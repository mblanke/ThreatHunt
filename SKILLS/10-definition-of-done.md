
# Definition of Done (DoD)

A change is "done" only when:

## Code correctness
- Builds successfully (if applicable)
- Tests pass
- Linting/formatting passes
- Types/checks pass (if applicable)

## Quality
- No new warnings introduced
- Edge cases handled (inputs validated, errors meaningful)
- Hot paths not regressed (if applicable)

## Hygiene
- No secrets committed
- Docs updated if behavior or usage changed
- PR summary includes verification steps

## Commands
- macOS/Linux: `./scripts/dod.sh`
- Windows: `\scripts\dod.ps1`
