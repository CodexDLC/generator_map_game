# Этот файл будет выполняться в отдельном процессе

from generator_tester.world_manager import WorldManager


def worker_main(task_queue, city_seed: int):
    """
    Главная функция процесса-воркера.
    Она висит в бесконечном цикле, ждет задач из очереди и генерирует чанки.
    """
    print(f"[Worker-{city_seed}] process started.")
    # Каждый воркер имеет свой собственный WorldManager
    world_manager = WorldManager(city_seed)

    while True:
        try:
            # Блокирующая операция: ждем, пока в очереди появится задача
            task = task_queue.get()

            # "Стоп-сигнал" для завершения процесса
            if task is None:
                print(f"[Worker-{city_seed}] received stop signal. Shutting down.")
                break

            world_id, current_seed, cx, cz = task

            # Временно устанавливаем контекст для генератора
            world_manager.world_id = world_id
            world_manager.current_seed = current_seed

            # Выполняем тяжелую работу
            world_manager._load_or_generate_chunk(cx, cz)

        except Exception as e:
            print(f"[Worker-{city_seed}] CRITICAL ERROR: {e}")

    print(f"[Worker-{city_seed}] process finished.")