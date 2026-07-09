import typing as t

from celery import shared_task
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.users.models import User


@shared_task(
    # The name is the contract, not the module path. Without it Celery derives
    # `apps.users.tasks.send_password_reset_email`, which changes the moment the
    # module moves — orphaning queued messages and any beat row that names it.
    # Safe to choose freely today: nothing is deployed and no broker holds work.
    name="users.send_password_reset_email",
    bind=True,
    ignore_result=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_password_reset_email(self: t.Any, user_pk: str) -> None:
    """Mail a password-reset link to the user, retrying on SMTP failure.

    A missing user is not an error: the account may have been deleted between
    the request and the worker picking the job up.

    Args:
        self: the bound task, for `retry`.
        user_pk: primary key of the user to mail.
    """
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        return

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

    try:
        send_mail(
            subject="Reset your Zita Boutique password",
            message=(
                "We received a request to reset your password.\n\n"
                f"Open this link to choose a new one:\n{link}\n\n"
                "If you didn't request this, you can ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)
