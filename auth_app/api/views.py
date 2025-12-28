from django.contrib.auth import get_user_model
from django.conf import settings

from rest_framework import status

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, CustomTokenObtainPairSerializer

from auth_app.services.mailer import send_activation_email, send_password_reset_email
from auth_app.utils.activation import activate_user, password_reset_token, sanitize_uid, sanitize_token, decode_uid

User = get_user_model()


class RegisterView(APIView):
    """
    RegisterView: API endpoint to register a new user.

    Handles POST requests to create a user account using RegisterSerializer.
    - Validates incoming data using RegisterSerializer; on validation failure a 400
        response is raised by serializer.is_valid(raise_exception=True).
    - Persists the new user with serializer.save().
    - Sends an account activation email by calling send_activation_email(user, request=request).
    - Returns HTTP 201 Created with a minimal JSON payload containing the new user's id and email:
        {"user": {"id": <int>, "email": "<string>"}}

    Permissions:
    - AllowAny: no authentication required to access this endpoint.

    Side effects:
    - Creates a user record in the database.
    - Triggers an outbound email (activation) as part of the registration flow.

    Notes:
    - The exact request schema and required fields are defined by RegisterSerializer.
    - Other exceptions follow DRF's default error handling and may produce appropriate HTTP error responses.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        send_activation_email(user, request=request)

        return Response(
            {
                "user": {
                    "id": user.id,
                    "email": user.email,
                }
            },
            status=status.HTTP_201_CREATED,
        )


class ActivateAccountView(APIView):
    """
    APIView that handles account activation via a GET request.

    Expects:
    - uidb64 (str): Base64-encoded user ID taken from the activation URL.
    - token (str): One-time activation token associated with the user.

    Behavior:
    - Calls activate_user(uidb64, token) which returns (user, error).
    - If an error is returned, responds with HTTP 400 and a JSON message containing the error.
    - If activation succeeds, responds with HTTP 200 and a success message.

    Responses:
    - 200: {"message": "Account successfully activated."}
    - 400: {"message": "<error message>"}

    Permissions:
    - AllowAny: no authentication required to access this endpoint.

    Notes:
    - The request object is accepted to match the DRF view signature but is not directly used by the method.
    - The returned user value from activate_user is not used beyond activation success handling.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        user, error = activate_user(uidb64, token)
        if error:
            return Response(
                {"message": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Account successfully activated."},
            status=status.HTTP_200_OK,
        )

class CookieTokenObtainPairView(TokenObtainPairView):
    """
    Authenticate a user and return JWT tokens as HTTP-only cookies.

    This view extends TokenObtainPairView and uses CustomTokenObtainPairSerializer to
    authenticate credentials and obtain an access and refresh token pair. On a successful
    POST it:

    - Calls the parent implementation to validate credentials and produce token data.
    - Extracts 'access', 'refresh' and 'user' from the parent response.
    - Replaces the response body with a minimal success payload containing a message
        and serialized user information.
    - Attaches two cookies to the response:
            - 'access_token' (HttpOnly)
            - 'refresh_token' (HttpOnly)
        Both cookies use samesite='Lax' and set secure=True when settings.DEBUG is False.

    Security notes:
    - Cookies are HttpOnly to mitigate JavaScript access (XSS). The secure flag is
        enabled in non-debug environments to require HTTPS.
    - Refresh handling may still require CSRF protection depending on your frontend
        and refresh flow; consider additional CSRF/rotation measures and appropriate
        token lifetimes.

    Behavior:
    - Returns the Response instance produced by the parent view with cookies set.
    - Propagates authentication/validation errors raised by the parent implementation.
    """
    serializer_class = CustomTokenObtainPairSerializer
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        data = response.data

        access = data.get("access")
        refresh = data.get("refresh")
        user = data.get("user")

        response.data = {
            "detail": "Login successful!",
            "user": user
        }

        response.set_cookie(
            key='access_token',
            value=str(access),
            httponly=True,
            secure=not settings.DEBUG,
            samesite='Lax'
        )

        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            httponly=True,
            secure=not settings.DEBUG,
            samesite='Lax'
        )

        return response


