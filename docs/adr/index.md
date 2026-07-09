# Architecture Decision Records

A record of decisions that were **made**, not decisions that are pending. If we have not
decided, there is no ADR — there is an open question, and it lives in an issue or in
[USER_JOURNEYS.md](../../USER_JOURNEYS.md).

Write one when a decision is **significant and hard to reverse**. The test is not "was this
hard to think about" but "will someone, in eight months, reasonably wonder why it is this
way and be tempted to change it back."

These ADRs are canonical for **both** repositories. The frontend links here rather than
keeping a second copy, because a decision recorded twice is a decision that will eventually
disagree with itself.

## Index

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-django-neon-system-of-record.md) | Django + Neon becomes the system of record | Accepted |
| [0002](0002-two-repositories.md) | Two repositories, not a monorepo | Accepted |
| [0003](0003-token-custody-in-the-bff.md) | Token custody lives in the Next BFF | Accepted |
| [0004](0004-email-is-the-login-credential.md) | Email is the login credential | Accepted |
| [0005](0005-i18n-deferred.md) | i18n is deferred | Accepted |
| [0006](0006-coverage-is-a-ratchet.md) | Coverage is a ratchet, not a target | Accepted |
| [0007](0007-npm-over-pnpm.md) | npm, not pnpm | Accepted |
| [0008](0008-deploy-config-lives-in-the-repo.md) | Deploy config lives in the backend repo | Accepted |
| [0009](0009-a-gate-must-be-seen-to-fail.md) | A gate is not trusted until observed failing | Accepted |
| [0010](0010-no-third-party-code-verbatim.md) | No third-party code is carried verbatim | Accepted |
| [0011](0011-src-layout-and-boutique-package.md) | `src/` layout, settings package named `boutique` | Accepted |

## Template

```markdown
# ADR-NNNN: Title

## Status

Accepted | Proposed | Deprecated | Superseded by [ADR-XXXX](XXXX-slug.md)

## Context

What forced the decision. What was true at the time. What we did not know.

## Decision

What we chose, stated so plainly that a stranger could apply it.

## Consequences

What becomes easier. What becomes harder. What we are now committed to.
What would make us revisit this.
```

## Adding one

1. Take the next number. Do not reuse a number, even for an abandoned draft.
2. Write the **Context** before the **Decision**, and be honest about what was unknown.
   An ADR whose context reads like a justification is a press release.
3. Fill in **Consequences**, including the ones you do not like. An ADR with no downsides
   is either trivial or dishonest.
4. Name the condition that would reverse it. A decision you cannot imagine reversing is a
   belief, not a decision.
5. Add a row to the index above.

Superseding an ADR does not mean deleting it. Mark the old one `Superseded by`, and say in
the new one what changed — the reasoning that was once correct is the most useful thing in
the file.
