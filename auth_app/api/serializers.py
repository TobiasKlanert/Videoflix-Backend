from django.contrib.auth import get_user_model
from django.utils.text import slugify

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    confirmed_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("email", "password", "confirmed_password")
        extra_kwargs = {"password": {"write_only": True}}

    def validate(self, attrs):
        if attrs["password"] != attrs["confirmed_password"]:
            raise serializers.ValidationError(
                {"confirmed_password": "Passwords do not match."})
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
