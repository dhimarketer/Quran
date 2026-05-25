# Quran Video Generator — Technical Blueprint

## Project Structure

```
Quran/
├── quran_video/                  # Main Python package
│   ├── __init__.py               # Package init, exports `main`
│   ├── __main__.py               # Entry: `python -m quran_video`
│   ├── cli.py                    # CLI argument parsing, orchestration
│   ├── config.py                 # Constants — dimensions, colors, fonts, paths
│   ├── api.py                    # Quran data — local quran.json / API fetch
│   ├── text.py                   # Arabic text processing, normalization
│   ├── layout_engine.py          # PangoCairo text layout + Kashida justification + pagination
│   ├── drawing.py                # Cairo drawing primitives — headers, basmalah, footer
│   ├── render.py                 # Page-based renderer via Cairo + Pango
│   ├── timing.py                 # Ayah duration from Al-Afasy MP3 metadata
│   └── encode.py                 # FFmpeg streaming video encoder (page-based)
├── legacy/                       # Pre-refactor scripts (not used by package)
│   ├── test_video.py             # Fatihah test — centered, KFGQPC
│   ├── test_video_long.py        # Al-Baqarah 1-30 test
│   ├── test_video_justified.py   # Mus'haf-style justified layout
│   ├── test_20_verses.py         # Quick 20-verse test
│   └── generate_videos.py        # Original juz generator (pre-refactor)
├── generate_chapter.py           # Standalone chapter generator (Noto + Amiri)
├── requirements.txt              # numpy, Pillow, imageio-ffmpeg, mutagen, PyGObject
├── quran.json                    # Local Quran data — 114 surahs, 6236 verses
├── quran-full-tashkeel.txt       # Full tashkeel concatenated Quran
├── quran-min-tashkeel.txt        # Minimal tashkeel concatenated Quran
├── cache/                        # Downloaded API & timing data
│   ├── juz_*.json                # Cached juz responses from alquran.cloud
│   ├── surah_*_quran-uthmani.json
│   └── ayah_durations_partial.json  # 148 entries (partial)
└── output/                       # Generated MP4 files
```

---

## Dependencies

```
numpy
Pillow
imageio-ffmpeg
mutagen
PyGObject (gi)
PyGObject-cairo (gi.repository.PangoCairo)
```

| Package | Usage |
|---|---|
| **numpy** | Array ops for page frame construction |
| **Pillow** | Image conversion from Cairo surface |
| **imageio-ffmpeg** | FFmpeg binary path via `imageio_ffmpeg.get_ffmpeg_exe()` |
| **mutagen** | MP3 metadata parsing for ayah durations |
| **PyGObject** | Pango + PangoCairo for Arabic text layout with Kashida justification |
| **cairo (PyGObject)** | cairo.ImageSurface for page rendering |
| **imageio-ffmpeg** | FFmpeg binary path via `imageio_ffmpeg.get_ffmpeg_exe()` |
| **mutagen** | MP3 metadata parsing for ayah durations |

No `pyproject.toml`, `setup.py`, or `setup.cfg`.

---

## CLI

### Invocation

```bash
python -m quran_video [OPTIONS]
```

`__main__.py` → `cli.main()`, `__init__.py` exports `main`.

### Arguments

| Flag | Type | Default | Description |
|---|---|---|---|
| `--surah` / `--chapter` | int | None | Surah number 1-114 |
| `--juz` | int | None | Juz number 1-30 |
| `--verse` | str | None | `CHAPTER:VERSE` or `CHAPTER:START-END` |
| `--ayahs` | str | None | Verse range within surah: `START-END` |
| `--layout` | `centered`\|`justified` | `centered` | Layout style |
| `--output` | str | None | Custom output filename |
| `--duration` | str | None | Total video duration (e.g. `30m`, `1800`, `1h30m`). Juz default: 30m. Surah: derived from juz proportionally. |
| `--workers` | int | None | Number of parallel encode workers. None/0 = serial (default). N > 1 = parallel. |
| `--hang-timeout` | int | 120 | Seconds without ffmpeg progress before auto-abort (0 = disable) |

### CLI Flow

1. Parse args
2. If `--duration`: parse duration string (e.g. `30m`, `1h30m`, `1800`) into seconds
3. If `--verse`: parse spec → `generate_surah_video(chapter, layout, range, ...)`
4. If `--surah` [+ optional `--ayahs`]: → `generate_surah_video(...)`
5. If `--juz`: → `generate_juz_video(juz_num, ...)` — adds 3 s footer hold at end by capping `scroll_range` at last page's `scroll_y` and appending `3*FPS` extra frames
6. If no args: print help, exit(1)

Duration defaults:
- **Juz**: 30 minutes (1800 s) + 3 s footer hold = 1803 s total
- **Surah / verse range**: derived proportionally from juz default — `num_verses × (DEFAULT_JUZ_DURATION / AVG_AYAHS_PER_JUZ)` where AVG_AYAHS_PER_JUZ = 6236/30 ≈ 208
- Per-ayah MP3 timing downloads are no longer triggered by default

### Verse Spec Parser

- `"34:1-30"` → `(chapter=34, start=1, end=30)`
- `"34:15"` → `(chapter=34, start=15, end=15)`

---

## Data Sources

### Local: `quran.json`

JSON array of 114 surahs from `quran-cloud` npm package.

```json
{
  "id": 1, "name": "الفاتحة", "transliteration": "Al-Fatihah",
  "type": "meccan", "total_verses": 7,
  "verses": [
    {"id": 1, "text": "بِسۡمِ ..."},
    ...
  ]
}
```

