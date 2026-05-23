import io
import json
import os
import urllib.request

import mutagen

from .config import TIMINGS_JSON, CACHE_DIR


def load_timings(quran=None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.exists(TIMINGS_JSON):
        with open(TIMINGS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)

    if quran is None:
        from .api import load_quran
        quran = load_quran()

    print("Downloading ayah durations from Al-Afasy recitation...")
    total_ayahs = sum(s["total_verses"] for s in quran)
    print(f"  Total ayahs: {total_ayahs}")

    durations = {}
    ayah_num = 1
    for surah in quran:
        for verse_idx in range(surah["total_verses"]):
            url = f"https://cdn.islamic.network/quran/audio/128/ar.alafasy/{ayah_num}.mp3"
            try:
                data = urllib.request.urlopen(url).read()
                audio = mutagen.File(io.BytesIO(data))
                durations[str(ayah_num)] = round(audio.info.length, 3)
            except Exception as e:
                print(f"  Warning: ayah {ayah_num} failed: {e}")
                durations[str(ayah_num)] = 5.0
            if ayah_num % 500 == 0:
                print(f"  Progress: {ayah_num}/{total_ayahs}")
            ayah_num += 1

    with open(TIMINGS_JSON, "w", encoding="utf-8") as f:
        json.dump(durations, f)
    print(f"  Saved durations for {len(durations)} ayahs")
    return durations


def fetch_ayah_duration(ayah_number, timings=None):
    if timings and str(ayah_number) in timings:
        return timings[str(ayah_number)]
    url = f"https://cdn.islamic.network/quran/audio/128/ar.alafasy/{ayah_number}.mp3"
    try:
        data = urllib.request.urlopen(url).read()
        return mutagen.File(io.BytesIO(data)).info.length
    except Exception:
        return 5.0