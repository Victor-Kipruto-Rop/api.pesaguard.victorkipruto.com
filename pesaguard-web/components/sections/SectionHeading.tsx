import type { ReactNode } from "react";
import { cn } from "@/lib/utils/cn";

type Variant = "plain" | "centered" | "row";

/**
 * Eyebrow, heading and supporting line for a section.
 *
 * `variant="row"` places an action (usually a link or button) beside the
 * heading on wide screens; the heading text itself is never split across
 * elements, so screen readers and search engines read one clean string.
 */
export function SectionHeading({
  eyebrow,
  title,
  body,
  action,
  variant = "plain",
  as: Tag = "h2",
  id,
  className,
}: {
  eyebrow?: string;
  title: string;
  body?: string;
  /** Rendered beside the heading when `variant` is `row`. */
  action?: ReactNode;
  variant?: Variant;
  as?: "h2" | "h3";
  id?: string;
  className?: string;
}) {
  const heading = (
    <div className={cn("section-heading", variant === "centered" && "section-heading-centered", className)}>
      {eyebrow ? (
        <p className="eyebrow">
          {eyebrow}
          <span aria-hidden="true" className="eyebrow-rule" />
        </p>
      ) : null}
      <Tag id={id}>{title}</Tag>
      {body ? <p>{body}</p> : null}
    </div>
  );

  if (variant === "row") {
    return (
      <div className="section-heading-row">
        {heading}
        {action}
      </div>
    );
  }

  return heading;
}