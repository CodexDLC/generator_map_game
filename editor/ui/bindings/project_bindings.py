# editor/ui/bindings/project_bindings.py
import numpy as np
import logging
from PySide6 import QtCore

logger = logging.getLogger(__name__)

def collect_project_data_from_ui(mw) -> dict:
    """Собирает все глобальные настройки из UI для сохранения в project.json."""
    return {
        "world_topology": {
            "subdivision": mw.subdivision_level_input.currentText(),
            "resolution": mw.region_resolution_input.currentText(),
            "vertex_distance": mw.vertex_distance_input.value(),
            "max_height": mw.max_height_input.value(),
        },
        "global_noise": {
            # --- ИСПРАВЛЕНИЕ: Добавлены все новые поля ---
            "base_elevation_pct": mw.ws_base_elevation_pct.value(),
            "sea_level_pct": mw.ws_sea_level.value(),
            "scale": mw.ws_relative_scale.value(),
            "octaves": int(mw.ws_octaves.value()),
            "gain": mw.ws_gain.value(),
            "power": mw.ws_power.value(),
            "warp_strength": mw.ws_warp_strength.value(),
            "seed": mw.ws_seed.value(),
        }
    }


def apply_project_to_ui(mw, data: dict) -> None:
    """Применяет загруженные данные из project.json к виджетам в UI."""
    logger.debug("Applying project data to UI.")
    topo = data.get("world_topology", {})
    noise = data.get("global_noise", {})

    mw.subdivision_level_input.setCurrentText(topo.get("subdivision", "8 (642 регионов)"))
    mw.region_resolution_input.setCurrentText(topo.get("resolution", "4096x4096"))
    mw.vertex_distance_input.setValue(topo.get("vertex_distance", 1.0))
    mw.max_height_input.setValue(topo.get("max_height", 4000.0))

    # --- ИСПРАВЛЕНИЕ: Добавлены все новые поля ---
    mw.ws_base_elevation_pct.setValue(noise.get("base_elevation_pct", 0.5))
    mw.ws_sea_level.setValue(noise.get("sea_level_pct", 0.4))
    mw.ws_relative_scale.setValue(noise.get("scale", 0.25))
    mw.ws_octaves.setValue(noise.get("octaves", 8))
    mw.ws_gain.setValue(noise.get("gain", 0.5))
    mw.ws_power.setValue(noise.get("power", 1.0))
    mw.ws_warp_strength.setValue(noise.get("warp_strength", 0.2))
    mw.ws_seed.setValue(noise.get("seed", 12345))

    QtCore.QTimer.singleShot(0, mw._update_dynamic_ranges)


def collect_context_from_ui(mw, for_preview: bool = True) -> dict:
    """
    Собирает контекст из UI, используя сохраненное смещение от клика по карте.
    """
    try:
        if for_preview:
            preview_res_str = mw.preview_resolution_input.currentText()
            resolution = int(preview_res_str.split('x')[0])
        else:
            region_res_str = mw.region_resolution_input.currentText()
            resolution = int(region_res_str.split('x')[0])

        vertex_distance = mw.vertex_distance_input.value()
        max_height = mw.max_height_input.value()

        offset_x, offset_z = mw.current_world_offset

    except (AttributeError, ValueError, IndexError) as e:
        logger.error(f"Ошибка чтения настроек из UI: {e}")
        resolution, vertex_distance, max_height = 512, 1.0, 1000.0
        offset_x, offset_z = 0.0, 0.0

    if for_preview:
        preview_vertex_distance = 1.0
        preview_max_height = max_height / vertex_distance if vertex_distance > 0 else max_height
        world_size_meters = resolution * preview_vertex_distance
    else:
        world_size_meters = resolution * vertex_distance
        preview_max_height = max_height

    half_size = world_size_meters / 2.0
    x_min, x_max = offset_x - half_size, offset_x + half_size
    z_min, z_max = offset_z - half_size, offset_z + half_size

    x_range = np.linspace(x_min, x_max, resolution, dtype=np.float32)
    z_range = np.linspace(z_min, z_max, resolution, dtype=np.float32)
    x_coords, z_coords = np.meshgrid(x_range, z_range)

    return {
        "x_coords": x_coords,
        "z_coords": z_coords,
        "WORLD_SIZE_METERS": world_size_meters,
        "max_height_m": preview_max_height,
    }