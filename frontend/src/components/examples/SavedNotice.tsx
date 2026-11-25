import type { EvaluateResponse, ExampleList } from "../../api/client";
import { copy } from "../../lib/copy";
import { localDate } from "../../lib/format";
import { Banner } from "../ui/Banner";

/**
 * Shown above a saved analysis. Section 9 is about not claiming more than the pipeline
 * supports, and a saved result quietly presented as a fresh one is exactly that kind of
 * overclaim: it was produced by a named model on a past date, possibly not the model this
 * server is running now, and the policy may have changed since. So the banner says all of it.
 */
export function SavedNotice({ data, run }: { data: EvaluateResponse; run: ExampleList | null }) {
  const company = data.policy.company_name ?? copy.examples.savedBadge;
  // The run metadata is the authority on when and with what. If the list request failed after
  // the example itself loaded, the response's own meta carries the same two facts.
  const model = run?.model ?? data.meta.model;
  const when = localDate(run?.analysed_at ?? data.meta.analysed_at);

  return <Banner title={copy.examples.savedBadge}>{copy.examples.savedBanner(company, model, when)}</Banner>;
}
