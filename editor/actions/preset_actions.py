# editor/actions/preset_actions.py
import json
import logging
from pathlib import Path

from editor.graph_utils import create_default_graph_session

logger = logging.getLogger(__name__)


def create_new_preset_files(project_path: str, preset_name: str) -> dict:
    """Создает 3 .json файла для нового пресета с нодами по умолчанию."""
    pipelines_dir = Path(project_path) / "pipelines"
    pipelines_dir.mkdir(exist_ok=True)

    # --- ИЗМЕНЕНИЕ ---
    # Получаем 100% корректный json вместо самописного
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


def load_preset_into_graphs(main_window, preset_info: dict):
    """Загружает 3 файла графов из пресета в соответствующие вкладки."""
    project_path = Path(main_window.current_project_path)

    layer_map = {
        "Ландшафт": "landscape_graph",
        "Климат (Заглушка)": "climate_graph",
        "Биомы (Заглушка)": "biome_graph"
    }

    for tab_name, graph_key in layer_map.items():
        graph = main_window.graphs.get(tab_name)
        graph_path_str = preset_info.get(graph_key)

        if not graph or not graph_path_str:
            continue

        graph_path = project_path / graph_path_str
        graph.clear_session()

        if graph_path.exists():
            try:
                # --- НАЧАЛО ИЗМЕНЕНИЯ: Улучшенная загрузка ---
                with open(graph_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Если файл пустой или не содержит нод, создаем дефолтные
                if not data or not data.get("nodes"):
                    input_node = graph.create_node('Ландшафт.Пайплайн.WorldInputNode', name='Вход', pos=(-300, 0))
                    output_node = graph.create_node('Ландшафт.Пайплайн.OutputNode', name='Выход', pos=(100, 0))
                    input_node.set_output(0, output_node.input(0))
                else:
                    graph.deserialize_session(data)
                # --- КОНЕЦ ИЗМЕНЕНИЯ ---
            except Exception as e:
                logger.error(f"Failed to load graph file {graph_path}: {e}")