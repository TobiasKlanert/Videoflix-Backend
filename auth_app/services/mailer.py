from django.conf import settings
from django.core.mail import EmailMultiAlternatives

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

    display_name = user.get_username() if hasattr(
        user, "get_username") else user.email

    subject = "Activate your account"
    text_message = (
        f"Dear {display_name},\n\n"
        "Thank you for registering with Videoflix. To complete your registration and verify your email address, please click the link below:\n"
        f"{activate_url}\n\n"
        "If you did not create an account with us, please disregard this email.\n\n"
        "Best regards,\n\n"
        "Your Videoflix Team."
    )
    html_message = f"""\
<p>Dear {display_name},</p>
<p>Thank you for registering with Videoflix. To complete your registration and verify your email address, please click the button below:</p>
<p>
  <a href="{activate_url}" style="display:inline-block;font-size:18px;font-weight:600;padding:12px 24px;background:rgba(46, 62, 223, 1);color:rgb(255, 255, 255);text-decoration:none;border-radius:40px;">
    Activate account
  </a>
</p>
<p>If you did not create an account with us, please disregard this email.</p>
<p>Best regards,<br>Your Videoflix Team.</p>
"""

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_message, "text/html")
    email.send()
