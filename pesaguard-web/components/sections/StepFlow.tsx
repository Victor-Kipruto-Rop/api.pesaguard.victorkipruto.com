import { cn } from "@/lib/utils/cn";
import type { StepBlock } from "@/types/content";

/**
 * Numbered process steps.
 *
 * Uses CSS counters, so the visible number comes from document order and cannot
 * disagree with the order a screen reader announces.
 */
export function StepFlow({
  steps,
  className,
  tone = "plain",
}: {
  steps: StepBlock[];
  className?: string;
  /** `line` renders the horizontal home-page variant. */
  tone?: "plain" | "line";
}) {
  if (steps.length === 0) {
    return null;
  }

  if (tone === "line") {
    return (
      <div className="flow-line">
        {steps.map((step) => (
          <div className="flow-step" key={step.step}>
            <small>
              {step.step} / {step.title}
            </small>
            <strong>{step.body}</strong>
            {step.detail ? <p>{step.detail}</p> : null}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={cn("step-flow", className)}>
      {steps.map((step) => (
        <article className="step" key={step.step}>
          <h3>{step.title}</h3>
          <p>{step.body}</p>
          {step.detail ? (
            <p className="step-detail">
              <span aria-hidden="true" className="badge badge-neutral">
                {step.step}
              </span>
              {step.detail}
            </p>
          ) : null}
        </article>
      ))}
    </div>
  );
}