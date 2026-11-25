"""OpenAI Responses API with the hosted web_search tool.

Docs: https://developers.openai.com/api/docs/guides/tools-web-search
The default model is the one the web-search guide uses. Override it with
AISV_OPENAI_MODEL when your account should call a different model.
"""

from aisv import __version__
from aisv.errors import ProviderError
from aisv.models import ProviderResponse
from aisv.providers.base import ANSWER_INSTRUCTIONS, ProviderContext, Transport
from aisv.providers.http import HttpFailure, HttpxTransport
from aisv.providers.parsing import parse_answer_payload

_DEFAULT_MODEL = "gpt-6.2-astra"
_DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAIProvider:
    def __init__(
        self,
        *,
        name: str,
        model: str,
        api_key: str,
        base_url: str,
        timeout: float,
        transport: Transport,
    ) -> None:
        self._name = name
        self._model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    def ask(self, prompt: str) -> ProviderResponse:
        payload: dict[str, object] = {
            "model": self._model,
            "tools": [{"type": "web_search"}],
            "instructions": ANSWER_INSTRUCTIONS,
            "input": prompt,
        }
        try:
            data = self._transport.post_json(
                f"{self._base_url}/responses",
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
        text, citations, model = parse_answer_payload(self._name, data)
        reported = model if model != "unknown" else self._model
        return ProviderResponse(
            provider=self._name,
            model=reported,
            text=text,
            citations=citations,
        )


def factory(ctx: ProviderContext) -> OpenAIProvider:
    key = ctx.env.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ProviderError("openai", "OPENAI_API_KEY is not set")
    model = ctx.env.get("AISV_OPENAI_MODEL", "").strip() or _DEFAULT_MODEL
    base = ctx.env.get("AISV_OPENAI_BASE_URL", "").strip() or _DEFAULT_BASE
    return OpenAIProvider(
        name=ctx.recorded_name,
        model=model,
        api_key=key,
        base_url=base,
        timeout=ctx.timeout,
        transport=ctx.transport or HttpxTransport(),
    )


def describe() -> str:
    return "OpenAI Responses API with the web_search tool. Requires OPENAI_API_KEY."
