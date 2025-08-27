import tkinter as tk
from dataclasses import dataclass
from setting.config import GenConfig, BiomeConfig


@dataclass
class GenerateState:
    # базовые поля
    world_id: tk.StringVar
    seed: tk.StringVar
    chunks_w: tk.StringVar
    chunks_h: tk.StringVar
    chunk_size: tk.StringVar

    plains_scale: tk.StringVar
    plains_oct: tk.StringVar
    mount_scale: tk.StringVar
    mount_oct: tk.StringVar
    mask_scale: tk.StringVar
    mount_strength: tk.StringVar
    dist_power: tk.StringVar
    lacunarity: tk.StringVar
    gain: tk.StringVar

    ocean_m: tk.StringVar
    land_m: tk.StringVar
    beach_m: tk.StringVar
    rock_m: tk.StringVar
    snow_m: tk.StringVar
    slope_deg: tk.StringVar

    export_godot: tk.BooleanVar
    version: tk.StringVar

    # --- ВУЛКАН / ОСТРОВ ---
    volcano_enable: tk.BooleanVar
    volcano_peak_m: tk.StringVar
    volcano_radius_m: tk.StringVar
    crater_radius_m: tk.StringVar
    island_radius_m: tk.StringVar
    island_band_m: tk.StringVar
    ridge_noise_amp: tk.StringVar
    volcano_center_x: tk.StringVar   # можно оставить пустым => центр карты
    volcano_center_y: tk.StringVar

    @staticmethod
    def create_defaults():
        return GenerateState(
            world_id=tk.StringVar(value="demo"),
            seed=tk.StringVar(value="12345"),
            chunks_w=tk.StringVar(value="8"),
            chunks_h=tk.StringVar(value="8"),
            chunk_size=tk.StringVar(value="512"),

            plains_scale=tk.StringVar(value="4000"),
            plains_oct=tk.StringVar(value="4"),
            mount_scale=tk.StringVar(value="1600"),
            mount_oct=tk.StringVar(value="6"),
            mask_scale=tk.StringVar(value="8000"),
            mount_strength=tk.StringVar(value="0.45"),
            dist_power=tk.StringVar(value="1.1"),
            lacunarity=tk.StringVar(value="2.0"),
            gain=tk.StringVar(value="0.5"),

            ocean_m=tk.StringVar(value="0"),
            land_m=tk.StringVar(value="150"),
            beach_m=tk.StringVar(value="5"),
            rock_m=tk.StringVar(value="500"),
            snow_m=tk.StringVar(value="1000"),
            slope_deg=tk.StringVar(value="40"),

            export_godot=tk.BooleanVar(value=True),
            version=tk.StringVar(value="v1"),

            # вулкан
            volcano_enable=tk.BooleanVar(value=False),
            volcano_peak_m=tk.StringVar(value="120"),
            volcano_radius_m=tk.StringVar(value="2500"),
            crater_radius_m=tk.StringVar(value="300"),
            island_radius_m=tk.StringVar(value="9000"),
            island_band_m=tk.StringVar(value="2000"),
            ridge_noise_amp=tk.StringVar(value="0.10"),
            volcano_center_x=tk.StringVar(value=""),
            volcano_center_y=tk.StringVar(value=""),
        )

    def to_config(self) -> GenConfig:
        width_px = int(self.chunks_w.get()) * int(self.chunk_size.get())
        height_px = int(self.chunks_h.get()) * int(self.chunk_size.get())

        cfg = GenConfig(
            world_id=self.world_id.get(),
            version=self.version.get(),
            seed=int(self.seed.get()),
            width=width_px,
            height=height_px,
            chunk=int(self.chunk_size.get()),

            plains_scale=float(self.plains_scale.get()),
            plains_octaves=int(self.plains_oct.get()),
            mountains_scale=float(self.mount_scale.get()),
            mountains_octaves=int(self.mount_oct.get()),
            mask_scale=float(self.mask_scale.get()),
            mountain_strength=float(self.mount_strength.get()),
            height_distribution_power=float(self.dist_power.get()),
            lacunarity=float(self.lacunarity.get()),
            gain=float(self.gain.get()),

            land_height_m=float(self.land_m.get()),
            export_for_godot=bool(self.export_godot.get()),

            biome_config=BiomeConfig(
                ocean_level_m=float(self.ocean_m.get()),
                beach_height_m=float(self.beach_m.get()),
                rock_height_m=float(self.rock_m.get()),
                snow_height_m=float(self.snow_m.get()),
                max_grass_slope_deg=float(self.slope_deg.get()),
            ),
        )

        # вулкан
        cfg.volcano_enable   = bool(self.volcano_enable.get())
        cfg.peak_add_m       = float(self.volcano_peak_m.get())
        cfg.volcano_radius_m = float(self.volcano_radius_m.get())
        cfg.crater_radius_m  = float(self.crater_radius_m.get())
        cfg.island_radius_m  = float(self.island_radius_m.get())
        cfg.island_band_m    = float(self.island_band_m.get())
        cfg.ridge_noise_amp  = float(self.ridge_noise_amp.get() or 0.0)

        x_txt = (self.volcano_center_x.get() or "").strip()
        y_txt = (self.volcano_center_y.get() or "").strip()
        if x_txt != "" and y_txt != "":
            try:
                cx = int(x_txt); cy = int(y_txt)
                cfg.volcano_center_px = (cx, cy)
            except ValueError:
                cfg.volcano_center_px = (width_px // 2, height_px // 2)
        else:
            cfg.volcano_center_px = (width_px // 2, height_px // 2)

        return cfg
