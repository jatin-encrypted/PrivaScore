/**
 * A realistic /evaluate response for tests.
 *
 * It is typed as EvaluateResponse, which is generated from the backend's own OpenAPI schema, so
 * if the contract changes this file stops compiling instead of silently testing a shape the
 * backend no longer sends. The numbers are from the real Razorpay run.
 */
import type { EvaluateResponse, FlagResult } from "../api/client";

export const TEXT = [
  "Razorpay Privacy Policy",
  "We may share your personal information with third party partners for advertising.",
  "You can request deletion of your account data by writing to our grievance officer.",
].join("\n");

/**
 * Paragraph and quote offsets derived from the real line boundaries, never hardcoded lengths:
 * the backend computes them the same way, and an off-by-one here would hide a real one.
 */
const offsets = (() => {
  const lines = TEXT.split("\n");
  const starts: number[] = [];
  let pos = 0;
  for (const line of lines) {
    starts.push(pos);
    pos += line.length + 1;
  }
  const range = (i: number): [number, number] => [starts[i]!, starts[i]! + lines[i]!.length];
  const quote = (i: number, phrase: string): [number, number] => {
    const at = lines[i]!.indexOf(phrase);
    return [starts[i]! + at, starts[i]! + at + phrase.length];
  };
  return {
    head: range(0),
    p2: range(1),
    p3: range(2),
    quoteG2: quote(1, "We may share your personal information with third party partners"),
    quoteG5: quote(2, "You can request deletion of your account data"),
  };
})();

export function flag(over: Partial<FlagResult> = {}): FlagResult {
  return {
    id: "G1",
    key: "first_party_collection",
    title: "Data the company collects",
    group: "general",
    type: "exposure",
    weight: 1,
    question: "What personal data does the company itself collect, and how broad is it?",
    state: "ED",
    state_meaning: "Collects a broad range of personal data.",
    status: "verified",
    applicable: true,
    not_applicable_reason: null,
    risk_points: 1,
    max_risk_points: 1,
    quality_points: 2,
    rationale: "The policy lists the categories it collects.",
    evidence: [],
    dropped_evidence_count: 0,
    n_candidates: 18,
    n_search_terms: 11,
    ...over,
  };
}

export const FLAGS: FlagResult[] = [
  flag(),
  flag({
    id: "G2",
    key: "third_party_advertising_tracking",
    title: "Selling or sharing data for ads",
    weight: 3,
    state: "ED",
    state_meaning: "Shares data with third parties for advertising with no first-party opt out.",
    risk_points: 3,
    max_risk_points: 3,
    quality_points: 2,
    rationale: "Third parties are permitted to collect visit details for ad targeting.",
    evidence: [
      {
        sentence_id: "p002.s1",
        heading: "Razorpay Privacy Policy",
        match: "exact",
        offset_utf16: offsets.quoteG2,
        text: TEXT.slice(offsets.quoteG2[0], offsets.quoteG2[1]),
      },
    ],
  }),
  flag({
    id: "G4",
    key: "retention_period",
    title: "How long data is kept",
    group: "general",
    type: "governance",
    weight: 2,
    state: "CD",
    state_meaning: "Keeps data for as long as needed, with some limits named.",
    risk_points: 1,
    max_risk_points: 2,
    quality_points: 1.5,
  }),
  flag({
    id: "G5",
    key: "access_correction_deletion",
    title: "Access, correction and deletion",
    group: "general",
    type: "governance",
    weight: 2,
    state: "ED",
    state_meaning: "Grants access, correction and deletion to all users.",
    risk_points: 0,
    max_risk_points: 2,
    quality_points: 2,
    evidence: [
      {
        sentence_id: "p003.s1",
        heading: null,
        match: "normalized",
        offset_utf16: offsets.quoteG5,
        text: TEXT.slice(offsets.quoteG5[0], offsets.quoteG5[1]),
      },
    ],
  }),
  flag({
    id: "G7",
    key: "children",
    title: "Children and minors",
    group: "general",
    type: "governance",
    weight: 2,
    state: "NS",
    state_meaning: "The policy says nothing usable about this practice.",
    status: "absent_unverifiable",
    risk_points: 0,
    max_risk_points: 2,
    quality_points: 0,
    rationale: "Nothing on minors in the candidate sentences.",
    evidence: [],
    n_candidates: 4,
  }),
  flag({
    id: "AI1",
    key: "ai_training_on_user_data",
    title: "Training AI on your data",
    group: "ai",
    weight: 3,
    state: "NS",
    state_meaning: "The policy says nothing usable about this practice.",
    status: "no_candidates",
    risk_points: 0,
    max_risk_points: 3,
    quality_points: 0,
    rationale: null,
    evidence: [],
    n_candidates: 0,
    n_search_terms: 7,
  }),
  flag({
    id: "AI2",
    key: "ai_training_opt_out_control",
    title: "Opting out of AI training",
    group: "ai",
    type: "governance",
    weight: 2,
    state: "NS",
    state_meaning: "The policy says nothing usable about this practice.",
    status: "not_applicable",
    applicable: false,
    not_applicable_reason: "not applicable: AI1=NS",
    risk_points: 0,
    max_risk_points: 0,
    quality_points: 0,
    rationale: null,
    evidence: [],
    n_candidates: 0,
    n_search_terms: 0,
  }),
  flag({
    id: "DPDP3",
    key: "grievance_officer",
    title: "Grievance or data protection officer",
    group: "dpdp",
    type: "readiness",
    weight: 1,
    state: "ED",
    state_meaning: "Publishes a Grievance Officer with contact details.",
    risk_points: 0,
    max_risk_points: 1,
    quality_points: 2,
  }),
  flag({
    id: "DPDP4",
    key: "indian_languages",
    title: "Notice in Indian languages",
    group: "dpdp",
    type: "readiness_info",
    weight: 0,
    state: "NS",
    state_meaning: "The policy says nothing usable about this practice.",
    status: "no_candidates",
    applicable: false,
    not_applicable_reason: "informational flag (weight 0)",
    risk_points: 0,
    max_risk_points: 0,
    quality_points: 0,
    rationale: null,
    evidence: [],
    n_candidates: 0,
    n_search_terms: 5,
  }),
];

