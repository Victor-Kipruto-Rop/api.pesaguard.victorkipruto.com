import { Badge, StatusDot } from "@/components/ui/Badge";
import type { StatusSnapshot } from "@/types/status";

/**
 * Status board.
 *
 * The badge above the board distinguishes a live probe from a configured-but-
 * unreachable backend, and `snapshot.live` is false whenever we could not reach
 * the API. Nothing here reports "operational" on the marketing site unless the
 * backend actually answered.
 */
export function StatusBoard({ snapshot }: { snapshot: StatusSnapshot }) {
  return (
    <div>
      <p className="status-updated">
        <Badge dot={snapshot.live} tone={snapshot.live ? "live" : "neutral"}>
          {snapshot.live ? "Live probe" : "No live probe"}
        </Badge>
        <span>{snapshot.headline}</span>
        <span>{snapshot.note}</span>
        {snapshot.checkedAt ? <span>Checked {snapshot.checkedAt}</span> : null}
      </p>

      <div className="status-board">
        {snapshot.services.map((service) => (
          <div className="status-row" key={service.name}>
            <strong>{service.name}</strong>
            <span>{service.detail}</span>
            <StatusDot state={service.state} />
          </div>
        ))}
      </div>
    </div>
  );
}