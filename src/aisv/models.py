"""Values that move between config, providers, scoring, storage, and reports."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Role = Literal["brand", "competitor"]
Sentiment = Literal["positive", "neutral", "negative", "unmentioned"]
PositionMethod = Literal["list", "order", "unranked", "none"]


@dataclass(frozen=True)
class Entity:
    name: str
    domain: str
    aliases: tuple[str, ...] = ()
    role: Role = "brand"


@dataclass(frozen=True)
class Prompt:
    id: str
    text: str
    category: str = "general"


@dataclass(frozen=True)
class Project:
    brand: Entity
    competitors: tuple[Entity, ...]
    prompts: tuple[Prompt, ...]
    providers: tuple[str, ...]
    timeout_seconds: float = 90.0
    source: str = ""


@dataclass(frozen=True)
class Citation:
    url: str
    domain: str
    title: str = ""


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model: str
    text: str
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True)
class EntityHit:
    name: str
    role: Role
    mentioned: bool
    position: int | None
    position_method: PositionMethod


@dataclass(frozen=True)
class AttributedCitation:
    url: str
    domain: str
    title: str
    owner: str
    role: Literal["brand", "competitor", "other"]


@dataclass(frozen=True)
class ScoreParts:
    mention_factor: str
    position_factor: str
    sentiment_factor: str
    citation_factor: str
    visibility: str


@dataclass(frozen=True)
class AnswerAnalysis:
    mentioned: bool
    position: int | None
    position_scale: int | None
    position_method: PositionMethod
    sentiment: Sentiment
    sentiment_score: str | None
    cited_brand_domain: bool
    citations: tuple[AttributedCitation, ...]
    entities: tuple[EntityHit, ...]
    parts: ScoreParts


@dataclass(frozen=True)
class StoredCitation:
    url: str
    domain: str
    title: str
    owner: str
    role: str


@dataclass(frozen=True)
class StoredMention:
    entity_name: str
    role: str
    mentioned: bool
    position: int | None
    position_method: str


@dataclass(frozen=True)
class StoredAnswer:
    prompt_id: str
    prompt_text: str
    category: str
    prompt_index: int
    provider: str
    provider_index: int
    model: str
    answer_text: str
    synthetic: bool
    mentioned: bool | None
    position: int | None
    position_scale: int | None
    position_method: str | None
    sentiment: str | None
    sentiment_score: str | None
    visibility_score: str | None
    mention_factor: str | None
    position_factor: str | None
    sentiment_factor: str | None
    citation_factor: str | None
    cited_brand_domain: bool | None
    error: str | None
    citations: tuple[StoredCitation, ...]
    mentions: tuple[StoredMention, ...]


@dataclass(frozen=True)
class StoredRun:
    id: str
    created_at: str
    brand_name: str
    brand_domain: str
    competitors: tuple[Entity, ...]
    providers: tuple[str, ...]
    dry_run: bool
    mock_seed: int | None
    answers: tuple[StoredAnswer, ...]


@dataclass(frozen=True)
class RunSummary:
    """One finished `aisv run`, including answers that failed."""

    run: StoredRun
    visibility: Decimal | None
    mentions: int
    own_domain_citations: int
    successful: int
    failed: int
