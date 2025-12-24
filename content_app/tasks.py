import subprocess
import os


def convert_480p(source):
    filename, file_extension = os.path.splitext(source)
    new_file = filename + '_480p' + file_extension
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
