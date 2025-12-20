from django.conf import settings
from django.core.mail import send_mail

from auth_app.utils.activation import account_activation_token, encode_uid


def send_activation_email(user, request=None):
    uid = encode_uid(user.id)
    token = account_activation_token.make_token(user)

    if request:
        activate_url = (
            f"{request.build_absolute_uri(settings.FRONTEND_ACTIVATION_URL)}"
            f"?uid={uid}&token={token}"
        )
    else:
        activate_url = f"{settings.FRONTEND_ACTIVATION_URL}?uid={uid}&token={token}"

    subject = "Activate your account"
    message = (
        "Hi!\n\n"
        "Please activate your account by clicking the link below:\n"
        f"{activate_url}\n\n"
        "If you did not sign up, you can ignore this email."
    )

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
