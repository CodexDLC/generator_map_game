# generator_tester/config.py
import pathlib

# --- Основные настройки мира ---
CHUNK_SIZE = 128
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PRESET_PATH = PROJECT_ROOT / "engine" / "presets" / "world" / "base_default.json"
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"

# --- Настройки отображения (Viewport) ---
TILE_SIZE = 5  # Размер одного тайла в пикселях
# <<< ИЗМЕНЕНО: Задаем размер видимой области в тайлах >>>
VIEWPORT_WIDTH_TILES = 160
VIEWPORT_HEIGHT_TILES = 120
SCREEN_WIDTH = VIEWPORT_WIDTH_TILES * TILE_SIZE
SCREEN_HEIGHT = VIEWPORT_HEIGHT_TILES * TILE_SIZE

# --- Настройки управления ---
PLAYER_MOVE_SPEED = 0.1  # Секунд на перемещение на 1 тайл

# --- Цвета ---
PLAYER_COLOR = (255, 255, 255)
PATH_COLOR = (255, 255, 0)
BACKGROUND_COLOR = (15, 15, 25)
ERROR_COLOR = (255, 0, 255)
GATEWAY_COLOR = (255, 215, 0) # Золотой
