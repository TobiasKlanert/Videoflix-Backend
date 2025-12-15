import subprocess


def convert_480p(source):
    new_file = source + '_480p.mp4'
    cmd = [
        "ffmpeg",
        "-i",
        source,
        "-s",
        "hd480",
        "-c:v",
        "libx264",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-strict",
        "-2",
        new_file,
    ]
    subprocess.run(cmd, capture_output=True)
