import { useCallback, useReducer, useState } from "react";

import { ApiError, evaluate, getExample, normaliseText } from "./api/client";
import { ExampleGallery } from "./components/examples/ExampleGallery";
import { SavedNotice } from "./components/examples/SavedNotice";
import { ScoreMap } from "./components/examples/ScoreMap";
import { AnalysisProgress } from "./components/AnalysisProgress";
import { ErrorPanel } from "./components/ErrorPanel";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { PolicyInput } from "./components/PolicyInput";
import { ResultsView } from "./components/results/ResultsView";
import { copy } from "./lib/copy";
import { initialState, reducer } from "./lib/machine";
import { useExamples } from "./lib/useExamples";
import { useLimits } from "./lib/useLimits";

/**
 * The shell: header, one <main> per state (section 7.3), footer.
 *
 * There is exactly one aria-live region, and it announces three things once each: the analysis
 * started, it finished, or it failed. The elapsed timer is never announced (section 7.4 B).
 */
export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const limits = useLimits();
  const examples = useExamples();
  // Local, not in the machine: this only disables the gallery's buttons for the few hundred
  // milliseconds of a cached GET. It is not one of the app's four states.
  const [opening, setOpening] = useState(false);

  const start = useCallback(
    (type: "submit" | "retry") => {
      const controller = new AbortController();
      dispatch({ type, startedAt: Date.now(), controller });
      const { text, companyName, scope } = state.input;
      evaluate({ text, companyName, scope }, controller.signal)
        .then((data) => dispatch({ type: "succeeded", data }))
        .catch((e: unknown) =>
          dispatch({ type: "failed", error: e instanceof ApiError ? e : new ApiError("INTERNAL") }),
        );
    },
    [state.input],
  );

  const openExample = useCallback((policyId: string) => {
    setOpening(true);
    getExample(policyId)
      .then((data) => dispatch({ type: "openedExample", data }))
      .catch((e: unknown) =>
        dispatch({ type: "failed", error: e instanceof ApiError ? e : new ApiError("INTERNAL") }),
      )
      .finally(() => setOpening(false));
  }, []);

  const exampleList = examples.status === "ready" ? examples.data : null;

  // Derived, not stored: the live region announces whenever this text changes, and there is no
  // effect to keep in sync. Errors are deliberately absent: ErrorPanel is a role="alert", which
  // already announces itself, and saying it here too would read the message out twice.
  const announcement =
    state.status === "loading" ? copy.loading.started
    : state.status === "results" ? copy.loading.complete
    : "";

  return (
    <div className="flex min-h-dvh flex-col bg-bg text-ink">
      <Header />

      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>

      <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-12 sm:px-6 lg:px-10 lg:py-20">
        {state.status === "idle" ? (
          <div className="mx-auto max-w-[1180px] space-y-20">
            <PolicyInput
              input={state.input}
              limits={limits}
              onChange={(patch) => dispatch({ type: "edit", patch })}
              onSubmit={() => start("submit")}
            />
            {exampleList ? (
              <ExampleGallery data={exampleList} onOpen={openExample} busy={opening} />
            ) : null}
          </div>
        ) : null}

        {state.status === "loading" ? (
          <AnalysisProgress
            text={state.input.text}
            startedAt={state.startedAt}
            onCancel={() => dispatch({ type: "cancel" })}
          />
        ) : null}

        {state.status === "error" ? (
          <ErrorPanel
            code={state.code}
            limits={limits}
            onRetry={() => start("retry")}
            onEditText={() => dispatch({ type: "editText" })}
          />
        ) : null}

        {state.status === "results" ? (
          <ResultsView
            data={state.data}
            // Every offset in the response indexes into this exact string. For a live result it
            // is the text that was sent; a saved example was never in this browser, so the
            // backend ships its text in `document.text` for precisely this purpose.
            text={state.data.document.text ?? normaliseText(state.input.text)}
            onReset={() => dispatch({ type: "reset" })}
            notice={
              state.source === "example" ? (
                <SavedNotice data={state.data} run={exampleList} />
              ) : null
            }
            resetLabel={state.source === "example" ? copy.examples.backToStart : undefined}
            footer={
              exampleList ? (
                <section aria-labelledby="map-heading" className="border-t border-rule pt-8">
                  <h2 id="map-heading" className="t-h3">
                    {copy.map.heading}
                  </h2>
                  <p className="t-small mt-2 max-w-[46ch] text-ink-3">{copy.map.sub}</p>
                  <div className="mt-4">
                    <ScoreMap
                      examples={exampleList.examples}
                      current={{
                        risk: state.data.scores.risk_index,
                        quality: state.data.scores.disclosure_quality,
                        label: state.data.policy.company_name ?? copy.map.thisPolicy,
                      }}
                    />
                  </div>
                </section>
              ) : null
            }
          />
        ) : null}
      </main>

      <Footer />
    </div>
  );
}