- Total: 114 surahs, 6236 verses
- Surah 1 verse 1 **is** the basmalah in the data — the code strips it for separate rendering

### API: Juz (`api.py`)

- Endpoint: `https://api.alquran.cloud/v1/juz/{juz_num}`
- Cached in `cache/juz_{N}.json`
- Each ayah: `number`, `text`, `surah` (object with `name`, `englishName`), `numberInSurah`

### Timing Data (`timing.py`)

- Source: Al-Afasy MP3s at `https://cdn.islamic.network/quran/audio/128/ar.alafasy/{global_num}.mp3`
- Duration via `mutagen.File().info.length`
- Cached in `cache/ayah_durations.json` (partial: 148 entries)
- Fallback: `5.0` seconds per ayah

### Unused Data Files

`quran-full-tashkeel.txt` and `quran-min-tashkeel.txt` contain concatenated Quran text with SQL headers — not used by current code.

---

## Fonts

### Font Files

| Constant | Path | Fallback | Purpose |
|---|---|---|---|
| `FONT_AMIRI_QURAN` | `~/.local/share/fonts/AmiriQuran.ttf` | NotoNaskhArabic-Regular | Both layouts: Quran text + Basmalah |
| `FONT_AMIRI_BOLD` | `~/.local/share/fonts/Amiri-Bold.ttf` | NotoNaskhArabic-Bold | Arabic surah header |
| `FONT_AMIRI_REG` | `~/.local/share/fonts/Amiri-Regular.ttf` | NotoNaskhArabic-Regular | Footer text |

### Font Sizes & Layout Assignment

| Constant | Size | Layout | Used For |
|---|---|---|---|
| `FONT_SIZE_QURAN` | 58 | centered | Quranic verse text (AmiriQuran) |
| `FONT_SIZE_BASMALAH` | 64 | centered | Basmalah text (AmiriQuran) |
| `FONT_SIZE_SURAH_AR` | 46 | centered | Arabic surah name (Amiri Bold) |
| `FONT_SIZE_SURAH_EN` | 26 | centered | Footer text (Amiri Regular) |
| `FONT_SIZE_JUSTIFIED` | 58 | justified | Quranic verse text (AmiriQuran) |
| `FONT_SIZE_BASMALAH_JUSTIFIED` | 64 | justified | Basmalah text (AmiriQuran) |
| `FONT_SIZE_SURAH_JUSTIFIED` | 46 | justified | Arabic surah name (Amiri Bold) |

### Font Loading (`render.py:load_fonts`)

- **Centered**: returns `(font_quran, font_ar, font_basm)` — **with `layout_engine=Layout.RAQM`**
  - AmiriQuran @ 58, AmiriBold @ 46, AmiriQuran @ 64
- **Justified**: returns `(font_quran, font_ar, font_basm)` — **with `layout_engine=Layout.RAQM`**
  - AmiriQuran @ 58, AmiriBold @ 46, AmiriQuran @ 64
- **RAQM**: Used for both layouts for proper Arabic shaping (ligatures, diacritic positioning, waqf mark combining)

---

## Rendering Pipeline

```
Data Fetch → Element Building → PangoCairo Layout → Page Rendering → Duration Calc → Video Encode
```

### Stage 1: Data Fetch

- **Surah**: `fetch_surah(n)` from `quran.json`, computes global ayah numbers
- **Juz**: `fetch_juz(n)` from API (with local cache)
- **Verse**: surah mode with a verse slice

### Stage 2: Element Building

**Functions**: `build_elements_from_surah()` / `build_elements_from_juz()` (in `render.py`)

Output: list of element tuples:

```
("surah_header",  name_ar,  name_en)
("basmalah",)                             # Not added for Surah 9
("verse",         text,     display_num, global_num)
("juz_footer",    juz_num,  last_ayah_in_surah, surah_name, surah_num)
```

Processing:
1. Strip BOM (`\ufeff`)
2. `normalize_arabic(text)` — universal character mapping (Farsi yeh, hair space, word joiner); all waqf marks preserved
3. If verse 1 has basmalah: `strip_bismillah()` removes first 4 words
4. If text is empty after stripping: skip verse
5. Surah 9 (At-Tawbah) always skips the `("basmalah",)` element

### Stage 3: PangoCairo Layout (`layout_engine.py`)

**Class**: `LayoutEngine`

The `LayoutEngine` replaces manual word-splitting + `getbbox()` measurement with native Pango text layout:

1. _build_text_stream(): Build a single text string from all verse words + markers, with Pango attributes for verse marker colouring
2. _pango_layout(): Feed text through PangoLayout with `set_justify(True)` for Kashida-based Arabic justification, `set_wrap(WORD)` for line breaking
3. Track word positions (char_start/char_end) to map Pango line ranges back to individual words and their waqf overlays
4. _layout_items(): Position surah headers, basmalahs, text lines, and footer at absolute Y coordinates
5. _paginate(): Split layout items into 1920×1080 Page objects for O(1) memory rendering

**Key improvement**: Pango's `set_justify(True)` inserts Kashida (U+0640 Tatweel) stretches at valid Arabic word-joining points. This produces typographically correct Arabic justification instead of the previous approach of widening inter-word spaces.

**Data structures**:

```python
@dataclass WordSlot:    text, text_clean, mushaf_letters, is_marker, char_start, char_end
```