export function response(over: Partial<EvaluateResponse> = {}): EvaluateResponse {
  return {
    api_version: "1",
    source: "live",
    policy: {
      company_name: "Razorpay",
      scope: "all_users",
      chars: TEXT.length,
      sentences: 3,
      paragraphs: 3,
      text_sha256: "8c5d095bc8c19a8d9f1222e0e6bbd77832c93a8b6609df94428ac8c742bcb8c0",
    },
    scores: {
      risk_index: 50,
      risk_index_display: 50,
      disclosure_quality: 67.8571,
      disclosure_quality_display: 68,
      n_applicable: 14,
      n_not_stated: 3,
      complete: true,
      rejected_flags: [],
      scoring_version: "1.0",
    },
    flags: FLAGS,
    metrics: {
      readability: {
        fk_grade: 15.5,
        flesch_reading_ease: 31.7,
        reading_minutes: 11.2,
        words: 2668,
        prose_sentences: 100,
        avg_words_per_sentence: 26.7,
      },
      vagueness: {
        vague_sentence_fraction: 0.48,
        multi_category_fraction: 0.119,
        cues_per_1000_words: {
          conditionality: 2.6,
          generalization: 5.5,
          modality: 17.8,
          numeric_quantifier: 14.7,
        },
        examples: [
          {
            sentence_id: "p020.s2",
            text: "We may collect such as financial information in some cases.",
            cues: {
              conditionality: ["in some cases"],
              generalization: ["such as"],
              modality: ["may"],
            },
          },
        ],
      },
      bert_profile: {
        available: true,
        paragraphs: 75,
        threshold: 0.5,
        categories: [
          { name: "First Party Collection/Use", share: 0.16 },
          { name: "Third Party Sharing/Collection", share: 0.2 },
          { name: "Other", share: 0.653 },
          { name: "Do Not Track", share: 0 },
        ],
      },
    },
    document: {
      paragraphs: [
        { id: "p001", offset_utf16: offsets.head, is_heading: true },
        { id: "p002", offset_utf16: offsets.p2, is_heading: false },
        { id: "p003", offset_utf16: offsets.p3, is_heading: false },
      ],
      text: null,
    },
    warnings: [],
    meta: {
      provider: "gemini",
      model: "gemini-3.6-flash",
      prompt_version: "1.0",
      rules_version: "1.1",
      flag_definitions_version: "1.4",
      privascore_version: "0.1.0",
      llm_calls: 1,
      timings_ms: { metrics: 18, extraction: 61727, total: 61735 },
      analysed_at: "2026-11-25T09:30:00Z",
    },
    ...over,
  };
}
