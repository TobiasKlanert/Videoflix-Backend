from django.contrib.auth import get_user_model
from django.utils.text import slugify

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for registering a new user.

    This ModelSerializer accepts an email, password and confirmed_password and is
    responsible for validating the input and creating a new inactive User instance.

    Behavior
    - Fields:
        - email: the user's email address (from User model).
        - password: write-only password field.
        - confirmed_password: write-only field used to confirm the password.
    - Validation:
        - Ensures password and confirmed_password match.
        - Ensures the provided email is not already associated with an existing user.
        - On failure raises serializers.ValidationError with field-specific messages.
    - Creation:
        - Removes confirmed_password from validated data.
        - Extracts and hashes password with set_password().
        - If the User model uses a "username" USERNAME_FIELD and exposes a username
            attribute, generates a unique username derived from the email local part.
        - Marks the created user as inactive (is_active = False) and saves to DB.
        - Returns the created User instance.

    Helper
    - _generate_username(email):
        - Produces a URL-safe (slugified) base from the email local-part or "user".
        - Appends a numeric suffix if needed to avoid username collisions.

    Side effects
    - Persists a new User in the database with is_active=False.
    - May raise serializers.ValidationError during validation.
    """
    confirmed_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("email", "password", "confirmed_password")
        extra_kwargs = {"password": {"write_only": True}}

    def validate(self, attrs):
        if attrs["password"] != attrs["confirmed_password"]:
            raise serializers.ValidationError(
                {"confirmed_password": "Passwords do not match."})
        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError({"email": "Please check your entries and try again."
        })
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirmed_password")
        password = validated_data.pop("password")
        email = validated_data.get("email", "")

        if getattr(User, "USERNAME_FIELD", None) == "username" and hasattr(User, "username"):
            validated_data["username"] = self._generate_username(email)

        user = User(**validated_data)
        user.set_password(password)
        user.is_active = False
        user.save()
        return user

    def _generate_username(self, email):
        local_part = email.split("@")[0] if email else ""
        base = slugify(local_part) or "user"
        username = base
        suffix = 1

        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f"{base}{suffix}"

        return username


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer that issues JWT refresh and access tokens using an email credential.

    This class customizes TokenObtainPairSerializer to use "email" as the username_field
    and overrides validate(...) to perform authentication via a case-insensitive email
    lookup. validate expects attrs to contain "email" and "password"; it raises
    serializers.ValidationError if either is missing, if the credentials are invalid,
    or if the account is not active.

    On successful authentication, validate returns a dict containing:
    - "refresh": str(refresh token)
    - "access": str(access token)
    - "user": {"id": <user id>, "username": <user email>}
    """
    username_field = "email"

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if not email or not password:
            raise serializers.ValidationError(
                {"detail": "Email and password are required."})

        user = User.objects.filter(email__iexact=email).first()
        if user is None or not user.check_password(password):
            raise serializers.ValidationError(
                {"detail": "No active account found with the given credentials."})
        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "Account is not active."})

        self.user = user
        refresh = self.get_token(user)
        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
        data["user"] = {
            "id": self.user.id,
            "username": self.user.email
        }
        return data
