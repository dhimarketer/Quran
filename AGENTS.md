# Project Agent Instructions

## Blueprint Maintenance

`blueprint.md` is the detailed technical blueprint for this project. It documents all key design decisions, data structures, rendering pipeline details, and configuration constants.

**After any code change, check `blueprint.md` and update it** to reflect the change. This includes but is not limited to:

- Changes to constants, data types, or configuration values
- Changes to function signatures, behavior, or return types
- Changes to the rendering pipeline, layout algorithms, or text processing logic
- Changes to font assignments, color values, or dimension constants
- Changes to CLI arguments, data sources, or file formats
- Bug fixes that affect documented behavior
- New features or edge case handling

When updating `blueprint.md`:

1. Read the relevant section first to understand what's currently documented
2. Edit only the parts that need to change — preserve the rest verbatim
3. Keep tables, code blocks, and section structure consistent
4. If a change adds a new concept, add a new section or subsection rather than burying it in an existing one
5. Update the commit history table with a descriptive entry for the current change

## Project Structure

This is a Quran video generator. Key modules:

- `quran_video/text.py` — Arabic text processing, waqf marks, normalization
- `quran_video/render.py` — Layout engine and image rasterization
- `quran_video/drawing.py` — Drawing primitives (headers, basmalah, footer)
- `quran_video/config.py` — Constants, dimensions, colors, font paths
- `quran_video/cli.py` — CLI entry point
- `quran_video/api.py` — Quran data fetching
- `quran_video/encode.py` — FFmpeg video encoding
- `quran_video/timing.py` — Ayah duration from MP3 metadata

## Key Conventions

- Both layouts use **AmiriQuran with RAQM** for Quran text — this is essential for Arabic shaping
- `WAQF_CATEGORIES = {"Mn", "Lm", "So"}` — covers combining marks, modifier letters, and symbols
- `WAQF_MUSHAF_MAP` maps Unicode waqf code points to traditional Mushaf indicator letters — compound symbols like صلي, قلي, صل, طم for nuanced stop rules, and single letters (م ج ط ز ن و ي) for simple rules
- `extract_waqf(word)` removes waqf marks from word text and returns `(cleaned_word, mushaf_letters)` — invisible marks are stripped, visible ones are kept in text AND also generate a Mushaf letter
- Mushaf letters are drawn above their word in `WAQF_MARKER_COLOR` using `WAQF_FONT_SIZE` Amiri Bold font
- `ARABIC_NORMALIZE_MAP` only contains formatting mappings (Farsi yeh, hair space, word joiner, open tanween) — waqf mark normalization is handled by `WAQF_MUSHAF_MAP` instead
- U+06DE (rub el hizb) and U+06E9 (sajdah) are kept in-text as standalone symbols
- U+06E1 (hamzat al-wasl) is kept in-text — it's a sukun indicator, not a stop mark
- `ARABIC_NORMALIZE_MAP` normalizes U+0670 (superscript alif ٰ) → U+0622 (madda alif آ) so the alif renders as a visible letter instead of a tiny circle; U+0670+U+0640 (tatweel+superscript alif ـٰ) → U+0622+U+0640 (tatweel+madda alif ـآ)
- U+06E0 (silent alif marker ۠) is kept in-text — it's an orthographic marker indicating a silent alif, not a waqf stop mark
- KFGQPC font is no longer used
- `normalize_arabic(text)` is a simple function (no font parameter) — same normalization for both layouts
- Verse markers use U+06DD (۝) Arabic End of Ayah character followed by Arabic-Indic numeral — a font-based marker, not a drawn shape
- Line breaking is continuous: all words across verses flow together, wrapping at line width, justified or centered as before
- Every verse gets its own U+06DD+numeral marker at the end of its words