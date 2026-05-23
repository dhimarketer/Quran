import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import Layout

from .config import (
    WIDTH, HEIGHT, MARGIN_X, MARGIN_X_JUSTIFIED, TEXT_WIDTH_JUSTIFIED,
    BG_COLOR_CENTERED, TEXT_COLOR, VERSE_MARKER_COLOR, LINE_RULE_COLOR, DARK_GOLD,
    FONT_KFGQPC, FONT_AMIRI_QURAN, FONT_AMIRI_BOLD, FONT_AMIRI_REG,
    FONT_SIZE_QURAN, FONT_SIZE_BASMALAH, FONT_SIZE_SURAH_AR, FONT_SIZE_SURAH_EN,
    FONT_SIZE_JUSTIFIED, FONT_SIZE_BASMALAH_JUSTIFIED, FONT_SIZE_SURAH_JUSTIFIED,
    LINE_H_CENTERED, LINE_H_JUSTIFIED,
    TOP_PAD, BOT_PAD, BASMALAH_WORD,
)
from .text import (
    to_arabic_numeral, attach_waqf_marks, strip_bismillah,
    make_verse_marker, center_wrap_text, build_justified_lines,
    build_continuous_lines,
)
from .drawing import (
    draw_ornament_line, draw_surah_header_centered, draw_surah_header_justified,
    draw_basmalah_centered, draw_basmalah_justified, draw_justified_line,
    draw_centered_continuous_line,
)


class LayoutItem:
    __slots__ = ("kind", "data", "y")

    def __init__(self, kind, data, y):
        self.kind = kind
        self.data = data
        self.y = y


def _build_elements_from_surah(surah, ayahs_slice=None):
    elements = []
    elements.append(("surah_header", surah["name"], surah.get("englishName", "")))
    elements.append(("basmalah",))

    first_ayah = surah["ayahs"][0]["text"].strip("\ufeff")
    has_bismillah = first_ayah.split()[0] == BASMALAH_WORD

    ayahs = surah["ayahs"] if ayahs_slice is None else surah["ayahs"][ayahs_slice]
    display_num = 1
    for v in ayahs:
        txt = v["text"].strip("\ufeff")
        if v["numberInSurah"] == 1 and has_bismillah:
            txt = strip_bismillah(txt)
            if not txt:
                continue
        if txt:
            elements.append(("verse", txt, display_num, v["number"]))
            display_num += 1

    return elements


def _build_elements_from_juz(juz_data):
    elements = []
    last_surah = None
    for ayah in juz_data["data"]["ayahs"]:
        surah_id = ayah["surah"]["number"]
        if surah_id != last_surah:
            elements.append(("surah_header", ayah["surah"]["name"], ayah["surah"]["englishName"]))
            elements.append(("basmalah",))
            last_surah = surah_id
        elements.append(("verse", ayah["text"], ayah["numberInSurah"], ayah["number"]))
    return elements


def _layout_centered(elements, fonts):
    font_quran, font_bold, font_en, font_basmalah = fonts
    max_w = WIDTH - 2 * MARGIN_X

    header_items = []
    y = TOP_PAD

    all_words = []

    for elem in elements:
        kind = elem[0]
        if kind == "surah_header":
            header_h = 36 + 28 + FONT_SIZE_SURAH_AR + 12 + FONT_SIZE_SURAH_EN + 16 + 36
            header_items.append(LayoutItem("surah_header", elem[1:], y))
            y += header_h
        elif kind == "basmalah":
            header_items.append(LayoutItem("basmalah", None, y))
            y += FONT_SIZE_BASMALAH + 20 + 36
        elif kind == "verse":
            text, vnum = elem[1], elem[2]
            marker = make_verse_marker(vnum, style="circle")
            words = text.split()
            words.append(marker)
            all_words.extend(words)

    lines = build_continuous_lines(all_words, font_quran, max_w, style="ornate")

    total_height = y + len(lines) * LINE_H_CENTERED + BOT_PAD
    return header_items, lines, total_height, y


def _layout_justified(elements, fonts):
    font_quran, font_ar, font_basm = fonts

    all_words = []
    header_items = []
    y = TOP_PAD

    for elem in elements:
        kind = elem[0]
        if kind == "surah_header":
            header_items.append(LayoutItem("surah_header_j", elem[1:], y))
            y += 2 * 35 + 60 + 40
        elif kind == "basmalah":
            header_items.append(LayoutItem("basmalah_j", None, y))
            y += FONT_SIZE_BASMALAH_JUSTIFIED + 20 + 36
        elif kind == "verse":
            text, vnum = elem[1], elem[2]
            marker = make_verse_marker(vnum, style="circle")
            verse_words = attach_waqf_marks(text.split())
            verse_words.append(marker)
            all_words.extend(verse_words)

    lines = build_justified_lines(all_words, font_quran, TEXT_WIDTH_JUSTIFIED)

    total_height = y + len(lines) * LINE_H_JUSTIFIED + BOT_PAD
    return header_items, lines, total_height, y


