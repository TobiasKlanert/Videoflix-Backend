import subprocess
import os

from django.conf import settings

from .models import Video


def convert_hls(source):
    """Convert the given source media file into HLS (HTTP Live Streaming) format.

    Checks whether the input has an audio track, prepares the HLS output
    directory structure, builds an ffmpeg command tailored to the input (taking
    audio presence into account), and runs ffmpeg to generate HLS segments and
    playlists.

    Args:
        source (str | pathlib.Path): Path to the input media file to convert.

    Returns:
        None

    Raises:
        subprocess.CalledProcessError: If the ffmpeg process invoked to perform the
            conversion exits with a non-zero status.
        OSError: If preparing output directories or performing file I/O fails.

    Side effects:
        Creates or overwrites files in the HLS output directory.
    """
    has_audio = _has_audio(source)
    output_dir = _prepare_hls_dirs(source)
    cmd = _build_hls_cmd(source, output_dir, has_audio)
    _run_ffmpeg(cmd)


def extract_thumbnail(video_id, source):
    """Extract a thumbnail from a video and persist its URL on the Video model.

    Generates a single JPEG frame from the given source video using ffmpeg,
    stores it under ``MEDIA_ROOT/thumbnail/<basename>.jpg``, builds a public URL
    for the saved file, and updates the corresponding ``Video`` row
    (``thumbnail_url``) in the database.

    The extracted frame is taken at timestamp ``00:00:01`` to avoid producing a
    black frame from the first video frame.

    Args:
        video_id (int): Primary key of the ``Video`` instance to update.
        source (str | pathlib.Path): Path to the input video file.

    Returns:
        None

    Raises:
        RuntimeError: If ffmpeg exits with a non-zero status (raised by
            ``_run_ffmpeg``).
        OSError: If creating the thumbnail output directory or writing the file
            fails.

    Side effects:
        - Creates or overwrites a JPEG file in ``MEDIA_ROOT/thumbnail``.
        - Updates ``Video.thumbnail_url`` in the database for the given
          ``video_id``.
    """
    output_path = _thumbnail_output_path(source)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        "00:00:01",
        "-i",
        source,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        output_path,
    ]
    _run_ffmpeg(cmd)
    Video.objects.filter(pk=video_id).update(
        thumbnail_url=_thumbnail_url(output_path)
    )


def _has_audio(source):
    """Check whether the input media contains at least one audio stream.

    Uses ffprobe to detect audio streams in the given source file.

    Args:
        source (str | pathlib.Path): Path to the input media file.

    Returns:
        bool: True if at least one audio stream is present, otherwise False.

    Raises:
        OSError: If the ffprobe binary cannot be executed (e.g. not installed).
    """
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            source,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0 and bool(probe.stdout.strip())


def _prepare_hls_dirs(source):
    """Create the HLS output directory structure for a given source media file.

    Builds an output directory next to the source file named
    ``<basename>_hls`` and ensures per-variant subdirectories exist for:
    ``480p``, ``720p``, and ``1080p``.

    Args:
        source (str | pathlib.Path): Path to the input media file.

    Returns:
        str: Absolute/normalized path to the created HLS output directory.

    Raises:
        OSError: If directory creation fails.
    """
    base_dir = os.path.dirname(source)
    base_name = os.path.splitext(os.path.basename(source))[0]
    output_dir = os.path.join(base_dir, f"{base_name}_hls")
    os.makedirs(output_dir, exist_ok=True)
    for variant in ("480p", "720p", "1080p"):
        os.makedirs(os.path.join(output_dir, variant), exist_ok=True)
    return output_dir


def _hls_maps_and_audio(has_audio):
    """Return ffmpeg mapping and audio options depending on audio availability.

    If the input has no audio track, only video streams are mapped and no audio
    encoding options are added. If audio exists, each video variant gets an
    associated audio map (optional: ``0:a:0?``) and AAC encoding parameters are
    included.

    Args:
        has_audio (bool): Whether the input media contains an audio stream.

    Returns:
        tuple[list[str], str, list[str]]:
            - maps: CLI tokens for ``-map`` statements.
            - var_stream_map: Value for ``-var_stream_map`` describing variants.
            - audio_opts: Additional CLI tokens for audio codec parameters.
    """
    if not has_audio:
        return (
            [
                "-map",
                "[v480out]",
                "-map",
                "[v720out]",
                "-map",
                "[v1080out]",
            ],
            "v:0,name:480p v:1,name:720p v:2,name:1080p",
            [],
        )
    return (
        [
            "-map",
            "[v480out]",
            "-map",
            "0:a:0?",
            "-map",
            "[v720out]",
            "-map",
            "0:a:0?",
            "-map",
            "[v1080out]",
            "-map",
            "0:a:0?",
        ],
        "v:0,a:0,name:480p v:1,a:1,name:720p v:2,a:2,name:1080p",
        ["-c:a", "aac", "-ar", "48000"],
    )


