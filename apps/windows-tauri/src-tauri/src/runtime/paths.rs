use serde::Serialize;
use std::{fs, io, path::PathBuf};

const APP_DIR_NAME: &str = "FullSpectrum Studio";

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimePaths {
    pub app_data_dir: String,
    pub cache_dir: String,
    pub logs_dir: String,
    pub projects_dir: String,
    pub shaders_dir: String,
    pub temp_dir: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimePathsResponse {
    pub paths: RuntimePaths,
    pub created: Vec<String>,
}

pub fn prepare_runtime_paths() -> io::Result<RuntimePathsResponse> {
    let data_base = dirs::data_dir()
        .unwrap_or_else(|| std::env::temp_dir())
        .join(APP_DIR_NAME);
    let cache_base = dirs::cache_dir()
        .unwrap_or_else(|| std::env::temp_dir())
        .join(APP_DIR_NAME);
    let documents_base = dirs::document_dir()
        .unwrap_or_else(|| data_base.clone())
        .join(APP_DIR_NAME);
    let temp_base = std::env::temp_dir().join("FullSpectrumStudio");

    let logs_dir = data_base.join("logs");
    let projects_dir = documents_base.join("projects");
    let shaders_dir = data_base.join("shaders");

    let directories = [
        data_base.clone(),
        cache_base.clone(),
        logs_dir.clone(),
        projects_dir.clone(),
        shaders_dir.clone(),
        temp_base.clone(),
    ];

    let mut created = Vec::new();
    for directory in directories {
        fs::create_dir_all(&directory)?;
        created.push(display_path(directory));
    }

    Ok(RuntimePathsResponse {
        paths: RuntimePaths {
            app_data_dir: display_path(data_base),
            cache_dir: display_path(cache_base),
            logs_dir: display_path(logs_dir),
            projects_dir: display_path(projects_dir),
            shaders_dir: display_path(shaders_dir),
            temp_dir: display_path(temp_base),
        },
        created,
    })
}

pub fn display_path(path: PathBuf) -> String {
    path.to_string_lossy().into_owned()
}
