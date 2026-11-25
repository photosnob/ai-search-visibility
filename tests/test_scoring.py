from decimal import Decimal
from pathlib import Path

from aisv.scoring import (
    CITATION_WEIGHT,
    MENTION_WEIGHT,
    POSITION_WEIGHT,
    SENTIMENT_WEIGHT,
    arithmetic_paragraph,
    failed_answers_paragraph,
    mean_scores,
    methodology_paragraph,
    score_from_factors,
    share_of_voice_paragraph,
)


def test_weights_sum_to_one() -> None:
    assert MENTION_WEIGHT + POSITION_WEIGHT + SENTIMENT_WEIGHT + CITATION_WEIGHT == 1


def test_score_uses_rounded_components() -> None:
    # Position 2 of 3 is 2/3, which quantizes to 0.666667 before weighting.
    score = score_from_factors("1.000000", "0.666667", "1.000000", "1.000000")
    raw = (
        MENTION_WEIGHT * Decimal("1.000000")
        + POSITION_WEIGHT * Decimal("0.666667")
        + SENTIMENT_WEIGHT * Decimal("1.000000")
        + CITATION_WEIGHT * Decimal("1.000000")
    ) * 100
    assert score == f"{raw.quantize(Decimal('0.1'))}"


def test_unranked_negative_mention_without_a_citation() -> None:
    score = score_from_factors("1.000000", "0.500000", "0.200000", "0.400000")
    assert score == "62.5"


def test_mean_rounds_half_up() -> None:
    assert mean_scores(["70.5", "71.0"]) == "70.8"
    assert mean_scores([]) is None


def test_methodology_names_the_weights() -> None:
    text = methodology_paragraph()
    assert "0.40" in text
    assert "0.25" in text
    assert "0.20" in text
    assert "0.15" in text
    assert "Share of voice is separate" in text


def test_readme_prints_the_scoring_contract() -> None:
    readme = Path(__file__).resolve().parents[1].joinpath("README.md").read_text(encoding="utf-8")
    assert methodology_paragraph() in readme
    assert arithmetic_paragraph() in readme
    assert share_of_voice_paragraph() in readme
    assert failed_answers_paragraph() in readme
    assert "Sample data" in readme
    assert "not a benchmark" in readme
