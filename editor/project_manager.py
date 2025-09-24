# ==============================================================================
# Файл: editor/project_manager.py
# Назначение: Полноценный лончер проектов со сканированием папки.
# ВЕРСИЯ 2.0: Полная переработка.
# ==============================================================================
import logging
import json
import os
from pathlib import Path
from PySide6 import QtWidgets, QtCore

from .actions.project_actions import on_new_project, on_open_project

# Константы для сохранения настроек
ORGANIZATION_NAME = "MyGameStudio"
APPLICATION_NAME = "WorldEditor"
SETTINGS_KEY_PROJECTS_DIR = "projects_directory"

logger = logging.getLogger(__name__)

class ProjectManagerDialog(QtWidgets.QDialog):
    """
    Диалог, который сканирует папку по умолчанию, показывает список проектов
    и позволяет создавать, открывать и управлять проектами.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("Initializing ProjectManagerDialog.")
        self.setWindowTitle("Менеджер Проектов")
        self.setMinimumSize(600, 400)
        self.settings = QtCore.QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
        self.projects_dir = self.settings.value(SETTINGS_KEY_PROJECTS_DIR, "")
        self.selected_project_path = None

        self._setup_ui()
        self._connect_signals()
        self._initial_load()

    def _setup_ui(self):
        """Создает весь интерфейс лончера."""
        main_layout = QtWidgets.QVBoxLayout(self)

        # --- Верхняя панель с кнопками ---
        top_bar_layout = QtWidgets.QHBoxLayout()
        self.new_project_button = QtWidgets.QPushButton("Создать новый...")
        self.open_other_button = QtWidgets.QPushButton("Открыть другой...")
        self.change_dir_button = QtWidgets.QPushButton("Сменить папку...")
        top_bar_layout.addWidget(self.new_project_button)
        top_bar_layout.addWidget(self.open_other_button)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.change_dir_button)
        main_layout.addLayout(top_bar_layout)

        # --- Список проектов ---
        self.project_list_widget = QtWidgets.QListWidget()
        self.project_list_widget.setIconSize(QtCore.QSize(32, 32))
        main_layout.addWidget(self.project_list_widget)

        # --- Нижняя панель ---
        bottom_bar_layout = QtWidgets.QHBoxLayout()
        self.projects_dir_label = QtWidgets.QLabel(f"Папка проектов: {self.projects_dir or 'Не выбрана'}")
        self.projects_dir_label.setStyleSheet("color: #888;")
        self.open_selected_button = QtWidgets.QPushButton("Открыть выбранный")
        self.open_selected_button.setEnabled(False)  # Выключена по умолчанию
        self.close_button = QtWidgets.QPushButton("Выход")

        bottom_bar_layout.addWidget(self.projects_dir_label)
        bottom_bar_layout.addStretch()
        bottom_bar_layout.addWidget(self.open_selected_button)
        bottom_bar_layout.addWidget(self.close_button)
        main_layout.addLayout(bottom_bar_layout)

    def _connect_signals(self):
        """Подключает все сигналы к слотам."""
        self.new_project_button.clicked.connect(self.handle_new_project)
        self.open_other_button.clicked.connect(self.handle_open_other)
        self.change_dir_button.clicked.connect(self.handle_change_dir)
        self.open_selected_button.clicked.connect(self.handle_open_selected)
        self.close_button.clicked.connect(self.reject)
        self.project_list_widget.itemSelectionChanged.connect(
            lambda: self.open_selected_button.setEnabled(True)
        )
        self.project_list_widget.itemDoubleClicked.connect(self.handle_open_selected)

    def _initial_load(self):
        """Первоначальная загрузка: проверяет папку и сканирует проекты."""
        if not self.projects_dir or not os.path.exists(self.projects_dir):
            logger.warning("Projects directory is not set or does not exist. Asking user for a new one.")
            self._ask_for_projects_directory()
        else:
            logger.info(f"Found projects directory: {self.projects_dir}")
            self.scan_for_projects()

    def _ask_for_projects_directory(self):
        """Запрашивает у пользователя базовую папку для проектов."""
        QtWidgets.QMessageBox.information(
            self, "Настройка", "Пожалуйста, выберите основную папку, где будут храниться ваши проекты."
        )
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Выберите папку для проектов"
        )
        if directory:
            self.projects_dir = directory
            self.settings.setValue(SETTINGS_KEY_PROJECTS_DIR, self.projects_dir)
            self.projects_dir_label.setText(f"Папка проектов: {self.projects_dir}")
            logger.info(f"User selected new projects directory: {self.projects_dir}")
            self.scan_for_projects()
        else:
            logger.warning("User cancelled the directory selection dialog.")
            reply = QtWidgets.QMessageBox.warning(
                self, "Папка не выбрана",
                "Папка проектов не была выбрана. Без нее работа невозможна.\nВы хотите выбрать папку сейчас?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self._ask_for_projects_directory()
            else:
                self.reject()  # Закрываем лончер

    def scan_for_projects(self):
        """Сканирует папку `projects_dir` на наличие подпапок с `project.json`."""
        self.project_list_widget.clear()
        if not self.projects_dir:
            return

        project_count = 0
        for item_name in os.listdir(self.projects_dir):
            item_path = Path(self.projects_dir) / item_name
            project_file = item_path / "project.json"
            if item_path.is_dir() and project_file.exists():
                project_count += 1
                try:
                    with open(project_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        project_name = data.get("project_name", item_name)
                except Exception:
                    project_name = f"{item_name} (ошибка чтения)"

                list_item = QtWidgets.QListWidgetItem(project_name)
                list_item.setData(QtCore.Qt.ItemDataRole.UserRole, str(item_path))  # Сохраняем путь в элементе списка
                self.project_list_widget.addItem(list_item)

        logger.info(f"Scan complete. Found {project_count} valid projects.")

    def handle_change_dir(self):
        logger.debug("User clicked 'Change Directory' button.")
        self._ask_for_projects_directory()

    def handle_new_project(self):
        logger.debug("User clicked 'New Project' button.")
        project_path = on_new_project(self)
        if project_path:
            self.selected_project_path = project_path
            self.accept()

    def handle_open_other(self):
        logger.debug("User clicked 'Open Other' button.")
        project_path = on_open_project(self)
        if project_path:
            self.selected_project_path = project_path
            self.accept()

    def handle_open_selected(self):
        """Открывает проект, выбранный в списке."""
        selected_items = self.project_list_widget.selectedItems()
        if not selected_items:
            return

        project_path = selected_items[0].data(QtCore.Qt.ItemDataRole.UserRole)
        logger.info(f"User selected project '{project_path}' to open.")
        self.selected_project_path = project_path
        self.accept()


def show_project_manager() -> str | None:
    """
    Фабричная функция для запуска лончера.
    """
    logger.info("Showing project manager...")
    dialog = ProjectManagerDialog()
    result_code = dialog.exec()

    if result_code == QtWidgets.QDialog.DialogCode.Accepted:
        logger.info(f"Project manager accepted. Selected project: {dialog.selected_project_path}")
        return dialog.selected_project_path
    else:
        logger.info("Project manager was closed or cancelled.")
        return None