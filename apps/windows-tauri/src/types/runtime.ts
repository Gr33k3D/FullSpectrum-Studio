export type RuntimePaths = {
  appDataDir: string;
  cacheDir: string;
  logsDir: string;
  projectsDir: string;
  shadersDir: string;
  tempDir: string;
};

export type RuntimePathsResponse = {
  paths: RuntimePaths;
  created: string[];
};

export type GpuAdapterInfo = {
  name: string;
  vendor: string;
  backend: string;
  deviceType: string;
  driver: string | null;
};

export type GpuInfo = {
  available: boolean;
  backendPlan: "placeholder" | "wgpu";
  adapters: GpuAdapterInfo[];
  notes: string[];
};

export type LogLevel = "debug" | "info" | "warn" | "error";

export type LogWriteResult = {
  path: string;
  bytesWritten: number;
};

export type LogEntry = {
  timestamp: string | null;
  level: LogLevel;
  message: string;
  raw: string;
};
