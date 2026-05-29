import type {
  AppSettings,
  ConversionResult,
  PaletteMode,
  PaletteSource,
  RealSlotSelection
} from "../types/core";

type PaletteEnginePanelProps = {
  settings: AppSettings;
  sourcePath: string | null;
  referencePath: string | null;
  outputDir: string | null;
  converting: boolean;
  result: ConversionResult | null;
  onSettingsChange: (settings: AppSettings) => void;
  onChooseReference: () => void;
  onChooseOutput: () => void;
  onConvert: () => void;
  onOpenOutput: () => void;
};

const paletteSources: Array<{ value: PaletteSource; label: string }> = [
  { value: "inventory", label: "My Inventory" },
  { value: "catalog", label: "PLA Basic / Matte / Silk+" },
  { value: "all-bambu", label: "All Bambu" },
  { value: "exact-cmykw", label: "Exact CMYKW" }
];

const realSlotOptions: Array<{ value: RealSlotSelection; label: string }> = [
  { value: "auto", label: "Auto" },
  { value: "2", label: "2" },
  { value: "3", label: "3" },
  { value: "4", label: "4" },
  { value: "5", label: "5" },
  { value: "6", label: "6" }
];

export function PaletteEnginePanel({
  settings,
  sourcePath,
  referencePath,
  outputDir,
  converting,
  result,
  onSettingsChange,
  onChooseReference,
  onChooseOutput,
  onConvert,
  onOpenOutput
}: PaletteEnginePanelProps) {
  const update = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    onSettingsChange({ ...settings, [key]: value });
  };
  const canConvert = Boolean(sourcePath) && !converting;

  return (
    <section className="panel palette-engine" id="palette-engine">
      <div className="panel-title-row">
        <div>
          <p className="eyebrow">Palette Engine</p>
          <h2>Painted 3MF Compression</h2>
        </div>
        <span className={result?.output ? "status-chip success" : "status-chip"}>{result?.output ? "validated" : "ready"}</span>
      </div>

      <div className="segmented-control" aria-label="Palette strategy">
        {(["official", "cmykw"] as PaletteMode[]).map((mode) => (
          <button
            className={settings.paletteMode === mode ? "active" : ""}
            key={mode}
            type="button"
            onClick={() => update("paletteMode", mode)}
          >
            {mode === "official" ? "Bambu PLA" : "CMYKW"}
          </button>
        ))}
      </div>

      <div className="form-grid">
        <label>
          <span>Filament source</span>
          <select
            value={settings.paletteSource}
            onChange={(event) => update("paletteSource", event.currentTarget.value as PaletteSource)}
          >
            {paletteSources.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Physical slots</span>
          <select
            value={settings.realSlots}
            onChange={(event) => update("realSlots", event.currentTarget.value as RealSlotSelection)}
          >
            {realSlotOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="wide">
          <span>Quality vs waste: {settings.qualityBias}</span>
          <input
            max="100"
            min="0"
            type="range"
            value={settings.qualityBias}
            onChange={(event) => update("qualityBias", Number(event.currentTarget.value))}
          />
        </label>
      </div>

      <div className="option-row">
        <label>
          <input
            checked={settings.autoOpenValidatedOutput}
            type="checkbox"
            onChange={(event) => update("autoOpenValidatedOutput", event.currentTarget.checked)}
          />
          Auto-open validated output
        </label>
      </div>

      <div className="path-grid">
        <div>
          <strong>Source</strong>
          <span>{sourcePath ? displayPath(sourcePath) : "Choose a painted .3mf, .obj or .glb"}</span>
        </div>
        <div>
          <strong>Reference</strong>
          <span>{referencePath ? displayPath(referencePath) : "Optional visual target"}</span>
        </div>
        <div>
          <strong>Output folder</strong>
          <span>{outputDir ? displayPath(outputDir) : "Source folder or engine default"}</span>
        </div>
      </div>

      <div className="button-row">
        <button type="button" onClick={onChooseReference}>
          Reference
        </button>
        <button type="button" onClick={onChooseOutput}>
          Output Folder
        </button>
        <button className="primary-action" disabled={!canConvert} type="button" onClick={onConvert}>
          {converting ? "Converting..." : "Convert and Validate"}
        </button>
        <button disabled={!result?.output && !outputDir} type="button" onClick={onOpenOutput}>
          Open Output
        </button>
      </div>

      {result ? (
        <div className="result-card">
          <div>
            <strong>{result.realSlots ?? "?"} real</strong>
            <span>{result.outputSlots ?? "?"} output slots</span>
          </div>
          <div>
            <strong>{result.quality?.qualityScore ?? result.quality?.confidenceScore ?? "?"}/100</strong>
            <span>{result.quality?.qualityScore ? "quality" : "confidence"}</span>
          </div>
          <div>
            <strong>{result.validation ?? (result.colorValidation?.verified ? "OK" : "Check")}</strong>
            <span>paint and mixed-color validation</span>
          </div>
          <div>
            <strong>{result.quality?.estimatedDeltaE ?? result.quality?.meanDeltaE ?? "?"}</strong>
            <span>estimated ΔE</span>
          </div>
          <div className="wide">
            <strong>Output</strong>
            <span>{result.output ? displayPath(result.output) : "No output path returned"}</span>
          </div>
          {result.recommendation?.summary ? (
            <div className="wide">
              <strong>Recommendation</strong>
              <span>{result.recommendation.summary}</span>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function displayPath(path: string) {
  const cleaned = path.replace(/\\/g, "/");
  const parts = cleaned.split("/").filter(Boolean);
  return parts.length ? parts[parts.length - 1] : path;
}
