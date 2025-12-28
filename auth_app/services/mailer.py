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
    """
    Return the filesystem path to the application's logo icon.

    Constructs and returns a pathlib.Path pointing to "static/assets/logo_icon.png"
    located under settings.BASE_DIR.

    Returns:
        pathlib.Path: Path to the logo_icon.png file.

    Notes:
        - The function does not check whether the file exists; callers should
          verify existence if required.
        - Relies on settings.BASE_DIR being a valid base directory (typically a str or Path).
    """
    return Path(settings.BASE_DIR) / "static" / "assets" / "logo_icon.png"


def _attach_logo(email):
    """Attach the application logo image to the provided email message as an inline MIME image.

    Parameters:
    email : email.message.EmailMessage (or compatible)
        The email message object to which the logo will be attached. The object must support
        an attach() method that accepts a MIME part.

    Behavior:
    - Resolves the logo file location via the module helper _logo_path().
    - If the resolved path does not exist, the function returns immediately without modifying
      the email.
    - If the file exists, it is opened in binary mode, wrapped in a MIMEImage, and the MIME
      headers are set:
        - Content-ID is set to the module-level LOGO_CID (wrapped in angle brackets).
        - Content-Disposition is set to "inline" with the original filename.
    - The MIMEImage part is attached to the provided email message.

    Returns:
    None

    Notes:
    Relies on module-level identifiers/functions: _logo_path() and LOGO_CID.
    """
    path = _logo_path()
    if not path.exists():
        return
    with path.open("rb") as handle:
        image = MIMEImage(handle.read())
    image.add_header("Content-ID", f"<{LOGO_CID}>")
    image.add_header("Content-Disposition", "inline", filename=path.name)
    email.attach(image)


def send_activation_email(user, request=None):
    """
    Send an account activation email to a user.

    Parameters:
    user : object
        User instance with attributes:
        - id (used for UID encoding)
        - email (recipient address)
        - optional get_username() method (used for display name if present)
    request : django.http.HttpRequest or None, optional
        If provided, request.build_absolute_uri(settings.FRONTEND_ACTIVATION_URL)
        is used to construct an absolute activation URL; otherwise
        settings.FRONTEND_ACTIVATION_URL is used directly.

    Behavior:
    - Encodes the user's id and generates an activation token.
    - Builds an activation URL containing 'uid' and 'token' query parameters.
    - Composes both plain-text and HTML email bodies; the HTML includes an
      inline-logo referenced by a content ID and a call-to-action button linking
      to the activation URL.
    - Attaches the logo to the email and sends a multipart (text + HTML) email
      from settings.DEFAULT_FROM_EMAIL to the user's email address.

    Returns:
    None

    Raises:
    Any exceptions raised by UID/token generation, URL building, email
    construction/attachment, or sending (e.g., AttributeError, SMTP-related
    exceptions) may be propagated to the caller.
    """
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
<br>
<p>Dear {display_name},</p>
<p>Thank you for registering with Videoflix. To complete your registration and verify your email address, please click the button below:</p>
<br>
<p>
  <a href="{activate_url}" style="display:inline-block;font-size:18px;font-weight:600;padding:12px 24px;background:rgba(46, 62, 223, 1);color:rgb(255, 255, 255);text-decoration:none;border-radius:40px;">
    Activate account
  </a>
</p>
<br>
<p>If you did not create an account with us, please disregard this email.</p>
<br>
<p>Best regards,<br><br>Your Videoflix Team.</p>
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
    """
    Send a password-reset email to a user.

    Parameters:
    user : object
        User-like object providing at minimum:
        - id: used to generate an encoded UID for the reset link.
        - email: recipient address.
        - get_username() (optional): used as display name when present.
    request : django.http.HttpRequest, optional
        If provided, used to build an absolute frontend reset URL via
        request.build_absolute_uri(settings.FRONTEND_PASSWORD_RESET_URL).
        If omitted, settings.FRONTEND_PASSWORD_RESET_URL is used directly.

    Behavior:
    - Generates a UID and password reset token.
    - Builds a frontend reset URL with query parameters ?uid=<uid>&token=<token>.
    - Composes a plain-text and HTML multipart email (HTML includes a CTA button and
      an inline logo referenced by a content ID).
    - Attaches the logo and sends the email via Django's EmailMultiAlternatives.

    Returns:
    None

    Raises:
    AttributeError
        If required attributes (e.g., id or email) are missing on the user object.
    django.core.mail.MailException or smtplib.SMTPException
        If sending the email fails.

    Notes:
    - Relies on settings.FRONTEND_PASSWORD_RESET_URL and settings.DEFAULT_FROM_EMAIL.
    - Token lifetime is enforced by the token generator, not by this function.
    - This function has the side effect of sending an email and does not persist any state.
    """
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
<br>
<p>We recently received a request to reset your password.</p>
<p>If you made this request, please click on the following link to reset your password:</p>
<br>
<p>
  <a href="{reset_url}" style="display:inline-block;font-size:18px;font-weight:600;padding:12px 24px;background:rgba(46, 62, 223, 1);color:rgb(255, 255, 255);text-decoration:none;border-radius:40px;">
    Reset password
  </a>
</p>
<br>
<p>Please note that for security reasons, this link is only valid for 24 hours.</p>
<br>
<p>If you did not request a password reset, please ignore this email.</p>
<br>
<p>Best regards,<br>Your Videoflix Team.</p>
<br>
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
