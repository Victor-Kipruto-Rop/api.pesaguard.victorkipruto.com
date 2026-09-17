import Link from "next/link";
import { AvailabilityBadge } from "@/components/ui/Badge";
import type { IntegrationSummary } from "@/types/content";

/**
 * Grid of payment rails and channels.
 *
 * Every card carries its availability badge and the evidence behind the claim,
 * so a reader can see that Airtel Money and bank rails are not live yet without
 * having to compare the page against a changelog.
 */
export function IntegrationGrid({ items }: { items: IntegrationSummary[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="integration-grid">
      {items.map((item) => (
        <article className="integration-card" key={item.name}>
          <div className="integration-top">
            <h3>{item.name}</h3>
            <AvailabilityBadge availability={item.availability} />
          </div>
          <p>{item.summary}</p>
          <div className="integration-meta">
            <span className="small muted">{item.evidence}</span>
            <Link className="text-link" href={item.href}>
              Details
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}