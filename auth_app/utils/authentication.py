"""Custom JWT authentication that also reads the access token from cookies."""

from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate requests using a JWT supplied either in the Authorization header
    or in an 'access_token' cookie.

    This class extends JWTAuthentication and overrides authenticate(request)
    to allow the access token to be provided via a cookie as a fallback when no
    Authorization header is present.

    Behavior:
    - First attempts to extract a raw token from the Authorization header using
        self.get_header and self.get_raw_token (i.e. header takes precedence).
    - If no token is found in the header, attempts to read the token from
        request.COOKIES['access_token'].
    - If no token is found at all, returns None so other authentication backends
        can run or the request is treated as unauthenticated.
    - If a raw token is found, it is validated with self.get_validated_token and
        the corresponding user is retrieved with self.get_user.
    - On success returns a (user, validated_token) tuple. On invalid token cases
        the underlying validation methods will raise the appropriate authentication
        exceptions.

    Parameters:
    - request: Django HttpRequest instance.

    Returns:
    - tuple(user, validated_token) on successful authentication, or None if no
        token was provided.

    Security notes:
    - The cookie name expected is 'access_token'. For production use, store this
        cookie with Secure, HttpOnly and an appropriate SameSite attribute to reduce
        exposure to XSS/CSRF.
    - Prefer sending tokens in the Authorization header where feasible; the cookie
        fallback is intended for convenience in browser-based flows.
    """

    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = None

        if header is not None:
            raw_token = self.get_raw_token(header)

        if raw_token is None:
            raw_token = request.COOKIES.get("access_token")

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
