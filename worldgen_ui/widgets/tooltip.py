import tkinter as tk

class _Tooltip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _):
        if self.tip or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") or (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(self.tip, text=self.text, justify="left",
                       relief="solid", borderwidth=1,
                       background="#ffffe0")
        lbl.pack(ipadx=4, ipady=2)

    def _hide(self, _):
        if self.tip:
            self.tip.destroy()
            self.tip = None

def attach(widget, text: str):
    """Прикрепить всплывающую подсказку к виджету."""
    _Tooltip(widget, text)
