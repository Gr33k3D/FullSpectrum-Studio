mod commands;
mod runtime;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            commands::get_app_version,
            commands::get_runtime_paths,
            commands::select_project_directory,
            commands::load_project_metadata,
            commands::inspect_project,
            commands::convert_project,
            commands::reveal_path,
            commands::write_log,
            commands::read_recent_logs,
            commands::get_gpu_info_placeholder
        ])
        .run(tauri::generate_context!())
        .expect("failed to run FullSpectrum Studio Tauri app");
}
