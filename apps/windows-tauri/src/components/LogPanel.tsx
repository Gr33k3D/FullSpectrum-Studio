import type { LogEntry } from "../types/runtime";

type LogPanelProps = {
  logs: LogEntry[];
};

export function LogPanel({ logs }: LogPanelProps) {
  return (
    <section className="log-panel" id="logs">
      <div className="panel-title-row">
        <h2>Runtime Log</h2>
        <span>{logs.length} entries</span>
      </div>
      <pre>
        {logs.length
          ? logs.map((entry) => `${entry.timestamp ?? ""} [${entry.level.toUpperCase()}] ${entry.message}`).join("\n")
          : "No logs yet."}
      </pre>
    </section>
  );
}
