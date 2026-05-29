use crate::runtime::{
    engine::convert_project as convert_with_engine,
    engine::inspect_project as inspect_with_engine,
    gpu::{placeholder_gpu_info, GpuInfo},
    logging::{append_log, recent_logs, LogEntry, LogWriteResult},
    models::{ConversionRequest, ProjectInspection, ProjectMetadata},
    paths::{prepare_runtime_paths, RuntimePathsResponse},
    project::metadata_for_path,
};
use serde::Serialize;
use serde_json::Value;
use std::{
    path::{Path, PathBuf},
    process::Command,
};

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DirectorySelection {
    selected_path: Option<String>,
    projects_dir: String,
    metadata: ProjectMetadata,
    note: String,
}

#[tauri::command]
pub fn get_app_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[tauri::command]
pub fn get_runtime_paths() -> Result<RuntimePathsResponse, String> {
    prepare_runtime_paths().map_err(|error| error.to_string())
}

#[tauri::command(rename_all = "camelCase")]
pub fn select_project_directory(
    selected_path: Option<String>,
) -> Result<DirectorySelection, String> {
    let paths = prepare_runtime_paths().map_err(|error| error.to_string())?;
    let selected = selected_path.unwrap_or_else(|| paths.paths.projects_dir.clone());
    let metadata = metadata_for_path(Some(&selected)).map_err(|error| error.to_string())?;
    Ok(DirectorySelection {
        selected_path: Some(selected),
        projects_dir: paths.paths.projects_dir.clone(),
        metadata,
        note: "Project directory selected and scanned by the Rust runtime bridge.".to_string(),
    })
}

#[tauri::command]
pub fn load_project_metadata(path: Option<String>) -> Result<ProjectMetadata, String> {
    metadata_for_path(path.as_deref()).map_err(|error| error.to_string())
}

#[tauri::command(rename_all = "camelCase")]
pub fn inspect_project(
    app: tauri::AppHandle,
    path: String,
    metadata_only: Option<bool>,
) -> Result<ProjectInspection, String> {
    let inspection =
        inspect_with_engine(&app, &path, metadata_only).map_err(|error| error.to_string())?;
    let _ = append_log(
        "info",
        &format!(
            "Inspected source {} with {} source slots.",
            inspection.filename, inspection.source_slots
        ),
    );
    Ok(inspection)
}

#[tauri::command(rename_all = "camelCase")]
pub fn convert_project(app: tauri::AppHandle, request: ConversionRequest) -> Result<Value, String> {
    convert_with_engine(&app, request).map_err(|error| error.to_string())
}

#[tauri::command(rename_all = "camelCase")]
pub fn reveal_path(path: String) -> Result<(), String> {
    reveal_in_file_manager(Path::new(&path)).map_err(|error| error.to_string())
}

#[tauri::command]
pub fn write_log(level: Option<String>, message: String) -> Result<LogWriteResult, String> {
    append_log(level.as_deref().unwrap_or("info"), &message).map_err(|error| error.to_string())
}

#[tauri::command]
pub fn read_recent_logs(limit: Option<usize>) -> Result<Vec<LogEntry>, String> {
    recent_logs(limit.unwrap_or(80)).map_err(|error| error.to_string())
}

#[tauri::command]
pub fn get_gpu_info_placeholder() -> GpuInfo {
    placeholder_gpu_info()
}

fn reveal_in_file_manager(path: &Path) -> std::io::Result<()> {
    let target = if path.exists() {
        path.to_path_buf()
    } else if let Some(parent) = path.parent() {
        parent.to_path_buf()
    } else {
        PathBuf::from(".")
    };

    #[cfg(target_os = "windows")]
    {
        if target.is_file() {
            Command::new("explorer")
                .arg(format!("/select,{}", target.display()))
                .spawn()?;
        } else {
            Command::new("explorer").arg(target).spawn()?;
        }
    }

    #[cfg(target_os = "macos")]
    {
        if target.is_file() {
            Command::new("open").arg("-R").arg(target).spawn()?;
        } else {
            Command::new("open").arg(target).spawn()?;
        }
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let directory = if target.is_file() {
            target
                .parent()
                .unwrap_or_else(|| Path::new("."))
                .to_path_buf()
        } else {
            target
        };
        Command::new("xdg-open").arg(directory).spawn()?;
    }

    Ok(())
}
