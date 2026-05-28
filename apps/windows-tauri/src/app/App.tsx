import { useEffect, useMemo, useState } from "react";
import { MainLayout } from "../layout/MainLayout";
import { WebRendererPlaceholder } from "../renderer/WebRendererPlaceholder";
import type { RendererStatus } from "../renderer/types";
import {
  getAppVersion,
  getGpuInfoPlaceholder,
  getRuntimePaths,
  readRecentLogs,
  selectProjectDirectory,
  selectSourceFile,
  writeLog
} from "../runtime/tauriRuntime";
import {
  defaultAppSettings,
  type AppSettings,
  type ProjectInspection,
  type ProjectMetadata,
  type RuntimeStatus
} from "../types/core";
import type { GpuInfo, LogEntry, RuntimePathsResponse } from "../types/runtime";

export function App() {
  const renderer = useMemo(() => new WebRendererPlaceholder(), []);
  const [version, setVersion] = useState("0.1.0");
  const [status, setStatus] = useState("Starting Windows runtime shell...");
  const [runtime, setRuntime] = useState<RuntimePathsResponse | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus>({
    ready: false,
    message: "Starting Windows runtime shell...",
    paths: null,
    gpu: null,
    lastError: null
  });
  const [settings] = useState<AppSettings>(defaultAppSettings);
  const [metadata, setMetadata] = useState<ProjectMetadata | null>(null);
  const [inspection, setInspection] = useState<ProjectInspection | null>(null);
  const [selectedDirectory, setSelectedDirectory] = useState<string | null>(null);
  const [gpuInfo, setGpuInfo] = useState<GpuInfo | null>(null);
  const [rendererStatus, setRendererStatus] = useState<RendererStatus>(renderer.getStatus());
  const [logs, setLogs] = useState<LogEntry[]>([]);

  useEffect(() => {
    void initialize();
    return () => {
      void renderer.dispose();
    };
  }, []);

  async function initialize() {
    try {
      const [appVersion, paths, gpu] = await Promise.all([
        getAppVersion(),
        getRuntimePaths(),
        getGpuInfoPlaceholder()
      ]);
      await renderer.initialize();
      setVersion(appVersion);
      setRuntime(paths);
      setGpuInfo(gpu);
      setRuntimeStatus({
        ready: true,
        message: "Runtime directories prepared. Renderer placeholder ready.",
        paths: paths.paths,
        gpu,
        lastError: null
      });
      setRendererStatus(renderer.getStatus());
      setStatus("Runtime directories prepared. Renderer placeholder ready.");
      await writeLog("info", `Runtime initialized with ${paths.created.length} prepared directories.`);
      await refreshLogs();
    } catch (error) {
      reportError(error);
    }
  }

  async function handleRefreshRuntime() {
    try {
      const paths = await getRuntimePaths();
      setRuntime(paths);
      setRuntimeStatus((current) => ({
        ...current,
        ready: true,
        paths: paths.paths,
        message: "Runtime paths refreshed.",
        lastError: null
      }));
      setStatus("Runtime paths refreshed.");
      await writeLog("info", `Runtime paths refreshed: ${paths.paths.appDataDir}`);
      await refreshLogs();
    } catch (error) {
      reportError(error);
    }
  }

  async function handleSelectProjectDirectory() {
    try {
      const result = await selectProjectDirectory();
      if (result === null) {
        setStatus("Project folder selection cancelled.");
        return;
      }
      const selectedPath = result.selectedPath ?? result.projectsDir;
      setSelectedDirectory(selectedPath);
      setMetadata(result.metadata);
      await renderer.loadProject(selectedPath);
      setRendererStatus(renderer.getStatus());
      setStatus(result.note);
      await writeLog("info", `Project directory selected: ${selectedPath}`);
      await refreshLogs();
    } catch (error) {
      reportError(error);
    }
  }

  async function handleOpenSource() {
    try {
      setStatus("Opening source file...");
      const result = await selectSourceFile();
      if (result === null) {
        setStatus("Source selection cancelled.");
        return;
      }
      setInspection(result);
      setSelectedDirectory(result.input);
      await renderer.loadProject(result.input);
      setRendererStatus(renderer.getStatus());
      setStatus(`${result.filename}: ${result.sourceSlots} source slots inspected by the FullSpectrum engine.`);
      await refreshLogs();
    } catch (error) {
      reportError(error);
    }
  }

  async function handleWriteLog() {
    try {
      const written = await writeLog("info", "Windows Tauri shell wrote a test log entry.");
      setStatus(`Log written to ${written.path}`);
      await refreshLogs();
    } catch (error) {
      reportError(error);
    }
  }

  async function refreshLogs() {
    const entries = await readRecentLogs(80);
    setLogs(entries);
  }

  function reportError(error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    setStatus(message);
    setRuntimeStatus((current) => ({ ...current, ready: false, lastError: message, message }));
    void writeLog("error", message)
      .then(() => refreshLogs())
      .catch(() => {
        setLogs((existing) => [
          { timestamp: null, level: "error", message, raw: `ERROR ${message}` },
          ...existing
        ]);
      });
  }

  return (
    <MainLayout
      version={version}
      status={status}
      runtime={runtime}
      runtimeStatus={runtimeStatus}
      settings={settings}
      metadata={metadata}
      inspection={inspection}
      selectedDirectory={selectedDirectory}
      rendererStatus={rendererStatus}
      rendererCapabilities={renderer.capabilities}
      gpuInfo={gpuInfo}
      logs={logs}
      onOpenSource={handleOpenSource}
      onSelectProjectDirectory={handleSelectProjectDirectory}
      onRefreshRuntime={handleRefreshRuntime}
      onWriteLog={handleWriteLog}
    />
  );
}
