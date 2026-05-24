"""
PangoCairo-based text layout engine for Quran video generation.

Replaces manual word-splitting with native Pango layout:
- Kashida-based Arabic justification (not space-widening)
- Proper RTL line-breaking and word-wrap
- Pango attributes for colouring verse markers differently from text
- Page-based output (1920x1080 pages) instead of one tall image
"""
from dataclasses import dataclass, field
from typing import Optional

import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo
import cairo

from .config import (
    WIDTH, HEIGHT, MARGIN_X, MARGIN_X_JUSTIFIED, TEXT_WIDTH_JUSTIFIED,
    TEXT_COLOR, VERSE_MARKER_COLOR, WAQF_MARKER_COLOR, WAQF_FONT_SIZE,
    LINE_RULE_COLOR,
    LINE_H_CENTERED, LINE_H_JUSTIFIED,
    FONT_SIZE_QURAN, FONT_SIZE_JUSTIFIED,
    FONT_SIZE_SURAH_AR, FONT_SIZE_SURAH_EN, FONT_SIZE_SURAH_JUSTIFIED,
    FONT_SIZE_BASMALAH, FONT_SIZE_BASMALAH_JUSTIFIED,
    TOP_PAD, BOT_PAD,
)
from .text import (
    attach_waqf_marks, extract_waqf, get_waqf_mushaf_letters, make_verse_marker, Verse,
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WordSlot:
    """A word with waqf overlay info and position tracking.

    char_start and char_end are byte offsets into the Pango text buffer
    (Pango uses UTF-8 byte offsets internally).

    text contains waqf marks — used by draw_waqf_overlays for positioning.
    text_clean has waqf marks stripped — used by draw_text_line for rendering.
    """
    text: str
    text_clean: str
    mushaf_letters: str
    is_marker: bool       # verse-end marker (U+06DD + numeral)
    char_start: int = 0   # byte offset into Pango text
    char_end: int = 0


@dataclass
class TextLine:
    """One wrapped-and-justified line of Quran text."""
    words: list[WordSlot]
    y: int = 0
    is_verse_last: bool = False


@dataclass
class HeaderItem:
    """A surah header positioned on the virtual scroll."""
    y: int
    height: int
    name_ar: str
    name_en: str
    layout: str


@dataclass
class BasmalahItem:
    """A basmalah positioned on the virtual scroll."""
    y: int
    height: int


@dataclass
class FooterItem:
    """A juz footer positioned on the virtual scroll."""
    y: int
    height: int
    juz_num: int
    last_ayah: int
    surah_name: str
    surah_num: int


@dataclass
class Page:
    """One discrete 1920x1080 page of the virtual scroll."""
    index: int
    scroll_y: int
    headers: list[HeaderItem]    = field(default_factory=list)
    basmalahs: list[BasmalahItem] = field(default_factory=list)
    text_lines: list[TextLine]    = field(default_factory=list)
    footer: Optional[FooterItem]  = None


# ---------------------------------------------------------------------------
# LayoutEngine
# ---------------------------------------------------------------------------

_AMIRI_QURAN_FAMILY = "Amiri Quran"
_AMIRI_BOLD_FAMILY = "Amiri"
_AMIRI_REGULAR_FAMILY = "Amiri"


class LayoutEngine:
    """Measures and lays out Quranic text using Pango.

    Produces a list of Page objects, each holding the items that
    appear within a 1080-pixel-tall window on the virtual scroll.
    """

    def __init__(self, layout: str = "centered"):
        self.layout = layout
        self._init_fonts(layout)
        self._init_constants(layout)

    # -- init ---------------------------------------------------------------

    def _init_fonts(self, layout):
        if layout == "justified":
            self.fd_quran = Pango.FontDescription.from_string(
                f"{_AMIRI_QURAN_FAMILY} {FONT_SIZE_JUSTIFIED}")
            self.fd_ar = Pango.FontDescription.from_string(
                f"{_AMIRI_BOLD_FAMILY} Bold {FONT_SIZE_SURAH_JUSTIFIED}")
            self.fd_basm = Pango.FontDescription.from_string(
                f"{_AMIRI_QURAN_FAMILY} {FONT_SIZE_BASMALAH_JUSTIFIED}")
        else:
            self.fd_quran = Pango.FontDescription.from_string(
                f"{_AMIRI_QURAN_FAMILY} {FONT_SIZE_QURAN}")
            self.fd_ar = Pango.FontDescription.from_string(
                f"{_AMIRI_BOLD_FAMILY} Bold {FONT_SIZE_SURAH_AR}")
            self.fd_basm = Pango.FontDescription.from_string(
                f"{_AMIRI_QURAN_FAMILY} {FONT_SIZE_BASMALAH}")

        self.fd_waqf = Pango.FontDescription.from_string(
            f"{_AMIRI_BOLD_FAMILY} Bold {WAQF_FONT_SIZE}")

    def _init_constants(self, layout):
        if layout == "justified":
            self.text_width = TEXT_WIDTH_JUSTIFIED
            self.margin_x = MARGIN_X_JUSTIFIED
            self.line_h = LINE_H_JUSTIFIED
            self.header_h = 2 * 35 + FONT_SIZE_SURAH_JUSTIFIED + 40
            self.basmalah_h = FONT_SIZE_BASMALAH_JUSTIFIED + 20 + 36
        else:
            self.text_width = WIDTH - 2 * MARGIN_X
            self.margin_x = MARGIN_X
            self.line_h = LINE_H_CENTERED
            self.header_h = 36 + 28 + FONT_SIZE_SURAH_AR + 12 + FONT_SIZE_SURAH_EN + 16 + 36
            self.basmalah_h = FONT_SIZE_BASMALAH + 20 + 36

    # -- public API ---------------------------------------------------------

    def layout_pages(self, elements: list) -> tuple[list[Page], int]:
        """Convert element tuples into a list of Page objects.

        Returns (pages, total_height).
        """
        all_items = self._layout_items(elements)
        return self._paginate(all_items)

    # -- item layout --------------------------------------------------------

    def _layout_items(self, elements: list) -> list:
        """Process elements sequentially, laying out verse text in batches
        per surah block. Returns flat list of all positioned items."""
        items: list = []
        y = TOP_PAD

        verse_texts: list[str] = []
        verse_vnums: list[int] = []

        def flush_verse_batch():
            nonlocal y
            if not verse_texts:
                return
            lines = self._pango_layout(verse_texts, verse_vnums)
            for li in lines:
                li.y = y
                items.append(li)
                y += self.line_h
            verse_texts.clear()
            verse_vnums.clear()

        for elem in elements:
            if isinstance(elem, Verse):
                verse_texts.append(elem.text)
                verse_vnums.append(elem.number_in_surah)
                continue

            kind = elem[0]

            if kind == "surah_header":
                flush_verse_batch()
                name_ar, name_en = elem[1], elem[2]
                items.append(HeaderItem(
                    y=y, height=self.header_h,
                    name_ar=name_ar, name_en=name_en or "",
                    layout=self.layout,
                ))
                y += self.header_h
                verse_texts.clear()
                verse_vnums.clear()

            elif kind == "basmalah":
                items.append(BasmalahItem(y=y, height=self.basmalah_h))
                y += self.basmalah_h

            elif kind == "juz_footer":
                flush_verse_batch()
                footer_h = 80
                items.append(FooterItem(
                    y=y, height=footer_h,
                    juz_num=elem[1], last_ayah=elem[2],
                    surah_name=elem[3], surah_num=elem[4],
                ))
                y += footer_h

        flush_verse_batch()

        return items

    # -- Pango line-breaking ------------------------------------------------

    def _pango_layout(self, verse_texts: list[str],
                      verse_vnums: list[int]) -> list[TextLine]:
        """Feed verse texts through Pango, return wrapped + justified lines."""
        text, attr_list, word_slots = self._build_text_with_tracking(
            verse_texts, verse_vnums)

        if not text.strip():
            return []

        # Create a tiny disposable surface for the Pango context
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
        cr = cairo.Context(surf)
        pango_ctx = PangoCairo.create_context(cr)
        layout = Pango.Layout.new(pango_ctx)
        layout.set_font_description(self.fd_quran)
        layout.set_text(text)

        ot_features = Pango.AttrFontFeatures.new("mark 1, mkmk 1, ccmp 1")
        ot_features.start_index = 0
        ot_features.end_index = len(text.encode("utf-8"))
        attr_list.insert(ot_features)

        layout.set_attributes(attr_list)
        layout.set_width(Pango.units_from_double(self.text_width))
        layout.set_wrap(Pango.WrapMode.WORD)
        layout.set_justify(True)
        layout.set_alignment(Pango.Alignment.LEFT)
        layout.set_auto_dir(True)

        line_count = layout.get_line_count()
        text_lines: list[TextLine] = []
        text_byte_len = len(text.encode("utf-8"))

        for li in range(line_count):
            pango_line = layout.get_line(li)
            if pango_line is None:
                continue
            if pango_line.start_index >= text_byte_len:
                continue  # phantom trailing lines from Pango justification

            line_start = pango_line.start_index
            line_end = line_start + pango_line.length

            # Gather word slots whose start falls within this line's range.
            # Pango WORD wrapping never splits words, so checking start
            # position is sufficient.
            line_words: list[WordSlot] = []
            for ws in word_slots:
                if ws.char_start < line_start:
                    continue
                if ws.char_start >= line_end:
                    continue
                line_words.append(WordSlot(
                    text=ws.text,
                    text_clean=ws.text_clean,
                    mushaf_letters=ws.mushaf_letters,
                    is_marker=ws.is_marker,
                    char_start=ws.char_start,
                    char_end=ws.char_end,
                ))

            text_lines.append(TextLine(
                words=line_words,
                y=0,
                is_verse_last=False,
            ))

        # Only the last line is unjusified and centred
        if text_lines:
            text_lines[-1].is_verse_last = True

        return text_lines

    def _build_text_with_tracking(self, verse_texts: list[str],
                                  verse_vnums: list[int]):
        """Build a text string for Pango with colour attributes and word
        position tracking.

        Uses byte positions throughout because Pango's internal indices
        (line start_index, attribute start/end) are byte offsets into
        the UTF-8 representation of the text.

        Returns (full_text, attr_list, word_slots).
        """
        parts: list[str] = []
        attr_list = Pango.AttrList()
        word_slots: list[WordSlot] = []
        byte_pos = 0

        # Get the UTF-8 bytes of the accumulated text to track byte offsets.
        # We build the text as before (character-level) and compute byte
        # offsets by encoding each part incrementally.
        text_parts: list[str] = []

        # 8-bit → 16-bit colour channels for Pango
        vr, vg, vb = (c * 257 for c in VERSE_MARKER_COLOR)

        for i, (text, vnum) in enumerate(zip(verse_texts, verse_vnums)):
            raw_words = attach_waqf_marks(text.split())

            for w in raw_words:
                if not w:
                    continue
                cleaned, mushaf = extract_waqf(w)
                if not cleaned:
                    continue
                start = byte_pos
                text_parts.append(w)
                byte_pos += len(w.encode("utf-8"))
                word_slots.append(WordSlot(
                    text=w,
                    text_clean=cleaned,
                    mushaf_letters=mushaf,
                    is_marker=False,
                    char_start=start,
                    char_end=byte_pos,
                ))

                # Space separator between words
                text_parts.append(" ")
                byte_pos += 1  # space is 1 byte in UTF-8

            # Verse-end marker (coloured gold)
            marker = make_verse_marker(vnum, style="arabic_indicate")
            start = byte_pos
            text_parts.append(marker)
            end = start + len(marker.encode("utf-8"))
            byte_pos = end
            word_slots.append(WordSlot(
                text=marker,
                text_clean=marker,
                mushaf_letters="",
                is_marker=True,
                char_start=start,
                char_end=end,
            ))
            attr = Pango.attr_foreground_new(vr, vg, vb)
            attr.start_index = start
            attr.end_index = end
            attr_list.insert(attr)

            # Space between verses (but not after the last verse)
            if i < len(verse_texts) - 1:
                text_parts.append(" ")
                byte_pos += 1

        return "".join(text_parts).rstrip(), attr_list, word_slots

    # -- pagination ---------------------------------------------------------

    _PAGE_HEIGHT = HEIGHT
    _PAGE_OVERLAP = 4

    def _paginate(self, items: list) -> tuple[list[Page], int]:
        """Split layout items into 1920x1080 Page windows.

        Only creates pages that contain at least one content item.
        The last page may be shorter than PAGE_HEIGHT.
        """
        if not items:
            return [], BOT_PAD + TOP_PAD

        # Determine total virtual height
        max_y = 0
        for item in items:
            max_y = max(max_y, self._item_bottom(item))
        total_height = max_y + BOT_PAD

        pages: list[Page] = []
        scroll_y = 0

        while scroll_y < max_y:  # stop at last content item, not total_height
            page = Page(index=len(pages), scroll_y=scroll_y)
            page_end_y = scroll_y + self._PAGE_HEIGHT

            for item in items:
                item_bottom = self._item_bottom(item)
                item_top = item.y if hasattr(item, 'y') else 0

                if item_bottom <= scroll_y:
                    continue
                if item_top >= page_end_y:
                    continue

                rel = self._rel_item(item, -scroll_y)
                if isinstance(item, HeaderItem):
                    page.headers.append(rel)
                elif isinstance(item, BasmalahItem):
                    page.basmalahs.append(rel)
                elif isinstance(item, TextLine):
                    page.text_lines.append(rel)
                elif isinstance(item, FooterItem):
                    page.footer = rel

            pages.append(page)
            next_y = scroll_y + self._PAGE_HEIGHT - self._PAGE_OVERLAP
            # Ensure forward progress
            if next_y <= scroll_y:
                break
            scroll_y = next_y

        return pages, total_height

    def _item_bottom(self, item) -> int:
        if isinstance(item, HeaderItem):
            return item.y + item.height
        elif isinstance(item, BasmalahItem):
            return item.y + item.height
        elif isinstance(item, TextLine):
            return item.y + self.line_h
        elif isinstance(item, FooterItem):
            return item.y + item.height
        return 0

    def _rel_item(self, item, offset_y: int):
        """Return a copy of *item* with Y shifted by *offset_y*."""
        if isinstance(item, HeaderItem):
            return HeaderItem(
                y=item.y + offset_y, height=item.height,
                name_ar=item.name_ar, name_en=item.name_en,
                layout=item.layout,
            )
        elif isinstance(item, BasmalahItem):
            return BasmalahItem(y=item.y + offset_y, height=item.height)
        elif isinstance(item, TextLine):
            return TextLine(
                words=item.words, y=item.y + offset_y,
                is_verse_last=item.is_verse_last,
            )
        elif isinstance(item, FooterItem):
            return FooterItem(
                y=item.y + offset_y, height=item.height,
                juz_num=item.juz_num, last_ayah=item.last_ayah,
                surah_name=item.surah_name, surah_num=item.surah_num,
            )
        return item
