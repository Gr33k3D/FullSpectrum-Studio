import type { RendererBridge, RendererCapabilities, RendererStatus } from "./types";

export class NativeRendererBridge implements RendererBridge {
  readonly capabilities: RendererCapabilities = {
    backend: "native-bridge",
    supports3D: false,
    supportsTexturePreview: false,
    supportsHeatmap: false,
    supportsAnchorInfluence: false,
    supportsNativeGpu: false,
    maxRecommendedTriangles: null,
    notes: [
      "TODO: wire this bridge to Rust runtime commands once the renderer contract is extracted.",
      "Future path: Rust runtime owns GPU device selection and streams renderer state to React."
    ]
  };

  private status: RendererStatus = "idle";

  getStatus(): RendererStatus {
    return this.status;
  }

  async initialize(): Promise<void> {
    this.status = "initializing";
    await new Promise((resolve) => window.setTimeout(resolve, 80));
    this.status = "ready";
  }

  async loadProject(_path: string): Promise<void> {
    this.status = "loading-project";
    await new Promise((resolve) => window.setTimeout(resolve, 80));
    this.status = "ready";
  }

  async dispose(): Promise<void> {
    this.status = "idle";
  }
}
