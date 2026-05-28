use super::paths::prepare_runtime_paths;
use chrono::Utc;
use serde::Serialize;
use std::{
    fs::{self, OpenOptions},
    io::{self, Write},
    path::PathBuf,
};

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LogWriteResult {
    pub path: String,
    pub bytes_written: usize,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LogEntry {
    pub timestamp: Option<String>,
    pub level: String,
    pub message: String,
    pub raw: String,
}

pub fn append_log(level: &str, message: &str) -> io::Result<LogWriteResult> {
    let paths = prepare_runtime_paths()?;
    let log_path = PathBuf::from(paths.paths.logs_dir).join("fullspectrum-studio.log");
    let normalized_level = match level.to_ascii_lowercase().as_str() {
        "debug" | "info" | "warn" | "error" => level.to_ascii_uppercase(),
        _ => "INFO".to_string(),
    };
    let line = format!(
        "{} [{}] {}\n",
        Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true),
        normalized_level,
        message.replace('\n', " ")
    );
    let mut file = OpenOptions::new().create(true).append(true).open(&log_path)?;
    file.write_all(line.as_bytes())?;
    Ok(LogWriteResult {
        path: log_path.to_string_lossy().into_owned(),
        bytes_written: line.len(),
    })
}

pub fn recent_logs(limit: usize) -> io::Result<Vec<LogEntry>> {
    let paths = prepare_runtime_paths()?;
    let log_path = PathBuf::from(paths.paths.logs_dir).join("fullspectrum-studio.log");
    if !log_path.exists() {
        return Ok(Vec::new());
    }

    let text = fs::read_to_string(log_path)?;
    let mut entries = Vec::new();
    for line in text.lines().rev().take(limit.max(1).min(500)) {
        entries.push(parse_log_line(line));
    }
    Ok(entries)
}

fn parse_log_line(line: &str) -> LogEntry {
    let mut timestamp = None;
    let mut level = "info".to_string();
    let mut message = line.to_string();

    if let Some((time, rest)) = line.split_once(" [") {
        if let Some((raw_level, raw_message)) = rest.split_once("] ") {
            timestamp = Some(time.to_string());
            level = raw_level.to_ascii_lowercase();
            message = raw_message.to_string();
        }
    }

    LogEntry {
        timestamp,
        level,
        message,
        raw: line.to_string(),
    }
}
