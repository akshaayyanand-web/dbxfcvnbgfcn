import { Link } from "react-router-dom";
import { ago, date } from "../lib/format";
import type { ActivityEvent } from "../types/api";

const DOT: Record<string, string> = {
  analysis_completed: "ok", analysis_failed: "bad", analysis_cancelled: "", analysis_started: "info",
  prediction: "lime", report: "info", experiment_created: "", dataset_import: "warn",
};

export function ActivityTimeline({ events, empty = "No activity recorded yet." }: { events: ActivityEvent[]; empty?: string }) {
  if (!events.length) return <p className="body-s subtle">{empty}</p>;
  return (
    <ol className="timeline">
      {events.map((e, i) => {
        const href = e.report_id ? "/reports" : e.prediction_id ? "/prediction" : e.experiment_id ? `/experiments/${e.experiment_id}` : e.kind === "dataset_import" ? "/datasets" : null;
        return (
          <li key={`${e.time}-${i}`}>
            <span className={`dot ${DOT[e.kind] ?? ""}`} aria-hidden />
            <span className="body-s">{href ? <Link to={href}>{e.title}</Link> : e.title}</span>
            <time className="when" dateTime={e.time} title={date(e.time)}>{ago(e.time)}</time>
          </li>
        );
      })}
    </ol>
  );
}
