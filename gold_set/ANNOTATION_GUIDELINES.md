# PrivaScore gold set: annotation guidelines

**Version 1.0, approved by the project owner on 14 Nov 2026.** These guidelines go with `flag_definitions.json` v1.4. Don't change a definition once labelling has started. If a rule turns out to be wrong, record it, finish the current policy, and bump the version.

The flag IDs, keys, types and weights are defined in `flag_definitions.json`. They were first proposed in an earlier LLM-generated draft gold set. **That draft's labels and quotes are not used**: only 16% of its quotes could be found in the real policies.

---

## 1. What you are labelling

For each of the 15 policies and each of the 16 flags, you record **one label** saying what the **saved snapshot** says about the flag. You are labelling what the policy text *says*. You are not judging what the company actually does.

### 1.1 Presence (your first decision)

| Presence | Meaning | Evidence IDs |
|---|---|---|
| **Present** | The snapshot addresses this flag. It may say the company does it, does it with conditions, or does not do it. | ≥ 1 required |
| **Absent** | The snapshot says nothing usable about this flag. | none (nearby text goes in `related_ids`) |
| **Unclear** | The snapshot addresses the flag, but the wording is contradictory or too vague to place it in ED, CD or EE. | ≥ 1 required, plus a note |

**Present does not mean "the risky practice happens."** A policy that says "we never sell your data" is Present for G2, with the state EE.

### 1.2 State (only for Present)

| State | General meaning | |
|---|---|---|
| **ED**, explicitly disclosed | The policy clearly states the practice or right, without significant conditions. | |
| **CD**, conditionally disclosed | The practice or right exists, but with conditions: an opt-out, a default that can be changed, a jurisdiction or tier limit, or a purpose restriction. | |
| **EE**, explicitly excluded | The policy explicitly says the practice does **not** happen, or explicitly denies the right or protection. | |

Absent is stored as **NS** and Unclear as **UN**. The validator fills these in.

**What ED/EE mean for risk depends on the flag type.** This is why every flag below has its own state table.
- **Exposure flags** (G1–G3, G6, AI1, AI3–AI5) describe a practice. ED is the most exposure and EE is none.
- **Governance and readiness flags** (G4, G5, G7, AI2, DPDP1–DPDP3) describe a protection. ED is the best protection and EE is the protection explicitly denied.
- **DPDP4** is informational only. Its weight is 0.

---

## 2. General rules (apply to every flag)

**R1. Evidence is cited by sentence ID, never typed.** Write IDs such as `p036.s1; p063.s1` in `evidence_ids`. The validator pulls the exact text from the snapshot. Put the most important ID first. Use as many IDs as you need.

**R2. Use only the snapshot.** Use the saved text file in `policies/text/` and read it in `evidence/<key>_numbered.md`. Don't use your memory of the company, news, help-centre articles or other documents.
- If the snapshot points elsewhere ("see our Cookie Policy", "this help center article"), set `refers_elsewhere = yes`.
- Then label only what the snapshot itself says. If the snapshot only points elsewhere and says nothing more, label **Absent** with `refers_elsewhere = yes`.

**R3. Use the search packet, but don't rely on it alone.** `evidence/<key>_evidence.md` lists sentences that match each flag's search terms. It is a reading aid. Before labelling **Absent**:
- (a) look at every candidate sentence;
- (b) scan the section headings in the numbered text for anything related;
- (c) write what you did in `absence_check`, e.g. "packet: 0 candidates; headings scanned; nothing on human review".

The search log is saved automatically. Failing to find a keyword **is not proof** that the practice is absent.

**R4. Scope.** Label for the scope in the manifest. All AI products (P01–P05) are `consumer`, and P06–P15 are `all_users`.
- Ignore sentences that apply only to enterprise, business or API customers when the scope is `consumer`. Mention them in `notes` if they are relevant.
- If a rule applies only to some users (e.g. "if you are a Pro user"), that makes the label **CD**.

