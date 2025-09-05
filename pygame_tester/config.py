# pygame_tester/config.py
import pathlib

# --- Основные настройки мира ---
CHUNK_SIZE = 128
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PRESET_PATH = PROJECT_ROOT / "game_engine" / "presets" / "world" / "base_default.json"
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"

MENU_WIDTH = 220


TILE_SIZE = 35
VIEWPORT_WIDTH_TILES = 48  # <-- Увеличиваем количество тайлов по ширине
VIEWPORT_HEIGHT_TILES = 32 # <-- Увеличиваем количество тайлов по высоте

SCREEN_WIDTH = VIEWPORT_WIDTH_TILES * TILE_SIZE + MENU_WIDTH
SCREEN_HEIGHT = VIEWPORT_HEIGHT_TILES * TILE_SIZE

# --- Настройки управления ---
PLAYER_MOVE_SPEED = 0.1

# --- Цвета ---
PLAYER_COLOR = (255, 255, 255)
PATH_COLOR = (255, 255, 0)
BACKGROUND_COLOR = (15, 15, 25)
ERROR_COLOR = (255, 0, 255)
GATEWAY_COLOR = (255, 215, 0)