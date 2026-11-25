from decimal import Decimal

from aisv.analysis import analyze_answer
from aisv.models import Citation, Entity
from aisv.scoring import score_from_factors

BRAND = Entity("Northwind", "northwind.example", ("Northwind Outfitters",), "brand")
CONTOSO = Entity("Contoso", "contoso.example", role="competitor")
FABRIKAM = Entity("Fabrikam", "fabrikam.example", role="competitor")


def _analyze(text: str, citations: tuple[Citation, ...] = ()) -> object:
    return analyze_answer(text, citations, BRAND, (CONTOSO, FABRIKAM))


def test_word_boundary_and_alias() -> None:
    missed = analyze_answer("The Northwinded coat is durable.", (), BRAND, ())
    assert missed.mentioned is False
    named = analyze_answer("A Northwind coat is durable.", (), BRAND, ())
    assert named.mentioned is True
    alias = analyze_answer("People buy Northwind Outfitters jackets.", (), BRAND, ())
    assert alias.mentioned is True
    shouted = analyze_answer("NORTHWIND shows up in roundups.", (), BRAND, ())
    assert shouted.mentioned is True


def test_list_rank_beats_a_later_prose_mention() -> None:
    text = """
Contoso gets a passing mention before the ranking.

1. Fabrikam is widely stocked.
2. Northwind is a reliable option.
3. Contoso is the budget pick.
"""
    result = analyze_answer(text, (), BRAND, (CONTOSO, FABRIKAM))
    assert result.position_method == "list"
    assert result.position == 2
    assert result.position_scale == 3
    assert result.sentiment == "positive"


def test_named_outside_a_ranking_is_unranked() -> None:
    text = """
I would not start with Northwind.

1. Contoso is the reliable default.
2. Fabrikam is a reasonable alternative.
"""
    result = analyze_answer(text, (), BRAND, (CONTOSO, FABRIKAM))
    assert result.mentioned is True
    assert result.position_method == "unranked"
    assert result.position is None


def test_prose_order_when_there_is_no_list() -> None:
    text = "Contoso and Northwind both come up. Northwind is a practical choice."
    result = analyze_answer(text, (), BRAND, (CONTOSO, FABRIKAM))
    assert result.position_method == "order"
    assert result.position == 2
    assert result.position_scale == 2


def test_lone_mention_is_unranked() -> None:
    result = analyze_answer("Northwind is comfortable.", (), BRAND, (CONTOSO,))
    assert result.position_method == "unranked"
    assert result.parts.position_factor == "0.500000"


def test_negation_flips_a_nearby_polarity_word() -> None:
    negative = analyze_answer("Northwind is not reliable.", (), BRAND, ())
    assert negative.sentiment == "negative"
    positive = analyze_answer("Northwind is never disappointing.", (), BRAND, ())
    assert positive.sentiment == "positive"
    neutral = analyze_answer("Northwind was founded in 1994.", (), BRAND, ())
    assert neutral.sentiment == "neutral"
    assert neutral.sentiment_score == "0.00"


def test_urls_are_citations_not_mentions() -> None:
    text = "See https://www.northwind.example/guide. for the spec."
    result = analyze_answer(text, (), BRAND, (CONTOSO,))
    assert result.mentioned is False
    assert result.cited_brand_domain is True
    assert result.citations[0].domain == "northwind.example"
    assert result.citations[0].url == "https://northwind.example/guide"
    assert result.parts.visibility == "15.0"


def test_host_matching_rejects_a_lookalike_domain() -> None:
    citations = (
        Citation("https://shop.northwind.example/a", "", ""),
        Citation("https://northwind.example.evil.test/a", "", ""),
        Citation("https://notnorthwind.example/a", "", ""),
        Citation("https://contoso.example/a", "", "Contoso"),
    )
    result = analyze_answer("No brand is named here.", citations, BRAND, (CONTOSO,))
    owners = {item.domain: item.owner for item in result.citations}
    assert owners["shop.northwind.example"] == "Northwind"
    assert owners["northwind.example.evil.test"] == "other"
    assert owners["notnorthwind.example"] == "other"
    assert owners["contoso.example"] == "Contoso"


def test_provider_citation_is_kept_when_the_text_has_no_url() -> None:
    citations = (Citation("https://northwind.example/journal", "northwind.example", "Journal"),)
    result = analyze_answer("Northwind is a practical choice.", citations, BRAND, ())
    assert result.cited_brand_domain is True
    assert result.citations[0].title == "Journal"


def test_score_recomputes_from_the_stored_factors() -> None:
    result = analyze_answer(
        "1. Northwind is reliable.\n2. Contoso is ordinary.",
        (Citation("https://northwind.example/", "", ""),),
        BRAND,
        (CONTOSO,),
    )
    recomputed = score_from_factors(
        result.parts.mention_factor,
        result.parts.position_factor,
        result.parts.sentiment_factor,
        result.parts.citation_factor,
    )
    assert recomputed == result.parts.visibility
    assert Decimal(result.parts.visibility) == Decimal("100.0")
