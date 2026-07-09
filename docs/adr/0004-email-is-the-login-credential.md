# ADR-0004: Email is the login credential

## Status

Accepted. Supersedes the phone-login decision recorded in [backend-build.md](../backend-build.md).

## Context

`backend-build.md` locked in phone-number login, under the reasoning that a Kigali boutique's
customers are reached by phone and think in phone numbers, not email addresses.

The implementation went the other way. `User.USERNAME_FIELD` is `email`, migration `0002`
added the field, and `create_user` requires it.

Nobody noticed the drift, because nothing exercised login. The frontend's `/api/auth/login`
route still carried a comment saying it posts `{ phone_number, password }` to `/auth/pair`,
which would have failed on first contact.

A test written during the guardrail install pinned the behaviour and forced the question.

## Decision

**Email is `USERNAME_FIELD`.** `phone_number` remains a required, unique field on the user —
it is how the seller actually reaches a customer to arrange delivery — but it is not a
credential.

`frontend/src/features/auth/lib/auth-schema.ts` already validated email. The BFF route's
comment was the only thing that disagreed, and it was wrong.

## Consequences

Password reset works, because password reset needs an inbox. A phone-login system would have
needed SMS delivery, a provider, and a per-message cost, for an app that otherwise sends no
SMS at all.

Customers must have an email address to hold an account. This matters less than it appears:
an account buys exactly one feature, Favorites. **Browsing, the Selection, placing an order,
and Tubaze chat are all guest-allowed** and always will be — an order collects name, phone
and delivery address, and no account.

Two tests guard this. One asserts `/auth/pair` accepts `email`; one asserts it rejects
`phone_number`. If someone flips `USERNAME_FIELD` back without updating the frontend, the
second fails.

We would revisit this if customer registration proved a real drop-off point, in which case
phone-plus-OTP is the alternative — and it is a larger change than swapping a field, because
it replaces the password flow entirely.
