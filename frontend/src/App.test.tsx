import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { response, TEXT } from "./test/fixture";

const META = {
  limits: { min_chars: 1000, max_chars: 200_000, max_body_bytes: 1_000_000, max_concurrent: 1 },
  provider: "mock",
  model: "mock",
};

const RESULT = response();

const ok = (body: unknown) =>
  Promise.resolve({ ok: true, status: 200, headers: new Headers(), json: () => Promise.resolve(body) });

const EXAMPLES = {
  run: "gemini36_batch_v1.1",
  provider: "gemini",
  model: "gemini-3.6-flash",
  analysed_at: "2026-11-19T21:06:18+00:00",
  examples: [
    {
      policy_id: "P06", company_name: "Zoom", cohort: "global", scope: "consumer",
      source_url: "https://explore.zoom.us/en/privacy/", chars: 53_759, sentences: 1_234,
      risk_index: 33.1, risk_index_display: 33, disclosure_quality: 78.6,
      disclosure_quality_display: 79, n_not_stated: 1, complete: true,
    },
  ],
};

/** A saved analysis differs from a live one in two ways that the UI depends on. */
const RESULT_EXAMPLE = {
  ...RESULT,
  source: "example",
  policy: { ...RESULT.policy, company_name: "Zoom" },
  // The real fixture text, because every offset in the response indexes into it.
  document: { ...RESULT.document, text: TEXT },
};

/**
 * A fetch stub that answers /meta and /examples immediately and /evaluate when the test
 * resolves it. Routing by path matters: the app now makes three different GETs, and a stub that
 * answered them all with the same body is what hid a real bug in useExamples.
 */
function stubFetch(evaluateResult: () => Promise<unknown>, examples: unknown = EXAMPLES) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    void init;
    const path = String(url);
    if (path.endsWith("/meta")) return ok(META);
    if (path.endsWith("/examples")) {
      return examples === null
        ? Promise.resolve({ ok: false, status: 404, headers: new Headers(),
                            json: () => Promise.resolve({ error: { code: "EXAMPLES_UNAVAILABLE" } }) })
        : ok(examples);
    }
    if (path.includes("/examples/")) return ok(RESULT_EXAMPLE);
    return evaluateResult();
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function paste(text = "a".repeat(1000)) {
  const box = screen.getByLabelText("Privacy policy text");
  // fireEvent-style paste: userEvent.type would be 1000 keystrokes.
  await userEvent.click(box);
  await userEvent.paste(text);
}

afterEach(() => vi.unstubAllGlobals());

describe("the app wiring", () => {
  it("starts on the input screen", async () => {
    stubFetch(() => ok(RESULT));
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: /What does this privacy policy actually say/ }))
      .toBeInTheDocument();
  });

  it("goes to the loading screen on Analyze and announces it once", async () => {
    stubFetch(() => new Promise(() => { /* never settles: stay on loading */ }));
    render(<App />);
    await paste();
    await userEvent.click(screen.getByRole("button", { name: "Analyze policy" }));
    expect(await screen.findByRole("heading", { name: "Reading the policy" })).toBeInTheDocument();
    expect(screen.getByText("Analysis started")).toBeInTheDocument();
  });

  it("shows the results when the analysis succeeds", async () => {
    stubFetch(() => ok(RESULT));
    render(<App />);
    await paste();
    await userEvent.click(screen.getByRole("button", { name: "Analyze policy" }));
    expect(await screen.findByRole("heading", { name: "Razorpay" })).toBeInTheDocument();
    expect(screen.getByText("Analysis complete")).toBeInTheDocument();
  });

  it("sends the text the user pasted, normalised, to /evaluate", async () => {
    const f = stubFetch(() => ok(RESULT));
    render(<App />);
    await paste("line\r\n".repeat(200) + "a".repeat(1000));
    await userEvent.click(screen.getByRole("button", { name: "Analyze policy" }));
    // Wait for the /evaluate call itself, not for a total call count: the app also GETs /meta
    // and /examples, and pinning the total makes this test fail whenever that changes.
    const evaluateCall = () => f.mock.calls.find((c) => String(c[0]).endsWith("/evaluate"));
    await waitFor(() => expect(evaluateCall()).toBeDefined());
    const sent = JSON.parse(String(evaluateCall()?.[1]?.body));
    expect(sent.text).not.toContain("\r");
    expect(sent.scope).toBe("all_users");
  });

  it("shows the error screen, keeping the text, and returns to it on Edit text", async () => {
    stubFetch(() =>
      Promise.resolve({
        ok: false, status: 429, headers: new Headers({ "Retry-After": "60" }),
        json: () => Promise.resolve({ error: { code: "LLM_QUOTA", retry_after_s: 60 } }),
      }),
    );
    render(<App />);
    await paste();
    await userEvent.click(screen.getByRole("button", { name: "Analyze policy" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/usage limit has been reached/);
    // Exactly once: the alert announces itself, so the live region must stay quiet.
    expect(screen.getAllByText(/usage limit has been reached/)).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Edit text" }));
    expect(screen.getByLabelText("Privacy policy text")).toHaveValue("a".repeat(1000));
  });

  it("returns to the input screen with the text intact on Cancel", async () => {
    stubFetch(() => new Promise(() => { /* never settles */ }));
    render(<App />);
    await paste();
    await userEvent.click(screen.getByRole("button", { name: "Analyze policy" }));
    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(screen.getByLabelText("Privacy policy text")).toHaveValue("a".repeat(1000));
  });

  it("clears the text from memory on 'Analyze another policy'", async () => {
    stubFetch(() => ok(RESULT));
    render(<App />);
    await paste();
    await userEvent.click(screen.getByRole("button", { name: "Analyze policy" }));
    await userEvent.click(await screen.findByRole("button", { name: "Analyze another policy" }));
    expect(screen.getByLabelText("Privacy policy text")).toHaveValue("");
  });

  it("never writes the pasted text to browser storage", async () => {
    stubFetch(() => ok(RESULT));
    render(<App />);
    await paste("SECRET-POLICY-TEXT".repeat(60));
    await userEvent.click(screen.getByRole("button", { name: "Analyze policy" }));
    await screen.findByRole("heading", { name: "Razorpay" });
    const dumped = JSON.stringify({ ...localStorage, ...sessionStorage }) + document.cookie + location.href;
    expect(dumped).not.toContain("SECRET-POLICY-TEXT");
  });
});

