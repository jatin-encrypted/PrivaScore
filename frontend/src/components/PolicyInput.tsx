import { useId, useMemo } from "react";

import { copy } from "../lib/copy";
import { num, readingMinutes } from "../lib/format";
import { inputProblem, type Input } from "../lib/machine";
import { Button } from "./ui/Button";

/**
 * Screen A (section 7.4). The textarea is the hero: full content width, 2px ink border, square,
 * at least 50dvh tall. The Analyze button is disabled until the text is within the limits the
 * backend enforces, so a user never earns a 422 by pressing it.
 *
 * autocomplete is off and nothing is prefilled: the pasted text is never stored anywhere
 * (section 7.8).
 *
 * Not centred in its container: the saved-analyses gallery below it is wider, and the two
 * sections have to share a left edge. The reading measure is still capped (section 8.4).
 */
export function PolicyInput({
  input,
  limits,
  onChange,
  onSubmit,
}: {
  input: Input;
  limits: { minChars: number; maxChars: number };
  onChange: (patch: Partial<Input>) => void;
  onSubmit: () => void;
}) {
  const textId = useId();
  const companyId = useId();
  const scopeId = useId();
  const counterId = useId();
  const scopeHelpId = useId();

  const problem = useMemo(() => inputProblem(input.text, limits), [input.text, limits]);
  const empty = input.text.trim().length === 0;
  const minutes = useMemo(() => readingMinutes(input.text), [input.text]);

  const message =
    problem === "too_short" && !empty
      ? copy.input.tooShort(num(limits.minChars))
      : problem === "too_long"
        ? copy.input.tooLong(num(limits.maxChars))
        : null;

  return (
    <div className="max-w-[880px]">
      <h1 className="t-display">{copy.hero.headline}</h1>
      <p className="t-body mt-6 text-ink-2">{copy.hero.sub}</p>

      <div className="mt-12">
        <label className="t-small block pb-2" htmlFor={textId}>
          {copy.input.label}
        </label>
        <textarea
          id={textId}
          value={input.text}
          onChange={(e) => onChange({ text: e.target.value })}
          placeholder={copy.input.placeholder}
          spellCheck={false}
          autoComplete="off"
          aria-describedby={counterId}
          aria-invalid={message !== null}
          className={`t-body block max-w-none w-full resize-y bg-surface p-4 sm:p-5
            min-h-[50dvh] border-2 placeholder:text-ink-3
            ${message ? "border-signal" : "border-ink"}`}
        />

        {/* The counter is live but not announced on every keystroke: a screen reader user gets
            it on focus or on demand, not as a stream of interruptions. */}
        <div
          id={counterId}
          className="mt-2 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1"
        >
          <span className="t-small t-num text-ink-2">
            {empty ? " " : copy.input.counter(num(input.text.length), num(minutes))}
          </span>
          <span className="t-small t-num text-ink-3">{copy.input.limit(num(limits.maxChars))}</span>
        </div>

        {message ? (
          <p className="t-small mt-2 text-signal" role="status">
            {message}
          </p>
        ) : null}
      </div>

      <div className="mt-8 flex flex-col gap-6 sm:flex-row sm:items-start sm:gap-10">
        <div>
          <label className="t-small block pb-2" htmlFor={companyId}>
            {copy.input.company}
          </label>
          <input
            id={companyId}
            type="text"
            value={input.companyName}
            maxLength={120}
            autoComplete="off"
            onChange={(e) => onChange({ companyName: e.target.value })}
            className="t-body h-12 w-full border-2 border-ink bg-surface px-3 sm:w-[22rem]"
          />
        </div>

        <div className="sm:pt-8">
          <div className="flex items-start gap-3">
            <input
              id={scopeId}
              type="checkbox"
              checked={input.scope === "consumer"}
              aria-describedby={scopeHelpId}
              onChange={(e) => onChange({ scope: e.target.checked ? "consumer" : "all_users" })}
              className="mt-1 size-4 shrink-0 accent-[var(--ink)]"
            />
            <div>
              <label className="t-small text-ink" htmlFor={scopeId}>
                {copy.input.scope}
              </label>
              <p id={scopeHelpId} className="t-small max-w-[34ch] text-ink-3">
                {copy.input.scopeHelp}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-10">
        <Button onClick={onSubmit} disabled={problem !== null}>
          {copy.input.submit}
        </Button>
        {/* Section 9: the text IS sent to Gemini, and the UI says so plainly. */}
        <p className="t-small mt-4 max-w-[60ch] text-ink-3">{copy.input.privacyNote}</p>
      </div>
    </div>
  );
}
