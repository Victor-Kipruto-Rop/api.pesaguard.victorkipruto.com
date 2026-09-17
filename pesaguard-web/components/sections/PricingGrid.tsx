import { Check } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils/cn";
import type { PlanBlock } from "@/types/content";

/**
 * Commercial plans.
 *
 * Prices are strings because some tiers are quoted per merchant rather than
 * listed. Anything described in `features` has to be something we can actually
 * deliver today, with the availability caveat stated in `note` where it applies.
 */
export function PricingGrid({ plans }: { plans: PlanBlock[] }) {
  if (plans.length === 0) {
    return null;
  }

  return (
    <div className="pricing-grid">
      {plans.map((plan) => (
        <article className={cn("plan", plan.featured && "plan-featured")} key={plan.name}>
          <div className="plan-head">
            <h3>{plan.name}</h3>
            <p>{plan.summary}</p>
          </div>
          <p className="plan-price">
            <strong>{plan.price}</strong>
            {plan.cadence ? <span>{plan.cadence}</span> : null}
          </p>
          <ul className="check-list plan-features">
            {plan.features.map((feature) => (
              <li key={feature}>
                <Check aria-hidden="true" size={16} />
                {feature}
              </li>
            ))}
          </ul>
          <Button href={plan.cta.href} variant={plan.featured ? "primary" : "quiet"}>
            {plan.cta.label}
          </Button>
          {plan.note ? <p className="plan-note">{plan.note}</p> : null}
        </article>
      ))}
    </div>
  );
}