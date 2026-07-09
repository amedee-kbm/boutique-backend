# Engineering notes

Rules that cannot be linted. Each of these describes a failure that either cannot reproduce
locally, cannot be caught by a test, or hides behind a green checkmark. They are here because
prose is the only enforcement available.

Read the Celery and PgBouncer sections **before** dispatching a task from a request handler or
iterating a large queryset.

---

## Neon's pooled endpoint is PgBouncer, and it will not hold your cursor

Neon's pooled connection string (the host with `-pooler` in it) is PgBouncer in **transaction
pooling** mode. The server connection is returned to the pool at every `COMMIT`.

Two consequences, both configured in `boutique/settings.py`:

**`DISABLE_SERVER_SIDE_CURSORS = True`.** `QuerySet.iterator()` opens a server-side cursor by
default. Under transaction pooling that cursor is orphaned the moment the transaction commits,
and the next fetch fails with `InvalidCursorName`. So:

```python
# Wrong. Works against a local Postgres; dies against the pooler.
for order in Order.objects.filter(status="new").iterator():
    contact(order)

# Right. Materialise the ids, then work in bounded chunks.
order_ids = list(Order.objects.filter(status="new").values_list("id", flat=True))
for order_id in order_ids:
    with transaction.atomic():
        order = Order.objects.select_for_update().get(id=order_id)
        contact(order)
```

**`CONN_MAX_AGE = 0`.** A pooled connection is not ours to keep. Persistent connections against
PgBouncer exhaust the pool and stall every other worker.

**This class of bug cannot be caught by a test.** `compose.yaml` runs a plain Postgres with no
pooler, so the wrong code passes locally, passes in CI, and fails in production on the first
sweep over a table that has grown. That is why it is written down rather than asserted.

the upstream project learned this the hard way; we inherited the lesson without the outage.

---

## A Celery task's name is its contract, not its location

Every `@shared_task` **must** pass an explicit `name=`:

```python
@shared_task(name="users.send_password_reset_email", bind=True, max_retries=3)
def send_password_reset_email(self, user_pk: str) -> None: ...
```

A bare `@shared_task` registers under a name Celery derives from the module path —
`apps.users.tasks.send_password_reset_email`. That string is written into two places you do
not control:

1. Messages already sitting in the broker, which name the task they want run.
2. `django_celery_beat` `PeriodicTask` rows, which reference tasks by name.

Move or rename the module and the registered name changes silently. In-flight messages address
a task that no longer exists; beat rows point at nothing. **Nothing raises at import time.** The
symptom is tasks that simply never run, after a deploy, in production.

**When moving an existing task, keep its current name verbatim.** The name is the contract; the
file is an implementation detail.

Enforced statically by `scripts/check_task_names.py`, wired into `make check` and CI. It found
this exact bug in `apps/users/tasks.py` on its first run.

---

## `on_commit` never fires under pytest

`pytest-django` wraps each test in a transaction and rolls it back. `transaction.on_commit`
callbacks are therefore **never executed**.

This means a test asserting that a Celery task was dispatched from a request will pass whether
or not the dispatch is wired up. The mechanism under test was never allowed to run.

```python
def test_reset_enqueues_mail(client, customer, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        client.post("/api/v1/auth/password/reset-request", ...)
    assert len(mail.outbox) == 1
```

Use `django_capture_on_commit_callbacks(execute=True)`, or
`@pytest.mark.django_db(transaction=True)` with a docstring explaining why. Never both.

The general form of this trap: **if a test mocks or suppresses the thing that would actually
fail, it cannot catch that failure.** See the frontend note below.

---

## A green Vitest suite is not evidence the frontend works

Vitest imports modules directly. It applies none of Next's runtime contracts: no `"use server"`
enforcement, no RSC serialization, no `"use client"` boundary checking, no `await`-ing of async
request APIs.

A real example, from this codebase's history: a `"use server"` file may export **only async
functions**. Exporting `const schema = z.object(...)` from one throws
`A "use server" file can only export async functions, found object` at runtime and breaks every
action in that module. The unit tests were green. The browser was not.

So:

- Keep `"use server"` files as pure actions. Zod schemas, types and helpers shared with tests
  live in a sibling `*.schema.ts`.
- `npm run build` is the real check for server/client boundary violations. It collects page data
  and fails on a boundary breach. Run it before believing a refactor.
- For every mutation, one path must exercise it **unmocked**. A test that mocks `@/lib/db`
  proves the caller's logic, not that the write reaches the database.

---

## The token is a prop away from the browser

Under React Server Components, any value a Server Component passes as a prop to a Client
Component is serialized into the Flight payload and sent to the browser. So is anything a
Server Action returns. There is no type error and no warning.

The token stays in HttpOnly cookies, read only by the four BFF route handlers. This is
[ADR-0003](adr/0003-token-custody-in-the-bff.md), enforced by
`frontend/scripts/check-rsc-token.mjs`.

If a Server Component needs authenticated data, it calls `/api/django/*` like everyone else. It
does not read the cookie.

---

## Do not buffer responses in front of the Next app

Whatever proxy sits in front of the frontend must stream. Next's App Router delivers RSC
payloads progressively; a proxy that buffers the whole response before forwarding it converts a
streaming render into a blank page followed by everything at once.

Inherited from `the upstream infrastructure repository`'s `Caddyfile`, whose comment reads *"MUST NOT buffer responses.
Buffering breaks SvelteKit's streaming SSR."* Different framework, identical constraint.

---

## Windows: `make` hands recipes a stripped environment

MSYS `make` (Git Bash) removes the Windows environment variables before invoking a recipe. Three
symptoms, all fixed in the backend `Makefile`, all baffling on first contact:

- `docker compose` reports `unknown command: docker compose`, while the identical command typed
  into the same shell works. The Docker CLI cannot locate its `cli-plugins` directory. We call
  the plugin binary directly rather than rely on discovery.
- `pip-audit` dies with `Could not determine home directory` — Python's `expanduser()` on
  Windows reads `USERPROFILE`, never `HOME`.
- `uv` silently creates a literal `~/AppData/Local/…` **directory inside the repository**, having
  failed to expand `~`.

`USERPROFILE`, `LOCALAPPDATA` and `APPDATA` are restored at the top of the `Makefile`, guarded to
MSYS.

## Windows: a native Postgres may already own port 5432

If `postgres.exe` runs as a Windows service, Docker will still bind 5432 and report the container
healthy — but `localhost:5432` reaches the *other* server, which rejects your credentials with
`password authentication failed`. The error blames you; the cause is the port.

`compose.yaml` publishes **55432** for this reason. `make test` points at it, and the test
database URL lives in the `Makefile` rather than `.env`, so a stray `pytest` can never create a
test database on Neon.
