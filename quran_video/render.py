"""
Page-based renderer using Cairo + PangoCairo.

Renders discrete 1920x1080 pages from the layout engine's output.
Each page is a standalone Cairo surface → numpy array.
"""
import numpy as np
from PIL import Image

import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango
import cairo

from .config import (
    WIDTH, HEIGHT, MARGIN_X, MARGIN_X_JUSTIFIED,
    BG_COLOR_CENTERED, DARK_GOLD, WAQF_FONT_SIZE,
    LINE_H_CENTERED, LINE_H_JUSTIFIED,
    FONT_SIZE_QURAN, FONT_SIZE_JUSTIFIED,
    FONT_SIZE_SURAH_AR, FONT_SIZE_SURAH_EN, FONT_SIZE_SURAH_JUSTIFIED,
    FONT_SIZE_BASMALAH, FONT_SIZE_BASMALAH_JUSTIFIED,
    FONT_AMIRI_BOLD, FONT_AMIRI_REG,
)
from .layout_engine import (
    LayoutEngine, Page, HeaderItem, BasmalahItem,
    TextLine, FooterItem,
)
from .drawing import (
    draw_ornament_line, draw_surah_header_centered,
    draw_surah_header_justified, draw_basmalah,
    draw_juz_footer, draw_text_line, draw_line_rule,
    draw_waqf_overlays, _cairo_rgb, _set_cairo_color,
)

_AMIRI_QURAN_FAMILY = "Amiri Quran"
_AMIRI_BOLD_FAMILY = "Amiri"
_AMIRI_REGULAR_FAMILY = "Amiri"


# ---------------------------------------------------------------------------
# Font descriptors (Pango FontDescription objects)
# ---------------------------------------------------------------------------

def _make_fds(layout_mode: str):
    """Create Pango FontDescription objects for each text role."""
    if layout_mode == "justified":
        fd_quran = Pango.FontDescription.from_string(
            f"{_AMIRI_QURAN_FAMILY} {FONT_SIZE_JUSTIFIED}")
        fd_ar = Pango.FontDescription.from_string(
            f"{_AMIRI_BOLD_FAMILY} Bold {FONT_SIZE_SURAH_JUSTIFIED}")
        fd_basm = Pango.FontDescription.from_string(
            f"{_AMIRI_QURAN_FAMILY} {FONT_SIZE_BASMALAH_JUSTIFIED}")
    else:
        fd_quran = Pango.FontDescription.from_string(
            f"{_AMIRI_QURAN_FAMILY} {FONT_SIZE_QURAN}")
        fd_ar = Pango.FontDescription.from_string(
            f"{_AMIRI_BOLD_FAMILY} Bold {FONT_SIZE_SURAH_AR}")
        fd_basm = Pango.FontDescription.from_string(
            f"{_AMIRI_QURAN_FAMILY} {FONT_SIZE_BASMALAH}")

    fd_en = Pango.FontDescription.from_string(
        f"{_AMIRI_BOLD_FAMILY} Bold {FONT_SIZE_SURAH_EN}")
    fd_footer = Pango.FontDescription.from_string(
        f"{_AMIRI_BOLD_FAMILY} Bold {FONT_SIZE_SURAH_EN}")
    fd_waqf = Pango.FontDescription.from_string(
        f"{_AMIRI_BOLD_FAMILY} Bold {WAQF_FONT_SIZE}")

    return fd_quran, fd_ar, fd_basm, fd_en, fd_footer, fd_waqf


# ---------------------------------------------------------------------------
# Page renderer
# ---------------------------------------------------------------------------

def render_pages(pages: list[Page], total_height: int,
                 layout_mode: str = "centered") -> list[np.ndarray]:
    """Render each Page to a 1920x1080 numpy array.

    Returns (page_arrays, total_height).
    """
    fd_quran, fd_ar, fd_basm, fd_en, fd_footer, fd_waqf = _make_fds(layout_mode)

    if layout_mode == "justified":
        line_h = LINE_H_JUSTIFIED
    else:
        line_h = LINE_H_CENTERED

    arrays = []
    for page in pages:
        arr = _render_one_page(page, total_height, layout_mode, line_h,
                               fd_quran, fd_ar, fd_basm, fd_en, fd_footer,
                               fd_waqf)
        arrays.append((page.scroll_y, arr))

    return arrays


