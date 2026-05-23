#!/usr/bin/env python3
"""Test video v3: Al-Fatihah with all reviewer fixes applied.
- KFGQPC Uthmanic Script HAFS font (proper Quranic font)
- Centered text alignment
- Arabic-Indic numerals in ornate brackets at end of verse
- Separate decorative Basmalah header (no duplicate)
- Fixed surah header (no double 'سورة')
- Uthmani script text
"""

import json
import os
import subprocess
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1920
HEIGHT = 1080
FPS = 24
RATE_2X = 2.0

FONT_KFGQPC = "/home/mine/.local/share/fonts/KFGQPCUthmanicScriptHAFS.otf"
FONT_AMIRI_BOLD = "/home/mine/.local/share/fonts/Amiri-Bold.ttf"
FONT_AMIRI_REG = "/home/mine/.local/share/fonts/Amiri-Regular.ttf"

FONT_SIZE_QURAN = 52
FONT_SIZE_BASMALAH = 60
FONT_SIZE_SURAH_AR = 44
FONT_SIZE_SURAH_EN = 26
MARGIN_X = 200

BG_COLOR = (12, 8, 20)
TEXT_COLOR = (235, 230, 215)
GOLD = (200, 160, 60)
DARK_GOLD = (100, 75, 25)
VERSE_MARKER_COLOR = (180, 145, 65)
BASMALAH_COLOR = (220, 190, 100)
LINE_H = FONT_SIZE_QURAN + 12

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

import imageio_ffmpeg
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def to_arabic_numeral(n):
    arabic_digits = ""
    for ch in str(n):
        if ch.isdigit():
            arabic_digits += chr(0x0660 + int(ch))
        else:
            arabic_digits += ch
    return arabic_digits


def draw_ornament_line(draw, y, width, color, thickness=1, length=250):
    cx = width // 2
    draw.line([(cx - length, y), (cx - 6, y)], fill=color, width=thickness)
    draw.line([(cx + 6, y), (cx + length, y)], fill=color, width=thickness)
    draw.ellipse([(cx - 5, y - 4), (cx + 5, y + 4)], fill=color)