Note: `char_start` and `char_end` are **UTF-8 byte offsets** into the Pango text buffer (Pango uses byte offsets internally for indices). Using character offsets would cause misalignment between word tracking and Pango line positions, since Arabic characters are 2 bytes in UTF-8.
@dataclass TextLine:    words, y, is_verse_last (True only for the very last line of a batch)
@dataclass HeaderItem:  y, height, name_ar, name_en, layout
@dataclass BasmalahItem: y, height
@dataclass FooterItem:  y, height, juz_num, last_ayah, surah_name, surah_num
@dataclass Page:        index, scroll_y, headers, basmalahs, text_lines, footer
```

### Stage 4: Page Rendering (`render.py` + `drawing.py`)

**Function**: `render_pages(pages, total_height, layout_mode)`

Each page is rendered independently as a 1920×1080 `cairo.ImageSurface`:

1. Paint background colour
2. Draw ornamental border lines (first/last page)
3. Draw surah headers via `PangoCairo.show_layout()`
4. Draw basmalah via `PangoCairo.show_layout()`
5. Draw text lines with Kashida justification via `PangoCairo.show_layout()` using `text_clean` (waqf marks stripped — only Mushaf overlays appear above)
6. Draw waqf Mushaf letters above words using `PangoLayout.index_to_pos()` on the marked-text layout (correct GPOS positions)
7. Draw ruled lines between text lines
8. Draw juz footer
9. Convert `cairo.ImageSurface` → numpy array (BGRA → RGB swap)

**Key improvement**: Each page is rendered independently (O(1) memory), instead of one massive tall image. Pages overlap by 4px for smooth scrolling transitions.

**Vertical offset**: Pango's ink rectangle has an offset from the logical origin (`ink.y`). All drawing functions use `_show_layout_at()` which adjusts by subtracting `ink.y` to place visible text at the exact desired position. Callers use `ink.height` for vertical centring within `line_h`.

### Stage 5: Duration Calculation

```python
# Juz: fixed default or user-specified
if duration is None:
    duration = DEFAULT_JUZ_DURATION  # 1800 s (30 min)

# Surah / verse range: derived proportionally from juz default
num_verses = count_verses(elements)
duration = num_verses * (DEFAULT_JUZ_DURATION / AVG_AYAHS_PER_JUZ)

DEFAULT_JUZ_DURATION = 30 * 60   # 1800 s
AVG_AYAHS_PER_JUZ = 6236 / 30    # ≈ 207.87
```

Duration controls the number of frames (`num_frames = duration * FPS`). Scroll speed is uniform across all content (`step = scroll_range / num_frames`). More text → more pages to scroll through → higher `scroll_range` → faster pixel scroll rate to fit the fixed duration.

Per-ayah MP3 timing (`timing.py`) is preserved but not invoked by default. Use `--duration` to set a fixed total duration instead.

### Stage 6: Video Encoding (`encode.py`)

**Functions**:

- `encode_video(page_arrays, output_path, num_frames, scroll_range, progress, workers, hang_timeout)` — top-level entry point. Defaults to serial mode for reliability.
- `_encode_serial(...)` — single ffmpeg process with custom OS pipe (1 MiB buffer), stderr parsing for real progress, hang detection watchdog
- `_encode_parallel(...)` — splits frames into worker chunks, each encodes to a temp MP4 segment, then concat. Progress via output file size polling.
- `_worker_encode(...)` — runs in child process via `multiprocessing.Process`; each worker gets its own large-buffer pipe
- `_concat_parts(part_paths, output_path)` — ffmpeg concat demuxer (no re-encode)
- `_get_frame(sorted_pages, scroll_y)` — extract a 1080px slice from pre-rendered pages
- `encoded_ms_from_bytes(total_bytes, total_duration_ms, min_ratio)` — heuristic that maps MP4 file size to approximate encoded video milliseconds (used for parallel-mode progress only)

**Page-based frame generation**:
- `page_arrays`: list of `(scroll_y, numpy_array)` tuples, one per 1920×1080 page
- For each frame, calculate the virtual scroll position `y = int(frame_index × step)`
- Binary-search the sorted pages to find the page covering that `y` range
- Extract a 1080-pixel-tall slice from the page array
- Write raw RGB24 bytes via `os.write(fd, buf)` through a custom OS pipe

**Key design improvements** (vs earlier attempts):

| Problem | Previous Approach | New Solution |
|---|---|---|
| Pipe write blocks | `subprocess.PIPE` (64 KiB OS buffer) | `os.pipe()` + `fcntl.F_SETPIPE_SZ` → 1 MiB buffer (16× larger) |
| CPU underutilisation | `-threads 2` fixed per ffmpeg | Serial: `-threads 0` (auto, all cores); Parallel: `cpu_count // workers` threads each |
| Stderr deadlock | No reader thread in early attempts | Dedicated stderr reader thread per ffmpeg process, reads `out_time_ms=` lines |
| Parallel progress race | `multiprocessing.Manager().Value/dict()` with locks | Parallel progress via polling output MP4 file sizes on disk (no IPC) |
| No hang detection | Process hangs silently | Watchdog thread monitors `encoded_ms` changes; warns at 30 s, kills ffmpeg at 120 s |
| Inaccurate ETA | Frames-sent ≠ frames-encoded | ETA calculated from ffmpeg's `out_time_ms=` value (real encoder output time) |

**Serial encoding** (default, `--workers 1`):
1. Create OS pipe with 1 MiB kernel buffer via `os.pipe()` + `fcntl.F_SETPIPE_SZ`
2. Launch ffmpeg with `-threads 0` (auto-detect all CPU cores), `-progress pipe:2`, `-loglevel error`
3. Stderr reader thread parses `out_time_ms=` lines for real encoding progress (milliseconds of video encoded)
4. Watchdog thread polls `encoded_ms` every 5 s; warns at 30 s stall, kills ffmpeg at 120 s
5. Main loop writes each frame via `os.write(w_fd, buf)` — rarely blocks due to 1 MiB buffer
6. Progress report every 5 s of video: percentage, elapsed, ETA, fps
7. Close write end, wait for ffmpeg, report final stats

