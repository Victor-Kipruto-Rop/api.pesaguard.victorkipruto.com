import type { ReactNode } from "react";
import { Breadcrumbs, type Crumb } from "@/components/layout/Breadcrumbs";
import { AvailabilityBadge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils/cn";
import type { Availability } from "@/types/content";

type HeroStatus = {
  availability: Availability;
  label: string;
  note: string;
};

/**
 * Page opening band.
 *
 * `status` is optional and only used on pages that describe scoped
 * capabilities: it states how far along the work really is before the reader
 * reaches any other copy.
 */
export function PageHero({
  title,
  lede,
  label,
  trail,
  status,
  actions,
  children,
  tone = "paper",
  id,
}: {
  title: string;
  lede?: string;
  /** Small label above the heading, e.g. "Reconciliation". */
  label?: string;
  trail?: Crumb[];
  status?: HeroStatus;
  actions?: ReactNode;
  /** Extra content, such as a spec list or a proof row. */
  children?: ReactNode;
  tone?: "paper" | "ink";
  id?: string;
}) {
  return (
    <section className={cn("page-hero", tone === "ink" && "page-hero-ink on-dark")}>
      <div className="container page-hero-inner">
        {trail?.length ? <Breadcrumbs trail={trail} /> : null}
        {label ? (
          <p className="eyebrow">
            {label}
            <span aria-hidden="true" className="eyebrow-rule" />
          </p>
        ) : null}
        <h1 id={id}>{title}</h1>
        {lede ? <p className="lede">{lede}</p> : null}
        {status ? (
          <p className="status-updated">
            <AvailabilityBadge availability={status.availability} />
            <span>{status.label}</span>
            <span>{status.note}</span>
          </p>
        ) : null}
        {children}
        {actions ? <div className="actions">{actions}</div> : null}
      </div>
    </section>
  );
}