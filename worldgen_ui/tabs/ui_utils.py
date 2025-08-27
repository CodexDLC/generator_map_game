import tkinter as tk


def create_help_window(parent, title: str, help_content: list):
    """
    Создает и настраивает стандартное окно справки.

    :param parent: Родительский виджет.
    :param title: Заголовок окна.
    :param help_content: Список кортежей (тег, текст) из HELP_TEXTS.
    """
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("650x600")
    win.transient(parent)
    win.grab_set()

    text_widget = tk.Text(win, wrap="word", padx=10, pady=10, relief="flat", background="#f0f0f0")
    text_widget.pack(expand=True, fill="both")

    # Настройка стилей текста
    text_widget.tag_configure("h1", font=("TkDefaultFont", 14, "bold"), spacing3=10)
    text_widget.tag_configure("h2", font=("TkDefaultFont", 11, "bold"), spacing1=10, spacing3=5)
    text_widget.tag_configure("h3", font=("TkDefaultFont", 10, "bold"), spacing1=5, spacing3=3)
    text_widget.tag_configure("p", lmargin1=10, lmargin2=10)

    # Заполнение контентом
    for tag, content in help_content:
        text_widget.insert("end", content + "\n\n", tag)

    text_widget.configure(state="disabled")