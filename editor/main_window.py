# ==============================================================================
# Файл: main_window.py
# ВЕРСИЯ 8.1 (HOTFIX): Исправлен поиск ноды по типу.
# - Заменен ошибочный вызов get_nodes_by_class_name на get_nodes_by_type.
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
from editor.ui_panels.region_presets_panel import make_region_presets_widget
from editor.ui_panels.shortcuts import install_shortcuts
from editor.preview_widget import Preview3DWidget
from editor.project_manager import ProjectManager

from editor.actions import preset_actions
from editor.ui_panels.world_settings_panel import make_world_settings_widget

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
        self.presets_widget = None

        # --- Атрибуты для новых виджетов настроек ---
        self.ws_max_height_input = None
        self.ws_vertex_spacing_input = None
        self.pv_resolution_input = None
        self.pv_realtime_checkbox = None
        self.gv_scale_input = None
        self.gv_octaves_input = None
        self.gv_roughness_input = None
        self.gv_variation_input = None

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
        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("TopTabsRight")
        tabs.setDocumentMode(True)
        self.props_bin = create_properties_widget(self)
        tabs.addTab(self.props_bin, "Параметры")
        self.node_inspector = make_node_inspector_widget(self)
        tabs.addTab(self.node_inspector, "Инспектор")
        return tabs

    def _create_left_tabs(self) -> QtWidgets.QTabWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        world_settings_panel = make_world_settings_widget(self)
        tabs.addTab(world_settings_panel, "Настройки Мира")
        self.presets_widget = make_region_presets_widget(self)
        tabs.addTab(self.presets_widget, "Пресеты")
        return tabs

    def _connect_components(self):
        if self.graph:
            if self.props_bin: self.props_bin.set_graph(self.graph)
            if self.node_inspector: self.node_inspector.bind_graph(self.graph)
            if self.right_outliner: self.right_outliner.bind_graph(self.graph)
            if self.left_palette: self.left_palette.bind_graph(self.graph)
            QtCore.QTimer.singleShot(0, self.graph.finalize_setup)

        if self.right_outliner:
            self.right_outliner.apply_clicked.connect(self._on_apply_clicked)

        if self.presets_widget:
            self.presets_widget.load_requested.connect(self.action_load_region_preset)
            self.presets_widget.create_from_current_requested.connect(self.action_create_preset_from_dialog)
            self.presets_widget.delete_requested.connect(self.action_delete_preset_by_name)
            self.presets_widget.save_as_requested.connect(self.action_save_active_preset)

    def _load_presets_list(self):
        if not self.presets_widget or not self.project_manager.current_project_data: return
        presets_data = self.project_manager.current_project_data.get("region_presets", {})
        self.presets_widget.set_presets(list(presets_data.keys()))
        active_preset = self.project_manager.current_project_data.get("active_preset_name")
        if active_preset: self.presets_widget.select_preset(active_preset)

    def get_project_data(self) -> Dict[str, Any] | None:
        return self.project_manager.current_project_data

    def get_active_graph(self):
        return self.graph

    def action_load_region_preset(self, preset_name: str):
        project_data = self.get_project_data()
        if not project_data: return
        preset_info = project_data.get("region_presets", {}).get(preset_name)
        if preset_info:
            project_data["active_preset_name"] = preset_name
            preset_actions.load_preset_into_graph(self, preset_info)
            self.presets_widget.select_preset(preset_name)
            self._mark_dirty()

    def action_create_preset_from_dialog(self, preset_name_from_field: str):
        preset_actions.handle_new_preset(self)

    def action_delete_preset_by_name(self, preset_name: str):
        items = self.presets_widget.list.findItems(preset_name, QtCore.Qt.MatchExactly)
        if items:
            self.presets_widget.list.setCurrentItem(items[0])
            preset_actions.handle_delete_preset(self)

    def action_save_active_preset(self):
        preset_actions.handle_save_active_preset(self)

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
            # 1. Находим финальную ноду (или ту, что в фокусе)
            # --- ИЗМЕНЕНИЕ: Используем правильный метод get_nodes_by_type ---
            output_nodes = self.graph.get_nodes_by_type('OutputNode')
            output_node = self.graph.selected_nodes()[0] if self.graph.selected_nodes() else (output_nodes[0] if output_nodes else None)
            if not output_node:
                raise RuntimeError("В графе не найдена выходная нода и ни одна нода не выбрана.")

            # 2. Собираем контекст из UI
            context = self.project_manager.collect_ui_context()

            # 3. Генерируем Мировой Фрактал для WorldInputNode
            from generator_logic.terrain.fractals import generate_multifractal

            fractal_params = {
                'type': 'fbm',
                'octaves': self.gv_octaves_input.value(),
                'roughness': self.gv_roughness_input.value(),
                'seed': context['seed'],
            }
            variation_params = {
                'variation': self.gv_variation_input.value(),
                'smoothness': 0.0, # Глобально вариация всегда плавная
            }
            position_params = {}
            warp_params = {'type': 'none'}

            scale = self.gv_scale_input.value()
            coords_x = context['x_coords'] * scale
            coords_z = context['z_coords'] * scale

            world_fractal_noise = generate_multifractal(
                coords_x, coords_z, fractal_params, variation_params, position_params, warp_params
            )

            context["world_input_noise"] = world_fractal_noise

            # 4. Запускаем вычисление графа
            final_map_01 = run_graph(output_node, context)

            # 5. Применяем финальное масштабирование в метры для превью
            max_height_m = self.ws_max_height_input.value()
            final_map_meters = final_map_01 * max_height_m

            # 6. Отправляем результат в 3D-вьюпорт
            if self.preview_widget:
                cell_size = self.ws_vertex_spacing_input.value()
                self.preview_widget.update_mesh(final_map_meters, cell_size)

        except Exception as e:
            logger.exception(f"Ошибка во время генерации: {e}")
            QtWidgets.QMessageBox.critical(self, "Ошибка генерации", f"Произошла ошибка: {e}")
        finally:
            if self.right_outliner:
                self.right_outliner.set_busy(False)

    def _trigger_apply(self) -> None:
        if self.right_outliner and self.right_outliner.apply_button:
            self.right_outliner.apply_button.animateClick(10)
