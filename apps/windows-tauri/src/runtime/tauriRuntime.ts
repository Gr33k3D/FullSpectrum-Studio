import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import type { ConversionRequest, ConversionResult, ProjectInspection, ProjectMetadata } from "../types/core";
import type { GpuInfo, LogEntry, LogLevel, LogWriteResult, RuntimePathsResponse } from "../types/runtime";

export type ProjectDirectorySelection = {
  selectedPath: string | null;
  projectsDir: string;
  metadata: ProjectMetadata;
  note: string;
};

export async function getAppVersion(): Promise<string> {
  return invoke<string>("get_app_version");
}

export async function getRuntimePaths(): Promise<RuntimePathsResponse> {
  return invoke<RuntimePathsResponse>("get_runtime_paths");
}

export async function selectProjectDirectory(): Promise<ProjectDirectorySelection | null> {
  const selected = await open({
    directory: true,
    multiple: false,
    title: "Open FullSpectrum Project Folder"
  });
  if (typeof selected !== "string") {
    return null;
  }
  return invoke<ProjectDirectorySelection>("select_project_directory", { selectedPath: selected });
}

export async function loadProjectMetadata(path: string | null): Promise<ProjectMetadata> {
  return invoke<ProjectMetadata>("load_project_metadata", { path });
}

export async function selectSourceFile(): Promise<ProjectInspection | null> {
  const selected = await open({
    directory: false,
    multiple: false,
    title: "Open Painted 3MF or Textured Source",
    filters: [
      {
        name: "FullSpectrum sources",
        extensions: ["3mf", "obj", "glb"]
      }
    ]
  });
  if (typeof selected !== "string") {
    return null;
  }
  return inspectProject(selected);
}

export async function selectReferenceFile(): Promise<string | null> {
  const selected = await open({
    directory: false,
    multiple: false,
    title: "Open Optional Visual Reference",
    filters: [
      {
        name: "Reference assets",
        extensions: ["obj", "glb", "png", "jpg", "jpeg"]
      }
    ]
  });
  return typeof selected === "string" ? selected : null;
}

export async function selectOutputDirectory(): Promise<string | null> {
  const selected = await open({
    directory: true,
    multiple: false,
    title: "Choose FullSpectrum Output Folder"
  });
  return typeof selected === "string" ? selected : null;
}

export async function inspectProject(path: string): Promise<ProjectInspection> {
  const metadataOnly = path.toLowerCase().endsWith(".3mf");
  return invoke<ProjectInspection>("inspect_project", { path, metadataOnly });
}

export async function convertProject(request: ConversionRequest): Promise<ConversionResult> {
  return invoke<ConversionResult>("convert_project", { request });
}

export async function revealPath(path: string): Promise<void> {
  return invoke<void>("reveal_path", { path });
}

export async function writeLog(level: LogLevel, message: string): Promise<LogWriteResult> {
  return invoke<LogWriteResult>("write_log", { level, message });
}

export async function readRecentLogs(limit = 80): Promise<LogEntry[]> {
  return invoke<LogEntry[]>("read_recent_logs", { limit });
}

export async function getGpuInfoPlaceholder(): Promise<GpuInfo> {
  return invoke<GpuInfo>("get_gpu_info_placeholder");
}
