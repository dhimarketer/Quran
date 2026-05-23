import unicodedata

from .config import BASMALAH_WORD, AYAH_MARKER_CHAR, VERSE_MARKER_OPEN, VERSE_MARKER_CLOSE


def to_arabic_numeral(n):
    return "".join(chr(0x0660 + int(c)) if c.isdigit() else c for c in str(n))


WAQF_CATEGORIES = {"Mn", "Lm"}

ARABIC_NORMALIZE_MAP = {
    "\u06ED": "\u06DA",  # small low meem -> small high jeem
    "\u06CC": "\u064A",  # Farsi yeh -> Arabic yeh (KFGQPC has no Farsi glyph)
    "\u06DF": "\u06DA",  # small high rounded zero -> small high jeem
    "\u08F0": "\u064B",  # open fathatan -> standard fathatan
    "\u08F1": "\u064C",  # open dammatan -> standard dammatan
    "\u08F2": "\u064D",  # open kasratan -> standard kasratan
    "\u06E6": "\u064A",  # small yeh -> Arabic yeh
    "\u200A": " ",       # hair space -> regular space
    "\u2060": "",        # word joiner -> remove
}

def normalize_arabic(text):
    for old, new in ARABIC_NORMALIZE_MAP.items():
        text = text.replace(old, new)
    return text

def _is_waqf_word(w):
    if not w:
        return False
    return all(
        unicodedata.category(c) in WAQF_CATEGORIES and ord(c) >= 0x0600
        or c == "\u0640"
        for c in w
    )


def attach_waqf_marks(words):
    result = []
    for w in words:
        if result and _is_waqf_word(w):
            result[-1] += w
        else:
            result.append(w)
    return result


def strip_bismillah(text):
    words = text.split()
    if words and words[0] == BASMALAH_WORD and len(words) > 4:
        return " ".join(words[4:])
    return text


def make_verse_marker(vnum, style="ornate"):
    if style == "ornate":
        return f" {VERSE_MARKER_OPEN}{to_arabic_numeral(vnum)}{VERSE_MARKER_CLOSE}"
    if style == "circle":
        return "  " + to_arabic_numeral(vnum)
    if style == "arabic_indicate":
        return AYAH_MARKER_CHAR + to_arabic_numeral(vnum)
    return f"\u27eb{to_arabic_numeral(vnum)}\u27ea"


def is_arabic_digit(c):
    return "\u0660" <= c <= "\u0669"


def is_verse_marker(word):
    """Detect if word is a standalone Arabic numeral (circle marker)."""
    stripped = word.strip()
    if not stripped:
        return False
    # allow one leading optional U+06DD
    if stripped[0] == "\u06DD":
        stripped = stripped[1:]
    return all(is_arabic_digit(c) for c in stripped)


def measure_word(font, word):
    bbox = font.getbbox(word)
    return bbox[2] - bbox[0]


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


def build_justified_lines(all_words, font, max_width):
    word_data = []
    for w in all_words:
        is_marker = is_verse_marker(w)
        bbox = font.getbbox(w)
        ww = bbox[2] - bbox[0]
        word_data.append((w, ww, is_marker))

    lines = []
    current = []
    current_w = 0

    for w, ww, is_marker in word_data:
        space_w = measure_word(font, " ") if current else 0

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


def build_continuous_lines(all_words, font, max_width, style="ornate"):
    word_data = []
    for w in all_words:
        is_marker = is_verse_marker(w) or \
                    (style == "arabic_indicate" and w.startswith(AYAH_MARKER_CHAR)) or \
                    (style == "ornate" and (w.startswith(VERSE_MARKER_OPEN) or w.startswith(" " + VERSE_MARKER_OPEN)))
        bbox = font.getbbox(w)
        ww = bbox[2] - bbox[0]
        word_data.append((w, ww, is_marker))

    lines = []
    current = []
    current_w = 0

    for w, ww, is_marker in word_data:
        space_w = measure_word(font, " ") if current else 0

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