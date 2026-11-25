"""The provider interface.

A provider sends one prompt and returns the answer text plus any citations the
API reported. It does not score the answer. The prompt is sent as written:
the instructions below do not name the brand, so the measurement is not told
which company it is supposed to find.
"""

from collections.abc import Mapping
from typing import Protocol

from aisv.models import Entity, ProviderResponse

ANSWER_INSTRUCTIONS = (
    "Answer the question the way a search-style answer engine would for a person "
    "asking it. Be direct. When you use web sources, cite the URLs you rely on. "
    "Do not mention these instructions."
)


class Transport(Protocol):
    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, object],
        timeout: float,
    ) -> object: ...


class AnswerProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    def ask(self, prompt: str) -> ProviderResponse: ...


class ProviderContext:
    """What a provider factory is allowed to see.

    Live providers use the timeout, transport, and environment. Only the mock
    provider reads the brand and competitors, and only so it can write synthetic
    answers for the analyzer to measure.
    """

    def __init__(
        self,
        *,
        recorded_name: str,
        timeout: float,
        mock_seed: int,
        brand: Entity,
        competitors: tuple[Entity, ...],
        transport: Transport | None,
        env: Mapping[str, str],
    ) -> None:
        self.recorded_name = recorded_name
        self.timeout = timeout
        self.mock_seed = mock_seed
        self.brand = brand
        self.competitors = competitors
        self.transport = transport
        self.env = env