def _render_one_page(page: Page, total_height: int, layout_mode: str,
                     line_h: int, fd_quran, fd_ar, fd_basm, fd_en,
                     fd_footer, fd_waqf) -> np.ndarray:
    """Render a single page to a numpy array."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    cr = cairo.Context(surf)

    # Background
    bg = _cairo_rgb(BG_COLOR_CENTERED)
    cr.set_source_rgb(*bg)
    cr.paint()

    # Top ornament line (only on first page, near the top of the scroll)
    if page.scroll_y == 0:
        draw_ornament_line(cr, 16, WIDTH, DARK_GOLD, 1, 350)

    # Bottom ornament line (only on last page, near the bottom)
    last_page_bottom = page.scroll_y + HEIGHT >= total_height - 4
    if last_page_bottom:
        bot_y_rel = total_height - page.scroll_y - 16
        draw_ornament_line(cr, bot_y_rel, WIDTH, DARK_GOLD, 1, 350)

    # Headers
    for h in page.headers:
        if layout_mode == "justified":
            draw_surah_header_justified(cr, h.y, h.name_ar, fd_ar)
        else:
            draw_surah_header_centered(cr, h.y, h.name_ar, h.name_en,
                                       fd_ar, fd_en)

    # Basmalahs
    for b in page.basmalahs:
        draw_basmalah(cr, b.y, layout_mode, fd_basm)

    # Text lines
    for i, tl in enumerate(page.text_lines):
        draw_text_line(cr, tl.words, tl.y, tl.is_verse_last,
                       layout_mode, line_h, fd_quran)
        draw_waqf_overlays(cr, tl.words, tl.y, fd_quran, fd_waqf,
                            layout_mode=layout_mode,
                            is_verse_last=tl.is_verse_last,
                            line_h=line_h)

        # Ruled line below (skip after the last text line on this page)
        is_page_last_line = (i == len(page.text_lines) - 1)
        if not is_page_last_line:
            rule_y = tl.y + line_h
            draw_line_rule(cr, rule_y, layout_mode)

    # Footer
    if page.footer:
        draw_juz_footer(
            cr, page.footer.y,
            page.footer.juz_num, page.footer.last_ayah,
            page.footer.surah_name, page.footer.surah_num,
            fd_footer,
        )

    # Convert Cairo surface to numpy array (RGBA → RGB)
    buf = surf.get_data()
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(HEIGHT, WIDTH, 4)
    # Cairo uses BGRA byte order in little-endian (ARGB in big-endian).
    # On little-endian, buf is BGRA. Convert to RGB.
    rgb = arr[:, :, :3].copy()
    # Swap B and R channels (Cairo BGRA → RGB)
    rgb[:, :, [0, 2]] = rgb[:, :, [2, 0]]
    return rgb


# ---------------------------------------------------------------------------
# High-level entry point (replaces render.render())
# ---------------------------------------------------------------------------

def build_and_render(elements: list, layout_mode: str = "centered"
                     ) -> tuple[list, int, list]:
    """Layout elements and render pages.

    Returns (page_arrays, total_height, pages).
    page_arrays is a list of (scroll_y, numpy_array) tuples.
    """
    engine = LayoutEngine(layout=layout_mode)
    pages, total_height = engine.layout_pages(elements)
    page_arrays = render_pages(pages, total_height, layout_mode)
    return page_arrays, total_height, pages


# ---------------------------------------------------------------------------
# Public API (matches old render module)
# ---------------------------------------------------------------------------

def render(elements, layout="centered", fonts=None):
    """Layout and render to pages. Returns (page_arrays, total_height)."""
    page_arrays, total_height, pages = build_and_render(elements, layout)
    return page_arrays, total_height


def load_fonts(layout="centered"):
    """No-op — Pango handles fonts internally via FontDescription."""
    return None


# ---------------------------------------------------------------------------
# Element builders
# ---------------------------------------------------------------------------

def build_elements_from_surah(surah, ayahs_slice=None):
    """Build element tuples from a surah dict.

    Verse elements are Verse dataclass instances; other elements are tuples.
    """
    from .text import normalize_arabic, strip_bismillah, Verse
    from .config import BASMALAH_WORD

    elements = []
    elements.append(("surah_header", surah["name"], surah.get("englishName", "")))
    if surah.get("number") != 9:
        elements.append(("basmalah",))

    first_ayah = surah["ayahs"][0]["text"].strip("\ufeff")
    has_bismillah = first_ayah.split()[0].replace("\u06E1", "\u0652") == BASMALAH_WORD

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
            elements.append(Verse(
                text=txt,
                number=v["number"],
                number_in_surah=display_num,
            ))
            display_num += 1

    return elements


def build_elements_from_juz(juz_data):
    """Build element tuples from juz data.

    Verse elements are Verse dataclass instances; other elements are tuples.
    """
    from .text import normalize_arabic, strip_bismillah, Verse

    elements = []
    last_surah = None
    is_first_ayah_in_surah = False
    last_ayah_in_surah = 0
    last_surah_name = ""
    last_surah_num = 0

    for ayah in juz_data["data"]["ayahs"]:
        surah_id = ayah["surah"]["number"]
        if surah_id != last_surah:
            elements.append(("surah_header", ayah["surah"]["name"],
                             ayah["surah"]["englishName"]))
            if surah_id != 9:
                elements.append(("basmalah",))
            last_surah = surah_id
            is_first_ayah_in_surah = True

        txt = normalize_arabic(ayah["text"])
        if is_first_ayah_in_surah:
            txt = strip_bismillah(txt)
            is_first_ayah_in_surah = False
            if not txt:
                continue

        elements.append(Verse(
            text=txt,
            number=ayah["number"],
            number_in_surah=ayah["numberInSurah"],
        ))
        last_ayah_in_surah = ayah["numberInSurah"]
        last_surah_name = ayah["surah"]["name"]
        last_surah_num = ayah["surah"]["number"]

    elements.append(("juz_footer", juz_data["data"]["number"],
                     last_ayah_in_surah, last_surah_name, last_surah_num))
    return elements
