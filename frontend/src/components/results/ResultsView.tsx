import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { X } from "@phosphor-icons/react";

import type { EvaluateResponse } from "../../api/client";
import { copy } from "../../lib/copy";
import { Button } from "../ui/Button";
import { CategoryProfile } from "./CategoryProfile";
import { FlagGroups } from "./FlagGroups";
import { MethodNotes } from "./MethodNotes";
import { PolicySummary } from "./PolicySummary";
import { ReadingPanel } from "./ReadingPanel";
import { ScorePair } from "./ScorePair";
import { SourceDocument } from "./SourceDocument";

/**
 * Section 7.4 C. Two columns from lg: results on the left, the source document on the right,
 * sticky with its own scroll. Below lg the source document is a real <dialog> opened from any
 * "Show in policy" link.
 *
 * `text` is the exact normalised string that was sent to the backend, because every offset in
 * the response indexes into it.
 */
export function ResultsView({
  data,
  text,
  onReset,
  notice,
  footer,
  resetLabel,
}: {
  data: EvaluateResponse;
  text: string;
  onReset: () => void;
  /** Rendered above the summary. Used for the saved-analysis provenance banner. */
  notice?: ReactNode;
  /** Rendered under the action row. Used for the score map on a saved analysis. */
  footer?: ReactNode;
  resetLabel?: string;
}) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const pendingTarget = useRef<string | null>(null);

  /** The signature interaction: scroll the marked span into view and flash it once. */
  const reveal = useCallback((sentenceId: string) => {
    const el = document.getElementById(`ev-${sentenceId}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.focus({ preventScroll: true });
    el.dataset.active = "true";
    // The flash is a one-off cue, not a persistent state, so it clears itself.
    window.setTimeout(() => delete el.dataset.active, 1200);
  }, []);

  const showInPolicy = useCallback(
    (sentenceId: string) => {
      // Below lg the panel is not mounted in the flow, so open the sheet first and reveal once
      // the dialog's content exists.
      if (window.matchMedia("(min-width: 1024px)").matches) {
        reveal(sentenceId);
        return;
      }
      pendingTarget.current = sentenceId;
      setSheetOpen(true);
    },
    [reveal],
  );

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (sheetOpen && !dialog.open) {
      dialog.showModal();                       // a real <dialog>: focus trap and Esc for free
      if (pendingTarget.current) {
        reveal(pendingTarget.current);
        pendingTarget.current = null;
      }
    } else if (!sheetOpen && dialog.open) {
      dialog.close();
    }
  }, [sheetOpen, reveal]);

  const download = useCallback(() => {
    // Built in the browser from the response, with nothing added to it. For a LIVE result that
    // means the pasted text is absent, because `document.text` is null in live mode and nothing
    // here puts it back (section 7.8). A saved example does carry its text, which is a published
    // policy from the gold set, not anything the user typed.
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `privascore-${(data.policy.company_name ?? "policy").toLowerCase().replace(/\W+/g, "-")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [data]);

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
      <div className="min-w-0 space-y-16 lg:space-y-24">
        <div className="space-y-16">
          {notice ? <div>{notice}</div> : null}
          <PolicySummary data={data} />
          <ScorePair scores={data.scores} />
        </div>

        <FlagGroups flags={data.flags} onShowInPolicy={showInPolicy} />
        <CategoryProfile metrics={data.metrics} />
        <ReadingPanel metrics={data.metrics} />
        <MethodNotes />

        <div className="flex flex-wrap gap-4 border-t border-rule pt-8">
          <Button onClick={onReset}>{resetLabel ?? copy.results.analyzeAnother}</Button>
          <Button variant="secondary" onClick={download}>
            {copy.results.downloadJson}
          </Button>
        </div>

        {footer ? <div>{footer}</div> : null}
      </div>

      {/* Desktop: sticky panel with its own scroll. */}
      <div className="hidden min-w-0 lg:block">
        <div className="sticky top-6 overflow-y-auto" style={{ maxHeight: "calc(100dvh - 3rem)" }}>
          <SourceDocument data={data} text={text} />
        </div>
      </div>

      {/* Mobile and tablet: the same panel as a modal sheet. */}
      <dialog
        ref={dialogRef}
        onClose={() => setSheetOpen(false)}
        className="m-0 h-dvh max-h-none w-screen max-w-none bg-bg p-4 text-ink lg:hidden"
      >
        <div className="mb-4 flex justify-end">
          <button type="button" onClick={() => setSheetOpen(false)} className="p-2">
            <X aria-hidden="true" size={20} />
            <span className="sr-only">Close</span>
          </button>
        </div>
        {sheetOpen ? <SourceDocument data={data} text={text} /> : null}
      </dialog>
    </div>
  );
}
