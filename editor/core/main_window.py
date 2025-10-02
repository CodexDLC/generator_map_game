# editor/core/main_window.py
from __future__ import annotations
import logging
import traceback
from typing import Optional, Dict, Any

import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from editor.graph.graph_runner import run_graph
from editor.ui_panels.accordion_properties import create_properties_widget, SliderSpinCombo, SeedWidget, CollapsibleBox
from editor.ui_panels.central_graph import create_bottom_work_area_v2
from editor.ui_panels.menu import build_menus
from editor.ui_panels.node_inspector import make_node_inspector_widget
from editor.ui_panels.region_presets_panel import make_region_presets_widget
from editor.ui_panels.shortcuts import install_shortcuts
from editor.widgets.preview_widget import Preview3DWidget
from editor.core.project_manager import ProjectManager
from editor.actions import preset_actions
from editor.ui_panels.world_settings_panel import make_world_settings_widget
from editor.ui_panels.render_panel import make_render_panel_widget
from editor.core.render_settings import RenderSettings
# --- НОВЫЙ ИМПОРТ ---
from editor.ui_panels.world_map_widget import WorldMapWidget

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs) -> None:
        project_path: Optional[str] = kwargs.pop("project_path", None)
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Редактор Миров")
        self.resize(1600, 900)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.project_manager = ProjectManager(self)
        self.render_settings = RenderSettings()

        self.graph: 'CustomNodeGraph' | None = None
        self.preview_widget: Preview3DWidget | None = None
        self.props_bin: QtWidgets.QWidget | None = None
        self.right_outliner: 'RightOutlinerWidget' | None = None
        self.left_palette: QtWidgets.QWidget | None = None
        self.node_inspector: QtWidgets.QWidget | None = None
        self.presets_widget: 'RegionPresetsWidget' | None = None
        self._last_selected_node = None
        self.world_map_widget: WorldMapWidget | None = None

        # --- АТРИБУТЫ ДЛЯ НАСТРОЕК МИРА (V2) ---
        self.region_resolution_input: QtWidgets.QComboBox | None = None
        self.vertex_distance_input: QtWidgets.QDoubleSpinBox | None = None
        self.max_height_input: QtWidgets.QDoubleSpinBox | None = None
        self.global_x_offset_input: QtWidgets.QDoubleSpinBox | None = None
        self.global_z_offset_input: QtWidgets.QDoubleSpinBox | None = None
        self.preview_resolution_input: QtWidgets.QComboBox | None = None
        self.realtime_checkbox: QtWidgets.QCheckBox | None = None
        self.ws_noise_box: CollapsibleBox | None = None

        # --- АТРИБУТЫ ДЛЯ СФЕРИЧЕСКОГО ШУМА ---
        self.ws_sphere_radius: QtWidgets.QDoubleSpinBox | None = None
        self.ws_sphere_frequency: SliderSpinCombo | None = None
        self.ws_sphere_octaves: SliderSpinCombo | None = None
        self.ws_sphere_gain: SliderSpinCombo | None = None
        self.ws_sphere_ridge: QtWidgets.QCheckBox | None = None
        self.ws_sphere_seed: SeedWidget | None = None
        self.ws_warp_type: QtWidgets.QComboBox | None = None
        self.ws_warp_rel_size: SliderSpinCombo | None = None
        self.ws_warp_strength: SliderSpinCombo | None = None
        self.ws_ocean_latitude: SliderSpinCombo | None = None
        self.ws_ocean_falloff: SliderSpinCombo | None = None

        self._build_ui()
        build_menus(self)
        install_shortcuts(self)
        if project_path:
            self.project_manager.load_project(project_path)

    def _build_ui(self) -> None:
        try:
            self.preview_widget = Preview3DWidget(self)
            self.preview_widget.setParent(self)
        except (ImportError, RuntimeError) as e:
            logger.exception(f"Не удалось создать Preview3DWidget: {e}")
            self.preview_widget = QtWidgets.QLabel("Preview widget failed to load")
            self.preview_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        bottom_work_area, self.graph, self.left_palette, self.right_outliner = create_bottom_work_area_v2(self)
        tabs_left = self._create_left_tabs()
        tabs_right = self._create_right_tabs()

        top_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        top_splitter.addWidget(tabs_left)
        top_splitter.addWidget(self.preview_widget)
        top_splitter.addWidget(tabs_right)
        top_splitter.setStretchFactor(1, 1)
        top_splitter.setSizes([360, 900, 420])

        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, self)
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
        self.render_panel = make_render_panel_widget(
            self, self.render_settings, self._on_render_settings_changed
        )
        tabs.addTab(self.render_panel, "Рендер")
        return tabs

    def _create_left_tabs(self) -> QtWidgets.QTabWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        world_settings_panel, ws_widgets = make_world_settings_widget(self)
        for name, widget in ws_widgets.items():
            setattr(self, name, widget)
        tabs.addTab(world_settings_panel, "Настройки Мира")
        self.presets_widget = make_region_presets_widget(self)
        tabs.addTab(self.presets_widget, "Пресеты")
        return tabs

    def _connect_components(self):
        # --- ИЗМЕНЕНИЕ: Подключаем новые виджеты ---
        if self.region_resolution_input: self.region_resolution_input.currentIndexChanged.connect(self._trigger_preview_update)
        if self.vertex_distance_input: self.vertex_distance_input.editingFinished.connect(self._trigger_preview_update)
        if self.max_height_input: self.max_height_input.editingFinished.connect(self._trigger_preview_update)
        if self.global_x_offset_input: self.global_x_offset_input.editingFinished.connect(self._trigger_preview_update)
        if self.global_z_offset_input: self.global_z_offset_input.editingFinished.connect(self._trigger_preview_update)
        if self.preview_resolution_input: self.preview_resolution_input.currentIndexChanged.connect(self._trigger_preview_update)
        if self.ws_noise_box: self.ws_noise_box.toggled.connect(self._trigger_preview_update)

        # --- ПОДКЛЮЧЕНИЯ ДЛЯ СФЕРИЧЕСКОГО ШУМА ---
        if self.ws_sphere_frequency: self.ws_sphere_frequency.editingFinished.connect(self._trigger_preview_update)
        if self.ws_sphere_octaves: self.ws_sphere_octaves.editingFinished.connect(self._trigger_preview_update)
        if self.ws_sphere_gain: self.ws_sphere_gain.editingFinished.connect(self._trigger_preview_update)
        if self.ws_sphere_ridge: self.ws_sphere_ridge.toggled.connect(self._trigger_preview_update)
        if self.ws_sphere_seed: self.ws_sphere_seed.editingFinished.connect(self._trigger_preview_update)
        if self.ws_warp_type: self.ws_warp_type.currentIndexChanged.connect(self._trigger_preview_update)
        if self.ws_warp_rel_size: self.ws_warp_rel_size.editingFinished.connect(self._trigger_preview_update)
        if self.ws_warp_strength: self.ws_warp_strength.editingFinished.connect(self._trigger_preview_update)
        if self.ws_ocean_latitude: self.ws_ocean_latitude.editingFinished.connect(self._trigger_preview_update)
        if self.ws_ocean_falloff: self.ws_ocean_falloff.editingFinished.connect(self._trigger_preview_update)

        if self.graph:
            if self.props_bin: self.props_bin.set_graph(self.graph, self)
            if self.node_inspector: self.node_inspector.bind_graph(self.graph)
            if self.right_outliner: self.right_outliner.bind_graph(self.graph)
            if self.left_palette: self.left_palette.bind_graph(self.graph)
            QtCore.QTimer.singleShot(0, self.graph.finalize_setup)
            self.graph.selection_changed.connect(self._on_node_selection_changed)
        if self.right_outliner:
            self.right_outliner.apply_clicked.connect(self._on_apply_clicked)
        if self.presets_widget:
            self.presets_widget.load_requested.connect(self.action_load_region_preset)
            self.presets_widget.create_from_current_requested.connect(self.action_create_preset_from_dialog)
            self.presets_widget.delete_requested.connect(self.action_delete_preset_by_name)
            self.presets_widget.save_as_requested.connect(self.action_save_active_preset)

    @QtCore.Slot(object)
    def _on_render_settings_changed(self, new_settings: RenderSettings):
        old_hex = self.render_settings.height_exaggeration
        new_hex = new_settings.height_exaggeration
        self.render_settings = new_settings
        if self.preview_widget:
            self.preview_widget.apply_render_settings(new_settings)
        if abs(old_hex - new_hex) > 1e-6:
            self._on_apply_clicked()

    @QtCore.Slot()
    def _trigger_preview_update(self):
        if self.realtime_checkbox.isChecked():
            self._on_apply_clicked()

    @QtCore.Slot(list)
    def _on_node_selection_changed(self, selected_nodes):
        if selected_nodes:
            self._last_selected_node = selected_nodes[0]
            if self.realtime_checkbox.isChecked():
                self._on_apply_clicked()

    def get_project_data(self) -> Dict[str, Any] | None:
        return self.project_manager.current_project_data

    def get_active_graph(self):
        return self.graph

    def new_project(self):
        self.project_manager.new_project()

    def open_project(self):
        self.project_manager.open_project()

    def save_project(self) -> bool:
        return self.project_manager.save_project()

    def _load_presets_list(self):
        if not self.presets_widget or not self.project_manager.current_project_data: return
        presets_data = self.project_manager.current_project_data.get("region_presets", {})
        self.presets_widget.set_presets(list(presets_data.keys()))
        active_preset = self.project_manager.current_project_data.get("active_preset_name")
        if active_preset: self.presets_widget.select_preset(active_preset)

    def action_load_region_preset(self, preset_name: str):
        project_data = self.get_project_data()
        if not project_data: return
        preset_info = project_data.get("region_presets", {}).get(preset_name)
        if preset_info:
            project_data["active_preset_name"] = preset_name
            preset_actions.load_preset_into_graph(self, preset_info)
            self.presets_widget.select_preset(preset_name)
            self._mark_dirty()

    def action_create_preset_from_dialog(self, _preset_name_from_field: str):
        preset_actions.handle_new_preset(self)

    def action_delete_preset_by_name(self, preset_name: str):
        items = self.presets_widget.list.findItems(preset_name, QtCore.Qt.MatchFlag.MatchExactly)
        if items:
            self.presets_widget.list.setCurrentItem(items[0])
            preset_actions.handle_delete_preset(self)

    def action_save_active_preset(self):
        preset_actions.handle_save_active_preset(self)

    def _mark_dirty(self, *_args, **_kwargs):
        self.project_manager.mark_dirty(True)

    def closeEvent(self, ev: QtGui.QCloseEvent):
        if self.project_manager.close_project_with_confirmation():
            ev.accept()
        else:
            ev.ignore()

    def _on_apply_clicked(self):
        if self.right_outliner: self.right_outliner.set_busy(True)
        try:
            target_node = self.graph.selected_nodes()[0] if self.graph.selected_nodes() else self._last_selected_node
            if not target_node:
                logger.warning("Нет выбранной ноды для превью. Рендер отменен.")
                return

            logger.info(f"Рендеринг превью для ноды: '{target_node.name()}'")

            context = self.project_manager.collect_ui_context(for_preview=True)

            # --- НАЧАЛО ИСПРАВЛЕНИЯ: Рассчитываем реальный размер мира для консистентности шума ---
            try:
                real_res_str = self.region_resolution_input.currentText()
                real_res = int(real_res_str.split('x')[0])
                real_vertex_dist = self.vertex_distance_input.value()
                # Это реальный размер региона в метрах, он не зависит от разрешения превью
                real_world_size_for_noise = real_res * real_vertex_dist
            except Exception:
                # В случае ошибки используем размер из контекста превью
                real_world_size_for_noise = context['WORLD_SIZE_METERS']
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

            if self.ws_noise_box.isChecked():
                from game_engine_restructured.numerics.fast_noise import fbm_grid_bipolar, fbm_amplitude
                params = {
                    "seed": self.ws_sphere_seed.value(),
                    "coords_x": context['x_coords'], "coords_z": context['z_coords'],
                    # --- ИЗМЕНЕНИЕ: Используем РЕАЛЬНЫЙ размер для расчета частоты ---
                    "freq0": 1.0 / (real_world_size_for_noise * self.ws_sphere_frequency.value() * 0.1),
                    "octaves": int(self.ws_sphere_octaves.value()),
                    "gain": self.ws_sphere_gain.value(),
                    "ridge": self.ws_sphere_ridge.isChecked(),
                }
                raw_noise = fbm_grid_bipolar(**params)
                max_amp = fbm_amplitude(params['gain'], params['octaves'])
                if max_amp > 1e-9: raw_noise /= max_amp
                world_fractal_noise = (raw_noise + 1.0) * 0.5
            else:
                world_fractal_noise = np.zeros_like(context["x_coords"], dtype=np.float32)

            context["world_input_noise"] = world_fractal_noise
            final_map_01 = run_graph(target_node, context)

            preview_max_height = context.get('max_height_m', 1000.0)
            final_map_meters = final_map_01 * preview_max_height

            if self.preview_widget:
                preview_vertex_spacing = 1.0
                self.preview_widget.update_mesh(final_map_meters, preview_vertex_spacing)

        except Exception as e:
            logger.exception(f"Ошибка во время генерации: {e}")
            QtWidgets.QMessageBox.critical(self, "Ошибка генерации",
                                           f"Произошла ошибка: {e}\n\n{traceback.format_exc()}")
        finally:
            if self.right_outliner: self.right_outliner.set_busy(False)

    def _trigger_apply(self) -> None:
        if self.right_outliner and self.right_outliner.apply_button:
            self.right_outliner.apply_button.animateClick(10)

    # --- НОВЫЕ МЕТОДЫ В КОНЦЕ КЛАССА ---

    def show_world_map(self):
        ''' Открывает или показывает окно с картой мира. '''
        if self.world_map_widget is None:
            self.world_map_widget = WorldMapWidget(self)
            self.world_map_widget.map_label.region_selected.connect(self.on_region_selected_from_map)

        self.world_map_widget.show()
        self.world_map_widget.activateWindow()
        self.world_map_widget.raise_()

    @QtCore.Slot(float, float)
    def on_region_selected_from_map(self, offset_x: float, offset_z: float):
        ''' Обновляет смещения в UI и запускает перерисовку. '''
        if self.global_x_offset_input and self.global_z_offset_input:
            self.global_x_offset_input.setValue(offset_x)
            self.global_z_offset_input.setValue(offset_z)
            self._on_apply_clicked()