import type { AppSettings, ProjectInspection, ProjectMetadata, RuntimeStatus } from "../types/core";
import type { RuntimePathsResponse } from "../types/runtime";

type ProjectSidebarProps = {
  runtime: RuntimePathsResponse | null;
  runtimeStatus: RuntimeStatus;
  settings: AppSettings;
  metadata: ProjectMetadata | null;
  inspection: ProjectInspection | null;
  selectedDirectory: string | null;
};

export function ProjectSidebar({ runtime, runtimeStatus, settings, metadata, inspection, selectedDirectory }: ProjectSidebarProps) {
  return (
    <aside className="sidebar">
      <nav className="panel navigation-panel" aria-label="Workspace navigation">
        <h2>Workspace</h2>
        <a className="nav-item active" href="#renderer">Renderer</a>
        <a className="nav-item" href="#palette-engine">Palette Engine</a>
        <a className="nav-item" href="#assets">Assets</a>
        <a className="nav-item" href="#runtime">Runtime</a>
        <a className="nav-item" href="#logs">Logs</a>
      </nav>

      <section className="panel" id="project">
        <h2>Project</h2>
        {metadata ? (
          <dl className="metadata-list">
            <dt>Name</dt>
            <dd>{metadata.name ?? "No project selected"}</dd>
            <dt>Type</dt>
            <dd>{metadata.kind}</dd>
            <dt>Extension</dt>
            <dd>{metadata.extension ?? "none"}</dd>
            <dt>Supported</dt>
            <dd>{metadata.supportedInput ? "Yes" : "Not yet"}</dd>
            <dt>Files</dt>
            <dd>
              {metadata.fileCount} total · {metadata.supportedFileCount} supported
            </dd>
            <dt>Assets</dt>
            <dd>{metadata.assets.length} listed</dd>
          </dl>
        ) : (
          <p className="muted">No project metadata loaded yet.</p>
        )}
      </section>

      <section className="panel">
        <h2>Source Inspection</h2>
        {inspection ? (
          <dl className="metadata-list compact">
            <dt>Name</dt>
            <dd>{inspection.filename}</dd>
            <dt>Slots</dt>
            <dd>{inspection.sourceSlots}</dd>
            <dt>Colors</dt>
            <dd>{inspection.sourceColors.length}</dd>
            <dt>Preview</dt>
            <dd>{inspection.thumbnail ? "Plate image loaded" : inspection.previewMesh ? "Mesh ready" : "Metadata loaded"}</dd>
          </dl>
        ) : (
          <p className="muted">Open a source file to inspect the real engine metadata.</p>
        )}
      </section>

      <section className="panel" id="runtime">
        <h2>Runtime</h2>
        {runtime ? (
          <dl className="metadata-list compact">
            <dt>Status</dt>
            <dd>{runtimeStatus.ready ? "Ready" : "Not ready"}</dd>
            <dt>App Data</dt>
            <dd>{runtime.paths.appDataDir}</dd>
            <dt>Cache</dt>
            <dd>{runtime.paths.cacheDir}</dd>
            <dt>Projects</dt>
            <dd>{runtime.paths.projectsDir}</dd>
            <dt>Shaders</dt>
            <dd>{runtime.paths.shadersDir}</dd>
          </dl>
        ) : (
          <p className="muted">Runtime paths have not been prepared.</p>
        )}
      </section>

      <section className="panel">
        <h2>Settings</h2>
        <dl className="metadata-list compact">
          <dt>Palette</dt>
          <dd>{settings.paletteMode}</dd>
          <dt>Source</dt>
          <dd>{settings.paletteSource}</dd>
          <dt>Slots</dt>
          <dd>{settings.realSlots}</dd>
          <dt>Viewer</dt>
          <dd>{settings.viewerPerformance}</dd>
        </dl>
      </section>

      <section className="panel">
        <h2>Selected Folder</h2>
        <p className="path-value">{selectedDirectory ?? "No folder selected."}</p>
        <p className="muted">Open Folder is for workspace browsing. Open Source is the converter entry point.</p>
      </section>

      <section className="panel">
        <h2>Assets</h2>
        {metadata?.assets.length ? (
          <div className="asset-list">
            {metadata.assets.slice(0, 8).map((asset) => (
              <div className="asset-row" key={asset.path}>
                <strong>{asset.name}</strong>
                <span>{asset.kind} · {asset.extension ?? "no extension"}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">Open a project folder to list supported assets.</p>
        )}
      </section>
    </aside>
  );
}
