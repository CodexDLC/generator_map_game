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
            # --- ИЗМЕНЕНИЕ: Это поле теперь вычисляемое, сохранять его не нужно ---
            # "vertex_distance": mw.vertex_distance_input.value(),
        },
        "global_noise": {
            "planet_radius_km": mw.planet_radius_input_km.value(),  # Сохраняем радиус
            "planet_type_preset": mw.planet_type_preset_input.currentText(),
            # --- ИЗМЕНЕНИЕ: Сохраняем новое значение в километрах ---
            "continent_scale_km": mw.ws_continent_scale_km.value(),
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

    # --- НАЧАЛО ИЗМЕНЕНИЙ: Логика загрузки радиуса и масштаба ---

    # Загружаем радиус. Если его нет, оставляем значение по умолчанию.
    if "planet_radius_km" in noise:
        mw.planet_radius_input_km.setValue(noise.get("planet_radius_km", 6371.0))

    # Обратная совместимость для масштаба континентов
    if "continent_scale_km" in noise:
        # Если есть новый ключ - используем его
        mw.ws_continent_scale_km.setValue(noise.get("continent_scale_km", 4000.0))
    elif "scale" in noise:
        # Если есть только старый ключ "scale" (0..1), конвертируем его в примерные километры
        # Это грубая эвристика для старых проектов
        old_relative_scale = noise.get("scale", 0.25)
        # Предположим, что старый "масштаб 1.0" соответствовал ~20000 км
        estimated_km = 2000.0 + old_relative_scale * 18000.0
        mw.ws_continent_scale_km.setValue(estimated_km)
        logger.warning("Загружен старый проект: относительный масштаб 'scale' был конвертирован в ~%d км.",
                       estimated_km)

    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    mw.planet_type_preset_input.setCurrentText(noise.get("planet_type_preset", "Землеподобная (0.3%)"))
    mw.ws_octaves.setValue(noise.get("octaves", 8))
    mw.ws_gain.setValue(noise.get("gain", 0.5))
    mw.ws_power.setValue(noise.get("power", 1.0))
    mw.ws_warp_strength.setValue(noise.get("warp_strength", 0.2))
    mw.ws_seed.setValue(noise.get("seed", 12345))

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

        offset_x, offset_z = 0.0, 0.0

    except (AttributeError, ValueError, IndexError) as e:
        logger.error(f"Ошибка чтения настроек из UI: {e}")
        resolution, vertex_distance, max_height = 512, 1.0, 1000.0
        offset_x, offset_z = 0.0, 0.0

    x_coords = np.zeros((resolution, resolution), dtype=np.float32)
    z_coords = np.zeros((resolution, resolution), dtype=np.float32)

    return {
        "x_coords": x_coords,
        "z_coords": z_coords,
        "WORLD_SIZE_METERS": resolution * vertex_distance,
        "max_height_m": max_height,
        "project": mw.project_manager.current_project_data if mw.project_manager else {}
    }