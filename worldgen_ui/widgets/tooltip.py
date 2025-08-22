import tkinter as tk

class Tooltip:
    def __init__(self, widget, text: str, delay_ms=300):
        self.widget, self.text, self.delay = widget, text, delay_ms
        self.tip, self.after_id = None, None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _): self.after_id = self.widget.after(self.delay, self._show)
    def _show(self):
        if self.tip or not self.text: return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify="left", relief="solid",
                 borderwidth=1, background="#ffffe0", padx=6, pady=4).pack()
    def _hide(self, _=None):
        if self.after_id: self.widget.after_cancel(self.after_id); self.after_id = None
        if self.tip: self.tip.destroy(); self.tip = None

def tip(widget, text): Tooltip(widget, text)
