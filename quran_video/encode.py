"""
Streaming video encoder that pipes frames directly to FFmpeg.

Uses page-based rendering: each frame is read from the appropriate
page's numpy array, avoiding the massive "tall image" approach.
Memory is O(1) regardless of content length.
"""
import subprocess

import numpy as np
import imageio_ffmpeg

from .config import WIDTH, HEIGHT, FPS, FFMPEG_PRESET, FFMPEG_CRF


def encode_video(page_arrays, output_path, num_frames, scroll_range,
                 progress=True, quick=False):
    """Encode a scrolling video from page arrays.

    Parameters
    ----------
    page_arrays : list of (scroll_y, np.ndarray)
        Each tuple is the page's virtual-scroll Y and its 1920x1080 RGB image.
    output_path : str
        Output MP4 file path.
    num_frames : int
        Total number of frames to produce.
    scroll_range : int
        Total scrollable range in pixels (total_height - HEIGHT).
    progress : bool
        Whether to print progress messages.
    quick : bool
        Use ultrafast preset and higher CRF for fast preview.
    """
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

    # Build frame lookup: (scroll_y_start, page_arr) sorted
    sorted_pages = sorted(page_arrays, key=lambda p: p[0])

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_size = HEIGHT * WIDTH * 3
    buf = bytearray(frame_size)
    report_interval = max(1, FPS * 15)

    for i in range(num_frames):
        scroll_y = int(i * step)
        scroll_y = min(scroll_y, scroll_range)

        # Find the page that contains this scroll_y
        frame_data = _get_frame(sorted_pages, scroll_y)
        if frame_data is not None:
            buf[:] = frame_data.tobytes()
        else:
            # Fallback: black frame
            buf[:] = b'\x00' * frame_size

        proc.stdin.write(buf)

        if progress and i % report_interval == 0 and num_frames > 0:
            pct = 100 * i // num_frames
            print(f"  {pct}%")

    try:
        proc.stdin.close()
    except (ValueError, BrokenPipeError):
        pass
    proc.wait()
    stderr = proc.stderr.read()
    proc.stderr.close()
    if proc.returncode != 0:
        err_msg = stderr.decode(errors="replace")
        print(f"  ERROR: {err_msg[-500:]}")
        return False
    return True


def _get_frame(sorted_pages, scroll_y):
    """Extract a 1080px-tall frame at the given virtual scroll position.

    Finds the page whose scroll_y range covers [scroll_y, scroll_y+HEIGHT).
    If the frame spans two pages, composites them.
    """
    frame_h = HEIGHT
    page_w = WIDTH

    # Binary search for the page that starts at or before scroll_y
    lo, hi = 0, len(sorted_pages) - 1
    best_idx = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        page_start = sorted_pages[mid][0]
        if page_start <= scroll_y:
            best_idx = mid
            lo = mid + 1
        else:
            hi = mid - 1

    if best_idx == -1:
        best_idx = 0

    page_start, page_arr = sorted_pages[best_idx]
    page_h = page_arr.shape[0]
    page_end = page_start + page_h

    rel_y = scroll_y - page_start
    remaining = frame_h
    frame = np.zeros((frame_h, WIDTH, 3), dtype=np.uint8)

    src_y = max(0, rel_y)
    dst_y = 0
    copy_h = min(frame_h, page_h - src_y)
    if copy_h > 0:
        frame[dst_y:dst_y + copy_h] = page_arr[src_y:src_y + copy_h]
    remaining -= copy_h

    # If frame spans into next page, fill the rest
    if remaining > 0 and best_idx + 1 < len(sorted_pages):
        next_page_start, next_arr = sorted_pages[best_idx + 1]
        copy_h2 = min(remaining, next_arr.shape[0])
        if copy_h2 > 0:
            frame[frame_h - remaining:frame_h - remaining + copy_h2] = \
                next_arr[0:copy_h2]

    return frame
