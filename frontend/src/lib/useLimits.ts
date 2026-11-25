import { useEffect, useState } from "react";

import { getMeta } from "../api/client";

/**
 * The character limits are the backend's (PRIVASCORE_MIN_CHARS / MAX_CHARS), so the UI reads
 * them from /meta instead of keeping a second copy that can drift. The documented defaults are
 * used until the response arrives, and kept if /meta is unreachable: the limits only decide
 * whether a button is enabled, and the backend enforces them regardless.
 */
export const DEFAULT_LIMITS = { minChars: 1000, maxChars: 200_000 } as const;

export type Limits = { minChars: number; maxChars: number };

export function useLimits(): Limits {
  const [limits, setLimits] = useState<Limits>(DEFAULT_LIMITS);

  useEffect(() => {
    const controller = new AbortController();
    getMeta(controller.signal)
      .then((m) => setLimits({ minChars: m.limits.min_chars, maxChars: m.limits.max_chars }))
      .catch(() => {
        /* keep the defaults: the backend is the real gate */
      });
    return () => controller.abort();
  }, []);

  return limits;
}
