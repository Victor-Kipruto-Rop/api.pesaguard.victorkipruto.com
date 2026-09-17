import type { ReactNode } from "react";
import { cn } from "@/lib/utils/cn";

/**
 * Static code sample.
 *
 * Samples are rendered on the server with no copy button, so the page needs no
 * client JavaScript to show them. `label` names the file or endpoint being
 * shown; the language hint is plain text, not a claim about syntax support.
 */
export function CodeBlock({
  code,
  label,
  language,
  children,
  className,
}: {
  /** Raw text of the sample. Use `children` if the sample is pre-tokenised. */
  code?: string;
  label?: string;
  language?: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <figure className={cn("code-block", className)}>
      {label || language ? (
        <figcaption className="code-label">
          {label ? <span>{label}</span> : null}
          {language ? <span className="mono-label">{language}</span> : null}
        </figcaption>
      ) : null}
      <pre>
        <code>{children ?? code}</code>
      </pre>
    </figure>
  );
}