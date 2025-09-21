# ==============================================================================
# Файл: editor/actions/worker.py
# Назначение: Worker для выполнения долгих задач в фоновом потоке.
# ==============================================================================
from PySide6 import QtCore

# Импортируем сам движок
from game_engine_restructured.world_actor import WorldActor
from game_engine_restructured.world.regions import RegionManager


class GenerationWorker(QtCore.QObject):
    """
    Worker, который выполняет генерацию мира в отдельном потоке.
    """
    # Сигналы для связи с основным потоком UI
    progress = QtCore.Signal(int, str)  # процент, сообщение
    finished = QtCore.Signal(str)  # сообщение о завершении
    error = QtCore.Signal(str)  # сообщение об ошибке

    def __init__(self, world_seed, graph_data, artifacts_root, radius):
        super().__init__()
        self.world_seed = world_seed
        self.graph_data = graph_data
        self.artifacts_root = artifacts_root
        self.radius = radius
        self.is_running = True

    def run(self):
        """
        Основной метод, который будет выполняться в фоновом потоке.
        """
        try:
            # Создаем коллбэк, который будет пробрасывать прогресс в наш сигнал
            def progress_callback(percent, message):
                if not self.is_running:
                    # Генерируем исключение, чтобы корректно прервать процесс
                    raise InterruptedError("Generation was cancelled.")
                self.progress.emit(percent, message)

            # Передаем этот коллбэк в WorldActor
            region_manager = RegionManager(self.world_seed, None, self.artifacts_root)
            world_actor = WorldActor(
                seed=self.world_seed,
                graph_data=self.graph_data,
                artifacts_root=self.artifacts_root,
                progress_callback=progress_callback,
                verbose=True,
            )

            world_actor.prepare_starting_area(region_manager)

            if self.is_running:
                self.finished.emit("Генерация мира успешно завершена!")

        except InterruptedError:
            self.error.emit("Генерация отменена пользователем.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(f"Критическая ошибка: {e}")

    def stop(self):
        self.is_running = False