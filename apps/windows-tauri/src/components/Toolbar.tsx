type ToolbarProps = {
  version: string;
  onOpenSource: () => void;
  onConvert: () => void;
  onSelectProjectDirectory: () => void;
  onRefreshRuntime: () => void;
  converting: boolean;
  canConvert: boolean;
};

export function Toolbar({
  version,
  onOpenSource,
  onConvert,
  onSelectProjectDirectory,
  onRefreshRuntime,
  converting,
  canConvert
}: ToolbarProps) {
  return (
    <header className="toolbar">
      <div className="brand-mark" aria-hidden="true">
        FS
      </div>
      <div>
        <h1>FullSpectrum Studio</h1>
        <p>Windows desktop preview · real FullSpectrum engine · v{version}</p>
      </div>
      <div className="toolbar-actions">
        <button type="button" onClick={onOpenSource}>
          Open Source
        </button>
        <button className="primary-action" disabled={!canConvert || converting} type="button" onClick={onConvert}>
          {converting ? "Converting..." : "Convert"}
        </button>
        <button type="button" onClick={onSelectProjectDirectory}>
          Open Folder
        </button>
        <button type="button" onClick={onRefreshRuntime}>
          Runtime
        </button>
      </div>
    </header>
  );
}
