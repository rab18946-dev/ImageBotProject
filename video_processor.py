import os
import subprocess


def add_logo_to_video(video_path, logo_path, output_path):
    """
    מוסיף לוגו לסרטון בפינה הימנית התחתונה
    """

    command = [
        "ffmpeg",
        "-i", video_path,
        "-i", logo_path,
        "-filter_complex",
        "[1:v]scale=150:-1[logo];[0:v][logo]overlay=W-w-20:H-h-20",
        "-codec:a",
        "copy",
        output_path,
        "-y"
    ]

    subprocess.run(
        command,
        check=True
    )

    return output_path
