"""Frozen BERT mapping guard (no model needed)."""
from privascore.bert import CATEGORIES
from privascore.bert_eval import FIT, FLAG_TO_CATEGORY, SHORT, STRONG, UNMAPPED, wilson
from privascore.flags import load_flags


def test_mapping_is_frozen_and_complete():
    all_flags = {f.id for f in load_flags().flags}
    assert set(FLAG_TO_CATEGORY) | set(UNMAPPED) == all_flags and not set(FLAG_TO_CATEGORY) & set(UNMAPPED)
    assert set(UNMAPPED) == {"AI1", "AI3", "AI4", "DPDP4"}
    assert set(FLAG_TO_CATEGORY.values()) <= set(CATEGORIES) and set(SHORT) == set(CATEGORIES)
    assert set(FIT) == set(FLAG_TO_CATEGORY) and [f for f in FIT if FIT[f] == "strong"] == STRONG


def test_wilson():
    lo, hi = wilson(60, 60)
    assert hi == 1.0 and 0.93 < lo < 0.95
