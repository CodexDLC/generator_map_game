# editor/nodes/base_node.py
# -----------------------------------------------------------------------------
# ВЕРСИЯ С ВЫНЕСЕННЫМИ ВИДЖЕТАМИ
# -----------------------------------------------------------------------------

import time
import logging
import numpy as np
from NodeGraphQt import BaseNode
from PySide6 import QtCore

from ..widgets.separator_widget import SeparatorWidget


logger = logging.getLogger(__name__)

class GeneratorNode(BaseNode):
    __identifier__ = 'generator.nodes'

    def __init__(self):
        super().__init__()
        # Служебные поля
        self._description_text = "Описание для этой ноды не задано."
        self._port_desc = {}
        self._is_dirty = True
        self._result_cache = None
        self._rev = 0
        self._last_sig = None
        self._last_tab_name = None

        # Свойства по умолчанию
        self.add_text_input('node_name', 'Node Name', tab='Node Properties', text=self.name())
        id_widget = self.add_text_input('display_id', 'Node ID', tab='Node Properties', text=self.id)
        if id_widget and hasattr(id_widget.get_custom_widget(), 'setReadOnly'):
            id_widget.get_custom_widget().setReadOnly(True)

        self.add_text_input('about_desc_fallback', 'Description', tab='About', text=self._description_text)
        self._apply_tooltips_to_node()
        self._deferred_init_tooltips()

    def _add_property_with_separator(self, add_func, *args, **kwargs):
        tab_name = kwargs.get('tab')
        if tab_name and tab_name != self._last_tab_name:
            sep_name = f'_separator_{tab_name.replace(" ", "_")}'
            if not self.has_property(sep_name):
                self.add_custom_widget(SeparatorWidget(name=sep_name, label=tab_name))
            self._last_tab_name = tab_name
        kwargs.pop('tab', None)
        return add_func(*args, **kwargs)


    # --- Переопределяем стандартные методы, чтобы они использовали наш перехватчик ---
    def add_text_input(self, name, label, text='', tab=None):
        return self._add_property_with_separator(
            super().add_text_input, name, label, text=text, tab=tab
        )

    def add_checkbox(self, name, label, text='', state=False, tab=None):
        return self._add_property_with_separator(
            super().add_checkbox, name, label, text=text, state=state, tab=tab
        )

    def add_combo_menu(self, name, label, items=None, tab=None):
        items = items or []
        return self._add_property_with_separator(
            super().add_combo_menu, name, label, items=items, tab=tab
        )

    def add_custom_widget(self, widget, widget_type=None, tab=None):
        return self._add_property_with_separator(
            super().add_custom_widget, widget, widget_type=widget_type, tab=tab
        )

    # -----------------------------------------

    def set_property(self, name, value, push_undo=False, **kwargs):
        try:
            if self.get_property(name) != value:
                self.mark_dirty()
        except Exception:
            self.mark_dirty()

        if name == 'node_name':
            if self.name() != str(value):
                self.set_name(str(value))

        return super().set_property(name, value, push_undo=push_undo, **kwargs)

    def _deferred_init_tooltips(self, tries=0, delay_ms=50):
        v = getattr(self, 'view', None)
        if v is None or v.scene() is None:
            if tries < 10:
                QtCore.QTimer.singleShot(delay_ms, lambda: self._deferred_init_tooltips(tries + 1, delay_ms))
            return

        # Если все на месте, применяем подсказки
        self._apply_tooltips_to_node()
        self._apply_tooltips_to_ports()

    def _safe_tip(self, item, txt):
        try:
            if item and hasattr(item, 'scene') and item.scene() is not None:
                item.setToolTip(txt)
        except Exception:
            pass

    def _apply_tooltips_to_node(self):
        v = getattr(self, 'view', None)
        if not v or getattr(v, 'scene', lambda: None)() is None: return
        txt = self._description_text
        self._safe_tip(v, txt)
        for attr in ('title_item', '_name_item', 'name_item', 'bg_item', 'content', 'content_widget'):
            self._safe_tip(getattr(v, attr, None), txt)
        try:
            for it in v.childItems(): self._safe_tip(it, txt)
        except Exception:
            pass

    def _apply_tooltips_to_ports(self):
        v = getattr(self, 'view', None)
        if not v or getattr(v, 'scene', lambda: None)() is None: return
        for p in list(self.inputs().values()) + list(self.outputs().values()):
            vi = getattr(p, 'view', None)
            if vi and getattr(vi, 'scene', lambda: None)() is not None:
                txt = self._port_desc.get(p, f"{self.name()} · {p.name()}")
                self._safe_tip(vi, txt)

    def set_port_description(self, port_obj, text: str):
        self._port_desc[port_obj] = str(text)
        self._apply_tooltips_to_ports()

    def set_port_description_by_name(self, port_name: str, text: str):
        for p in list(self.inputs().values()) + list(self.outputs().values()):
            if p.name() == port_name:
                self.set_port_description(p, text)
                return

    def add_input(self, name='input', multi_input=False, display_name=True,
                  color=None, locked=False, painter_func=None):
        p = super().add_input(name, multi_input, display_name, color, locked, painter_func)
        try:
            self._port_desc.setdefault(p, f"{self.name()} · {p.name()}")
            vi = getattr(p, 'view', None)
            if vi: vi.setToolTip(self._port_desc[p])
        except Exception:
            pass
        return p

    def add_output(self, name='output', multi_output=True, display_name=True,
                   color=None, locked=False, painter_func=None):
        p = super().add_output(name, multi_output, display_name, color, locked, painter_func)
        try:
            self._port_desc.setdefault(p, f"{self.name()} · {p.name()}")
            vi = getattr(p, 'view', None)
            if vi: vi.setToolTip(self._port_desc[p])
        except Exception:
            pass
        return p

    def set_description(self, text: str):
        import textwrap
        self._description_text = textwrap.dedent(text).strip()
        try:
            if hasattr(self, "has_property") and self.has_property('about_desc_fallback'):
                self.set_property('about_desc_fallback', self._description_text)
        except Exception:
            pass
        self._apply_tooltips_to_node()

    def get_description(self) -> str:
        return self._description_text

    def mark_dirty(self):
        if self._is_dirty: return
        self._is_dirty = True
        self._result_cache = None
        self._rev += 1
        for port in self.output_ports():
            for conn in port.connected_ports():
                node = conn.node()
                if isinstance(node, GeneratorNode):
                    node.mark_dirty()

    def _make_context_signature(self, context: dict):
        try:
            seed = int(context.get('seed'))
            cell_size = float(context.get('cell_size'))
            grid_shape = getattr(context.get('x_coords'), 'shape', None)
            gn = context.get('global_noise')
            gn_sig = tuple(sorted(gn.items())) if isinstance(gn, dict) else None
            ctx_rev = context.get('_ctx_rev', None)
            return 'v1', seed, cell_size, grid_shape, gn_sig, ctx_rev
        except Exception:
            return 'v1_fallback', id(context)

    def _make_upstream_signature(self):
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
        ctx_sig = self._make_context_signature(context)
        up_sig = self._make_upstream_signature()
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

    def add_enum_input(self, name: str, label: str, options, *, tab: str | None = None, default: str | None = None):
        return self._add_property_with_separator(
            self._add_enum_input_base, name, label, options, tab=tab, default=default
        )

    def _add_enum_input_base(self, name: str, label: str, options, *, tab: str | None = None,
                             default: str | None = None):
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
            w = self.add_combo_menu(name, label, items=opts)
            self.set_property(name, defval)
            return w
        except Exception:
            if not (hasattr(self, "has_property") and self.has_property(name)):
                self.add_text_input(name, label, text=str(defval))
            else:
                self.set_property(name, defval)
            return None

    def _enum(self, name: str, allowed: list[str], default: str) -> str:
        v = self.get_property(name)
        if isinstance(v, int):
            return allowed[v] if 0 <= v < len(allowed) else default
        if isinstance(v, str):
            s = v.strip().lower()
            return s if s in allowed else default
        return default

    def _f(self, name: str, default: float) -> float:
        v = self.get_property(name)
        try:
            if v in ("", None):
                return float(default)
            v = str(v).replace(',', '.')
            x = float(v)
            return x if np.isfinite(x) else float(default)
        except (TypeError, ValueError):
            return float(default)