import json
import os
import urllib.request

from .config import QURAN_JSON, CACHE_DIR


_quran_cache = None


def load_quran():
    global _quran_cache
    if _quran_cache is not None:
        return _quran_cache
    with open(QURAN_JSON, "r", encoding="utf-8") as f:
        _quran_cache = json.load(f)
    return _quran_cache


def fetch_surah(surah_num):
    quran = load_quran()
    for surah in quran:
        if surah["id"] == surah_num:
            ayahs = []
            global_ayah = _surah_start_ayah(surah_num, quran)
            for i, v in enumerate(surah["verses"]):
                ayahs.append({
                    "number": global_ayah + i,
                    "numberInSurah": i + 1,
                    "text": v["text"],
                })
            return {
                "number": surah_num,
                "name": surah["name"],
                "englishName": surah["transliteration"],
                "ayahs": ayahs,
            }
    raise ValueError(f"Surah {surah_num} not found")


def fetch_juz(juz_num):
    cache_path = os.path.join(CACHE_DIR, f"juz_{juz_num}.json")
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    url = f"https://api.alquran.cloud/v1/juz/{juz_num}"
    print(f"  Fetching Juz {juz_num}...")
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def _surah_start_ayah(surah_num, quran):
    start = 1
    for s in quran:
        if s["id"] == surah_num:
            return start
        start += s["total_verses"]
    return start