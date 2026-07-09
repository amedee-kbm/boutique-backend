# PM-0001: Guardrails that checked nothing

## Summary

Zita's engineering apparatus — its checkers, CI, and quality gates — was transplanted from
[the upstream project](https://github.com/upstream), a mature Django project with a SvelteKit frontend. The
transplant carried the scripts across intact and dropped them into a codebase with a different
shape.

Two of them landed on nothing and reported success. `check-file-length.sh` searched a `src/`
directory that did not exist. `check-no-ssr-token.sh` grepped for `.svelte` files and
`+page.server.ts` load functions in a Next.js App Router project. Each found zero files,
printed a green tick, and exited 0.

The second was guarding the most security-critical invariant in the frontend: that a bearer
JWT never reaches the browser.

Nothing was ever compromised. The gates were never pushed, CI never ran, and the code they
should have been guarding happened to be correct. The failure is that we could not have known
that, and we would have kept not knowing.

## Detection

Found by inspection, during an audit of what the transplant had actually brought over — not
by anything failing.

The trigger was mundane: reading `check-file-length.sh` to retarget it, and noticing it began
`find src -name '*.py'` in a repository whose Python lives under `apps/` and `api/`. Running
it produced a tick. Running it in an empty directory produced the same tick.

That prompted a check of every other inherited gate. `check-no-ssr-token.sh` was the second
one, and the serious one.

## Timeline

All times 2026-07-09, local.

- **~14:00** — Audit of the transplanted material begins. 112 markdown files, ~40 code files,
  none of which implement a feature.
- **~14:20** — `check-file-length.sh` read. `find src` noted. There is no `src/`.
- **~14:25** — Run it: `✓ No file exceeds its length ceiling`. Exit 0. It scanned zero files.
- **~14:40** — `check-no-ssr-token.sh` read. It greps `--include="*.svelte"` and
  `--include="+page.server.ts"`. Neither exists in App Router.
- **~14:42** — Run it: `✓ No SSR access-token leaks`. Exit 0. It inspected zero files.
- **~14:45** — Realisation that these two are not different bugs. They are the same bug, and
  the bug is not in the scripts.
- **Later** — Both rewritten. Both proven to fail before being trusted to pass.

Two things we believed and were wrong about:

We assumed a copied gate is a working gate, degraded at worst. It is not: it is a gate whose
*target* is absent while its *machinery* is intact, and machinery with no target reports
success.

We assumed CI would have caught it. CI would have reported two more green checkmarks.

## Root Cause

**A guardrail moved into a foreign codebase keeps its enforcement path and loses its target.**

Every check has two halves: a set of things to inspect, and a rule to apply to them. Copying
moves the rule. The set is expressed as paths, globs, and file extensions — and those are
facts about the *original* repository, not the rule.

When the set comes back empty, the rule is vacuously true. `for file in []: assert rule(file)`
passes. And it passes with the same exit code, the same tick, and the same green square in a
CI run as a rule that genuinely held over a thousand files.

The deeper cause is that **the passing case of a check carries no information.** You cannot
distinguish "checked 1,000 files, all good" from "checked nothing" by looking at the output,
which is the only thing anyone ever looks at. Green means "no evidence of failure," and we
habitually read it as "evidence of no failure."

Copying is what makes this likely, because nobody reads code they did not have to write.

## Impact

None realised. Neither gate ran in CI (GitHub reads only a root-level `.github/`, and both
were nested). Neither was pushed. The invariants they should have enforced were, on
inspection, held.

The potential impact of the second is what sets the severity. `check-no-ssr-token.sh` existed
because the upstream project shipped a real leak (`upstream-frontend#387`), where a bearer JWT returned from a
`load` function was serialized into the page HTML. Under React Server Components the same leak
is *easier*: any value a Server Component passes as a prop to a Client Component is serialized
into the Flight payload. No type error, no warning.

Had anyone written that prop, the guard would have said `✓`.

**Medium**, on the rule that a control which silently stops controlling is Medium regardless
of whether anything walked through the open door — because nothing was watching the door.

## Resolution

Both gates were rewritten from their intent rather than repaired:

- `backend/scripts/check-file-length.sh` — walks `src/`, with per-file overrides that each
  carry a rationale. Proven red on a 600-line module, and again on an override breach.
- `frontend/scripts/check-rsc-token.mjs` — enforces a boundary rather than a leak shape. Only
  the four BFF files may import `lib/auth/tokens`; no `'use client'` file may name a token; no
  credential-shaped `NEXT_PUBLIC_*`; `tokens.ts` and `refresh.ts` must `import 'server-only'`.
  All four rules proven red.

Every other gate in `make check`, on both halves, was likewise proven red-then-green.

Commits: `2dbcba6` (backend), `efa1f9a` (frontend).

## Lessons Learned

**A gate is not trusted until it has been observed failing.** Introduce a deliberate
violation, watch it go red, revert. Do it when the gate is written. This is
[ADR-0009](../adr/0009-a-gate-must-be-seen-to-fail.md).

**A skip is never acceptable in a gate.** If a check cannot evaluate something, that is a
failure, not a pass. This corollary earned itself immediately: `audit-theme-contrast.mjs` was
written to *warn* on a missing token. Making it fail instead surfaced that
`--destructive-foreground` was never defined, while a component used
`hover:text-destructive-foreground` — a dead class, and a delete icon at 2.77:1 contrast in
dark mode.

**If a gate cannot be rewritten from scratch, it is not understood well enough to be trusted.**
This is [ADR-0010](../adr/0010-no-third-party-code-verbatim.md), and it is the same lesson
approached from the other side. Rewriting the three gates we kept revealed that all three
would have been broken as ports: `audit-brand-themes.py` parses HSL and our tokens are `oklch`;
`check-licenses.mjs` shells out to `npm query`, which Node 26 will not spawn; and
`check-no-ssr-token.sh` guards a framework we do not use.

The most instructive detail: **writing the gate mandated by this postmortem reproduced this
postmortem.** The first draft of `audit-theme-contrast.mjs` located the `.dark` token block
with `indexOf('.dark')`, which matched `@custom-variant dark (&:is(.dark *))` on line five
instead — silently skipping every dark-mode pair while reporting on light mode. The rule caught
its own author. That is the strongest evidence we have that the rule is worth its cost.

## References

- [ADR-0009: A gate is not trusted until it has been observed failing](../adr/0009-a-gate-must-be-seen-to-fail.md)
- [ADR-0010: No third-party code is carried verbatim](../adr/0010-no-third-party-code-verbatim.md)
- [ADR-0003: Token custody lives in the Next BFF](../adr/0003-token-custody-in-the-bff.md)
- `upstream-frontend#387` — the original SSR token leak, cited in the header of the script we
  inherited and could not use.
