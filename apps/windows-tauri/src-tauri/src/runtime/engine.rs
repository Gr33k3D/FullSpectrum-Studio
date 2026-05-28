use super::{
    logging::append_log,
    models::ProjectInspection,
};
use serde::Deserialize;
use std::{
    ffi::OsStr,
    io,
    path::{Path, PathBuf},
    process::Command,
};
use tauri::{path::BaseDirectory, AppHandle, Manager};

#[derive(Debug, thiserror::Error)]
pub enum EngineError {
    #[error("FullSpectrum engine resource could not be found.")]
    MissingEngine,
    #[error("Python runtime was not found. Install Python or bundle the engine as a native runtime before release.")]
    MissingPython,
    #[error("FullSpectrum engine failed: {0}")]
    ProcessFailure(String),
    #[error("Could not parse FullSpectrum engine JSON output: {0}")]
    Json(String),
    #[error("I/O error: {0}")]
    Io(#[from] io::Error),
}

#[derive(Debug, Deserialize)]
struct ProgressEvent {
    progress: Option<f64>,
    message: Option<String>,
}

pub fn inspect_project(
    app: &AppHandle,
    source_path: &str,
    metadata_only: Option<bool>,
) -> Result<ProjectInspection, EngineError> {
    let source = Path::new(source_path);
    let engine = locate_engine(app)?;
    let python = python_executable();
    let use_metadata_only = metadata_only.unwrap_or_else(|| is_extension(source, "3mf"));

    let mut args = vec![
        engine.to_string_lossy().into_owned(),
        "--inspect".to_string(),
        "--json".to_string(),
        "--mix-model".to_string(),
        "bambu".to_string(),
    ];
    if use_metadata_only && is_extension(source, "3mf") {
        args.push("--metadata-only".to_string());
    }
    args.push(source_path.to_string());

    let mut command = Command::new(&python);
    command.args(args);
    if let Some(parent) = engine.parent() {
        command.current_dir(parent);
    }

    let output = command.output().map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            EngineError::MissingPython
        } else {
            EngineError::Io(error)
        }
    })?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    log_progress_events(&stderr);

    if !output.status.success() {
        let message = stderr
            .lines()
            .rev()
            .find_map(|line| line.strip_prefix("ERROR:").map(str::trim))
            .filter(|line| !line.is_empty())
            .unwrap_or_else(|| stderr.trim())
            .to_string();
        return Err(EngineError::ProcessFailure(if message.is_empty() {
            "Engine exited without an error message.".to_string()
        } else {
            message
        }));
    }

    let json_line = stdout
        .lines()
        .rev()
        .find(|line| line.trim_start().starts_with('{'))
        .ok_or_else(|| EngineError::Json("engine did not write JSON".to_string()))?;
    serde_json::from_str::<ProjectInspection>(json_line)
        .map_err(|error| EngineError::Json(error.to_string()))
}

fn locate_engine(app: &AppHandle) -> Result<PathBuf, EngineError> {
    if let Ok(path) = std::env::var("FULLSPECTRUM_ENGINE_PATH") {
        let candidate = PathBuf::from(path);
        if candidate.exists() {
            return Ok(candidate);
        }
    }

    if let Ok(resource) = app
        .path()
        .resolve("fullspectrum_engine.py", BaseDirectory::Resource)
    {
        if resource.exists() {
            return Ok(resource);
        }
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for candidate in [
        manifest_dir.join("resources").join("fullspectrum_engine.py"),
        manifest_dir.join("../../../fullspectrum_engine.py"),
    ] {
        if candidate.exists() {
            return Ok(candidate);
        }
    }

    Err(EngineError::MissingEngine)
}

fn python_executable() -> String {
    std::env::var("FULLSPECTRUM_PYTHON").unwrap_or_else(|_| {
        if cfg!(windows) {
            "python".to_string()
        } else {
            "python3".to_string()
        }
    })
}

fn is_extension(path: &Path, extension: &str) -> bool {
    path.extension()
        .and_then(OsStr::to_str)
        .map(|value| value.eq_ignore_ascii_case(extension))
        .unwrap_or(false)
}

fn log_progress_events(stderr: &str) {
    for line in stderr.lines() {
        if !line.trim_start().starts_with('{') {
            continue;
        }
        if let Ok(event) = serde_json::from_str::<ProgressEvent>(line) {
            if let Some(message) = event.message {
                let prefix = event
                    .progress
                    .map(|progress| format!("{:.0}% ", (progress * 100.0).clamp(0.0, 100.0)))
                    .unwrap_or_default();
                let _ = append_log("debug", &format!("engine: {prefix}{message}"));
            }
        }
    }
}
