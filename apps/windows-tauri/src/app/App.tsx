import { useEffect, useMemo, useState } from "react";
import { MainLayout } from "../layout/MainLayout";
import { WebRendererPlaceholder } from "../renderer/WebRendererPlaceholder";
import type { RendererStatus } from "../renderer/types";
import {
  getAppVersion,
  getGpuInfoPlaceholder,
  getRuntimePaths,
  readRecentLogs,
  convertProject,
  revealPath,
  selectOutputDirectory,
  selectProjectDirectory,
  selectReferenceFile,
  selectSourceFile,
  writeLog
} from "../runtime/tauriRuntime";
import {
  defaultAppSettings,
  type AppSettings,
  type ConversionResult,
  type ProjectInspection,
  type ProjectMetadata,
  type RuntimeStatus
} from "../types/core";
import type { GpuInfo, LogEntry, RuntimePathsResponse } from "../types/runtime";

export function App() {
  const renderer = useMemo(() => new WebRendererPlaceholder(), []);
  const [version, setVersion] = useState("0.1.0");
  const [status, setStatus] = useState("Starting Windows FullSpectrum runtime...");
  const [runtime, setRuntime] = useState<RuntimePathsResponse | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus>({
    ready: false,
    message: "Starting Windows FullSpectrum runtime...",
    paths: null,
    gpu: null,
    lastError: null
  });
  const [settings, setSettings] = useState<AppSettings>(defaultAppSettings);
  const [metadata, setMetadata] = useState<ProjectMetadata | null>(null);
  const [inspection, setInspection] = useState<ProjectInspection | null>(null);
  const [sourcePath, setSourcePath] = useState<string | null>(null);
  const [referencePath, setReferencePath] = useState<string | null>(null);
  const [outputDir, setOutputDir] = useState<string | null>(null);
  const [conversionResult, setConversionResult] = useState<ConversionResult | null>(null);
  const [converting, setConverting] = useState(false);
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
        message: "Runtime directories prepared. Conversion engine bridge ready.",
        paths: paths.paths,
        gpu,
        lastError: null
      });
      setRendererStatus(renderer.getStatus());
      setStatus("Runtime directories prepared. Conversion engine bridge ready.");
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
      setSourcePath(result.input);
      setConversionResult(null);
      setOutputDir((current) => current ?? parentDirectory(result.input));
      await renderer.loadProject(result.input);
      setRendererStatus(renderer.getStatus());
      setStatus(`${result.filename}: ${result.sourceSlots} source slots inspected by the FullSpectrum engine.`);
      await refreshLogs();
    } catch (error) {
      reportError(error);
    }
  }

  async function handleChooseReference() {
    try {
      const selected = await selectReferenceFile();
      if (selected === null) {
        setStatus("Reference selection cancelled.");
        return;
      }
      setReferencePath(selected);
      setStatus(`Reference selected: ${fileName(selected)}`);
    } catch (error) {
      reportError(error);
    }
  }

  async function handleChooseOutput() {
    try {
      const selected = await selectOutputDirectory();
      if (selected === null) {
        setStatus("Output folder selection cancelled.");
        return;
      }
      setOutputDir(selected);
      setStatus(`Output folder selected: ${selected}`);
    } catch (error) {
      reportError(error);
    }
  }

  async function handleConvert() {
    if (!sourcePath || converting) {
      setStatus("Open a source file before converting.");
      return;
    }
    setConverting(true);
    setStatus("Converting and validating with the FullSpectrum engine...");
    try {
      const result = await convertProject({
        inputPath: sourcePath,
        outputDir,
        referencePath,
        paletteMode: settings.paletteMode,
        paletteSource: settings.paletteSource,
        realSlots: settings.realSlots,
        qualityBias: settings.qualityBias,
        autoOpenValidatedOutput: settings.autoOpenValidatedOutput
      });
      setConversionResult(result);
      setStatus(`Validated output ready: ${result.output ?? fileName(sourcePath)}`);
      await refreshLogs();
    } catch (error) {
      reportError(error);
    } finally {
      setConverting(false);
    }
  }

  async function handleOpenOutput() {
    try {
      const target = conversionResult?.output ?? outputDir;
      if (!target) {
        setStatus("Convert a source or choose an output folder first.");
        return;
      }
      await revealPath(target);
      setStatus(`Opened output location: ${target}`);
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
      sourcePath={sourcePath}
      referencePath={referencePath}
      outputDir={outputDir}
      converting={converting}
      conversionResult={conversionResult}
      rendererStatus={rendererStatus}
      rendererCapabilities={renderer.capabilities}
      gpuInfo={gpuInfo}
      logs={logs}
      onOpenSource={handleOpenSource}
      onChooseReference={handleChooseReference}
      onChooseOutput={handleChooseOutput}
      onConvert={handleConvert}
      onOpenOutput={handleOpenOutput}
      onSettingsChange={setSettings}
      onSelectProjectDirectory={handleSelectProjectDirectory}
      onRefreshRuntime={handleRefreshRuntime}
    />
  );
}

function parentDirectory(path: string): string | null {
  const normalized = path.replace(/\\/g, "/");
  const index = normalized.lastIndexOf("/");
  return index > 0 ? path.slice(0, index) : null;
}

function fileName(path: string): string {
  return path.replace(/\\/g, "/").split("/").pop() ?? path;
}
