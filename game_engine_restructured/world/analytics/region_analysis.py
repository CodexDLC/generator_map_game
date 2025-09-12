# Файл: game_engine_restructured/world/analytics/region_analysis.py
from __future__ import annotations
import textwrap
from typing import Dict, Tuple, Any
import numpy as np

# --- НАЧАЛО ИЗМЕНЕНИЙ ---


def _extract_core(
    stitched_layers: Dict[str, np.ndarray], chunk_size: int
) -> Dict[str, np.ndarray]:
    """Извлекает 'ядро' региона (без 'фартука' в 1 чанк)."""
    border_px = chunk_size
    core_layers = {}
    for name, grid in stitched_layers.items():
        if grid is not None and grid.ndim == 2 and grid.shape[0] > 2 * border_px:
            core_layers[name] = grid[border_px:-border_px, border_px:-border_px]
    return core_layers


def _seam_rmse(A_core: np.ndarray, B_core: np.ndarray, side: str) -> float | str:
    """Вычисляет RMSE на шве между двумя 'ядрами' регионов."""
    if A_core is None or B_core is None:
        return "N/A"
    try:
        if side == "north":  # Текущий регион A, северный сосед B
            a, b = A_core[0, :], B_core[-1, :]
        elif side == "west":  # Текущий регион A, западный сосед B
            a, b = A_core[:, 0], B_core[:, -1]
        else:
            return "N/A"  # E/S проверяются соседями

        diff = a.astype(np.float32) - b.astype(np.float32)
        return float(np.sqrt(np.mean(diff * diff)))
    except (IndexError, ValueError):
        return "ERROR"


# --- КОНЕЦ ИЗМЕНЕНИЙ ---


