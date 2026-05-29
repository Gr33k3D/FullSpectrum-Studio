import type { RendererBridge, RendererCapabilities, RendererStatus } from "./types";

export class WebRendererPlaceholder implements RendererBridge {
  readonly capabilities: RendererCapabilities = {
    backend: "web-three",
    supports3D: true,
    supportsTexturePreview: true,
    supportsHeatmap: false,
    supportsAnchorInfluence: false,
    supportsNativeGpu: false,
    maxRecommendedTriangles: 250_000,
    notes: [
      "Three.js viewer loads GLB/OBJ references with an orbit camera and build plate.",
      "Heatmap and anchor influence still depend on the future shared preview asset contract."
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
    this.status = "loading-project";
    await new Promise((resolve) => window.setTimeout(resolve, 120));
    this.status = "ready";
  }

  async dispose(): Promise<void> {
    this.status = "idle";
  }
}
