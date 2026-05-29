type StatusBarProps = {
  status: string;
  runtimeReady: boolean;
};

export function StatusBar({ status, runtimeReady }: StatusBarProps) {
  return (
    <footer className="status-bar">
      <span className={runtimeReady ? "dot ready" : "dot"} />
      <span>{status}</span>
      <span className="status-spacer" />
      <span>Windows desktop app · Tauri v2 · FullSpectrum engine bridge</span>
    </footer>
  );
}
