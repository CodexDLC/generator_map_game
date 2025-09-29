# ==============================================================================
# Файл: main_window.py
# ВЕРСИЯ 5.4 (РЕФАКТОРИНГ): Уточнена обработка исключений при создании Preview3DWidget.
# - Заменено общее 'except Exception' на более конкретные исключения.
# ==============================================================================

from __future__ import annotations

import logging
from typing import Optional

from PySide6 import QtWidgets, QtCore, QtGui

from editor.graph_runner import run_graph
from editor.nodes.height.io.output_node import OutputNode

from editor.theme import APP_STYLE_SHEET
from editor.ui_panels.central_graph import create_bottom_work_area_v2
from editor.ui_panels.menu import build_menus
from editor.ui_panels.accordion_properties import create_properties_widget
from editor.ui_panels.shortcuts import install_shortcuts
from editor.preview_widget import Preview3DWidget
from editor.project_manager import ProjectManager

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
        except (ImportError, RuntimeError) as e: # Уточненные исключения
            logger.exception(f"Не удалось создать Preview3DWidget: {e}")
            lbl = QtWidgets.QLabel("Preview widget failed to load")
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            self.preview_widget = lbl

        bottom_work_area, self.graph, self.left_palette, self.right_outliner = create_bottom_work_area_v2(self)

        tabs_left = self._create_left_tabs()
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
        tabs.addTab(project_params_panel, "Параметры Проекта")

        global_noise_panel = self._create_global_noise_panel()
        tabs.addTab(global_noise_panel, "Глобальный Шум")
        
        return tabs

    def _create_right_tabs(self) -> QtWidgets.QTabWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        self.props_bin = create_properties_widget(self)
        tabs.addTab(self.props_bin, "Параметры")
        tabs.addTab(QtWidgets.QWidget(), "Нода")
        return tabs

    def _connect_components(self):
        if self.graph:
            if self.props_bin: self.props_bin.set_graph(self.graph)
            if self.right_outliner: self.right_outliner.bind_graph(self.graph)
            if self.left_palette: self.left_palette.bind_graph(self.graph)

            self.graph.finalize_setup()
            
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
            # 1. Проверяем наличие графа
            if not self.graph:
                raise RuntimeError("Граф не инициализирован.")

            # 2. Находим выходную ноду
            output_node = None
            for node in self.graph.all_nodes():
                if isinstance(node, OutputNode):
                    output_node = node
                    break
            if not output_node:
                raise RuntimeError("В графе не найдена выходная нода (OutputNode).")

            # 3. Собираем контекст из UI
            context = {
                "seed": self.seed_input.value(),
                "chunk_size": self.chunk_size_input.value(),
                "region_size_in_chunks": self.region_size_in_chunks_input.value(),
                "cell_size": self.cell_size_input.value(),
                "global_x_offset": self.global_x_offset_input.value(),
                "global_z_offset": self.global_z_offset_input.value(),
                "global_noise": {
                    "scale_tiles": self.gn_scale_input.value(),
                    "octaves": self.gn_octaves_input.value(),
                    "amp_m": self.gn_amp_input.value(),
                    "ridge": self.gn_ridge_checkbox.isChecked()
                }
            }

            # 4. Запускаем вычисление графа
            logger.info(f"Запуск вычисления графа от ноды: {output_node.name()}")
            height_map = run_graph(output_node, context)

            # 5. Обновляем предпросмотр
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
