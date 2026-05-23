#!/usr/bin/env python3
"""Continuous justified block layout like a real Mushaf.
Verses flow together, waqf marks preserved with proper OpenType shaping,
ayah markers inline with ﴿ ﴾.
"""

import json
import os
import subprocess
import unicodedata
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import Layout

WIDTH = 1920
HEIGHT = 1080
FPS = 24
RATE_2X = 2.0

FONT_PATH = "/home/mine/.local/share/fonts/AmiriQuran.ttf"
FONT_AMIRI_BOLD = "/home/mine/.local/share/fonts/Amiri-Bold.ttf"

FONT_SIZE = 58
FONT_SIZE_BASMALAH = 64
FONT_SIZE_SURAH = 46
LINE_H = 150
MARGIN_X = int(WIDTH * 0.075)
TEXT_WIDTH = WIDTH - 2 * MARGIN_X

BG_COLOR = (12, 8, 20)
TEXT_COLOR = (235, 230, 215)
GOLD = (200, 160, 60)
DARK_GOLD = (100, 75, 25)
BASMALAH_COLOR = (220, 190, 100)
MARKER_COLOR = (180, 145, 65)

BASMALAH_WORD = "\u0628\u0650\u0633\u0652\u0645\u0650"
AYAH_MARKER = "\u06DD"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

import imageio_ffmpeg
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def to_arabic_numeral(n):
    return "".join(chr(0x0660 + int(c)) if c.isdigit() else c for c in str(n))


def attach_waqf_marks(words):
    """Merge standalone combining marks (e.g. waqf symbols) with preceding word.

    U+06D6-U+06ED (waqf marks) are Unicode Mn (Mark Nonspacing) category.
    RAQM positions them above the preceding base character when attached
    without a space, producing correct superscript-waqf rendering.
    """
    result = []
    for w in words:
        if result and all(unicodedata.category(c) == 'Mn' for c in w):
            result[-1] += w
        else:
            result.append(w)
    return result


def strip_bismillah(text):
    words = text.split()
    if words and words[0] == BASMALAH_WORD and len(words) > 4:
        return " ".join(words[4:])
    return text


def measure_word(font, word):
    bbox = font.getbbox(word)
    return bbox[2] - bbox[0]


def draw_ornament_line(draw, y, width, color=GOLD, thickness=1, length=250):
    cx = width // 2
    draw.line([(cx - length, y), (cx - 6, y)], fill=color, width=thickness)
    draw.line([(cx + 6, y), (cx + length, y)], fill=color, width=thickness)
    draw.ellipse([(cx - 5, y - 4), (cx + 5, y + 4)], fill=color)


