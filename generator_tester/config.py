# generator_tester/config.py
import os
import pathlib # <<< Добавляем pathlib

# --- Основные настройки мира ---
CHUNK_SIZE = 128

# <<< НОВЫЙ БЛОК: Вычисляем абсолютные пути >>>
# Находим путь к корню проекта (папка, где лежат engine и generator_tester)
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Строим полные пути к файлам, которые нам нужны
PRESET_PATH = PROJECT_ROOT / "engine" / "presets" / "world" / "base_default.json"
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"
# <<< КОНЕЦ НОВОГО БЛОКА >>>


# --- Настройки отображения ---
TILE_SIZE = 5
SCREEN_WIDTH_TILES = 128
SCREEN_HEIGHT_TILES = 128
SCREEN_WIDTH = SCREEN_WIDTH_TILES * TILE_SIZE
SCREEN_HEIGHT = SCREEN_HEIGHT_TILES * TILE_SIZE

# --- Цвета ---
PLAYER_COLOR = (255, 255, 255)
PATH_COLOR = (255, 255, 0)
BACKGROUND_COLOR = (0, 0, 0)
ERROR_COLOR = (255, 0, 255)

# --- Управление ---
PLAYER_MOVE_SPEED = 0.1 # Секунд на перемещение на 1 тайл