import { convertFileSrc } from "@tauri-apps/api/core";
import type { RendererCapabilities, RendererStatus } from "../renderer/types";
import type { AppSettings, ConversionResult, PreviewMode, ProjectInspection, ViewerPerformance } from "../types/core";
import type { GpuInfo } from "../types/runtime";

type RendererPreviewProps = {
  status: RendererStatus;
  capabilities: RendererCapabilities;
  gpuInfo: GpuInfo | null;
  inspection: ProjectInspection | null;
  conversionResult: ConversionResult | null;
  settings: AppSettings;
  onSettingsChange: (settings: AppSettings) => void;
};

const previewModes: Array<{ value: PreviewMode; label: string }> = [
  { value: "original", label: "Original" },
  { value: "predicted", label: "Predicted" },
  { value: "validation", label: "Reduced" },
  { value: "colorLoss", label: "Heatmap" },
  { value: "anchorInfluence", label: "Anchors" },
  { value: "wireframe", label: "Wireframe" }
];

const renderModes: Array<{ value: ViewerPerformance; label: string }> = [
  { value: "fast", label: "Fast" },
  { value: "balanced", label: "Balanced" },
  { value: "high", label: "High" },
  { value: "maximum", label: "Maximum" }
];

export function RendererPreview({
  status,
  capabilities,
  gpuInfo,
  inspection,
  conversionResult,
  settings,
  onSettingsChange
}: RendererPreviewProps) {
  const thumbnail = inspection?.thumbnail ? convertFileSrc(inspection.thumbnail) : null;
  const metrics = inspection?.metrics;
  const sourceColorCount = inspection?.sourceColors.length ?? 0;
  const update = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    onSettingsChange({ ...settings, [key]: value });
  };

  return (
    <section className="renderer-panel" id="renderer">
      <div className="renderer-header">
        <div>
          <p className="eyebrow">Model Preview</p>
          <h2>{inspection?.filename ?? "Open a painted project"}</h2>
        </div>
        <span className="status-chip">{conversionResult?.validation === "OK" ? "validated" : status}</span>
      </div>

      <div className="preview-toolbar">
        <div className="mode-tabs" aria-label="Preview mode">
          {previewModes.map((mode) => (
            <button
              className={settings.previewMode === mode.value ? "active" : ""}
              key={mode.value}
              type="button"
              onClick={() => update("previewMode", mode.value)}
            >
              {mode.label}
            </button>
          ))}
        </div>
        <label className="render-select">
          Render
          <select
            value={settings.viewerPerformance}
            onChange={(event) => update("viewerPerformance", event.currentTarget.value as ViewerPerformance)}
          >
            {renderModes.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={thumbnail ? "preview-stage has-image" : "preview-stage"}>
        {thumbnail ? (
          <img alt={`${inspection?.filename ?? "Source"} plate preview`} className="plate-preview-image" src={thumbnail} />
        ) : (
          <div className="preview-cube" aria-hidden="true" />
        )}
        <div className="preview-copy">
          <h3>{previewModeTitle(settings.previewMode)}</h3>
          <p>
            The Windows app now drives the same FullSpectrum engine as the macOS app. The heavy orbitable renderer is still
            being migrated, so this panel shows the source plate thumbnail and validated color/runtime metadata without
            pretending the native GPU viewer is finished.
          </p>
          {inspection?.previewNotice ? <p className="warning-text">{inspection.previewNotice}</p> : null}
        </div>
      </div>

      {inspection?.sourceColors.length ? (
        <div className="source-strip" aria-label="Source paint colors">
          {inspection.sourceColors.slice(0, 64).map((color, index) => (
            <span key={`${color}-${index}`} title={`Source slot ${index + 1}: ${color}`} style={{ background: color }} />
          ))}
          {inspection.sourceColors.length > 64 ? <strong>+{inspection.sourceColors.length - 64}</strong> : null}
        </div>
      ) : null}

      <div className="renderer-grid">
        <div>
          <strong>Source colors</strong>
          <span>{sourceColorCount ? `${sourceColorCount} slots` : "Waiting"}</span>
        </div>
        <div>
          <strong>Triangles</strong>
          <span>{formatNumber(metrics?.triangleCount ?? metrics?.polygonCount)}</span>
        </div>
        <div>
          <strong>Vertices</strong>
          <span>{formatNumber(metrics?.vertexCount)}</span>
        </div>
        <div>
          <strong>Output slots</strong>
          <span>{conversionResult?.outputSlots ? `${conversionResult.outputSlots}` : "Convert first"}</span>
        </div>
        <div>
          <strong>Quality</strong>
          <span>{conversionResult?.quality?.qualityScore ? `${conversionResult.quality.qualityScore}/100` : "Pending"}</span>
        </div>
        <div>
          <strong>Renderer path</strong>
          <span>{capabilities.supportsNativeGpu ? "Native" : gpuInfo?.backendPlan ?? "Tauri bridge"}</span>
        </div>
      </div>
    </section>
  );
}

function previewModeTitle(mode: PreviewMode) {
  switch (mode) {
    case "original":
      return "Original source";
    case "predicted":
      return "Predicted print";
    case "validation":
      return "Reduced palette";
    case "colorLoss":
      return "Color loss heatmap";
    case "anchorInfluence":
      return "Anchor influence";
    case "wireframe":
      return "Wireframe check";
    case "plateImage":
      return "Plate image";
  }
}

function formatNumber(value: number | null | undefined) {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "Not sampled";
}
