# editor/ui/menu.py
from PySide6 import QtWidgets

def build_menu(mw):
    m = mw.menuBar()

    proj_menu = m.addMenu("Проект")
    proj_menu.addAction("Сменить проект...").triggered.connect(mw._return_to_manager)
    proj_menu.addSeparator()
    proj_menu.addAction("Сохранить Проект").triggered.connect(mw.on_save_project)
    proj_menu.addSeparator()
    proj_menu.addAction("Сгенерировать Мир...").triggered.connect(mw.on_generate_world_menu)
    proj_menu.addSeparator()
    proj_menu.addAction("Выход").triggered.connect(mw.close)

    presets_menu = m.addMenu("Пресеты")
    presets_menu.addAction("Загрузить Пресет").triggered.connect(mw.on_load_pipeline_menu)
    presets_menu.addAction("Сохранить Пресет...").triggered.connect(mw.on_save_pipeline_menu)
