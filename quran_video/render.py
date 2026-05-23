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
    to_arabic_numeral, attach_waqf_marks, strip_bismillah, normalize_arabic,
    make_verse_marker, center_wrap_text, build_justified_lines,
    build_continuous_lines,
)
from .drawing import (
    draw_ornament_line, draw_surah_header_centered, draw_surah_header_justified,
    draw_basmalah_centered, draw_basmalah_justified, draw_justified_line,
    draw_centered_continuous_line,
)


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
        txt = normalize_arabic(txt)
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
        elements.append(("verse", normalize_arabic(ayah["text"]), ayah["numberInSurah"], ayah["number"]))
    return elements


def _layout_centered(elements, fonts):
    font_quran, font_bold, font_en, font_basmalah = fonts
    max_w = WIDTH - 2 * MARGIN_X

    header_h = 36 + 28 + FONT_SIZE_SURAH_AR + 12 + FONT_SIZE_SURAH_EN + 16 + 36
    basmalah_h = FONT_SIZE_BASMALAH + 20 + 36

    surah_blocks = []
    y = TOP_PAD

    current_header_data = None
    current_header_y = 0
    current_basmalah_y = 0
    current_verse_words = []

    for elem in elements:
        kind = elem[0]
        if kind == "surah_header":
            if current_verse_words:
                lines = build_continuous_lines(current_verse_words, font_quran, max_w, style="circle")
                text_start_y = current_basmalah_y + basmalah_h
                surah_blocks.append({
                    "header_data": current_header_data,
                    "header_y": current_header_y,
                    "basmalah_y": current_basmalah_y,
                    "lines": lines,
                    "text_start_y": text_start_y,
                })
                y = text_start_y + len(lines) * LINE_H_CENTERED

            current_header_data = elem[1:]
            current_header_y = y
            y += header_h
            current_basmalah_y = y
            current_verse_words = []
        elif kind == "basmalah":
            y += basmalah_h
        elif kind == "verse":
            text, vnum = elem[1], elem[2]
            marker = make_verse_marker(vnum, style="circle")
            words = attach_waqf_marks(text.split())
            words.append(marker)
            current_verse_words.extend(words)

    if current_verse_words:
        lines = build_continuous_lines(current_verse_words, font_quran, max_w, style="circle")
        text_start_y = current_basmalah_y + basmalah_h
        surah_blocks.append({
            "header_data": current_header_data,
            "header_y": current_header_y,
            "basmalah_y": current_basmalah_y,
            "lines": lines,
            "text_start_y": text_start_y,
        })
        y = text_start_y + len(lines) * LINE_H_CENTERED

    total_height = y + BOT_PAD
    return surah_blocks, total_height


def _layout_justified(elements, fonts):
    font_quran, font_ar, font_basm = fonts

    header_h = 2 * 35 + 60 + 40
    basmalah_h = FONT_SIZE_BASMALAH_JUSTIFIED + 20 + 36

    surah_blocks = []
    y = TOP_PAD

    current_header_data = None
    current_header_y = 0
    current_basmalah_y = 0
    current_verse_words = []

    for elem in elements:
        kind = elem[0]
        if kind == "surah_header":
            if current_verse_words:
                lines = build_justified_lines(current_verse_words, font_quran, TEXT_WIDTH_JUSTIFIED)
                text_start_y = current_basmalah_y + basmalah_h
                surah_blocks.append({
                    "header_data": current_header_data,
                    "header_y": current_header_y,
                    "basmalah_y": current_basmalah_y,
                    "lines": lines,
                    "text_start_y": text_start_y,
                })
                y = text_start_y + len(lines) * LINE_H_JUSTIFIED

            current_header_data = elem[1:]
            current_header_y = y
            y += header_h
            current_basmalah_y = y
            current_verse_words = []
        elif kind == "basmalah":
            y += basmalah_h
        elif kind == "verse":
            text, vnum = elem[1], elem[2]
            marker = make_verse_marker(vnum, style="circle")
            verse_words = attach_waqf_marks(text.split())
            verse_words.append(marker)
            current_verse_words.extend(verse_words)

    if current_verse_words:
        lines = build_justified_lines(current_verse_words, font_quran, TEXT_WIDTH_JUSTIFIED)
        text_start_y = current_basmalah_y + basmalah_h
        surah_blocks.append({
            "header_data": current_header_data,
            "header_y": current_header_y,
            "basmalah_y": current_basmalah_y,
            "lines": lines,
            "text_start_y": text_start_y,
        })
        y = text_start_y + len(lines) * LINE_H_JUSTIFIED

    total_height = y + BOT_PAD
    return surah_blocks, total_height


