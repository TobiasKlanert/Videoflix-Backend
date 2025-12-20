from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from rest_framework import status

from .serializers import RegisterSerializer
from auth_app.services.mailer import send_activation_email
from auth_app.utils.activation import activate_user

User = get_user_model()


class RegisterView(APIView):
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