def draw_surah_header(draw, y, name_ar, name_en, font_ar, font_en):
    cx = WIDTH // 2

    draw_ornament_line(draw, y, WIDTH, GOLD, 2)
    y += 28

    bbox = font_ar.getbbox(name_ar)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, y), name_ar, fill=GOLD, font=font_ar)
    y += FONT_SIZE_SURAH_AR + 12

    bbox = font_en.getbbox(name_en)
    sw = bbox[2] - bbox[0]
    draw.text((cx - sw // 2, y), name_en, fill=DARK_GOLD, font=font_en)
    y += FONT_SIZE_SURAH_EN + 16

    draw_ornament_line(draw, y, WIDTH, GOLD, 2)
    return y + 36


def draw_basmalah(draw, y, font_basmalah):
    text = "\u0628\u0650\u0633\u0652\u0645\u0650 \u0627\u0644\u0644\u0651\u064e\u0647\u0650 \u0627\u0644\u0631\u0651\u064e\u062d\u0652\u0645\u064e\u0670\u0646\u0650 \u0627\u0644\u0631\u0651\u064e\u062d\u0650\u064a\u0645\u0650"
    bbox = font_basmalah.getbbox(text)
    tw = bbox[2] - bbox[0]
    cx = WIDTH // 2
    x = cx - tw // 2
    draw.text((x, y), text, fill=BASMALAH_COLOR, font=font_basmalah)
    return y + FONT_SIZE_BASMALAH + 60


def center_wrap_text(text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = current + (" " if current else "") + word
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def render_tall_image(elements, fonts):
    font_quran, font_bold, font_en, font_basmalah = fonts
    max_w = WIDTH - 2 * MARGIN_X
    TOP_PAD = 180
    BOT_PAD = HEIGHT
    VERSE_GAP = 28

    y = TOP_PAD
    for elem in elements:
        if elem[0] == "surah_header":
            y += 36 + 28 + FONT_SIZE_SURAH_AR + 12 + FONT_SIZE_SURAH_EN + 16 + 36
        elif elem[0] == "basmalah":
            y += FONT_SIZE_BASMALAH + 60
        elif elem[0] == "verse":
            text, vnum = elem[1], elem[2]
            marker = f" \uFD3F{to_arabic_numeral(vnum)}\uFD3E"
            lines = center_wrap_text(text + marker, font_quran, max_w)
            y += len(lines) * LINE_H + VERSE_GAP

    total_height = y + BOT_PAD

    img = Image.new("RGB", (WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # subtle top/bottom border lines for the viewport
    draw_ornament_line(draw, 16, WIDTH, DARK_GOLD, 1, 350)
    draw_ornament_line(draw, HEIGHT - 16, WIDTH, DARK_GOLD, 1, 350)

    y = TOP_PAD
    for elem in elements:
        if elem[0] == "surah_header":
            y = draw_surah_header(draw, y, elem[1], elem[2], font_bold, font_en)
        elif elem[0] == "basmalah":
            y = draw_basmalah(draw, y, font_basmalah)
        elif elem[0] == "verse":
            text, vnum = elem[1], elem[2]
            marker = f" \uFD3F{to_arabic_numeral(vnum)}\uFD3E"
            lines = center_wrap_text(text + marker, font_quran, max_w)
            for line in lines:
                bbox = font_quran.getbbox(line)
                lw = bbox[2] - bbox[0]
                x = (WIDTH - lw) // 2
                draw.text((x, y), line, fill=TEXT_COLOR, font=font_quran)
                y += LINE_H
            y += VERSE_GAP

    return np.array(img)


def main():
    data = json.loads(urllib.request.urlopen(
        "https://api.alquran.cloud/v1/surah/1/quran-uthmani").read())
    surah = data["data"]

    font_quran = ImageFont.truetype(FONT_KFGQPC, FONT_SIZE_QURAN)
    font_bold = ImageFont.truetype(FONT_AMIRI_BOLD, FONT_SIZE_SURAH_AR)
    font_en = ImageFont.truetype(FONT_AMIRI_REG, FONT_SIZE_SURAH_EN)
    font_basmalah = ImageFont.truetype(FONT_KFGQPC, FONT_SIZE_BASMALAH)
    fonts = (font_quran, font_bold, font_en, font_basmalah)

    # Build elements - Basmalah as decorative header (not numbered), verses renumbered from 1
    elements = [
        ("surah_header", surah["name"], surah["englishName"]),
        ("basmalah",),
    ]
    display_num = 1
    for v in surah["ayahs"]:
        txt = v["text"].strip("\ufeff")
        if v["numberInSurah"] == 1 and "\u0628\u0650\u0633\u0652\u0645\u0650" in txt:
            continue  # basmalah shown in decorative box, skip from verse list
        elements.append(("verse", txt, display_num))
        display_num += 1

    tall_arr = render_tall_image(elements, fonts)

    import io, mutagen
    total_duration = 2.0 + 3.0  # header + basmalah pause
    for v in surah["ayahs"]:
        if v["numberInSurah"] == 1:
            total_duration += 3.0 / RATE_2X  # basmalah already shown
        else:
            aurl = f"https://cdn.islamic.network/quran/audio/128/ar.alafasy/{v['number']}.mp3"
            adur = mutagen.File(io.BytesIO(urllib.request.urlopen(aurl).read())).info.length
            total_duration += adur / RATE_2X
            print(f"  Ayah {v['numberInSurah']}: {adur:.1f}s -> {adur/RATE_2X:.1f}s at 2x")

    total_height = tall_arr.shape[0]
    num_frames = int(total_duration * FPS)
    scroll_range = total_height - HEIGHT
    step = scroll_range / max(num_frames, 1)

    print(f"\nVideo: {total_height}px, {total_duration:.1f}s, {scroll_range/total_duration:.0f}px/s")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "test_fatihah_v3.mp4")

    cmd = [FFMPEG_EXE, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
           "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for i in range(num_frames):
        y_off = min(int(i * step), scroll_range)
        proc.stdin.write(tall_arr[y_off:y_off + HEIGHT, :, :].tobytes())
    proc.stdin.close()
    proc.wait()

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nDone: {output_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()