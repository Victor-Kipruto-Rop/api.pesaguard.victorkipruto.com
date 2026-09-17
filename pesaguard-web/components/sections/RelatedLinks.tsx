import { LinkCard } from "@/components/ui/Card";
import type { RelatedLink } from "@/types/content";

/**
 * Footer links under a page body.
 *
 * Only routes that exist are listed; the caller passes the set of links that
 * apply to the page, so a reader is never sent to a 404 from a "read next"
 * block.
 */
export function RelatedLinks({ links, columns = 3 }: { links: RelatedLink[]; columns?: 2 | 3 }) {
  if (links.length === 0) {
    return null;
  }

  return (
    <div className={`card-grid grid-${columns}`}>
      {links.map((link) => (
        <LinkCard href={link.href} key={link.href} title={link.label}>
          <p className="small muted">{link.description}</p>
        </LinkCard>
      ))}
    </div>
  );
}