**Parallel encoding** (when `--workers N` with N > 1):
1. Split `num_frames` into N roughly equal chunks
2. Launch N `multiprocessing.Process` instances, each running `_worker_encode()`
3. Each worker: own OS pipe with 1 MiB buffer, own ffmpeg instance, `-threads cpu_count/N`
4. Page arrays passed as args (pickled) — the old `_GLOBAL_SORTED_PAGES` fork-COW approach is removed for simplicity
5. Main process polls output MP4 file sizes every second for approximate progress (mapped to encoded ms via `encoded_ms_from_bytes` heuristic)
6. After all workers finish, concatenate segments via ffmpeg concat demuxer (`-c copy`)
7. Clean up temp `.tmp_*` segment files

**Encoding settings**:
- Preset `veryfast`, CRF 23 — good visual quality for 50" TV display, compact file size (~80 MB per 30 min juz), fast encoding (~5 min per juz on 12-core CPU)
- All output uses `-movflags +faststart` for streaming-friendly MP4

**Hang detection**:
- Configurable via `--hang-timeout SEC` CLI flag (default: 120 s, 0 = disable)
- Watchdog thread checks every 5 s if `encoded_ms` has changed since last check
- 30 s with no progress → prints WARNING to stderr
- `hang_timeout` seconds with no progress → kills ffmpeg process, prints error

---

## Layout Details

### Centered Layout

| Constant | Value |
|---|---|
| `MARGIN_X` | 200 px |
| Max text width | 1520 px |
| `LINE_H_CENTERED` | 150 px |
| Header height | 200 px (36+28+46+12+26+16+36) |
| Basmalah height | 120 px (`64+20+36`) |
| `TOP_PAD` | 180 px |
| `BOT_PAD` | 1080 px |
| Verse marker style | `"arabic_indicate"` — U+06DD (۝) + Arabic-Indic numeral |
| Verse gap | 0 (words flow continuously) |
| Font | AmiriQuran via Pango (same as justified) |

Line rendering via PangoLayout: `set_justify(True)` for all lines except the very last line of content; last line uses `set_alignment(CENTER)` with `width_px=text_width` (constrained to margins, not natural width).

### Justified Layout

| Constant | Value |
|---|---|
| `MARGIN_X_JUSTIFIED` | 144 px (7.5% of 1920) |
| `TEXT_WIDTH_JUSTIFIED` | 1632 px |
| `LINE_H_JUSTIFIED` | 150 px |
| Header height | 156 px (2×35+46+40) |
| Basmalah height | 120 px (`64+20+36`) |
| `TOP_PAD` | 180 px |
| `BOT_PAD` | 1080 px |
| Verse marker style | `"arabic_indicate"` — U+06DD (۝) + Arabic-Indic numeral |
| Header | Arabic-only (no English) |

Line rendering via PangoLayout: `set_justify(True)` for all except last line; `set_justify(False)` for last line.

### Surah Block Grouping

Both layouts group elements by surah:
1. New `surah_header` → finalize previous block, start new one
2. Block = `[header, basmalah, all following verse words until next header]`
3. Ensures headers interleave properly with their verses when a juz spans multiple surahs

---

## Drawing Functions (`drawing.py`)

All drawing uses Cairo (vector graphics) and PangoCairo (text layout).

### `_show_layout_at(cr, layout, x, y, v_center_height=None)`

Renders a PangoLayout at position `(x, y)`. Automatically adjusts for Pango's logical-to-ink offset by subtracting `ink.y` (not `logical.y` — this ensures visible text is placed at the exact desired position). If `v_center_height` is provided, the ink is vertically centred within that height.

### `draw_ornament_line(cr, y, width, color, thickness=1, length=250)`

Horizontal ornament: left dash, centre diamond, right dash. Same visual as before, drawn with Cairo paths instead of PIL.

### `draw_surah_header_centered(cr, y, name_ar, name_en, fd_ar, fd_en)`

1. Ornament line (GOLD, thickness 2)
2. y + 28 → Arabic name centred (GOLD), rendered via PangoLayout
3. +44 +12 → English name centred (DARK_GOLD), rendered via PangoLayout
4. +26 +16 → Ornament line (GOLD, thickness 2)

### `draw_surah_header_justified(cr, y, name_ar, fd_ar)`

1. Ornament line (GOLD, thickness 2)
2. Arabic name centred (GOLD) with 35px padding
3. Ornament line below (GOLD, thickness 2)

### `draw_basmalah(cr, y, layout, basmalah_font_desc)`

- Text: `بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ` (hardcoded)
- Centred, BASMALAH_COLOR, PangoLayout with font_desc
- Ornament line 20px below text bottom (GOLD, thickness 2)

### `draw_text_line(cr, line_words, y, is_verse_last, layout_mode, line_h, quran_fd)`

Renders one line of Quran text using PangoCairo. Key features:

