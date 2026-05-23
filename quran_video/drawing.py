import numpy as np
from PIL import Image, ImageDraw

from .config import (
    WIDTH, HEIGHT, MARGIN_X, MARGIN_X_JUSTIFIED, TEXT_WIDTH_JUSTIFIED,
    BG_COLOR_CENTERED, TEXT_COLOR, GOLD, DARK_GOLD, BASMALAH_COLOR,
    VERSE_MARKER_COLOR, LINE_RULE_COLOR,
    FONT_SIZE_BASMALAH, FONT_SIZE_SURAH_AR, FONT_SIZE_SURAH_EN,
    LINE_H_CENTERED, LINE_H_JUSTIFIED,
)


def draw_ornament_line(draw, y, width, color, thickness=1, length=250):
    cx = width // 2
    draw.line([(cx - length, y), (cx - 6, y)], fill=color, width=thickness)
    draw.line([(cx + 6, y), (cx + length, y)], fill=color, width=thickness)
    draw.ellipse([(cx - 5, y - 4), (cx + 5, y + 4)], fill=color)


def draw_surah_header_centered(draw, y, name_ar, name_en, font_ar, font_en):
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


def draw_surah_header_justified(draw, y, name_ar, font_ar):
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


def draw_basmalah_centered(draw, y, font_basmalah):
    text = "\u0628\u0650\u0633\u0652\u0645\u0650 \u0627\u0644\u0644\u0651\u064e\u0647\u0650 \u0627\u0644\u0631\u0651\u064e\u062d\u0652\u0645\u064e\u0670\u0646\u0650 \u0627\u0644\u0631\u0651\u064e\u062d\u0650\u064a\u0645\u0650"
    bbox = font_basmalah.getbbox(text)
    tw = bbox[2] - bbox[0]
    x = (WIDTH - tw) // 2
    draw.text((x, y), text, fill=BASMALAH_COLOR, font=font_basmalah)
    rule_y = y + bbox[3] + 20
    draw_ornament_line(draw, rule_y, WIDTH, GOLD, 2, 250)
    return rule_y + 36


def draw_basmalah_justified(draw, y, font_basm):
    text = "\u0628\u0650\u0633\u0652\u0645\u0650 \u0627\u0644\u0644\u0651\u064e\u0647\u0650 \u0627\u0644\u0631\u0651\u064e\u062d\u0652\u0645\u064e\u0670\u0646\u0650 \u0627\u0644\u0631\u0651\u064e\u062d\u0650\u064a\u0645\u0650"
    bbox = font_basm.getbbox(text)
    tw = bbox[2] - bbox[0]
    draw.text(((WIDTH - tw) // 2, y), text, fill=BASMALAH_COLOR, font=font_basm)
    rule_y = y + bbox[3] + 20
    draw_ornament_line(draw, rule_y, WIDTH, GOLD, 2, 250)
    return rule_y + 36


def draw_justified_line(draw, y, word_items, font, max_width, is_last):
    if not word_items:
        return
    total_word_w = sum(ww for _, ww, _ in word_items)
    space_w = font.getbbox(" ")[2] - font.getbbox(" ")[0]
    if is_last or len(word_items) == 1:
        gap = space_w
    else:
        num_gaps = len(word_items) - 1
        total_space = max_width - total_word_w
        gap = total_space / num_gaps if num_gaps > 0 else 0
    x = WIDTH - MARGIN_X_JUSTIFIED
    for w, ww, is_marker in word_items:
        x -= ww
        color = VERSE_MARKER_COLOR if is_marker else TEXT_COLOR
        draw.text((x, y), w, fill=color, font=font)
        x -= gap


def draw_centered_continuous_line(draw, y, word_items, font, max_width, is_last):
    if not word_items:
        return
    total_word_w = sum(ww for _, ww, _ in word_items)
    space_w = font.getbbox(" ")[2] - font.getbbox(" ")[0]

    num_gaps = len(word_items) - 1
    if is_last or num_gaps == 0:
        total_w = total_word_w + num_gaps * space_w
        x = (WIDTH + total_w) // 2
        for w, ww, is_marker in word_items:
            x -= ww
            color = VERSE_MARKER_COLOR if is_marker else TEXT_COLOR
            draw.text((x, y), w, fill=color, font=font)
            x -= space_w
    else:
        total_space = max_width - total_word_w
        gap = total_space / num_gaps if num_gaps > 0 else space_w
        x = WIDTH - MARGIN_X
        for w, ww, is_marker in word_items:
            x -= ww
            color = VERSE_MARKER_COLOR if is_marker else TEXT_COLOR
            draw.text((x, y), w, fill=color, font=font)
            x -= gap