# ADR-0006: Coverage is a ratchet, not a target

## Status

Accepted.

## Context

the upstream project enforces 90% branch coverage in CI. Zita's backend, at the moment the gate was
installed, had zero tests and about 450 lines of application code.

Adopting 90% would have meant one of two things. Either we write enough tests to clear it —
achievable on 450 lines, and it says nothing about the code not yet written. Or the number
sits in `pyproject.toml` as an aspiration, red on every run, and within a week somebody adds
`--no-cov` to make the build pass.

A coverage number is only meaningful relative to a codebase. Inherited, it is a number about
somebody else's codebase.

## Decision

**`fail_under` is set to what the suite genuinely achieves, and only ever raised.**

Today: **92%** branch coverage on the backend, from 21 tests over `apps/users`. The number was
measured after the tests were written, not chosen before.

Lowering `fail_under` to make a red build green is forbidden. If a change drops coverage,
either it needs tests or the dead code it added needs deleting.

The frontend has no coverage floor yet. It has 13 unit tests over pure helpers, and the code
that matters most there — server actions, RSC boundaries — is not meaningfully covered by
Vitest at all (see [engineering-notes.md](../engineering-notes.md)). A floor over the helpers
alone would measure the wrong thing.

## Consequences

The number means something. 92% is a fact about `apps/users`, and when `apps/catalog` lands
with tests, the floor moves with it.

It ratchets in one direction, so a large untested feature cannot land without either tests or
an explicit, visible lowering of the bar in a diff someone has to approve.

The gate was proven by raising the floor to 99% and watching the suite fail, then restoring
it. See [ADR-0009](0009-a-gate-must-be-seen-to-fail.md).

We would revisit if the ratchet ever incentivised the wrong thing — tests written to cover
lines rather than behaviour. The defence against that is review, and no number can substitute
for it.
