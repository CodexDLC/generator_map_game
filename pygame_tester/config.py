# pygame_tester/config.py
import pathlib

# --- Основные настройки мира ---
CHUNK_SIZE = 256
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PRESET_PATH = PROJECT_ROOT / "game_engine" / "presets" / "world" / "base_default.json"
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"

# --- Настройки окна и камеры ---
MENU_WIDTH = 240  # Немного увеличим меню
TILE_SIZE = 48    # <-- ГЛАВНОЕ ИЗМЕНЕНИЕ: Жестко задаем размер гекса в пикселях
VIEWPORT_WIDTH_TILES = 32
VIEWPORT_HEIGHT_TILES = 20

SCREEN_WIDTH = VIEWPORT_WIDTH_TILES * TILE_SIZE + MENU_WIDTH
SCREEN_HEIGHT = VIEWPORT_HEIGHT_TILES * TILE_SIZE

# --- Настройки управления ---
PLAYER_MOVE_SPEED = 0.1 # Скорость движения по пути (в секундах на клетку)
CAMERA_MOVE_SPEED = 400.0 # Скорость ручного перемещения камеры (в пикселях в секунду)

# --- Цвета ---
PLAYER_COLOR = (255, 255, 255)
PATH_COLOR = (255, 255, 0)
BACKGROUND_COLOR = (15, 15, 25)
ERROR_COLOR = (255, 0, 255)
GATEWAY_COLOR = (255, 215, 0)