class LogoutCookieView(APIView):
    """
    Logs out an authenticated user by blacklisting the JWT refresh token found in cookies and removing authentication cookies from the response.

    Behavior:
    - Permission: IsAuthenticated
    - POST:
        - Reads 'refresh_token' from request.COOKIES.
        - If missing: returns HTTP 400 with {"detail": "Refresh token not found!"}.
        - If present: constructs a RefreshToken and calls token.blacklist() to invalidate the refresh token.
        - Deletes 'access_token' and 'refresh_token' cookies from the response.
        - Returns HTTP 200 with {"detail": "Logout successful! All tokens will be deleted. Refresh token is now invalid."}.

    Side effects and requirements:
    - Blacklisting requires the Simple JWT token blacklist app to be enabled.
    - Access tokens are not actively revoked server-side (stateless); this view removes client cookies to prevent further use.
    - Token construction or blacklisting may raise token-related exceptions which are not explicitly handled here.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        token = RefreshToken(refresh_token)
        token.blacklist()

        response = Response(
            {"detail": "Logout successful! All tokens will be deleted. Refresh token is now invalid."}, status=status.HTTP_200_OK)
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response


class CookieRefreshView(TokenRefreshView):
    """
    Class-based view that overrides TokenRefreshView.post to refresh an access token
    using a refresh token stored in an HTTP cookie.

    Behavior:
    - Reads the refresh token from the request cookie named 'refresh_token'.
    - If the cookie is missing, returns a 400 Bad Request with detail "Refresh token not found!".
    - Uses self.get_serializer(data={'refresh': refresh_token}) to validate the refresh token.
    - If validation fails, returns a 401 Unauthorized with detail "Refresh token invalid!".
    - On successful validation, retrieves the new access token from serializer.validated_data['access'],
        returns a 200 OK JSON response containing {"detail": "Token refreshed", "access": <token>},
        and sets an 'access_token' cookie containing the access token.

    Side effects / Cookie behavior:
    - Sets an 'access_token' cookie with these attributes:
        - httponly=True (not accessible to JavaScript)
        - secure=not settings.DEBUG (secure flag enabled in production)
        - samesite='Lax'

    Notes:
    - The view intentionally does not read or use the positional/keyword parameters passed to post
        (i.e., *args and **kwargs are unused).
    - HTTP status codes used:
        - 200 OK on success
        - 400 Bad Request when the refresh cookie is absent
        - 401 Unauthorized when the refresh token is invalid
    - Relies on the serializer returned by self.get_serializer to perform standard token refresh validation
        (expected to provide 'access' in validated_data on success).
    """
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')

        if refresh_token is None:
            return Response(
                {"detail": "Refresh token not found!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data={'refresh': refresh_token})

        try:
            serializer.is_valid(raise_exception=True)
        except:
            return Response(
                {"detail": "Refresh token invalid!"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        access_token = serializer.validated_data.get('access')

        response = Response({
            "detail": "Token refreshed",
            "access": access_token
            })

        response.set_cookie(
            key='access_token',
            value=access_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite='Lax'
        )

        return response


class PasswordResetRequestView(APIView):
    """
    Handle POST requests to initiate a password reset for a user.

    Expected input:
    - request.data should contain:
        - "email" (string): the email address to look up; leading/trailing whitespace is trimmed.

    Behavior:
    - Permission: AllowAny (no authentication required).
    - Validates that an email value is provided; returns HTTP 400 if missing or empty.
    - Looks up a User by case-insensitive email (email__iexact). If no user is found, returns HTTP 404.
    - If a matching user is found, calls send_password_reset_email(user, request=request) to send reset instructions and returns HTTP 200.

    Responses (JSON):
    - 200 OK: {"detail": "An email has been sent to reset your password."}
    - 400 Bad Request: {"detail": "Email is required."}
    - 404 Not Found: {"detail": "No account found with this email."}

    Notes:
    - This endpoint reveals whether an account exists for the provided email (returns 404 for non-existent emails).
    - Side effect: triggers sending of a password reset email via the send_password_reset_email utility.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response(
                {"detail": "No account found with this email."},
                status=status.HTTP_404_NOT_FOUND,
            )

        send_password_reset_email(user, request=request)

        return Response(
            {"detail": "An email has been sent to reset your password."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """
    Handles POST requests to confirm and apply a previously initiated password reset.

    Expected URL parameters:
    - uidb64 (str): Base64/URL-safe encoded user identifier. This value is sanitized with sanitize_uid before decoding.
    - token (str): Password-reset token included in the reset link. This value is sanitized with sanitize_token before validation.

    Expected JSON body:
    - new_password (str): The new password to set. Required, trimmed of surrounding whitespace.
    - confirm_password (str): Confirmation of the new password. Required, trimmed of surrounding whitespace and must match new_password.

    Behavior:
    - Verifies both new_password and confirm_password are present and non-empty.
    - Ensures new_password and confirm_password match.
    - Decodes uidb64 to a user ID using decode_uid and fetches the corresponding User instance.
    - Validates the provided token against the user using password_reset_token.check_token.
    - If validation succeeds, sets the user's password (via User.set_password) and persists only the password field.

    HTTP responses (JSON):
    - 200 OK: {"detail": "Your Password has been successfully reset."}
    - 400 Bad Request: Returned for any of the following conditions with an explanatory message:
        - Missing new_password or confirm_password ("New password and confirmation are required.")
        - Passwords do not match ("Passwords do not match.")
        - uidb64 cannot be decoded or user not found ("Invalid reset link.")
        - Token is invalid or expired ("Invalid or expired token.")

    Permissions:
    - AllowAny: endpoint can be accessed without authentication.

    Notes:
    - All inputs are sanitized before use (sanitize_uid, sanitize_token).
    - Errors are handled by returning appropriate HTTP responses; no exceptions are propagated to the caller.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        uidb64 = sanitize_uid(uidb64)
        token = sanitize_token(token)

        new_password = (request.data.get("new_password") or "").strip()
        confirm_password = (request.data.get("confirm_password") or "").strip()

        if not new_password or not confirm_password:
            return Response(
                {"detail": "New password and confirmation are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {"detail": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_id = decode_uid(uidb64)
            user = User.objects.get(pk=user_id)
        except Exception:
            return Response(
                {"detail": "Invalid reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password_reset_token.check_token(user, token):
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        return Response(
            {"detail": "Your Password has been successfully reset."},
            status=status.HTTP_200_OK,
        )
