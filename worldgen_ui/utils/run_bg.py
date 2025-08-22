import threading

def run_bg(fn, on_done=None):
    def _wrap():
        try:
            fn()
        finally:
            if on_done: on_done()
    t = threading.Thread(target=_wrap, daemon=True)
    t.start()
    return t
