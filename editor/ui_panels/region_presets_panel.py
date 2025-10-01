# ==============================================================================
# Файл: editor/ui_panels/region_presets_panel.py
# Назначение: «Пресеты региона» — V2-виджет + независимое окно; док (legacy).
#
# ВЕРСИЯ 2.0:
#   - NEW: make_region_presets_widget(main_window)  — встраиваемый виджет (без док-рамки)
#   - NEW: open_region_presets_window(main_window)  — отдельное окно (меню «Пресеты»)
#
# Принципы:
#   - UI-слой только шлёт сигналы, бизнес-логика остаётся в main_window.
#   - Сигналы/хелперы: set_presets(names), current_preset(), select_preset(name).
#   - Кнопки «Загрузить/Сохранить/Удалить/Обновить», поиск и двойной клик для загрузки.
# ==============================================================================

from __future__ import annotations
from typing import List, Optional

from PySide6 import QtWidgets, QtCore, QtGui


class RegionPresetsWidget(QtWidgets.QWidget):
    # Сигналы — привяжешь к своим хэндлерам в main_window
    load_requested = QtCore.Signal(str)          # имя пресета
    save_as_requested = QtCore.Signal(str)       # имя (из поля ввода)
    delete_requested = QtCore.Signal(str)        # имя пресета
    refresh_requested = QtCore.Signal()          # пересканировать список
    create_from_current_requested = QtCore.Signal(str)  # имя (из поля ввода)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RegionPresetsWidget")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Верхняя строка: поиск
        search_lay = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setPlaceholderText("Поиск пресетов…")
        self.search_edit.textChanged.connect(self._apply_filter)
        search_lay.addWidget(self.search_edit, 1)

        self.refresh_btn = QtWidgets.QToolButton(self)
        self.refresh_btn.setText("↻")
        self.refresh_btn.setToolTip("Обновить список")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        search_lay.addWidget(self.refresh_btn, 0)

        root.addLayout(search_lay)

        # Список пресетов
        self.list = QtWidgets.QListWidget(self)
        self.list.setObjectName("RegionPresetsList")
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.list.itemDoubleClicked.connect(self._on_activate_item)
        root.addWidget(self.list, 1)

        # Ввод имени (для «Сохранить как…» / «Создать из текущего»)
        name_lay = QtWidgets.QHBoxLayout()
        name_lay.addWidget(QtWidgets.QLabel("Имя:", self), 0)
        self.name_edit = QtWidgets.QLineEdit(self)
        self.name_edit.setPlaceholderText("новое_имя_пресета")
        name_lay.addWidget(self.name_edit, 1)
        root.addLayout(name_lay)

        # Кнопки действий
        btns = QtWidgets.QHBoxLayout()

        self.load_btn = QtWidgets.QPushButton("Загрузить", self)
        self.load_btn.clicked.connect(self._on_click_load)
        btns.addWidget(self.load_btn)

        self.save_as_btn = QtWidgets.QPushButton("Сохранить как…", self)
        self.save_as_btn.clicked.connect(self._on_click_save_as)
        btns.addWidget(self.save_as_btn)

        self.create_btn = QtWidgets.QPushButton("Создать...", self)  # Переименовали переменную и текст
        self.create_btn.clicked.connect(self._on_click_create_from_current)  # Сигнал тот же
        btns.addWidget(self.create_btn)  # Добавляем новую кнопку

        self.delete_btn = QtWidgets.QPushButton("Удалить", self)
        self.delete_btn.clicked.connect(self._on_click_delete)
        btns.addWidget(self.delete_btn)

        root.addLayout(btns)

        # Подвал (подсказка)
        hint = QtWidgets.QLabel("Двойной клик — загрузить пресет. Enter — загрузить выбранный.")
        hint.setStyleSheet("color:#aaa; font-size:11px;")
        root.addWidget(hint)

        # Горячие клавиши
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Return), self, activated=self._on_click_load)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Enter), self, activated=self._on_click_load)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self._on_click_delete)

        # Данные
        self._all_names: List[str] = []

    # ------------------------------- публичные методы для интеграции

    def set_presets(self, names: List[str]) -> None:
        """Полностью заменить список доступных пресетов (до фильтра)."""
        self._all_names = list(sorted(set(names), key=str.lower))
        self._apply_filter(self.search_edit.text())

    def current_preset(self) -> Optional[str]:
        """Текущее выбранное имя в списке (или None)."""
        it = self.list.currentItem()
        return it.text() if it else None

    def select_preset(self, name: str) -> None:
        """Выделить пресет в списке по имени (если есть)."""
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.text() == name:
                self.list.setCurrentItem(it)
                self.list.scrollToItem(it, QtWidgets.QAbstractItemView.PositionAtCenter)
                return

    # ------------------------------- приватные слои UI → сигналы

    def _apply_filter(self, text: str) -> None:
        text = (text or "").strip().lower()
        self.list.clear()
        for n in self._all_names:
            if not text or text in n.lower():
                self.list.addItem(QtWidgets.QListWidgetItem(n))

    def _on_activate_item(self, it: QtWidgets.QListWidgetItem) -> None:
        if it:
            self.load_requested.emit(it.text())

    def _on_click_load(self) -> None:
        name = self.current_preset()
        if name:
            self.load_requested.emit(name)

    def _on_click_save_as(self) -> None:
        name = self.name_edit.text().strip()
        if name:
            self.save_as_requested.emit(name)

    def _on_click_create_from_current(self) -> None:
        name = self.name_edit.text().strip()
        if name:
            self.create_from_current_requested.emit(name)

    def _on_click_delete(self) -> None:
        name = self.current_preset()
        if name:
            self.delete_requested.emit(name)


