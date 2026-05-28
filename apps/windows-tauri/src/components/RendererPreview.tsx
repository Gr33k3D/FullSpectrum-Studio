import type { GpuInfo } from "../types/runtime";
import type { RendererCapabilities, RendererStatus } from "../renderer/types";

type RendererPreviewProps = {
  status: RendererStatus;
  capabilities: RendererCapabilities;
  gpuInfo: GpuInfo | null;
};

export function RendererPreview({ status, capabilities, gpuInfo }: RendererPreviewProps) {
  return (
    <section className="renderer-panel" id="renderer">
      <div className="renderer-header">
        <div>
          <p className="eyebrow">Renderer</p>
          <h2>Preview Foundation</h2>
        </div>
        <span className="status-chip">{status}</span>
      </div>

      <div className="renderer-canvas-placeholder">
        <div className="preview-cube" aria-hidden="true" />
        <div>
          <h3>{capabilities.backend}</h3>
          <p>
            Placeholder surface for the Windows renderer. This is intentionally honest: no 3D GPU renderer is claimed until
            the shared preview/runtime layer is extracted.
          </p>
        </div>
      </div>

      <div className="renderer-grid">
        <div>
          <strong>3D</strong>
          <span>{capabilities.supports3D ? "Ready" : "Pending"}</span>
        </div>
        <div>
          <strong>Heatmap</strong>
          <span>{capabilities.supportsHeatmap ? "Ready" : "Pending"}</span>
        </div>
        <div>
          <strong>Native GPU</strong>
          <span>{capabilities.supportsNativeGpu ? "Ready" : "Planned"}</span>
        </div>
        <div>
          <strong>GPU path</strong>
          <span>{gpuInfo?.backendPlan ?? "placeholder"}</span>
        </div>
      </div>
    </section>
  );
}