**R5. Jurisdiction: label for a user in India.** PrivaScore is evaluated as an Indian-user tool. Use the first of these that exists:
1. an India-specific section;
2. the global or default text;
3. if the text covers only other regions (e.g. "EEA residents have the right to…") and says nothing for other users, treat it as a limitation, which normally means **CD** for rights flags.

Record the jurisdiction issue in `notes`.

**R6. "May" counts as disclosure.** "We may share X with advertisers" discloses the practice. Treat it as stated, then apply the flag's conditions. Hedging alone does not make a passage Unclear.

**R7. Conflicts within the policy.**
- A specific statement beats a general one. For example, "we don't sell data" in the overview vs "we share device IDs with ad partners" in the cookie section: the specific sharing statement decides.
- If two specific statements genuinely contradict each other, label **Unclear** and cite both.

**R8. Exceptions mean CD.** "We don't do X, except…" or "we do X unless you opt out" → **CD**, as long as the exception or condition is real and stated.

**R9. Silence is never EE.** EE needs an explicit statement. "The policy doesn't mention children" is **Absent**, not EE.

> **Change from the Gemini draft:** that draft used EE for silence on G7, DPDP2 and DPDP3. These guidelines don't.

**R10. Label each flag independently, except AI2,** which depends on AI1 (see AI2).

**R11. Record your doubt.** If you hesitated between two states, write `between CD and ED: …` in `notes`. Those notes show where the definitions are hard to apply, and they go into the write-up.

**R12. Keep the reference set independent of the system under test.** Never open `runs/` (the Gemini extractor outputs) or the earlier Gemini draft gold set while drafting or reviewing labels. (Changed 14 Nov 2026: see section 6. The original rule was blind labelling from a blank sheet.)

---

## 3. Flag definitions

The examples are **made-up wording written for these guidelines, not quotes from any policy**. Each table mixes AI, general-tech and Indian-service examples so the same rule is applied everywhere.

### G1 `first_party_collection_scope` (exposure, weight 1)
**Question:** what personal data does the company itself collect, and how broad is it?

| State | Rule |
|---|---|
| ED | Collects personal data beyond basic account and contact details. This includes any of: device or usage data, location, user content (messages, prompts, uploads, recordings), contacts, financial/KYC or sensitive data, or data obtained from other sources. |
| CD | Collection is limited to what the service needs, and any extra categories are opt-in. |
| EE | Says it collects no personal data. |

| Example (made up) | Label |
|---|---|
| "We collect the prompts and files you submit and information about your device." | Present, ED |
| "We collect your name, PAN and bank details for KYC, and your transaction history." | Present, ED |
| "We only collect your email address. Location is collected only if you turn it on." | Present, CD |

*Known issue:* almost every modern policy will be ED, so this flag barely separates policies. It's still labelled, but it is reported separately from headline accuracy (see section 5).

### G2 `third_party_advertising_tracking` (exposure, weight 3)
**Question:** does the company sell personal data, or share it with or let third parties collect it for advertising, marketing or cross-site tracking?

| State | Rule |
|---|---|
| ED | Sells data, or shares it with ad networks, ad partners, pixels or SDKs for advertising or tracking, and **no** way to opt out is described. |
| CD | Does the above, but describes a way to opt out (a setting, cookie choices, a "Do Not Sell" link, GPC) or limits it (e.g. no targeted ads for minors). |
| EE | Explicitly says it does not sell data **and** does not share data for targeted or cross-context advertising, and nothing elsewhere contradicts that (R7). |

- Analytics-only providers (usage statistics, not advertising) don't make G2 ED or CD on their own. Note them in `notes`.
- "We don't sell your data" alone isn't EE if the cookie section describes advertising partners.

| Example (made up) | Label |
|---|---|
| "We work with advertising partners who place cookies to show you relevant ads." | Present, ED |
| "We share device identifiers with ad networks. You can opt out in Settings → Ads." | Present, CD |
| "We do not sell personal data or share it for targeted advertising." | Present, EE |

