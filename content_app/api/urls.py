from django.urls import path

from .views import VideoHlsManifestAPIView, VideoHlsSegmentAPIView, VideoListAPIView

urlpatterns = [
    path("video/", VideoListAPIView.as_view(), name="video"),
    path(
        "video/<int:movie_id>/<str:resolution>/index.m3u8",
        VideoHlsManifestAPIView.as_view(),
        name="video-hls-manifest",
    ),
    path(
        "video/<int:movie_id>/<str:resolution>/<str:segment>/",
        VideoHlsSegmentAPIView.as_view(),
        name="video-hls-segment",
    ),
]
