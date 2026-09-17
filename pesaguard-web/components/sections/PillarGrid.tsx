import { cn } from "@/lib/utils/cn";
import type { PillarBlock } from "@/types/content";

/**
 * Numbered principles or architecture pillars.
 *
 * The index is rendered from content rather than a CSS counter because these
 * are referenced by name in prose ("principle 3"), so the visible number has to
 * survive being read out of order by a screen reader.
 */
export function PillarGrid({ pillars, className }: { pillars: PillarBlock[]; className?: string }) {
  if (pillars.length === 0) {
    return null;
  }

  return (
    <div className={cn("pillar-grid", className)}>
      {pillars.map((pillar) => (
        <article className="pillar" key={pillar.index}>
          <span aria-hidden="true" className="pillar-index">
            {pillar.index}
          </span>
          <h3>{pillar.title}</h3>
          <p>{pillar.body}</p>
        </article>
      ))}
    </div>
  );
}