def draw_surah_header(draw, y, name_ar, font_ar):
    cx = WIDTH // 2
    draw_ornament_line(draw, y, WIDTH, GOLD, 2)

    bbox = font_ar.getbbox(name_ar)
    tw = bbox[2] - bbox[0]
    asc = bbox[1]
    desc = bbox[3]
    text_h = desc - asc

    GAP = 35
    y_text = y + GAP - asc
    y_bottom = y + 2 * GAP + text_h

    draw.text((cx - tw // 2, y_text), name_ar, fill=GOLD, font=font_ar)
    draw_ornament_line(draw, y_bottom, WIDTH, GOLD, 2)
    return y_bottom + 40


def draw_basmalah(draw, y, font_basm):
    text = "\u0628\u0650\u0633\u0652\u0645\u0650 \u0671\u0644\u0644\u0651\u064e\u0647\u0650 \u0671\u0644\u0631\u0651\u064e\u062d\u0652\u0645\u064e\u0670\u0646\u0650 \u0671\u0644\u0631\u0651\u064e\u062d\u0650\u064a\u0645\u0650"
    bbox = font_basm.getbbox(text)
    tw = bbox[2] - bbox[0]
    draw.text(((WIDTH - tw) // 2, y), text, fill=BASMALAH_COLOR, font=font_basm)
    rule_y = y + bbox[3] + 8
    draw.line([(MARGIN_X, rule_y), (WIDTH - MARGIN_X, rule_y)],
               fill=DARK_GOLD, width=1)
    return rule_y + 4


def build_justified_lines(all_words, font, max_width):
    word_data = []
    for w in all_words:
        is_marker = w.startswith(AYAH_MARKER)
        bbox = font.getbbox(w)
        ww = bbox[2] - bbox[0]
        word_data.append((w, ww, is_marker))

    lines = []
    current = []
    current_w = 0

    for w, ww, is_marker in word_data:
        space_w = 0
        if current:
            space_w = measure_word(font, " ")

        if current and current_w + space_w + ww > max_width:
            lines.append(current)
            current = [(w, ww, is_marker)]
            current_w = ww
        else:
            if current:
                current_w += space_w
            current.append((w, ww, is_marker))
            current_w += ww

    if current:
        lines.append(current)

    return lines


def draw_justified_line(draw, y, word_items, font, max_width, is_last):
    if not word_items:
        return

    words = [w for w, _, _ in word_items]
    widths = [ww for _, ww, _ in word_items]

    total_word_w = sum(widths)
    space_w = measure_word(font, " ")

    if is_last or len(words) == 1:
        gap = space_w
    else:
        num_gaps = len(words) - 1
        total_space = max_width - total_word_w
        gap = total_space / num_gaps if num_gaps > 0 else 0

    x = WIDTH - MARGIN_X

    for w, ww, is_marker in word_items:
        x -= ww
        color = MARKER_COLOR if is_marker else TEXT_COLOR
        draw.text((x, y), w, fill=color, font=font)
        x -= gap


def render_tall_image(elements, fonts):
    font_quran, font_ar, font_basm = fonts
    TOP_PAD = 180
    BOT_PAD = HEIGHT

    all_words = []
    for elem in elements:
        if elem[0] == "verse":
            text, vnum = elem[1], elem[2]
            marker = AYAH_MARKER + to_arabic_numeral(vnum)
            verse_words = attach_waqf_marks(text.split())
            verse_words.append(marker)
            all_words.extend(verse_words)

    lines = build_justified_lines(all_words, font_quran, TEXT_WIDTH)

    header_h = 0
    basmalah_h = 0
    for elem in elements:
        if elem[0] == "surah_header":
            header_h += 2 * 35 + 60 + 40
        elif elem[0] == "basmalah":
            basmalah_h += FONT_SIZE_BASMALAH + 115

    total_height = TOP_PAD + header_h + basmalah_h + len(lines) * LINE_H + BOT_PAD

    img = Image.new("RGB", (WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    draw_ornament_line(draw, 16, WIDTH, DARK_GOLD, 1, 350)
    draw_ornament_line(draw, total_height - 16, WIDTH, DARK_GOLD, 1, 350)

    y = TOP_PAD
    for elem in elements:
        if elem[0] == "surah_header":
            y = draw_surah_header(draw, y, elem[1], font_ar)
        elif elem[0] == "basmalah":
            y = draw_basmalah(draw, y, font_basm)

    LINE_RULE_COLOR = (40, 35, 55)

    for i, line_items in enumerate(lines):
        is_last = (i == len(lines) - 1)
        draw_justified_line(draw, y, line_items, font_quran, TEXT_WIDTH, is_last)

        if not is_last:
            line_text = " ".join(w for w, _, _ in line_items)
            tb = font_quran.getbbox(line_text)
            rule_y = y + tb[3] + 5
            draw.line([(MARGIN_X, rule_y), (WIDTH - MARGIN_X, rule_y)],
                       fill=LINE_RULE_COLOR, width=3)

        y += LINE_H

    return np.array(img)


def main():
    surah_num = 2
    data = json.loads(urllib.request.urlopen(
        f"https://api.alquran.cloud/v1/surah/{surah_num}/quran-uthmani").read())
    surah = data["data"]

    font_quran = ImageFont.truetype(FONT_PATH, FONT_SIZE, layout_engine=Layout.RAQM)
    font_ar = ImageFont.truetype(FONT_AMIRI_BOLD, FONT_SIZE_SURAH, layout_engine=Layout.RAQM)
    font_basm = ImageFont.truetype(FONT_PATH, FONT_SIZE_BASMALAH, layout_engine=Layout.RAQM)
    fonts = (font_quran, font_ar, font_basm)

    elements = [("surah_header", surah["name"])]

    first_ayah = surah["ayahs"][0]["text"].strip("\ufeff")
    has_bismillah = first_ayah.split()[0] == BASMALAH_WORD

    if has_bismillah:
        elements.append(("basmalah",))

    display_num = 1
    for v in surah["ayahs"][:30]:
        txt = v["text"].strip("\ufeff")
        if v["numberInSurah"] == 1 and has_bismillah:
            txt = strip_bismillah(txt)
            if not txt:
                continue
        if txt:
            elements.append(("verse", txt, display_num))
            display_num += 1

    tall_arr = render_tall_image(elements, fonts)

    import io, mutagen
    total_duration = 2.0 + 3.0
    for v in surah["ayahs"][:30]:
        if v["numberInSurah"] == 1:
            total_duration += 3.0 / RATE_2X
            continue
        aurl = f"https://cdn.islamic.network/quran/audio/128/ar.alafasy/{v['number']}.mp3"
        adur = mutagen.File(io.BytesIO(urllib.request.urlopen(aurl).read())).info.length
        total_duration += adur / RATE_2X

    total_height = tall_arr.shape[0]
    num_frames = int(total_duration * FPS)
    scroll_range = total_height - HEIGHT
    step = scroll_range / max(num_frames, 1)

    print(f"Video: {total_height}px, {total_duration:.0f}s ({total_duration/60:.1f}min)")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "test_baqarah_continuous.mp4")

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