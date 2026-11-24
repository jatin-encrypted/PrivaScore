"""Readability / vagueness checks."""
import pytest

from privascore.textstats import VAGUE_TERMS, analyse, count_syllables, is_prose


@pytest.mark.parametrize("word,n", [("cat", 1), ("data", 2), ("privacy", 3), ("information", 4),
                                    ("table", 2), ("possible", 3), ("shared", 1), ("deleted", 3),
                                    ("personal", 3), ("policy", 3), ("we", 1), ("user's", 2)])
def test_syllables(word, n):
    assert count_syllables(word) == n


def test_flesch_matches_formula_by_hand():
    # 2 prose sentences, 8 + 6 = 14 words; syllables: 13 one-syllable words + "data" (2) = 15
    t = "We do not sell the data you give.\nWe keep it for one year.\n"
    s = analyse(t)
    assert (s.sentences, s.words, s.syllables) == (2, 14, 15)
    wps, spw = s.words / s.sentences, s.syllables / s.words
    assert s.flesch_reading_ease == round(206.835 - 1.015 * wps - 84.6 * spw, 1)
    assert s.fk_grade == round(0.39 * wps + 11.8 * spw - 15.59, 1)


def test_harder_text_scores_harder():
    easy = "We do not sell your data to anyone at all.\nYou can ask us to delete it at any time you like.\n"
    hard = ("Notwithstanding the foregoing, personal information may be disclosed to affiliated organisations "
            "for legitimate operational purposes consistent with applicable regulatory obligations.\n")
    assert analyse(hard).fk_grade > analyse(easy).fk_grade + 5
    assert analyse(hard).flesch_reading_ease < analyse(easy).flesch_reading_ease


def test_vague_cues_by_category_and_traceable():
    t = ("Privacy Policy\n"
         "We may share certain information with partners as necessary to provide the service.\n"
         "We delete your chats 30 days after you close your account.\n")
    s = analyse(t)
    assert s.sentences == 2 and s.vague_sentence_fraction == 0.5 and s.multi_category_fraction == 0.5
    v = s.top_vague[0]
    assert v.sid == "p002.s1" and set(v.categories) == {"modality", "numeric_quantifier", "conditionality"}
    assert v.categories["modality"] == ["may"] and "as necessary" in v.categories["conditionality"]


def test_month_may_is_not_a_cue():
    s = analyse("This policy was last updated on May 26, 2026 and replaces the earlier version.\n")
    assert s.vague_sentence_fraction == 0


def test_navigation_and_headings_are_not_prose():
    assert not is_prose("Privacy Policy")
    assert not is_prose("Home Payments Links")
    assert is_prose("We collect information that you provide to us directly.")


def test_lexicon_has_four_categories():
    assert set(VAGUE_TERMS) == {"conditionality", "generalization", "modality", "numeric_quantifier"}
