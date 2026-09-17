import type { ReactNode } from "react";
import { cn } from "@/lib/utils/cn";

/**
 * Section surface tones.
 *
 * `ink` and `lime` add the `on-dark` helper so nested text, links and focus
 * rings switch to their high-contrast variants without per-component overrides.
 */
type Tone = "paper" | "sunken" | "ink" | "lime";

const toneClasses: Record<Tone, string> = {
  paper: "",
  sunken: "section-paper-sunken",
  ink: "section-ink on-dark",
  lime: "section-lime",
};

/**
 * The standard page band: vertical rhythm plus a centred container.
 *
 * Every marketing section renders through this component so spacing comes from
 * `--section-y` in one place instead of ad-hoc margins per page.
 */
export function SectionShell({
  children,
  tone = "paper",
  tight = false,
  className,
  id,
  labelledBy,
}: {
  children: ReactNode;
  tone?: Tone;
  /** Uses the tighter vertical rhythm, for short bands such as proof strips. */
  tight?: boolean;
  className?: string;
  id?: string;
  /** Id of the heading that names this region, when the band has one. */
  labelledBy?: string;
}) {
  return (
    <section
      aria-labelledby={labelledBy}
      className={cn("section", tight && "section-tight", toneClasses[tone], className)}
      id={id}
    >
      <div className="container">{children}</div>
    </section>
  );
}