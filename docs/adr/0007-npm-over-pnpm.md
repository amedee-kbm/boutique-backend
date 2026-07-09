# ADR-0007: npm, not pnpm

## Status

Accepted.

## Context

Every transplanted Makefile target and CI workflow assumed pnpm. The frontend has used npm
since its first commit, with a `package-lock.json` and 120 commits of history behind it.

Adopting pnpm would have ported the inherited `check-licenses.mjs` (`pnpm licenses list --json`),
the `deps.yml` workflows, and the dependabot cooldown configuration unchanged.

## Decision

**Stay on npm.** Rewrite the tooling that assumed otherwise.

`check-licenses.mjs` was rewritten anyway, per
[ADR-0010](0010-no-third-party-code-verbatim.md), and ended up not shelling out to a package
manager at all — it walks `node_modules` and reads each manifest. That is faster, has no
moving parts, and sidesteps a real problem: `npm` is a shell script, Node 26 refuses to spawn
a `.cmd` without a shell, and `shell: true` is deprecated for argument-injection reasons.

## Consequences

No lockfile migration, no change to the Vercel build command, no risk of a resolution
difference between the old lockfile and a new one.

We give up pnpm's content-addressed store (faster installs, less disk) and its
`minimumReleaseAge` supply-chain hold-down, which delays adopting a freshly published version.
That hold-down is a genuinely useful defence against a compromised package, and it is the one
thing we actually lose here.

We would revisit if install time became painful in CI, or if the two repositories ever shared
a workspace — pnpm workspaces are better than npm's. Neither applies:
[ADR-0002](0002-two-repositories.md) says the halves do not share a build.
