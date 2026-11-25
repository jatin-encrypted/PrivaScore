import type { ButtonHTMLAttributes } from "react";

/**
 * Section 8.5. Square, flat, 48px tall. Primary is an ink fill; secondary is a 2px ink border
 * that inverts on hover. No loading state: the whole view changes when an analysis starts.
 */
type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" };

const base =
  "h-12 px-6 transition-colors duration-[140ms] active:translate-y-px " +
  "disabled:cursor-not-allowed disabled:active:translate-y-0";

const variants = {
  primary: "bg-ink text-bg hover:bg-ink-2 disabled:bg-rule disabled:text-ink-3",
  secondary:
    "border-2 border-ink text-ink hover:bg-ink hover:text-bg " +
    "disabled:border-rule disabled:text-ink-3 disabled:hover:bg-transparent disabled:hover:text-ink-3",
} as const;

export function Button({ variant = "primary", className = "", ...rest }: Props) {
  return (
    <button
      type="button"
      className={`${base} ${variants[variant]} ${className}`}
      style={{ fontStretch: "112%", fontWeight: 700 }}
      {...rest}
    />
  );
}
