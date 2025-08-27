from threading import Thread

def run_in_thread(fn, *args, **kwargs) -> Thread:
    t = Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t
