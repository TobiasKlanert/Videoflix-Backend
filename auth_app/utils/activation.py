import re

from django.conf import settings
from django.core import signing
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth import get_user_model
from django.utils.encoding import force_bytes, force_str
from django.utils.http import (
    urlsafe_base64_encode,
    urlsafe_base64_decode,
)

ACTIVATION_SALT = "account-activation"
account_activation_token = PasswordResetTokenGenerator()
_UID_RE = re.compile(r"[^A-Za-z0-9_-]")
_TOKEN_RE = re.compile(r"[^A-Za-z0-9-]")


def make_activation_token(user_id: int) -> str:
    return signing.dumps({"uid": user_id}, salt=ACTIVATION_SALT)


def verify_activation_token(token: str) -> int:
    data = signing.loads(
        token,
        salt=ACTIVATION_SALT,
        max_age=getattr(settings, "ACTIVATION_TOKEN_MAX_AGE_SECONDS", 86400),
    )
    return int(data["uid"])


def encode_uid(user_id: int) -> str:
    return urlsafe_base64_encode(force_bytes(user_id)).rstrip("=")


def decode_uid(uidb64: str) -> int:
    padding = "=" * (-len(uidb64) % 4)
    return int(force_str(urlsafe_base64_decode(uidb64 + padding)))


def sanitize_uid(value: str) -> str:
    value = _decode_qp_artifacts(value)
    value = _UID_RE.sub("", value)
    return value.strip("=")


def sanitize_token(value: str) -> str:
    value = _decode_qp_artifacts(value)
    return _TOKEN_RE.sub("", value)


def _decode_qp_artifacts(value: str) -> str:
    value = value.replace("=\r\n", "").replace("=\n", "")
    value = value.replace("=3D", "=")
    while value.startswith("3D"):
        value = value[2:]
    return value.strip()


def activate_user(uidb64: str, token: str):
    uidb64 = sanitize_uid(uidb64)
    token = sanitize_token(token)

    User = get_user_model()
    try:
        user_id = decode_uid(uidb64)
        user = User.objects.get(pk=user_id)
    except Exception:
        return None, "Invalid activation link."

    if not account_activation_token.check_token(user, token):
        return None, "Invalid or expired token."

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])

    return user, None
