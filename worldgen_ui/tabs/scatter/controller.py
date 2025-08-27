from collections import namedtuple
from ...services import worldgen as svc
from .view import ScatterView

TabHandle = namedtuple("TabHandle", "name frame on_show dispose")

def make_tab(parent, services):
    ui = ScatterView(parent)

    def on_click():
        args = ui.state.to_args()
        ui.btn_run.config(state="disabled")
        ui.lbl_status.config(text="Размещение объектов...")

        # сервис вызывает реализацию из worldgen_core.scatter.scatter_world, если она есть
        t = svc.scatter(**args)

        def poll():
            if t.is_alive():
                ui.frame.after(150, poll)
            else:
                ui.lbl_status.config(text="Готово.")
                ui.btn_run.config(state="normal")

        ui.frame.after(150, poll)

    ui.btn_run.config(command=on_click)
    return TabHandle(name="Scatter", frame=ui.frame, on_show=lambda: None, dispose=lambda: None)
