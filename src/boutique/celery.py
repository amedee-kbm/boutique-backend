import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "boutique.settings")

app = Celery("boutique")

# Read CELERY_* keys from Django settings; workers discover each app's tasks.py.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