def _draw_centered(surah_blocks, total_height, fonts):
    font_quran, font_bold, font_en, font_basmalah = fonts
    max_w = WIDTH - 2 * MARGIN_X

    img = Image.new("RGB", (WIDTH, total_height), BG_COLOR_CENTERED)
    draw = ImageDraw.Draw(img)
    draw_ornament_line(draw, 16, WIDTH, DARK_GOLD, 1, 350)
    draw_ornament_line(draw, total_height - 16, WIDTH, DARK_GOLD, 1, 350)

    ascent, descent = font_quran.getmetrics()
    v_offset = (LINE_H_CENTERED - (ascent + descent)) // 2

    for block in surah_blocks:
        name_ar, name_en = block["header_data"]
        draw_surah_header_centered(draw, block["header_y"], name_ar, name_en or "", font_bold, font_en)
        draw_basmalah_centered(draw, block["basmalah_y"], font_basmalah)

        y = block["text_start_y"]
        for i, line_items in enumerate(block["lines"]):
            is_last = (i == len(block["lines"]) - 1)
            draw_centered_continuous_line(draw, y + v_offset, line_items, font_quran, max_w, is_last)
            if not is_last:
                rule_y = y + LINE_H_CENTERED
                draw.line([(MARGIN_X, rule_y), (WIDTH - MARGIN_X, rule_y)],
                          fill=LINE_RULE_COLOR, width=2)
            y += LINE_H_CENTERED

    return np.array(img)


def _draw_justified(surah_blocks, total_height, fonts):
    font_quran, font_ar, font_basm = fonts

    img = Image.new("RGB", (WIDTH, total_height), BG_COLOR_CENTERED)
    draw = ImageDraw.Draw(img)
    draw_ornament_line(draw, 16, WIDTH, DARK_GOLD, 1, 350)
    draw_ornament_line(draw, total_height - 16, WIDTH, DARK_GOLD, 1, 350)

    ascent, descent = font_quran.getmetrics()
    v_offset = (LINE_H_JUSTIFIED - (ascent + descent)) // 2

    for block in surah_blocks:
        name_ar = block["header_data"][0]
        draw_surah_header_justified(draw, block["header_y"], name_ar, font_ar)
        draw_basmalah_justified(draw, block["basmalah_y"], font_basm)

        y = block["text_start_y"]
        for i, line_items in enumerate(block["lines"]):
            is_last = (i == len(block["lines"]) - 1)
            draw_justified_line(draw, y + v_offset, line_items, font_quran, TEXT_WIDTH_JUSTIFIED, is_last)
            if not is_last:
                rule_y = y + LINE_H_JUSTIFIED
                draw.line([(MARGIN_X_JUSTIFIED, rule_y), (WIDTH - MARGIN_X_JUSTIFIED, rule_y)],
                          fill=LINE_RULE_COLOR, width=2)
            y += LINE_H_JUSTIFIED

    return np.array(img)


def render(elements, layout="centered", fonts=None):
    if layout == "justified":
        surah_blocks, total_height = _layout_justified(elements, fonts)
        return _draw_justified(surah_blocks, total_height, fonts)
    surah_blocks, total_height = _layout_centered(elements, fonts)
    return _draw_centered(surah_blocks, total_height, fonts)


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