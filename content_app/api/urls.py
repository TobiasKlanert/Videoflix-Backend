from django.urls import path
from .views import VideoListAPIView

urlpatterns = [
    path("video/", VideoListAPIView.as_view(), name="video")
]