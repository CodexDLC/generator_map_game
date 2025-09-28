# editor/nodes/base_node.py
# ВЕРСИЯ 4.0: Компактные ноды. Свойства только в правой панели.
# -----------------------------------------------------------------------------
from __future__ import annotations

import time
import logging
import textwrap
from typing import Any, Dict, List, Tuple

import numpy as np
from PySide6 import QtCore
from NodeGraphQt import BaseNode

logger = logging.getLogger(__name__)


class GeneratorNode(BaseNode):
    """
    Базовая нода для генератора:
    - Никаких виджетов на самой ноде: только model.add_property(...) -> редактирование в PropertiesBin.
    - Кеширование результата с инвалидацией по контексту и апстриму.
    - Устойчивые тултипы (по именам портов).
    - Авто-инвалидация при connect/disconnect.
    """
    __identifier__ = 'generator.nodes'

    # --- Конструктор ---------------------------------------------------------
    def __init__(self):
        super().__init__()
        self._description_text: str = "Описание для этой ноды не задано."
        self._port_desc_by_name: Dict[str, str] = {}   # ключ: имя порта
        self._is_dirty: bool = True
        self._result_cache: Any = None
        self._rev: int = 0
        self._last_sig: Tuple[Any, Any] | None = None

        # Подсказки: безопасная инициализация после появления scene/view.
        self._apply_tooltips_to_node()
        self._deferred_init_tooltips()

    # --- Свойства только в модели (никаких виджетов на ноде) -----------------
    def add_text_input(self, name: str, label: str, text: str = '', tab: str = 'Properties'):
        self.model.add_property(name, text, tab=tab)
        return None

    def add_checkbox(self, name: str, label: str, text: str = '', state: bool = False, tab: str = 'Properties'):
        self.model.add_property(name, bool(state), tab=tab)
        return None

    def add_combo_menu(self, name: str, label: str, items: List[str] | None = None, tab: str = 'Properties'):
        items = items or []
        default_value = items[0] if items else ''
        self.model.add_property(name, default_value, items=items, tab=tab)
        return None

    def add_enum_input(self, name: str, label: str, options: List[str] | tuple, *,
                       tab: str = 'Properties', default: str | None = None):
        opts = list(options)
        defval = default if default is not None else (opts[0] if opts else '')
        self.model.add_property(name, defval, items=opts, tab=tab)
        return None

    # --- Унифицированная установка свойств с инвалидацией --------------------
    def set_property(self, name, value, push_undo: bool = False):
        try:
            if self.get_property(name) != value:
                self.mark_dirty()
        except Exception:
            self.mark_dirty()

        # синхронизируем title ноды с property "name" (если такое свойство есть)
        if name == 'name':
            val = str(value)
            if self.name() != val:
                self.set_name(val)

        super().set_property(name, value, push_undo=push_undo)

    # --- Подсказки (tooltips) -------------------------------------------------
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
        # Используем единый стиль доступа: .inputs()/.outputs() -> dict[name->port]
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

    # --- Порты: добавляем и сразу задаём дефолтные тултипы --------------------
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

    # --- Описание ноды --------------------------------------------------------
    def set_description(self, text: str):
        self._description_text = textwrap.dedent(str(text)).strip()
        self._apply_tooltips_to_node()

    def get_description(self) -> str:
        return self._description_text

    # --- Инвалидация / кеширование -------------------------------------------
    def mark_dirty(self):
        if self._is_dirty:
            return
        self._is_dirty = True
        self._result_cache = None
        self._rev += 1
        # проталкиваем грязность вниз по графу
        for port in self.outputs().values():
            for conn in port.connected_ports():
                node = conn.node()
                if isinstance(node, GeneratorNode):
                    node.mark_dirty()

    # На свежем NodeGraphQt эти хуки вызываются, когда порты соединяются/разрываются
    def on_connected(self, in_port, out_port):
        super().on_connected(in_port, out_port)
        self.mark_dirty()

    def on_disconnected(self, in_port, out_port):
        super().on_disconnected(in_port, out_port)
        self.mark_dirty()

    # --- Сигнатуры для кеша ---------------------------------------------------
    def _make_context_signature(self, context: dict) -> Tuple[Any, ...]:
        try:
            seed = int(context.get('seed'))
            cell_size = float(context.get('cell_size'))
            x = context.get('x_coords')
            grid_shape = getattr(x, 'shape', None)
            gn = context.get('global_noise')
            gn_sig = tuple(sorted(gn.items())) if isinstance(gn, dict) else None
            ctx_rev = context.get('_ctx_rev', None)
            return ('v2', seed, cell_size, grid_shape, gn_sig, ctx_rev)
        except Exception:
            return ('v2_fallback', id(context))

    def _make_upstream_signature(self) -> Tuple[Any, ...]:
        sig = []
        for p in self.inputs().values():
            conns = p.connected_ports()
            if not conns:
                sig.append((p.name(), None))
            else:
                ids = tuple(sorted((c.node().id, getattr(c.node(), '_rev', 0)) for c in conns))
                sig.append((p.name(), ids))
        return tuple(sig)

    # --- Основной compute с кешированием -------------------------------------
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

    # --- Абстрактная реализация узла -----------------------------------------
    def _compute(self, context: dict):
        raise NotImplementedError(
            f"Метод '_compute' не реализован в ноде '{self.name()}' (Тип: {self.__class__.__name__})"
        )

    # --- Утилиты для чтения свойств ------------------------------------------
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
