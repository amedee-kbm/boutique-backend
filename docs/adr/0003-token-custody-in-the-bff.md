# ADR-0003: Token custody lives in the Next BFF

## Status

Accepted.

## Context

Django issues a JWT access/refresh pair. Something has to hold them.

The browser is the obvious place and the wrong one. `localStorage` is readable by any
script that ends up on the page, which is every XSS bug you have not found yet. Keeping the
access token in memory is better, but it dies on refresh and it still crosses into
JavaScript's reach.

The subtler trap is specific to React Server Components, and it is worth stating precisely
because it has no symptom.

**Any value a Server Component passes as a prop to a Client Component is serialized into the
RSC Flight payload and shipped to the browser.** So is anything a Server Action returns.
There is no type error. There is no warning. The token simply appears in view-source, in the
streamed response, in proxy logs, and in the browser's back/forward cache.

The boundary that leaks is a prop. It does not look like a boundary. In a classic SSR
framework the leak at least has a name — the upstream project's SvelteKit frontend shipped one in
`upstream-frontend#387`, where a bearer JWT returned from a `load` function was serialized into
the page HTML. In RSC the same leak is available from any Server Component, silently.

## Decision

**The tokens live in HttpOnly cookies on the Next origin, and only the BFF may read them.**

- `/api/auth/login` exchanges credentials at Django's `/auth/pair`, writes both tokens to
  HttpOnly, SameSite=Lax cookies, and returns **only** the user object to the browser.
- `/api/django/[...path]` is a same-origin proxy. It reads the access cookie server-side,
  attaches `Authorization: Bearer`, forwards to Django, and on a 401 refreshes once and
  retries. Token expiry is invisible to the caller.
- `/api/auth/logout` blacklists the refresh token server-side, then clears both cookies —
  and clears them even if the blacklist call fails.
- The browser calls the BFF. The BFF calls Django. The browser never holds a token.

Enforced mechanically by `frontend/scripts/check-rsc-token.mjs`, which is part of
`make check`:

1. **Only the four BFF files may import `lib/auth/tokens`.** This subsumes "a Server
   Component read the token" — it cannot.
2. No `'use client'` file may name a token identifier or cookie name.
3. No `NEXT_PUBLIC_*` variable may be named like a credential. Anything so prefixed is
   inlined into the client bundle. Two reviewed exceptions carry written reasons.
4. `tokens.ts` and `refresh.ts` must `import 'server-only'`, so a client import fails at
   build time rather than at runtime.

Rule 1 is the invariant. Rules 2–4 are defence in depth.

## Consequences

Every authenticated read from the browser is a same-origin call to `/api/django/*`, one hop
longer than calling Django directly. This is the price, and it is small: the hop is
process-local in production, and CORS stops being a concern for that path entirely.

A Server Component cannot fetch authenticated data by reading the cookie. It must go through
the BFF like everyone else. This feels like a restriction and is the entire point — the
alternative is a prop away from a leak.

Refresh-token rotation is safe because the proxy is the only refresher. Django blacklists
each refresh token on use (`ROTATE_REFRESH_TOKENS`, `BLACKLIST_AFTER_ROTATION`), and two
concurrent refreshes cannot race because only one place performs them.

We would revisit this if the frontend stopped being the only client. A mobile app cannot use
HttpOnly cookies and would need tokens in the clear, at which point the BFF becomes one
consumer of Django's auth rather than its custodian.

Verified by hand once, before the script was trusted: register through the real app, confirm
the `auth-token` cookie is `HttpOnly`, and confirm the token appears nowhere in the page
source or the Flight payload. See [ADR-0009](0009-a-gate-must-be-seen-to-fail.md).
