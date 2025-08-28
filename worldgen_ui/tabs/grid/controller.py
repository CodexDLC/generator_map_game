from collections import namedtuple
from ...services import worldgen as svc
import threading
from .view import GridView

TabHandle = namedtuple("TabHandle", "name frame on_show dispose")

def make_tab(parent, services):
    ui = GridView(parent)

    def on_generate_click():
        # Здесь мы получаем словарь args со всеми параметрами, включая wall_chance
        args = ui.state.to_args()
        ui.lbl_status.config(text="Генерация...")
        ui.btn_generate.config(state="disabled")

        def task_done(result):
            if isinstance(result, dict):
                png_path = result.get("png")
                json_path = result.get("json")
            else:
                png_path = result
                json_path = None

            if png_path:
                ui.set_preview_image(png_path)
                ui.lbl_status.config(text="Готово! Карта сохранена.")
            else:
                ui.lbl_status.config(text="Ошибка генерации.")

            if json_path:
                ui.show_json_path(json_path)

            ui.btn_generate.config(state="normal")

        def task():
            try:
                res = svc.generate_grid_sync(**args)
                ui.frame.after(0, lambda: task_done(res))
            except Exception as e:
                import logging
                logging.error(f"Ошибка в потоке генерации: {e}", exc_info=True)
                ui.frame.after(0, lambda: task_done(None))

        # Добавим импорт logging для отладки
        import logging
        t = threading.Thread(target=task, daemon=True)
        t.start()

    ui.btn_generate.config(command=on_generate_click)
    return TabHandle(name="Grid", frame=ui.frame, on_show=lambda: None, dispose=lambda: None)