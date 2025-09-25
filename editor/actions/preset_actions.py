import json
import logging
from pathlib import Path

from PySide6 import QtWidgets

from editor.actions.project_actions import on_save_project
from editor.graph_utils import create_default_graph_session

logger = logging.getLogger(__name__)


def get_project_data(self):
    if not self.current_project_path: return None
    try:
        with open(Path(self.current_project_path) / "project.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        self.statusBar.showMessage(f"Ошибка чтения файла проекта: {e}", 5000)
        return None


def create_new_preset_files(project_path: str, preset_name: str) -> dict:
    """Создает 3 .json файла для нового пресета с нодами по умолчанию."""
    pipelines_dir = Path(project_path) / "pipelines"
    pipelines_dir.mkdir(exist_ok=True)

    default_graph_data = create_default_graph_session()

    preset_info = {
        "description": "Новый пресет",
        "landscape_graph": f"pipelines/{preset_name}_landscape.json",
        "climate_graph": f"pipelines/{preset_name}_climate.json",
        "biome_graph": f"pipelines/{preset_name}_biome.json"
    }

    for key, rel_path in preset_info.items():
        if key.endswith("_graph"):
            full_path = Path(project_path) / rel_path
            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(default_graph_data, f, indent=2)

    return preset_info


# --- НАЧАЛО ФИНАЛЬНОГО ИСПРАВЛЕНИЯ ---
def load_preset_into_graph(main_window, preset_info: dict):
    """
    Загружает граф ЛАНДШАФТА из пресета в единственную рабочую область.
    """
    project_path = Path(main_window.current_project_path)

    # Получаем единственный граф напрямую
    graph = main_window.graph

    # Нас интересует только граф ландшафта
    graph_key = "landscape_graph"
    graph_path_str = preset_info.get(graph_key)

    if not graph or not graph_path_str:
        logger.warning(f"Граф или путь к файлу графа '{graph_key}' не найдены. Загрузка пресета пропущена.")
        return

    graph_path = project_path / graph_path_str
    graph.clear_session()

    if graph_path.exists():
        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Если файл пустой или не содержит нод, создаем дефолтные
            if not data or not data.get("nodes"):
                input_node = graph.create_node('Ландшафт.Пайплайн.WorldInputNode', name='Вход', pos=(-300, 0))
                output_node = graph.create_node('Ландшафт.Пайплайн.OutputNode', name='Выход', pos=(100, 0))
                input_node.set_output(0, output_node.input(0))
            else:
                graph.deserialize_session(data)
        except Exception as e:
            logger.error(f"Не удалось загрузить файл графа {graph_path}: {e}")


# --- КОНЕЦ ФИНАЛЬНОГО ИСПРАВЛЕНИЯ ---

def handle_new_preset(main_window):
    """
    Обрабатывает логику создания нового пресета, включая диалог с пользователем,
    создание файлов и обновление project.json.
    """
    preset_name, ok = QtWidgets.QInputDialog.getText(main_window, "Новый пресет", "Введите имя пресета:")
    if not (ok and preset_name.strip()):
        return

    preset_name = preset_name.strip()
    project_data = main_window.get_project_data()

    if preset_name in project_data.get("region_presets", {}):
        QtWidgets.QMessageBox.warning(main_window, "Ошибка", "Пресет с таким именем уже существует.")
        return

    preset_info = create_new_preset_files(main_window.current_project_path, preset_name)

    if "region_presets" not in project_data:
        project_data["region_presets"] = {}

    project_data["region_presets"][preset_name] = preset_info
    on_save_project(main_window, project_data)

    main_window._load_presets_list()
    main_window.statusBar.showMessage(f"Пресет '{preset_name}' создан.", 4000)


def handle_delete_preset(main_window):
    """Обрабатывает логику удаления пресета."""
    selected_items = main_window.presets_list_widget.selectedItems()
    if not selected_items:
        main_window.statusBar.showMessage("Сначала выберите пресет для удаления.", 3000)
        return

    preset_name = selected_items[0].text()
    if preset_name == "default":
        QtWidgets.QMessageBox.warning(main_window, "Ошибка", "Пресет 'default' нельзя удалить.")
        return

    reply = QtWidgets.QMessageBox.question(main_window, "Подтверждение",
                                           f"Вы уверены, что хотите удалить пресет '{preset_name}'?",
                                           QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
    if reply == QtWidgets.QMessageBox.StandardButton.No:
        return

    project_data = main_window.get_project_data()
    presets = project_data.get("region_presets", {})
    preset_to_delete = presets.pop(preset_name, None)

    if preset_to_delete:
        project_path = Path(main_window.current_project_path)
        for key in ["landscape_graph", "climate_graph", "biome_graph"]:
            try:
                (project_path / preset_to_delete[key]).unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Could not delete file: {e}")

    if project_data.get("active_preset_name") == preset_name:
        project_data["active_preset_name"] = "default"

    on_save_project(main_window, project_data)
    main_window._load_presets_list()
    main_window.statusBar.showMessage(f"Пресет '{preset_name}' удален.", 4000)

