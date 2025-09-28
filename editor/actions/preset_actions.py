# editor/actions/preset_actions.py
import json
import logging
from pathlib import Path
from typing import Optional, cast

from PySide6 import QtWidgets

# Импортируем нужные экшены из соседних файлов
from .project_actions import on_save_project
from .pipeline_actions import _atomic_write_json

logger = logging.getLogger(__name__)


# -------------------- Вспомогательные функции (без изменений) --------------------

def _status_bar(mw) -> Optional[QtWidgets.QStatusBar]:
    try:
        sb_func = getattr(mw, "statusBar", None)
        if callable(sb_func):
            bar = sb_func()
            if isinstance(bar, QtWidgets.QStatusBar):
                return cast(QtWidgets.QStatusBar, bar)
    except Exception:
        pass
    return None

def _show_status(mw, text: str, msec: int = 4000) -> None:
    bar = _status_bar(mw)
    if bar:
        bar.showMessage(text, msec)

def _build_default_landscape_graph(graph) -> None:
    """Создаёт минимальный пайплайн: WorldInputNode -> OutputNode."""
    try:
        input_node  = graph.create_node('Ландшафт.Пайплайн.WorldInputNode',
                                        name='Вход',  pos=(-300, 0))
        output_node = graph.create_node('Ландшафт.Пайплайн.OutputNode',
                                        name='Выход', pos=(100, 0))
        input_node.set_output(0, output_node.input(0))
    except Exception as e:
        logger.error("Не удалось создать дефолтные ноды: %s", e)

# -------------------- Основная логика --------------------

def load_preset_into_graph(main_window, preset_info: dict):
    """
    Загружает граф ЛАНДШАФТА. Если файл пуст/битый — строит дефолтные ноды.
    """
    project_path = Path(main_window.current_project_path)
    graph = getattr(main_window, "graph", None)
    graph_path_str = preset_info.get("landscape_graph")

    if not graph or not graph_path_str:
        logger.warning("Граф или путь к файлу не найдены. Загрузка пресета пропущена.")
        return

    graph_path = project_path / graph_path_str
    graph.clear_session()  # Сначала всегда очищаем поле

    # Если файла физически нет, создаем дефолтный граф
    if not graph_path.exists():
        _build_default_landscape_graph(graph)
        return

    # Если файл есть, пытаемся его загрузить
    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Если в файле есть ноды - десериализуем.
        # Если файл пустой (только что созданный пресет) - ничего не делаем,
        # оставляя поле пустым, как и должно быть.
        if data and data.get("nodes"):
            graph.deserialize_session(data)

    except Exception as e:
        # Если файл поврежден (невалидный JSON), создаем дефолтный граф
        logger.warning("Ошибка десериализации графа %s: %s. Создаю дефолтный.", graph_path, e)
        _build_default_landscape_graph(graph)

def handle_new_preset(main_window):
    """
    Диалог -> создание файла графа -> запись в project.json -> загрузка в граф.
    """
    preset_name, ok = QtWidgets.QInputDialog.getText(main_window, "Новый пресет", "Введите имя пресета:")
    if not (ok and preset_name.strip()):
        return

    preset_name = preset_name.strip()
    project_data = main_window.get_project_data()
    if project_data is None: return

    presets = project_data.setdefault("region_presets", {})
    if preset_name in presets:
        QtWidgets.QMessageBox.warning(main_window, "Ошибка", "Пресет с таким именем уже существует.")
        return

    # Создаем запись и пустой файл для графа
    pipelines_dir = Path(main_window.current_project_path) / "pipelines"
    pipelines_dir.mkdir(exist_ok=True)
    preset_info = {
        "description": "Новый пресет",
        "landscape_graph": f"pipelines/{preset_name}.json",
    }
    graph_path = Path(main_window.current_project_path) / preset_info["landscape_graph"]
    with open(graph_path, "w", encoding="utf-8") as f:
        # Создаем пустой граф, который при загрузке превратится в стандартный
        json.dump({}, f)

    presets[preset_name] = preset_info
    project_data["active_preset_name"] = preset_name

    on_save_project(main_window, project_data)
    main_window._load_presets_list()
    load_preset_into_graph(main_window, preset_info)
    _show_status(main_window, f"Пресет '{preset_name}' создан и загружен.", 4000)


def handle_delete_preset(main_window):
    """
    Удаляет выбранный пресет, если он не последний.
    """
    selected_items = main_window.presets_list_widget.selectedItems()
    if not selected_items:
        _show_status(main_window, "Сначала выберите пресет для удаления.", 3000)
        return

    preset_name = selected_items[0].text()
    project_data = main_window.get_project_data()
    if project_data is None: return

    presets = project_data.get("region_presets", {})

    # --- НОВАЯ ЛОГИКА ЗАЩИТЫ ---
    if len(presets) <= 1:
        QtWidgets.QMessageBox.warning(main_window, "Действие запрещено", "Нельзя удалить последний пресет в проекте.")
        return
    # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

    reply = QtWidgets.QMessageBox.question(
        main_window, "Подтверждение", f"Удалить пресет '{preset_name}'?",
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
    )
    if reply == QtWidgets.QMessageBox.StandardButton.No:
        return

    preset_to_delete = presets.pop(preset_name, None)
    if preset_to_delete:
        graph_rel_path = preset_to_delete.get("landscape_graph")
        if graph_rel_path:
            try:
                (Path(main_window.current_project_path) / graph_rel_path).unlink(missing_ok=True)
            except Exception as e:
                logger.error("Не удалось удалить файл графа: %s", e)

    if project_data.get("active_preset_name") == preset_name:
        # Если удалили активный, делаем активным первый из оставшихся
        project_data["active_preset_name"] = next(iter(presets.keys()))

    on_save_project(main_window, project_data)
    main_window._load_presets_list()
    _show_status(main_window, f"Пресет '{preset_name}' удалён.", 4000)


def handle_save_active_preset(main_window):
    """Сохраняет текущий граф в файл активного пресета без диалогового окна."""
    # --- НАЧАЛО ИСПРАВЛЕНИЙ ---
    # Получаем доступ к графу напрямую, это более надежно.
    graph = main_window.get_active_graph()
    if not graph:
        _show_status(main_window, "Ошибка: не найден активный граф для сохранения.", 5000)
        return
    # --- КОНЕЦ ИСПРАВЛЕНИЙ ---

    project_data = main_window.get_project_data()
    if not project_data: return

    active_preset_name = project_data.get("active_preset_name")
    if not active_preset_name:
        _show_status(main_window, "Активный пресет не выбран.", 4000)
        return

    presets = project_data.get("region_presets", {})
    active_preset_info = presets.get(active_preset_name)
    if not active_preset_info or "landscape_graph" not in active_preset_info:
        _show_status(main_window, f"Ошибка: не найден путь для пресета '{active_preset_name}'.", 5000)
        return

    try:
        # --- ИЗМЕНЕНИЕ: Используем нашу переменную graph ---
        graph_data = graph.serialize_session()
        # --------------------------------------------------

        # Диагностика: можно временно включить, чтобы посмотреть, что сохраняется
        # print(json.dumps(graph_data, indent=2))

        file_path = Path(main_window.current_project_path) / active_preset_info["landscape_graph"]
        _atomic_write_json(file_path, graph_data)  # Ожидает Path, а не строку
        _show_status(main_window, f"Пресет '{active_preset_name}' сохранен.", 4000)
        logger.info(f"Preset '{active_preset_name}' saved to {file_path}")
    except Exception as e:
        logger.exception("Failed to save active preset.")
        _show_status(main_window, f"Ошибка сохранения: {e}", 6000)