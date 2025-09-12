# Файл: game_engine_restructured/world/analytics/region_analysis.py
from __future__ import annotations
import textwrap
from typing import Dict, Tuple
import numpy as np


# =======================================================================
# АНАЛИТИЧЕСКИЕ ИНСТРУМЕНТЫ
# =======================================================================

def seam_rmse(A: np.ndarray, B: np.ndarray, side: str) -> float:
    """Вычисляет ошибку на шве (RMSE) между двумя массивами."""
    try:
        if side == "east":
            a, b = A[:, -1], B[:, 0]
        elif side == "west":
            a, b = A[:, 0], B[:, -1]
        elif side == "north":
            a, b = A[0, :], B[-1, :]
        elif side == "south":
            a, b = A[-1, :], B[0, :]
        else:
            return -1.0

        diff = a.astype(np.float32) - b.astype(np.float32)
        return float(np.sqrt(np.mean(diff * diff)))
    except (IndexError, ValueError):
        return -1.0


class RegionAnalysis:
    """Собирает и форматирует отчёт по сгенерированному региону."""

    def __init__(self, scx: int, scz: int, stitched_layers: Dict[str, np.ndarray]):
        self.scx = scx
        self.scz = scz
        self.layers = stitched_layers
        self.report = {}

    def run(self, neighbor_data: Dict[str, Dict[str, np.ndarray] | None]):
        """Выполняет все расчёты для отчёта."""
        self._calculate_means()
        self._calculate_correlations()
        self._check_temp_dry()
        self._check_seams(neighbor_data)
        # TODO: Реализовать расчет градиентов, когда будет стабильная база
        self.report['gradients'] = "N/A (требуется доработка)"

    def _calculate_means(self):
        means = {}
        mean_layers = ['height', 'temperature', 'humidity', 'shadow', 'coast', 'river', 'temp_dry']
        for name in mean_layers:
            if name in self.layers and self.layers[name] is not None:
                means[name] = self.layers[name].mean()
        self.report['means'] = means

    def _calculate_correlations(self):
        corrs = {}
        if 'height' in self.layers and 'temperature' in self.layers:
            h = self.layers['height'].flatten()
            t = self.layers['temperature'].flatten()
            if np.std(h) > 0 and np.std(t) > 0:
                corrs['height_temp'] = np.corrcoef(h, t)[0, 1]
        if 'height' in self.layers and 'humidity' in self.layers:
            h = self.layers['height'].flatten()
            hu = self.layers['humidity'].flatten()
            if np.std(h) > 0 and np.std(hu) > 0:
                corrs['height_humid'] = np.corrcoef(h, hu)[0, 1]
        self.report['correlations'] = corrs

    def _check_temp_dry(self):
        if 'temp_dry' in self.layers:
            td_layer = self.layers['temp_dry']
            active_pixels = np.sum(td_layer > 0)
            total_pixels = td_layer.size
            self.report['temp_dry_active'] = active_pixels > 0
            self.report['temp_dry_pct'] = (active_pixels / total_pixels) * 100 if total_pixels > 0 else 0.0
        else:
            self.report['temp_dry_active'] = "N/A"
            self.report['temp_dry_pct'] = 0.0

    def _check_seams(self, neighbor_data: Dict[str, Dict[str, np.ndarray] | None]):
        seams = {}
        for layer_name in ['height', 'temperature', 'humidity']:
            if layer_name not in self.layers: continue
            current_layer = self.layers[layer_name]

            north_neighbor = neighbor_data.get("north")
            if north_neighbor and layer_name in north_neighbor:
                seams[f'{layer_name}_N'] = seam_rmse(north_neighbor[layer_name], current_layer, "south")

            west_neighbor = neighbor_data.get("west")
            if west_neighbor and layer_name in west_neighbor:
                seams[f'{layer_name}_W'] = seam_rmse(west_neighbor[layer_name], current_layer, "east")

        self.report['seams'] = seams if seams else "No neighbors processed yet"

    def print_report(self):
        """Выводит отформатированный отчёт в консоль."""
        seam_report = self.report.get('seams', {})
        if isinstance(seam_report, dict):
            seam_str = " | ".join(
                [f"{k}: {v:.4f}" for k, v in seam_report.items()]) if seam_report else "No neighbors processed yet"
        else:
            seam_str = seam_report

        report_str = f"""
        ============================================================
        ANALYTICS REPORT for REGION ({self.scx}, {self.scz})
        ============================================================
        1. Mean Values:
           - Height:     {self.report['means'].get('height', 0):.2f} m
           - Temperature:{self.report['means'].get('temperature', 0):.2f} C
           - Humidity:   {self.report['means'].get('humidity', 0):.3f}
           - Shadow:     {self.report['means'].get('shadow', 0):.3f}
           - Coast Effect:{self.report['means'].get('coast', 0):.3f}
           - River Effect:{self.report['means'].get('river', 0):.3f}

        2. Intra-Region Correlations:
           - corr(height, temp):  {self.report['correlations'].get('height_temp', 0):.3f}
           - corr(height, humid): {self.report['correlations'].get('height_humid', 0):.3f}

        3. Feature Flags:
           - temp_dry_active: {self.report['temp_dry_active']} ({self.report['temp_dry_pct']:.1f}% area)

        4. Inter-Region Analysis:
           - Gradients: {self.report['gradients']}
           - Seam RMSE: {seam_str}
        ============================================================
        """
        print(textwrap.dedent(report_str))