# ==============================================================================
# editor/ui_panels/accordion_properties.py
# ВЕРСИЯ 3.3 (УЛУЧШЕНИЕ UX):
# - FIX: Гарантирована работа вертикальной прокрутки при большом кол-ве свойств.
# - NEW: Добавлен композитный виджет SliderSpinCombo для удобной настройки
#   параметров в диапазоне [0..1] с помощью ползунка.
# ==============================================================================

from __future__ import annotations

import random
from typing import Dict, Optional, Any, List

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt

from editor.theme import PALETTE
from editor.custom_graph import CustomNodeGraph
from editor.nodes.base_node import GeneratorNode


# ==============================================================================
# НОВЫЙ ВИДЖЕТ ДЛЯ РАБОТЫ С СИДАМИ
# ==============================================================================
class SeedWidget(QtWidgets.QWidget):
    """Комбинированный виджет для сида: поле ввода, кнопка "🎲" и история."""
    valueChanged = QtCore.Signal(float)
    editingFinished = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._block_signals = False

        self.spinbox = QtWidgets.QDoubleSpinBox()
        self.spinbox.setRange(0, 4294967295)
        self.spinbox.setDecimals(0)
        self.spinbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.generate_btn = QtWidgets.QToolButton()
        self.generate_btn.setText("🎲")
        self.generate_btn.setToolTip("Сгенерировать новый случайный сид")

        self.history_btn = QtWidgets.QToolButton()
        self.history_btn.setText("📖")
        self.history_btn.setToolTip("Показать историю сидов")
        self.history_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.history_menu = QtWidgets.QMenu(self)
        self.history_btn.setMenu(self.history_menu)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.spinbox, 1)
        layout.addWidget(self.generate_btn)
        layout.addWidget(self.history_btn)

        self.generate_btn.clicked.connect(self.generate_new_seed)
        self.spinbox.valueChanged.connect(self.valueChanged.emit)
        self.spinbox.editingFinished.connect(self.editingFinished.emit)

    def generate_new_seed(self):
        new_seed = random.randint(0, 4294967295)
        self.spinbox.setValue(new_seed)
        self.editingFinished.emit()  # Сигнализируем о завершении редактирования

    def value(self) -> int:
        return int(self.spinbox.value())

    def setValue(self, value: int):
        self.spinbox.setValue(value)

    def set_history(self, history: List[int]):
        self.history_menu.clear()
        for seed in history:
            action = QtGui.QAction(str(seed), self)
            action.triggered.connect(lambda _, s=seed: self.setValue(s))
            self.history_menu.addAction(action)

# ==============================================================================
# НОВЫЙ КОМПОЗИТНЫЙ ВИДЖЕТ: ПОЛЗУНОК + ПОЛЕ ВВОДА (с изменениями)
# ==============================================================================
class SliderSpinCombo(QtWidgets.QWidget):
    """
    Комбинированный виджет, состоящий из слайдера (QSlider) и числового
    поля (QDoubleSpinBox) для точной настройки значений в диапазоне [0, 1].
    """
    # --- ИЗМЕНЕНИЕ: Сигнал теперь называется по-другому для ясности ---
    editingFinished = QtCore.Signal()
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._block_signals = False

        # --- Создание и компоновка виджетов без изменений ---
        self.slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)

        self.spinbox = QtWidgets.QDoubleSpinBox()
        self.spinbox.setRange(0.0, 1.0)
        self.spinbox.setDecimals(3)
        self.spinbox.setSingleStep(0.01)
        self.spinbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spinbox.setFixedWidth(60)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.slider)
        layout.addWidget(self.spinbox)


        # --- ИЗМЕНЕНИЕ: Полностью новая логика сигналов ---
        # valueChanged больше не используется для отправки сигнала наружу
        self.slider.valueChanged.connect(self._on_slider_change)
        self.spinbox.valueChanged.connect(self._on_spinbox_change)
        
        # Сигнал editingFinished будет отправлен только когда пользователь
        # отпустит слайдер или закончит ввод в поле.
        self.slider.sliderReleased.connect(self.editingFinished.emit)
        self.spinbox.editingFinished.connect(self.editingFinished.emit)
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    def value(self) -> float:
        return self.spinbox.value()

    def setValue(self, value: float):
        value = max(0.0, min(1.0, float(value)))
        self._block_signals = True
        try:
            self.spinbox.setValue(value)
            self.slider.setValue(int(value * 1000))
        finally:
            self._block_signals = False
    
    @QtCore.Slot(int)
    def _on_slider_change(self, slider_value: int):
        if self._block_signals:
            return
        # Просто синхронизируем значение, но не отправляем сигнал
        float_value = slider_value / 1000.0
        self._block_signals = True
        self.spinbox.setValue(float_value)
        self._block_signals = False

    # --- ИЗМЕНЕНИЕ: Упрощенный слот для spinbox ---
    @QtCore.Slot(float)
    def _on_spinbox_change(self, spinbox_value: float):
        if self._block_signals:
            return
        # Просто синхронизируем значение, но не отправляем сигнал
        self._block_signals = True
        self.slider.setValue(int(spinbox_value * 1000))
        self._block_signals = False
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---


