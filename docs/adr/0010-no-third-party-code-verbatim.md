# ADR-0010: No third-party code is carried verbatim

## Status

Accepted.

## Context

This project's engineering apparatus came from an existing open-source codebase — MIT licensed,
mature, and written by people who had already paid for the lessons it encodes. Taking it was the
right call. Taking it *as code* was not.

Two problems, one legal and one real.

The legal one is small and easily satisfied. MIT requires the copyright notice to travel
with substantial portions of the work. Attribution in a `NOTICE` file would have discharged
it.

The real problem is that a copied gate is an *unexamined* gate. `check-file-length.sh`
arrived pointed at a directory that did not exist. `check-no-ssr-token.sh` arrived grepping
for a framework we do not use, its header comment citing an issue number in a repository we
do not own. Both were green. Both were useless. Nobody read them, because they were
already written — that is the entire appeal of copying, and it is the entire problem.

There is a distinction to draw here that matters. `line-length = 120` is not authorship. It
is a fact about how you want your linter to behave, and copying it costs nothing and teaches
nothing you needed to learn. The two hundred lines of Python that *enforce* a rule are
authorship, and copying them means you now depend on a mechanism you have never read.

## Decision

**Adopt intent and configuration values. Write the implementation.**

Configuration — a ruff `select` list, a coverage floor, a set of forbidden SPDX identifiers
— is taken directly. Implementations are written from scratch, from an understanding of
what the gate defends against.

**If a gate cannot be rewritten from scratch, it is not understood well enough to be
trusted.** That is the operative half of this rule. The licence question is a side effect.

Concretely, in this repository, everything below was written rather than ported:
`check_task_names.py`, `check-file-length.sh` (both halves), `check-licenses.mjs`,
`check-rsc-token.mjs`, `audit-image-alt.mjs`, `audit-theme-contrast.mjs`, both `Makefile`s,
the CI workflows, and both `CLAUDE.md` files.

### Scope

This ADR governs **executable and enforcing artifacts**: gates, build tooling, CI, and the
configuration that drives them. Those are the things whose failure modes are invisible, and
whose comprehension is the point.

It does **not** currently govern `.claude/` — the agent, command and skill prompts. Those remain
derived from the upstream codebase and are being adapted in place rather than rewritten. They
instruct a model; they do not gate a build, and a misunderstood prompt announces itself in its
output rather than hiding behind a green tick.

That exemption has a price, and it is the licence question this ADR otherwise dissolves. Before
either repository is made public, `.claude/` must either be rewritten or carry the attribution the
upstream MIT licence requires. Recorded here so the choice is made deliberately rather than
discovered.

## Consequences

The repository carries a plain MIT `LICENSE` with no `NOTICE`, because there is nothing of
anyone else's in it to attribute.

Rewriting costs days, not hours. It bought, immediately:

- `check-rsc-token.mjs` guards a boundary (only the BFF may import the token module) rather than
  a leak shape. The script it replaces grepped for the two specific expressions one particular
  leak had taken. Ours cannot be evaded by a third expression, because there is nothing to evade —
  the module is unimportable.
- `audit-theme-contrast.mjs` parses `oklch`. The one it replaces parses HSL. A port would have
  found zero tokens in `globals.css` and passed — the exact failure of
  [ADR-0009](0009-a-gate-must-be-seen-to-fail.md), reintroduced by the act of copying.
- `check-licenses.mjs` walks `node_modules` instead of shelling out to `npm query`, because Node
  26 refuses to spawn a `.cmd` without a shell. The inherited approach does not run here at all.

Three ports that would have been silently or loudly broken. We only know that because we
had to read them.

We would revisit this for a dependency proper — something installed, versioned, and
maintained upstream. This ADR is about **vendoring**: code copied into the tree, where the
upstream never updates it and nobody owns it.
