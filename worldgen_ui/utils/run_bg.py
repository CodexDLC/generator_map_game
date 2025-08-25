import threading

def run_bg(fn, on_done=None, master_widget=None):
    """
    Запускает функцию fn в фоновом потоке.
    По завершении вызывает on_done в основном потоке UI.
    """
    result = [None]  # Используем список, чтобы сделать переменную изменяемой внутри _wrap

    def _wrap():
        try:
            result[0] = fn()
        finally:
            if on_done:
                # Вызываем on_done безопасно в основном потоке Tkinter
                if master_widget:
                    master_widget.after(0, lambda: on_done(result[0]))
                else:
                    on_done(result[0])

    t = threading.Thread(target=_wrap, daemon=True)
    t.start()
    return t