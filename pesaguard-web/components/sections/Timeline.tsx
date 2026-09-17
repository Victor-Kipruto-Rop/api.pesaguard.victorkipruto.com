import type { TimelineEntry } from "@/types/content";

const stateLabel: Record<NonNullable<TimelineEntry["state"]>, string> = {
  done: "Done",
  active: "In progress",
  todo: "Planned",
};

/**
 * Vertical timeline used for roadmaps and incident history.
 *
 * `state` drives both the marker colour and a text label, so the status of each
 * entry is never communicated by colour alone. Entries without a state are
 * treated as planned rather than silently rendered as done.
 */
export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  if (entries.length === 0) {
    return null;
  }

  return (
    <ol className="timeline">
      {entries.map((entry) => {
        const state = entry.state ?? "todo";
        return (
          <li className="timeline-item" data-state={state} key={entry.title}>
            <p className="timeline-when">
              <span>{entry.when}</span>
              <span className="badge badge-neutral">{stateLabel[state]}</span>
            </p>
            <h3>{entry.title}</h3>
            <p>{entry.body}</p>
          </li>
        );
      })}
    </ol>
  );
}