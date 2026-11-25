"""Read an answer: mentions, rank, sentiment, citations.

The analyzer never calls a model. Given the same text and the same citation
list, it returns the same result.
"""

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from aisv.lexicon import NEGATIONS, NEGATIVE, POSITIVE
from aisv.models import (
    AnswerAnalysis,
    AttributedCitation,
    Citation,
    Entity,
    EntityHit,
    PositionMethod,
    ScoreParts,
    Sentiment,
)
from aisv.scoring import (
    citation_factor,
    format_factor,
    position_factor,
    score_from_factors,
    sentiment_factor,
)
from aisv.urls import canonicalize, extract_urls, host_matches, host_of, redact_urls

_TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?|n't")
_LIST_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+(\S.*)$")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_POSITIVE_AT = Decimal("0.2")
_NEGATIVE_AT = Decimal("-0.2")
_SCORE_PLACES = Decimal("0.01")


def analyze_answer(
    text: str,
    citations: tuple[Citation, ...] | list[Citation],
    brand: Entity,
    competitors: tuple[Entity, ...] | list[Entity],
) -> AnswerAnalysis:
    prose = redact_urls(text)
    entities = (brand, *competitors)
    items = _ranking_list(prose)
    hits = _assign_order([_hit(prose, items, entity) for entity in entities], prose, entities)
    brand_hit = hits[0]
    attributed = _attribute(text, citations, entities)
    cited_brand = any(item.role == "brand" for item in attributed)
    sentiment, sentiment_score = _sentiment(prose, brand)
    scale = _scale(brand_hit, items, hits)

    mention = format_factor(Decimal(1 if brand_hit.mentioned else 0))
    position = format_factor(position_factor(brand_hit.position_method, brand_hit.position, scale))
    sentiment_component = format_factor(sentiment_factor(sentiment))
    citation = format_factor(
        citation_factor(mentioned=brand_hit.mentioned, cited_brand=cited_brand)
    )
    parts = ScoreParts(
        mention_factor=mention,
        position_factor=position,
        sentiment_factor=sentiment_component,
        citation_factor=citation,
        visibility=score_from_factors(mention, position, sentiment_component, citation),
    )
    return AnswerAnalysis(
        mentioned=brand_hit.mentioned,
        position=brand_hit.position,
        position_scale=scale,
        position_method=brand_hit.position_method,
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        cited_brand_domain=cited_brand,
        citations=attributed,
        entities=hits,
        parts=parts,
    )


def _scale(hit: EntityHit, items: list[str], hits: tuple[EntityHit, ...]) -> int | None:
    if hit.position_method == "list":
        return len(items)
    if hit.position_method == "order":
        return sum(1 for item in hits if item.position_method == "order")
    return None


def _hit(text: str, items: list[str], entity: Entity) -> EntityHit:
    mentioned = _first_index(text, entity) is not None
    list_rank = _list_rank(items, entity)
    if list_rank is not None:
        return EntityHit(entity.name, entity.role, True, list_rank, "list")
    if items and mentioned:
        # Named in the answer, but not placed in the ranking it actually gave.
        return EntityHit(entity.name, entity.role, True, None, "unranked")
    if not mentioned:
        return EntityHit(entity.name, entity.role, False, None, "none")
    return EntityHit(entity.name, entity.role, True, None, "order")


def _assign_order(
    hits: list[EntityHit], text: str, entities: tuple[Entity, ...]
) -> tuple[EntityHit, ...]:
    """Fill 1-based mention order. A lone prose mention stays unranked."""
    pending = [hit for hit in hits if hit.position_method == "order"]
    if not pending:
        return tuple(hits)
    ranked = sorted(
        pending,
        key=lambda hit: _first_index(text, _entity_named(hit.name, entities)) or 0,
    )
    method: PositionMethod = "order" if len(ranked) > 1 else "unranked"
    order = {hit.name: index for index, hit in enumerate(ranked, start=1)}
    updated: list[EntityHit] = []
    for hit in hits:
        if hit.position_method != "order":
            updated.append(hit)
        elif method == "unranked":
            updated.append(EntityHit(hit.name, hit.role, True, None, "unranked"))
        else:
            updated.append(EntityHit(hit.name, hit.role, True, order[hit.name], "order"))
    return tuple(updated)


