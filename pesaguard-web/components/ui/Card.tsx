import type { ReactNode } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils/cn";

/** Generic surface. `raised` lifts it off the page; `ghost` removes the border. */
export function Card({
  children,
  tone = "plain",
  className,
}: {
  children: ReactNode;
  tone?: "plain" | "raised" | "ink" | "lime" | "ghost" | "dark";
  className?: string;
}) {
  const toneClasses: Record<string, string> = {
    plain: "card",
    raised: "card panel-raised",
    ink: "card card-ink",
    lime: "card card-lime",
    ghost: "card card-ghost",
    dark: "card feature-card-dark",
  };

  return <article className={cn(toneClasses[tone], className)}>{children}</article>;
}

/** Card that links somewhere. The whole card is the click target. */
export function LinkCard({
  href,
  children,
  title,
  className,
}: {
  href: string;
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <Link className={cn("card card-interactive", className)} href={href}>
      {title ? <h3 className="card-title">{title}</h3> : null}
      {children}
    </Link>
  );
}

/** Responsive card container: 2, 3 or 4 columns on desktop. */
export function CardGrid({
  children,
  columns = 3,
  className,
}: {
  children: ReactNode;
  columns?: 2 | 3 | 4;
  className?: string;
}) {
  return <div className={cn("card-grid", `grid-${columns}`, className)}>{children}</div>;
}

/**
 * A card with a small index label, used for ordered capability lists.
 * Kept separate from `Card` because the index is decorative and must not be
 * announced as part of the heading.
 */
export function FeatureCard({
  index,
  title,
  children,
  icon,
  tone = "plain",
  footer,
}: {
  index?: string;
  title: string;
  children: ReactNode;
  icon?: ReactNode;
  tone?: "plain" | "ink";
  footer?: ReactNode;
}) {
  return (
    <article className={tone === "ink" ? "card card-ink" : "card"}>
      <div className="card-body">
        {icon ? <span className="card-icon">{icon}</span> : null}
        {index ? (
          <span aria-hidden="true" className="card-index">
            {index}
          </span>
        ) : null}
        <h3 className="card-title">{title}</h3>
        <div className="rich-text">{children}</div>
      </div>
      {footer ? <div className="panel-foot">{footer}</div> : null}
    </article>
  );
}

/** Neutral info panel used for asides such as "what we do not claim". */
export function Panel({
  title,
  children,
  tone = "plain",
  footer,
  className,
}: {
  title?: string;
  children: ReactNode;
  tone?: "plain" | "raised" | "ink";
  footer?: ReactNode;
  className?: string;
}) {
  const toneClasses: Record<string, string> = {
    plain: "panel",
    raised: "panel panel-raised",
    ink: "panel card-ink",
  };

  return (
    <section className={cn(toneClasses[tone], className)}>
      {title ? (
        <div className="panel-top">
          <h3>{title}</h3>
        </div>
      ) : null}
      <div className="rich-text">{children}</div>
      {footer ? <div className="panel-foot">{footer}</div> : null}
    </section>
  );
}

/** Square icon container with a tinted variant. */
export function IconBox({
  children,
  tone = "plain",
}: {
  children: ReactNode;
  tone?: "plain" | "amber" | "blue";
}) {
  const toneClasses: Record<string, string> = {
    plain: "icon-box",
    amber: "icon-box icon-box-amber",
    blue: "icon-box icon-box-blue",
  };

  return (
    <span aria-hidden="true" className={toneClasses[tone]}>
      {children}
    </span>
  );
}

/** Single figure with its label, used in stat bands. */
export function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div className="metric">
      <span className="metric-value">{value}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}
