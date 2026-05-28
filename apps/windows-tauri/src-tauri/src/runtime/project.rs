use super::models::{AssetKind, AssetMetadata, ProjectKind, ProjectMetadata};
use std::{fs, io, path::Path, time::UNIX_EPOCH};

const MAX_SCANNED_FILES: usize = 10_000;
const MAX_RETURNED_ASSETS: usize = 80;

pub fn metadata_for_path(path: Option<&str>) -> io::Result<ProjectMetadata> {
    let Some(path) = path else {
        return Ok(ProjectMetadata {
            selected_path: None,
            exists: false,
            kind: ProjectKind::Missing,
            name: None,
            extension: None,
            size_bytes: None,
            modified_unix_ms: None,
            supported_input: false,
            file_count: 0,
            supported_file_count: 0,
            total_bytes: 0,
            assets: Vec::new(),
            notes: vec!["No path supplied.".to_string()],
        });
    };

    let path_ref = Path::new(path);
    if !path_ref.exists() {
        return Ok(ProjectMetadata {
            selected_path: Some(path.to_string()),
            exists: false,
            kind: ProjectKind::Missing,
            name: path_ref.file_name().map(|value| value.to_string_lossy().into_owned()),
            extension: path_ref.extension().map(|value| value.to_string_lossy().into_owned()),
            size_bytes: None,
            modified_unix_ms: None,
            supported_input: false,
            file_count: 0,
            supported_file_count: 0,
            total_bytes: 0,
            assets: Vec::new(),
            notes: vec!["Path does not exist.".to_string()],
        });
    }

    let metadata = fs::metadata(path_ref)?;
    let extension = path_ref
        .extension()
        .map(|value| value.to_string_lossy().to_ascii_lowercase());
    let supported_input = is_supported_extension(extension.as_deref());
    let kind = if metadata.is_dir() {
        ProjectKind::Directory
    } else if metadata.is_file() {
        ProjectKind::File
    } else {
        ProjectKind::Unknown
    };
    let mut notes = Vec::new();
    let (file_count, supported_file_count, total_bytes, assets) = if metadata.is_dir() {
        let summary = scan_directory(path_ref)?;
        if summary.truncated {
            notes.push(format!(
                "Directory scan stopped after {MAX_SCANNED_FILES} files. TODO: add paged project indexing before huge workspace support."
            ));
        }
        (
            summary.file_count,
            summary.supported_file_count,
            summary.total_bytes,
            summary.assets,
        )
    } else if metadata.is_file() {
        let asset = asset_metadata(path_ref, &metadata)?;
        (
            1,
            usize::from(asset.supported_input),
            metadata.len(),
            vec![asset],
        )
    } else {
        (0, 0, 0, Vec::new())
    };
    if supported_input {
        notes.push("Supported FullSpectrum input extension detected.".to_string());
    } else if metadata.is_dir() {
        notes.push("Directory support is prepared for future project/workspace loading.".to_string());
    } else {
        notes.push("File type is not currently a supported FullSpectrum input.".to_string());
    }
    if matches!(extension.as_deref(), Some("3mf")) {
        notes.push("TODO: parse Metadata/project_settings.config through the shared project loader.".to_string());
    }

    Ok(ProjectMetadata {
        selected_path: Some(path.to_string()),
        exists: true,
        kind,
        name: path_ref.file_name().map(|value| value.to_string_lossy().into_owned()),
        extension,
        size_bytes: metadata.is_file().then_some(metadata.len()),
        modified_unix_ms: metadata
            .modified()
            .ok()
            .and_then(|time| time.duration_since(UNIX_EPOCH).ok())
            .map(|duration| duration.as_millis()),
        supported_input,
        file_count,
        supported_file_count,
        total_bytes,
        assets,
        notes,
    })
}

struct DirectoryScan {
    file_count: usize,
    supported_file_count: usize,
    total_bytes: u64,
    assets: Vec<AssetMetadata>,
    truncated: bool,
}

fn scan_directory(root: &Path) -> io::Result<DirectoryScan> {
    let mut stack = vec![root.to_path_buf()];
    let mut file_count = 0;
    let mut supported_file_count = 0;
    let mut total_bytes = 0;
    let mut assets = Vec::new();
    let mut truncated = false;

    while let Some(directory) = stack.pop() {
        for entry in fs::read_dir(directory)? {
            let entry = entry?;
            let path = entry.path();
            let metadata = entry.metadata()?;
            if metadata.is_dir() {
                stack.push(path);
                continue;
            }
            if !metadata.is_file() {
                continue;
            }

            file_count += 1;
            total_bytes = total_bytes.saturating_add(metadata.len());
            let asset = asset_metadata(&path, &metadata)?;
            if asset.supported_input {
                supported_file_count += 1;
            }
            if assets.len() < MAX_RETURNED_ASSETS {
                assets.push(asset);
            }
            if file_count >= MAX_SCANNED_FILES {
                truncated = true;
                break;
            }
        }
        if truncated {
            break;
        }
    }

    assets.sort_by(|left, right| {
        left.kind
            .to_string_rank()
            .cmp(&right.kind.to_string_rank())
            .then_with(|| left.name.cmp(&right.name))
    });

    Ok(DirectoryScan {
        file_count,
        supported_file_count,
        total_bytes,
        assets,
        truncated,
    })
}

fn asset_metadata(path: &Path, metadata: &fs::Metadata) -> io::Result<AssetMetadata> {
    let extension = path
        .extension()
        .map(|value| value.to_string_lossy().to_ascii_lowercase());
    let kind = asset_kind(extension.as_deref(), metadata.is_dir());
    let supported_input = is_supported_extension(extension.as_deref());
    Ok(AssetMetadata {
        path: path.to_string_lossy().into_owned(),
        name: path
            .file_name()
            .map(|value| value.to_string_lossy().into_owned())
            .unwrap_or_else(|| path.to_string_lossy().into_owned()),
        extension,
        kind,
        size_bytes: metadata.is_file().then_some(metadata.len()),
        modified_unix_ms: metadata
            .modified()
            .ok()
            .and_then(|time| time.duration_since(UNIX_EPOCH).ok())
            .map(|duration| duration.as_millis()),
        supported_input,
    })
}

fn is_supported_extension(extension: Option<&str>) -> bool {
    matches!(
        extension,
        Some("3mf" | "obj" | "glb" | "png" | "jpg" | "jpeg" | "bmp" | "tif" | "tiff" | "json")
    )
}

fn asset_kind(extension: Option<&str>, is_dir: bool) -> AssetKind {
    if is_dir {
        return AssetKind::Directory;
    }
    match extension {
        Some("3mf") => AssetKind::Project3mf,
        Some("obj") => AssetKind::Obj,
        Some("glb") => AssetKind::Glb,
        Some("png" | "jpg" | "jpeg" | "bmp" | "tif" | "tiff") => AssetKind::Texture,
        Some("json") => AssetKind::CustomPalette,
        _ => AssetKind::Other,
    }
}

trait AssetKindRank {
    fn to_string_rank(&self) -> u8;
}

impl AssetKindRank for AssetKind {
    fn to_string_rank(&self) -> u8 {
        match self {
            AssetKind::Project3mf => 0,
            AssetKind::Obj => 1,
            AssetKind::Glb => 2,
            AssetKind::Texture => 3,
            AssetKind::CustomPalette => 4,
            AssetKind::Directory => 5,
            AssetKind::Other => 6,
        }
    }
}
