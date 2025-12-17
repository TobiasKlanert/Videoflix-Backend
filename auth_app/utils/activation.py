from django.conf import settings
from django.core import signing
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import (
    urlsafe_base64_encode,
    urlsafe_base64_decode,
)

ACTIVATION_SALT = "account-activation"
account_activation_token = PasswordResetTokenGenerator()


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
    return urlsafe_base64_encode(force_bytes(user_id))


def decode_uid(uidb64: str) -> int:
    return int(force_str(urlsafe_base64_decode(uidb64)))
