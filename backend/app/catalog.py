"""UI labels that are not in the pipeline's own data files (_local/team.md appendices A and B).

Flag questions, types and weights come from gold_set/flag_definitions.json via load_flags();
the per-flag ED/CD/EE meanings come from privascore/flag_rules.json via load_rules(). Only the
titles, the grouping and the two shared state texts are new labels for this app.
"""
from __future__ import annotations

# id -> (title, group). Group is general | ai | dpdp.
FLAGS: dict[str, tuple[str, str]] = {
    "G1": ("Data the company collects", "general"),
    "G2": ("Selling or sharing data for ads", "general"),
    "G3": ("Profiling and automated decisions", "general"),
    "G4": ("How long data is kept", "general"),
    "G5": ("Access, correction and deletion", "general"),
    "G6": ("Transfers to other countries", "general"),
    "G7": ("Children and minors", "general"),
    "AI1": ("Training AI on your data", "ai"),
    "AI2": ("Opting out of AI training", "ai"),
    "AI3": ("People reading your content", "ai"),
    "AI4": ("De-identified and aggregated data", "ai"),
    "AI5": ("Outside AI providers", "ai"),
    "DPDP1": ("How consent is obtained", "dpdp"),
    "DPDP2": ("Withdrawing consent", "dpdp"),
    "DPDP3": ("Grievance or data protection officer", "dpdp"),
    "DPDP4": ("Notice in Indian languages", "dpdp"),
}

GROUP_TITLES = {"general": "General practices", "ai": "AI practices", "dpdp": "India DPDP readiness"}

STATE_LABELS = {"ED": "Disclosed", "CD": "Conditional", "EE": "Excluded",
                "NS": "Not stated", "UN": "Unclear"}

# ED/CD/EE are per-flag (flag_rules.json). These two are shared across all 16 flags.
SHARED_STATE_MEANINGS = {
    "NS": "The policy says nothing usable about this practice.",
    "UN": "The policy addresses this, but the wording is contradictory or too vague to classify.",
}


def title(flag_id: str) -> str:
    return FLAGS[flag_id][0]


def group(flag_id: str) -> str:
    return FLAGS[flag_id][1]


def state_meaning(rules: dict, flag_id: str, state: str) -> str:
    """The exact text the model was given for ED/CD/EE; the shared text for NS/UN."""
    if state in SHARED_STATE_MEANINGS:
        return SHARED_STATE_MEANINGS[state]
    return rules["flags"][flag_id].get(state, "")
