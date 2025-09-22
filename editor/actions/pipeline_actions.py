# ==============================================================================
# Файл: editor/actions/pipeline_actions.py
# Назначение: Сохранение/загрузка пайплайнов (графов) с безопасной записью,
#             стартом из папки проекта, запоминанием последней директории.
# ==============================================================================

from __future__ import annotations

import json
import os
from pathlib import Path
from PySide6 import QtWidgets, QtCore


# ------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------

def _project_paths(main_window) -> tuple[Path | None, Path | None]:
    """
    Возвращает (project_path, pipelines_dir) если проект открыт, иначе (None, None).
    """
    proj = getattr(main_window, "current_project_path", None)
    if not proj:
        return None, None
    project_path = Path(proj)
    pipelines_dir = project_path / "pipelines"
    return project_path, pipelines_dir


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _remember_dir(kind: str, directory: Path) -> None:
    s = QtCore.QSettings("WorldEditor", "Generator")
    s.setValue(f"{kind}_last_dir", str(directory))


def _recall_dir(kind: str) -> Path | None:
    s = QtCore.QSettings("WorldEditor", "Generator")
    v = s.value(f"{kind}_last_dir", "")
    if v:
        try:
            p = Path(v)
            if p.exists():
                return p
        except Exception:
            pass
    return None


def _atomic_write_json(path: Path, data: dict) -> None:
    """
    Безопасная запись JSON: сначала .tmp, затем rename.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _ensure_json_suffix(path_str: str) -> str:
    p = Path(path_str)
    if p.suffix.lower() != ".json":
        p = p.with_suffix(".json")
    return str(p)


# ------------------------------------------------------------------------------
# actions
# ------------------------------------------------------------------------------

def on_save_pipeline(main_window):
    """
    Сохранение текущей сцены графа в JSON.
    - Если открыт проект: по умолчанию <project>/pipelines/<имя_проекта>.json
    - Если проект не открыт: стартуем из последней использованной папки или домашней.
    - Всегда добавляем .json, пишем атомарно.
    """
    graph = getattr(main_window, "graph", None)
    if graph is None:
        QtWidgets.QMessageBox.warning(main_window, "Сохранение",
                                      "Граф не инициализирован.")
        return

    project_path, pipelines_dir = _project_paths(main_window)
    if project_path and pipelines_dir:
        _ensure_dir(pipelines_dir)
        default_name = f"{project_path.name}.json"
        start_dir = str(pipelines_dir / default_name)
    else:
        last = _recall_dir("pipeline_save") or Path.home()
        start_dir = str(last / "pipeline.json")

    file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
        main_window,
        "Сохранить пайплайн",
        start_dir,
        "JSON Files (*.json)"
    )
    if not file_path:
        return

    file_path = _ensure_json_suffix(file_path)

    try:
        data = graph.serialize_session()
        _atomic_write_json(Path(file_path), data)
        main_window.statusBar.showMessage(f"Пайплайн сохранён: {file_path}", 5000)
        _remember_dir("pipeline_save", Path(file_path).parent)
        print(f"[Pipeline] saved -> {file_path}")
    except Exception as e:
        main_window.statusBar.showMessage(f"Ошибка сохранения: {e}", 6000)
        QtWidgets.QMessageBox.critical(main_window, "Ошибка сохранения", str(e))


def on_load_pipeline(main_window):
    """
    Загрузка сцены графа из JSON.
    - Если открыт проект: по умолчанию <project>/pipelines
    - Иначе: последняя использованная папка или домашняя.
    - Перед загрузкой чистим текущую сессию.
    """
    graph = getattr(main_window, "graph", None)
    if graph is None:
        QtWidgets.QMessageBox.warning(main_window, "Загрузка",
                                      "Граф не инициализирован.")
        return

    _, pipelines_dir = _project_paths(main_window)
    if pipelines_dir and pipelines_dir.exists():
        start_dir = str(pipelines_dir)
    else:
        start_dir = str(_recall_dir("pipeline_load") or Path.home())

    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        main_window,
        "Загрузить пайплайн",
        start_dir,
        "JSON Files (*.json)"
    )
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        graph.clear_session()
        # Важно: к этому моменту все классы нод уже должны быть зарегистрированы!
        graph.deserialize_session(graph_data)

        main_window.statusBar.showMessage(f"Пайплайн загружен: {file_path}", 5000)
        _remember_dir("pipeline_load", Path(file_path).parent)
        print(f"[Pipeline] loaded <- {file_path}")
    except Exception as e:
        main_window.statusBar.showMessage(f"Ошибка загрузки: {e}", 6000)
        QtWidgets.QMessageBox.critical(main_window, "Ошибка загрузки", str(e))
