from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


@shared_task(
    bind=True,
    ignore_result=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_password_reset_email(self, user_pk: str) -> None:
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
