import subprocess


def add_logo_to_video(video_path, logo_path, output_path, position="bottom_right"):

    positions = {
        "top_left": "20:20",
        "top_right": "W-w-20:20",
        "bottom_left": "20:H-h-20",
        "bottom_right": "W-w-20:H-h-20"
    }

    overlay_position = positions.get(
        position,
        "W-w-20:H-h-20"
    )

    command = [
        "ffmpeg",
        "-i", video_path,
        "-i", logo_path,
        "-filter_complex",
        f"[1:v]scale=150:-1[logo];[0:v][logo]overlay={overlay_position}",
        "-c:a",
        "copy",
        "-y",
        output_path
    ]

    subprocess.run(
        command,
        check=True
    )

    return output_path
