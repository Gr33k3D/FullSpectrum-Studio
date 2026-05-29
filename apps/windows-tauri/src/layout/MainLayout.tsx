import { AssetPanel } from "../components/AssetPanel";
import { LogPanel } from "../components/LogPanel";
import { PaletteEnginePanel } from "../components/PaletteEnginePanel";
import { ProjectSidebar } from "../components/ProjectSidebar";
import { RendererPreview } from "../components/RendererPreview";
import { StatusBar } from "../components/StatusBar";
import { Toolbar } from "../components/Toolbar";
import type { RendererCapabilities, RendererStatus } from "../renderer/types";
import type { AppSettings, ConversionResult, ProjectInspection, ProjectMetadata, RuntimeStatus } from "../types/core";
import type { GpuInfo, LogEntry, RuntimePathsResponse } from "../types/runtime";

type MainLayoutProps = {
  version: string;
  status: string;
  runtime: RuntimePathsResponse | null;
  runtimeStatus: RuntimeStatus;
  settings: AppSettings;
  metadata: ProjectMetadata | null;
  inspection: ProjectInspection | null;
  selectedDirectory: string | null;
  sourcePath: string | null;
  referencePath: string | null;
  outputDir: string | null;
  converting: boolean;
  conversionResult: ConversionResult | null;
  rendererStatus: RendererStatus;
  rendererCapabilities: RendererCapabilities;
  gpuInfo: GpuInfo | null;
  logs: LogEntry[];
  onOpenSource: () => void;
  onChooseReference: () => void;
  onChooseOutput: () => void;
  onConvert: () => void;
  onOpenOutput: () => void;
  onSettingsChange: (settings: AppSettings) => void;
  onSelectProjectDirectory: () => void;
  onRefreshRuntime: () => void;
};

export function MainLayout(props: MainLayoutProps) {
  return (
    <div className="app-shell">
      <Toolbar
        version={props.version}
        onOpenSource={props.onOpenSource}
        onConvert={props.onConvert}
        onSelectProjectDirectory={props.onSelectProjectDirectory}
        onRefreshRuntime={props.onRefreshRuntime}
        converting={props.converting}
        canConvert={Boolean(props.sourcePath)}
      />
      <main className="workspace">
        <div className="center-stack">
          <RendererPreview
            status={props.rendererStatus}
            capabilities={props.rendererCapabilities}
            gpuInfo={props.gpuInfo}
            inspection={props.inspection}
            conversionResult={props.conversionResult}
            settings={props.settings}
            onSettingsChange={props.onSettingsChange}
          />
          <AssetPanel metadata={props.metadata} inspection={props.inspection} gpuInfo={props.gpuInfo} />
          <LogPanel logs={props.logs} />
        </div>
        <div className="right-stack">
          <PaletteEnginePanel
            settings={props.settings}
            sourcePath={props.sourcePath}
            referencePath={props.referencePath}
            outputDir={props.outputDir}
            converting={props.converting}
            result={props.conversionResult}
            onSettingsChange={props.onSettingsChange}
            onChooseReference={props.onChooseReference}
            onChooseOutput={props.onChooseOutput}
            onConvert={props.onConvert}
            onOpenOutput={props.onOpenOutput}
          />
          <ProjectSidebar
            runtime={props.runtime}
            runtimeStatus={props.runtimeStatus}
            settings={props.settings}
            metadata={props.metadata}
            inspection={props.inspection}
            selectedDirectory={props.selectedDirectory}
          />
        </div>
      </main>
      <StatusBar status={props.status} runtimeReady={props.runtime !== null} />
    </div>
  );
}