# ==============================================================================
# Фабричная функция (без изменений)
# ==============================================================================
def create_properties_widget(parent: QtWidgets.QWidget) -> "AccordionProperties":
    props = AccordionProperties(parent=parent)
    props.setObjectName("PropertiesAccordion")
    props.setMinimumWidth(360)
    props.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Expanding)
    return props


# ==============================================================================
# Основной класс виджета (с изменениями)
# ==============================================================================
class CollapsibleBox(QtWidgets.QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setObjectName("CollapsibleBox")
        self.setCheckable(True)
        self.setChecked(True)

        # --- НАЧАЛО ИЗМЕНЕНИЯ ---
        # Эта строка запрещает группе сжиматься по вертикали.
        # Теперь она будет требовать ровно столько места, сколько нужно её содержимому.
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Minimum)
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(6)

        self._content = QtWidgets.QWidget(self)
        lay.addWidget(self._content)

        self.body = QtWidgets.QFormLayout(self._content)
        self.body.setContentsMargins(4, 4, 4, 4)
        self.body.setSpacing(6)

        self.toggled.connect(self._content.setVisible)


class AccordionProperties(QtWidgets.QScrollArea):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("AccordionProperties")
        self.setWidgetResizable(True)

        self._graph: Optional[CustomNodeGraph] = None
        self._node: Optional[GeneratorNode] = None
        self._main_window: Optional[QtWidgets.QMainWindow] = None

        self._root = QtWidgets.QWidget()
        self._root.setStyleSheet(f"background-color: {PALETTE['dock_bg']};")
        self._vl = QtWidgets.QVBoxLayout(self._root)
        self._vl.setContentsMargins(6, 6, 6, 6)
        self._vl.setSpacing(8)

        # --- ИЗМЕНЕНИЕ ДЛЯ ПРОКРУТКИ ---
        # Мы НЕ добавляем addStretch(1) здесь. Растягивающийся элемент будет
        # добавлен в самом конце, после всех виджетов, в методе _rebuild.
        # Это гарантирует, что если контент превысит высоту, появится прокрутка.
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        self.setWidget(self._root)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

    # ... (методы set_graph, _on_graph_selection, clear_layout, set_node без изменений)
    def set_graph(self, graph: Optional[CustomNodeGraph], main_window: Optional[QtWidgets.QMainWindow] = None) -> None:
        self._main_window = main_window  # Сохраняем ссылку
        if self._graph is graph:
            return

        if self._graph:
            try:
                self._graph.selection_changed.disconnect(self._on_graph_selection)
            except (RuntimeError, TypeError):
                pass

        self._graph = graph
        if self._graph is None:
            return

        self._graph.selection_changed.connect(self._on_graph_selection)
        self._on_graph_selection(self._graph.selected_nodes())

    @QtCore.Slot(list)
    def _on_graph_selection(self, selected_nodes: list) -> None:
        node = None
        if selected_nodes and isinstance(selected_nodes[0], GeneratorNode):
            node = selected_nodes[0]

        self.set_node(node)

    def clear_layout(self):
        while self._vl.count():
            item = self._vl.takeAt(0)
            if item is None: continue
            w = item.widget()
            if w:
                w.deleteLater()
            layout = item.layout()
            if layout:
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    @QtCore.Slot(object)
    def set_node(self, node: Optional[GeneratorNode]):
        if self._node is node:
            return

        self._node = node
        self._rebuild()

    def _rebuild(self):
        self.clear_layout()

        node = self._node
        if not node:
            # Если нода не выбрана, добавляем растяжку, чтобы ничего не было
            self._vl.addStretch(1)
            return

        meta = node.properties_meta()

        if not meta:
            self._vl.addStretch(1)
            return

        groups: Dict[str, CollapsibleBox] = {}

        sorted_meta_items = sorted(meta.items(), key=lambda item: (
            item[1].get('group') or 'Params',
            item[0]
        ))

        for name, prop_meta in sorted_meta_items:
            if name in ('name', 'color', 'text_color', 'disabled'):
                continue

            group_name = prop_meta.get('group') or 'Params'

            if group_name not in groups:
                box = CollapsibleBox(group_name, self._root)
                groups[group_name] = box
                self._vl.addWidget(box)

            box = groups[group_name]

            widget = self._create_widget_for_property(node, name, prop_meta)
            if widget:
                label = prop_meta.get('label', name)
                box.body.addRow(label, widget)

        # --- ИЗМЕНЕНИЕ ДЛЯ ПРОКРУТКИ ---
        # Добавляем растяжку в самый конец, чтобы все группы прижимались кверху.
        self._vl.addStretch(1)
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    def _create_widget_for_property(self, node: GeneratorNode, name: str, meta: dict) -> Optional[QtWidgets.QWidget]:
        kind = meta.get('type')
        value = node.get_property(name)
        label = meta.get('label', name)
        update_slot = getattr(self._main_window, '_trigger_preview_update', None)

        is_float = kind in ('float', 'double', 'f')
        # --- ИЗМЕНЕНИЕ: Улучшенное и более общее условие для ползунка ---
        is_ratio = "(0..1)" in label or "(%)" in label or "ratio" in name.lower() or "lerp" in name.lower() or "gain" in name.lower() or "jitter" in name.lower() or "strength" in name.lower() or "amplitude" in name.lower()
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        if is_float and is_ratio:
            w = SliderSpinCombo()
            w.setValue(value)
            # Привязываем изменение значения к установке свойства ноды
            w.slider.valueChanged.connect(lambda val, nn=name, ww=w: node.set_property(nn, val / 1000.0))
            w.spinbox.valueChanged.connect(lambda val, nn=name, ww=w: node.set_property(nn, val))
            # А сигнал о завершении редактирования - к обновлению превью
            if update_slot:
                w.editingFinished.connect(update_slot)
            return w

        if kind == 'line':
            w = QtWidgets.QLineEdit()
            if name == 'name' and value is None:
                value = node.name()
            w.setText(str(value))
            w.editingFinished.connect(lambda nn=name, ww=w: node.set_property(nn, ww.text()))
            if update_slot:
                w.editingFinished.connect(update_slot)
            return w

        elif kind in ('int', 'i', 'float', 'double', 'f'):
            w = QtWidgets.QDoubleSpinBox()
            if is_float:
                w.setDecimals(meta.get('decimals', 3))
                w.setSingleStep(meta.get('step', 0.01))
                w.setRange(meta.get('range', (-1e12, 1e12))[0], meta.get('range', (-1e12, 1e12))[1])
            else:
                w.setDecimals(0)
                w.setSingleStep(meta.get('step', 1))
                w.setRange(meta.get('range', (-4294967295, 4294967295))[0],
                           meta.get('range', (-4294967295, 4294967295))[1])

            w.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            w.setAlignment(Qt.AlignmentFlag.AlignRight)
            w.setMaximumWidth(meta.get('width', 100))
            w.setValue(float(value or 0))
            # --- ИЗМЕНЕНИЕ: Привязываем разные сигналы ---
            w.valueChanged.connect(lambda val, nn=name: node.set_property(nn, val)) # Обновляем свойство сразу
            if update_slot:
                w.editingFinished.connect(update_slot) # А превью - по завершению
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---
            return w
        
        # --- НАЧАЛО НОВОГО БЛОКА ---
        elif kind == 'seed':
            w = SeedWidget()
            w.setValue(int(value or 0))

            # Заполняем историю
            history = node._seed_history.get(name, [])
            w.set_history(history)

            # Обновляем свойство ноды при изменении значения
            w.valueChanged.connect(lambda val, nn=name: node.set_property(nn, int(val)))

            # При завершении редактирования (клик по "🎲" или Enter)
            def on_finish():
                new_val = w.value()
                # 1. Добавляем в историю
                node.add_to_seed_history(name, new_val)
                # 2. Обновляем выпадающий список
                w.set_history(node._seed_history.get(name, []))
                # 3. Запускаем пересчет превью
                if update_slot:
                    update_slot()

            w.editingFinished.connect(on_finish)
            return w
        # --- КОНЕЦ НОВОГО БЛОКА ---

        elif kind == 'check':
            w = QtWidgets.QCheckBox()
            w.setChecked(bool(value))
            w.toggled.connect(lambda state, nn=name: node.set_property(nn, state))
            if update_slot:
                w.toggled.connect(update_slot)
            return w

        elif kind == 'combo':
            w = QtWidgets.QComboBox()
            items = [str(x) for x in meta.get('items', [])]
            w.addItems(items)
            if str(value) in items:
                w.setCurrentText(str(value))
            w.currentTextChanged.connect(lambda text, nn=name: node.set_property(nn, text))
            if update_slot:
                w.currentTextChanged.connect(update_slot)
            return w

        return None
