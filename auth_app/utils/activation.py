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
password_reset_token = PasswordResetTokenGenerator()
_UID_RE = re.compile(r"[^A-Za-z0-9_-]")
_TOKEN_RE = re.compile(r"[^A-Za-z0-9-]")


def make_activation_token(user_id: int) -> str:
    """
    Create a URL-safe signed activation token for a user ID.

    Parameters:
    user_id : int
        The ID of the user to encode into the token.

    Returns:
    str
        A signed, URL-safe token string encoding the provided user ID,
        suitable for use in account activation links.

    Notes:
    The token is generated using the module-level ACTIVATION_SALT and the
    signing utility to protect against tampering.
    """
    return signing.dumps({"uid": user_id}, salt=ACTIVATION_SALT)


def verify_activation_token(token: str) -> int:
    """
    Verify a signed activation token and return the user id it encodes.

    Validates and unsigns the given token using ACTIVATION_SALT and the
    ACTIVATION_TOKEN_MAX_AGE_SECONDS setting (defaults to 86400 seconds). On
    success, returns the 'uid' value from the token payload as an int.

    Parameters:
    token : str
        Signed activation token to verify.

    Returns:
    int
        The user id extracted from the token.

    Raises:
    django.core.signing.SignatureExpired
        If the token's age exceeds the configured max_age.
    django.core.signing.BadSignature
        If the token is invalid or has been tampered with.
    """
    data = signing.loads(
        token,
        salt=ACTIVATION_SALT,
        max_age=getattr(settings, "ACTIVATION_TOKEN_MAX_AGE_SECONDS", 86400),
    )
    return int(data["uid"])


def encode_uid(user_id: int) -> str:
    """
    Encode a user ID as a URL-safe base64 string without padding.

    The integer user_id is converted to bytes (via force_bytes), then encoded
    with urlsafe_base64_encode. Any trailing '=' padding characters are removed
    so the result is safe for inclusion in URLs and tokens.

    Args:
        user_id (int): The user ID to encode.

    Returns:
        str: URL-safe base64-encoded representation of the user ID with padding removed.

    Raises:
        TypeError: If the provided user_id cannot be converted to bytes.
    """
    return urlsafe_base64_encode(force_bytes(user_id)).rstrip("=")


def decode_uid(uidb64: str) -> int:
    """Decode a URL-safe base64-encoded user id string to an integer.

    Parameters:
    uidb64 : str
        URL-safe base64-encoded representation of an integer user id.
        Padding characters ('=') may be omitted.

    Returns:
    int
        The decoded integer user id.

    Raises:
    ValueError
        If the input cannot be base64-decoded to a valid integer.

    Examples:
    >>> decode_uid("MTIz")  # base64 for "123"
    123
    """
    padding = "=" * (-len(uidb64) % 4)
    return int(force_str(urlsafe_base64_decode(uidb64 + padding)))


def sanitize_uid(value: str) -> str:
    """
    Sanitize a UID-like string by decoding quoted-printable artifacts, removing characters
    disallowed by the module's UID regex, and stripping trailing '=' padding.

    Parameters:
    value : str
        Raw UID input (may contain quoted-printable artifacts or unwanted characters).

    Returns:
    str
        Sanitized UID with internal decoding applied, disallowed characters removed,
        and trailing '=' characters stripped. May be an empty string if no valid
        characters remain.
    """
    value = _decode_qp_artifacts(value)
    value = _UID_RE.sub("", value)
    return value.strip("=")


def sanitize_token(value: str) -> str:
    """
    Sanitize an activation token string.

    This function decodes common quoted-printable artifacts from the input and
    then removes any characters that do not match the internal token pattern
    (_TOKEN_RE). It is intended to produce a normalized token suitable for
    validation or storage after being transmitted in contexts that may introduce
    encoding artifacts (e.g., email or URL-safe encodings).

    Parameters:
    value : str
        The raw token value to sanitize.

    Returns:
    str
        The cleaned token containing only characters allowed by the token regex.

    Examples:
    >>> sanitize_token("abc=20def\r\n")
    "abcdef"
    """
    value = _decode_qp_artifacts(value)
    return _TOKEN_RE.sub("", value)


def _decode_qp_artifacts(value: str) -> str:
    """
    Normalize common artifacts produced by quoted-printable (QP) encoding.

    This function performs a lightweight cleanup of strings that may contain QP
    artifacts: it removes soft line breaks ("=\r\n" and "=\n"), decodes the QP
    representation of the equals sign ("=3D" -> "="), strips any repeated leading
    "3D" markers that can remain at the start of the string, and trims surrounding
    whitespace.

    Args:
        value (str): Input string that may contain quoted-printable artifacts.

    Returns:
        str: A cleaned string with common QP artifacts removed. Note that this is
        not a full quoted-printable decoder; it only handles a few common patterns.
    """
    value = value.replace("=\r\n", "").replace("=\n", "")
    value = value.replace("=3D", "=")
    while value.startswith("3D"):
        value = value[2:]
    return value.strip()


def activate_user(uidb64: str, token: str):
    """
    Activate a user account given a base64-encoded user id and an activation token.

    Parameters:
    uidb64 : str
        Base64-encoded user id (sanitized and decoded).
    token : str
        Activation token (sanitized).

    Returns:
    tuple[Optional[django.contrib.auth.models.AbstractBaseUser], Optional[str]]
        (user, None) on success where `user` is the activated User instance.
        (None, error_message) on failure. Possible error messages include
        "Invalid activation link." and "Invalid or expired token."

    Behavior:
    - Sanitizes `uidb64` and `token`.
    - Decodes `uidb64` to obtain the user id and fetches the user via `get_user_model()`.
    - Validates the token using `account_activation_token.check_token(user, token)`.
    - If valid and the user is not already active, sets `user.is_active = True` and saves it.
    - Catches decoding/lookup exceptions and token validation failures and returns an appropriate error message instead of raising.
    """
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
