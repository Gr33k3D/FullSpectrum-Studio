import { AssetPanel } from "../components/AssetPanel";
import { LogPanel } from "../components/LogPanel";
import { ProjectSidebar } from "../components/ProjectSidebar";
import { RendererPreview } from "../components/RendererPreview";
import { StatusBar } from "../components/StatusBar";
import { Toolbar } from "../components/Toolbar";
import type { RendererCapabilities, RendererStatus } from "../renderer/types";
import type { AppSettings, ProjectInspection, ProjectMetadata, RuntimeStatus } from "../types/core";
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
  rendererStatus: RendererStatus;
  rendererCapabilities: RendererCapabilities;
  gpuInfo: GpuInfo | null;
  logs: LogEntry[];
  onOpenSource: () => void;
  onSelectProjectDirectory: () => void;
  onRefreshRuntime: () => void;
  onWriteLog: () => void;
};

export function MainLayout(props: MainLayoutProps) {
  return (
    <div className="app-shell">
      <Toolbar
        version={props.version}
        onOpenSource={props.onOpenSource}
        onSelectProjectDirectory={props.onSelectProjectDirectory}
        onRefreshRuntime={props.onRefreshRuntime}
        onWriteLog={props.onWriteLog}
      />
      <main className="workspace">
        <ProjectSidebar
          runtime={props.runtime}
          runtimeStatus={props.runtimeStatus}
          settings={props.settings}
          metadata={props.metadata}
          inspection={props.inspection}
          selectedDirectory={props.selectedDirectory}
        />
        <div className="center-stack">
          <RendererPreview
            status={props.rendererStatus}
            capabilities={props.rendererCapabilities}
            gpuInfo={props.gpuInfo}
          />
          <AssetPanel metadata={props.metadata} inspection={props.inspection} gpuInfo={props.gpuInfo} />
          <LogPanel logs={props.logs} />
        </div>
      </main>
      <StatusBar status={props.status} runtimeReady={props.runtime !== null} />
    </div>
  );
}
