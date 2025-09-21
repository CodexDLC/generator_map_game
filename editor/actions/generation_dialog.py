# ==============================================================================
# Файл: editor/actions/generation_dialog.py
# Назначение: Диалоговое окно для запуска финальной генерации мира.
# ==============================================================================
from PySide6 import QtWidgets


class GenerationDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, project_name=""):
        super().__init__(parent)
        self.setWindowTitle("Настройки Генерации Мира")

        self.layout = QtWidgets.QFormLayout(self)

        # Отображаем имя проекта (нельзя редактировать)
        self.project_label = QtWidgets.QLabel(f"<b>{project_name}</b>")
        self.layout.addRow("Проект:", self.project_label)

        # Поле для радиуса генерации
        self.radius_input = QtWidgets.QSpinBox()
        self.radius_input.setRange(0, 10)  # 0 = 1x1, 1 = 3x3, 2 = 5x5 регионов
        self.radius_input.setValue(1)
        self.layout.addRow("Радиус генерации (в регионах):", self.radius_input)

        # Поле для выбора папки артефактов
        self.artifacts_path_input = QtWidgets.QLineEdit()
        self.artifacts_path_button = QtWidgets.QPushButton("Выбрать...")
        self.artifacts_path_button.clicked.connect(self._select_artifacts_path)
        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(self.artifacts_path_input)
        path_layout.addWidget(self.artifacts_path_button)
        self.layout.addRow("Папка для артефактов:", path_layout)

        # Кнопки OK и Cancel
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def _select_artifacts_path(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Выберите папку для артефактов")
        if path:
            self.artifacts_path_input.setText(path)

    def get_values(self):
        """Возвращает выбранные пользователем значения."""
        return {
            "radius": self.radius_input.value(),
            "artifacts_path": self.artifacts_path_input.text()
        }