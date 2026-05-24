"""
Cairo-based drawing primitives for Quran video pages.

Replaces the PIL ImageDraw module with Cairo vector graphics.
Headers, basmalahs, ornament lines, and text all use Cairo/PangoCairo.
"""
import math

import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo
import cairo

from .config import (
    WIDTH, HEIGHT, MARGIN_X, MARGIN_X_JUSTIFIED, TEXT_WIDTH_JUSTIFIED,
    BG_COLOR_CENTERED, TEXT_COLOR, GOLD, DARK_GOLD, BASMALAH_COLOR,
    VERSE_MARKER_COLOR, WAQF_MARKER_COLOR, WAQF_FONT_SIZE, LINE_RULE_COLOR,
    LINE_H_CENTERED, LINE_H_JUSTIFIED,
    FONT_SIZE_QURAN, FONT_SIZE_JUSTIFIED,
    FONT_SIZE_SURAH_AR, FONT_SIZE_SURAH_EN, FONT_SIZE_SURAH_JUSTIFIED,
    FONT_SIZE_BASMALAH, FONT_SIZE_BASMALAH_JUSTIFIED,
)

BASMALAH_TEXT = (
    "\u0628\u0650\u0633\u0652\u0645\u0650 "
    "\u0627\u0644\u0644\u0651\u064e\u0647\u0650 "
    "\u0627\u0644\u0631\u0651\u064e\u062d\u0652\u0645\u064e\u0670\u0646\u0650 "
    "\u0627\u0644\u0631\u0651\u064e\u062d\u0650\u064a\u0645\u0650"
)

