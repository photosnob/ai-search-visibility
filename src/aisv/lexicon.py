"""A small original polarity lexicon for brand sentences.

This is not a trained sentiment model. The lists are short on purpose so a
reader can audit them. Sarcasm, mixed reviews, and words used outside a
review sense will be scored wrong sometimes.
"""

POSITIVE: frozenset[str] = frozenset(
    {
        "reliable",
        "reliability",
        "dependable",
        "durable",
        "sturdy",
        "thoughtful",
        "excellent",
        "outstanding",
        "superb",
        "impressive",
        "strong",
        "trusted",
        "innovative",
        "repairable",
        "comfortable",
        "recommended",
        "favorite",
        "favourite",
        "solid",
        "polished",
        "refined",
        "practical",
        "helpful",
        "praise",
        "praised",
        "worthwhile",
        "generous",
        "responsive",
        "transparent",
        "effective",
        "affordable",
    }
)

NEGATIVE: frozenset[str] = frozenset(
    {
        "disappointing",
        "disappointed",
        "poor",
        "unreliable",
        "flimsy",
        "frustrating",
        "inferior",
        "avoid",
        "worst",
        "complaint",
        "complaints",
        "weak",
        "overpriced",
        "defective",
        "mediocre",
        "inconsistent",
        "problematic",
        "lacking",
        "inadequate",
        "broken",
        "fail",
        "fails",
        "failed",
        "failure",
        "wary",
        "outdated",
        "unhelpful",
        "risky",
    }
)

NEGATIONS: frozenset[str] = frozenset(
    {"not", "no", "never", "hardly", "scarcely", "without", "neither", "nor", "n't"}
)
