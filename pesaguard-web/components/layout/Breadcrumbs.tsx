import Link from "next/link";

/** One step in a breadcrumb trail. The last entry is the current page. */
export type Crumb = {
  label: string;
  href: string;
};

/**
 * Breadcrumb trail.
 *
 * The trail is passed in explicitly rather than derived from the URL, so a page
 * that is nested for routing reasons still shows the section a reader came
 * from. The final entry renders as plain text with `aria-current="page"`
 * because linking to the page you are already on is noise for keyboard and
 * screen-reader users.
 */
export function Breadcrumbs({ trail, className }: { trail: Crumb[]; className?: string }) {
  if (trail.length === 0) {
    return null;
  }

  const parents = trail.slice(0, -1);
  const current = trail[trail.length - 1];

  return (
    <nav aria-label="Breadcrumb" className={className ? `breadcrumbs ${className}` : "breadcrumbs"}>
      {parents.map((crumb) => (
        <span className="cluster" key={crumb.href}>
          <Link href={crumb.href}>{crumb.label}</Link>
          <span aria-hidden="true">/</span>
        </span>
      ))}
      <span aria-current="page">{current.label}</span>
    </nav>
  );
}