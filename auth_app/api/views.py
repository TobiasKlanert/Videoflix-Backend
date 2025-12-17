from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .serializers import RegisterSerializer
from auth_app.utils.activation import (
    account_activation_token,
    encode_uid,
    decode_uid,
)

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        uidb64 = encode_uid(user.id)
        token = account_activation_token.make_token(user)

        activation_link = (
            f"{settings.FRONTEND_ACTIVATION_URL}"
            f"?uidb64={uidb64}&token={token}"
        )

        send_mail(
            "Activate your account",
            f"Click the link to activate your account:\n\n{activation_link}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )

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
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            user_id = decode_uid(uidb64)
            user = User.objects.get(pk=user_id)
        except Exception:
            return Response(
                {"message": "Invalid activation link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not account_activation_token.check_token(user, token):
            return Response(
                {"message": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

        return Response(
            {"message": "Account successfully activated."},
            status=status.HTTP_200_OK,
        )
