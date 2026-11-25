"""Visibility score.

The score is a weighted sum, not a model of traffic or revenue. Share of voice
is reported beside it and is not an input.
"""

from decimal import ROUND_HALF_UP, Decimal

from aisv.models import Sentiment

MENTION_WEIGHT = Decimal("0.40")
POSITION_WEIGHT = Decimal("0.25")
SENTIMENT_WEIGHT = Decimal("0.20")
CITATION_WEIGHT = Decimal("0.15")

UNRANKED_POSITION = Decimal("0.5")
CITATION_IF_MENTIONED = Decimal("0.4")
POSITIVE_SENTIMENT = Decimal("1")
NEUTRAL_SENTIMENT = Decimal("0.6")
NEGATIVE_SENTIMENT = Decimal("0.2")

_FACTOR = Decimal("0.000001")
_SCORE = Decimal("0.1")

_SENTIMENT_FACTOR: dict[Sentiment, Decimal] = {
    "positive": POSITIVE_SENTIMENT,
    "neutral": NEUTRAL_SENTIMENT,
    "negative": NEGATIVE_SENTIMENT,
    "unmentioned": Decimal("0"),
}


def methodology_paragraph() -> str:
    """The scoring contract. Reports and the README both print this text."""
    return (
        "Each successful answer is scored from 0 to 100. "
        f"The score is 100 × (mention × {MENTION_WEIGHT} + position × {POSITION_WEIGHT} + "
        f"sentiment × {SENTIMENT_WEIGHT} + citation × {CITATION_WEIGHT}). "
        "Mention is 1 when the brand name or an alias appears as a whole word, otherwise 0. "
        "Position is (N − rank + 1) / N when the brand is placed in a list of N items or "
        f"among N tracked names in prose; a mention that is not ranked scores {UNRANKED_POSITION}. "
        "Sentiment uses the sentences that name the brand: "
        f"positive {POSITIVE_SENTIMENT}, neutral {NEUTRAL_SENTIMENT}, "
        f"negative {NEGATIVE_SENTIMENT}, and 0 when the brand is absent. "
        "Citation is 1 when a cited host is the brand domain, "
        f"{CITATION_IF_MENTIONED} when the brand is mentioned but not cited, and 0 otherwise. "
        "Share of voice is separate and is not part of this score."
    )


def arithmetic_paragraph() -> str:
    return (
        "Mention, position, sentiment, and citation components are rounded to 6 decimal "
        "places before weighting. The weighted sum is multiplied by 100 and rounded half "
        "up to 1 decimal place. answers.csv stores the components, so the score can be "
        "recomputed from the file."
    )


def share_of_voice_paragraph() -> str:
    return (
        "Mention share of voice is the brand's mentions divided by all mentions of the "
        "brand and the configured competitors. An answer that names three tracked brands "
        "counts three times, once each. Citation share is the same ratio over cited URLs "
        "whose host matches a tracked domain. Citations to anyone else are reported as "
        "other and are left out of the share. A run with no tracked mentions has no share."
    )


def failed_answers_paragraph() -> str:
    return (
        "Answers that fail, including timeouts and HTTP errors, are stored with the error "
        "and left out of averages, mention rate, and share of voice. An outage is not "
        "treated as a visibility of zero."
    )


def quantize_factor(value: Decimal) -> Decimal:
    return value.quantize(_FACTOR, rounding=ROUND_HALF_UP)


def format_factor(value: Decimal) -> str:
    return format(quantize_factor(value), "f")


def format_score(value: Decimal) -> str:
    return format(value.quantize(_SCORE, rounding=ROUND_HALF_UP), "f")


def position_factor(method: str, position: int | None, scale: int | None) -> Decimal:
    if method == "unranked":
        return UNRANKED_POSITION
    if method in {"list", "order"} and position is not None and scale:
        return Decimal(scale - position + 1) / Decimal(scale)
    return Decimal("0")


def sentiment_factor(sentiment: Sentiment) -> Decimal:
    return _SENTIMENT_FACTOR[sentiment]


def citation_factor(*, mentioned: bool, cited_brand: bool) -> Decimal:
    if cited_brand:
        return Decimal("1")
    if mentioned:
        return CITATION_IF_MENTIONED
    return Decimal("0")


def score_from_factors(
    mention_factor: str,
    position_factor_value: str,
    sentiment_factor_value: str,
    citation_factor_value: str,
) -> str:
    """Score the components exactly as they are stored in the CSV."""
    raw = (
        MENTION_WEIGHT * Decimal(mention_factor)
        + POSITION_WEIGHT * Decimal(position_factor_value)
        + SENTIMENT_WEIGHT * Decimal(sentiment_factor_value)
        + CITATION_WEIGHT * Decimal(citation_factor_value)
    )
    return format_score(raw * Decimal(100))


def mean_scores(scores: list[str]) -> str | None:
    if not scores:
        return None
    total = sum((Decimal(score) for score in scores), Decimal("0"))
    return format_score(total / Decimal(len(scores)))
