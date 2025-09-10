# Файл: game_engine_restructured/algorithms/climate/climate.py
from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
from opensimplex import OpenSimplex
from scipy.ndimage import distance_transform_edt

from ...core.preset.model import Preset
from ...core.types import GenResult
from ...core import constants as const

if TYPE_CHECKING:
    from ...core.preset.model import Preset

BIOME_TO_SURFACE = {
    "temperate_seasonal_forest": const.KIND_FOREST_FLOOR,
    "plains": const.KIND_PLAINS_GRASS,
    "savanna": const.KIND_SAVANNA_DRYGRASS,
    "subtropical_desert": const.KIND_DESERT_GROUND,
    "tropical_rainforest": const.KIND_JUNGLE_DARKFLOOR,
    "boreal_forest": const.KIND_TAIGA_MOSS,
    "tundra": const.KIND_TUNDRA_SNOWGROUND,
}


def determine_biome(temperature: float, humidity: float) -> str:
    """Определяет ID биома по диаграмме Уиттекера."""
    if temperature > 24:
        if humidity > 0.6: return "tropical_rainforest"
        if humidity > 0.25: return "savanna"
        return "subtropical_desert"
    elif temperature > 5:
        if humidity > 0.4: return "temperate_seasonal_forest"
        return "plains"
    else:
        if humidity > 0.3: return "boreal_forest"
        return "tundra"


def generate_climate_maps(result: GenResult, preset: Preset):
    climate_cfg = preset.climate
    if not climate_cfg.get("enabled"):
        return

    size = result.size
    height_grid = np.array(result.layers["height_q"]["grid"], dtype=np.float32)

    # --- 1. Генерация температуры (без изменений) ---
    temp_cfg = climate_cfg.get("temperature", {})
    if temp_cfg.get("enabled"):
        base_temp = temp_cfg.get("base_c", 18.0)
        noise_amp = temp_cfg.get("noise_amp_c", 6.0)
        lapse_rate = temp_cfg.get("lapse_rate_c_per_m", -0.0065)
        clamp_min, clamp_max = temp_cfg.get("clamp_c", [-15.0, 35.0])

        noise_gen = OpenSimplex(result.stage_seeds["temperature"])
        noise_scale = temp_cfg.get("noise_scale_tiles", 9000.0)
        freq = 1.0 / noise_scale if noise_scale > 0 else 0

        z_coords = np.arange(result.cz * size, (result.cz + 1) * size)
        latitude_grad = z_coords * temp_cfg.get("gradient_c_per_km", -0.02) * -0.1
        temperature_grid = np.full((size, size), base_temp, dtype=np.float32)
        temperature_grid += latitude_grad[:, np.newaxis]

        noise_grid = np.zeros((size, size), dtype=np.float32)
        for z in range(size):
            for x in range(size):
                wx, wz = (result.cx * size) + x, (result.cz * size) + z
                noise_grid[z, x] = noise_gen.noise2(wx * freq, wz * freq)

        temperature_grid += noise_grid * noise_amp
        temperature_grid += height_grid * lapse_rate
        np.clip(temperature_grid, clamp_min, clamp_max, out=temperature_grid)
        result.layers["temperature"] = temperature_grid.tolist()

    # --- 2. Генерация влажности (НОВАЯ ЛОГИКА) ---
    humidity_cfg = climate_cfg.get("humidity", {})
    if humidity_cfg.get("enabled"):
        base_humidity = humidity_cfg.get("base", 0.45)
        noise_amp = humidity_cfg.get("noise_amp", 0.35)
        clamp_min, clamp_max = humidity_cfg.get("clamp", [0.0, 1.0])

        # --- ШАГ 2.1: Создаем карту близости к воде ---
        nav_grid = np.array(result.layers["navigation"])
        is_water = nav_grid == const.NAV_WATER

        # distance_transform_edt вычисляет расстояние от каждой НЕ-водной клетки до ближайшей водной
        dist_to_water = distance_transform_edt(~is_water)

        # --- ШАГ 2.2: Превращаем расстояние во влажность ---
        # Чем ближе к воде (меньше dist), тем выше влажность
        coastal_effect_range = 32  # Влажность будет падать на протяжении 32 метров от берега
        coastal_humidity = 1.0 - np.clip(dist_to_water / coastal_effect_range, 0.0, 1.0)
        # Умножаем на 0.5, чтобы максимальный бонус был +50%
        coastal_humidity_bonus = coastal_humidity * 0.5

        # --- ШАГ 2.3: Генерируем базовый шум влажности ---
        noise_gen = OpenSimplex(result.stage_seeds["humidity"])
        noise_scale = humidity_cfg.get("noise_scale_tiles", 10000.0)
        freq = 1.0 / noise_scale if noise_scale > 0 else 0
        humidity_grid = np.full((size, size), base_humidity, dtype=np.float32)

        noise_grid = np.zeros((size, size), dtype=np.float32)
        for z in range(size):
            for x in range(size):
                wx, wz = (result.cx * size) + x, (result.cz * size) + z
                noise_grid[z, x] = (noise_gen.noise2(wx * freq, wz * freq) + 1.0) / 2.0

        humidity_grid += (noise_grid - 0.5) * (2 * noise_amp)

        # --- ШАГ 2.4: Складываем базовую влажность и бонус от близости к воде ---
        humidity_grid += coastal_humidity_bonus

        # Ограничиваем итоговый диапазон
        np.clip(humidity_grid, clamp_min, clamp_max, out=humidity_grid)
        result.layers["humidity"] = humidity_grid.tolist()

    print(f"  -> Climate maps generated for chunk ({result.cx}, {result.cz})")


def apply_biomes_to_surface(result: GenResult):
    """
    Проходит по картам климата и назначает каждой клетке
    соответствующий базовый тип поверхности биома.
    """
    if "temperature" not in result.layers or "humidity" not in result.layers:
        print(f"  -> Skipping biome application: climate data not found for chunk ({result.cx}, {result.cz}).")
        return

    size = result.size
    temp_grid = result.layers["temperature"]
    humidity_grid = result.layers["humidity"]
    surface_grid = result.layers["surface"]

    biome_counts = {}

    for z in range(size):
        for x in range(size):
            # Не меняем скалы и другие специальные тайлы
            if surface_grid[z][x] not in (const.KIND_BASE_DIRT,):
                continue

            temp = temp_grid[z][x]
            humidity = humidity_grid[z][x]
            biome_id = determine_biome(temp, humidity)

            biome_counts[biome_id] = biome_counts.get(biome_id, 0) + 1

            surface_kind = BIOME_TO_SURFACE.get(biome_id, const.KIND_BASE_DIRT)
            surface_grid[z][x] = surface_kind

    if biome_counts:
        # Определяем доминирующий биом для всего чанка
        dominant_biome = max(biome_counts, key=biome_counts.get)
        result.metrics["dominant_biome"] = dominant_biome
        print(f"  -> Biomes applied. Dominant: {dominant_biome} for chunk ({result.cx}, {result.cz}).")