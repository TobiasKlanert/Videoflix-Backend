import os

from django.http import FileResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from content_app.models import Video
from .serializers import VideoSerializer


def _not_found_response(message):
    return Response({"detail": message}, status=status.HTTP_404_NOT_FOUND)


def _bad_request_response(message):
    return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)


def _get_video_or_response(movie_id):
    video = Video.objects.filter(pk=movie_id).first()
    if video is None:
        return None, _not_found_response("Video not found.")
    return video, None


def _hls_dir_for_video(video):
    base_dir = os.path.dirname(video.video_file.path)
    base_name = os.path.splitext(os.path.basename(video.video_file.path))[0]
    return os.path.join(base_dir, f"{base_name}_hls")


def _manifest_path(hls_dir, resolution):
    if resolution == "master":
        return os.path.join(hls_dir, "master.m3u8")
    return os.path.join(hls_dir, resolution, "playlist.m3u8")


def _segment_path(hls_dir, resolution, segment):
    return os.path.join(hls_dir, resolution, segment)


def _segment_is_valid(segment):
    return os.path.basename(segment) == segment and segment.endswith(".ts")


def _file_response_or_missing(path, content_type, missing_message):
    if not os.path.isfile(path):
        return _not_found_response(missing_message)
    return FileResponse(open(path, "rb"), content_type=content_type)


class VideoListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        videos = Video.objects.all().order_by('-created_at')
        serializer = VideoSerializer(videos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class VideoHlsManifestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, movie_id, resolution, *args, **kwargs):
        video, error = _get_video_or_response(movie_id)
        if error:
            return error
        hls_dir = _hls_dir_for_video(video)
        manifest_path = _manifest_path(hls_dir, resolution)
        return _file_response_or_missing(
            manifest_path,
            "application/vnd.apple.mpegurl",
            "HLS manifest not found.",
        )


class VideoHlsSegmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, movie_id, resolution, segment, *args, **kwargs):
        if not _segment_is_valid(segment):
            return _bad_request_response("Invalid segment name.")
        video, error = _get_video_or_response(movie_id)
        if error:
            return error
        hls_dir = _hls_dir_for_video(video)
        segment_path = _segment_path(hls_dir, resolution, segment)
        return _file_response_or_missing(
            segment_path,
            "video/MP2T",
            "HLS segment not found.",
        )
