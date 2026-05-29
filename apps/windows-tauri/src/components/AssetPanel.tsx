import type { ProjectInspection, ProjectMetadata } from "../types/core";
import type { GpuInfo } from "../types/runtime";

type AssetPanelProps = {
  metadata: ProjectMetadata | null;
  inspection: ProjectInspection | null;
  gpuInfo: GpuInfo | null;
};

export function AssetPanel({ metadata, inspection, gpuInfo }: AssetPanelProps) {
  return (
    <section className="panel asset-panel" id="assets">
      <div>
        <p className="eyebrow">Assets</p>
        <h2>Project and Runtime Bridge</h2>
      </div>
      <div className="asset-grid">
        <div>
          <strong>Input support</strong>
          <span>.3mf conversion, experimental .obj/.glb import</span>
        </div>
        <div>
          <strong>Current metadata</strong>
          <span>{inspection?.filename ?? metadata?.name ?? "No loaded project"}</span>
        </div>
        <div>
          <strong>Files scanned</strong>
          <span>{metadata ? `${metadata.fileCount} total / ${metadata.supportedFileCount} supported` : "Waiting"}</span>
        </div>
        <div>
          <strong>GPU adapters</strong>
          <span>{gpuInfo?.adapters.length ?? 0} reported</span>
        </div>
        <div>
          <strong>Runtime bridge</strong>
          <span>{inspection ? "FullSpectrum engine active" : "Tauri commands ready"}</span>
        </div>
      </div>
      {inspection?.sourceColors.length ? (
        <div className="source-colors">
          {inspection.sourceColors.slice(0, 48).map((color, index) => (
            <span key={`${color}-${index}`} title={`Slot ${index + 1}: ${color}`} style={{ background: color }} />
          ))}
        </div>
      ) : null}
    </section>
  );
}
