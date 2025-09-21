# ==============================================================================
# Файл: editor/actions/progress_dialog.py
# Назначение: Диалоговое окно с прогресс-баром.
# ==============================================================================
from PySide6 import QtWidgets, QtCore


class ProgressDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Генерация Мира...")
        self.setModal(True)  # Блокируем основное окно
        self.setFixedSize(400, 120)

        self.layout = QtWidgets.QVBoxLayout(self)

        self.status_label = QtWidgets.QLabel("Инициализация...")
        self.layout.addWidget(self.status_label)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.layout.addWidget(self.progress_bar)

        self.cancel_button = QtWidgets.QPushButton("Отмена")
        self.layout.addWidget(self.cancel_button)

        # Не даем пользователю закрыть окно крестиком
        self.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)

    def update_progress(self, percent, message):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)