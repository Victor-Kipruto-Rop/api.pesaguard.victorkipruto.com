import type { ReactNode } from "react";
import { cn } from "@/lib/utils/cn";

/**
 * Disclosure built on `details`/`summary` so it works without JavaScript and is
 * reachable by keyboard and screen readers by default.
 */
export function AccordionItem({
  title,
  children,
  defaultOpen = false,
  className,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}) {
  return (
    <details className={cn("accordion-item", className)} open={defaultOpen}>
      <summary>{title}</summary>
      <div className="accordion-panel">{children}</div>
    </details>
  );
}

/** A stack of disclosures rendered as one `.accordion` block. */
export function AccordionGroup({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("accordion", className)}>{children}</div>;
}
