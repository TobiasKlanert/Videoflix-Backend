from django.urls import path
from .views import (
    RegisterView,
    ActivateAccountView,
    CookieTokenObtainPairView,
    LogoutCookieView,
    CookieRefreshView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("activate/<uidb64>/<token>/", ActivateAccountView.as_view(), name="activate"),
    path("login/", CookieTokenObtainPairView.as_view(), name="login"),
    path("logout/", LogoutCookieView.as_view(), name="logout"),
    path("token/refresh/", CookieRefreshView.as_view(), name="refresh"),
    path("password_reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password_confirm/<uidb64>/<token>/", PasswordResetConfirmView.as_view(), name="password-confirm"),
]
