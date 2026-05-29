use super::{
    logging::append_log,
    models::{ConversionRequest, PaletteMode, PaletteSource, ProjectInspection, RealSlotSelection},
};
use serde::Deserialize;
use serde_json::Value;
use std::{
    ffi::OsStr,
    fs, io,
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
    let thumbnail_dest = preview_thumbnail_path(source)?;

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
    if let Some(thumbnail_dest) = thumbnail_dest.as_ref() {
        args.push("--thumbnail-out".to_string());
        args.push(thumbnail_dest.to_string_lossy().into_owned());
    }
    args.push(source_path.to_string());

    let value = run_engine_json(&engine, &python, args)?;
    serde_json::from_value::<ProjectInspection>(value)
        .map_err(|error| EngineError::Json(error.to_string()))
}

pub fn convert_project(app: &AppHandle, request: ConversionRequest) -> Result<Value, EngineError> {
    let engine = locate_engine(app)?;
    let python = python_executable();
    let mut args = vec![
        engine.to_string_lossy().into_owned(),
        "--json".to_string(),
        "--mix-model".to_string(),
        "bambu".to_string(),
        "--mode".to_string(),
        palette_mode_cli(&request.palette_mode).to_string(),
        "--palette-source".to_string(),
        palette_source_cli(&request.palette_source).to_string(),
        "--real-slots".to_string(),
        real_slots_cli(&request.real_slots).to_string(),
        "--quality-bias".to_string(),
        request.quality_bias.clamp(0, 100).to_string(),
    ];

    if let Some(output_dir) = request
        .output_dir
        .as_deref()
        .filter(|value| !value.is_empty())
    {
        args.push("--output-dir".to_string());
        args.push(output_dir.to_string());
    }
    if let Some(reference_path) = request
        .reference_path
        .as_deref()
        .filter(|value| !value.is_empty())
    {
        args.push("--reference".to_string());
        args.push(reference_path.to_string());
    }
    if !request.auto_open_validated_output {
        args.push("--no-reveal".to_string());
    }
    args.push(request.input_path.clone());

    let value = run_engine_json(&engine, &python, args)?;
    let output_path = value
        .get("output")
        .and_then(Value::as_str)
        .unwrap_or("unknown output");
    let _ = append_log(
        "info",
        &format!(
            "Converted {} into {}.",
            Path::new(&request.input_path)
                .file_name()
                .and_then(OsStr::to_str)
                .unwrap_or(request.input_path.as_str()),
            output_path
        ),
    );
    Ok(value)
}

fn run_engine_json(engine: &Path, python: &str, args: Vec<String>) -> Result<Value, EngineError> {
    let mut command = Command::new(python);
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
    serde_json::from_str::<Value>(json_line).map_err(|error| EngineError::Json(error.to_string()))
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
        manifest_dir
            .join("resources")
            .join("fullspectrum_engine.py"),
        manifest_dir.join("../../../fullspectrum_engine.py"),
    ] {
        if candidate.exists() {
            return Ok(candidate);
        }
    }

    Err(EngineError::MissingEngine)
}

fn preview_thumbnail_path(source: &Path) -> Result<Option<PathBuf>, EngineError> {
    let paths = super::paths::prepare_runtime_paths()?;
    let previews = PathBuf::from(paths.paths.cache_dir).join("previews");
    fs::create_dir_all(&previews)?;
    let stem = source
        .file_stem()
        .and_then(OsStr::to_str)
        .unwrap_or("source")
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() || matches!(character, '-' | '_') {
                character
            } else {
                '_'
            }
        })
        .collect::<String>();
    Ok(Some(previews.join(format!("{stem}-plate.png"))))
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

fn palette_mode_cli(value: &PaletteMode) -> &'static str {
    match value {
        PaletteMode::Official => "official",
        PaletteMode::Cmykw => "cmykw",
    }
}

fn palette_source_cli(value: &PaletteSource) -> &'static str {
    match value {
        PaletteSource::Inventory => "inventory",
        PaletteSource::Catalog => "catalog",
        PaletteSource::AllBambu => "all-bambu",
        PaletteSource::Custom => "custom",
        PaletteSource::ExactCmykw => "exact-cmykw",
    }
}

fn real_slots_cli(value: &RealSlotSelection) -> &'static str {
    match value {
        RealSlotSelection::Auto => "auto",
        RealSlotSelection::Two => "2",
        RealSlotSelection::Three => "3",
        RealSlotSelection::Four => "4",
        RealSlotSelection::Five => "5",
        RealSlotSelection::Six => "6",
    }
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
