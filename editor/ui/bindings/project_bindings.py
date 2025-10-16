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
        },
        "global_noise": {
            "planet_type_preset": mw.planet_type_preset_input.currentText(),
            "continent_scale_km": mw.ws_continent_scale_km.value(),
            "octaves": int(mw.ws_octaves.value()),
            "gain": mw.ws_gain.value(),
            "power": mw.ws_power.value(),
            "warp_strength": mw.ws_warp_strength.value(),
            "seed": mw.ws_seed.value(),
        },
        # --- НОВЫЙ БЛОК ДЛЯ СОХРАНЕНИЯ КЛИМАТА ---
        "climate": {
            "enabled": mw.climate_enabled.isChecked(),
            "sea_level_pct": mw.climate_sea_level.value(),
            "avg_temp_c": mw.climate_avg_temp.value(),
            "axis_tilt_deg": mw.climate_axis_tilt.value(),
            "wind_dir_deg": mw.climate_wind_dir.value(),
            "shadow_strength": mw.climate_shadow_strength.value()
        }
    }


def apply_project_to_ui(mw, data: dict) -> None:
    """Применяет загруженные данные из project.json к виджетам в UI."""
    logger.debug("Applying project data to UI.")
    topo = data.get("world_topology", {})
    noise = data.get("global_noise", {})
    climate = data.get("climate", {}) # Загружаем секцию климата

    mw.subdivision_level_input.setCurrentText(topo.get("subdivision", "8 (642 регионов)"))
    mw.region_resolution_input.setCurrentText(topo.get("resolution", "4096x4096"))

    # --- Совместимость для старых проектов ---
    if "continent_scale_km" in noise:
        mw.ws_continent_scale_km.setValue(noise.get("continent_scale_km", 4000.0))
    elif "scale" in noise:
        old_relative_scale = noise.get("scale", 0.25)
        estimated_km = 2000.0 + old_relative_scale * 18000.0
        mw.ws_continent_scale_km.setValue(estimated_km)
        logger.warning("Загружен старый проект: относительный масштаб 'scale' был конвертирован в ~%d км.",
                       estimated_km)

    mw.planet_type_preset_input.setCurrentText(noise.get("planet_type_preset", "Землеподобная (0.3%)"))
    mw.ws_octaves.setValue(noise.get("octaves", 8))
    mw.ws_gain.setValue(noise.get("gain", 0.5))
    mw.ws_power.setValue(noise.get("power", 1.0))
    mw.ws_warp_strength.setValue(noise.get("warp_strength", 0.2))
    mw.ws_seed.setValue(noise.get("seed", 12345))

    # --- ПРИМЕНЯЕМ НАСТРОЙКИ КЛИМАТА ---
    mw.climate_enabled.setChecked(climate.get("enabled", False))
    mw.climate_sea_level.setValue(climate.get("sea_level_pct", 40.0))
    mw.climate_avg_temp.setValue(climate.get("avg_temp_c", 15.0))
    mw.climate_axis_tilt.setValue(climate.get("axis_tilt_deg", 23.5))
    mw.climate_wind_dir.setValue(climate.get("wind_dir_deg", 225.0))
    mw.climate_shadow_strength.setValue(climate.get("shadow_strength", 0.6))


    # Вызываем обновление вычисляемых полей ПОСЛЕ установки всех значений
    QtCore.QTimer.singleShot(0, mw._update_calculated_fields)


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

    except (AttributeError, ValueError, IndexError) as e:
        logger.error(f"Ошибка чтения настроек из UI: {e}")
        resolution, vertex_distance, max_height = 512, 1.0, 1000.0

    x_coords = np.zeros((resolution, resolution), dtype=np.float32)
    z_coords = np.zeros((resolution, resolution), dtype=np.float32)

    return {
        "x_coords": x_coords,
        "z_coords": z_coords,
        "WORLD_SIZE_METERS": resolution * vertex_distance,
        "max_height_m": max_height,
        "project": mw.project_manager.current_project_data if mw.project_manager else {}
    }