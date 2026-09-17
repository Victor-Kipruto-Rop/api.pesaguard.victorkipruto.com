import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Icon } from "@/components/sections/Icon";
import { cn } from "@/lib/utils/cn";
import type { FeatureBlock } from "@/types/content";

/**
 * Responsive grid of feature cards.
 *
 * Cards always render real copy; nothing here is a placeholder. A card only
 * links somewhere when the destination exists, so the grid cannot produce a
 * dead affordance.
 */
export function FeatureGrid({ items, className }: { items: FeatureBlock[]; className?: string }) {
  return (
    <div className={cn("feature-grid", className)}>
      {items.map((item) => (
        <article
          className={cn("feature-card", item.tone === "dark" && "feature-card-dark")}
          key={item.title}
        >
          {item.iconKey ? <Icon name={item.iconKey} /> : null}
          {item.index ? (
            <span aria-hidden="true" className="card-index">
              {item.index}
            </span>
          ) : null}
          <h3>{item.title}</h3>
          <p>{item.body}</p>
          {item.href && item.linkLabel ? (
            <Link href={item.href}>
              {item.linkLabel}
              <ArrowUpRight aria-hidden="true" size={16} />
            </Link>
          ) : null}
        </article>
      ))}
    </div>
  );
}