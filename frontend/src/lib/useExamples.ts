import { useEffect, useState } from "react";

import { type ExampleList, getExamples } from "../api/client";

/**
 * The saved gold-set analyses, fetched once on mount.
 *
 * "unavailable" is a normal outcome, not an error screen: a deployment without gold_set/ and
 * runs/ still analyses pasted text perfectly well, so the gallery simply does not render.
 */
export type ExamplesState =
  | { status: "loading" }
  | { status: "ready"; data: ExampleList }
  | { status: "unavailable" };

export function useExamples(): ExamplesState {
  const [state, setState] = useState<ExamplesState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    getExamples(controller.signal)
      .then((data) => {
        // The gallery is optional, so a response that is not the shape we expect degrades to
        // "no gallery" rather than throwing inside render. A proxy that answers every path with
        // the same JSON is the realistic way this happens.
        if (!Array.isArray(data?.examples) || data.examples.length === 0) {
          setState({ status: "unavailable" });
          return;
        }
        setState({ status: "ready", data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: "unavailable" });
      });
    return () => controller.abort();
  }, []);

  return state;
}
