import unicodedata

from .config import BASMALAH_WORD, AYAH_MARKER_CHAR, VERSE_MARKER_OPEN, VERSE_MARKER_CLOSE


def to_arabic_numeral(n):
    return "".join(chr(0x0660 + int(c)) if c.isdigit() else c for c in str(n))


WAQF_CATEGORIES = {"Mn", "Lm", "So"}

WAQF_MUSHAF_MAP = {
    0x06D6: "صلي",  # ۖ sad-lam-alef -> صلي (wasl awla, continuing preferred)
    0x06D7: "قلي",  # ۗ qaf-lam-alef -> قلي (stopping preferred)
    0x06D8: "طم",   # ۘ meem initial -> طم (preferred stop with concession)
    0x06DA: "ج",    # ۚ jeem -> ج (ja'iz, permissible)
    0x06DB: "ز",    # ۛ three dots -> ز (mushtarak)
    0x06DC: "صل",   # ۜ seen -> صل (permissible to continue)
    0x06DF: "م",    # ۟ rounded zero -> م (waqf lazim)
    0x06E2: "م",    # ۢ meem isolated -> م (waqf lazim)
    0x06E4: "ط",    # ۤ madda -> ط (waqf mutlaq)
    0x06E5: "و",    # ۥ small waw -> و (pronunciation)
    0x06E6: "ي",    # ۦ small yeh -> ي (pronunciation)
    0x06E7: "ج",    # ۧ small high yeh -> ج (ja'iz)
    0x06E8: "ن",    # ۨ small high noon -> ن (waqf noon)
    0x06EC: "م",    # ۬ rounded high stop -> م (waqf lazim)
    0x06ED: "م",    # ۭ low meem -> م (iqlab/waqf lazim)
}

WAQF_CHARS = set(WAQF_MUSHAF_MAP.keys()) | {0x06DE, 0x06E9}

ARABIC_NORMALIZE_MAP = {
    "\u0670\u0640": "\u0627\u0640",  # superscript alif + tatweel -> alif + tatweel
    "\u0670": "\u0622",              # standalone superscript alif -> madda alif
    "\u06CC": "\u064A",              # Farsi yeh -> Arabic yeh
    "\u200A": " ",                    # hair space -> regular space
    "\u2060": "",                     # word joiner -> remove
    "\u08F0": "\u064B",              # open fathatan -> fathatan
    "\u08F1": "\u064C",              # open dammatan -> dammatan
    "\u08F2": "\u064D",              # open kasratan -> kasratan
}


def normalize_arabic(text):
    for old, new in ARABIC_NORMALIZE_MAP.items():
        text = text.replace(old, new)
    return text


def extract_waqf(word):
    cleaned = []
    mushaf_letters = []
    for c in word:
        cp = ord(c)
        if cp in WAQF_MUSHAF_MAP:
            mushaf_letters.append(WAQF_MUSHAF_MAP[cp])
        elif cp == 0x06E1:
            pass  # hamzat al-wasl: keep as-is below
            cleaned.append(c)
        elif cp == 0x06DE or cp == 0x06E9:
            cleaned.append(c)  # rub el hizb, sajdah: keep in text
        else:
            cleaned.append(c)
    return "".join(cleaned), "".join(mushaf_letters)


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
    if not words:
        return text
    first = words[0].replace("\u06E1", "\u0652")
    if first == BASMALAH_WORD and len(words) > 4:
        return " ".join(words[4:])
    return text


def make_verse_marker(vnum, style="arabic_indicate"):
    if style == "ornate":
        return f" {VERSE_MARKER_OPEN}{to_arabic_numeral(vnum)}{VERSE_MARKER_CLOSE}"
    if style == "arabic_indicate":
        return AYAH_MARKER_CHAR + to_arabic_numeral(vnum)
    return f"\u27eb{to_arabic_numeral(vnum)}\u27ea"


def is_arabic_digit(c):
    return "\u0660" <= c <= "\u0669"


def is_verse_marker(word):
    stripped = word.strip()
    if not stripped:
        return False
    if stripped[0] == "\u06DD":
        return True
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


def _to_word_data(words_list, font, style="circle"):
    word_data = []
    for w, waqf in words_list:
        if style == "circle":
            is_marker = is_verse_marker(w)
        else:
            is_marker = is_verse_marker(w) or \
                        (style == "arabic_indicate" and w.startswith(AYAH_MARKER_CHAR)) or \
                        (style == "ornate" and (w.startswith(VERSE_MARKER_OPEN) or w.startswith(" " + VERSE_MARKER_OPEN)))
        bbox = font.getbbox(w)
        ww = bbox[2] - bbox[0]
        word_data.append((w, ww, is_marker, waqf))
    return word_data


def build_justified_lines(all_words, font, max_width):
    word_data = _to_word_data(all_words, font, style="circle")
    lines = []
    current = []
    current_w = 0
    for w, ww, is_marker, waqf in word_data:
        space_w = measure_word(font, " ") if current else 0
        if current and current_w + space_w + ww > max_width:
            lines.append(current)
            current = [(w, ww, is_marker, waqf)]
            current_w = ww
        else:
            if current:
                current_w += space_w
            current.append((w, ww, is_marker, waqf))
            current_w += ww
    if current:
        lines.append(current)
    return lines


def build_continuous_lines(all_words, font, max_width, style="ornate"):
    word_data = _to_word_data(all_words, font, style=style)
    lines = []
    current = []
    current_w = 0
    for w, ww, is_marker, waqf in word_data:
        space_w = measure_word(font, " ") if current else 0
        if current and current_w + space_w + ww > max_width:
            lines.append(current)
            current = [(w, ww, is_marker, waqf)]
            current_w = ww
        else:
            if current:
                current_w += space_w
            current.append((w, ww, is_marker, waqf))
            current_w += ww
    if current:
        lines.append(current)
    return lines