_AMIRI_QURAN_FAMILY = "Amiri Quran"
_AMIRI_BOLD_FAMILY = "Amiri"


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _cairo_rgb(rgb):
    """8-bit (0-255) → 0.0-1.0 float."""
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def _set_cairo_color(cr, rgb):
    cr.set_source_rgb(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _make_pango_layout(cr, text, family, size, width_px=None, justify=False,
                       alignment=Pango.Alignment.LEFT):
    """Create a PangoLayout with sensible defaults for Arabic text."""
    pctx = PangoCairo.create_context(cr)
    fd = Pango.FontDescription.from_string(f"{family} {size}")
    layout = Pango.Layout.new(pctx)
    layout.set_font_description(fd)
    layout.set_text(text)
    layout.set_auto_dir(True)
    if width_px is not None:
        layout.set_width(Pango.units_from_double(width_px))
    if justify:
        layout.set_justify(True)
    layout.set_alignment(alignment)
    return layout


def _pango_text_extents(layout):
    """Return (width_px, height_px, ink_y, log_y) of a PangoLayout.

    ink_y and log_y are the ink/logical offsets from the layout origin.
    These are needed to correctly position text vertically.
    """
    ink, logical = layout.get_pixel_extents()
    return logical.width, logical.height, ink.y, logical.y


def _show_layout_at(cr, layout, x, y, v_center_height=None):
    """Render a PangoLayout at (x, y) in the Cairo context.

    (x, y) is the desired position for the ink (visible text) top.
    PangoCairo.show_layout places the layout origin at (x, render_y),
    so we adjust by -ink.y to align ink top at y.

    If v_center_height is given, the ink is centred vertically within
    that many pixels (useful for headers/basmalahs).
    """
    ink, logical = layout.get_pixel_extents()
    if v_center_height is not None:
        v_offset = (v_center_height - ink.height) // 2
    else:
        v_offset = 0
    render_y = y - ink.y + v_offset
    cr.save()
    cr.move_to(x, render_y)
    PangoCairo.show_layout(cr, layout)
    cr.restore()


OT_FEATURES_STR = "mark 1, mkmk 1, ccmp 1"


def _add_ot_features(attr_list, byte_len):
    ot = Pango.AttrFontFeatures.new(OT_FEATURES_STR)
    ot.start_index = 0
    ot.end_index = byte_len
    attr_list.insert(ot)


# ---------------------------------------------------------------------------
# Ornaments
# ---------------------------------------------------------------------------

def draw_ornament_line(cr, y, width, color, thickness=1, length=250):
    """Horizontal ornament: left dash, centre diamond, right dash."""
    cr.set_line_width(thickness)
    _set_cairo_color(cr, color)
    cx = width // 2

    # Left dash
    cr.move_to(cx - length, y)
    cr.line_to(cx - 6, y)
    cr.stroke()

    # Right dash
    cr.move_to(cx + 6, y)
    cr.line_to(cx + length, y)
    cr.stroke()

    # Centre diamond
    cr.move_to(cx, y - 4)
    cr.line_to(cx + 4, y)
    cr.line_to(cx, y + 4)
    cr.line_to(cx - 4, y)
    cr.close_path()
    cr.fill()


# ---------------------------------------------------------------------------
# Surah headers
# ---------------------------------------------------------------------------

def draw_surah_header_centered(cr, y, name_ar, name_en,
                               fd_ar: Pango.FontDescription,
                               fd_en: Pango.FontDescription):
    """Centred surah header with Arabic + English names and ornament lines."""
    draw_ornament_line(cr, y, WIDTH, GOLD, 2)

    y += 28
    layout_ar = _make_pango_layout(cr, name_ar, _AMIRI_BOLD_FAMILY, FONT_SIZE_SURAH_AR)
    ar_w, _, _, _ = _pango_text_extents(layout_ar)
    _set_cairo_color(cr, GOLD)
    _show_layout_at(cr, layout_ar, (WIDTH - ar_w) / 2, y)

    y += FONT_SIZE_SURAH_AR + 12
    if name_en:
        layout_en = _make_pango_layout(cr, name_en, _AMIRI_BOLD_FAMILY, FONT_SIZE_SURAH_EN)
        en_w, _, _, _ = _pango_text_extents(layout_en)
        _set_cairo_color(cr, DARK_GOLD)
        _show_layout_at(cr, layout_en, (WIDTH - en_w) / 2, y)

    y += FONT_SIZE_SURAH_EN + 16
    draw_ornament_line(cr, y, WIDTH, GOLD, 2)


def draw_surah_header_justified(cr, y, name_ar,
                                fd_ar: Pango.FontDescription):
    """Justified-layout surah header — Arabic only."""
    GAP = 35
    draw_ornament_line(cr, y, WIDTH, GOLD, 2)

    layout_ar = _make_pango_layout(cr, name_ar, _AMIRI_BOLD_FAMILY, FONT_SIZE_SURAH_JUSTIFIED)
    ar_w, _, _, _ = _pango_text_extents(layout_ar)

    _set_cairo_color(cr, GOLD)
    _show_layout_at(cr, layout_ar, (WIDTH - ar_w) / 2, y + GAP)

    y_bottom = y + 2 * GAP
    draw_ornament_line(cr, y_bottom, WIDTH, GOLD, 2)


# ---------------------------------------------------------------------------
# Basmalah
# ---------------------------------------------------------------------------

def draw_basmalah(cr, y, layout, basmalah_font_desc):
    """Render the Basmalah centred with an ornament line below."""
    from .config import FONT_SIZE_BASMALAH_JUSTIFIED
    basm_h = FONT_SIZE_BASMALAH if layout == "centered" else FONT_SIZE_BASMALAH_JUSTIFIED

    p_layout = _make_pango_layout(cr, BASMALAH_TEXT, _AMIRI_QURAN_FAMILY, 0)
    p_layout.set_font_description(basmalah_font_desc)
    bw, bh, ink_y, log_y = _pango_text_extents(p_layout)

    cr.save()
    _set_cairo_color(cr, BASMALAH_COLOR)
    _show_layout_at(cr, p_layout, (WIDTH - bw) / 2, y, v_center_height=basm_h)
    cr.restore()

    # Ornament line below the basmalah text
    ink, logical = p_layout.get_pixel_extents()
    rule_y = y + basm_h + 20
    draw_ornament_line(cr, rule_y, WIDTH, GOLD, 2, 250)


# ---------------------------------------------------------------------------
# Juz footer
# ---------------------------------------------------------------------------

def draw_juz_footer(cr, y, juz_num, last_ayah_in_surah,
                    surah_name, surah_num, fd_footer):
    """Render the juz info footer with ornament lines."""
    FOOTER_LINE_LEN = 180
    GAP = 18

    footer_text = (
        f"Juz {juz_num}  \u2014  Verse {last_ayah_in_surah}  "
        f"\u2014  {surah_name} ({surah_num})"
    )

    p_layout = _make_pango_layout(cr, footer_text, _AMIRI_BOLD_FAMILY, 0)
    p_layout.set_font_description(fd_footer)
    fw, fh, _, _ = _pango_text_extents(p_layout)

    draw_ornament_line(cr, y, WIDTH, GOLD, 2, FOOTER_LINE_LEN)

    _set_cairo_color(cr, GOLD)
    _show_layout_at(cr, p_layout, (WIDTH - fw) / 2, y + GAP)

    bottom_ornament = y + GAP + fh + GAP
    draw_ornament_line(cr, bottom_ornament, WIDTH, GOLD, 2, FOOTER_LINE_LEN)


# ---------------------------------------------------------------------------
# Text lines with PangoCairo + Kashida justification
# ---------------------------------------------------------------------------

def _build_line_text_for_pango(words: list) -> str:
    """Join word texts with spaces for Pango rendering (includes waqf marks)."""
    return " ".join(w.text for w in words)


def _build_line_text_clean(words: list) -> str:
    """Join word texts without waqf marks for clean rendering."""
    return " ".join(w.text_clean for w in words if w.text_clean)


def _build_line_attrs(words: list) -> Pango.AttrList:
    """Build Pango attributes to colour verse markers differently.

    Uses w.text (with waqf marks) for byte offsets — matches
    the full marked-text Pango layout used by draw_waqf_overlays.
    """
    attr_list = Pango.AttrList()
    vr, vg, vb = (c * 257 for c in VERSE_MARKER_COLOR)
    byte_pos = 0

    for w in words:
        w_bytes = len(w.text.encode("utf-8"))
        if w.is_marker:
            attr = Pango.attr_foreground_new(vr, vg, vb)
            attr.start_index = byte_pos
            attr.end_index = byte_pos + w_bytes
            attr_list.insert(attr)
        byte_pos += w_bytes + 1  # +1 for space between words

    return attr_list


def _build_line_attrs_clean(words: list) -> Pango.AttrList:
    """Build Pango attributes for the clean-text layout (draw_text_line).

    Uses w.text_clean (without waqf marks) for byte offsets.
    """
    attr_list = Pango.AttrList()
    vr, vg, vb = (c * 257 for c in VERSE_MARKER_COLOR)
    byte_pos = 0

    for w in words:
        if not w.text_clean:
            continue
        w_bytes = len(w.text_clean.encode("utf-8"))
        if w.is_marker:
            attr = Pango.attr_foreground_new(vr, vg, vb)
            attr.start_index = byte_pos
            attr.end_index = byte_pos + w_bytes
            attr_list.insert(attr)
        byte_pos += w_bytes + 1

    return attr_list


def draw_text_line(cr, line_words, y, is_verse_last: bool,
                   layout_mode: str, line_h: int,
                   quran_fd: Pango.FontDescription):
    """Render one line of Quran text at position y using PangoCairo.

    - Justified layout: full Kashida justification for non-last lines.
    - Centred layout: last line centred, other lines spread to margins.
    - y is the top of the line area; text is centred vertically within line_h.
    """
    if layout_mode == "justified":
        text_width = TEXT_WIDTH_JUSTIFIED
        margin_x = MARGIN_X_JUSTIFIED
        rule_margin = MARGIN_X_JUSTIFIED
    else:
        text_width = WIDTH - 2 * MARGIN_X
        margin_x = MARGIN_X
        rule_margin = MARGIN_X

    line_text = _build_line_text_clean(line_words)
    if not line_text.strip():
        return

    attr_list = _build_line_attrs_clean(line_words)

    if layout_mode == "centered" and is_verse_last:
        # Last line: centred alignment, no justification, constrained to margins
        p_layout = _make_pango_layout(
            cr, line_text, _AMIRI_QURAN_FAMILY, 0,
            width_px=text_width, justify=False, alignment=Pango.Alignment.CENTER,
        )
        p_layout.set_font_description(quran_fd)
        _add_ot_features(attr_list, len(line_text.encode("utf-8")))
        p_layout.set_attributes(attr_list)
        p_layout.set_wrap(Pango.WrapMode.WORD)
        ink, log = p_layout.get_pixel_extents()
        v_offset = (line_h - ink.height) // 2
        x = WIDTH - margin_x - text_width
        cr.save()
        _set_cairo_color(cr, TEXT_COLOR)
        _show_layout_at(cr, p_layout, x, y + v_offset)
        cr.restore()
    else:
        # Non-last or justified lines: full Kashida justification
        p_layout = _make_pango_layout(
            cr, line_text, _AMIRI_QURAN_FAMILY, 0,
            width_px=text_width, justify=not is_verse_last,
            alignment=Pango.Alignment.LEFT,
        )
        p_layout.set_font_description(quran_fd)
        _add_ot_features(attr_list, len(line_text.encode("utf-8")))
        p_layout.set_attributes(attr_list)
        p_layout.set_wrap(Pango.WrapMode.WORD)
        ink, log = p_layout.get_pixel_extents()
        v_offset = (line_h - ink.height) // 2
        x = WIDTH - margin_x - text_width
        cr.save()
        _set_cairo_color(cr, TEXT_COLOR)
        _show_layout_at(cr, p_layout, x, y + v_offset)
        cr.restore()


def draw_line_rule(cr, y, layout_mode: str):
    """Horizontal rule between text lines."""
    if layout_mode == "justified":
        x0, x1 = MARGIN_X_JUSTIFIED, WIDTH - MARGIN_X_JUSTIFIED
    else:
        x0, x1 = MARGIN_X, WIDTH - MARGIN_X

    _set_cairo_color(cr, LINE_RULE_COLOR)
    cr.set_line_width(2)
    cr.move_to(x0, y)
    cr.line_to(x1, y)
    cr.stroke()


# ---------------------------------------------------------------------------
# Waqf overlay
# ---------------------------------------------------------------------------

def draw_waqf_overlays(cr, line_words, y, quran_fd, waqf_fd,
                       layout_mode: str = "centered",
                       is_verse_last: bool = False,
                       line_h: int = 150):
    """Draw Mushaf waqf indicator letters above the text line.

    Words retain their Unicode waqf marks during Pango shaping for
    correct GPOS positioning.  index_to_pos() returns word extents
    that account for mark positioning via RAQM/HarfBuzz.
    """
    if layout_mode == "justified":
        text_width = TEXT_WIDTH_JUSTIFIED
        margin_x = MARGIN_X_JUSTIFIED
    else:
        text_width = WIDTH - 2 * MARGIN_X
        margin_x = MARGIN_X

    line_text = _build_line_text_for_pango(line_words)
    if not line_text.strip():
        return

    if layout_mode == "centered" and is_verse_last:
        p_layout = _make_pango_layout(
            cr, line_text, _AMIRI_QURAN_FAMILY, 0,
            width_px=text_width, justify=False, alignment=Pango.Alignment.CENTER,
        )
    else:
        p_layout = _make_pango_layout(
            cr, line_text, _AMIRI_QURAN_FAMILY, 0,
            width_px=text_width, justify=not is_verse_last,
            alignment=Pango.Alignment.LEFT,
        )
    p_layout.set_font_description(quran_fd)
    p_layout.set_wrap(Pango.WrapMode.WORD)

    attr_list = _build_line_attrs(line_words)
    _add_ot_features(attr_list, len(line_text.encode("utf-8")))
    p_layout.set_attributes(attr_list)

    ink, log = p_layout.get_pixel_extents()
    base_x = WIDTH - margin_x - text_width + log.x
    text_ink_top = y + (line_h - ink.height) // 2

    waqf_items: list[tuple[int, int, str]] = []
    byte_pos = 0
    for wi, w in enumerate(line_words):
        w_bytes = len(w.text.encode("utf-8"))
        byte_next = byte_pos + w_bytes + 1
        if w.mushaf_letters:
            try:
                r_start = p_layout.index_to_pos(byte_pos)
                r_end = p_layout.index_to_pos(byte_next)
                word_left = base_x + (r_end.x // Pango.SCALE)
                word_right = base_x + (r_start.x // Pango.SCALE)
                if word_left > word_right:
                    word_left, word_right = word_right, word_left
                waqf_items.append((word_left, word_right, w.mushaf_letters))
            except Exception:
                pass
        byte_pos = byte_next

    if not waqf_items:
        return

    waqf_layout = Pango.Layout.new(PangoCairo.create_context(cr))
    waqf_layout.set_font_description(waqf_fd)

    cr.save()
    _set_cairo_color(cr, WAQF_MARKER_COLOR)

    for word_left, word_right, mushaf in waqf_items:
        waqf_layout.set_text(mushaf)
        w_ink, w_log = waqf_layout.get_pixel_extents()
        mushaf_x = (word_left + word_right - w_ink.width) // 2
        waqf_bottom_y = text_ink_top - 4
        cr.move_to(mushaf_x, waqf_bottom_y - w_ink.y - w_ink.height)
        PangoCairo.show_layout(cr, waqf_layout)

    cr.restore()
