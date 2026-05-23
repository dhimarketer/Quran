#!/usr/bin/env python3
"""Generate scrolling HD videos for each Juz of the Quran.

Renders text to a tall image, then scrolls through it with ffmpeg.
Duration per ayah uses actual Al-Afasy recitation timing at 2x speed.
"""

import json
import os
import subprocess
import textwrap
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
QURAN_JSON = os.path.join(SCRIPT_DIR, "quran.json")
TIMINGS_JSON = os.path.join(CACHE_DIR, "ayah_durations.json")

WIDTH = 1920
HEIGHT = 1080
FONT_SIZE = 52
LINE_SPACING = 28
VERSE_GAP = 36
SURAH_GAP = 80
TOP_PADDING = 200
BOTTOM_PADDING = HEIGHT
PADDING_X = 140

BG_COLOR = (6, 6, 18)
TEXT_COLOR = (230, 230, 230)
VERSE_NUM_COLOR = (160, 140, 80)
SURAH_NAME_COLOR = (218, 165, 32)
DECORATION_COLOR = (80, 70, 45)

FONT_PATH = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"

FPS = 24
RATE_2X = 2.0  # scroll at 2x recitation speed

import imageio_ffmpeg
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def load_quran():
    if not os.path.exists(QURAN_JSON):
        url = "https://cdn.jsdelivr.net/npm/quran-cloud@1.0.0/dist/quran.json"
        urllib.request.urlretrieve(url, QURAN_JSON)
    with open(QURAN_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_juz(juz_num):
    cache_path = os.path.join(CACHE_DIR, f"juz_{juz_num}.json")
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    url = f"https://api.alquran.cloud/v1/juz/{juz_num}"
    print(f"  Fetching Juz {juz_num}...")
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def load_timings(quran):
    """Load or download per-ayah recitation durations from Al-Afasy audio."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.exists(TIMINGS_JSON):
        with open(TIMINGS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)

    print("Downloading ayah durations from Al-Afasy recitation...")
    total_ayahs = sum(s["total_verses"] for s in quran)
    print(f"  Total ayahs: {total_ayahs}")

    import io
    import mutagen

    durations = {}
    ayah_num = 1
    for surah in quran:
        for verse_idx in range(surah["total_verses"]):
            url = f"https://cdn.islamic.network/quran/audio/128/ar.alafasy/{ayah_num}.mp3"
            try:
                data = urllib.request.urlopen(url).read()
                audio = mutagen.File(io.BytesIO(data))
                durations[str(ayah_num)] = round(audio.info.length, 3)
            except Exception as e:
                print(f"  Warning: ayah {ayah_num} failed: {e}")
                durations[str(ayah_num)] = 5.0
            if ayah_num % 500 == 0:
                print(f"  Progress: {ayah_num}/{total_ayahs}")
            ayah_num += 1

    with open(TIMINGS_JSON, "w", encoding="utf-8") as f:
        json.dump(durations, f)
    print(f"  Saved durations for {len(durations)} ayahs")
    return durations


def render_tall_image(juz_data, font, font_bold):
    ayahs = juz_data["data"]["ayahs"]
    elements = []
    last_surah = None
    for ayah in ayahs:
        surah_id = ayah["surah"]["number"]
        if surah_id != last_surah:
            elements.append(("surah_header", ayah["surah"]["name"], ayah["surah"]["englishName"]))
            last_surah = surah_id
        elements.append(("verse", ayah["text"], ayah["numberInSurah"], ayah["number"]))

    y = TOP_PADDING
    for elem in elements:
        if elem[0] == "surah_header":
            y += SURAH_GAP + FONT_SIZE + LINE_SPACING + 40
        elif elem[0] == "verse":
            wrapped = textwrap.fill(elem[1], width=65)
            line_count = len(wrapped.split("\n"))
            y += line_count * (FONT_SIZE + LINE_SPACING) + FONT_SIZE + LINE_SPACING + VERSE_GAP
    total_height = y + BOTTOM_PADDING

    img = Image.new("RGB", (WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = TOP_PADDING
    for elem in elements:
        if elem[0] == "surah_header":
            header = f"\u0633\u0648\u0631\u0629 {elem[1]} - {elem[2]}"
            bbox = font_bold.getbbox(header)
            tw = bbox[2] - bbox[0]
            x = (WIDTH - tw) // 2
            draw.line([(x - 80, y + FONT_SIZE // 2), (x - 10, y + FONT_SIZE // 2)],
                       fill=DECORATION_COLOR, width=2)
            draw.line([(x + tw + 10, y + FONT_SIZE // 2), (x + tw + 80, y + FONT_SIZE // 2)],
                       fill=DECORATION_COLOR, width=2)
            draw.text((x, y), header, fill=SURAH_NAME_COLOR, font=font_bold)
            draw.line([(x, y + FONT_SIZE + 12), (x + tw, y + FONT_SIZE + 12)],
                       fill=DECORATION_COLOR, width=1)
            y += SURAH_GAP + FONT_SIZE + LINE_SPACING + 40
        elif elem[0] == "verse":
            text, verse_num = elem[1], elem[2]
            wrapped = textwrap.fill(text, width=65)
            lines = wrapped.split("\n")
            for line in lines:
                bbox = font.getbbox(line)
                lw = bbox[2] - bbox[0]
                x = (WIDTH - lw) // 2
                draw.text((x, y), line, fill=TEXT_COLOR, font=font)
                y += FONT_SIZE + LINE_SPACING
            verse_str = f"\u27eb{verse_num}\u27ea"
            bbox = font.getbbox(verse_str)
            vw = bbox[2] - bbox[0]
            vx = (WIDTH - vw) // 2
            draw.text((vx, y), verse_str, fill=VERSE_NUM_COLOR, font=font)
            y += FONT_SIZE + LINE_SPACING + VERSE_GAP

    return np.array(img), elements


def generate_juz_video(juz_num, quran, font, font_bold, timings):
    juz_data = fetch_juz(juz_num)
    tall_arr, elements = render_tall_image(juz_data, font, font_bold)

    # Calculate total duration from actual recitation times at 2x speed
    total_duration = 0.0
    for elem in elements:
        if elem[0] == "verse":
            ayah_number = elem[3]
            recite_time = timings.get(str(ayah_number), 5.0)
            total_duration += recite_time / RATE_2X
        elif elem[0] == "surah_header":
            total_duration += 2.0  # 2 seconds pause for surah header

    total_height = tall_arr.shape[0]
    num_frames = int(total_duration * FPS)
    scroll_range = total_height - HEIGHT
    step_per_frame = scroll_range / num_frames if num_frames > 0 else 1

    duration_min = total_duration / 60
    print(f"  Juz {juz_num}: {len([e for e in elements if e[0]=='verse'])} ayahs, "
          f"{total_height}px, {total_duration:.0f}s ({duration_min:.1f}min), "
          f"scroll={scroll_range/total_duration:.0f}px/s")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"juz_{juz_num:02d}.mp4")

    cmd = [
        FFMPEG_EXE, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24",
        "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        output_path,
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    for i in range(num_frames):
        y_off = min(int(i * step_per_frame), scroll_range)
        frame = tall_arr[y_off:y_off + HEIGHT, :, :]
        proc.stdin.write(frame.tobytes())
        if i % (FPS * 15) == 0:
            print(f"    {i}/{num_frames} frames ({100*i//num_frames}%)")

    proc.stdin.close()
    _, stderr = proc.communicate()
    if proc.returncode != 0:
        print(f"  ERROR: {stderr.decode()[-500:]}")
        return None

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Done: {output_path} ({size_mb:.1f} MB)")
    return output_path


def main():
    quran = load_quran()
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    font_bold = ImageFont.truetype(FONT_BOLD_PATH, FONT_SIZE + 6)

    timings = load_timings(quran)

    import sys
    juz_list = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [1]

    print(f"Video: {WIDTH}x{HEIGHT}, Speed: {RATE_2X}x recitation speed")
    for juz_num in juz_list:
        print(f"\n=== Juz {juz_num}/30 ===")
        generate_juz_video(juz_num, quran, font, font_bold, timings)
    print("\nDone!")


if __name__ == "__main__":
    main()