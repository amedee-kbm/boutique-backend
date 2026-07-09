# Security

## Reporting a vulnerability

**Do not open a public issue.** Use GitHub's private vulnerability reporting on this
repository (Security → Report a vulnerability), or email the maintainer.

Include what you did, what happened, and what you expected. A proof of concept helps enormously
and does not need to be weaponised — a curl command is plenty.

You will get an acknowledgement. If the report is valid you will be told when it is fixed.

## What we protect

Zita handles no payments. No card data, no wallet, no online checkout — the sale closes offline
between seller and customer. That removes an entire class of risk and concentrates what remains
on two things:

**Customer contact details.** An order carries a name, a phone number, and a delivery address.
That is the sensitive payload of this application, and it is why the Orders inbox is behind the
seller gate.

**The seller's session.** The `is_seller` flag on a user is the only thing standing between a
customer and the admin surface. There is no role table, no permissions matrix. That simplicity
is a feature, and it means the gate must be exactly right.

## Controls

| Control | Where |
| --- | --- |
| Static application security testing | `bandit`, in `make check` and CI |
| Dependency vulnerabilities | `pip-audit`, in CI and nightly |
| Licence compliance | `licensecheck`, rejects copyleft and source-available |
| Secret scanning | `gitleaks`, on every push |
| Strict typing | `mypy --strict` |
| Branch coverage floor | 92%, ratcheting |
| Token leakage to the browser | `check-rsc-token.mjs`, frontend `make check` |

Every one of these has been observed failing on a deliberate violation before being trusted
([ADR-0009](docs/adr/0009-a-gate-must-be-seen-to-fail.md)). A control that has never gone red is
not a control.

## Authorization

Two status codes, and the difference between them is the entire model:

- **401** — no token, or an invalid one. The frontend should re-authenticate.
- **403** — a valid token belonging to a non-seller. The session is fine; the door is closed.

Returning 401 where 403 belongs sends a signed-in customer into a login loop. Returning 200
where 403 belongs is a breach. Both are covered by tests in `apps/users/tests/test_auth.py`, and
they are the most important tests in the repository.

Note for the frontend: **Drizzle bypasses Row Level Security.** RLS is not the gate on the admin
write path — the `'use server'` action is. Every admin mutation must call the guard itself. No
type checker will catch a missing one.

## Passwords and tokens

Passwords are hashed by Django and validated against its standard validators.

Password reset does not leak account existence: `/auth/password/reset-request` returns an
identical status and body whether or not the address has an account, and a test asserts it.

Access and refresh tokens live in HttpOnly cookies on the Next origin and are read only by the
BFF route handlers ([ADR-0003](docs/adr/0003-token-custody-in-the-bff.md)). Refresh tokens
rotate on use and the old one is blacklisted, so a stolen refresh token is single-use and its
theft is detectable.

## Suppressing a CVE

Bumping the dependency is always preferred. A suppression requires all four:

1. A written rationale — why this vulnerability cannot be reached from our code.
2. An exit condition — what would make us remove the suppression.
3. A re-review date.
4. The suppression itself, in the `Makefile`'s `audit` target, next to the other three.

A suppression without a rationale is not a suppression; it is a hole with a comment character in
front of it.

The same discipline applies to `licensecheck` exceptions in `pyproject.toml`. Two exist today —
`certifi` and `pathspec`, both MPL-2.0, both file-level copyleft that binds only files we
neither modify nor redistribute. `psycopg` is LGPL-3.0 and passes on its own merits: we link it,
never modify it, and never ship a binary. If this application ever becomes a redistributable
artifact, that reasoning stops holding.

## What we have not done

Honesty is a control too.

There is no rate limiting on the API. There is no audit log of admin actions. There is no DAST
scanning, no penetration test, and no bug-bounty programme. The password-reset token has
Django's default lifetime and no additional throttling.

None of these is acceptable indefinitely. All of them are acceptable for an application that has
not launched, and they are written here so that "we forgot" never becomes the explanation.
