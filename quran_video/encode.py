import subprocess

import numpy as np
import imageio_ffmpeg

from .config import WIDTH, HEIGHT, FPS, FFMPEG_PRESET, FFMPEG_CRF


def encode_video(tall_arr, output_path, num_frames, scroll_range, progress=True, quick=False):
    step = scroll_range / max(num_frames, 1)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    preset = "ultrafast" if quick else FFMPEG_PRESET
    crf = 28 if quick else FFMPEG_CRF

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24",
        "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        output_path,
    ]

    offsets = np.clip((np.arange(num_frames) * step).astype(int), 0, scroll_range)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_size = HEIGHT * WIDTH * 3
    buf = bytearray(frame_size)
    report_interval = max(1, FPS * 15)
    for i in range(num_frames):
        y_off = offsets[i]
        buf[:] = tall_arr[y_off:y_off + HEIGHT, :, :].tobytes()
        proc.stdin.write(buf)
        if progress and i % report_interval == 0 and num_frames > 0:
            print(f"  {100 * i // num_frames}%")
    try:
        proc.stdin.close()
    except (ValueError, BrokenPipeError):
        pass
    proc.wait()
    stderr = proc.stderr.read()
    proc.stderr.close()
    if proc.returncode != 0:
        print(f"  ERROR: {stderr.decode()[-500:]}")
        return False
    return True