def _build_hls_cmd(source, output_dir, has_audio):
    """Build the ffmpeg command to generate multi-variant HLS output.

    Produces three scaled video renditions (480p/720p/1080p) via a
    ``filter_complex`` split + scale graph. Audio handling is conditional:
    if audio exists, it is mapped per rendition and encoded to AAC.

    Outputs:
        - ``<output_dir>/master.m3u8`` master playlist
        - ``<output_dir>/<variant>/playlist.m3u8`` variant playlists
        - ``<output_dir>/<variant>/segment_###.ts`` segment files

    Args:
        source (str | pathlib.Path): Path to the input media file.
        output_dir (str | pathlib.Path): Directory where HLS output is written.
        has_audio (bool): Whether the input media contains an audio stream.

    Returns:
        list[str]: The ffmpeg CLI command as a list of tokens.
    """
    maps, var_stream_map, audio_opts = _hls_maps_and_audio(has_audio)
    return [
        "ffmpeg",
        "-i",
        source,
        "-filter_complex",
        "[0:v]split=3[v480][v720][v1080];"
        "[v480]scale=854:480[v480out];"
        "[v720]scale=1280:720[v720out];"
        "[v1080]scale=1920:1080[v1080out]",
        *maps,
        "-c:v",
        "libx264",
        "-crf",
        "23",
        *audio_opts,
        "-f",
        "hls",
        "-hls_time",
        "6",
        "-hls_playlist_type",
        "vod",
        "-hls_segment_filename",
        os.path.join(output_dir, "%v", "segment_%03d.ts"),
        "-master_pl_name",
        "master.m3u8",
        "-var_stream_map",
        var_stream_map,
        os.path.join(output_dir, "%v", "playlist.m3u8"),
    ]


def _run_ffmpeg(cmd):
    """Run an ffmpeg command and raise an error if it fails.

    Executes the provided ffmpeg command (tokenized list), capturing stdout and
    stderr. If ffmpeg returns a non-zero exit code, a ``RuntimeError`` is raised
    including the stderr output.

    Args:
        cmd (list[str]): ffmpeg CLI command as a list of tokens.

    Returns:
        None

    Raises:
        RuntimeError: If ffmpeg exits with a non-zero status.
        OSError: If the ffmpeg binary cannot be executed.
    """
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed with code {result.returncode}: {result.stderr.strip()}"
        )


def _thumbnail_output_path(source):
    """Build the filesystem output path for a video's thumbnail image.

    The output path is ``MEDIA_ROOT/thumbnail/<basename>.jpg`` and the thumbnail
    directory is created if it does not exist.

    Args:
        source (str | pathlib.Path): Path to the input video file used to derive
            the thumbnail file name.

    Returns:
        str: Full filesystem path where the thumbnail JPEG should be written.

    Raises:
        OSError: If creating the thumbnail directory fails.
    """
    base_name = os.path.splitext(os.path.basename(source))[0]
    output_dir = os.path.join(os.fspath(settings.MEDIA_ROOT), "thumbnail")
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{base_name}.jpg")


def _thumbnail_url(output_path):
    """Convert a thumbnail filesystem path into a public URL.

    Computes the path relative to ``MEDIA_ROOT`` and prefixes it with the
    configured ``MEDIA_BASE_URL`` and ``MEDIA_URL`` while normalizing path
    separators for URLs.

    Args:
        output_path (str | pathlib.Path): Absolute filesystem path to the saved
            thumbnail.

    Returns:
        str: Publicly accessible URL pointing to the thumbnail.
    """
    relative_path = os.path.relpath(
        output_path, os.fspath(settings.MEDIA_ROOT)
    ).replace("\\", "/")
    media_url = settings.MEDIA_URL.lstrip("/")
    base_url = settings.MEDIA_BASE_URL.rstrip("/")
    return f"{base_url}/{media_url}{relative_path}"