- **Kashida justification**: Non-last lines use `PangoLayout.set_justify(True)` for Kashida stretching
- **RTL**: `set_auto_dir(True)` handles right-to-left directionality automatically
- **Verse marker colouring**: Pango `attr_foreground_new()` attributes colour verse markers (۝+numeral) in VERSE_MARKER_COLOR
- **Centred last line**: In "centered" mode, only the very last line of the entire content uses `Pango.Alignment.CENTER` with `width_px=text_width` (constrained to margins). All other lines are Kashida-justified.
- **Vertical centring**: Text ink is centred vertically within `line_h` using Pango ink extents (`ink.height`, `ink.y`)
- **Line width constraint**: All lines (including centred last lines) are constrained to `text_width` (1520 or 1632 px)

### `draw_line_rule(cr, y, layout_mode)`

Horizontal rule between text lines (LINE_RULE_COLOR, 2px width). Margin x varies by layout.

### `draw_juz_footer(cr, y, juz_num, last_ayah_in_surah, surah_name, surah_num, fd_footer)`

Format: `Juz N — Verse M — Surah Name (N)` (U+2014 em-dash separators). Ornament lines above and below.

---

## Text Processing (`text.py`)

### Verse dataclass

```python
@dataclass
class Verse:
    """Immutable representation of a single Quranic verse."""
    text: str              # cleaned text (normalized, basmalah stripped)
    number: int            # global ayah number (1-6236)
    number_in_surah: int   # verse number within its surah (1-N)
```

Element builders (`build_elements_from_surah` / `build_elements_from_juz`) now use `Verse` instances for verse elements instead of unnamed tuples. Non-verse elements remain as tuples: `("surah_header", name_ar, name_en)`, `("basmalah",)`, `("juz_footer", ...)`.

### Constants

```python
BASMALAH_WORD     = "بِسْمِ"          # Basmalah first word for detection
AYAH_MARKER_CHAR  = "\u06DD"          # ۝
VERSE_MARKER_OPEN = "\uFD3F"          # ﴿
VERSE_MARKER_CLOSE= "\uFD3E"          # ﴾
```

### `ARABIC_NORMALIZE_MAP` — Formatting character substitutions

Only formatting-level mappings (not waqf marks):

| From | Code | To | Code | Reason |
|---|---|---|---|---|
| Superscript alif (tatweel) | U+0670+U+0640 | Alif + tatweel | U+0622+U+0640 | ـٰ → ـآ (visible alif) |
| Superscript alif (standalone) | U+0670 | Madda alif | U+0622 | ٰ → آ (visible alif) |
| Farsi yeh | U+06CC | Arabic yeh | U+064A | No Farsi glyph in AmiriQuran |
| Hair space | U+200A | Regular space | U+0020 | Spacing normalize |
| Word joiner | U+2060 | (removed) | — | Invisible, remove |
| Open fathatan | U+08F0 | Fathatan | U+064B | Open → closed tanween (API data) |
| Open dammatan | U+08F1 | Dammatan | U+064C | Open → closed tanween (API data) |
| Open kasratan | U+08F2 | Kasratan | U+064D | Open → closed tanween (API data) |

### `WAQF_MUSHAF_MAP` — Waqf mark reference (kept for compatibility)

Each waqf Unicode code point maps to a traditional Mushaf indicator letter (م ص ق ج س ط ز ن و ي). Waqf marks are **no longer stripped from text** during rendering — they remain in the string so RAQM/HarfBuzz can position them via GPOS anchor tables (`+mark`, `+mkmk`, `+ccmp`). The native Unicode marks render directly as combining glyphs above their base characters. The Mushaf letter overlay system has been removed in favor of native font rendering, which is cleaner and avoids double-rendering artifacts.

| Code | Unicode name | Mushaf letter | Meaning |
|---|---|---|---|
| U+06D6 | Sad-lam-alef (ۖ) | صلي | Wasl awla (continuing preferred) |
| U+06D7 | Qaf-lam-alef (ۗ) | قلي | Stopping preferred |
| U+06D8 | Meem initial (ۘ) | طم | Preferred stop with concession |
| U+06DA | Jeem (ۚ) | ج | Ja'iz (permissible stop) |
| U+06DB | Three dots (ۛ) | ز | Mushtarak |
| U+06DC | Seen (ۜ) | صل | Permissible to continue |
| U+06DF | Rounded zero (۟) | م | Waqf lazim (must stop) |
| U+06E2 | Meem isolated (ۢ) | م | Waqf lazim |
| U+06E4 | Madda (ۤ) | ط | Waqf mutlaq (absolute pause) |
| U+06E5 | Small waw (ۥ) | و | Waw pronunciation |
| U+06E6 | Small yeh (ۦ) | ي | Yeh pronunciation |
| U+06E7 | Small high yeh (ۧ) | ج | Ja'iz |
| U+06E8 | Small high noon (ۨ) | ن | Waqf noon |
| U+06EC | Rounded high stop (۬) | م | Waqf lazim |
| U+06ED | Low meem (ۭ) | م | Iqlab / waqf lazim |

Characters NOT in WAQF_MUSHAF_MAP (kept in-text and NOT extracted to Mushaf letters):
- U+06E1 (dotless khah ۡ) — hamzat al-wasl, not a waqf mark (sukun indicator)
- U+06E0 (upright rectangular zero ۠) — silent alif marker, orthographic (not a stop mark)
- U+06DE (rub el hizb ۞) — standalone section marker
- U+06E9 (sajdah ۩) — standalone prostration marker

### `_is_waqf_word(w)` — Detect standalone WAQF marks

Returns True if all chars are:
- Unicode category `Mn`, `Lm`, or `So` (includes rub el hizb ۞ U+06DE and sajdah ۩ U+06E9)
- AND char ≥ U+0600 (Arabic block) OR char == U+0640 (tatweel/kashida)

The `So` category was added to recognize rub el hizb (U+06DE) and place of sajdah (U+06E9) as attachable waqf marks.