class RegionAnalysis:
    """Собирает и форматирует отчёт по сгенерированному региону."""

    # --- НАЧАЛО ИЗМЕНЕНИЙ: Конструктор теперь принимает chunk_size ---
    def __init__(
        self,
        scx: int,
        scz: int,
        stitched_layers_ext: Dict[str, np.ndarray],
        chunk_size: int,
    ):
        self.scx = scx
        self.scz = scz
        self.layers_ext = stitched_layers_ext
        self.layers_core = _extract_core(stitched_layers_ext, chunk_size)
        self.report: Dict[str, Any] = {}

    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    def run(self, neighbor_data: Dict[str, Dict[str, np.ndarray] | None]):
        """Выполняет все расчёты для отчёта."""
        self._calculate_stats()  # Объединяем расчеты
        self._check_seams(neighbor_data)
        self._calculate_gradients(neighbor_data)

    # --- НАЧАЛО ИЗМЕНЕНИЙ: Переработано для 'ядра' и добавления стандартного отклонения ---
    def _calculate_stats(self):
        stats: Dict[str, Dict[str, float]] = {"mean": {}, "std_dev": {}}
        stat_layers = [
            "height",
            "temperature",
            "humidity",
            "shadow",
            "coast",
            "river",
            "temp_dry",
        ]

        for name in stat_layers:
            layer = self.layers_core.get(name)
            if layer is not None:
                stats["mean"][name] = float(layer.mean())
                stats["std_dev"][name] = float(layer.std())

        self.report["stats"] = stats

        if "temp_dry" in self.layers_core:
            td_layer = self.layers_core["temp_dry"]
            active_pixels = np.sum(
                td_layer > 0.5
            )  # Считаем активными только те, что прошли smoothstep
            total_pixels = td_layer.size
            self.report["temp_dry_active"] = active_pixels > 0
            self.report["temp_dry_pct"] = (
                (active_pixels / total_pixels) * 100 if total_pixels > 0 else 0.0
            )
        else:
            self.report["temp_dry_active"] = "N/A"
            self.report["temp_dry_pct"] = 0.0

    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    def _check_seams(self, neighbor_data: Dict[str, Dict[str, np.ndarray] | None]):
        seams = {}
        for layer_name in ["height", "temperature", "humidity"]:
            if layer_name not in self.layers_core:
                continue
            current_layer_core = self.layers_core[layer_name]

            # Сравнение с северным соседом
            north_neighbor_core = neighbor_data.get("north")
            if north_neighbor_core and layer_name in north_neighbor_core:
                seams[f"{layer_name}_N"] = _seam_rmse(
                    current_layer_core, north_neighbor_core[layer_name], "north"
                )

            # Сравнение с западным соседом
            west_neighbor_core = neighbor_data.get("west")
            if west_neighbor_core and layer_name in west_neighbor_core:
                seams[f"{layer_name}_W"] = _seam_rmse(
                    current_layer_core, west_neighbor_core[layer_name], "west"
                )

        self.report["seams"] = seams if seams else "No neighbors processed yet"

    # --- НАЧАЛО НОВОГО КОДА ---
    def _calculate_gradients(
        self, neighbor_data: Dict[str, Dict[str, np.ndarray] | None]
    ):
        grads = {}
        for layer_name in ["temperature", "humidity"]:
            current_mean = self.report.get("stats", {}).get("mean", {}).get(layer_name)
            if current_mean is None:
                continue

            # Градиент по X (Запад -> Центр)
            west_neighbor_core = neighbor_data.get("west")
            if west_neighbor_core and layer_name in west_neighbor_core:
                west_mean = west_neighbor_core[layer_name].mean()
                grads[f"d(μ_{layer_name})/dx"] = current_mean - west_mean

            # Градиент по Z (Север -> Центр)
            north_neighbor_core = neighbor_data.get("north")
            if north_neighbor_core and layer_name in north_neighbor_core:
                north_mean = north_neighbor_core[layer_name].mean()
                grads[f"d(μ_{layer_name})/dz"] = current_mean - north_mean

        self.report["gradients"] = grads if grads else "N/A"

    # --- КОНЕЦ НОВОГО КОДА ---

    def print_report(self):
        """Выводит отформатированный отчёт в консоль."""
        seam_report = self.report.get("seams", {})
        if isinstance(seam_report, dict):
            seam_str = (
                " | ".join(
                    [
                        f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}"
                        for k, v in seam_report.items()
                    ]
                )
                if seam_report
                else "No neighbors processed yet"
            )
        else:
            seam_str = str(seam_report)

        grad_report = self.report.get("gradients", {})
        if isinstance(grad_report, dict):
            grad_str = " | ".join([f"{k}: {v:+.3f}" for k, v in grad_report.items()])
        else:
            grad_str = str(grad_report)

        s = self.report.get("stats", {"mean": {}, "std_dev": {}})

        report_str = f"""
        ============================================================
        ANALYTICS REPORT for REGION ({self.scx}, {self.scz})
        ============================================================
        1. Core Statistics (Mean | Std Dev):
           - Height:      {s["mean"].get("height", 0):>7.2f} m | {s["std_dev"].get("height", 0):.2f}
           - Temperature: {s["mean"].get("temperature", 0):>7.2f} C | {s["std_dev"].get("temperature", 0):.2f}
           - Humidity:    {s["mean"].get("humidity", 0):>7.3f}   | {s["std_dev"].get("humidity", 0):.3f}
           - Shadow:      {s["mean"].get("shadow", 0):>7.3f}   | {s["std_dev"].get("shadow", 0):.3f}
           - River Effect:{s["mean"].get("river", 0):>7.3f}   | {s["std_dev"].get("river", 0):.3f}

        2. Feature Flags:
           - temp_dry_active: {self.report["temp_dry_active"]} ({self.report["temp_dry_pct"]:.1f}% area > 0.5)

        3. Inter-Region Analysis:
           - Gradients: {grad_str}
           - Seam RMSE: {seam_str}
        ============================================================
        """
        print(textwrap.dedent(report_str))
