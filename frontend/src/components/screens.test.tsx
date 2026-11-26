import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AnalysisProgress } from "./AnalysisProgress";
import { ErrorPanel } from "./ErrorPanel";
import { PolicyInput } from "./PolicyInput";
import { EMPTY_INPUT, type Input } from "../lib/machine";

const limits = { minChars: 1000, maxChars: 200_000 };
const long = "a".repeat(1000);

function input(patch: Partial<Input> = {}): Input {
  return { ...EMPTY_INPUT, ...patch };
}

describe("PolicyInput", () => {
  const props = { limits, onChange: vi.fn(), onSubmit: vi.fn() };

  it("has a real label for the textarea, not just a placeholder", () => {
    render(<PolicyInput {...props} input={input()} />);
    expect(screen.getByLabelText("Privacy policy text")).toBeInTheDocument();
  });

  it("disables Analyze while the text is empty or too short", () => {
    render(<PolicyInput {...props} input={input()} />);
    expect(screen.getByRole("button", { name: "Analyze policy" })).toBeDisabled();
  });

  it("enables Analyze once the text is within the limits", () => {
    render(<PolicyInput {...props} input={input({ text: long })} />);
    expect(screen.getByRole("button", { name: "Analyze policy" })).toBeEnabled();
  });

  it("disables Analyze when the text is over the maximum", () => {
    render(<PolicyInput {...props} input={input({ text: "a".repeat(200_001) })} />);
    expect(screen.getByRole("button", { name: "Analyze policy" })).toBeDisabled();
    expect(screen.getByText(/over 200,000 characters/)).toBeInTheDocument();
  });

  it("says nothing about length while the textarea is still empty", () => {
    render(<PolicyInput {...props} input={input()} />);
    expect(screen.queryByText(/Paste at least/)).not.toBeInTheDocument();
  });

  it("explains a too-short paste once there is something in the box", () => {
    render(<PolicyInput {...props} input={input({ text: "too short" })} />);
    expect(screen.getByText(/Paste at least 1,000 characters/)).toBeInTheDocument();
  });

  it("counts characters and reading time with thousands separators", () => {
    render(<PolicyInput {...props} input={input({ text: "word ".repeat(2380) })} />);
    expect(screen.getByText(/11,900 characters · about 10 min to read/)).toBeInTheDocument();
  });

  it("shows the privacy note, which says the text is sent to Gemini", () => {
    render(<PolicyInput {...props} input={input()} />);
    expect(
      screen.getByText(/sent to Google's Gemini API for analysis\. PrivaScore does not store or log it\./),
    ).toBeInTheDocument();
  });

  it("maps the Consumer AI product checkbox to the consumer scope", async () => {
    const onChange = vi.fn();
    render(<PolicyInput {...props} onChange={onChange} input={input()} />);
    await userEvent.click(screen.getByLabelText("Consumer AI product"));
    expect(onChange).toHaveBeenCalledWith({ scope: "consumer" });
  });

  it("does not autofill or spellcheck the pasted policy", () => {
    render(<PolicyInput {...props} input={input()} />);
    const box = screen.getByLabelText("Privacy policy text");
    expect(box).toHaveAttribute("spellcheck", "false");
    expect(box).toHaveAttribute("autocomplete", "off");
  });
});

describe("AnalysisProgress", () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => vi.useRealTimers());

  it("lists the steps as an explanation, with no checkmarks and no percentage", () => {
    render(<AnalysisProgress text={long} startedAt={Date.now()} onCancel={vi.fn()} />);
    expect(screen.getByText("Asking Gemini about 16 practices")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("counts real elapsed time", () => {
    render(<AnalysisProgress text={long} startedAt={Date.now() - 42_000} onCancel={vi.fn()} />);
    expect(screen.getByText("0:42 elapsed")).toBeInTheDocument();
  });

  it("adds the 'still working' line only after 90 seconds", () => {
    render(<AnalysisProgress text={long} startedAt={Date.now() - 89_000} onCancel={vi.fn()} />);
    expect(screen.queryByText(/Still working/)).not.toBeInTheDocument();
  });

  it("says Gemini can be slow once past 90 seconds", () => {
    render(<AnalysisProgress text={long} startedAt={Date.now() - 91_000} onCancel={vi.fn()} />);
    expect(screen.getByText(/Still working\. Gemini can be slow under load\./)).toBeInTheDocument();
  });

  it("escalates past 240 seconds", () => {
    render(<AnalysisProgress text={long} startedAt={Date.now() - 241_000} onCancel={vi.fn()} />);
    expect(screen.getByText(/taking unusually long/)).toBeInTheDocument();
  });

  it("offers Cancel", async () => {
    const onCancel = vi.fn();
    render(<AnalysisProgress text={long} startedAt={Date.now()} onCancel={onCancel} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});

describe("ErrorPanel", () => {
  const props = { limits, onRetry: vi.fn(), onEditText: vi.fn() };

  it("is announced as an alert", () => {
    render(<ErrorPanel {...props} code="LLM_QUOTA" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("gives the quota message and offers the saved analyses", () => {
    render(<ErrorPanel {...props} code="LLM_QUOTA" />);
    expect(screen.getByText(/usage limit has been reached/)).toBeInTheDocument();
  });

  it("explains RATE_LIMITED as the site's own limit, not a server fault", () => {
    render(<ErrorPanel {...props} code="RATE_LIMITED" />);
    expect(screen.getByRole("heading", { name: "Analysis limit reached" })).toBeInTheDocument();
    expect(screen.getByText(/limits how many new analyses/)).toBeInTheDocument();
    expect(screen.queryByText(/Something went wrong/)).not.toBeInTheDocument();
  });

  it("explains BUSY as one analysis at a time", () => {
    render(<ErrorPanel {...props} code="BUSY" />);
    expect(screen.getByText(/Another analysis is running/)).toBeInTheDocument();
  });

  it("tells the user nothing was saved when the service failed", () => {
    render(<ErrorPanel {...props} code="LLM_ERROR" />);
    expect(screen.getByText(/Nothing was saved/)).toBeInTheDocument();
  });

  it("falls back to the generic message for an unexpected code", () => {
    render(<ErrorPanel {...props} code="NOT_FOUND" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("offers Try again and Edit text", async () => {
    const onRetry = vi.fn();
    const onEditText = vi.fn();
    render(<ErrorPanel {...props} code="NETWORK" onRetry={onRetry} onEditText={onEditText} />);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await userEvent.click(screen.getByRole("button", { name: "Edit text" }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(onEditText).toHaveBeenCalledOnce();
  });
});