### `attach_waqf_marks(words)` — Merge WAQF symbols with preceding word

If current word is a WAQF mark → concatenate to previous word.  
This lets RAQM render WAQF symbols above their host word.

### `strip_bismillah(text)` — Remove basmalah from verse 1

1. Replace U+06E1 (dotless khah sukun) with U+0652 (standard sukun) in first word
2. If first word matches `BASMALAH_WORD` AND ≥ 5 words total → return `words[4:]`
3. Otherwise return unchanged

### `make_verse_marker(vnum, style)` — Verse number formatting

| Style | Pattern | Example |
|---|---|---|
| `"ornate"` | `﴿NUM﴾` | ﴿١﴾ |
| `"arabic_indicate"` | `۝NUM` | ۝١ (default) |
| default | `⟫NUM⟪` | ⟫١⟪ |

Currently used: `"arabic_indicate"` in both layouts.

### `is_arabic_digit(c)` — Utility: check for U+0660-U+0669

### `is_verse_marker(word)` — Utility: detect standalone Arabic numeral marker

Both `is_arabic_digit` and `is_verse_marker` are kept for backward compatibility but are not used by the current PangoCairo pipeline (the layout engine uses WordSlot.is_marker instead).

---

## Layout Engine (`layout_engine.py`)

### Overview

`LayoutEngine` replaces the manual word-splitting and `getbbox()` measurement approach with Pango-based text layout. It processes verse elements into a list of `Page` objects, each containing headers, basmalahs, text lines, and footer items positioned at absolute Y coordinates.

### Key Methods

| Method | Description |
|---|---|
| `layout_pages(elements)` | Main entry: elements → `(pages, total_height)` |
| `_layout_items(elements)` | Walk elements, flush verse batches through Pango |
| `_pango_layout(verse_texts, verse_vnums)` | Create PangoLayout for a batch of verses, extract TextLines |
| `_build_text_with_tracking(verse_texts, verse_vnums)` | Build Pango text + attribute list + WordSlot tracking |
| `_paginate(items)` | Split layout items into 1920×1080 Page windows (4px overlap) |

### Data Flow

```
Elements → _layout_items() → [HeaderItem, BasmalahItem, TextLine, FooterItem]
                                   ↓
                       _pango_layout() ← PangoLayout (Kashida justification)
                                   ↓
                       _paginate() → [Page(scroll_y, headers, basmalahs, text_lines, footer)]
```

### PangoLayout Configuration

```python
layout.set_font_description(fd_quran)    # Amiri Quran at 58pt (centered) or 64pt (justified)
layout.set_width(Pango.units_from_double(text_width))  # 1520 (centered) or 1632 (justified)
layout.set_wrap(Pango.WrapMode.WORD)      # Word-boundary wrapping
layout.set_justify(True)                   # Kashida-based Arabic justification
layout.set_alignment(Pango.Alignment.LEFT) # Flush-start for RTL
layout.set_auto_dir(True)                 # Automatic RTL detection
```

For the very last line in centered mode: `set_justify(False)`, `set_alignment(CENTER)`, `width_px=text_width` (constrained to margins).

### Phantom Line Filtering

Phantom Pango lines are filtered by checking `pango_line.start_index >= text_byte_len` where `text_byte_len = len(text.encode("utf-8"))`.

### Word Position Tracking

`_build_text_with_tracking()` builds a flat text string from all verse words + markers, with:
- `PangoAttrList` for verse marker colouring (VERSE_MARKER_COLOR attributes)
- `WordSlot` objects tracking `char_start`/`char_end` positions as **UTF-8 byte offsets** in the text buffer
- Mushaf waqf letters per word for overlay rendering

When mapping PangoLayoutLine byte ranges back to WordSlots, the check `ws.char_start >= line_start AND ws.char_start < line_end` ensures each word belongs to exactly one line. Both Pango line indices and WordSlot positions use UTF-8 byte offsets.

---

## Font & Rendering

### PangoCairo Text Stack

All text rendering uses Pango + Cairo via PyGObject:

- **HarfBuzz** (underneath Pango): shapes Arabic text, applies contextual ligatures, handles mark-to-base positioning for diacritics
- **Pango**: line breaking, word wrapping, **Kashida-based Arabic justification** (`set_justify(True)`), RTL directionality (`set_auto_dir(True)`)
- **Cairo**: rasterizes PangoLayouts to `ImageSurface`, draws ornamental lines and shapes

The previous Pillow + RAQM approach required manual word-by-word `getbbox()` measurement and inter-word gap calculation. Pango handles all of this natively with typographically correct Kashida stretching.

### Kashida Justification

When `PangoLayout.set_justify(True)` is enabled, Pango inserts Kashida (U+0640 Tatweel) characters at valid Arabic word-joining points to stretch lines to the full available width. This replaces the previous `gap = (max_w - total_w) / (num_words - 1)` space-widening approach, which is typographically incorrect for Arabic.

### Font Loading

Fonts are loaded via Pango `FontDescription` string (e.g. `"Amiri Quran 58"`) rather than file path. Pango uses Fontconfig to locate font files. The system must have Amiri fonts installed and discoverable via `fc-list`.

| Role | Pango family | Size | Purpose |
|---|---|---|---|
| Quran text | `Amiri Quran` | 58 / 64 | Both layouts: Quranic verse text + Basmalah |
| Arabic headers | `Amiri Bold` | 46 / 46 | Surah name headers |
| Footer text | `Amiri` | 26 | Juz footer English text |
| Waqf indicators | `Amiri Bold` | 24 | Mushaf letter waqf markers (overlay above text) |

