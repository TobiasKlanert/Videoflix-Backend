import subprocess
import os

from django.conf import settings

from .models import Video


def convert_hls(source):
    has_audio = _has_audio(source)
    output_dir = _prepare_hls_dirs(source)
    cmd = _build_hls_cmd(source, output_dir, has_audio)
    _run_ffmpeg(cmd)


def extract_thumbnail(video_id, source):
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
    base_dir = os.path.dirname(source)
    base_name = os.path.splitext(os.path.basename(source))[0]
    output_dir = os.path.join(base_dir, f"{base_name}_hls")
    os.makedirs(output_dir, exist_ok=True)
    for variant in ("480p", "720p", "1080p"):
        os.makedirs(os.path.join(output_dir, variant), exist_ok=True)
    return output_dir


def _hls_maps_and_audio(has_audio):
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed with code {result.returncode}: {result.stderr.strip()}"
        )


def _thumbnail_output_path(source):
    base_name = os.path.splitext(os.path.basename(source))[0]
    output_dir = os.path.join(os.fspath(settings.MEDIA_ROOT), "thumbnail")
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{base_name}.jpg")


def _thumbnail_url(output_path):
    relative_path = os.path.relpath(
        output_path, os.fspath(settings.MEDIA_ROOT)
    ).replace("\\", "/")
    media_url = settings.MEDIA_URL.lstrip("/")
    base_url = settings.MEDIA_BASE_URL.rstrip("/")
    return f"{base_url}/{media_url}{relative_path}"
