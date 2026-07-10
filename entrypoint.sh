#!/bin/sh
#
# Start the web service: migrate, then serve.
#
# This exists because Render splits `dockerCommand` on whitespace and execs it
# directly — there is no shell, so `a && b` is not expressible: `&&` and the
# second command are passed to the first as arguments. Wrapping it in `sh -c`
# does not help either, because the quotes survive the split.
#
# So the two-step start lives in the image, where it can be tested with a plain
# `docker run` and behaves identically in both places.
#
# Migrations run here rather than as a pre-deploy command because
# `preDeployCommand` requires a paid instance type. A container that migrates on
# boot races every other container booting at the same time; that is safe for
# exactly one reason — the free plan runs a single instance. Move to a paid plan
# and this must become `preDeployCommand` *before* scaling past one instance.

set -eu

python manage.py migrate --noinput

# exec, so gunicorn becomes PID 1 and receives SIGTERM directly. Without it the
# shell holds PID 1, swallows the signal, and Render kills the container after
# its grace period instead of letting gunicorn drain its connections.
exec gunicorn boutique.wsgi:application \
	--bind "0.0.0.0:${PORT:-8000}" \
	--workers 2 \
	--threads 4 \
	--timeout 60 \
	--access-logfile - \
	--error-logfile -
