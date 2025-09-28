# editor/nodes/_helpers/node_ui.py
from __future__ import annotations
from typing import Any, List, Optional

from NodeGraphQt import BaseNode

try:
    from NodeGraphQt.constants import NodePropWidgetEnum  # может не быть
except Exception:
    NodePropWidgetEnum = None  # type: ignore

RESERVED_TABS = {"Node", "Ports", ""}

def safe_tab(tab: str) -> str:
    t = (tab or "Params").strip()
    return "Params" if t in RESERVED_TABS else t

def widget_enum(member: str):
    try:
        return getattr(NodePropWidgetEnum, member) if NodePropWidgetEnum else None
    except Exception:
        return None

def hide_widget(w) -> None:
    try:
        if not w:
            return
        w.setVisible(False)
        if hasattr(w, "setMaximumHeight"):
            w.setMaximumHeight(0)
        if hasattr(w, "setMinimumHeight"):
            w.setMinimumHeight(0)
    except Exception:
        pass

def show_widget(w) -> None:
    try:
        if not w:
            return
        w.setVisible(True)
        if hasattr(w, "setMaximumHeight"):
            w.setMaximumHeight(24)
        if hasattr(w, "setMinimumHeight"):
            w.setMinimumHeight(16)
    except Exception:
        pass

def add_property_compat(node, name, value, *, items=None, tab="Params", widget_type=None):
    """Запасной путь для старых сборок: напрямую в модель."""
    try:
        items = list(items) if items else []
        return node.model.add_property(name, value, items=items, tab=tab)
    except Exception:
        return None

# --- Регистрация свойств нативным API + скрытие он-нод виджетов --------------

def register_text(node: BaseNode, widgets: List[Any], *,
                  name: str, label: str, text: str = "", tab: str = "Params",
                  compact: bool = True) -> None:
    tab = safe_tab(tab)
    fn = getattr(BaseNode, "add_text_input", None)
    if callable(fn):
        try:
            w = fn(node, name, label, text=text, tab=tab)
            widgets.append(w)
            if compact:
                hide_widget(w)
            return
        except Exception:
            pass
    add_property_compat(node, name, text, tab=tab, widget_type=widget_enum("LINE_EDIT"))

def register_checkbox(node: BaseNode, widgets: List[Any], *,
                      name: str, label: str, text: str = "", state: bool = False,
                      tab: str = "Params", compact: bool = True) -> None:
    tab = safe_tab(tab)
    fn = getattr(BaseNode, "add_checkbox", None)
    if callable(fn):
        try:
            w = fn(node, name, label, text=text, state=bool(state), tab=tab)
            widgets.append(w)
            if compact:
                hide_widget(w)
            return
        except Exception:
            pass
    add_property_compat(node, name, bool(state), tab=tab, widget_type=widget_enum("CHECKBOX"))

def register_combo(node: BaseNode, widgets: List[Any], *,
                   name: str, label: str, items: Optional[list] = None,
                   tab: str = "Params", compact: bool = True,
                   default: Optional[str] = None) -> None:
    tab = safe_tab(tab)
    items = list(items) if items else []
    fn = getattr(BaseNode, "add_combo_menu", None)
    if callable(fn):
        try:
            w = fn(node, name, label, items=items, tab=tab)
            widgets.append(w)
            if compact:
                hide_widget(w)
            if default is not None:
                try:
                    node.set_property(name, default)
                except Exception:
                    pass
            return
        except Exception:
            pass
    defval = default if default is not None else (items[0] if items else "")
    add_property_compat(node, name, defval, items=items, tab=tab,
                        widget_type=widget_enum("COMBO_BOX"))
