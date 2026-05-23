#!/usr/bin/env python3
"""Quick test: render 20 verses from Al-Baqarah and make a short video."""

import json
import os
import subprocess
import textwrap
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1920
HEIGHT = 1080
FPS = 24
RATE_2X = 2.0

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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

import imageio_ffmpeg
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def to_arabic_numeral(n):
    return "".join(chr(0x0660 + int(c)) if c.isdigit() else c for c in str(n))


def main():
    data = json.loads(urllib.request.urlopen(
        "https://api.alquran.cloud/v1/surah/2/quran-uthmani").read())
    surah = data["data"]

    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    font_bold = ImageFont.truetype(FONT_BOLD_PATH, FONT_SIZE + 6)

    elements = []
    elements.append(("surah_header", surah["name"], surah["englishName"]))

    display_num = 1
    basmalah = "\u0628\u0650\u0633\u0652\u0645\u0650"
    for v in surah["ayahs"][:20]:
        txt = v["text"].strip("\ufeff")
        if v["numberInSurah"] == 1 and basmalah in txt:
            continue
        elements.append(("verse", txt, display_num))
        display_num += 1

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
            bb = font_bold.getbbox(header)
            tw = bb[2] - bb[0]
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
            text, vnum = elem[1], elem[2]
            wrapped = textwrap.fill(text, width=65)
            lines = wrapped.split("\n")
            for line in lines:
                bb = font.getbbox(line)
                lw = bb[2] - bb[0]
                x = (WIDTH - lw) // 2
                draw.text((x, y), line, fill=TEXT_COLOR, font=font)
                y += FONT_SIZE + LINE_SPACING
            verse_str = f"\u27eb{to_arabic_numeral(vnum)}\u27ea"
            bb = font.getbbox(verse_str)
            vw = bb[2] - bb[0]
            vx = (WIDTH - vw) // 2
            draw.text((vx, y), verse_str, fill=VERSE_NUM_COLOR, font=font)
            y += FONT_SIZE + LINE_SPACING + VERSE_GAP

    tall_arr = np.array(img)

    import io, mutagen
    total_duration = 2.0
    for v in surah["ayahs"][:20]:
        if v["numberInSurah"] == 1:
            total_duration += 3.0 / RATE_2X
            continue
        aurl = f"https://cdn.islamic.network/quran/audio/128/ar.alafasy/{v['number']}.mp3"
        try:
            adur = mutagen.File(io.BytesIO(urllib.request.urlopen(aurl).read())).info.length
        except Exception:
            adur = 5.0
        total_duration += adur / RATE_2X
        print(f"  Ayah {v['numberInSurah']}: {adur:.1f}s -> {adur/RATE_2X:.1f}s at 2x")

    total_height = tall_arr.shape[0]
    num_frames = int(total_duration * FPS)
    scroll_range = total_height - HEIGHT
    step = scroll_range / max(num_frames, 1)

    print(f"\nVideo: {total_height}px, {total_duration:.0f}s ({total_duration/60:.1f}min), {scroll_range/total_duration:.0f}px/s")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "test_20_verses.mp4")

    cmd = [FFMPEG_EXE, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
           "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for i in range(num_frames):
        y_off = min(int(i * step), scroll_range)
        proc.stdin.write(tall_arr[y_off:y_off + HEIGHT, :, :].tobytes())
        if i % (FPS * 15) == 0:
            print(f"  {100*i//num_frames}%")
    proc.stdin.close()
    proc.wait()

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nDone: {output_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()