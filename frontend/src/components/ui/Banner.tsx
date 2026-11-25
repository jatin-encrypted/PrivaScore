import type { ReactNode } from "react";

/**
 * Section 8.5: a full-width row with a 2px top rule and a bold first sentence. No coloured
 * left borders, no icons in circles. `tone="signal"` is only for the incomplete and mock
 * banners, which are the two cases where the result itself is qualified.
 */
export function Banner({
  title,
  children,
  tone = "ink",
}: {
  title: string;
  children?: ReactNode;
  tone?: "ink" | "signal";
}) {
  return (
    <div className={`border-t-2 pt-3 ${tone === "signal" ? "border-signal" : "border-ink"}`}>
      <p className="t-body">
        <strong style={{ fontWeight: 700 }}>{title}</strong>
        {children ? <> {children}</> : null}
      </p>
    </div>
  );
}
