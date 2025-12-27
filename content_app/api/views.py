import os

from django.http import FileResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from content_app.models import Video
from .serializers import VideoSerializer


def _not_found_response(message):
    """Create a standardized 404 JSON response.

    Wraps the given message in the common DRF error format:
    ``{"detail": "<message>"}`` and returns it with HTTP 404.

    Args:
        message (str): Human-readable error message.

    Returns:
        rest_framework.response.Response: DRF Response with status 404.
    """
    return Response({"detail": message}, status=status.HTTP_404_NOT_FOUND)


def _bad_request_response(message):
    """Create a standardized 400 JSON response.

    Wraps the given message in the common DRF error format:
    ``{"detail": "<message>"}`` and returns it with HTTP 400.

    Args:
        message (str): Human-readable error message.

    Returns:
        rest_framework.response.Response: DRF Response with status 400.
    """
    return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)


def _get_video_or_response(movie_id):
    """Fetch a Video instance by primary key or return a 404 response.

    Performs a lookup for the given ``movie_id``. If no video exists, a DRF
    ``Response`` with status 404 is prepared.

    Args:
        movie_id (int): Primary key of the ``Video`` record.

    Returns:
        tuple[Video | None, rest_framework.response.Response | None]:
            - (video, None) when found
            - (None, 404 Response) when missing
    """
    video = Video.objects.filter(pk=movie_id).first()
    if video is None:
        return None, _not_found_response("Video not found.")
    return video, None


def _hls_dir_for_video(video):
    """Compute the HLS output directory for a given Video instance.

    Assumes HLS output is stored next to the uploaded video file using the
    naming convention ``<basename>_hls`` (e.g. ``movie.mp4`` -> ``movie_hls``).

    Args:
        video (Video): Video instance with ``video_file.path``.

    Returns:
        str: Absolute path to the HLS directory for this video.
    """
    base_dir = os.path.dirname(video.video_file.path)
    base_name = os.path.splitext(os.path.basename(video.video_file.path))[0]
    return os.path.join(base_dir, f"{base_name}_hls")


def _manifest_path(hls_dir, resolution):
    """Build the filesystem path to an HLS manifest.

    Supports:
        - ``resolution == "master"`` -> ``<hls_dir>/master.m3u8``
        - otherwise -> ``<hls_dir>/<resolution>/playlist.m3u8``

    Args:
        hls_dir (str | pathlib.Path): Base HLS directory.
        resolution (str): Either "master" or a variant folder name (e.g. "480p").

    Returns:
        str: Filesystem path to the requested manifest.
    """
    if resolution == "master":
        return os.path.join(hls_dir, "master.m3u8")
    return os.path.join(hls_dir, resolution, "playlist.m3u8")


def _segment_path(hls_dir, resolution, segment):
    """Build the filesystem path to a single HLS segment file.

    Args:
        hls_dir (str | pathlib.Path): Base HLS directory.
        resolution (str): Variant folder name (e.g. "480p", "720p", "1080p").
        segment (str): Segment file name (e.g. "segment_001.ts").

    Returns:
        str: Filesystem path to the segment file.
    """
    return os.path.join(hls_dir, resolution, segment)


def _segment_is_valid(segment):
    """Validate an HLS segment file name to reduce path traversal risk.

    Accepts only:
        - a plain file name (no directories)
        - ending with ``.ts``

    Examples:
        - "segment_001.ts" -> True
        - "../secret.txt" -> False
        - "sub/segment_001.ts" -> False
        - "segment_001.m4s" -> False

    Args:
        segment (str): Segment name provided by the client.

    Returns:
        bool: True if the segment name is considered safe/valid, else False.
    """
    return os.path.basename(segment) == segment and segment.endswith(".ts")


def _file_response_or_missing(path, content_type, missing_message):
    """Return a FileResponse if a file exists, otherwise a 404 response.

    Checks the filesystem for ``path``. When present, opens the file in binary
    mode and streams it via Django's ``FileResponse`` with the given content
    type.

    Args:
        path (str | pathlib.Path): Filesystem path to the file to serve.
        content_type (str): MIME type for the response.
        missing_message (str): Error message used if the file does not exist.

    Returns:
        django.http.FileResponse | rest_framework.response.Response:
            - FileResponse when the file exists
            - 404 DRF Response when missing

    Raises:
        OSError: If the file exists but cannot be opened (permissions, I/O error).
    """
    if not os.path.isfile(path):
        return _not_found_response(missing_message)
    return FileResponse(open(path, "rb"), content_type=content_type)


class VideoListAPIView(APIView):
    """List all videos for authenticated users.

    GET:
        Returns all ``Video`` objects ordered by ``created_at`` descending.

    Permissions:
        - Requires authentication (``IsAuthenticated``).

    Response:
        200: List of serialized videos.

    Notes:
        This endpoint currently returns *all* videos in the database. If you need
        per-user scoping, implement filtering in the queryset.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Return a list of videos ordered by newest first."""
        videos = Video.objects.all().order_by("-created_at")
        serializer = VideoSerializer(videos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class VideoHlsManifestAPIView(APIView):
    """Serve HLS manifest files (master or variant playlist) for a video.

    GET:
        Serves either the master playlist (``master.m3u8``) or a variant
        playlist (``<resolution>/playlist.m3u8``) from the video's HLS directory.

    URL params:
        movie_id (int): Video primary key.
        resolution (str): "master" or a variant folder name (e.g. "480p", "720p").

    Permissions:
        - Requires authentication (``IsAuthenticated``).

    Responses:
        200: HLS manifest as a streamed file response.
        404: Video not found, or manifest file missing.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, movie_id, resolution, *args, **kwargs):
        """Stream the requested manifest file if available."""
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
    """Serve individual HLS transport stream segments for a video.

    GET:
        Streams a ``.ts`` segment file from the video's HLS directory.

    URL params:
        movie_id (int): Video primary key.
        resolution (str): Variant folder name (e.g. "480p", "720p", "1080p").
        segment (str): Segment file name (must be a base name ending with .ts).

    Permissions:
        - Requires authentication (``IsAuthenticated``).

    Validation:
        Rejects invalid segment names to prevent path traversal (400).

    Responses:
        200: HLS segment as a streamed file response.
        400: Invalid segment name.
        404: Video not found, or segment file missing.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, movie_id, resolution, segment, *args, **kwargs):
        """Stream the requested segment file if available and valid."""
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
