# generator_logic/terrain/landlab_erosion.py
import numpy as np
try:
    from landlab import RasterModelGrid
    from landlab.components import FlowAccumulator, FastscapeEroder, LinearDiffuser
except ImportError:
    # Функция может вернуть None или входную карту, если landlab не установлен
    def landlab_erosion_wrapper(context, height_map, params):
        raise ImportError("Landlab is not installed. Please install it to use erosion.")
else:
    def landlab_erosion_wrapper(context, height_map, params):
        """
        Простая флювиальная эрозия на один временной шаг.
        context содержит WORLD_SIZE_METERS и другие настройки.
        params: dict с ключами:
            'dt' — длительность шага (лет или секунд),
            'K_sp' — коэффициент эрозии,
            'm_sp', 'n_sp' — показатели степени,
            'diffusivity' — для hillslope-диффузии,
            'num_steps' — количество шагов итерации.
        height_map: numpy.ndarray (H,W) — текущая карта высот.
        Возвращает новую карту высот (H,W).
        """
        # Высота в метрах:
        z = height_map.astype(np.float64).copy()
        nrows, ncols = z.shape

        # Размер ячейки (метры/пиксель)
        world_size = float(context.get('WORLD_SIZE_METERS', 1000.0))
        cell_size = world_size / max(nrows, ncols)

        # Создаём сетку Landlab
        grid = RasterModelGrid((nrows, ncols), xy_spacing=cell_size)
        grid.add_field('topographic__elevation', z.ravel(), at='node')

        # Компоненты Landlab
        fa = FlowAccumulator(grid, flow_director='D8')
        sp = FastscapeEroder(grid, K_sp=params.get('K_sp', 5e-6),
                             m_sp=params.get('m_sp', 0.5),
                             n_sp=params.get('n_sp', 1.0))
        lin_diff = LinearDiffuser(grid, linear_diffusivity=params.get('diffusivity', 0.01))

        dt = float(params.get('dt', 1.0))  # размер временного шага
        num_steps = int(params.get('num_steps', 1))

        for _ in range(num_steps):
            fa.run_one_step()            # накопить сток
            sp.run_one_step(dt)          # флювиальная эрозия
            lin_diff.run_one_step(dt)    # hillslope-диффузия

        new_z = grid.at_node['topographic__elevation'].reshape((nrows, ncols))
        return new_z.astype(np.float32)
