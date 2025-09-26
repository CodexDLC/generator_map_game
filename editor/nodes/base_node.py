# base_node.py
# -----------------------------------------------------------------------------
# GeneratorNode для NodeGraphQt 0.6.42
# - Вкладка "About" (многострочный QTextEdit через add_custom_widget(widget, widget_type, tab))
# - Тултипы: на карточке ноды и на портах
# - Сохранена логика dirty/cache/compute/enum
# -----------------------------------------------------------------------------

import time
import logging
from NodeGraphQt import BaseNode, NodeBaseWidget
from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QTextOption

logger = logging.getLogger(__name__)

class ReadOnlyTextWidget(NodeBaseWidget):
    def __init__(self, name='about_desc', label='Description', text=''):
        super().__init__(name=name, label=label)
        te = QtWidgets.QTextEdit()
        te.setReadOnly(True)
        te.setMinimumHeight(140)
        te.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        te.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        te.setPlainText(text)
        self.set_custom_widget(te)

    def get_value(self):
        return self._custom_widget.toPlainText()

    def set_value(self, value):
        self._custom_widget.setPlainText(str(value))

class GeneratorNode(BaseNode):
    __identifier__ = 'generator.nodes'

    def __init__(self):
        super().__init__()

        # --- описание / служебные поля ---
        self._description_text = "Описание для этой ноды не задано."
        self._port_desc = {}
        self._is_dirty = getattr(self, "_is_dirty", True)
        self._result_cache = getattr(self, "_result_cache", None)
        self._rev = getattr(self, "_rev", 0)
        self._last_sig = getattr(self, "_last_sig", None)

        # --- базовые свойства в панели ---
        self.add_text_input('node_name', 'node name', tab='Node Properties')
        self.add_text_input('node_id', 'node id', tab='Node Properties')

        # --- About: корректный путь для 0.6.42 (NodeBaseWidget) ---
        self._desc_widget = None
        try:
            self._desc_widget = ReadOnlyTextWidget(text=self._description_text)
            # 0.6.42: add_custom_widget(self, widget: NodeBaseWidget, widget_type=None, tab=None)
            self.add_custom_widget(self._desc_widget, widget_type='NodeWidget', tab='About')
        except Exception:
            # мягкий фолбэк: кнопка с модалкой
            btn = QtWidgets.QPushButton("Show description…")

            def _show_desc():
                dlg = QtWidgets.QDialog(self.view.window() if getattr(self, 'view', None) else None)
                dlg.setWindowTitle(self.name())
                lay = QtWidgets.QVBoxLayout(dlg)
                te = QtWidgets.QTextEdit()
                te.setReadOnly(True)
                te.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
                te.setWordWrapMode(QTextOption.WrapMode.WordWrap)
                te.setPlainText(self._description_text)
                lay.addWidget(te)
                dlg.resize(560, 380)
                dlg.exec()

            try:
                self.add_custom_widget(btn, widget_type='QPushButton', tab='About')
                btn.clicked.connect(_show_desc)
            except Exception:
                self.add_text_input('about_desc_fallback', 'Description', tab='About',
                                    text=self._description_text)

        # --- Тултипы: сразу + отложенная добивка (после построения QGraphics-дерева) ---
        self._apply_tooltips_to_node()
        self._deferred_init_tooltips()

    # ======================================================================
    # ТУЛТИПЫ
    # ======================================================================

    def _deferred_init_tooltips(self, tries=0, delay_ms=50):
        # Нода может ещё не быть в сцене, или уже быть удалённой.
        v = getattr(self, 'view', None)
        scene = getattr(v, 'scene', lambda: None)()
        if v is None or scene is None:
            if tries < 10:  # максимум 10 попыток ~ 0.5 сек
                QtCore.QTimer.singleShot(delay_ms, lambda: self._deferred_init_tooltips(tries + 1, delay_ms))
            return
        # Когда реально в сцене — ставим тултипы
        self._apply_tooltips_to_node()
        self._apply_tooltips_to_ports()

    def _safe_tip(self, item, txt):
        try:
            if item and hasattr(item, 'scene') and item.scene() is not None:
                item.setToolTip(txt)
        except Exception:
            pass

    # --- усиленный «веник» для тултипов ноды (оставь у себя вместо текущего) ---
    def _apply_tooltips_to_node(self):
        v = getattr(self, 'view', None)
        if not v or getattr(v, 'scene', lambda: None)() is None:
            return
        txt = self._description_text
        self._safe_tip(v, txt)
        for attr in ('title_item', '_name_item', 'name_item', 'bg_item', 'content', 'content_widget'):
            self._safe_tip(getattr(v, attr, None), txt)
        try:
            for it in v.childItems():
                self._safe_tip(it, txt)
        except Exception:
            pass

    def _apply_tooltips_to_ports(self):
        v = getattr(self, 'view', None)
        if not v or getattr(v, 'scene', lambda: None)() is None:
            return
        for p in list(self.inputs().values()) + list(self.outputs().values()):
            vi = getattr(p, 'view', None)
            if vi and getattr(vi, 'scene', lambda: None)() is not None:
                txt = self._port_desc.get(p, f"{self.name()} · {p.name()}")
                self._safe_tip(vi, txt)

    def set_port_description(self, port_obj, text: str):
        """Кастомный текст конкретного порта + обновление тултипа."""
        self._port_desc[port_obj] = str(text)
        self._apply_tooltips_to_ports()

    def set_port_description_by_name(self, port_name: str, text: str):
        """Удобно назначать описание по имени порта (inputs/outputs)."""
        for p in list(self.inputs().values()) + list(self.outputs().values()):
            if p.name() == port_name:
                self.set_port_description(p, text)
                return

    # Перехваты с ПРАВИЛЬНОЙ сигнатурой для 0.6.42
    def add_input(self, name='input', multi_input=False, display_name=True,
                  color=None, locked=False, painter_func=None):
        p = super().add_input(name, multi_input, display_name, color, locked, painter_func)
        try:
            self._port_desc.setdefault(p, f"{self.name()} · {p.name()}")
            vi = getattr(p, 'view', None)
            if vi:
                vi.setToolTip(self._port_desc[p])
        except Exception:
            pass
        return p

    def add_output(self, name='output', multi_output=True, display_name=True,
                   color=None, locked=False, painter_func=None):
        p = super().add_output(name, multi_output, display_name, color, locked, painter_func)
        try:
            self._port_desc.setdefault(p, f"{self.name()} · {p.name()}")
            vi = getattr(p, 'view', None)
            if vi:
                vi.setToolTip(self._port_desc[p])
        except Exception:
            pass
        return p

    # ======================================================================
    # ОПИСАНИЕ НОДЫ
    # ======================================================================

    def set_description(self, text: str):
        import textwrap
        self._description_text = textwrap.dedent(text).strip()
        try:
            if getattr(self, '_desc_widget', None) is not None:
                self._desc_widget.set_value(self._description_text)
        except Exception:
            pass
        try:
            if hasattr(self, "has_property") and self.has_property('about_desc_fallback'):
                self.set_property('about_desc_fallback', self._description_text)
        except Exception:
            pass
        self._apply_tooltips_to_node()
    def get_description(self) -> str:
        return self._description_text

    # ======================================================================
    # «ГРЯЗЬ» / РЕВИЗИИ / КЭШ
    # ======================================================================

    def mark_dirty(self):
        """Пометить ноду и всех потребителей как 'грязных'."""
        if self._is_dirty:
            return
        self._is_dirty = True
        self._result_cache = None
        self._rev += 1

        for port in self.output_ports():
            for conn in port.connected_ports():
                node = conn.node()
                if isinstance(node, GeneratorNode):
                    node.mark_dirty()

    def set_property(self, name, value, push_undo=False, **kwargs):
        # любое изменение свойства инвалидирует результат
        try:
            if self.get_property(name) != value:
                self.mark_dirty()
        except Exception:
            self.mark_dirty()

        # node_id отображаем, но принуждаем к реальному self.id
        if name == 'node_id':
            real_id = self.id
            if value != real_id:
                return super().set_property(name, real_id, push_undo=push_undo, **kwargs)
            return super().set_property(name, value, push_undo=push_undo, **kwargs)

        # синхронизируем заголовок
        if name == 'node_name':
            if self.name() != str(value):
                self.set_name(str(value))

        return super().set_property(name, value, push_undo=push_undo, **kwargs)

    def _make_context_signature(self, context: dict):
        """Мини-подпись контекста: если это поменялось — считаем заново."""
        try:
            seed       = int(context.get('seed'))
            cell_size  = float(context.get('cell_size'))
            grid_shape = getattr(context.get('x_coords'), 'shape', None)
            gn = context.get('global_noise')
            gn_sig = tuple(sorted(gn.items())) if isinstance(gn, dict) else None
            ctx_rev = context.get('_ctx_rev', None)
            return ('v1', seed, cell_size, grid_shape, gn_sig, ctx_rev)
        except Exception:
            return ('v1_fallback', id(context))

    def _make_upstream_signature(self):
        """Подпись входов: кто подключен и их ревизии."""
        sig = []
        for p in self.input_ports():
            conns = p.connected_ports()
            if not conns:
                sig.append((p.name(), None))
            else:
                ids = tuple(sorted((c.node().id, getattr(c.node(), '_rev', 0)) for c in conns))
                sig.append((p.name(), ids))
        return tuple(sig)

    def compute(self, context):
        # авто-инвалидация по контексту и по топологии/ревизиям
        ctx_sig = self._make_context_signature(context)
        up_sig  = self._make_upstream_signature()
        full_sig = (ctx_sig, up_sig)
        if full_sig != self._last_sig:
            self._last_sig = full_sig
            self._is_dirty = True

        depth = int(context.setdefault('_compute_depth', 0))
        pad = '  ' * depth
        tag = f"{self.__class__.__name__}({self.id})"

        if self._is_dirty:
            t0 = time.perf_counter()
            context['_compute_depth'] = depth + 1
            try:
                result = self._compute(context)
            finally:
                context['_compute_depth'] = depth
            self._result_cache = result
            self._is_dirty = False
            dt = (time.perf_counter() - t0) * 1000.0
            logger.debug(f"{pad}↻ recompute {tag} in {dt:.2f} ms")
        else:
            logger.debug(f"{pad}✓ cache-hit {tag}")

        return self._result_cache

    def _compute(self, context):
        raise NotImplementedError(
            f"Метод '_compute' не реализован в ноде '{self.name()}' (Тип: {self.__class__.__name__})"
        )

    # ======================================================================
    # ENUM-поля (Combo c фолбэком)
    # ======================================================================

    def add_enum_input(self, name: str, label: str, options, *, tab: str | None = None, default: str | None = None):
        """
        Добавляет выпадающий список. Если свойство уже есть (после хот-ревода),
        не создаём заново — только выставляем значение.
        При отсутствии combo — fallback на текст, но чтение валидируется через _enum().
        """
        opts = list(options)
        defval = default if default is not None else opts[0]

        try:
            if hasattr(self, "has_property") and self.has_property(name):
                self.set_property(name, defval)
                try:
                    return self.get_widget(name)
                except Exception:
                    return None
        except Exception:
            pass

        try:
            w = self.add_combo_menu(name, label, items=opts, tab=tab)
            self.set_property(name, defval)
            return w
        except Exception:
            if not (hasattr(self, "has_property") and self.has_property(name)):
                self.add_text_input(name, label, tab=tab, text=str(defval))
            else:
                self.set_property(name, defval)
            return None

    def _enum(self, name: str, allowed: list[str], default: str) -> str:
        """Читает enum-свойство (combo или текст), возвращая только допустимые значения."""
        v = self.get_property(name)
        if isinstance(v, int):
            return allowed[v] if 0 <= v < len(allowed) else default
        if isinstance(v, str):
            s = v.strip().lower()
            return s if s in allowed else default
        return default
