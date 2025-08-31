# generator_tester/config.py
import pathlib

# --- Основные настройки мира ---
CHUNK_SIZE = 128
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PRESET_PATH = PROJECT_ROOT / "engine" / "presets" / "world" / "base_default.json"
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"

# --- Настройки отображения (Viewport) ---
# <<< ИЗМЕНЕНИЕ: Увеличиваем тайлы для читаемости текста >>>
TILE_SIZE = 20
# <<< ИЗМЕНЕНИЕ: Уменьшаем количество тайлов на экране для "зума" >>>
VIEWPORT_WIDTH_TILES = 40
VIEWPORT_HEIGHT_TILES = 30
SCREEN_WIDTH = VIEWPORT_WIDTH_TILES * TILE_SIZE
SCREEN_HEIGHT = VIEWPORT_HEIGHT_TILES * TILE_SIZE

# --- Настройки управления ---
PLAYER_MOVE_SPEED = 0.1

# --- Цвета ---
PLAYER_COLOR = (255, 255, 255)
PATH_COLOR = (255, 255, 0)
BACKGROUND_COLOR = (15, 15, 25)
ERROR_COLOR = (255, 0, 255)
GATEWAY_COLOR = (255, 215, 0)