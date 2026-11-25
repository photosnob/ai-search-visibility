"""Perplexity Agent API with web search.

Docs: https://docs.perplexity.ai/docs/agent-api/quickstart

By default the request sends `effort` and the web_search tool, and does not
pin a third-party model. That asks Perplexity's own grounded search, which is
the product a visibility run is trying to measure. Set AISV_PERPLEXITY_MODEL
to pin a model instead; the effort field is then omitted.
"""

from aisv import __version__
from aisv.errors import ProviderError
from aisv.models import ProviderResponse
from aisv.providers.base import ANSWER_INSTRUCTIONS, ProviderContext, Transport
from aisv.providers.http import HttpFailure, HttpxTransport
from aisv.providers.parsing import parse_answer_payload

_DEFAULT_EFFORT = "fast"
_DEFAULT_BASE = "https://api.perplexity.ai"


class PerplexityProvider:
    def __init__(
        self,
        *,
        name: str,
        model_label: str,
        api_key: str,
        base_url: str,
        timeout: float,
        transport: Transport,
        effort: str | None,
        pinned_model: str | None,
    ) -> None:
        self._name = name
        self._model_label = model_label
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport
        self._effort = effort
        self._pinned_model = pinned_model

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model_label

    def ask(self, prompt: str) -> ProviderResponse:
        payload: dict[str, object] = {
            "tools": [{"type": "web_search"}],
            "instructions": ANSWER_INSTRUCTIONS,
            "input": prompt,
        }
        if self._pinned_model:
            payload["model"] = self._pinned_model
        elif self._effort:
            payload["effort"] = self._effort
        try:
            data = self._transport.post_json(
                f"{self._base_url}/v1/agent",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": f"aisv/{__version__}",
                },
                json_body=payload,
                timeout=self._timeout,
            )
        except HttpFailure as exc:
            raise ProviderError(self._name, str(exc)) from exc
        text, citations, reported_model = parse_answer_payload(self._name, data)
        model = reported_model if reported_model != "unknown" else self._model_label
        return ProviderResponse(provider=self._name, model=model, text=text, citations=citations)


def factory(ctx: ProviderContext) -> PerplexityProvider:
    key = ctx.env.get("PERPLEXITY_API_KEY", "").strip()
    if not key:
        raise ProviderError("perplexity", "PERPLEXITY_API_KEY is not set")
    pinned = ctx.env.get("AISV_PERPLEXITY_MODEL", "").strip() or None
    effort = ctx.env.get("AISV_PERPLEXITY_EFFORT", "").strip() or _DEFAULT_EFFORT
    if pinned:
        label = pinned
        effort_value: str | None = None
    else:
        label = f"perplexity-effort:{effort}"
        effort_value = effort
    base = ctx.env.get("AISV_PERPLEXITY_BASE_URL", "").strip() or _DEFAULT_BASE
    return PerplexityProvider(
        name=ctx.recorded_name,
        model_label=label,
        api_key=key,
        base_url=base,
        timeout=ctx.timeout,
        transport=ctx.transport or HttpxTransport(),
        effort=effort_value,
        pinned_model=pinned,
    )


def describe() -> str:
    return "Perplexity Agent API with web_search. Requires PERPLEXITY_API_KEY."