# ------------------------------------------------------------------------------ V2 фабрика виджета

def make_region_presets_widget(main_window) -> RegionPresetsWidget:
    """
    Возвращает встраиваемый виджет пресетов.
    Подписки на бизнес-логику делаем здесь, если у main_window есть соответствующие методы.
    """
    w = RegionPresetsWidget(parent=main_window)

    # Автопривязка к методам main_window, если они определены
    if hasattr(main_window, "action_load_region_preset"):
        w.load_requested.connect(main_window.action_load_region_preset)      # (name) -> None

    if hasattr(main_window, "action_save_region_preset_as"):
        w.save_as_requested.connect(main_window.action_save_region_preset_as)  # (name) -> None

    if hasattr(main_window, "action_delete_region_preset"):
        w.delete_requested.connect(main_window.action_delete_region_preset)  # (name) -> None

    if hasattr(main_window, "action_refresh_region_presets"):
        w.refresh_requested.connect(main_window.action_refresh_region_presets) # () -> None

    if hasattr(main_window, "action_create_region_preset_from_current"):
        w.create_from_current_requested.connect(main_window.action_create_region_preset_from_current)  # (name) -> None

    # Если есть метод, который возвращает текущий список — заполним
    if hasattr(main_window, "get_region_preset_names"):
        try:
            names = list(main_window.get_region_preset_names())
            w.set_presets(names)
        except Exception:
            pass

    return w


# ------------------------------------------------------------------------------ Отдельное окно (меню «Пресеты»)

def open_region_presets_window(main_window) -> None:
    """
    Открыть независимое окно «Пресеты региона».
    Повторные вызовы — поднимают уже открытое окно.
    """
    win = getattr(main_window, "_region_presets_win", None)
    if isinstance(win, QtWidgets.QMainWindow) and not win.isHidden():
        win.show(); win.raise_(); win.activateWindow()
        return

    win = QtWidgets.QMainWindow(main_window)
    win.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
    win.setWindowTitle("Пресеты региона")

    content = make_region_presets_widget(main_window)
    win.setCentralWidget(content)
    win.resize(700, 520)

    main_window._region_presets_win = win
    win.show()
