type ToolbarProps = {
  version: string;
  onOpenSource: () => void;
  onSelectProjectDirectory: () => void;
  onRefreshRuntime: () => void;
  onWriteLog: () => void;
};

export function Toolbar({ version, onOpenSource, onSelectProjectDirectory, onRefreshRuntime, onWriteLog }: ToolbarProps) {
  return (
    <header className="toolbar">
      <div className="brand-mark" aria-hidden="true">
        FS
      </div>
      <div>
        <h1>FullSpectrum Studio</h1>
        <p>Windows Tauri migration foundation · v{version}</p>
      </div>
      <div className="toolbar-actions">
        <button type="button" onClick={onOpenSource}>
          Open Source
        </button>
        <button type="button" onClick={onSelectProjectDirectory}>
          Open Project
        </button>
        <button type="button" onClick={onRefreshRuntime}>
          Runtime Paths
        </button>
        <button type="button" onClick={onWriteLog}>
          Write Test Log
        </button>
      </div>
    </header>
  );
}
