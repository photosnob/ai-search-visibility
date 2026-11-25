from collections.abc import Mapping

import httpx
import pytest

from aisv.errors import ProviderError
from aisv.models import Entity
from aisv.providers.base import ANSWER_INSTRUCTIONS, ProviderContext
from aisv.providers.http import HttpxTransport
from aisv.providers.parsing import parse_answer_payload
from aisv.providers.registry import build, known

BRAND = Entity("Northwind", "northwind.example")


class FakeTransport:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.urls: list[str] = []
        self.bodies: list[Mapping[str, object]] = []
        self.headers: list[Mapping[str, str]] = []

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, object],
        timeout: float,
    ) -> object:
        self.urls.append(url)
        self.headers.append(headers)
        self.bodies.append(json_body)
        assert timeout == 90
        return self.payload


def _ctx(env: dict[str, str], transport: FakeTransport | None = None) -> ProviderContext:
    return ProviderContext(
        recorded_name="openai",
        timeout=90,
        mock_seed=0,
        brand=BRAND,
        competitors=(),
        transport=transport,
        env=env,
    )


def test_known_providers() -> None:
    assert set(known()) == {"openai", "perplexity", "mock"}


def test_openai_request_does_not_name_the_brand() -> None:
    transport = FakeTransport(
        {
            "model": "gpt-test",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "A short answer.", "annotations": []}
                    ],
                }
            ],
        }
    )
    provider = build("openai", _ctx({"OPENAI_API_KEY": "test-key"}, transport))
    result = provider.ask("Who makes durable jackets?")
    body = transport.bodies[0]
    assert transport.urls == ["https://api.openai.com/v1/responses"]
    assert body["input"] == "Who makes durable jackets?"
    assert body["instructions"] == ANSWER_INSTRUCTIONS
    assert body["tools"] == [{"type": "web_search"}]
    assert "Northwind" not in str(body)
    assert transport.headers[0]["Authorization"] == "Bearer test-key"
    assert result.model == "gpt-test"
    assert result.text == "A short answer."


def test_openai_reads_citations_from_annotations_and_search_sources() -> None:
    payload = {
        "model": "gpt-6.2-astra",
        "output": [
            {
                "type": "web_search_call",
                "action": {
                    "type": "search",
                    "sources": [{"type": "url", "url": "https://www.northwind.example/guide"}],
                },
            },
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Northwind is reliable.",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url": "https://contoso.example/review",
                                "title": "Review",
                            }
                        ],
                    }
                ],
            },
        ],
    }
    text, citations, model = parse_answer_payload("openai", payload)
    assert model == "gpt-6.2-astra"
    assert text == "Northwind is reliable."
    assert {item.domain for item in citations} == {"northwind.example", "contoso.example"}
    titled = next(item for item in citations if item.domain == "contoso.example")
    assert titled.title == "Review"


def test_perplexity_uses_effort_unless_a_model_is_pinned() -> None:
    transport = FakeTransport(
        {
            "model": "agent",
            "output": [
                {
                    "type": "search_results",
                    "results": [{"url": "https://fabrikam.example/a", "title": "Fabrikam"}],
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Fabrikam comes up. [1]"}],
                },
            ],
        }
    )
    ctx = ProviderContext(
        recorded_name="perplexity",
        timeout=90,
        mock_seed=0,
        brand=BRAND,
        competitors=(),
        transport=transport,
        env={"PERPLEXITY_API_KEY": "test-key"},
    )
    provider = build("perplexity", ctx)
    result = provider.ask("Best fleece?")
    body = transport.bodies[0]
    assert transport.urls == ["https://api.perplexity.ai/v1/agent"]
    assert body["effort"] == "fast"
    assert "model" not in body
    assert body["tools"] == [{"type": "web_search"}]
    assert result.text == "Fabrikam comes up. [1]"
    assert result.citations[0].domain == "fabrikam.example"

    transport.bodies.clear()
    pinned = ProviderContext(
        recorded_name="perplexity",
        timeout=90,
        mock_seed=0,
        brand=BRAND,
        competitors=(),
        transport=transport,
        env={"PERPLEXITY_API_KEY": "test-key", "AISV_PERPLEXITY_MODEL": "openai/gpt-test"},
    )
    build("perplexity", pinned).ask("Best fleece?")
    pinned_body = transport.bodies[0]
    assert pinned_body["model"] == "openai/gpt-test"
    assert "effort" not in pinned_body


def test_legacy_sonar_shape_is_still_readable() -> None:
    text, citations, _model = parse_answer_payload(
        "perplexity",
        {
            "model": "sonar",
            "choices": [{"message": {"content": "Legacy text"}}],
            "citations": ["https://fieldnotes.example/post"],
        },
    )
    assert text == "Legacy text"
    assert citations[0].domain == "fieldnotes.example"


def test_missing_keys() -> None:
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        build("openai", _ctx({}))
    with pytest.raises(ProviderError, match="PERPLEXITY_API_KEY"):
        build(
            "perplexity",
            ProviderContext(
                recorded_name="perplexity",
                timeout=90,
                mock_seed=0,
                brand=BRAND,
                competitors=(),
                transport=None,
                env={},
            ),
        )


def test_http_error_redacts_secrets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret-value"
        return httpx.Response(401, text='{"error":"bad sk-abcdefghijklmn and Bearer secret-value"}')

    transport = HttpxTransport(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ProviderError, match="HTTP 401") as caught:
        build("openai", _ctx({"OPENAI_API_KEY": "secret-value"}, transport)).ask("Hi")
    message = str(caught.value)
    assert "secret-value" not in message
    assert "sk-abcdefghijklmn" not in message
    assert "[redacted]" in message


def test_response_without_text_is_an_error() -> None:
    with pytest.raises(ProviderError, match="did not include answer text"):
        parse_answer_payload("openai", {"output": []})
    with pytest.raises(ProviderError, match="nope"):
        parse_answer_payload("openai", {"status": "failed", "error": {"message": "nope"}})
