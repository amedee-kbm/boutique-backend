# syntax=docker/dockerfile:1

# Two stages. The builder resolves dependencies and compiles static assets; the
# runtime carries neither uv nor a compiler.
#
# This application needs nothing from apt. No PDF renderer, no geospatial
# libraries, no virus scanner, no headless browser — psycopg ships its own
# libpq wheel. The image is small because the application is small.

# ─── builder ─────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependencies before source, so a code change does not re-resolve the graph.
# --no-dev: the dev group is quality tooling and never ships.
# --locked: fail if uv.lock disagrees with pyproject.toml, rather than quietly
# resolving something nobody tested.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY src/ ./src/

# WhiteNoise's manifest storage refuses to serve a file it has not hashed, so
# collectstatic must run here rather than at boot. Settings read the environment
# at import, so it needs values — these are build-time only, reach nothing, and
# do not survive into the runtime stage.
RUN DJANGO_SECRET_KEY=build-time-only \
    DJANGO_DEBUG=False \
    DJANGO_APPEND_SLASH=True \
    DJANGO_ALLOWED_HOSTS= \
    DJANGO_CSRF_TRUSTED_ORIGINS= \
    FRONTEND_URL=http://localhost \
    DATABASE_URL=postgresql://build:build@localhost:5432/build \
    /app/.venv/bin/python src/manage.py collectstatic --noinput --clear

# ─── runtime ─────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# Unbuffered so Render's log stream shows a traceback as it happens, not after
# the process dies and flushes.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# A compromised dependency should not own the filesystem it runs on.
#
# Not `--system`: that flag means "a UID below SYS_UID_MAX (999)", and we pin
# 1001, so useradd honours the number and warns about the contradiction. The IDs
# are pinned deliberately — they must match the `--chown` in the COPY layers and
# stay stable across rebuilds — and this is the application's user, not a system
# daemon account. So state the UID and drop the flag that disagrees with it.
#
# --create-home, though nobody logs in: gunicorn's control server opens a socket
# under $HOME, and without the directory every boot logs `Control server error:
# [Errno 13] Permission denied`. Not fatal — but a recurring ERROR that everyone
# learns to ignore is worse than no log line at all.
RUN groupadd --gid 1001 boutique \
    && useradd --uid 1001 --gid boutique --create-home --shell /usr/sbin/nologin boutique

WORKDIR /app

COPY --from=builder --chown=boutique:boutique /app/.venv /app/.venv
COPY --from=builder --chown=boutique:boutique /app/src /app/src
COPY --chmod=0755 entrypoint.sh /app/entrypoint.sh

USER boutique
WORKDIR /app/src

EXPOSE 8000

# The start sequence lives in entrypoint.sh, not here and not in render.yaml:
# Render splits `dockerCommand` on whitespace and execs it, so `migrate && gunicorn`
# cannot be expressed there. Keeping it in the image means `docker run` exercises
# exactly what Render runs.
CMD ["/app/entrypoint.sh"]
