# Postmortems

Written for failures that taught us something a test could not. The point is never blame; it
is to convert a scar into a rule, and then — where possible — the rule into a script.

A postmortem earns its keep when its **Lessons Learned** section produces an artifact:
an ADR, an entry in [engineering-notes.md](../engineering-notes.md), or a gate in
`make check`. A postmortem that produces only regret is a diary entry.

## Index

| PM | Title | Date | Severity |
| --- | --- | --- | --- |
| [0001](0001-guardrails-that-checked-nothing.md) | Guardrails that checked nothing | 2026-07-09 | Medium |

## Template

```markdown
# PM-NNNN: Title

## Summary
One paragraph. What broke, for whom, for how long.

## Detection
How we found out. If a user found out before we did, say so.

## Timeline
Timestamps, in order. Include the moments where we were wrong.

## Root Cause
Not "someone made a mistake." Why was the mistake possible, and why was it invisible?

## Impact
Concrete. Who or what was affected, and how badly.

## Resolution
What we changed. Link the commits.

## Lessons Learned
The rule this produces, and where that rule now lives.

## References
Issues, commits, upstream docs.
```

## Severity

- **High** — data loss, an authorization bypass, or a customer-visible outage.
- **Medium** — a defect that reached `main`, or a control that silently stopped working.
- **Low** — caught before merge, but the near-miss is instructive.

Severity is about what *could* have happened, not what did. A guard that silently stopped
guarding is Medium even if nothing walked through the open door, because nothing was
watching the door.
