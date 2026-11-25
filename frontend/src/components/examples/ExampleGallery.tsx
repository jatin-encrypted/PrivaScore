import type { ExampleList } from "../../api/client";
import { copy } from "../../lib/copy";
import { localDate, num } from "../../lib/format";
import { ScoreMap } from "./ScoreMap";

/**
 * The front door to a real result. Fifteen saved analyses, each one click away and instant,
 * so the app shows what it does before asking anyone to paste 1,000 characters of legal text.
 *
 * Deliberately not a ranking (section 9): there is no combined score to sort by, the order is
 * the gold set's own, and the copy says so. The two scores sit in separate columns and are
 * never added, averaged or turned into a band.
 *
 * Each row is a <button>, not a link: nothing here navigates, and the policy id never goes in
 * the URL. The rows are a real <table> so the numbers are announced with their column.
 */
export function ExampleGallery({
  data,
  onOpen,
  busy,
}: {
  data: ExampleList;
  onOpen: (policyId: string) => void;
  busy: boolean;
}) {
  return (
    <section aria-labelledby="examples-heading" className="border-t-2 border-ink pt-8">
      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_auto] lg:gap-12">
        <div className="min-w-0">
          <h2 id="examples-heading" className="t-h2">
            {copy.examples.heading}
          </h2>
          <p className="t-body mt-3 text-ink-2">{copy.examples.sub}</p>
          <p className="t-small mt-2 text-ink-3">
            {copy.examples.provenance(data.model, localDate(data.analysed_at))}{" "}
            {copy.examples.orderNote}
          </p>

          <table className="mt-6 w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-ink">
                <th scope="col" className="t-small py-2 pr-3 font-medium text-ink-3">
                  {copy.examples.columnPolicy}
                </th>
                <th scope="col" className="t-small w-16 py-2 pr-3 text-right font-medium text-ink-3">
                  {copy.examples.columnRisk}
                </th>
                <th scope="col" className="t-small w-20 py-2 pr-3 text-right font-medium text-ink-3">
                  {copy.examples.columnQuality}
                </th>
                <th
                  scope="col"
                  className="t-small hidden w-28 py-2 text-right font-medium text-ink-3 sm:table-cell"
                >
                  {copy.examples.columnLength}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.examples.map((e) => (
                <tr key={e.policy_id} className="border-b border-rule">
                  <th scope="row" className="py-0 pr-3 font-normal">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onOpen(e.policy_id)}
                      aria-label={copy.examples.open(e.company_name)}
                      className="t-row-title -mx-2 block w-full px-2 py-3 text-left
                        hover:bg-mark disabled:opacity-50"
                    >
                      {e.company_name}
                      {!e.complete ? (
                        <span className="t-code ml-2 align-middle text-signal">
                          {copy.examples.incomplete}
                        </span>
                      ) : null}
                    </button>
                  </th>
                  <td className="t-num t-body py-3 pr-3 text-right tabular-nums">
                    {e.risk_index_display}
                  </td>
                  <td className="t-num t-body py-3 pr-3 text-right tabular-nums">
                    {e.disclosure_quality_display}
                  </td>
                  <td className="t-num t-small hidden py-3 text-right text-ink-3 sm:table-cell">
                    {num(e.chars)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-10 lg:mt-0 lg:w-[460px]">
          <h3 className="t-h3">{copy.map.heading}</h3>
          <p className="t-small mt-2 max-w-[46ch] text-ink-3">{copy.map.sub}</p>
          <div className="mt-4">
            <ScoreMap examples={data.examples} />
          </div>
        </div>
      </div>
    </section>
  );
}