### G3 `profiling_automated_decisions` (exposure, weight 2)
**Question:** does the company build profiles or inferences about users, or make automated decisions about them?

| State | Rule |
|---|---|
| ED | Profiling or inference for ads, personalisation or scoring, with no user control described. Or automated decisions with significant effects (credit, eligibility, account bans) with no human review or appeal described. |
| CD | Personalisation or recommendations where a user control is described, **or** automated decisions with human review or appeal, **or** automated risk/fraud scoring limited to security and payments. |
| EE | Explicitly says it does not profile users, or makes no automated decisions with legal or similar effects, **and** no other profiling is described. |

| Example (made up) | Label |
|---|---|
| "We infer your interests from your activity to personalise ads." | Present, ED |
| "We recommend courses based on your learning history; you can turn this off." | Present, CD |
| "Transactions are scored automatically for fraud; flagged payments are reviewed by our team." | Present, CD |

### G4 `data_retention_specificity` (governance, weight 2)
**Question:** how specific is the policy about how long personal data is kept?

| State | Rule |
|---|---|
| ED (best) | A concrete period (a number of days, months or years, or a defined event such as "30 days after account deletion") for **at least one category of user-provided content or account data**. |
| CD | Only purpose-based retention ("as long as necessary", "as required by law"), **or** concrete periods only for peripheral data (cookies, server logs). |
| EE (worst) | Says identifiable data is kept indefinitely or permanently with no limit. |

- Periods for other people's data, or for backups only, don't make it ED.
- Deletion **after** you close your account counts if a period is given.

| Example (made up) | Label |
|---|---|
| "Deleted chats are removed from our systems within 30 days." | Present, ED |
| "We retain transaction records for 10 years as required by RBI." | Present, ED |
| "We keep personal data as long as necessary for the purposes described." | Present, CD |
| "Cookies expire after 13 months. We otherwise keep data as long as needed." | Present, CD |
| "We may retain your information indefinitely." | Present, EE |

### G5 `user_rights_access_deletion` (governance, weight 2)
**Question:** what rights do users have to access, correct and delete their data, and for whom?

