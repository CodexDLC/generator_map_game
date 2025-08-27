from collections import namedtuple
from pathlib import Path
from queue import Empty

from ...services import worldgen as svc
from .view import GenerateView

TabHandle = namedtuple("TabHandle", "name frame on_show dispose")


def make_tab(parent, services):
    ui = GenerateView(parent)

    def on_click():
        cfg = ui.state.to_config()

        cols = (cfg.width + cfg.chunk - 1) // cfg.chunk
        rows = (cfg.height + cfg.chunk - 1) // cfg.chunk
        total = max(1, cols * rows)

        ui.init_grid(cols, rows, tile_px=96)
        ui.btn_gen.config(state="disabled")
        ui.prog.config(value=0, maximum=total)
        ui.prog.grid()  # показать прогресс-бар только во время генерации
        ui.lbl_status.config(text="Генерация...")

        t, q = svc.generate(cfg)
        done = 0

        out_root = Path(getattr(cfg, "out_dir", "out")) / cfg.world_id / cfg.version

        def poll():
            nonlocal done
            while True:
                try:
                    msg = q.get_nowait()
                except Empty:
                    break

                if isinstance(msg, tuple) and len(msg) == 3:
                    if msg[0] == "done":
                        finalize()
                        return
                    cx, cy, _ = msg
                    p = out_root / f"chunk_{cx}_{cy}" / "biome.png"
                    if not p.exists():
                        p = out_root / f"chunk_{cx}_{cy}" / "height.png"
                    if p.exists():
                        ui.set_tile_image(cx, cy, p.as_posix())
                    done += 1
                    ui.prog.config(value=min(done, total))
                    ui.lbl_status.config(text=f"Чанк {cx},{cy} — {done}/{total}")

            if t.is_alive():
                ui.frame.after(100, poll)
            else:
                finalize()

        def finalize():
            ui.prog.grid_remove()          # спрятать прогресс-бар
            ui.prog.config(value=0)        # сбросить значение
            ui.lbl_status.config(text="Готово.")
            ui.btn_gen.config(state="normal")

        ui.frame.after(100, poll)

    ui.btn_gen.config(command=on_click)
    return TabHandle(name="Generate", frame=ui.frame, on_show=lambda: None, dispose=lambda: None)
