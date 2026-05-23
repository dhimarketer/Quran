import unicodedata

from .config import BASMALAH_WORD, AYAH_MARKER_CHAR, VERSE_MARKER_OPEN, VERSE_MARKER_CLOSE


def to_arabic_numeral(n):
    return "".join(chr(0x0660 + int(c)) if c.isdigit() else c for c in str(n))


def attach_waqf_marks(words):
    result = []
    for w in words:
        if result and all(unicodedata.category(c) == "Mn" for c in w):
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
    if style == "arabic_indicate":
        return AYAH_MARKER_CHAR + to_arabic_numeral(vnum)
    return f"\u27eb{to_arabic_numeral(vnum)}\u27ea"


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
        is_marker = w.startswith(AYAH_MARKER_CHAR)
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
        is_marker = (style == "arabic_indicate" and w.startswith(AYAH_MARKER_CHAR)) or \
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