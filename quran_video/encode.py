"""
Streaming video encoder that pipes frames directly to FFmpeg.

Uses page-based rendering: each frame is read from the appropriate
page's numpy array, avoiding the massive "tall image" approach.
Memory is O(1) regardless of content length.

Encoding modes:
- Serial (default): Single ffmpeg with full CPU threading, large pipe
  buffer, stderr progress parsing, hang detection watchdog.
- Parallel: Multiple workers encode frame chunks to temp MP4 segments,
  then concat. Progress via output file size polling.

Key design:
- Custom OS pipe with 1 MiB buffer (F_SETPIPE_SZ) avoids write blocking
- --threads 0 (auto) for full CPU utilisation on any core count
- Stderr reader thread prevents pipe deadlock
- Hang detection: warns at 30s, aborts at 120s of no progress
- Parallel progress: reads temp MP4 file sizes, not shared memory IPC
"""
import fcntl
import multiprocessing
import os
import subprocess
import sys
import tempfile
import threading
import time

import numpy as np
import imageio_ffmpeg

from .config import WIDTH, HEIGHT, FPS, FFMPEG_PRESET, FFMPEG_CRF

_PIPE_BUF_SIZE = 1024 * 1024       # 1 MiB — max allowed on this system
_HANG_WARN_S = 30                  # seconds without progress before warning
_HANG_ERROR_S = 120                # seconds without progress before abort


def _fmt_duration(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    m = int(seconds / 60)
    s = int(seconds % 60)
    return f"{m}m {s}s"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def encode_video(page_arrays, output_path, num_frames, scroll_range,
                 progress=True, workers=None, hang_timeout=_HANG_ERROR_S):
    """Encode pre-rendered pages to an H.264 MP4 video.

    Parameters
    ----------
    page_arrays : list of (scroll_y, np.ndarray)
    output_path : str
    num_frames : int
    scroll_range : int     Total virtual scroll height in pixels.
    progress : bool        Show encoding progress on stdout.
    workers : int | None   Parallel workers. None/0 = serial. N > 1 = parallel.
    hang_timeout : int     Seconds with no encoding progress before abort.
    """
    cpu_count = os.cpu_count() or 4
    if workers is None or workers == 0:
        workers = 1
    workers = max(1, min(workers, cpu_count))

    if workers == 1 or num_frames < workers * 60:
        return _encode_serial(page_arrays, output_path, num_frames,
                              scroll_range, progress, hang_timeout)

    return _encode_parallel(page_arrays, output_path, num_frames,
                            scroll_range, progress, workers,
                            hang_timeout)


# ---------------------------------------------------------------------------
# Serial encoder — single ffmpeg process, large pipe buffer, hang detection
# ---------------------------------------------------------------------------

def _encode_serial(page_arrays, output_path, num_frames, scroll_range,
                   progress, hang_timeout):
    """Encode all frames through a single ffmpeg instance.

    Uses a custom OS pipe with a 1 MiB buffer so that writes rarely block.
    ffmpeg stderr is parsed by a background thread for real encoding progress
    (the ``out_time_ms=`` field).  A watchdog thread detects stalls.
    """
    step = scroll_range / max(num_frames, 1)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    sorted_pages = sorted(page_arrays, key=lambda p: p[0])

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24",
        "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", str(FFMPEG_CRF),
        "-threads", "0",           # auto — use all cores
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-progress", "pipe:2",     # machine-readable progress on stderr
        "-loglevel", "error",      # suppress default human-readable progress
        output_path,
    ]

    # create a pipe with a large kernel buffer
    r_fd, w_fd = os.pipe()
    try:
        fcntl.fcntl(w_fd, fcntl.F_SETPIPE_SZ, _PIPE_BUF_SIZE)
    except OSError:
        pass

    frame_size = HEIGHT * WIDTH * 3

    try:
        proc = subprocess.Popen(
            cmd, stdin=r_fd, stderr=subprocess.PIPE,
            pass_fds=(r_fd,),
        )
    finally:
        os.close(r_fd)

    # stderr reader thread (real encoding progress)
    encoded_ms = [0]
    stderr_done = threading.Event()

    def _read_stderr():
        while True:
            line = proc.stderr.readline()
            if not line:
                break
            try:
                decoded = line.decode("utf-8", errors="ignore").strip()
                if decoded.startswith("out_time_ms="):
                    encoded_ms[0] = int(decoded.split("=")[1]) // 1000
            except Exception:
                break
        stderr_done.set()

    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stderr_thread.start()

    # watchdog thread (hang detection)
    hang_abort = False
    last_progress_ms = [0]
    last_progress_time = [time.time()]

    if hang_timeout > 0:
        def _watchdog():
            while not hang_abort:
                time.sleep(5)
                now = time.time()
                current = encoded_ms[0]
                if current > last_progress_ms[0]:
                    last_progress_ms[0] = current
                    last_progress_time[0] = now
                stalled = now - last_progress_time[0]
                if stalled > _HANG_ERROR_S:
                    print(f"\n  *** HANG DETECTED: no progress for "
                          f"{stalled:.0f}s — aborting ***")
                    proc.kill()
                    break
                elif stalled > _HANG_WARN_S:
                    print(f"\n  WARNING: no encoding progress for "
                          f"{stalled:.0f}s ... ffmpeg may be stalled")

        watchdog_thread = threading.Thread(target=_watchdog, daemon=True)
        watchdog_thread.start()

    # main loop: write each frame
    t_start = time.time()
    total_duration_ms = num_frames * 1000 // FPS
    last_pct = -1
    report_interval = max(1, FPS * 5)

    if progress:
        print(f"  Encoding {num_frames} frames ({num_frames / FPS / 60:.1f} min "
              f"of video, preset={FFMPEG_PRESET}, crf={FFMPEG_CRF}) ...")
        sys.stdout.flush()

    for i in range(num_frames):
        scroll_y = int(i * step)
        scroll_y = min(scroll_y, scroll_range)

        frame_data = _get_frame(sorted_pages, scroll_y)
        if frame_data is not None:
            buf = frame_data.tobytes()
        else:
            buf = b"\x00" * frame_size

        os.write(w_fd, buf)

        if progress and (i % report_interval == 0 or i == num_frames - 1):
            current_ms = encoded_ms[0]
            if current_ms <= 0:
                continue
            pct = min(99, 100 * current_ms // total_duration_ms)
            if pct > last_pct:
                elapsed = time.time() - t_start
                rate = current_ms / elapsed if elapsed > 0 else 0
                remaining = (total_duration_ms - current_ms) / rate if rate > 0 else 0
                fps = current_ms * FPS / 1000 / elapsed if elapsed > 0 else 0
                print(f"  Encoding {pct:>3d}%  "
                      f"Elapsed: {_fmt_duration(elapsed)}  "
                      f"ETA: {_fmt_duration(remaining)}  "
                      f"~{fps:.0f} fps")
                sys.stdout.flush()
                last_pct = pct

    os.close(w_fd)
    proc.wait()
    hang_abort = True

    elapsed = time.time() - t_start
    ok = proc.returncode == 0

    if progress:
        if ok:
            fps = num_frames / elapsed if elapsed > 0 else 0
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"  Encoding 100%  "
                  f"Done: {_fmt_duration(elapsed)}  "
                  f"({fps:.0f} fps, {size_mb:.1f} MB)")
        else:
            print(f"  FFmpeg exited with code {proc.returncode}")

    return ok


