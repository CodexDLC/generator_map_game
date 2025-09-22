# ==============================================================================
# Файл: editor/actions/progress_dialog.py
# Назначение: Немодальный диалог прогресса + встроенный лог (раскрывающийся).
# Совместим с вызовами dlg.open() из compute_actions.py
# ==============================================================================

from __future__ import annotations
from PySide6 import QtWidgets, QtCore

class ProgressDialog(QtWidgets.QDialog):
    """
    Немодальный диалог:
      - НЕ блокирует главное окно (setModal(False))
      - Кнопка "Отмена" (compute_actions сам коннектит её к worker.cancel)
      - Методы: update_progress(percent:int, message:str), set_busy(bool),
                append_log(str), log_progress(percent:int, message:str)
      - Встроенный лог (QPlainTextEdit) скрыт по умолчанию, включается кнопкой.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("Генерация…")
        self.setModal(False)  # мы используем dlg.open()
        self.setMinimumSize(420, 160)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # ── Разметка
        layout = QtWidgets.QVBoxLayout(self)

        self.status_label = QtWidgets.QLabel("Подготовка…", self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Кнопки: показать детали + Отмена
        row = QtWidgets.QHBoxLayout()
        self.details_btn = QtWidgets.QToolButton(self)
        self.details_btn.setText("Показать детали")
        self.details_btn.setCheckable(True)
        row.addWidget(self.details_btn)
        row.addStretch(1)
        self.cancel_button = QtWidgets.QPushButton("Отмена", self)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)

        # Зона лога (скрыта по умолчанию)
        self.log_area = QtWidgets.QPlainTextEdit(self)
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumBlockCount(2000)  # авто-обрезание истории
        self.log_area.setVisible(False)
        layout.addWidget(self.log_area)

        # Переключатель видимости лога
        self.details_btn.toggled.connect(self._on_toggle_details)

        self.setWindowFlag(QtCore.Qt.WindowType.WindowCloseButtonHint, True)
        self.setEscapeClosesDialog(True)

        # для авто-скролла не держим курсор в начале
        self._auto_scroll = True

    # ----------------- Публичный API -----------------

    @QtCore.Slot(int, str)
    def update_progress(self, percent: int, message: str) -> None:
        """Обновляет прогресс и подпись."""
        try:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(percent))
        except Exception:
            pass
        self.status_label.setText(str(message))

    @QtCore.Slot(bool)
    def set_busy(self, busy: bool) -> None:
        """Включить «бегущую ленту» или нормальный режим 0..100."""
        if busy:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)

    @QtCore.Slot(str)
    def append_log(self, line: str) -> None:
        """Добавить строку в лог, при необходимости прокрутить вниз."""
        if not line:
            return
        self.log_area.appendPlainText(line)
        if self._auto_scroll:
            self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    @QtCore.Slot(int, str)
    def log_progress(self, percent: int, message: str) -> None:
        """
        Универсальный слот: обновить прогресс И заодно записать лог.
        compute_actions может коннектить worker.progress прямо сюда.
        """
        self.update_progress(percent, message)
        self.append_log(f"{percent:3d}% | {message}")

    # ----------------- Вспомогательное -----------------

    def _on_toggle_details(self, checked: bool) -> None:
        self.log_area.setVisible(checked)
        self.details_btn.setText("Скрыть детали" if checked else "Показать детали")

    def setEscapeClosesDialog(self, enabled: bool) -> None:
        if enabled:
            self.installEventFilter(self)
        else:
            self.removeEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.KeyPress and event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
            return True
        return super().eventFilter(obj, event)
