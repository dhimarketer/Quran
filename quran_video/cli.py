#!/usr/bin/env python3
import argparse
import os
import re
import sys
import time

from .config import WIDTH, HEIGHT, FPS, OUTPUT_DIR, DEFAULT_JUZ_DURATION, AVG_AYAHS_PER_JUZ
from .api import fetch_surah, fetch_juz
from .render import render, load_fonts, build_elements_from_surah, build_elements_from_juz
from .encode import encode_video, estimate_encode_time, _fmt_duration
from .text import Verse


def parse_duration(s):
    """Parse a duration string like '30m', '1h30m', '1800' into seconds."""
    if isinstance(s, (int, float)):
        return float(s)
    s = s.strip().lower()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    total = 0.0
    h_match = re.search(r'(\d+)\s*h', s)
    if h_match:
        total += int(h_match.group(1)) * 3600
    m_match = re.search(r'(\d+)\s*m', s)
    if m_match:
        total += int(m_match.group(1)) * 60
    s_match = re.search(r'(\d+(?:\.\d+)?)\s*s(?:ec)?', s)
    if s_match:
        total += float(s_match.group(1))
    if total > 0:
        return total
    raise ValueError(f"Cannot parse duration: {s}")


def count_verses(elements):
    """Count the number of Verse instances in elements list."""
    return sum(1 for elem in elements if isinstance(elem, Verse))


def generate_surah_video(surah_num, layout, ayahs_range=None, output_name=None,
                         duration=None, workers=None, hang_timeout=None):
    surah = fetch_surah(surah_num)
    fonts = load_fonts(layout)
    elements = build_elements_from_surah(surah, ayahs_slice=ayahs_range)

    page_arrays, total_height = render(elements, layout=layout, fonts=fonts)

    if duration is None:
        num_verses = count_verses(elements)
        duration = num_verses * (DEFAULT_JUZ_DURATION / AVG_AYAHS_PER_JUZ)

    num_frames = int(duration * FPS)
    scroll_range = total_height - HEIGHT

    print(f"  Surah {surah_num}: {total_height}px, {len(page_arrays)} pages, "
          f"{duration:.0f}s ({duration/60:.1f}min)")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if output_name is None:
        suffix = f"_{layout}"
        if ayahs_range:
            suffix += f"_{ayahs_range.start+1}-{ayahs_range.stop}"
        output_name = f"surah_{surah_num}{suffix}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_name)

    est = estimate_encode_time(num_frames, workers)
    print(f"  Encoding ~{num_frames} frames (estimated: {_fmt_duration(est)})")

    t0 = time.time()
    ok = encode_video(page_arrays, output_path, num_frames, scroll_range,
                      workers=workers,
                      hang_timeout=hang_timeout if hang_timeout is not None else 120)
    elapsed = time.time() - t0
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Done: {output_path} ({size_mb:.1f} MB) [took {_fmt_duration(elapsed)}]")
    return output_path


def generate_juz_video(juz_num, layout="centered", duration=None, workers=None,
                       hang_timeout=None):
    juz_data = fetch_juz(juz_num)
    fonts = load_fonts(layout)
    elements = build_elements_from_juz(juz_data)

    page_arrays, total_height = render(elements, layout=layout, fonts=fonts)

    if duration is None:
        duration = DEFAULT_JUZ_DURATION

    FOOTER_PAD_S = 3
    num_frames = int(duration * FPS) + int(FOOTER_PAD_S * FPS)
    last_page_scroll = max(p[0] for p in page_arrays) if page_arrays else 0
    scroll_range = max(0, last_page_scroll)

    print(f"  Juz {juz_num}: {total_height}px, {len(page_arrays)} pages, "
          f"{duration:.0f}s (+{FOOTER_PAD_S}s footer hold) "
          f"({(duration+FOOTER_PAD_S)/60:.1f}min)")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"juz_{juz_num:02d}.mp4")

    est = estimate_encode_time(num_frames, workers)
    print(f"  Encoding ~{num_frames} frames (estimated: {_fmt_duration(est)})")

    t0 = time.time()
    ok = encode_video(page_arrays, output_path, num_frames, scroll_range,
                      workers=workers,
                      hang_timeout=hang_timeout if hang_timeout is not None else 120)
    elapsed = time.time() - t0
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Done: {output_path} ({size_mb:.1f} MB) [took {_fmt_duration(elapsed)}]")
    return output_path


def parse_verse_arg(verse_str):
    verse_str = verse_str.strip()
    if ":" in verse_str:
        chapter, verses = verse_str.split(":", 1)
        chapter = int(chapter)
        if "-" in verses:
            start, end = verses.split("-", 1)
            return chapter, int(start), int(end)
        return chapter, int(verses), int(verses)
    raise ValueError(f"Invalid verse format: {verse_str}. Use CHAPTER:VERSE or CHAPTER:START-END (e.g. 34:1-30)")


def main():
    parser = argparse.ArgumentParser(description="Generate scrolling HD Quran videos")
    parser.add_argument("--surah", "--chapter", type=int, help="Surah/chapter number (1-114)")
    parser.add_argument("--juz", type=int, help="Juz number (1-30)")
    parser.add_argument("--verse", type=str, help="Verse spec: CHAPTER:VERSE or CHAPTER:START-END (e.g. 34:1-30)")
    parser.add_argument("--ayahs", type=str, help="Ayah range within surah e.g. 1-30")
    parser.add_argument("--layout", choices=["centered", "justified"], default="centered")
    parser.add_argument("--output", type=str, help="Output filename")
    parser.add_argument("--duration", type=str, help="Total video duration (e.g. 30m, 1800, 1h30m). Juz default: 30m. Surah: derived from juz proportionally.")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel encode workers (default: 1 = serial)")
    parser.add_argument("--hang-timeout", type=int, default=None, metavar="SEC",
                        help="Seconds without ffmpeg progress before abort (default: 120, 0=disable)")
    args = parser.parse_args()

    duration = None
    if args.duration:
        duration = parse_duration(args.duration)

    if args.verse:
        chapter, v_start, v_end = parse_verse_arg(args.verse)
        ayahs_range = slice(v_start - 1, v_end)
        generate_surah_video(chapter, args.layout, ayahs_range, args.output,
                             duration, args.workers, args.hang_timeout)
    elif args.surah:
        ayahs_range = None
        if args.ayahs:
            parts = args.ayahs.split("-")
            start = int(parts[0]) - 1
            end = int(parts[1]) if len(parts) > 1 else start + 1
            ayahs_range = slice(start, end)
        generate_surah_video(args.surah, args.layout, ayahs_range,
                             args.output, duration, args.workers,
                             args.hang_timeout)
    elif args.juz:
        generate_juz_video(args.juz, args.layout, duration, args.workers,
                           args.hang_timeout)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
