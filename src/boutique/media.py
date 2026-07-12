"""Storage configuration for product images.

Kept out of settings.py so that module stays under its length ceiling, and so
the R2 wiring lives in one named place.
"""

import typing as t

import environ


def build_storages(env: environ.Env) -> dict[str, t.Any]:
    """The ``STORAGES`` setting.

    WhiteNoise fingerprints the admin's own static assets on collectstatic, so
    they need no separate web server; this app serves no user-facing static
    files. Product images go to R2 (see ``product_image_storage``). The default
    backend is the local filesystem and is essentially unused.
    """
    return {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
        "product_images": product_image_storage(env),
    }


def product_image_storage(env: environ.Env) -> dict[str, t.Any]:
    """The ``product_images`` storage backend.

    Cloudflare R2 when a bucket is configured: written through django-storages'
    S3 backend to R2's S3-compatible endpoint and served from a public custom
    domain, not signed URLs (``querystring_auth`` off; R2 has no ACLs). Without
    a bucket in the environment — CI and tests — it degrades to an in-memory
    backend, so nothing reaches the network.
    """
    bucket = env.str("R2_BUCKET", default="")
    if not bucket:
        return {
            "BACKEND": "django.core.files.storage.InMemoryStorage",
            "OPTIONS": {"base_url": "http://testserver/media/"},
        }
    # custom_domain must be a bare host — a scheme would double up in the URL.
    public_host = env.str("R2_PUBLIC_HOST").removeprefix("https://").removeprefix("http://").rstrip("/")
    return {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": bucket,
            "endpoint_url": env.str("R2_ENDPOINT"),
            "access_key": env.str("R2_ACCESS_KEY_ID"),
            "secret_key": env.str("R2_SECRET_ACCESS_KEY"),
            "custom_domain": public_host,
            "querystring_auth": False,
            "default_acl": None,
            "file_overwrite": False,
            "region_name": "auto",
        },
    }
