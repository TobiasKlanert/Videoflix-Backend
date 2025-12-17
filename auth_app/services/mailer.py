from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def send_activation_email(user_email: str, activation_token: str, request=None):
    if request:
        activate_url = request.build_absolute_uri(
            reverse("activate-account") + f"?token={activation_token}"
        )
    else:
        activate_url = f"{settings.FRONTEND_ACTIVATION_URL}?token={activation_token}"

    subject = "Activate your account"
    message = (
        "Hi!\n\n"
        "Please activate your account by clicking the link below:\n"
        f"{activate_url}\n\n"
        "If you didn’t sign up, you can ignore this email."
    )

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email])
