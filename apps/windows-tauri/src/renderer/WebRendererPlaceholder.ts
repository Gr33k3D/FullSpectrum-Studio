import type { RendererBridge, RendererCapabilities, RendererStatus } from "./types";

export class WebRendererPlaceholder implements RendererBridge {
  readonly capabilities: RendererCapabilities = {
    backend: "web-placeholder",
    supports3D: false,
    supportsTexturePreview: false,
    supportsHeatmap: false,
    supportsAnchorInfluence: false,
    supportsNativeGpu: false,
    maxRecommendedTriangles: null,
    notes: [
      "This is a layout-safe preview placeholder.",
      "The next renderer phase should consume shared inspection/preview assets from the engine."
    ]
  };

  private status: RendererStatus = "idle";

  getStatus(): RendererStatus {
    return this.status;
  }

  async initialize(): Promise<void> {
    this.status = "ready";
  }

  async loadProject(_path: string): Promise<void> {
    this.status = "rendering-placeholder";
    await new Promise((resolve) => window.setTimeout(resolve, 120));
    this.status = "ready";
  }

  async dispose(): Promise<void> {
    this.status = "idle";
  }
}
