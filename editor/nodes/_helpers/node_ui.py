# editor/nodes/_helpers/node_ui.py
# ВЕРСИЯ 2.1: Отключаем создание виджетов на ноде для чистого UI.
from __future__ import annotations
from typing import Any, List, Optional

from NodeGraphQt import BaseNode

try:
    from NodeGraphQt.constants import NodePropWidgetEnum
except Exception:
    NodePropWidgetEnum = None

RESERVED_TABS = {"Node", "Ports", ""}

def safe_tab(tab: str) -> str:
    t = (tab or "Params").strip()
    return "Params" if t in RESERVED_TABS else t

def widget_enum(member: str):
    try:
        return getattr(NodePropWidgetEnum, member) if NodePropWidgetEnum else None
    except Exception:
        return None

# --- Функции hide/show больше не нужны, но можно их оставить ---
def hide_widget(w) -> None:
    pass

def show_widget(w) -> None:
    pass
# ----------------------------------------------------------------

def add_property_compat(node, name, value, *, items=None, tab="Params", widget_type=None):
    """Запасной путь для старых сборок: напрямую в модель."""
    try:
        items = list(items) if items else []
        return node.model.add_property(name, value, items=items, tab=tab, widget_type=widget_type)
    except Exception:
        # Более старый API
        return node.model.add_property(name, value, items=items, tab=tab)

# --- НАЧАЛО ИЗМЕНЕНИЙ ---

def register_text(node: BaseNode, widgets: List[Any], *,
                  name: str, label: str, text: str = "", tab: str = "Params",
                  compact: bool = True) -> Any:
    tab = safe_tab(tab)
    add_property_compat(node, name, text, tab=tab, widget_type=widget_enum("LINE_EDIT"))
    return None

def register_checkbox(node: BaseNode, widgets: List[Any], *,
                      name: str, label: str, text: str = "", state: bool = False,
                      tab: str = "Params", compact: bool = True) -> Any:
    tab = safe_tab(tab)
    add_property_compat(node, name, bool(state), tab=tab, widget_type=widget_enum("CHECKBOX"))
    # Для чекбоксов также установим текст, если он есть
    try:
        node.set_custom_widget_text(name, text)
    except:
        pass
    return None

def register_combo(node: BaseNode, widgets: List[Any], *,
                   name: str, label: str, items: Optional[list] = None,
                   tab: str = "Params", compact: bool = True,
                   default: Optional[str] = None) -> Any:
    tab = safe_tab(tab)
    items = list(items) if items else []
    defval = default if default is not None else (items[0] if items else "")
    add_property_compat(node, name, defval, items=items, tab=tab,
                        widget_type=widget_enum("COMBO_BOX"))
    return None

# --- КОНЕЦ ИЗМЕНЕНИЙ ---