# editor/actions/preset_actions.py
import json
import logging
from pathlib import Path
from typing import Optional, cast

from PySide6 import QtWidgets

from editor.actions.project_actions import on_save_project

logger = logging.getLogger(__name__)


# -------------------- статус-бар (безопасно) --------------------

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


# -------------------- project.json --------------------

def get_project_data(self):
    if not getattr(self, "current_project_path", None):
        _show_status(self, "Проект не открыт.", 4000)
        return None
    p = Path(self.current_project_path) / "project.json"
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _show_status(self, f"Ошибка чтения {p.name}: {e}", 5000)
        return None


# -------------------- файлы пресета --------------------

def create_new_preset_files(project_path: str, preset_name: str) -> dict:
    """
    Создаёт ОДИН файл графа (landscape_graph) и оставляет его пустым.
    При загрузке мы построим актуальные ноды (WorldInputNode → OutputNode).
    """
    pipelines_dir = Path(project_path) / "pipelines"
    pipelines_dir.mkdir(exist_ok=True)

    preset_info = {
        "description": "Новый пресет",
        "landscape_graph": f"pipelines/{preset_name}.json",
    }

    graph_path = Path(project_path) / preset_info["landscape_graph"]
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

    return preset_info


# -------------------- загрузка графа --------------------

def _build_default_landscape_graph(graph) -> None:
    """Создаёт минимальный пайплайн: WorldInputNode -> OutputNode."""
    try:
        input_node  = graph.create_node('Ландшафт.Пайплайн.WorldInputNode',
                                        name='Вход',  pos=(-300, 0))
        output_node = graph.create_node('Ландшафт.Пайплайн.OutputNode',
                                        name='Выход', pos=(100, 0))
        # порт 0 у обоих — height
        input_node.set_output(0, output_node.input(0))
    except Exception as e:
        logger.error("Не удалось создать дефолтные ноды: %s", e)


def load_preset_into_graph(main_window, preset_info: dict):
    """
    Загружает граф ЛАНДШАФТА в единственную рабочую область.
    Если файл пуст/битый/со старыми классами — строит дефолтные ноды.
    """
    project_path = Path(main_window.current_project_path)
    graph = getattr(main_window, "graph", None)

    graph_path_str = preset_info.get("landscape_graph")
    if not graph or not graph_path_str:
        logger.warning("Граф или путь к файлу не найдены. Загрузка пресета пропущена.")
        return

    graph_path = project_path / graph_path_str
    graph.clear_session()

    if not graph_path.exists():
        # нет файла — просто создаём дефолтную связку
        _build_default_landscape_graph(graph)
        return

    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning("Не удалось прочитать файл графа %s: %s. Создаю дефолт.", graph_path, e)
        _build_default_landscape_graph(graph)
        return

    # Пусто или без нод — строим дефолт
    if not data or not data.get("nodes"):
        _build_default_landscape_graph(graph)
        return

    # Пробуем десериализовать. Если упало (старые классы и т.п.) — дефолт.
    try:
        graph.deserialize_session(data)
    except Exception as e:
        logger.warning("deserialize_session упал: %s. Создаю дефолт.", e)
        graph.clear_session()
        _build_default_landscape_graph(graph)


# -------------------- команды UI --------------------

def handle_new_preset(main_window):
    """
    Диалог -> создание 1 файла графа -> запись в project.json -> загрузка в граф.
    """
    preset_name, ok = QtWidgets.QInputDialog.getText(main_window, "Новый пресет", "Введите имя пресета:")
    if not (ok and preset_name.strip()):
        return

    preset_name = preset_name.strip()
    project_data = main_window.get_project_data()
    if project_data is None:
        return

    presets = project_data.setdefault("region_presets", {})

    if preset_name in presets:
        QtWidgets.QMessageBox.warning(main_window, "Ошибка", "Пресет с таким именем уже существует.")
        return

    preset_info = create_new_preset_files(main_window.current_project_path, preset_name)
    presets[preset_name] = preset_info

    # можно сразу активировать новый пресет
    project_data["active_preset_name"] = preset_name

    on_save_project(main_window, project_data)
    main_window._load_presets_list()

    # и сразу загрузить в граф
    load_preset_into_graph(main_window, preset_info)

    _show_status(main_window, f"Пресет '{preset_name}' создан и загружен.", 4000)


def handle_delete_preset(main_window):
    """Удаление пресета (одного файла графа)."""
    selected_items = main_window.presets_list_widget.selectedItems()
    if not selected_items:
        _show_status(main_window, "Сначала выберите пресет для удаления.", 3000)
        return

    preset_name = selected_items[0].text()
    if preset_name == "default":
        QtWidgets.QMessageBox.warning(main_window, "Ошибка", "Пресет 'default' нельзя удалить.")
        return

    reply = QtWidgets.QMessageBox.question(
        main_window, "Подтверждение",
        f"Удалить пресет '{preset_name}'?",
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
    )
    if reply == QtWidgets.QMessageBox.StandardButton.No:
        return

    project_data = main_window.get_project_data()
    if project_data is None:
        return

    presets = project_data.get("region_presets", {})
    preset_to_delete = presets.pop(preset_name, None)

    if preset_to_delete:
        graph_rel = preset_to_delete.get("landscape_graph")
        if graph_rel:
            try:
                (Path(main_window.current_project_path) / graph_rel).unlink(missing_ok=True)
            except Exception as e:
                logger.error("Не удалось удалить файл графа: %s", e)

    if project_data.get("active_preset_name") == preset_name:
        project_data["active_preset_name"] = "default"

    on_save_project(main_window, project_data)
    main_window._load_presets_list()
    _show_status(main_window, f"Пресет '{preset_name}' удалён.", 4000)
