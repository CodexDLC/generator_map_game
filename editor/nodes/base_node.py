# editor/nodes/base_node.py
# ВЕРСИЯ 5.2 (HOTFIX): Исправлена инициализация виджетов на нодах.
# ----------------------------------------------------------------------------
from __future__ import annotations

import time
import logging
import textwrap
from typing import Any, Dict, List, Tuple

import numpy as np
from PySide6 import QtCore
from NodeGraphQt import BaseNode

# Хелперы UI и кеш-сигнатур
from editor.nodes._helpers import node_ui as UIH
from editor.nodes._helpers import cache_utils as CU

logger = logging.getLogger(__name__)


class GeneratorNode(BaseNode):
    """
    Базовый узел:
      - Свойства регистрируются нативным API NodeGraphQt (панель свойств их видит).
      - На самой ноде виджеты можно скрывать (compact=True) или показывать (compact=False).
      - Кеш вычислений с инвалидацией по контексту и апстриму.
      - Тултипы для ноды и портов.
    """
    __identifier__ = 'generator.nodes'

    def __init__(self):
        super().__init__()

        self._prop_meta: Dict[
            str, dict] = {}  # {name: {'type': 'line'|'check'|'combo', 'label': str, 'tab': str, 'items': list}}

        self._onnode_widgets: List[Any] = []
        self._compact: bool = True

        self._description_text: str = "Описание для этой ноды не задано."
        self._port_desc_by_name: Dict[str, str] = {}

        self._is_dirty: bool = True
        self._result_cache: Any = None
        self._rev: int = 0
        self._last_sig: Tuple[Any, Any] | None = None

        self._apply_tooltips_to_node()
        self._deferred_init_tooltips()

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)
        for w in self._onnode_widgets:
            (UIH.hide_widget if self._compact else UIH.show_widget)(w)
        try:
            if getattr(self, 'view', None):
                self.view.update()
        except Exception:
            pass

    def toggle_compact(self) -> None:
        self.set_compact(not self._compact)

    def add_text_input(self, name, label, text='', tab='Params', group=None):
        UIH.register_text(self, self._onnode_widgets, name=name, label=label, text=text,
                          tab=tab, compact=self._compact)
        self._prop_meta[name] = {'type': 'line', 'label': label, 'tab': UIH.safe_tab(tab),
                                 'group': group or UIH.safe_tab(tab), 'items': []}
        return None

    def add_checkbox(self, name, label, text='', state=False, tab='Params', group=None):
        UIH.register_checkbox(self, self._onnode_widgets, name=name, label=label, text=text,
                              state=state, tab=tab, compact=self._compact)
        self._prop_meta[name] = {'type': 'check', 'label': label, 'tab': UIH.safe_tab(tab),
                                 'group': group or UIH.safe_tab(tab), 'items': []}
        return None

    def add_combo_menu(self, name, label, items=None, tab='Params', group=None):
        items = list(items) if items else []
        UIH.register_combo(self, self._onnode_widgets, name=name, label=label, items=items,
                           tab=tab, compact=self._compact)
        self._prop_meta[name] = {'type': 'combo', 'label': label, 'tab': UIH.safe_tab(tab),
                                 'group': group or UIH.safe_tab(tab), 'items': items}
        return None

    def add_enum_input(self, name, label, options, *, tab='Params', group=None, default=None):
        items = list(options) if options else []
        UIH.register_combo(self, self._onnode_widgets, name=name, label=label, items=items,
                           tab=tab, compact=self._compact, default=default)
        self._prop_meta[name] = {'type': 'combo', 'label': label, 'tab': UIH.safe_tab(tab),
                                 'group': group or UIH.safe_tab(tab), 'items': items}
        
        # --- HOTFIX: Принудительно устанавливаем значение по умолчанию, чтобы обновить виджет на ноде ---
        if default is not None:
            self.set_property(name, default, push_undo=False)

        return None

    def properties_meta(self) -> Dict[str, dict]:
        return self._prop_meta

    def get_property(self, name: str) -> Any:
        raw_value = super().get_property(name)
        if name not in self._prop_meta:
            return raw_value
        meta = self._prop_meta[name]
        kind = meta.get('type')
        if raw_value is None or raw_value == '':
            if kind in ('int', 'i'): return 0
            if kind in ('float', 'double', 'f'): return 0.0
            if kind == 'check': return False
            return raw_value
        try:
            if kind in ('int', 'i'):
                return int(float(str(raw_value).replace(',', '.')))
            elif kind in ('float', 'double', 'f'):
                return float(str(raw_value).replace(',', '.'))
            elif kind == 'check':
                if isinstance(raw_value, str):
                    return raw_value.lower() in ('true', '1', 't', 'y', 'yes')
                return bool(raw_value)
            return str(raw_value)
        except (ValueError, TypeError):
            if kind in ('int', 'i'): return 0
            if kind in ('float', 'double', 'f'): return 0.0
            if kind == 'check': return False
            return raw_value

    def set_property(self, name, value, push_undo: bool = False):
        try:
            if self.get_property(name) != value:
                self.mark_dirty()
        except Exception:
            self.mark_dirty()
        if name == 'name':
            val = str(value)
            if self.name() != val:
                self.set_name(val)
        super().set_property(name, value, push_undo=push_undo)

    def _deferred_init_tooltips(self, tries: int = 0, delay_ms: int = 50):
        v = getattr(self, 'view', None)
        if v is None or v.scene() is None:
            if tries < 20:
                QtCore.QTimer.singleShot(delay_ms, lambda: self._deferred_init_tooltips(tries + 1, delay_ms))
            return
        self._apply_tooltips_to_node()
        self._apply_tooltips_to_ports()

    def _safe_tip(self, item, txt: str):
        try:
            if item and hasattr(item, 'scene') and item.scene() is not None:
                item.setToolTip(txt)
        except Exception:
            pass

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
                name = p.name()
                txt = self._port_desc_by_name.get(name, f"{self.name()} · {name}")
                self._safe_tip(vi, txt)

    def set_port_description(self, port_obj, text: str):
        if not port_obj:
            return
        self._port_desc_by_name[port_obj.name()] = str(text)
        self._apply_tooltips_to_ports()

    def set_port_description_by_name(self, port_name: str, text: str):
        self._port_desc_by_name[str(port_name)] = str(text)
        self._apply_tooltips_to_ports()

    def add_input(self, name='input', multi_input=False, display_name=True,
                  color=None, locked=False, painter_func=None):
        p = super().add_input(name, multi_input, display_name, color, locked, painter_func)
        self._port_desc_by_name.setdefault(p.name(), f"{self.name()} · {p.name()}")
        self._apply_tooltips_to_ports()
        return p

    def add_output(self, name='output', multi_output=True, display_name=True,
                   color=None, locked=False, painter_func=None):
        p = super().add_output(name, multi_output, display_name, color, locked, painter_func)
        self._port_desc_by_name.setdefault(p.name(), f"{self.name()} · {p.name()}")
        self._apply_tooltips_to_ports()
        return p

    def set_description(self, text: str):
        self._description_text = textwrap.dedent(str(text)).strip()
        self._apply_tooltips_to_node()

    def get_description(self) -> str:
        return self._description_text

    def mark_dirty(self):
        if self._is_dirty:
            return
        self._is_dirty = True
        self._result_cache = None
        self._rev += 1
        for port in self.outputs().values():
            for conn in port.connected_ports():
                node = conn.node()
                if isinstance(node, GeneratorNode):
                    node.mark_dirty()

    def on_connected(self, in_port, out_port):
        super().on_connected(in_port, out_port)
        self.mark_dirty()

    def on_disconnected(self, in_port, out_port):
        super().on_disconnected(in_port, out_port)
        self.mark_dirty()

    def _make_context_signature(self, context: dict):
        return CU.make_context_signature(context)

    def _make_upstream_signature(self):
        return CU.make_upstream_signature(self)

    def compute(self, context: dict):
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

    def _compute(self, context: dict):
        raise NotImplementedError(
            f"Метод '_compute' не реализован в ноде '{self.name()}' (Тип: {self.__class__.__name__})"
        )

    def _enum(self, name: str, allowed: List[str], default: str) -> str:
        v = self.get_property(name)
        if isinstance(v, int):
            return allowed[v] if 0 <= v < len(allowed) else default
        if isinstance(v, str):
            s = v.strip().lower()
            low = [a.lower() for a in allowed]
            return allowed[low.index(s)] if s in low else default
        return default

    def _f(self, name: str, default: float) -> float:
        v = self.get_property(name)
        try:
            if v in ("", None):
                return float(default)
            x = float(str(v).replace(',', '.'))
            return x if np.isfinite(x) else float(default)
        except (TypeError, ValueError):
            return float(default)
