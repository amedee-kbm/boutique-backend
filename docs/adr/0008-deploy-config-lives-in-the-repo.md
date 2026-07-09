# ADR-0008: Deploy config lives in the backend repo

## Status

Accepted.

## Context

the upstream project is three repositories: `upstream-backend`, `upstream-frontend`, and `infra`. The application
repositories build a container image and push it to a registry. The infra repository holds
`docker-compose.yml`, a `Caddyfile`, an interactive `setup.sh`, and the observability stack —
and consumes the published image tag.

The image is the interface. The application never knows where it runs.

It is a clean separation, and it explains much of what was inherited: their `publish.yaml`
pushes to `an upstream container registry` and stops, and `backend/observability/` turned out to be a
copy of that third repository's directory, describing a cluster Zita does not have.

## Decision

**`render.yaml` lives in the backend repository, beside the code it deploys.** There is no
`zita-infra`.

The backend deploys to Render: a web service, two background workers (a Celery worker and a
Celery beat scheduler), and a managed Redis, all in Frankfurt beside the Neon database.

Postgres is Neon's and images will be R2's, so nothing needs a persistent disk. That
statelessness is what makes a managed platform correct here rather than a VPS.

## Consequences

Infrastructure is a reviewable diff, gated by the same CI as everything else, in the same pull
request as the change that requires it. Adding an environment variable and the code that reads
it happens once.

We give up multi-environment deploys from a single source of truth, and the ability to change
where the app runs without touching the app's repository. For one developer that indirection
is overhead — and buying it back later is a day's work, not a rewrite.

Frankfurt, not somewhere closer to Kigali, because Neon has no African region. The database
round trip dominates any edge-proximity argument, so the application belongs next to the
database.

We revisit this the moment a second environment exists — staging, or a second tenant — or if
the deploy target becomes something the application repository genuinely should not know
about.

One note worth keeping from `the upstream infrastructure repository`, whose `Caddyfile` warns: *"MUST NOT buffer
responses. Buffering breaks SvelteKit's streaming SSR."* Next's App Router streams RSC
payloads the same way. Whatever proxy sits in front of the Next app, that constraint applies.
It is recorded in [engineering-notes.md](../engineering-notes.md), because it is not lintable.
