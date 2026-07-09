# ADR-0009: A gate is not trusted until it has been observed failing

## Status

Accepted.

## Context

Zita's engineering apparatus was transplanted from [the upstream project](https://github.com/upstream), a
mature Django project. The transplant carried the upstream project's checkers across intact — their
enforcement paths, their exit codes, their green checkmarks — into a codebase with a
different shape.

Two of them landed on nothing.

`check-file-length.sh` ran `find src -name '*.py'`. There was no `src/` directory. It found
zero files, printed a tick, exited 0.

`check-no-ssr-token.sh` grepped for `.svelte` files and `+page.server.ts` load functions in
a Next.js App Router project. Zero matches. It printed `✓ No SSR access-token leaks` and
exited 0 — while guarding the single most security-critical invariant in the frontend.

Both passed. Both checked nothing. Nobody noticed, because green is what green looks like.
The full account is [PM-0001](../postmortems/0001-guardrails-that-checked-nothing.md).

The general failure is not "we copied a script wrong." It is that **the passing case of a
check carries no information.** A check that cannot fail and a check that has nothing to
check produce byte-identical output. You cannot tell them apart by looking at the output,
which is the only thing anyone ever looks at.

## Decision

**A gate is not trusted until it has been observed failing.**

For every check installed — a lint rule, a CI step, a script, a test, an assertion you are
about to rely on — introduce a deliberate violation, watch it go red, then revert and watch
it go green. Do this at the moment the gate is written, not later.

This applies to a gate's *branches*, not merely to the gate. `check-file-length.sh` has a
default ceiling and a per-file override; both were proven. `check-rsc-token.mjs` has four
rules; all four were proven.

A gate that can only be proven by contriving a scenario nobody would ever write is a gate
aimed at the wrong thing. If the violation is hard to construct, that is information.

## Consequences

Installing a gate costs more. Writing `check-rsc-token.mjs` took twenty minutes; proving
its four rules took another twenty. This is the correct ratio.

We catch the class of bug that has no symptom. While writing `audit-theme-contrast.mjs` —
the gate written *because of* this ADR — the first draft located the `.dark` block with
`indexOf('.dark')`, which matched `@custom-variant dark (&:is(.dark *))` instead and
silently skipped every dark-mode pair. The gate that this ADR mandates caught the gate that
this ADR mandated. That is not a coincidence; it is what the rule is for.

It follows that **a skip is never acceptable in a gate.** If a check cannot evaluate
something, that is a failure, not a pass. `audit-theme-contrast.mjs` treats a missing token
as red, which is how the undefined `--destructive-foreground` was found.

We would revisit this if the cost of proving a gate exceeded the cost of the bugs it
prevents. So far it has never come close: every gate installed under this rule has found a
real defect in existing code on its first run.

Companion to [ADR-0010](0010-no-third-party-code-verbatim.md): if a gate cannot be written
from scratch, it is not understood well enough to be trusted — and an untrusted gate is
exactly what this ADR exists to catch.
