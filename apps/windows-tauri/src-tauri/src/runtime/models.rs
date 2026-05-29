#![allow(dead_code)]

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AssetMetadata {
    pub path: String,
    pub name: String,
    pub extension: Option<String>,
    pub kind: AssetKind,
    pub size_bytes: Option<u64>,
    pub modified_unix_ms: Option<u128>,
    pub supported_input: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum AssetKind {
    Project3mf,
    Obj,
    Glb,
    Texture,
    CustomPalette,
    Directory,
    Other,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectMetadata {
    pub selected_path: Option<String>,
    pub exists: bool,
    pub kind: ProjectKind,
    pub name: Option<String>,
    pub extension: Option<String>,
    pub size_bytes: Option<u64>,
    pub modified_unix_ms: Option<u128>,
    pub supported_input: bool,
    pub file_count: usize,
    pub supported_file_count: usize,
    pub total_bytes: u64,
    pub assets: Vec<AssetMetadata>,
    pub notes: Vec<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum ProjectKind {
    File,
    Directory,
    Missing,
    Unknown,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectInspection {
    pub input: String,
    pub filename: String,
    pub source_slots: usize,
    pub source_colors: Vec<String>,
    pub thumbnail: Option<String>,
    pub preview_mesh: Option<String>,
    pub preview_notice: Option<String>,
    pub metrics: Option<MeshMetrics>,
    #[serde(rename = "import")]
    pub import_summary: Option<ImportSummary>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversionRequest {
    pub input_path: String,
    pub output_dir: Option<String>,
    pub reference_path: Option<String>,
    pub palette_mode: PaletteMode,
    pub palette_source: PaletteSource,
    pub real_slots: RealSlotSelection,
    pub quality_bias: u8,
    pub auto_open_validated_output: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MeshMetrics {
    pub object_count: Option<usize>,
    pub vertex_count: Option<usize>,
    pub triangle_count: Option<usize>,
    pub polygon_count: Option<usize>,
    pub texture_bytes: Option<usize>,
    pub recommended_render_mode: Option<String>,
    pub preview_memory_estimate_bytes: Option<usize>,
    pub preview_build_estimate_seconds: Option<f64>,
    pub source_slots: Option<usize>,
    pub paint_references: Option<usize>,
    pub paint_models: Option<usize>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ImportSummary {
    pub source_type: String,
    pub texture: String,
    pub vertex_count: usize,
    pub triangle_count: usize,
    pub internal_color_count: usize,
    pub export_color_count: usize,
    pub compressed_for_bambu: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RendererState {
    pub backend: RendererBackend,
    pub status: RendererStatus,
    pub preview_mode: PreviewMode,
    pub performance: ViewerPerformance,
    pub loaded_asset_path: Option<String>,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum RendererBackend {
    WebPlaceholder,
    WebThree,
    NativeBridge,
    WgpuFuture,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum RendererStatus {
    Idle,
    Initializing,
    LoadingProject,
    RenderingPlaceholder,
    Ready,
    Error,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum PreviewMode {
    PlateImage,
    Original,
    Predicted,
    Validation,
    ColorLoss,
    AnchorInfluence,
    Wireframe,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum ViewerPerformance {
    Fast,
    Balanced,
    High,
    Maximum,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeStatus {
    pub ready: bool,
    pub message: String,
    pub last_error: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    pub palette_mode: PaletteMode,
    pub palette_source: PaletteSource,
    pub real_slots: RealSlotSelection,
    pub mix_prediction: MixPrediction,
    pub quality_bias: u8,
    pub output_application: OutputApplication,
    pub auto_open_validated_output: bool,
    pub restore_last_session: bool,
    pub preview_mode: PreviewMode,
    pub viewer_performance: ViewerPerformance,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            palette_mode: PaletteMode::Official,
            palette_source: PaletteSource::Inventory,
            real_slots: RealSlotSelection::Auto,
            mix_prediction: MixPrediction::Bambu,
            quality_bias: 60,
            output_application: OutputApplication::BambuStudio,
            auto_open_validated_output: true,
            restore_last_session: false,
            preview_mode: PreviewMode::Original,
            viewer_performance: ViewerPerformance::Balanced,
        }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum PaletteMode {
    Official,
    Cmykw,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum PaletteSource {
    Inventory,
    Catalog,
    AllBambu,
    Custom,
    ExactCmykw,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum RealSlotSelection {
    Auto,
    #[serde(rename = "2")]
    Two,
    #[serde(rename = "3")]
    Three,
    #[serde(rename = "4")]
    Four,
    #[serde(rename = "5")]
    Five,
    #[serde(rename = "6")]
    Six,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum MixPrediction {
    Bambu,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum OutputApplication {
    BambuStudio,
    OrcaSlicer,
}
