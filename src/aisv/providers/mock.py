"""Synthetic answers for tests, dry runs, and the committed sample report.

The mock provider never calls a network. It writes text that mentions the
configured names, and the real analyzer scores that text. The numbers in a
dry run are measurements of these sentences, not of a live brand.

Which scenario a prompt lands on is a stable hash of the seed, the provider
name, and the prompt text. Change `--mock-seed` to get a different, repeatable
set of answers.
"""

import hashlib

from aisv.models import Citation, Entity, ProviderResponse
from aisv.providers.base import ProviderContext

_OTHER = "https://fieldnotes.example/roundup"


class MockProvider:
    def __init__(
        self,
        *,
        name: str,
        seed: int,
        brand: Entity,
        competitors: tuple[Entity, ...],
    ) -> None:
        self._name = name
        self._seed = seed
        self._brand = brand
        self._competitors = competitors

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return "mock"

    def ask(self, prompt: str) -> ProviderResponse:
        text, citations = render(self._brand, self._competitors, prompt, self._name, self._seed)
        return ProviderResponse(
            provider=self._name, model=self.model, text=text, citations=citations
        )


def render(
    brand: Entity,
    competitors: tuple[Entity, ...],
    prompt: str,
    provider: str,
    seed: int,
) -> tuple[str, tuple[Citation, ...]]:
    scenarios = _available(len(competitors))
    digest = hashlib.sha256(f"{seed}|{provider}|{prompt}".encode()).digest()
    name = scenarios[digest[0] % len(scenarios)]
    return _SCENARIOS[name](brand, competitors)


def factory(ctx: ProviderContext) -> MockProvider:
    return MockProvider(
        name=ctx.recorded_name,
        seed=ctx.mock_seed,
        brand=ctx.brand,
        competitors=ctx.competitors,
    )


def describe() -> str:
    return "Synthetic answers for dry runs and tests. No network, and not a measurement."


def _available(competitor_count: int) -> tuple[str, ...]:
    if competitor_count == 0:
        return ("sole_positive", "sole_negative")
    return (
        "brand_leads",
        "competitor_leads",
        "prose_shared",
        "brand_missing",
        "brand_negative",
        "sole_positive",
    )


def _brand_leads(
    brand: Entity, competitors: tuple[Entity, ...]
) -> tuple[str, tuple[Citation, ...]]:
    first = competitors[0]
    lines = [
        "For a question like this, a short list is more useful than a long survey.",
        "",
        f"1. {brand.name} is a reliable and thoughtful option. https://{brand.domain}/guide",
        f"2. {first.name} is widely stocked, with an ordinary finish. https://{first.domain}/",
    ]
    citations = [
        Citation(f"https://{brand.domain}/guide", brand.domain, f"{brand.name} guide"),
        Citation(f"https://{first.domain}/", first.domain, ""),
    ]
    if len(competitors) > 1:
        second = competitors[1]
        lines.append(f"3. {second.name} is the budget alternative. https://{second.domain}/")
        citations.append(Citation(f"https://{second.domain}/", second.domain, ""))
    lines.append("")
    lines.append(f"{brand.name} is the one to start with if you want something repairable.")
    return "\n".join(lines), tuple(citations)


def _competitor_leads(
    brand: Entity, competitors: tuple[Entity, ...]
) -> tuple[str, tuple[Citation, ...]]:
    first = competitors[0]
    lines = [
        f"1. {first.name} is the reliable default. https://{first.domain}/",
        (
            f"2. {brand.name} is a solid alternative if you already like the fit. "
            f"https://{brand.domain}/fit"
        ),
    ]
    citations = [
        Citation(f"https://{first.domain}/", first.domain, ""),
        Citation(f"https://{brand.domain}/fit", brand.domain, ""),
    ]
    if len(competitors) > 1:
        second = competitors[1]
        lines.append(f"3. {second.name} is easy to find and unremarkable. https://{second.domain}/")
        citations.append(Citation(f"https://{second.domain}/", second.domain, ""))
    return "\n".join(lines), tuple(citations)


def _prose_shared(
    brand: Entity, competitors: tuple[Entity, ...]
) -> tuple[str, tuple[Citation, ...]]:
    first = competitors[0]
    text = (
        f"{first.name} and {brand.name} both come up for this. "
        f"{brand.name} is a practical choice, while {first.name} is easier to find in stores."
    )
    citations = (
        Citation(f"https://{brand.domain}/journal", brand.domain, "Journal"),
        Citation(_OTHER, "fieldnotes.example", "Roundup"),
    )
    return text, citations


def _brand_missing(
    brand: Entity, competitors: tuple[Entity, ...]
) -> tuple[str, tuple[Citation, ...]]:
    del brand
    first = competitors[0]
    other = competitors[1] if len(competitors) > 1 else first
    text = (
        f"1. {first.name} is the name that comes up most often. https://{first.domain}/jackets\n"
        f"2. {other.name} is a reasonable alternative. https://guides.example/roundup"
    )
    return text, ()


def _brand_negative(
    brand: Entity, competitors: tuple[Entity, ...]
) -> tuple[str, tuple[Citation, ...]]:
    first = competitors[0]
    text = (
        f"{brand.name} looks polished in the photos, but owner writeups call the fit "
        f"disappointing and the warranty poor. {first.name} is described as more reliable "
        f"for the same use. https://{first.domain}/reviews"
    )
    return text, ()


def _sole_positive(
    brand: Entity, competitors: tuple[Entity, ...]
) -> tuple[str, tuple[Citation, ...]]:
    del competitors
    text = (
        f"{brand.name} is a dependable and comfortable option for this. "
        f"The buying guide is straightforward. https://{brand.domain}/guide"
    )
    return text, ()


def _sole_negative(
    brand: Entity, competitors: tuple[Entity, ...]
) -> tuple[str, tuple[Citation, ...]]:
    del competitors
    return f"{brand.name} has a disappointing fit and a poor warranty.", ()


_SCENARIOS = {
    "brand_leads": _brand_leads,
    "competitor_leads": _competitor_leads,
    "prose_shared": _prose_shared,
    "brand_missing": _brand_missing,
    "brand_negative": _brand_negative,
    "sole_positive": _sole_positive,
    "sole_negative": _sole_negative,
}