def _entity_named(name: str, entities: tuple[Entity, ...]) -> Entity:
    for entity in entities:
        if entity.name == name:
            return entity
    raise KeyError(name)


def _ranking_list(text: str) -> list[str]:
    """Return the longest run of consecutive list items, when it has 2 or more."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        match = _LIST_ITEM.match(line)
        if match:
            current.append(match.group(1).strip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    candidates = [block for block in blocks if len(block) >= 2]
    if not candidates:
        return []
    return max(candidates, key=len)


def _list_rank(items: list[str], entity: Entity) -> int | None:
    for index, item in enumerate(items, start=1):
        if _first_index(item, entity) is not None:
            return index
    return None


def _first_index(text: str, entity: Entity) -> int | None:
    best: int | None = None
    for term in (entity.name, *entity.aliases):
        if not term.strip():
            continue
        match = re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE)
        if match is not None and (best is None or match.start() < best):
            best = match.start()
    return best


def _mentions(text: str, entity: Entity) -> bool:
    return _first_index(text, entity) is not None


def _sentiment(text: str, brand: Entity) -> tuple[Sentiment, str | None]:
    if not _mentions(text, brand):
        return "unmentioned", None
    relevant = [sentence for sentence in _sentences(text) if _mentions(sentence, brand)]
    total = Decimal("0")
    hits = 0
    for sentence in relevant:
        tokens = _tokens(sentence)
        for index, token in enumerate(tokens):
            if token in POSITIVE:
                polarity = Decimal("1")
            elif token in NEGATIVE:
                polarity = Decimal("-1")
            else:
                continue
            window = tokens[max(0, index - 3) : index]
            if any(word in NEGATIONS for word in window):
                polarity *= -1
            total += polarity
            hits += 1
    if hits == 0:
        return "neutral", "0.00"
    score = (total / Decimal(hits)).quantize(_SCORE_PLACES, rounding=ROUND_HALF_UP)
    if score > _POSITIVE_AT:
        label: Sentiment = "positive"
    elif score < _NEGATIVE_AT:
        label = "negative"
    else:
        label = "neutral"
    return label, format(score, "f")


def _sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return [part for part in _SENTENCE_BOUNDARY.split(stripped) if part]


def _tokens(text: str) -> list[str]:
    normalized = re.sub(r"n't\b", " n't", text.lower())
    return _TOKEN.findall(normalized)


def _attribute(
    text: str,
    provided: tuple[Citation, ...] | list[Citation],
    entities: tuple[Entity, ...],
) -> tuple[AttributedCitation, ...]:
    ordered: list[Citation] = []
    seen: set[str] = set()
    for citation in provided:
        canonical = canonicalize(citation.url)
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        provided_host = host_of(canonical) or citation.domain
        ordered.append(Citation(url=canonical, domain=provided_host, title=citation.title))
    for url in extract_urls(text):
        if url in seen:
            continue
        extracted_host = host_of(url)
        if extracted_host is None:
            continue
        seen.add(url)
        ordered.append(Citation(url=url, domain=extracted_host, title=""))

    attributed: list[AttributedCitation] = []
    for citation in ordered:
        owner, role = _owner(citation.domain, entities)
        attributed.append(
            AttributedCitation(
                url=citation.url,
                domain=citation.domain,
                title=citation.title,
                owner=owner,
                role=role,
            )
        )
    return tuple(attributed)


def _owner(
    domain: str, entities: tuple[Entity, ...]
) -> tuple[str, Literal["brand", "competitor", "other"]]:
    for entity in entities:
        if host_matches(domain, entity.domain):
            return entity.name, entity.role
    return "other", "other"
