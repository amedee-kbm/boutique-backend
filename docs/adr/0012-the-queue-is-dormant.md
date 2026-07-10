# ADR-0012: The queue is dormant; the password-reset email is sent in the request

## Status

Accepted. Amends the deployment topology in [ADR-0008](0008-deploy-config-lives-in-the-repo.md),
which assumed a Celery worker and a beat scheduler.

## Context

This application has **one** background job: `users.send_password_reset_email`. Beat schedules
nothing at all.

Running that job asynchronously on Render costs a worker (~$7/month), a beat scheduler (~$7/month),
and a managed Redis (~$10/month). Twenty-four dollars a month, before launch, to deliver an
occasional email a second sooner than the request could.

Four alternatives were examined, and each was rejected for a reason worth recording.

**Oracle Cloud Always Free** would run the whole topology at no cost, and its terms defeat it:
Oracle reclaims an instance whose 95th-percentile CPU, network *and* memory utilisation all sit
below 20% for seven days. A pre-launch Django app with a worker waiting on an empty queue is not
near that threshold — it is nowhere near it. The free tier's idle rule selects precisely against
this workload. Defeating it means burning CPU in a keepalive loop, which is paying in electricity
and self-deception.

**A database-backed queue** — `procrastinate`, `django-q2`, `django-tasks` — removes Redis by using
Postgres, which we already pay for. `procrastinate` is the best of the three: MIT, typed
(`py.typed`, and we run `mypy --strict`), with retries and periodic tasks. `django-tasks` has
neither retries nor scheduling, and although Django 6 ships `django.tasks`, it ships only the
`immediate` and `dummy` backends — the database backend is a third-party package that depends on
the *backport*, so "just use the framework" is not on the table. `django-q2` is untyped.

But a database-backed queue means a worker that holds a connection and polls Postgres forever, so
**Neon's compute never autosuspends**. It trades a $10 Redis for Neon compute-hours. It also still
needs a worker process, so it saves the Redis and not the $7.

**`asyncio`** buys nothing here. We run `gunicorn boutique.wsgi:application` — there is no event
loop, and `asyncio.create_task()` raises. `send_mail` is a blocking SMTP call, so awaiting it inside
a loop would stall every concurrent request; the escape is `asyncio.to_thread`, which is a thread.
Fire-and-forget tasks also swallow exceptions unless the caller keeps the `Task` and inspects it. It
is a thread wearing a costume, on an ASGI migration.

**A background thread** gives a constant-time response and the same durability as `asyncio`: none.
It also makes an unauthenticated, unrate-limited endpoint into an amplification lever — one thread
and one SMTP connection per request — unless the pool is bounded.

## Decision

**Send the email synchronously, in the request. Keep the queue's code, delete none of it.**

`send_password_reset` calls `send_password_reset_email.apply(args=[pk], throw=False)`. `.apply()`
executes the task in this process regardless of `CELERY_TASK_ALWAYS_EAGER`, so nothing depends on a
Celery setting and no broker connection is ever opened. `throw=False` means an SMTP failure produces
a `FAILURE` result that is logged, rather than an exception that becomes a 500.

What stays: the Celery app, `tasks.py`, the pinned name `users.send_password_reset_email`, the
`make task-names` gate, and every test. `render.yaml` keeps the worker and Redis as a commented
block.

Render runs **one free web service**.

## Consequences

**The response is no longer constant-time.** Measured against the running container, with Django's
*console* email backend: an unknown address returns in **18 ms**, a known one in **170 ms**. A real
SMTP round trip widens that to roughly a second. The status code and body are identical — a test
asserts it — but the clock is an enumeration oracle. This is a real regression against `SECURITY.md`,
and it is recorded there rather than left for someone to find.

**An SMTP failure must never become a 500**, because a 500 for a known address and a 200 for an
unknown one is enumeration by status code. A test asserts this, and it was proven red before it was
trusted green ([ADR-0009](0009-a-gate-must-be-seen-to-fail.md)).

**`/auth/password/reset-request` now holds a gunicorn thread for the duration of an SMTP round
trip.** With two workers and four threads, eight concurrent requests occupy the server. The endpoint
is unauthenticated and unrate-limited. Rate limiting was already on the list of things not done; it
moved up it.

**A reset email in flight is lost if the process restarts.** The customer clicks the link again.

**Free-tier consequences.** `preDeployCommand` requires a paid instance, so migrations run at
container start. That races other instances — safe only because the free plan runs exactly one.
Free web services also spin down when idle, so the first request after a quiet period is slow.

## Reversal

Restore the queue when **either** becomes true:

1. A second asynchronous task exists.
2. The first task appears whose loss actually matters. A password-reset email lost to a restart
   means the customer clicks again. An order confirmation lost to a restart is a different
   conversation, and orders are coming.

The work is: uncomment the block in `render.yaml`, add `CELERY_BROKER_URL` to the web service, and
change `.apply(...)` back to `.delay(...)`. Roughly ten lines. The task name is already pinned, so no
queued message and no beat row breaks.

If instead the queue should be Postgres-backed rather than Redis-backed, `procrastinate` is the
choice already argued above — but note that it keeps Neon awake, and price that before choosing it.
