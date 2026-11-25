import type { EvaluateResponse } from "../../api/client";
import { copy } from "../../lib/copy";
import { localDateTime, num } from "../../lib/format";
import { Banner } from "../ui/Banner";

/**
 * Section 7.4 C1. Title, meta line, then the banners in a fixed order: mock, saved analysis,
 * incomplete, then the backend's warnings. Every banner is a statement about how much the
 * result can be trusted, so none of them is dismissible.
 */
export function PolicySummary({ data }: { data: EvaluateResponse }) {
  const { policy, meta, scores, warnings, metrics } = data;
  const mock = warnings.find((w) => w.code === "MOCK_PROVIDER");
  const rest = warnings.filter((w) => w.code !== "MOCK_PROVIDER");

  return (
    <div>
      <h1 className="t-display">{policy.company_name ?? copy.results.untitled}</h1>

      <p className="t-small t-num mt-4 text-ink-2">
        {num(metrics.readability.words)} words · {num(metrics.readability.reading_minutes)} min read ·{" "}
        <span className="t-code">{meta.model}</span> · {localDateTime(meta.analysed_at)}
      </p>

      {(mock || !scores.complete || rest.length > 0) && (
        <div className="mt-8 space-y-4">
          {mock ? <Banner tone="signal" title={mock.message} /> : null}

          {!scores.complete ? (
            <Banner tone="signal" title={copy.results.incomplete(scores.rejected_flags)} />
          ) : null}

          {rest.map((w) => (
            <Banner key={w.code} title={w.message} />
          ))}
        </div>
      )}
    </div>
  );
}
