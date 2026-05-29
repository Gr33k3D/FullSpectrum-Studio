import { defaultAppSettings, type ConversionResult, type ProjectInspection, type RuntimeStatus } from "../types/core";
import type { GpuInfo, RuntimePathsResponse } from "../types/runtime";

export type BrowserDemoState = {
  active: boolean;
  version: string;
  status: string;
  runtime: RuntimePathsResponse;
  runtimeStatus: RuntimeStatus;
  gpuInfo: GpuInfo;
  inspection: ProjectInspection;
  sourcePath: string;
  referencePath: string | null;
  outputDir: string;
  conversionResult: ConversionResult;
};

export function getBrowserDemoState(): BrowserDemoState | null {
  const params = new URLSearchParams(window.location.search);
  if (params.get("demo") !== "windows") {
    return null;
  }
  const referencePath = params.get("reference");
  const sourcePath = params.get("source") ?? "Angel-painted-source.3mf";
  const outputDir = params.get("output") ?? "FullSpectrum-output";
  return {
    active: true,
    version: "0.1.0-demo",
    status: "Demo preview loaded. Conversion controls use the same layout as the Tauri desktop app.",
    runtime: {
      paths: {
        appDataDir: "Local app data",
        cacheDir: "Local cache",
        logsDir: "Local logs",
        projectsDir: "Local projects",
        shadersDir: "Local shaders",
        tempDir: "Local temp"
      },
      created: []
    },
    runtimeStatus: {
      ready: true,
      message: "Demo runtime ready.",
      paths: {
        appDataDir: "Local app data",
        cacheDir: "Local cache",
        logsDir: "Local logs",
        projectsDir: "Local projects",
        shadersDir: "Local shaders",
        tempDir: "Local temp"
      },
      gpu: null,
      lastError: null
    },
    gpuInfo: {
      available: false,
      backendPlan: "placeholder",
      adapters: [],
      notes: ["Browser screenshot mode uses the same React viewer component."]
    },
    inspection: {
      input: sourcePath,
      filename: "Angel painted project",
      sourceSlots: 23,
      sourceColors: [
        "#F7E6DE",
        "#000000",
        "#AE835B",
        "#BA9594",
        "#E8DBB7",
        "#757575",
        "#8671CB",
        "#2060C0",
        "#F4A925",
        "#C8C8C8"
      ],
      thumbnail: null,
      previewMesh: null,
      previewNotice: "Screenshot mode does not package or publish the source 3MF/GLB.",
      metrics: {
        triangleCount: 5417070,
        vertexCount: 2705769,
        recommendedRenderMode: defaultAppSettings.viewerPerformance
      },
      import: null
    },
    sourcePath,
    referencePath,
    outputDir,
    conversionResult: {
      output: "Angel_FullSpectrum_preview.3mf",
      mode: defaultAppSettings.paletteMode,
      paletteSource: defaultAppSettings.paletteSource,
      sourceSlots: 23,
      realSlots: 6,
      outputSlots: 25,
      validation: "OK",
      quality: {
        qualityScore: 92,
        estimatedDeltaE: 3.4,
        confidenceScore: 74,
        contrastRetention: 81
      },
      colorValidation: {
        verified: true,
        maximumDeltaE: 0
      },
      printability: {
        complexity: "High",
        sliceRequiredForTimeAndUsage: true
      },
      recommendation: {
        summary: "Use the practical slider if you want fewer mixed logical slots."
      },
      preservation: {
        geometryPreserved: true,
        textureResourcesPreserved: true,
        paintRemapVerified: true
      }
    }
  };
}
