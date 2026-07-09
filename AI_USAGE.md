# AI Usage in Zita Boutique

This project is built with heavy AI assistance. It also refuses to let AI own
the result. Every line that reaches `main` is understood and defended by a human.

If you take one thing away: **the guardrails are the product of this document.** An LLM with a green
test suite and no guardrails is a slop generator with good manners.

---


## The two rules

**1. A gate is not trusted until it has been observed failing.** (`ADR-0009`)

When you add a check, break something on purpose, watch it go red, then revert. A green check that
has never gone red is not evidence. It is decoration. This applies to CI steps, lint rules, tests,
and any assertion you are about to rely on.

**2. No third-party code is carried verbatim.** (`ADR-0010`)

Adopt intent and configuration values; write the implementation. Copy `line-length = 120` — that is a
fact about how you want your linter to behave. Do not copy the two hundred lines of Python that
enforce it. **If a gate cannot be rewritten from scratch, it is not understood well enough to be
trusted**, and an untrusted gate is the thing rule 1 exists to catch.

The second rule is also why this repository carries a plain MIT licence with no `NOTICE`: nothing of
anyone else's is in it.

---

## Guardrails & QA posture

The Makefile is the contract. Two commands, and CI runs exactly what you run.

```bash
make check    # format, lint, mypy --strict, migration-check, file-length, task-names
make test     # pytest with branch coverage against a real Postgres
```

Neither is decoration. `make check` currently fails on `apps/users/tasks.py`, which declares a bare
`@shared_task` with no explicit `name=` — a Celery footgun that silently rebinds a task's registered
name when its module moves, stranding in-flight messages and orphaning `django_celery_beat` rows. The
gate found a real bug in this codebase on the day it was installed. That is the point.

**Coverage is a ratchet, not a target.** The floor is whatever the current suite genuinely achieves,
written into `pyproject.toml`, raised as code lands. An inherited 90% on a four-hundred-line app is a
number that means nothing, and a number that means nothing is worse than no number.

Supply chain: `licensecheck` rejects copyleft entering the dependency tree; `pip-audit` runs in CI and
nightly; a failing nightly opens an issue rather than a silent red square. Suppress a CVE only with a
written rationale, an exit condition, and a re-review date.

---

## The workflow

Discussion before implementation, for anything non-trivial. This is not politeness — it is the
cheapest place to catch a wrong approach.

1. **Investigate.** Read the code. Map what the change touches. Do not guess.
2. **Discuss.** Present findings. Propose approaches with tradeoffs. State assumptions out loud.
   Get explicit agreement before writing code.
3. **Implement.** Follow the agreed plan. Raise concerns the moment they surface, not afterwards.
4. **Verify.** Drive the real thing — an endpoint, a browser, a task — not just the test suite.

An agent that skips step 2 produces work that looks finished and is not.

---

## Tests are not optional

Every feature ships with tests. Every bug fix ships with a test that reproduces the bug first.

But be honest about what a test proves. The frontend learned this the hard way, and it is written
down in `frontend/CLAUDE.md`: **if a test mocks the thing that would actually fail, it cannot catch
that failure.** A `"use server"` file that exports a non-function object passes every mocked unit
test and throws in the browser on first load. Only the real runtime caught it.

The backend has its own version. `pytest-django` rolls back the wrapping transaction, so
`transaction.on_commit` callbacks never fire — a test asserting that a Celery task was dispatched
will pass whether or not the dispatch is wired up, unless you use
`django_capture_on_commit_callbacks(execute=True)`. Green means nothing if the mechanism under test
was never allowed to run.

For every mutation, one path must exercise it unmocked.

---

## PR review has three layers

1. **The machine.** `make check` and `make test`, then CI. Green is the bare minimum, not the goal.
2. **The agent.** `/code-review`, or the `pr-reviewer` agent. Fresh eyes with no attachment to the
   approach.
3. **The human.** Someone who can be asked "why" and must have an answer.

Green checks mean the change did not break the rules we knew how to write down. They say nothing
about whether the change is right.

---

## Tooling

Agents (`.claude/agents/`) — `pr-reviewer`, `test-engineer`, and two hunter/verifier pairs:
`vuln-analyst` + `vuln-verifier`, `tech-debt-assessor` + `tech-debt-verifier`. The hunter proposes;
the skeptical verifier adjudicates with a confidence score. One model finding problems and a second
refusing to believe it beats one model marking its own homework.

Commands (`.claude/commands/`) — `/vuln-scan`, `/tech-debt`, `/update-changelog`, `/release`.

Skills (`.claude/skills/`) — `update-changelog` (Keep a Changelog conventions), `updating-deps` (UV).

---

## Fair warning

AI accelerates the work. It does not own it.

Do not open a PR you cannot explain. Do not add a gate you have not watched fail. Do not copy code
you could not have written. If the diff is two hundred lines and it could be fifty, it is not
finished — it is unreviewed.