### Waqf Mark Rendering

Waqf marks are kept in the text during Pango shaping so RAQM/HarfBuzz positions them via GPOS `mark`, `mkmk`, `+ccmp` features (`Pango.AttrFontFeatures`). This binds each combining mark to its base glyph at the shaper level.

**Dual rendering eliminated**: `draw_text_line()` renders clean text (`WordSlot.text_clean` — waqf marks stripped) so the main text shows no native waqf glyphs. `draw_waqf_overlays()` uses the marked-text layout (`WordSlot.text` — marks included) for `index_to_pos()` positioning, drawing Mushaf indicator letters above. One rendering path per codepoint: extract to Mushaf letter, never render both the native glyph and the overlay.

**Positioning**: `base_x` MUST NOT include `log.x` from `get_pixel_extents()`. For RTL left-aligned text, `log.x` is NOT 0 — Pango includes the text's left-edge offset in the logical extent x-coordinate (~1159px for typical justified lines). Since `index_to_pos()` already returns positions in layout coordinates that account for alignment, adding `log.x` double-counts the offset, shifting all waqf markers far to the right (often off-screen past `WIDTH`=1920). The correct conversion is simply `base_x = WIDTH - margin_x - text_width` (the layout origin x).

Mark -> Mushaf letter mapping uses `WAQF_MUSHAF_MAP` in `text.py`. Key corrections:
- **U+06DC** (ARABIC SMALL HIGH SEEN ۜ): "صل" → **"س"** (seen = saktah/brief pause)
- **U+06D8** (ARABIC SMALL HIGH MEEM INITIAL FORM ۘ): "طم" → **"م"** (meem = waqf lazim)

### Full Waqf Mark Inventory in `quran.json`

| Character | Code | Count | Category | Mushaf letter |
|---|---|---|---|---|
| Small high dotless head of khah | U+06E1 | 37,147 | Mn | (kept in-text, not a waqf mark) |
| Small high jeem | U+06DA | 2,083 | Mn | ج |
| Small high ligature sad-lam-alef | U+06D6 | 1,651 | Mn | ص |
| Tatweel | U+0640 | 1,652 | Lm | (not a waqf mark) |
| Small waw | U+06E5 | 1,256 | Lm | و |
| Small yeh | U+06E6 | 958 | Lm | ي |
| Small high ligature qaf-lam-alef | U+06D7 | 511 | Mn | ق |
| Small high meem isolated | U+06E2 | 510 | Mn | م |
| Start of rub el hizb | U+06DE | 199 | So | (kept in-text) |
| Small high madda | U+06E4 | 184 | Mn | ط |
| Small low meem | U+06ED | 99 | Mn | م |
| Small high upright rect zero | U+06E0 | 66 | Mn | م |
| Small high yeh | U+06E7 | 38 | Mn | ج |
| Small high madda | U+06E4 | 26 | Mn | ط |
| Small high meem initial | U+06D8 | 21 | Mn | م |
| Place of sajdah | U+06E9 | 15 | So | (kept in-text) |
| Small high seen | U+06DC | 8 | Mn | س |
| Small high three dots | U+06DB | 6 | Mn | ز |
| Rounded high stop filled | U+06EC | 2 | Mn | م |

---

## Color Scheme

| Constant | RGB | Visual | Used For |
|---|---|---|---|
| `BG_COLOR_CENTERED` / `BG_COLOR_JUSTIFIED` | (12, 8, 20) | Very dark purple-black | Background |
| `TEXT_COLOR` | (235, 230, 215) | Warm off-white | Quranic verse text |
| `GOLD` | (200, 160, 60) | Rich gold | Header lines, ornaments, footer |
| `DARK_GOLD` | (100, 75, 25) | Muted dark gold | English surah name, page borders |
| `BASMALAH_COLOR` | (220, 190, 100) | Light gold-yellow | Basmalah text |
| `VERSE_MARKER_COLOR` | (180, 145, 65) | Medium gold | Verse number markers |
| `LINE_RULE_COLOR` | (40, 35, 55) | Subtle purple-gray | Inter-line ruled lines |

---

## Dimension Constants

| Constant | Value | Description |
|---|---|---|
| `WIDTH` | 1920 | Video width (Full HD) |
| `HEIGHT` | 1080 | Video height (Full HD) |
| `FPS` | 24 | Frames per second |
| `RATE_2X` | 2.0 | Scroll speed multiplier (2× recitation) |
| `DEFAULT_JUZ_DURATION` | 1800 (30 min) | Default juz video duration in seconds |
| `AVG_AYAHS_PER_JUZ` | 207.87 | Average ayahs per juz (6236/30) — used for proportional surah duration |

---

## Git Branches

| Branch | Description |
|---|---|
| `main` | Initial — `generate_videos.py`, raw Noto fonts, basic wrap |
| `milestone1_separators` | Separator lines between verses, centered, KFGQPC |
| `milestone2_fullwidth` | Full-width separators, equal padding, diamond ornament |
| `milestone3_bold` | Bold 3 px separators, diamond ornament |
| `milestone4_ruled` | Ruled layout — lines between every text line, justified |
| `milestone4_waqf_fixed` | Waqf preservation, module refactor, two layouts, juz/surah CLI, local quran.json, normalization |
| **`milestone5_pango_cairo`** | **Active** — PangoCairo stack: Kashida justification, page-based rendering, O(1) memory |

## Commit History (current branch)

