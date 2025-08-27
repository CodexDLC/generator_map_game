# --- ИЗМЕНЕНИЕ: ID биомов теперь начинаются с 0 для суши ---
BIOME_ID_LAND_BASE = 0      # Базовая суша
BIOME_ID_ROCK = 1           # Скалы
BIOME_ID_BEACH = 2          # Пляж
BIOME_ID_PLAIN = 3          # Равнины
BIOME_ID_FOREST = 4         # Лес
BIOME_ID_SNOW = 5           # Снег

# --- ИЗМЕНЕНИЕ: Специальный временный ID для воды ---
# Мы используем его только для генерации PNG-карты
BIOME_ID_WATER_VISUAL = 99

# Порог влажности для разделения равнин и лесов
MOISTURE_THRESHOLD_FOREST = 0.4