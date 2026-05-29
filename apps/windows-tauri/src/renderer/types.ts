export type RendererBackend = "web-placeholder" | "web-three" | "native-bridge" | "wgpu-future";

export type RendererStatus =
  | "idle"
  | "initializing"
  | "loading-project"
  | "rendering-placeholder"
  | "ready"
  | "error";

export type RendererCapabilities = {
  backend: RendererBackend;
  supports3D: boolean;
  supportsTexturePreview: boolean;
  supportsHeatmap: boolean;
  supportsAnchorInfluence: boolean;
  supportsNativeGpu: boolean;
  maxRecommendedTriangles: number | null;
  notes: string[];
};

export interface RendererBridge {
  readonly capabilities: RendererCapabilities;
  getStatus(): RendererStatus;
  initialize(): Promise<void>;
  loadProject(path: string): Promise<void>;
  dispose(): Promise<void>;
}