# ---------------------------------------------------------------------------
# Parallel encoder — chunked workers + concat
# ---------------------------------------------------------------------------

def _encode_parallel(page_arrays, output_path, num_frames, scroll_range,
                     progress, workers, hang_timeout):
    """Split frames across *workers* processes, concat temp MP4 files.

    Each worker writes frames through its own large-buffer pipe to its own
    ffmpeg process.  Progress is tracked by polling output file sizes on disk
    (no fragile shared-memory IPC).
    """
    step = scroll_range / max(num_frames, 1)

    output_dir = os.path.dirname(os.path.abspath(output_path))
    basename = os.path.basename(output_path)

    chunk_size = (num_frames + workers - 1) // workers
    chunks = []
    for w in range(workers):
        start = w * chunk_size
        end = min(start + chunk_size, num_frames)
        if start < end:
            chunks.append((start, end))
    workers = len(chunks)

    temp_mp4 = [
        os.path.join(output_dir, f".tmp_{w:03d}_{basename}")
        for w in range(workers)
    ]
    chunk_frames = [end - start for start, end in chunks]
    total_duration_ms = num_frames * 1000 // FPS

    if progress:
        print(f"  Encoding {num_frames} frames in {workers} parallel workers "
              f"(~{chunk_size} frames each, preset={FFMPEG_PRESET}) ...")
        sys.stdout.flush()

    t_start = time.time()
    procs = []

    for w in range(workers):
        start_frame, _ = chunks[w]
        p = multiprocessing.Process(
            target=_worker_encode,
            args=(
                page_arrays, temp_mp4[w], chunk_frames[w],
                scroll_range, start_frame, step, workers,
            ),
        )
        p.start()
        procs.append(p)

    # progress: poll MP4 file sizes
    last_pct = -1

    if progress:
        while True:
            active = any(p.is_alive() for p in procs)
            if not active:
                break

            time.sleep(1.0)

            total_bytes = 0
            for mp4_path in temp_mp4:
                try:
                    total_bytes += os.path.getsize(mp4_path)
                except OSError:
                    pass

            encoded = encoded_ms_from_bytes(
                total_bytes, total_duration_ms, 0.4
            )
            if encoded <= 0:
                continue
            pct = min(99, 100 * encoded // total_duration_ms)
            if pct > last_pct:
                elapsed = time.time() - t_start
                rate = encoded / elapsed if elapsed > 0 else 0
                remaining = (total_duration_ms - encoded) / rate if rate > 0 else 0
                line = (f"  Encoding {pct:>3d}%  "
                        f"Elapsed: {_fmt_duration(elapsed)}  "
                        f"ETA: {_fmt_duration(remaining)}")
                print(line)
                sys.stdout.flush()
                last_pct = pct

    for p in procs:
        p.join()

    elapsed = time.time() - t_start

    failed = []
    for w, mp4_path in enumerate(temp_mp4):
        if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 1000:
            failed.append(w)

    if failed:
        print(f"  Worker(s) {failed} failed — aborting")
        _cleanup_temp(temp_mp4)
        return False

    if progress:
        print(f"  Encoding 100%  Done: {_fmt_duration(elapsed)}")
        sys.stdout.flush()

    if progress:
        print("  Concatenating segments ...")
        sys.stdout.flush()

    ok = _concat_parts(temp_mp4, output_path)
    _cleanup_temp(temp_mp4)

    if progress and ok:
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  Total: {_fmt_duration(elapsed)} | {size_mb:.1f} MB")

    return ok


# ---------------------------------------------------------------------------
# Worker function (runs in child process)
# ---------------------------------------------------------------------------

def _worker_encode(page_arrays, output_path, chunk_frames,
                   scroll_range, start_frame, step, total_workers=1):
    """Encode one chunk of frames to a temp MP4 file via ffmpeg pipe."""
    sorted_pages = sorted(page_arrays, key=lambda p: p[0])

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    cpu_count = os.cpu_count() or 4
    worker_threads = max(1, cpu_count // total_workers)

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24",
        "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", str(FFMPEG_CRF),
        "-threads", str(worker_threads),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-loglevel", "error",
        output_path,
    ]

    r_fd, w_fd = os.pipe()
    try:
        fcntl.fcntl(w_fd, fcntl.F_SETPIPE_SZ, _PIPE_BUF_SIZE)
    except OSError:
        pass

    frame_size = HEIGHT * WIDTH * 3

    try:
        proc = subprocess.Popen(
            cmd, stdin=r_fd, stderr=subprocess.DEVNULL,
            pass_fds=(r_fd,),
        )
    finally:
        os.close(r_fd)

    for i in range(chunk_frames):
        global_i = start_frame + i
        scroll_y = int(global_i * step)
        scroll_y = min(scroll_y, scroll_range)

        frame_data = _get_frame(sorted_pages, scroll_y)
        if frame_data is not None:
            buf = frame_data.tobytes()
        else:
            buf = b"\x00" * frame_size

        os.write(w_fd, buf)

    os.close(w_fd)
    proc.wait()

    return proc.returncode == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def encoded_ms_from_bytes(total_bytes, total_duration_ms, min_ratio=0.4):
    """Estimate encoded video milliseconds from MP4 file byte count."""
    if total_bytes <= 0 or total_duration_ms <= 0:
        return 0
    bytes_per_ms = 10 * 1024 / 1000
    ms_by_size = int(total_bytes / bytes_per_ms)
    ms_min = int(total_duration_ms * min_ratio)
    est = max(ms_min, ms_by_size)
    return min(est, total_duration_ms)


def _get_frame(sorted_pages, scroll_y):
    """Extract a 1080px-tall frame at the given virtual scroll position."""
    frame_h = HEIGHT

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

    rel_y = scroll_y - page_start
    remaining = frame_h
    frame = np.zeros((frame_h, WIDTH, 3), dtype=np.uint8)

    src_y = max(0, rel_y)
    copy_h = min(frame_h, page_h - src_y)
    if copy_h > 0:
        frame[0:copy_h] = page_arr[src_y:src_y + copy_h]
    remaining -= copy_h

    if remaining > 0 and best_idx + 1 < len(sorted_pages):
        _, next_arr = sorted_pages[best_idx + 1]
        copy_h2 = min(remaining, next_arr.shape[0])
        if copy_h2 > 0:
            frame[frame_h - remaining:frame_h - remaining + copy_h2] = \
                next_arr[0:copy_h2]

    return frame


def _concat_parts(part_paths, output_path):
    """Concatenate MP4 segments using ffmpeg concat demuxer (no re-encode)."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    concat_list = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, dir=os.path.dirname(output_path)
    )
    try:
        for p in part_paths:
            abs_p = os.path.abspath(p)
            concat_list.write(f"file '{abs_p}'\n")
        concat_list.close()

        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list.name,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
        if proc.returncode != 0:
            err_msg = proc.stderr.decode(errors="replace")
            print(f"  ERROR concatenating: {err_msg[-500:]}")
            return False
        return True
    finally:
        os.unlink(concat_list.name)


def _cleanup_temp(paths):
    """Remove temporary MP4 segment files."""
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def estimate_encode_time(num_frames, workers):
    """Estimate total encoding time in seconds (pre-encode, instant)."""
    cpu_count = os.cpu_count() or 4
    if workers is None or workers == 0:
        workers = 1
    workers = max(1, min(workers, cpu_count))

    base_ms = 6.0
    thread_speedup = min(cpu_count, 8.0) ** 0.6
    ms_per_frame = base_ms / thread_speedup

    if workers > 1:
        ms_per_frame /= min(workers, cpu_count / 2) ** 0.7

    total_s = num_frames * ms_per_frame / 1000

    if workers > 1:
        total_s += 5

    return total_s
