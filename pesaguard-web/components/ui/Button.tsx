import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils/cn";

type Variant = "primary" | "lime" | "quiet" | "ghost-light";
type Size = "sm" | "md" | "lg";

const variantClasses: Record<Variant, string> = {
  primary: "button button-primary",
  lime: "button button-lime",
  quiet: "button button-quiet",
  "ghost-light": "button button-ghost-light",
};

const sizeClasses: Record<Size, string> = {
  sm: "button-sm",
  md: "",
  lg: "button-lg",
};

type ButtonProps = {
  children: ReactNode;
  /** When present the button renders as a `next/link` anchor. */
  href?: string;
  variant?: Variant;
  size?: Size;
  block?: boolean;
  type?: "button" | "submit";
  className?: string;
  /** Rendered after the label, e.g. a lucide arrow icon. */
  trailing?: ReactNode;
};

/**
 * The single button style for the site.
 *
 * `variant="ghost-light"` is intended for dark surfaces, where `quiet` would not
 * have enough contrast.
 */
export function Button({
  children,
  href,
  variant = "primary",
  size = "md",
  block = false,
  type = "button",
  className,
  trailing,
}: ButtonProps) {
  const classes = cn(variantClasses[variant], sizeClasses[size], block && "button-block", className);

  if (href) {
    return (
      <Link className={classes} href={href}>
        {children}
        {trailing}
      </Link>
    );
  }

  return (
    <button className={classes} type={type}>
      {children}
      {trailing}
    </button>
  );
}

/** Inline link with an arrow affordance, styled by `.text-link`. */
export function TextLink({
  href,
  children,
  trailing,
  className,
}: {
  href: string;
  children: ReactNode;
  trailing?: ReactNode;
  className?: string;
}) {
  return (
    <Link className={cn("text-link", className)} href={href}>
      {children}
      {trailing}
    </Link>
  );
}