| Hash | Description |
|---|---|---|
| *(current)* | Removed `--quick` mode (ultrafast produced bloated files). Default is veryfast + CRF 23 (~81 MB per 30 min juz, ~5 min encode). Encoding overhaul: custom OS pipe with 1 MiB buffer (F_SETPIPE_SZ), `--threads 0` for full CPU utilisation, stderr reader thread per ffmpeg, hang detection watchdog (warn at 30s, abort at 120s), parallel progress via MP4 file size polling (no shared memory IPC), `--hang-timeout` CLI flag, removed fragile Manager.Value/dict IPC |
| *(current)* | Duration parameter: `--duration` flag (e.g. `30m`, `1h30m`), juz default 30 min, surah duration derived proportionally from juz via `AVG_AYAHS_PER_JUZ`; removed per-ayah MP3 timing trigger from default flow |
| *(current)* | Milestone 5: PangoCairo refactor — Kashida justification, Cairo drawing, page-based rendering, streaming FFmpeg encode |
| *(current)* | Bug fixes: UTF-8 byte offsets in word tracking, ink-based vertical centering, constrained last-line width, proper is_verse_last for continuous flow |
| *(current)* | Waqf positioning fix: keep waqf marks in Pango text during shaping; enable `+mark` `+mkmk` `+ccmp` OpenType features; eliminated dual rendering — clean text in draw_text_line, marks-only in overlay positioning |
| *(current)* | Waqf mapping fix: corrected U+06DC (seen) "صل"→"س" and U+06D8 (meem initial) "طم"→"م" in WAQF_MUSHAF_MAP |
| *(current)* | Waqf overlay byte-tracking fix: `byte_next = byte_pos + w_bytes` (without +1) so word extent excludes trailing space; `byte_pos = byte_next + 1` to skip space for next word. Previously `byte_next` included the space, centering waqf letters over word+space instead of just the word — a 12+ px error in justified text. Matches `_build_line_attrs` pattern. |
| *(current)* | Footer hold: 3-second static hold at end of juz videos — `scroll_range` capped at last rendered page's `scroll_y` so footer stays visible during extra `3*FPS` hold frames |

---

## Edge Cases & Known Issues

### Handled

1. **Surah 9 (At-Tawbah)** — No basmalah rendered (checked in both element builders)
2. **Basmalah embedded in verse 1** — Detected by normalized word match (handles U+06E1 sukun variant), stripped after header rendering. Verses that are entirely the basmalah (4 words, e.g. Surah 1 verse 1) are correctly skipped.
3. **Sukun variant (U+06E1)** — Normalized to U+0652 before basmalah comparison
4. **Pango ink offset** — `_show_layout_at()` uses `ink.y` (not `logical.y`) to place visible text at the exact desired position. Callers use `ink.height` for vertical centring.
5. **Empty verse after basmalah strip** — Skipped
6. **Waqf marks** — Keep marks in text for GPOS shaping; clean text rendered separately; Mushaf overlays positioned from shaped layout; dual rendering eliminated via `text_clean`/`text` split per WordSlot; `base_x` must not include `log.x` (Pango already accounts for alignment in `index_to_pos()` return values — `log.x` for RTL left-aligned text is non-zero, typically 600–1200 px, and would double-count the alignment offset)
7. **Farsi yeh / hair space / word joiner / open tanween** — Normalized via `ARABIC_NORMALIZE_MAP`
8. **BOM character** — Stripped from all verse text
9. **WAQF detection** — Uses Unicode categories `Mn`, `Lm`, and `So` (for rub el hizb and sajdah), requires Arabic block range
10. **Last line rendering** — In centered mode, only the very last line of the content uses `set_alignment(CENTER)` with `width_px=text_width` (constrained). All other lines are Kashida-justified. The `is_verse_last` flag is True only on the final TextLine, not on every line containing a verse marker.
11. **Multi-surah juz footer** — Shows in-surah verse number, not global
12. **Phantom Pango lines** — Pango sometimes creates extra empty lines with `set_justify(True)`; filtered by checking `start_index >= text_byte_len` where `text_byte_len = len(text.encode("utf-8"))`
13. **UTF-8 byte offsets** — `_build_text_with_tracking()` and WordSlot positions use UTF-8 byte offsets (not character positions) because Pango's line indices and attribute positions are byte-based. Arabic characters are 2+ bytes in UTF-8, so character and byte positions differ.
14. **Page-based rendering** — Each page rendered independently, O(1) memory regardless of content length
15. **Kashida justification** — Pango's native Arabic justification via `set_justify(True)` inserts Tatweel stretches at valid connection points

### Limitations

1. **No audio output** — Videos are silent; durations only control scroll speed
2. **Partial timing data** — Only 148 entries cached; full download of 6236 MP3s takes hours
3. **Speed via duration, not rate** — User controls total duration; scroll speed derived from content height ÷ duration. No separate `--rate` flag.
4. **Output directory fixed** — Always `output/` under project root
5. **API vs local data differences** — The alquran.cloud API includes U+06DF (rounded zero), U+08F0–U+08F2 (open tanween), and other chars not present in quran.json. `ARABIC_NORMALIZE_MAP` handles open tanween; waqf marks are handled natively by the font via GPOS
6. **No verse highlighting** — Linear scroll, not synced to individual verses
7. **Legacy `generate_chapter.py`** — Not integrated with the module; no WAQF handling
8. ~~**No progress ETA**~~ — Resolved: encoding progress now shows percentage, elapsed, ETA, and fps parsed from ffmpeg stderr
9. **Font dependency** — Requires Amiri Quran and Amiri fonts installed and discoverable by Fontconfig (`fc-list`)