| State | Rule |
|---|---|
| ED (best) | Access **and** correction **and** deletion are offered to users generally, or to Indian users. |
| CD | Some rights are missing; or rights apply only to certain regions (R5); or deletion only means closing the whole account; or there are broad carve-outs (e.g. data already used in model training can't be removed). |
| EE (worst) | Explicitly denies access or deletion. |

| Example (made up) | Label |
|---|---|
| "You can access, correct or delete your personal data from Settings or by writing to us." | Present, ED |
| "If you live in the EEA or UK you have the right to access and erase your data." (nothing for others) | Present, CD |
| "As a Data Principal you may request correction and erasure, and nominate another person." | Present, ED (if access is also offered) |

### G6 `international_data_transfers` (exposure, weight 1)
**Question:** is personal data transferred to or stored in other countries, and are safeguards named?

| State | Rule |
|---|---|
| ED | Data is transferred or stored abroad, and **no** specific safeguard is named. Generic "appropriate safeguards" with no mechanism counts as ED; note it. |
| CD | Data is transferred abroad, and a specific mechanism is named: standard contractual clauses, adequacy decisions, the Data Privacy Framework, binding corporate rules, or contracts requiring equivalent protection. |
| EE | Explicitly says data is stored and processed only in one country, e.g. only in India. |

Partial localisation (e.g. payment data in India, other data abroad) is labelled by the "abroad" part. Mention the localisation in `notes`.

| Example (made up) | Label |
|---|---|
| "Your information may be processed in the United States and other countries." | Present, ED |
| "We transfer data outside the EEA using Standard Contractual Clauses." | Present, CD |
| "All customer data is stored on servers located in India." | Present, EE |

### G7 `childrens_data_safeguards` (governance, weight 2)
**Question:** what does the policy say about children and minors: the age threshold and the safeguards?

| State | Rule |
|---|---|
| ED (best) | Protections cover **under-18s**: the service is 18+ only, or verifiable parental consent is required under 18, or tracking or targeted ads for minors are explicitly banned. (The DPDP Act defines a child as under 18.) |
| CD | Only an under-13 or under-16 threshold, with no specific protection for older minors. Or minors may use the service with "parental permission" but no verification is described. |
| EE (worst) | Explicitly says it collects data from children with no safeguards. |

| Example (made up) | Label |
|---|---|
| "You must be 18 or older to use our services." | Present, ED |
| "Our service is not directed to children under 13." | Present, CD |
| "Users aged 13–17 need parental permission." (no verification) | Present, CD |

### AI1 `ai_model_training_on_user_content` (exposure, weight 3)
**Question:** does the company use users' personal data or content to train or improve AI or machine-learning models?

| State | Rule |
|---|---|
| ED | Uses personal data or content to train AI/ML models, and **no** opt-out or limit is described. |
| CD | Trains, but with an opt-out; or only on some data (e.g. feedback, public posts); or by default only for some user tiers; or ML only for narrow purposes (fraud or security models). |
| EE | Explicitly says user data or content is **not** used to train AI models. |

**Key rule:** "We use data to improve our services" **without** mentioning models, machine learning or AI does **not** count. Label it Absent, and cite the sentence in `related_ids`.

| Example (made up) | Label |
|---|---|
| "We use your conversations to train our models." | Present, ED |
| "We may use your content to improve our models; you can turn this off in Data Controls." | Present, CD |
| "We do not use your learning data to train AI models." | Present, EE |
| "We use your data to improve and develop our services." | Absent (related_ids) |

### AI2 `ai_training_opt_out_control` (governance, weight 2)
**Question:** if personal data is used for AI training, can the user stop it, and how?

**Applicability:** only when AI1 is **ED or CD**. If AI1 is EE or Absent, label AI2 **Absent** with the note `not applicable: AI1=<state>`.

| State | Rule |
|---|---|
| ED (best) | A self-serve setting or toggle stops training use. |
| CD | Opt-out only by email, form or request; or it covers only future data or some data types; or it requires deleting the account. |
| EE (worst) | Explicitly says users cannot opt out of training. |

If AI1 is ED because no opt-out is described, AI2 is normally **Absent**. Silence is not EE (R9).

| Example (made up) | Label |
|---|---|
| "You can turn off 'Improve the model' in Settings at any time." | Present, ED |
| "To opt out of training, email privacy@example.com." | Present, CD |

### AI3 `ai_human_review_of_chats` (exposure, weight 2)
**Question:** can people (employees, contractors, reviewers) read or review users' content?

| State | Rule |
|---|---|
| ED | Routine human review of user content, e.g. reviewers or annotators reading conversations to improve models or quality. |
| CD | Human access limited to specific triggers: safety/abuse flags, user-submitted feedback, support requests, or legal requests. |
| EE | Explicitly says no human reads user content. |

- Generic "our personnel access data as needed to provide the service" is CD. Note it.
- Many policies only describe this in help-centre pages (R2). Expect frequent **Absent** with `refers_elsewhere`.

| Example (made up) | Label |
|---|---|
| "Trained reviewers may read conversations to improve our systems." | Present, ED |
| "Our team may review content flagged for violating our policies." | Present, CD |
| "No person at our company can read your messages." | Present, EE |

### AI4 `deidentification_training_carveout` (exposure, weight 2)
**Question:** may the company keep, use or share de-identified or aggregated data, and for what?

| State | Rule |
|---|---|
| ED | De-identified or aggregated data may be shared with third parties, used for any purpose, kept indefinitely, or used to train or improve models. |
| CD | De-identified or aggregated data is used only internally for named narrow purposes (analytics, security, research) and is not shared. |
| EE | Explicitly says it won't use or share de-identified data beyond the policy's limits (rare). |

| Example (made up) | Label |
|---|---|
| "We may share aggregated, de-identified information with partners for any purpose." | Present, ED |
| "We use anonymised statistics internally to improve service reliability." | Present, CD |

### AI5 `third_party_ai_subprocessors` (exposure, weight 2)
**Question:** is user content sent to external AI or model providers, or licensed to others for AI training?

| State | Rule |
|---|---|
| ED | Content is shared with third-party AI/model providers, or licensed for others' AI training, and no restriction on their use is described. |
| CD | Third-party AI providers are bound by stated limits (no training on the data, confidentiality), **or** data flows only when the user turns on an integration or connector. |
| EE | Explicitly says no user content goes to third-party AI providers. |

- Generic "service providers (cloud hosting, payments)" is **not** AI5.
- The company's own name doesn't count. The search ignores it automatically.

| Example (made up) | Label |
|---|---|
| "We license public posts to companies that train AI models." | Present, ED |
| "Our assistant uses a third-party model provider that may not use your data for training." | Present, CD |
| "If you connect our app to an AI assistant, we share the data you request through it." | Present, CD |

### DPDP readiness flags: read this first
DPDP1–DPDP4 record **readiness wording only, not legal compliance**. The DPDP Rules were notified on 13 Nov 2025, and most obligations apply from about May 2027. A label here never means "violates the DPDP Act". These flags apply to all 15 policies, including non-Indian ones.

### DPDP1 `dpdp_unambiguous_affirmative_consent` (readiness, weight 2)
**Question:** how does the policy obtain consent?

| State | Rule |
|---|---|
| ED (best) | It describes an explicit affirmative action (a checkbox, a separate consent screen, a standalone itemised consent notice at sign-up). |
| CD | Consent is folded into accepting the terms or registration; or the policy relies on other legal bases (contract, legitimate interests) "depending on where you live". |
| EE (worst) | Browsewrap: "by visiting, using or downloading … you agree or consent to this policy". This applies to the policy as a whole, even if specific features ask for separate consent; note those features. |

| Example (made up) | Label |
|---|---|
| "At sign-up we show you a notice listing the data and purposes, and ask you to tick to consent." | Present, ED |
| "We process data based on contract, legitimate interests or consent, depending on your location." | Present, CD |
| "By using the app you consent to the collection and use of your information." | Present, EE |

### DPDP2 `dpdp_easy_consent_withdrawal` (readiness, weight 2)
**Question:** can users withdraw consent, and is it as easy as giving it?

| State | Rule |
|---|---|
| ED (best) | A self-serve way (settings, toggle, dashboard, consent manager) to withdraw consent for the main consent-based processing. |
| CD | Withdrawal only by email or contact; or only by deleting the account; or covering only marketing messages. |
| EE (worst) | Explicitly says consent can't be withdrawn. Silence is **Absent** (R9). |

| Example (made up) | Label |
|---|---|
| "You can withdraw consent at any time from Privacy Settings." | Present, ED |
| "To withdraw consent, write to our Grievance Officer." | Present, CD |
| "You can unsubscribe from marketing emails using the link in each email." (nothing else) | Present, CD (note: marketing only) |

### DPDP3 `dpdp_grievance_dpo_contact` (readiness, weight 1)
**Question:** does the policy publish a Grievance Officer or Data Protection Officer with contact details?

| State | Rule |
|---|---|
| ED (best) | A designated Grievance Officer or DPO (named person or designated role) **with** direct contact details. |
| CD | Only a generic privacy email, form or postal address, with no designated officer. |
| EE (worst) | Explicitly says there is no contact. Silence is **Absent**. |

| Example (made up) | Label |
|---|---|
| "Grievance Officer: [name], grievance@example.in" | Present, ED |
| "Data Protection Officer: dpo@example.com" | Present, ED |
| "Questions? Email privacy@example.com." | Present, CD |

### DPDP4 `dpdp_eighth_schedule_languages` (informational, weight 0)
**Question:** is the notice offered in Indian languages besides English? Write down which ones.

| State | Rule |
|---|---|
| ED | The notice says it is available in English and Eighth Schedule languages, or the snapshot itself offers versions in several Indian languages (e.g. a language switcher listing them). |
| CD | Some Indian languages only, or availability "on request". |
| EE | Explicitly says English only. |

- Always list the languages in `notes`, e.g. `hi, ta, te, mr, gu, kn, ml, or, bn, as`.
- **Never** treat this flag as compliance. The legal reading (all 22 languages?) is unsettled.
- A language switcher counts only if the language names appear in the snapshot text.

---

## 4. The labelling sheet

Create the sheet with `.venv/bin/python -I gold_set/build_evidence.py --init-sheet A1`. You are A1, the only annotator. One row per (policy, flag):

| Column | Fill in |
|---|---|
| `presence` | Present, Absent or Unclear |
| `state` | ED, CD or EE when Present; leave blank otherwise |
| `evidence_ids` | sentence IDs, most important first, separated by `;` |
| `related_ids` | nearby text that informed the decision but isn't evidence (e.g. "improve our services" for AI1) |
| `refers_elsewhere` | yes if the snapshot points to another document for this topic |
| `absence_check` | required for Absent: what you searched and read |
| `notes` | doubts, jurisdiction or scope issues, languages for DPDP4 |
| `labelled_on` | date |

Then run `.venv/bin/python -I gold_set/validate_labels.py --annotator A1`. It checks every rule above, rejects unknown IDs, and writes `labels_A1_resolved.json` with the exact quoted text pulled from the snapshot.

**Suggested order per policy:**
1. Skim the numbered text's headings (5 minutes).
2. Go through the packet flag by flag.
3. Validate.
4. Write down how long it took.

## 5. Decisions recorded here (approved 14 Nov 2026)

1. **Present / Absent / Unclear + ED / CD / EE.** Your three labels sit on top of the five states the scoring uses.
2. **Silence is never EE (R9).** This changes how the draft handled G7, DPDP2 and DPDP3.
3. **Indian-user perspective (R5).** Rights limited to other regions count as CD.
4. **AI1 needs models, ML or AI to be mentioned.** "Improve our services" alone is Absent.
5. **AI2 applies only if AI1 is ED or CD.**
6. **G4 ED needs a concrete period for user content or account data.** Log-only periods are CD.
7. **G1 is labelled but kept out of headline accuracy**, because it will almost always be ED.
8. **Single annotator** (updated 14 Nov 2026; there is no second labeller). The gold set is `labels_A1.csv`, grounded in sentence IDs and search logs and checked by `validate_labels.py`. No inter-annotator agreement (kappa) is reported, and the write-up must state this as a limitation. *Optional, if time allows:* re-label 2 policies at least 3 days later without looking at the first labels, and report self-consistency. This measures your own consistency, not agreement between two people.


## 6. Reference-set protocol (changed 14 Nov 2026, project owner's decision)

The project owner is a single student annotator without legal training and could not label 240 rows from blank in time. The reference set is therefore built by **cross-model pre-fill plus student verification**:

1. **Drafting.** Claude (Anthropic, `claude-opus-5.5`) drafted all 240 labels from the deterministic keyword evidence packets and the saved policy text, applying these guidelines. A different model family from the system under test (Gemini `gemini-3.6-flash`, Google) was chosen on purpose. The draft is recorded in the `drafted_by` column. Ambiguous rows carry `borderline` (two candidate states) and a note.
2. **Independence.** The drafter had not seen any Gemini 3.6 extractor output; the comparison was run only after all 240 labels existed. *Disclosure:* earlier in the same session the drafter had read parts of the Gemini-generated draft gold set (its score matrix and the OpenAI, Anthropic and Razorpay rows). That draft was shown to be unreliable (only 16% of its quotes were real) and was not used.
3. **Verification.** The student reviews every row (using a generated review checklist), borderline rows first, and sets `review_status` to `verified` or `edited` (with a reason in `notes`). Quotes are always resolved from sentence IDs by `validate_labels.py`, so they cannot be invented.
4. **Reporting.** The write-up states that the reference set was LLM-drafted (Claude) and verified by the author. It reports the number of rows verified and edited, and lists these limitations: anchoring bias towards pre-filled labels, no inter-annotator agreement, shared failure modes between LLM families, and a drafter that had seen the earlier Gemini draft.

## 7. Reviewer rulings (decision log)

**14 Nov 2026, review round 1 (project owner):**
- **G2 refined.** CD requires a **first-party** opt-out (a setting, a toggle, the company's own cookie tool or "Do Not Sell" link, honouring GPC) or a ban on ads to minors. Telling users to block cookies in their browser, or to visit third-party ad-network opt-out pages, does **not** count, so the label is ED. Applied to P11 and P14, both edited from CD to ED. P13 and P15 were then changed to ED in round 2.
- **G5 confirmed.** ED when access, correction and deletion are offered to all users, even if the legal-rights section mentions jurisdictions (P04, P14). CD when any of the three is region-gated or missing.
- **DPDP3 confirmed.** ED when a Data Protection Officer, Grievance Officer or Privacy Officer role is designated with a contact route, even a generic inbox (P05, P06, P10, P14). CD when there is only a generic contact with no designated role.
- **Not changed:** the LLM prompt rules (`privascore/flag_rules.json` v1.0) *(later updated to v1.1 with all section-7 clarifications on 14 Nov; v1.0 kept as `flag_rules_v1.0.json`)*, so every Gemini run in this round sees identical instructions. The G2 refinement applies to the reference set only, and the report should mention this.

**14 Nov 2026, review round 2 (project owner), 67 weight-2 borderline rows:**
- **G2:** P13 and P15 changed from CD to ED under the first-party opt-out rule.
- **G3 (new rule, parallel to G2):** when the only control is a third-party ad opt-out, the label is ED (P13, P14 changed from CD to ED).
- **G4 clarified:** a short processing deadline after a deletion request (e.g. "within 5 business days") is an erasure SLA, not a retention period, so the label is CD (P13 changed from ED to CD). A period for logs only, or "until account deletion", is CD.
- **G7 clarified:** a CCPA-style "no knowledge of selling under-16s' data" clause is not a children's age or safeguard rule, so the label is Absent (P08 changed from Unclear to Absent).
- **AI3 clarified:** routine review of content by volunteer human moderators counts as ED (P08 changed from CD to ED).
- **Confirmed as drafted:** G5 region-gated rights = CD; DPDP1 whole-policy browsewrap = EE; and 62 other rows verified.
**14 Nov 2026, review round 3 (project owner): last 17 borderline rows and the spot-check:**
- **Borderline rows:** V1–V17 (G6, DPDP3, DPDP4) confirmed as drafted. All 100 borderline rows have now been reviewed individually.
- **G6 confirmed:** a named mechanism, even if EU-only, = CD; no mechanism named = ED. "US-based company" alone = Absent. A negative-list transfer clause (Razorpay) = Unclear.
- **Spot-check:** 25 of the 139 non-borderline rows were drawn at random (seed 42, `annotations/spotcheck_A1.json`) without reading any extractor output. The reviewer changed 0 labels; the evidence order of S1 was changed. The remaining 113 rows are marked `accepted` (not `verified`).
- **G4 rule (W17) applied to P02:** conversations a user deletes are removed "within 30 days", which is an erasure SLA, so CD. The drafter made this edit for consistency and the reviewer may revert it. P01 and P05 stay ED because they also give an *automatic* 30-day deletion (Temporary Chat / Private Chat).
- **Final tally:** 117 verified · 10 edited · 113 accepted · 0 pending.
