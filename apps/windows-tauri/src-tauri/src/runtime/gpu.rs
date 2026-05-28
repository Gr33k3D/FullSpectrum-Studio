use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GpuAdapterInfo {
    pub name: String,
    pub vendor: String,
    pub backend: String,
    pub device_type: String,
    pub driver: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GpuInfo {
    pub available: bool,
    pub backend_plan: GpuBackendPlan,
    pub adapters: Vec<GpuAdapterInfo>,
    pub notes: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum GpuBackendPlan {
    Placeholder,
    Wgpu,
}

pub fn placeholder_gpu_info() -> GpuInfo {
    GpuInfo {
        available: false,
        backend_plan: GpuBackendPlan::Placeholder,
        adapters: Vec::new(),
        notes: vec![
            "GPU probing is intentionally a placeholder in this migration foundation.".to_string(),
            "TODO: enable the wgpu-runtime feature and enumerate adapters after renderer contracts are extracted.".to_string(),
        ],
    }
}

#[cfg(feature = "wgpu-runtime")]
pub mod wgpu_probe {
    use super::{GpuBackendPlan, GpuInfo};

    // TODO: Add optional `wgpu` dependency and adapter enumeration once the
    // renderer bridge has a stable ownership/lifetime model.
    pub fn probe() -> GpuInfo {
        GpuInfo {
            available: false,
            backend_plan: GpuBackendPlan::Wgpu,
            adapters: Vec::new(),
            notes: vec!["wgpu feature enabled, but adapter probing is not implemented yet.".to_string()],
        }
    }
}
