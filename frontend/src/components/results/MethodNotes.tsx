import { copy } from "../../lib/copy";

/**
 * Section 7.4 C8 and the copy deck's "How to read these results". Every claim here traces to
 * the pipeline or the evaluation; nothing is softened and nothing is added (section 9).
 */
export function MethodNotes() {
  return (
    <section aria-labelledby="how-to-read-heading" id="how-to-read">
      <h2 className="t-h2 border-t-2 border-rule-strong pt-8" id="how-to-read-heading">
        {copy.howToRead.heading}
      </h2>
      <ol className="mt-6 max-w-[68ch] list-decimal space-y-3 pl-5">
        {copy.howToRead.points.map((point) => (
          <li key={point} className="t-body text-ink-2">
            {point}
          </li>
        ))}
      </ol>
    </section>
  );
}
