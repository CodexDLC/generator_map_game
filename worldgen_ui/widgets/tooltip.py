import tkinter as tk

class Tooltip:
    _keepalive = []  # глобально удерживаем ссылки

    def __init__(self, widget, text: str, delay_ms=300):
        self.widget, self.text, self.delay = widget, text, delay_ms
        self._after_id = None
        self._tw = None
        # добавляем бинды, не перетирая существующие
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        Tooltip._keepalive.append(self)  # не даём GC удалить

    def _schedule(self, _):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self._tw or not self.text:
            return
        root = self.widget.winfo_toplevel()
        x, y = self.widget.winfo_pointerxy()  # показываем у курсора
        tw = tk.Toplevel(root)
        self._tw = tw
        tw.wm_overrideredirect(True)
        try:
            tw.wm_attributes("-topmost", True)
            tw.transient(root)
        except Exception:
            pass
        tw.geometry(f"+{x+12}+{y+12}")
        tk.Label(tw, text=self.text, justify="left",
                 background="#ffffe0", relief="solid",
                 borderwidth=1, padx=6, pady=4).pack()

    def _hide(self, _=None):
        self._cancel()
        if self._tw:
            self._tw.destroy()
            self._tw = None

    def _cancel(self):
        if self._after_id:
            try: self.widget.after_cancel(self._after_id)
            finally: self._after_id = None

def tip(widget, text: str):
    return Tooltip(widget, text)
