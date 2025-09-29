# ==============================================================================
# Файл: editor/menu.py
# Назначение: Построение меню приложения (V2-ready).
#
# Меню:
#   - Файл:      Выход
#   - Правка:    Отменить/Повторить (заглушки, при желании подвяжешь)
#   - Вид:       Показать/скрыть Левую палитру (F1), Правый Outliner (F2)
#   - Пресеты:   Загрузить, Сохранить…, Открыть пресеты региона…
#
# Примечания:
#   - "Открыть пресеты региона…" открывает независимое окно с виджетом пресетов.
#     Если у MainWindow есть метод open_region_presets_window — используем его.
#     Иначе падаем на локальную функцию _open_region_presets_window_fallback.
# ==============================================================================

from __future__ import annotations
from PySide6 import QtWidgets, QtCore

# Фабрика виджета пресетов (для запасного варианта)
try:
    from editor.ui_panels.region_presets_panel import make_region_presets_widget
except Exception:
    make_region_presets_widget = None  # type: ignore


def _open_region_presets_window_fallback(mw: QtWidgets.QMainWindow) -> None:
    """
    Запасной способ открыть окно пресетов региона,
    если у MainWindow нет метода open_region_presets_window().
    """
    if make_region_presets_widget is None:
        QtWidgets.QMessageBox.warning(mw, "Пресеты региона",
                                      "Функция пресетов региона недоступна.")
        return

    # Если окно уже открыто — поднимем его
    win = getattr(mw, "_region_presets_win", None)
    if isinstance(win, QtWidgets.QMainWindow) and not win.isHidden():
        win.show(); win.raise_(); win.activateWindow()
        return

    win = QtWidgets.QMainWindow(mw)
    win.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
    win.setWindowTitle("Пресеты региона")
    win.setCentralWidget(make_region_presets_widget(win))
    win.resize(700, 520)
    mw._region_presets_win = win
    win.show()


def _safe(mw: QtWidgets.QMainWindow, name: str):
    """Вернёт вызываемый метод mw.name или no-op, если его нет."""
    fn = getattr(mw, name, None)
    if callable(fn):
        return fn
    return lambda *a, **kw: None


def build_menus(mw: QtWidgets.QMainWindow) -> None:
    mb = mw.menuBar()
    mb.clear()

    # ---------------- Файл
    m_file = mb.addMenu("Файл")
    act_exit = m_file.addAction("Выход")
    act_exit.setShortcut("Ctrl+Q")
    act_exit.triggered.connect(mw.close)

    # ---------------- Проект
    m_project = mb.addMenu("Проект")
    act_change = m_project.addAction("Сменить проект…")
    act_change.triggered.connect(_safe(mw, "open_project_manager"))

    # ---------------- Правка (заглушки под Undo/Redo — подвяжешь позже)
    m_edit = mb.addMenu("Правка")
    act_undo = m_edit.addAction("Отменить")
    act_undo.setShortcut("Ctrl+Z")
    act_undo.triggered.connect(_safe(mw, "action_undo"))
    act_redo = m_edit.addAction("Повторить")
    act_redo.setShortcut("Ctrl+Y")
    act_redo.triggered.connect(_safe(mw, "action_redo"))

    # ---------------- Вид
    m_view = mb.addMenu("Вид")

    act_toggle_left = m_view.addAction("Показать/скрыть левую палитру")
    act_toggle_left.setShortcut("F1")
    act_toggle_left.triggered.connect(_safe(mw, "toggle_left_palette"))

    act_toggle_right = m_view.addAction("Показать/скрыть правый Outliner")
    act_toggle_right.setShortcut("F2")
    act_toggle_right.triggered.connect(_safe(mw, "toggle_right_outliner"))

    m_view.addSeparator()

    # Можно добавить сохранение/восстановление раскладки, если используешь saveState/restoreState
    act_save_layout = m_view.addAction("Сохранить раскладку")
    act_save_layout.triggered.connect(_safe(mw, "save_layout_state"))

    act_restore_layout = m_view.addAction("Восстановить раскладку")
    act_restore_layout.triggered.connect(_safe(mw, "restore_layout_state"))

    # ---------------- Пресеты
    m_presets = mb.addMenu("Пресеты")

    act_load = m_presets.addAction("Загрузить пресет…")
    act_load.triggered.connect(_safe(mw, "action_load_preset"))

    act_save = m_presets.addAction("Сохранить пресет…")
    act_save.triggered.connect(_safe(mw, "action_save_preset"))

    m_presets.addSeparator()

    act_open_region = m_presets.addAction("Открыть пресеты региона…")
    # Если есть прямой метод у MW — используем его; иначе форсим fallback
    if callable(getattr(mw, "open_region_presets_window", None)):
        act_open_region.triggered.connect(mw.open_region_presets_window)  # type: ignore
    else:
        act_open_region.triggered.connect(lambda: _open_region_presets_window_fallback(mw))
