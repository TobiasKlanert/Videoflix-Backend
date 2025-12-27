from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from auth_app.utils.activation import (
    account_activation_token,
    encode_uid,
    password_reset_token,
)

LOGO_CID = "videoflix_logo"


def _logo_path():
    return Path(settings.BASE_DIR) / "static" / "assets" / "logo_icon.png"


def _attach_logo(email):
    path = _logo_path()
    if not path.exists():
        return
    with path.open("rb") as handle:
        image = MIMEImage(handle.read())
    image.add_header("Content-ID", f"<{LOGO_CID}>")
    image.add_header("Content-Disposition", "inline", filename=path.name)
    email.attach(image)


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
<p style="text-align:center;">
  <img src="cid:{LOGO_CID}" alt="Videoflix" width="120" style="display:block;margin:0 auto;">
</p>
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
    _attach_logo(email)
    email.attach_alternative(html_message, "text/html")
    email.send()


def send_password_reset_email(user, request=None):
    uid = encode_uid(user.id)
    token = password_reset_token.make_token(user)

    if request:
        reset_url = (
            f"{request.build_absolute_uri(settings.FRONTEND_PASSWORD_RESET_URL)}"
            f"?uid={uid}&token={token}"
        )
    else:
        reset_url = f"{settings.FRONTEND_PASSWORD_RESET_URL}?uid={uid}&token={token}"

    display_name = user.get_username() if hasattr(
        user, "get_username") else user.email

    subject = "Reset your password"
    text_message = (
        f"Hello,\n\n"
        "We recently received a request to reset your password. "
        "If you made this request, please click on the following link to reset your password:\n"
        f"{reset_url}\n\n"
        "Please note that for security reasons, this link is only valid for 24 hours.\n\n"
        "If you did not request a password reset, please ignore this email.\n\n"
        "Best regards,\n\n"
        "Your Videoflix Team."
    )
    html_message = f"""\
<p>Hello,</p>
<p>We recently received a request to reset your password.</p>
<p>If you made this request, please click on the following link to reset your password:</p>
<p>
  <a href="{reset_url}" style="display:inline-block;font-size:18px;font-weight:600;padding:12px 24px;background:rgba(46, 62, 223, 1);color:rgb(255, 255, 255);text-decoration:none;border-radius:40px;">
    Reset password
  </a>
</p>
<p>Please note that for security reasons, this link is only valid for 24 hours.</p>
<p>If you did not request a password reset, please ignore this email.</p>
<p>Best regards,<br>Your Videoflix Team.</p>
<p><img src="cid:{LOGO_CID}" alt="Videoflix" width="120"></p>
"""

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    _attach_logo(email)
    email.attach_alternative(html_message, "text/html")
    email.send()
