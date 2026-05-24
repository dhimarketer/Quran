"""Arabic text processing and normalization for Quran video generation.

Pure functions — no side effects, no PIL/Pango dependencies.
The LayoutEngine handles all rendering concerns.
"""
import unicodedata
from dataclasses import dataclass
from typing import Optional

from .config import BASMALAH_WORD, AYAH_MARKER_CHAR, VERSE_MARKER_OPEN, VERSE_MARKER_CLOSE


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Verse:
    """Immutable representation of a single Quranic verse.

    Holds the cleaned text (normalized, basmalah stripped if applicable)
    along with its numbering.  The LayoutEngine decides how to render it.
    """
    text: str
    number: int              # global ayah number (1-6236)
    number_in_surah: int     # verse number within its surah (1-N)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WAQF_CATEGORIES = {"Mn", "Lm", "So"}

WAQF_MUSHAF_MAP = {
    0x06D6: "صلي",  # ۖ sad-lam-alef → صلي (wasl awla, continuing preferred)
    0x06D7: "قلي",  # ۗ qaf-lam-alef → قلي (stopping preferred)
    0x06D8: "طم",   # ۘ meem initial → طم (preferred stop with concession)
    0x06DA: "ج",    # ۚ jeem → ج (ja'iz, permissible)
    0x06DB: "ز",    # ۛ three dots → ز (mushtarak)
    0x06DC: "صل",   # ۜ seen → صل (permissible to continue)
    0x06DF: "م",    # ۟ rounded zero → م (waqf lazim)
    0x06E2: "م",    # ۢ meem isolated → م (waqf lazim)
    0x06E4: "ط",    # ۤ madda → ط (waqf mutlaq)
    0x06E5: "و",    # ۥ small waw → و (pronunciation)
    0x06E6: "ي",    # ۦ small yeh → ي (pronunciation)
    0x06E7: "ج",    # ۧ small high yeh → ج (ja'iz)
    0x06E8: "ن",    # ۨ small high noon → ن (waqf noon)
    0x06EC: "م",    # ۬ rounded high stop → م (waqf lazim)
    0x06ED: "م",    # ۭ low meem → م (iqlab / waqf lazim)
}

ARABIC_NORMALIZE_MAP = {
    "\u0670\u0640": "\u0627\u0640",  # superscript alif + tatweel → alif + tatweel
    "\u0670": "\u0622",              # standalone superscript alif → madda alif
    "\u06CC": "\u064A",              # Farsi yeh → Arabic yeh
    "\u200A": " ",                    # hair space → regular space
    "\u2060": "",                     # word joiner → remove
    "\u08F0": "\u064B",              # open fathatan → fathatan
    "\u08F1": "\u064C",              # open dammatan → dammatan
    "\u08F2": "\u064D",              # open kasratan → kasratan
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def to_arabic_numeral(n: int) -> str:
    """Convert integer to Arabic-Indic digits (U+0660–U+0669)."""
    return "".join(chr(0x0660 + int(c)) if c.isdigit() else c for c in str(n))


def normalize_arabic(text: str) -> str:
    """Apply formatting-level character replacements.

    Handles: superscript alif, Farsi yeh, hair space, word joiner,
    open tanween variants.  Does NOT modify waqf marks — those are
    handled by extract_waqf() + WAQF_MUSHAF_MAP.
    """
    for old, new in ARABIC_NORMALIZE_MAP.items():
        text = text.replace(old, new)
    return text


def extract_waqf(word: str) -> tuple[str, str]:
    """Remove Unicode waqf marks from *word* and collect Mushaf letters.

    Returns (cleaned_word, mushaf_letters) where mushaf_letters is a
    string of traditional Mushaf indicator characters (م ج ط etc.)
    to be drawn above the word.
    """
    cleaned: list[str] = []
    mushaf: list[str] = []
    for c in word:
        cp = ord(c)
        if cp in WAQF_MUSHAF_MAP:
            mushaf.append(WAQF_MUSHAF_MAP[cp])
        elif cp == 0x06E1:
            cleaned.append(c)  # hamzat al-wasl: keep in text
        elif cp in (0x06DE, 0x06E9):
            cleaned.append(c)  # rub el hizb / sajdah: keep in text
        else:
            cleaned.append(c)
    return "".join(cleaned), "".join(mushaf)


def _is_waqf_word(w: str) -> bool:
    """Return True if every character is a waqf-mark category."""
    if not w:
        return False
    return all(
        unicodedata.category(c) in WAQF_CATEGORIES and ord(c) >= 0x0600
        or c == "\u0640"
        for c in w
    )


def attach_waqf_marks(words: list[str]) -> list[str]:
    """Merge standalone waqf-mark words with the preceding word.

    This lets the shaper position waqf marks above their host word.
    """
    result: list[str] = []
    for w in words:
        if result and _is_waqf_word(w):
            result[-1] += w
        else:
            result.append(w)
    return result


def strip_bismillah(text: str) -> str:
    """Remove the basmalah from verse 1 text.

    Normalizes the sukun variant (U+06E1 → U+0652) in the first word
    for comparison, then drops the first four words if the verse
    starts with the basmalah.
    """
    words = text.split()
    if not words:
        return text
    first = words[0].replace("\u06E1", "\u0652")
    if first == BASMALAH_WORD and len(words) >= 4:
        return " ".join(words[4:])
    return text


def make_verse_marker(vnum: int, style: str = "arabic_indicate") -> str:
    """Format a verse number according to *style*.

    - "ornate":            ﴿NUM﴾
    - "arabic_indicate":   ۝NUM  (default)
    """
    if style == "ornate":
        return f" {VERSE_MARKER_OPEN}{to_arabic_numeral(vnum)}{VERSE_MARKER_CLOSE}"
    if style == "arabic_indicate":
        return AYAH_MARKER_CHAR + to_arabic_numeral(vnum)
    return f"\u27eb{to_arabic_numeral(vnum)}\u27ea"


# ---------------------------------------------------------------------------
# Utility (kept for compatibility — not used by current pipeline)
# ---------------------------------------------------------------------------

def is_arabic_digit(c: str) -> bool:
    """Return True if *c* is an Arabic-Indic digit U+0660–U+0669."""
    return "\u0660" <= c <= "\u0669"


def is_verse_marker(word: str) -> bool:
    """Return True if *word* looks like a standalone verse marker."""
    stripped = word.strip()
    if not stripped:
        return False
    if stripped[0] == "\u06DD":
        return True
    return all(is_arabic_digit(c) for c in stripped)
