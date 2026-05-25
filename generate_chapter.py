#!/usr/bin/env python3
"""Generate text-only scrolling video for a specific Quran chapter.
No audio. Uses available fonts (NotoNaskhArabic + Amiri).

Usage:
    python3 generate_chapter.py [chapter_number] [--duration 30m] [--output filename.mp4]
    python3 generate_chapter.py 30 --duration 15m --output chapter30.mp4
"""

import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1920
HEIGHT = 1080
FPS = 24
HEADER_DURATION = 3.0

DEFAULT_JUZ_DURATION = 30 * 60  # 30 minutes in seconds
AVG_AYAHS_PER_JUZ = 6236 / 30   # ~208 ayahs per juz

# Fonts (fallback chain)
FONT_PATHS = {
    "quran": [
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    ],
    "basmalah": [
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    ],
    "surah_ar": [
        "/home/mine/.local/share/fonts/Amiri-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    ],
    "surah_en": [
        "/home/mine/.local/share/fonts/Amiri-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    ],
}

FONT_SIZE_QURAN = 52
FONT_SIZE_BASMALAH = 60
FONT_SIZE_SURAH_AR = 44
FONT_SIZE_SURAH_EN = 26
MARGIN_X = 200
LINE_H = FONT_SIZE_QURAN + 12

BG_COLOR = (12, 8, 20)
TEXT_COLOR = (235, 230, 215)
GOLD = (200, 160, 60)
DARK_GOLD = (100, 75, 25)
VERSE_MARKER_COLOR = (180, 145, 65)
BASMALAH_COLOR = (220, 190, 100)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
QURAN_JSON = os.path.join(SCRIPT_DIR, "quran.json")

import imageio_ffmpeg
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def parse_duration(s):
    """Parse a duration string like '30m', '1h30m', '1800' into seconds."""
    if isinstance(s, (int, float)):
        return float(s)
    s = s.strip().lower()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    total = 0.0
    h_match = re.search(r'(\d+)\s*h', s)
    if h_match:
        total += int(h_match.group(1)) * 3600
    m_match = re.search(r'(\d+)\s*m', s)
    if m_match:
        total += int(m_match.group(1)) * 60
    s_match = re.search(r'(\d+(?:\.\d+)?)\s*s(?:ec)?', s)
    if s_match:
        total += float(s_match.group(1))
    if total > 0:
        return total
    raise ValueError(f"Cannot parse duration: {s}")


def load_font(key, size):
    for path in FONT_PATHS[key]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    raise FileNotFoundError(f"No font found for {key}. Searched: {FONT_PATHS[key]}")


def load_quran():
    with open(QURAN_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


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


def generate_chapter_video(chapter_num, output_filename=None, duration=None):
    quran = load_quran()
    surah = None
    for s in quran:
        if s["id"] == chapter_num:
            surah = s
            break

    if surah is None:
        raise ValueError(f"Chapter {chapter_num} not found in quran.json")

    print(f"Generating video for Surah {surah['id']}: {surah['name']} ({surah['transliteration']})")

    font_quran = load_font("quran", FONT_SIZE_QURAN)
    font_bold = load_font("surah_ar", FONT_SIZE_SURAH_AR)
    font_en = load_font("surah_en", FONT_SIZE_SURAH_EN)
    font_basmalah = load_font("basmalah", FONT_SIZE_BASMALAH)
    fonts = (font_quran, font_bold, font_en, font_basmalah)

    # Build elements
    elements = [
        ("surah_header", surah["name"], surah["transliteration"]),
        ("basmalah",),
    ]

    display_num = 1
    for v in surah["verses"]:
        txt = v["text"].strip("\ufeff")
        if v["id"] == 1 and "\u0628\u0650\u0633\u0652\u0645\u0650" in txt:
            continue  # basmalah shown separately
        elements.append(("verse", txt, display_num))
        display_num += 1

    tall_arr = render_tall_image(elements, fonts)

    verse_count = len([e for e in elements if e[0] == "verse"])
    if duration is None:
        duration = verse_count * (DEFAULT_JUZ_DURATION / AVG_AYAHS_PER_JUZ)

    total_height = tall_arr.shape[0]
    num_frames = int(duration * FPS)
    scroll_range = total_height - HEIGHT
    step = scroll_range / max(num_frames, 1)

    print(f"  Verses: {verse_count}, Duration: {duration:.0f}s ({duration/60:.1f}min), Height: {total_height}px")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not output_filename:
        output_filename = f"surah_{chapter_num:03d}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

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
    print(f"Done: {output_path} ({size_mb:.1f} MB)")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate text-only scrolling video for a Quran chapter")
    parser.add_argument("chapter", type=int, nargs="?", default=30, help="Chapter number (default: 30)")
    parser.add_argument("--duration", "-d", type=str, help="Total video duration (e.g. 30m, 1800). Default: derived from juz proportion.")
    parser.add_argument("--output", "-o", type=str, help="Output filename")
    args = parser.parse_args()

    duration = None
    if args.duration:
        duration = parse_duration(args.duration)

    generate_chapter_video(args.chapter, args.output, duration)