def _draw_centered(header_items, lines, total_height, text_start_y, fonts):
    font_quran, font_bold, font_en, font_basmalah = fonts
    max_w = WIDTH - 2 * MARGIN_X

    img = Image.new("RGB", (WIDTH, total_height), BG_COLOR_CENTERED)
    draw = ImageDraw.Draw(img)
    draw_ornament_line(draw, 16, WIDTH, DARK_GOLD, 1, 350)
    draw_ornament_line(draw, total_height - 16, WIDTH, DARK_GOLD, 1, 350)

    for item in header_items:
        if item.kind == "surah_header":
            name_ar, name_en = item.data
            draw_surah_header_centered(draw, item.y, name_ar, name_en or "", font_bold, font_en)
        elif item.kind == "basmalah":
            draw_basmalah_centered(draw, item.y, font_basmalah)

    ascent, descent = font_quran.getmetrics()
    v_offset = (LINE_H_CENTERED - (ascent + descent)) // 2

    y = text_start_y
    for i, line_items in enumerate(lines):
        is_last = (i == len(lines) - 1)
        draw_centered_continuous_line(draw, y + v_offset, line_items, font_quran, max_w, is_last)
        if not is_last:
            rule_y = y + LINE_H_CENTERED
            draw.line([(MARGIN_X, rule_y), (WIDTH - MARGIN_X, rule_y)],
                      fill=LINE_RULE_COLOR, width=2)
        y += LINE_H_CENTERED

    return np.array(img)


def _draw_justified(header_items, lines, total_height, text_start_y, fonts):
    font_quran, font_ar, font_basm = fonts

    img = Image.new("RGB", (WIDTH, total_height), BG_COLOR_CENTERED)
    draw = ImageDraw.Draw(img)
    draw_ornament_line(draw, 16, WIDTH, DARK_GOLD, 1, 350)
    draw_ornament_line(draw, total_height - 16, WIDTH, DARK_GOLD, 1, 350)

    for item in header_items:
        if item.kind == "surah_header_j":
            name_ar = item.data[0]
            draw_surah_header_justified(draw, item.y, name_ar, font_ar)
        elif item.kind == "basmalah_j":
            draw_basmalah_justified(draw, item.y, font_basm)

    ascent, descent = font_quran.getmetrics()
    v_offset = (LINE_H_JUSTIFIED - (ascent + descent)) // 2

    y = text_start_y
    for i, line_items in enumerate(lines):
        is_last = (i == len(lines) - 1)
        draw_justified_line(draw, y + v_offset, line_items, font_quran, TEXT_WIDTH_JUSTIFIED, is_last)
        if not is_last:
            rule_y = y + LINE_H_JUSTIFIED
            draw.line([(MARGIN_X_JUSTIFIED, rule_y), (WIDTH - MARGIN_X_JUSTIFIED, rule_y)],
                      fill=LINE_RULE_COLOR, width=2)
        y += LINE_H_JUSTIFIED

    return np.array(img)


def render(elements, layout="centered", fonts=None):
    if layout == "justified":
        header_items, lines, total_height, text_start_y = _layout_justified(elements, fonts)
        return _draw_justified(header_items, lines, total_height, text_start_y, fonts)
    header_items, lines, total_height, text_start_y = _layout_centered(elements, fonts)
    return _draw_centered(header_items, lines, total_height, text_start_y, fonts)


def load_fonts(layout="centered"):
    if layout == "justified":
        font_quran = ImageFont.truetype(FONT_AMIRI_QURAN, FONT_SIZE_JUSTIFIED, layout_engine=Layout.RAQM)
        font_ar = ImageFont.truetype(FONT_AMIRI_BOLD, FONT_SIZE_SURAH_JUSTIFIED, layout_engine=Layout.RAQM)
        font_basm = ImageFont.truetype(FONT_AMIRI_QURAN, FONT_SIZE_BASMALAH_JUSTIFIED, layout_engine=Layout.RAQM)
        return (font_quran, font_ar, font_basm)
    font_quran = ImageFont.truetype(FONT_KFGQPC, FONT_SIZE_QURAN)
    font_bold = ImageFont.truetype(FONT_AMIRI_BOLD, FONT_SIZE_SURAH_AR)
    font_en = ImageFont.truetype(FONT_AMIRI_REG, FONT_SIZE_SURAH_EN)
    font_basmalah = ImageFont.truetype(FONT_KFGQPC, FONT_SIZE_BASMALAH)
    return (font_quran, font_bold, font_en, font_basmalah)


def build_elements_from_surah(surah, ayahs_slice=None):
    return _build_elements_from_surah(surah, ayahs_slice)


def build_elements_from_juz(juz_data):
    return _build_elements_from_juz(juz_data)