describe("saved analyses", () => {
  it("lists them on the input screen with both scores in their own columns", async () => {
    stubFetch(() => ok(RESULT));
    render(<App />);
    const row = await screen.findByRole("button", { name: "Open the saved analysis of Zoom" });
    expect(row).toBeInTheDocument();
    // Section 9: two separate numbers, never one combined score.
    const cells = row.closest("tr")!.querySelectorAll("td");
    expect(Array.from(cells).map((c) => c.textContent)).toEqual(["33", "79", "53,759"]);
  });

  it("opens one without calling /evaluate, and says it is a saved analysis", async () => {
    const f = stubFetch(() => ok(RESULT));
    render(<App />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Open the saved analysis of Zoom" }),
    );
    expect(await screen.findByText(/This is a saved analysis of Zoom/)).toBeInTheDocument();
    expect(f.mock.calls.some((c) => String(c[0]).endsWith("/evaluate"))).toBe(false);
  });

  it("renders the source document from the response, not from the empty textarea", async () => {
    // A live result gets its text from what the user pasted. Nobody pasted anything here, so if
    // the app did not read `document.text` the source panel would be empty and the evidence
    // marks would have nothing to sit in.
    stubFetch(() => ok(RESULT));
    render(<App />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Open the saved analysis of Zoom" }),
    );
    await screen.findByText(/This is a saved analysis of Zoom/);

    const firstLine = TEXT.split("\n")[0]!;
    expect(screen.getAllByText(firstLine, { exact: false }).length).toBeGreaterThan(0);
    // The quotes are marked in place, which only works if the offsets matched the text.
    expect(document.querySelectorAll("mark.evidence").length).toBeGreaterThan(0);
  });

  it("does not call a published policy 'Your text'", async () => {
    stubFetch(() => ok(RESULT));
    render(<App />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Open the saved analysis of Zoom" }),
    );
    expect(await screen.findByRole("heading", { name: "Zoom's policy text" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Your text" })).not.toBeInTheDocument();
  });

  it("plots the opened analysis on the score map", async () => {
    stubFetch(() => ok(RESULT));
    render(<App />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Open the saved analysis of Zoom" }),
    );
    const map = await screen.findByRole("img", { name: /Zoom, the policy shown above/ });
    expect(map).toBeInTheDocument();
  });

  it("keeps a draft the user had typed when they close the example", async () => {
    stubFetch(() => ok(RESULT));
    render(<App />);
    await paste("draft text ".repeat(100));
    await userEvent.click(screen.getByRole("button", { name: "Open the saved analysis of Zoom" }));
    await userEvent.click(await screen.findByRole("button", { name: "Back to the start" }));
    expect(await screen.findByLabelText("Privacy policy text")).toHaveValue(
      "draft text ".repeat(100),
    );
  });

  it("still clears a live result's text on 'Analyze another policy'", async () => {
    // The example path must not have weakened section 7.8 for live analyses.
    stubFetch(() => ok(RESULT));
    render(<App />);
    await paste();
    await userEvent.click(screen.getByRole("button", { name: "Analyze policy" }));
    await userEvent.click(await screen.findByRole("button", { name: "Analyze another policy" }));
    expect(await screen.findByLabelText("Privacy policy text")).toHaveValue("");
  });

  it("hides the gallery when the server has no saved analyses", async () => {
    stubFetch(() => ok(RESULT), null);
    render(<App />);
    expect(await screen.findByLabelText("Privacy policy text")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Saved analyses" })).not.toBeInTheDocument(),
    );
  });

  it("hides the gallery when a proxy answers /examples with the wrong shape", async () => {
    stubFetch(() => ok(RESULT), { nonsense: true });
    render(<App />);
    expect(await screen.findByLabelText("Privacy policy text")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Saved analyses" })).not.toBeInTheDocument(),
    );
  });
});
