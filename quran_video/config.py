import os

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
QURAN_JSON = os.path.join(SCRIPT_DIR, "quran.json")
TIMINGS_JSON = os.path.join(CACHE_DIR, "ayah_durations.json")

WIDTH = 1920
HEIGHT = 1080
FPS = 24
RATE_2X = 2.0
DEFAULT_JUZ_DURATION = 30 * 60  # 30 minutes in seconds
AVG_AYAHS_PER_JUZ = 6236 / 30   # ~208 ayahs per juz

FONT_AMIRI_QURAN = "/home/mine/.local/share/fonts/AmiriQuran.ttf"
if not os.path.exists(FONT_AMIRI_QURAN):
    FONT_AMIRI_QURAN = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"

FONT_AMIRI_BOLD = "/home/mine/.local/share/fonts/Amiri-Bold.ttf"
if not os.path.exists(FONT_AMIRI_BOLD):
    FONT_AMIRI_BOLD = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"

FONT_AMIRI_REG = "/home/mine/.local/share/fonts/Amiri-Regular.ttf"
if not os.path.exists(FONT_AMIRI_REG):
    FONT_AMIRI_REG = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"

FONT_NOTO = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
FONT_NOTO_BOLD = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"

FONT_SIZE_QURAN = 58
FONT_SIZE_BASMALAH = 64
FONT_SIZE_SURAH_AR = 46
FONT_SIZE_SURAH_EN = 26
FONT_SIZE_JUSTIFIED = 58
FONT_SIZE_BASMALAH_JUSTIFIED = 64
FONT_SIZE_SURAH_JUSTIFIED = 46

MARGIN_X = 200
MARGIN_X_JUSTIFIED = int(WIDTH * 0.075)
TEXT_WIDTH_JUSTIFIED = WIDTH - 2 * MARGIN_X_JUSTIFIED

LINE_H_CENTERED = 150
LINE_H_JUSTIFIED = 150

TOP_PAD = 180
BOT_PAD = HEIGHT
VERSE_GAP = 28

BG_COLOR_CENTERED = (12, 8, 20)
BG_COLOR_JUSTIFIED = (12, 8, 20)
TEXT_COLOR = (235, 230, 215)
GOLD = (200, 160, 60)
DARK_GOLD = (100, 75, 25)
BASMALAH_COLOR = (220, 190, 100)
VERSE_MARKER_COLOR = (180, 145, 65)
WAQF_MARKER_COLOR = (180, 145, 65)
WAQF_FONT_SIZE = 24
LINE_RULE_COLOR = (40, 35, 55)

BASMALAH_WORD = "\u0628\u0650\u0633\u0652\u0645\u0650"
AYAH_MARKER_CHAR = "\u06DD"
VERSE_MARKER_OPEN = "\uFD3F"
VERSE_MARKER_CLOSE = "\uFD3E"

FFMPEG_PRESET = "veryfast"
FFMPEG_CRF = 23