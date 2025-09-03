# pygame_tester/config.py
import pathlib

# --- Основные настройки мира ---
CHUNK_SIZE = 96
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PRESET_PATH = PROJECT_ROOT / "game_engine" / "presets" / "world" / "base_default.json"
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"

MENU_WIDTH = 220

# --- НАЧАЛО ИЗМЕНЕНИЯ: Делаем "зум" для лучшей детализации ---
TILE_SIZE = 32  # Увеличили размер каждого тайла
VIEWPORT_WIDTH_TILES = 50  # Уменьшили количество тайлов по ширине
VIEWPORT_HEIGHT_TILES = 40 # Уменьшили количество тайлов по высоте
# --- КОНЕЦ ИЗМЕНЕНИЯ ---

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