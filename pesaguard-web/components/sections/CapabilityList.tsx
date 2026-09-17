import Link from "next/link";
import { ArrowUpRight, Check } from "lucide-react";
import { AvailabilityBadge } from "@/components/ui/Badge";
import type { CapabilityBlock } from "@/types/content";

/**
 * Alphabetical-by-decision list of capabilities.
 *
 * Each row states what the capability does and, where relevant, how far along
 * it is. The availability badge is rendered next to the detail rather than
 * hidden in a tooltip so a reader never has to go looking for the caveat.
 */
export function CapabilityList({ items }: { items: CapabilityBlock[] }) {
  return (
    <div className="capability-list">
      {items.map((item) => (
        <article className="capability-row" key={item.title}>
          <h3>
            {item.index ? <span>{item.index}</span> : null}
            {item.title}
          </h3>
          <div>
            <p>{item.body}</p>
            {item.items?.length ? (
              <ul className="check-list">
                {item.items.map((entry) => (
                  <li key={entry}>
                    <Check aria-hidden="true" size={16} />
                    {entry}
                  </li>
                ))}
              </ul>
            ) : null}
            {item.availability ? (
              <p className="mt-3">
                <AvailabilityBadge availability={item.availability} showNote />
              </p>
            ) : null}
            {item.href && item.linkLabel ? (
              <p className="mt-2">
                <Link className="text-link" href={item.href}>
                  {item.linkLabel}
                  <ArrowUpRight aria-hidden="true" size={16} />
                </Link>
              </p>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}