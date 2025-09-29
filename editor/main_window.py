# ==============================================================================
# Файл: main_window.py
# ВЕРСИЯ 5.5 (ИНТЕГРАЦИЯ): Полная интеграция управления пресетами.
# - Добавлена панель пресетов.
# - Реализованы методы для загрузки, сохранения и управления пресетами.
# - Все действия с пресетами теперь вызывают функции из preset_actions.py.
# ==============================================================================

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from PySide6 import QtWidgets, QtCore, QtGui

from editor.graph_runner import run_graph
from editor.nodes.height.io.output_node import OutputNode

from editor.theme import APP_STYLE_SHEET
from editor.ui_panels.accordion_properties import create_properties_widget
from editor.ui_panels.central_graph import create_bottom_work_area_v2
from editor.ui_panels.menu import build_menus
from editor.ui_panels.node_inspector import make_node_inspector_widget
# --- ИЗМЕНЕНИЕ: Импортируем панель пресетов ---
from editor.ui_panels.region_presets_panel import make_region_presets_widget
from editor.ui_panels.shortcuts import install_shortcuts
from editor.preview_widget import Preview3DWidget
from editor.project_manager import ProjectManager

# --- ИЗМЕНЕНИЕ: Импортируем действия для пресетов ---
from editor.actions import preset_actions

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs) -> None:
        project_path: Optional[str] = kwargs.pop("project_path", None)
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Редактор Миров")
        self.resize(1600, 900)

        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        self.project_manager = ProjectManager(self)

        # --- UI-компоненты ---
        self.graph = None
        self.preview_widget = None
        self.props_bin = None
        self.right_outliner = None
        self.left_palette = None
        self.node_inspector = None
        # --- ИЗМЕНЕНИЕ: Добавляем атрибут для виджета пресетов ---
        self.presets_widget = None

        # --- Виджеты параметров ---
        self.seed_input: QtWidgets.QSpinBox | None = None
        self.chunk_size_input: QtWidgets.QSpinBox | None = None
        self.region_size_in_chunks_input: QtWidgets.QSpinBox | None = None
        self.cell_size_input: QtWidgets.QDoubleSpinBox | None = None
        self.global_x_offset_input: QtWidgets.QDoubleSpinBox | None = None
        self.global_z_offset_input: QtWidgets.QDoubleSpinBox | None = None
        self.gn_scale_input: QtWidgets.QDoubleSpinBox | None = None
        self.gn_octaves_input: QtWidgets.QSpinBox | None = None
        self.gn_amp_input: QtWidgets.QDoubleSpinBox | None = None
        self.gn_ridge_checkbox: QtWidgets.QCheckBox | None = None

        self._build_ui()

        build_menus(self)
        install_shortcuts(self)

        if project_path:
            self.project_manager.load_project(project_path)

    def _build_ui(self) -> None:
        try:
            self.preview_widget = Preview3DWidget(self)
        except (ImportError, RuntimeError) as e:
            logger.exception(f"Не удалось создать Preview3DWidget: {e}")
            lbl = QtWidgets.QLabel("Preview widget failed to load")
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            self.preview_widget = lbl

        bottom_work_area, self.graph, self.left_palette, self.right_outliner = create_bottom_work_area_v2(self)

        tabs_left = self._create_left_tabs()

        # --- ИЗМЕНЕНИЕ: Панель свойств теперь создается отдельно ---
        from editor.ui_panels.accordion_properties import create_properties_widget
        self.props_bin = create_properties_widget(self)

        tabs_right = QtWidgets.QTabWidget()
        tabs_right.setDocumentMode(True)
        tabs_right.addTab(self.props_bin, "Свойства")

        tabs_right = self._create_right_tabs()
        top_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        top_splitter.addWidget(tabs_left)
        top_splitter.addWidget(self.preview_widget)
        top_splitter.addWidget(tabs_right)
        top_splitter.setStretchFactor(1, 1)
        top_splitter.setSizes([360, 900, 420])

        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_work_area)
        main_splitter.setSizes([int(self.height() * 0.55), int(self.height() * 0.45)])

        self.setCentralWidget(main_splitter)
        self._connect_components()

    def _create_right_tabs(self) -> QtWidgets.QTabWidget:
        """Создает правую панель с вкладками 'Параметры' и 'Инспектор'."""
        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("TopTabsRight")
        tabs.setDocumentMode(True)

        # Вкладка 1: Параметры генерации (Аккордеон)
        self.props_bin = create_properties_widget(self)
        tabs.addTab(self.props_bin, "Параметры")

        # Вкладка 2: Инспектор ноды (Имя, цвет, порты)
        self.node_inspector = make_node_inspector_widget(self)
        tabs.addTab(self.node_inspector, "Инспектор")

        return tabs

    def _create_project_params_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.seed_input = QtWidgets.QSpinBox()
        self.seed_input.setRange(0, 999999999)
        layout.addRow("Seed:", self.seed_input)

        self.chunk_size_input = QtWidgets.QSpinBox()
        self.chunk_size_input.setRange(16, 2048)
        self.chunk_size_input.setSingleStep(16)
        layout.addRow("Размер чанка:", self.chunk_size_input)

        self.region_size_in_chunks_input = QtWidgets.QSpinBox()
        self.region_size_in_chunks_input.setRange(1, 16)
        layout.addRow("Регион (в чанках):", self.region_size_in_chunks_input)

        self.cell_size_input = QtWidgets.QDoubleSpinBox()
        self.cell_size_input.setRange(0.1, 10.0)
        self.cell_size_input.setSingleStep(0.1)
        self.cell_size_input.setDecimals(1)
        layout.addRow("Размер ячейки:", self.cell_size_input)

        self.global_x_offset_input = QtWidgets.QDoubleSpinBox()
        self.global_x_offset_input.setRange(-1000000.0, 1000000.0)
        layout.addRow("Смещение X:", self.global_x_offset_input)

        self.global_z_offset_input = QtWidgets.QDoubleSpinBox()
        self.global_z_offset_input.setRange(-1000000.0, 1000000.0)
        layout.addRow("Смещение Z:", self.global_z_offset_input)

        layout.addItem(QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))
        return panel

    def _create_global_noise_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.gn_scale_input = QtWidgets.QDoubleSpinBox()
        self.gn_scale_input.setRange(1.0, 100000.0)
        self.gn_scale_input.setSingleStep(100.0)
        layout.addRow("Масштаб:", self.gn_scale_input)

        self.gn_octaves_input = QtWidgets.QSpinBox()
        self.gn_octaves_input.setRange(1, 10)
        layout.addRow("Октавы:", self.gn_octaves_input)

        self.gn_amp_input = QtWidgets.QDoubleSpinBox()
        self.gn_amp_input.setRange(0.0, 1000.0)
        layout.addRow("Амплитуда (м):", self.gn_amp_input)

        self.gn_ridge_checkbox = QtWidgets.QCheckBox()
        layout.addRow("Ridge:", self.gn_ridge_checkbox)

        layout.addItem(QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))
        return panel

    def _create_left_tabs(self) -> QtWidgets.QTabWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)

        project_params_panel = self._create_project_params_panel()
        tabs.addTab(project_params_panel, "Проект")

        global_noise_panel = self._create_global_noise_panel()
        tabs.addTab(global_noise_panel, "Глобальный Шум")

        # --- ИЗМЕНЕНИЕ: Создаем и добавляем панель пресетов ---
        self.presets_widget = make_region_presets_widget(self)
        tabs.addTab(self.presets_widget, "Пресеты")

        return tabs

    def _connect_components(self):
        if self.graph:
            if self.props_bin:
                self.props_bin.set_graph(self.graph)
            if self.node_inspector:
                self.node_inspector.bind_graph(self.graph)
            if self.right_outliner: self.right_outliner.bind_graph(self.graph)
            if self.left_palette: self.left_palette.bind_graph(self.graph)

            QtCore.QTimer.singleShot(0, self.graph.finalize_setup)

            self.graph.structure_changed.connect(self._mark_dirty)
            self.graph.property_changed.connect(self._mark_dirty)

        for widget in [self.seed_input, self.chunk_size_input, self.region_size_in_chunks_input,
                       self.cell_size_input, self.global_x_offset_input, self.global_z_offset_input,
                       self.gn_scale_input, self.gn_octaves_input, self.gn_amp_input]:
            if widget and isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                widget.valueChanged.connect(self._mark_dirty)
        if self.gn_ridge_checkbox:
            self.gn_ridge_checkbox.toggled.connect(self._mark_dirty)

        if self.right_outliner:
            self.right_outliner.apply_clicked.connect(self._on_apply_clicked)

        # --- ИЗМЕНЕНИЕ: Подключаем сигналы от панели пресетов к обработчикам ---
        if self.presets_widget:
            self.presets_widget.load_requested.connect(self.action_load_region_preset)
            self.presets_widget.create_from_current_requested.connect(self.action_create_preset)
            self.presets_widget.delete_requested.connect(self.action_delete_preset)
            # Сигнал save_as_requested используется для сохранения графа, привязываем его к действию сохранения
            self.presets_widget.save_as_requested.connect(self.action_save_active_preset)

    # --- ИЗМЕНЕНИЕ: Реализуем недостающий метод ---
    def _load_presets_list(self):
        """Загружает список пресетов из данных проекта и обновляет UI."""
        if not self.presets_widget or not self.project_manager.current_project_data:
            return

        presets_data = self.project_manager.current_project_data.get("region_presets", {})
        preset_names = list(presets_data.keys())
        self.presets_widget.set_presets(preset_names)

        active_preset = self.project_manager.current_project_data.get("active_preset_name")
        if active_preset:
            self.presets_widget.select_preset(active_preset)

    # --- ИЗМЕНЕНИЕ: Добавляем методы-обработчики для действий с пресетами ---
    def get_project_data(self) -> Dict[str, Any] | None:
        """Безопасный способ получить данные текущего проекта."""
        return self.project_manager.current_project_data

    def get_active_graph(self):
        """Возвращает текущий активный граф."""
        return self.graph

    def action_load_region_preset(self, preset_name: str):
        """Загружает выбранный пресет."""
        project_data = self.get_project_data()
        if not project_data: return

        preset_info = project_data.get("region_presets", {}).get(preset_name)
        if preset_info:
            project_data["active_preset_name"] = preset_name
            preset_actions.load_preset_into_graph(self, preset_info)
            self.presets_widget.select_preset(preset_name)
            self.mark_dirty()  # Смена пресета - это изменение проекта

    def action_create_preset(self):
        """Создает новый пресет."""
        preset_actions.handle_new_preset(self)

    def action_delete_preset(self):
        """Удаляет выбранный пресет."""
        preset_actions.handle_delete_preset(self)

    def action_save_active_preset(self):
        """Сохраняет текущее состояние графа в активный пресет."""
        preset_actions.handle_save_active_preset(self)

    # ... остальные методы (new_project, open_project, save_project, _mark_dirty, closeEvent, _on_apply_clicked, _trigger_apply) ...
    # ... остаются практически без изменений, за исключением того, что save_project теперь вызывается через ProjectManager ...
    def new_project(self):
        self.project_manager.new_project()

    def open_project(self):
        self.project_manager.open_project()

    def save_project(self) -> bool:
        return self.project_manager.save_project()

    def _mark_dirty(self, *args, **kwargs):
        self.project_manager.mark_dirty(True)

    def closeEvent(self, ev: QtGui.QCloseEvent):
        if self.project_manager.close_project_with_confirmation():
            ev.accept()
        else:
            ev.ignore()

    def _on_apply_clicked(self):
        if self.right_outliner:
            self.right_outliner.set_busy(True)
        try:
            if not self.graph:
                raise RuntimeError("Граф не инициализирован.")
            output_node = None
            for node in self.graph.all_nodes():
                if isinstance(node, OutputNode):
                    output_node = node
                    break
            if not output_node:
                raise RuntimeError("В графе не найдена выходная нода (OutputNode).")

            context = self.project_manager.collect_ui_context()  # Используем метод менеджера

            logger.info(f"Запуск вычисления графа от ноды: {output_node.name()}")
            height_map = run_graph(output_node, context)

            if self.preview_widget:
                current_cell_size = context.get("cell_size", 1.0)
                self.preview_widget.update_mesh(height_map, current_cell_size)
                logger.info("Виджет предпросмотра успешно обновлен.")
            else:
                logger.warning("Preview widget недоступен.")
        except Exception as e:
            logger.exception(f"Ошибка во время генерации мира: {e}")
            QtWidgets.QMessageBox.critical(self, "Ошибка генерации", f"Произошла ошибка: {e}")
        finally:
            if self.right_outliner:
                self.right_outliner.set_busy(False)

    def _trigger_apply(self) -> None:
        if self.right_outliner and self.right_outliner.apply_button:
            self.right_outliner.apply_button.animateClick(10)