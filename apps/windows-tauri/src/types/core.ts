import type { GpuInfo, RuntimePaths } from "./runtime";
import type { RendererBackend, RendererCapabilities, RendererStatus } from "../renderer/types";

export type AssetKind = "project3mf" | "obj" | "glb" | "texture" | "customPalette" | "directory" | "other";

export type AssetMetadata = {
  path: string;
  name: string;
  extension: string | null;
  kind: AssetKind;
  sizeBytes: number | null;
  modifiedUnixMs: number | null;
  supportedInput: boolean;
};

export type ProjectMetadata = {
  selectedPath: string | null;
  exists: boolean;
  kind: "file" | "directory" | "missing" | "unknown";
  name: string | null;
  extension: string | null;
  sizeBytes: number | null;
  modifiedUnixMs: number | null;
  supportedInput: boolean;
  fileCount: number;
  supportedFileCount: number;
  totalBytes: number;
  assets: AssetMetadata[];
  notes: string[];
};

export type MeshMetrics = {
  objectCount?: number | null;
  vertexCount?: number | null;
  triangleCount?: number | null;
  polygonCount?: number | null;
  textureBytes?: number | null;
  recommendedRenderMode?: string | null;
  previewMemoryEstimateBytes?: number | null;
  previewBuildEstimateSeconds?: number | null;
  sourceSlots?: number | null;
  paintReferences?: number | null;
  paintModels?: number | null;
};

export type ImportSummary = {
  sourceType: string;
  texture: string;
  vertexCount: number;
  triangleCount: number;
  internalColorCount: number;
  exportColorCount: number;
  compressedForBambu: boolean;
};

export type ProjectInspection = {
  input: string;
  filename: string;
  sourceSlots: number;
  sourceColors: string[];
  thumbnail: string | null;
  previewMesh: string | null;
  previewNotice: string | null;
  metrics: MeshMetrics | null;
  import: ImportSummary | null;
};

export type PreviewMode =
  | "plateImage"
  | "original"
  | "predicted"
  | "validation"
  | "colorLoss"
  | "anchorInfluence"
  | "wireframe";

export type ViewerPerformance = "fast" | "balanced" | "high" | "maximum";

export type RendererState = {
  backend: RendererBackend;
  status: RendererStatus;
  previewMode: PreviewMode;
  performance: ViewerPerformance;
  loadedAssetPath: string | null;
  capabilities: RendererCapabilities;
  warnings: string[];
};

export type RuntimeStatus = {
  ready: boolean;
  message: string;
  paths: RuntimePaths | null;
  gpu: GpuInfo | null;
  lastError: string | null;
};

export type PaletteMode = "official" | "cmykw";
export type PaletteSource = "inventory" | "catalog" | "all-bambu" | "custom" | "exact-cmykw";
export type RealSlotSelection = "auto" | "2" | "3" | "4" | "5" | "6";
export type MixPrediction = "bambu";
export type OutputApplication = "bambu-studio" | "orca-slicer";

export type AppSettings = {
  paletteMode: PaletteMode;
  paletteSource: PaletteSource;
  realSlots: RealSlotSelection;
  mixPrediction: MixPrediction;
  qualityBias: number;
  outputApplication: OutputApplication;
  autoOpenValidatedOutput: boolean;
  restoreLastSession: boolean;
  previewMode: PreviewMode;
  viewerPerformance: ViewerPerformance;
};

export const defaultAppSettings: AppSettings = {
  paletteMode: "official",
  paletteSource: "inventory",
  realSlots: "auto",
  mixPrediction: "bambu",
  qualityBias: 60,
  outputApplication: "bambu-studio",
  autoOpenValidatedOutput: true,
  restoreLastSession: false,
  previewMode: "original",
  viewerPerformance: "balanced"
};
