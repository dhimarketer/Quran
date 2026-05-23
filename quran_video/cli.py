#!/usr/bin/env python3
import argparse
import os
import sys

from .config import WIDTH, HEIGHT, RATE_2X, OUTPUT_DIR, FONT_KFGQPC, FONT_AMIRI_QURAN
from .api import fetch_surah, fetch_juz, load_quran
from .timing import load_timings, fetch_ayah_duration
from .render import render, load_fonts, build_elements_from_surah, build_elements_from_juz
from .encode import encode_video


FIXED_DURATION_PER_VERSE = 4.0


def compute_duration(elements, timings=None):
    total = 2.0
    for elem in elements:
        if elem[0] == "surah_header":
            total += 3.0 / RATE_2X
        elif elem[0] == "basmalah":
            total += 3.0 / RATE_2X
        elif elem[0] == "verse":
            ayah_number = elem[3]
            if timings:
                dur = fetch_ayah_duration(ayah_number, timings)
            else:
                dur = FIXED_DURATION_PER_VERSE
            total += dur / RATE_2X
    return total


def generate_surah_video(surah_num, layout, ayahs_range=None, output_name=None, timings=None, quick=False):
    surah = fetch_surah(surah_num)
    fonts = load_fonts(layout)
    elements = build_elements_from_surah(surah, ayahs_slice=ayahs_range)

    tall_arr = render(elements, layout=layout, fonts=fonts)

    total_duration = compute_duration(elements, None if quick else timings)
    total_height = tall_arr.shape[0]
    num_frames = int(total_duration * 24)
    scroll_range = total_height - HEIGHT

    print(f"  Surah {surah_num}: {total_height}px, {total_duration:.0f}s ({total_duration/60:.1f}min)")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if output_name is None:
        suffix = f"_{layout}"
        if ayahs_range:
            suffix += f"_{ayahs_range.start+1}-{ayahs_range.stop}"
        output_name = f"surah_{surah_num}{suffix}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_name)

    encode_video(tall_arr, output_path, num_frames, scroll_range, quick=quick)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Done: {output_path} ({size_mb:.1f} MB)")
    return output_path


def generate_juz_video(juz_num, timings=None, quick=False):
    juz_data = fetch_juz(juz_num)
    fonts = load_fonts("centered")
    elements = build_elements_from_juz(juz_data)

    tall_arr = render(elements, layout="centered", fonts=fonts)

    total_duration = compute_duration(elements, None if quick else timings)
    total_height = tall_arr.shape[0]
    num_frames = int(total_duration * 24)
    scroll_range = total_height - HEIGHT

    print(f"  Juz {juz_num}: {total_height}px, {total_duration:.0f}s ({total_duration/60:.1f}min)")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"juz_{juz_num:02d}.mp4")

    encode_video(tall_arr, output_path, num_frames, scroll_range, quick=quick)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Done: {output_path} ({size_mb:.1f} MB)")
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
    parser.add_argument("--quick", action="store_true", help="Fast mode: skip timing downloads, use fixed duration per verse, ultrafast encoding")
    args = parser.parse_args()

    timings = None
    if not args.quick and (args.juz or args.surah or args.verse):
        quran = load_quran()
        timings = load_timings(quran)

    if args.verse:
        chapter, v_start, v_end = parse_verse_arg(args.verse)
        ayahs_range = slice(v_start - 1, v_end)
        generate_surah_video(chapter, args.layout, ayahs_range, args.output, timings, args.quick)
    elif args.surah:
        ayahs_range = None
        if args.ayahs:
            parts = args.ayahs.split("-")
            start = int(parts[0]) - 1
            end = int(parts[1]) if len(parts) > 1 else start + 1
            ayahs_range = slice(start, end)
        generate_surah_video(args.surah, args.layout, ayahs_range, args.output, timings, args.quick)
    elif args.juz:
        generate_juz_video(args.juz, timings, args.quick)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()