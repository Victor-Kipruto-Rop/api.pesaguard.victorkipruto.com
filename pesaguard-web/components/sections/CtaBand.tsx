import { SectionShell } from "@/components/sections/SectionShell";
import { Button } from "@/components/ui/Button";
import type { CallToAction } from "@/types/content";

/**
 * Closing call to action.
 *
 * Rendered as a split panel rather than a full dark band so it can sit inside a
 * page that already ends on an ink surface. The secondary action is optional
 * and, like the primary, must point at a route that exists.
 */
export function CtaBand({ cta }: { cta: CallToAction }) {
  return (
    <SectionShell tone="paper">
      <div className="panel panel-split">
        {cta.eyebrow ? <p className="eyebrow">{cta.eyebrow}</p> : null}
        <h2>{cta.title}</h2>
        <p>{cta.body}</p>
        <div className="actions">
          <Button href={cta.primary.href} size="lg">
            {cta.primary.label}
          </Button>
          {cta.secondary ? (
            <Button href={cta.secondary.href} size="lg" variant="quiet">
              {cta.secondary.label}
            </Button>
          ) : null}
        </div>
      </div>
    </SectionShell>
  );
}