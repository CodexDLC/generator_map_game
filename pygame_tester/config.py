# pygame_tester/config.py
import pathlib

# --- Основные настройки мира ---
CHUNK_SIZE = 256
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PRESET_PATH = PROJECT_ROOT / "game_engine_restructured" / "data" / "presets" / "world" / "base_default.json"
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"

# --- Настройки окна и камеры (НОВЫЕ) ---
MENU_WIDTH = 240
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 1024
SCREEN_WIDTH = VIEWPORT_WIDTH + MENU_WIDTH
SCREEN_HEIGHT = VIEWPORT_HEIGHT

# --- Настройки управления (НОВЫЕ) ---
CAMERA_MOVE_SPEED_PIXELS = 800.0 # Скорость полета камеры (пикселей в секунду)
CAMERA_ZOOM_SPEED = 0.1         # Чувствительность зума

# --- Цвета ---
PLAYER_COLOR = (255, 255, 0, 150) # Сделаем полупрозрачным
BACKGROUND_COLOR = (15, 15, 25)
ERROR_COLOR = (255, 0, 255)