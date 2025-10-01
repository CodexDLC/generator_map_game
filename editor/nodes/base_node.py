# editor/nodes/base_node.py
# ВЕРСИЯ 6.1 (РЕФАКТОРИНГ): Исправлена реализация add_seed_input.
# - Убран ошибочный вызов set_default_text.
# - Начальное значение сида теперь корректно передается в register_text.
# ----------------------------------------------------------------------------
from __future__ import annotations

import random
import time
import logging
import textwrap
from typing import Any, Dict, List, Tuple

import numpy as np
from PySide6 import QtCore
from NodeGraphQt import BaseNode

from editor.nodes._helpers import node_ui as UIH
# --- ИЗМЕНЕНИЕ: Импортируем новую функцию ---
from editor.nodes._helpers import cache_utils as CU
# --- КОНЕЦ ИЗМЕНЕНИЯ ---

logger = logging.getLogger(__name__)


class GeneratorNode(BaseNode):
    __identifier__ = 'generator.nodes'

    def __init__(self):
        super().__init__()
        self._prop_meta: Dict[str, dict] = {}
        # --- НАЧАЛО ИЗМЕНЕНИЯ ---
        self._seed_history: Dict[str, List[int]] = {}
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        self._onnode_widgets: List[Any] = []
        self._compact: bool = True
        self._description_text: str = "Описание для этой ноды не задано."
        self._port_desc_by_name: Dict[str, str] = {}
        self._is_dirty: bool = True
        self._result_cache: Any = None
        self._rev: int = 0
        # --- ИЗМЕНЕНИЕ: Меняем _last_sig на _last_signature для ясности ---
        self._last_signature: Tuple[Any, ...] | None = None
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        self._apply_tooltips_to_node()
        self._deferred_init_tooltips()

    # --- НАЧАЛО ИЗМЕНЕНИЯ ---
    def add_to_seed_history(self, name: str, seed: int):
        """Добавляет сид в историю для указанного свойства."""
        if name not in self._seed_history:
            self._seed_history[name] = []

        history = self._seed_history[name]

        if seed in history:
            history.remove(seed)

        history.insert(0, seed)

        self._seed_history[name] = history[:15]
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    def add_seed_input(self, name, label, tab='Params', group=None):
        """
        Добавляет специализированный целочисленный ввод для сидов.
        При создании генерирует случайное начальное значение.
        """
        try:
            initial_seed = (int(self.id, 16) ^ int(time.time() * 1000)) & 0xFFFFFFFF
        except (ValueError, TypeError):
            initial_seed = random.randint(0, 0xFFFFFFFF)

        # --- НАЧАЛО ИЗМЕНЕНИЯ ---
        self._prop_meta[name] = {
            'type': 'seed',  # <-- Новый специальный тип!
            'label': label,
            'tab': UIH.safe_tab(tab),
            'group': group or UIH.safe_tab(tab)
        }
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        self.add_to_seed_history(name, initial_seed)

        # UIH.register_text по-прежнему используется для отображения на самой ноде
        UIH.register_text(self, self._onnode_widgets, name=name, label=label, text=str(initial_seed),
                          tab=tab, compact=self._compact)

        self.set_property(name, initial_seed, push_undo=False)


    def set_compact(self, compact: bool):
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

    def add_float_input(self, name, label, value=0.0, tab='Params', group=None):
        """Регистрирует свойство как float и создает для него текстовое поле."""
        # UI-часть остается такой же, как у add_text_input
        UIH.register_text(self, self._onnode_widgets, name=name, label=label, text=str(value),
                          tab=tab, compact=self._compact)
        # А вот метаданные теперь правильные
        self._prop_meta[name] = {
            'type': 'float', # <-- Вот ключевое изменение!
            'label': label,
            'tab': UIH.safe_tab(tab),
            'group': group or UIH.safe_tab(tab)
        }
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
            # --- ИЗМЕНЕНИЕ: Добавили 'seed' в список ---
            if kind in ('int', 'i', 'seed'): return 0
            if kind in ('float', 'double', 'f'): return 0.0
            if kind == 'check': return False
            return raw_value
        try:
            # --- ИЗМЕНЕНИЕ: Добавили 'seed' в список ---
            if kind in ('int', 'i', 'seed'):
                return int(float(str(raw_value).replace(',', '.')))
            elif kind in ('float', 'double', 'f'):
                return float(str(raw_value).replace(',', '.'))
            elif kind == 'check':
                if isinstance(raw_value, str):
                    return raw_value.lower() in ('true', '1', 't', 'y', 'yes')
                return bool(raw_value)
            return str(raw_value)
        except (ValueError, TypeError):
            # --- ИЗМЕНЕНИЕ: Добавили 'seed' в список ---
            if kind in ('int', 'i', 'seed'): return 0
            if kind in ('float', 'double', 'f'): return 0.0
            if kind == 'check': return False
            return raw_value

    def set_property(self, name, value, push_undo: bool = False):
        if name in ('color', 'text_color') and isinstance(value, str):
            try:
                clean_value = value.strip('()[] ')
                parts = [int(float(p.strip())) for p in clean_value.split(',')]
                if len(parts) >= 3:
                    value = tuple(parts[:3])
            except (ValueError, TypeError):
                pass

        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Проверяем, отличается ли значение ДО преобразования в строку
        try:
            if self.get_property(name) != value:
                self.mark_dirty()
        except Exception:
            self.mark_dirty()

        if name == 'name':
            val = str(value)
            if self.name() != val:
                self.set_name(val)

        # Преобразуем значение в строку для тех типов, которые используют
        # текстовое поле (QLineEdit) для отображения на самой ноде.
        # Ваш get_property() уже умеет преобразовывать это обратно в число.
        prop_meta = self._prop_meta.get(name)
        if prop_meta:
            kind = prop_meta.get('type')
            if kind in ('int', 'i', 'float', 'double', 'f', 'seed', 'line'):
                value = str(value)

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

    # --- ИЗМЕНЕНИЕ: Переписываем метод compute ---
    def compute(self, context: dict):
        # 1. Собираем полную сигнатуру состояния
        ctx_sig = CU.make_context_signature(context)
        up_sig = CU.make_upstream_signature(self)
        props_sig = CU.make_properties_signature(self)
        full_signature = (ctx_sig, up_sig, props_sig)

        # 2. Сравниваем с предыдущей сигнатурой
        if not self._is_dirty and full_signature == self._last_signature:
            # Если все совпадает и нода не "грязная", возвращаем кэш
            logger.debug(f"✓ cache-hit for {self.name()}")
            return self._result_cache

        # 3. Если сигнатура изменилась или нода помечена как грязная - пересчитываем
        logger.debug(f"↻ recomputing {self.name()}...")
        t0 = time.perf_counter()

        # Глубина вложенности для отладки
        depth = int(context.setdefault('_compute_depth', 0))
        context['_compute_depth'] = depth + 1
        try:
            # Вызываем основную логику вычислений
            result = self._compute(context)
        finally:
            # Восстанавливаем глубину
            context['_compute_depth'] = depth

        dt = (time.perf_counter() - t0) * 1000.0
        logger.debug(f"  -> recompute finished in {dt:.2f} ms")

        # 4. Сохраняем новый результат и сигнатуру в кэш
        self._result_cache = result
        self._last_signature = full_signature
        self._is_dirty = False # Сбрасываем флаг

        return self._result_cache
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---


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
