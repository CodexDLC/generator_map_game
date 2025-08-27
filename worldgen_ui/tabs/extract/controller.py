from collections import namedtuple
from ...services import worldgen as svc
from .view import ExtractView

TabHandle = namedtuple("TabHandle", "name frame on_show dispose")

def make_tab(parent, services):
    ui = ExtractView(parent)

    def on_click():
        args = ui.state.to_args()
        ui.btn_run.config(state="disabled")
        def done():
            ui.btn_run.after(0, lambda: ui.btn_run.config(state="normal"))
        t = svc.extract(*args)
        ui.btn_run.after(200, lambda: (None if t.is_alive() else done()))

    ui.btn_run.config(command=on_click)
    return TabHandle(name="Extract", frame=ui.frame, on_show=lambda: None, dispose=lambda: None)
