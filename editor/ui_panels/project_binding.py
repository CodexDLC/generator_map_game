# editor/ui_panels/project_binding.py
def apply_project_to_ui(mw, data: dict) -> None:
    mw.seed_input.setValue(int(data.get("seed", 1)))
    mw.chunk_size_input.setValue(int(data.get("chunk_size", 128)))
    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    mw.region_size_in_chunks_input.setValue(int(data.get("region_size_in_chunks", 4)))
    mw.cell_size_input.setValue(float(data.get("cell_size", 1.0)))
    mw.global_x_offset_input.setValue(int(data.get("global_x_offset", 0)))
    mw.global_z_offset_input.setValue(int(data.get("global_z_offset", 0)))

    noise_data = data.get("global_noise", {})
    mw.gn_scale_input.setValue(float(noise_data.get("scale_tiles", 6000.0)))
    mw.gn_octaves_input.setValue(int(noise_data.get("octaves", 3)))
    mw.gn_amp_input.setValue(float(noise_data.get("amp_m", 400.0)))
    mw.gn_ridge_checkbox.setChecked(bool(noise_data.get("ridge", False)))

    project_name = data.get("project_name", "Безымянный проект")
    mw.setWindowTitle(f"Редактор Миров — [{project_name}]")

def collect_context_from_ui(mw) -> dict:
    global_noise_params = {
        "scale_tiles": mw.gn_scale_input.value(),
        "octaves": mw.gn_octaves_input.value(),
        "amp_m": mw.gn_amp_input.value(),
        "ridge": mw.gn_ridge_checkbox.isChecked(),
    }
    cs = int(mw.chunk_size_input.value())
    # --- И ИЗМЕНЕНИЕ ЗДЕСЬ ---
    rs = int(mw.region_size_in_chunks_input.value())
    return {
        "cell_size": mw.cell_size_input.value(),
        "seed": mw.seed_input.value(),
        "global_x_offset": mw.global_x_offset_input.value(),
        "global_z_offset": mw.global_z_offset_input.value(),
        "chunk_size": cs,
        "region_size_in_chunks": rs,
        "global_noise": global_noise_params,
    }
