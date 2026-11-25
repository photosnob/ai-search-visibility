"""Pull answer text and citations out of provider JSON.

OpenAI Responses and the Perplexity Agent API both return an `output` array.
The legacy Perplexity Sonar shape (choices, top-level citations) is accepted
too, so a proxy that still speaks that dialect is readable.
"""

from aisv.errors import ProviderError
from aisv.models import Citation
from aisv.urls import canonicalize, host_of


def parse_answer_payload(provider: str, data: object) -> tuple[str, tuple[Citation, ...], str]:
    if not isinstance(data, dict):
        raise ProviderError(provider, "response was not a JSON object")
    error_message = _error_message(data.get("error"))
    status = data.get("status")
    texts: list[str] = []
    citations: list[Citation] = []

    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            _read_output_item(item, texts, citations)

    _read_legacy_choice(data.get("choices"), texts)
    citations.extend(_url_list(data.get("citations")))
    citations.extend(_result_list(data.get("search_results")))

    text = "\n".join(part.strip() for part in texts if part.strip()).strip()
    model = data.get("model")
    model_name = model.strip() if isinstance(model, str) and model.strip() else "unknown"
    if not text:
        if error_message:
            raise ProviderError(provider, error_message)
        if status in {"failed", "incomplete"}:
            raise ProviderError(provider, f"response status is {status}")
        raise ProviderError(provider, "response did not include answer text")
    return text, _dedupe(citations), model_name


def _read_output_item(item: dict[str, object], texts: list[str], citations: list[Citation]) -> None:
    kind = item.get("type")
    if kind == "message":
        content = item.get("content")
        if isinstance(content, str):
            texts.append(content)
            return
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") in {"output_text", "text"} and isinstance(
                    part.get("text"), str
                ):
                    text = part.get("text")
                    if isinstance(text, str):
                        texts.append(text)
                citations.extend(_annotations(part.get("annotations")))
        return
    if kind == "search_results":
        citations.extend(_result_list(item.get("results")))
        return
    if kind == "web_search_call":
        action = item.get("action")
        if isinstance(action, dict):
            citations.extend(_result_list(action.get("sources")))


def _read_legacy_choice(choices: object, texts: list[str]) -> None:
    if not isinstance(choices, list) or not choices:
        return
    first = choices[0]
    if not isinstance(first, dict):
        return
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)


def _annotations(value: object) -> list[Citation]:
    if not isinstance(value, list):
        return []
    found: list[Citation] = []
    for item in value:
        if not isinstance(item, dict) or item.get("type") != "url_citation":
            continue
        url = item.get("url")
        title = item.get("title")
        citation = _citation(url, title if isinstance(title, str) else "")
        if citation is not None:
            found.append(citation)
    return found


def _result_list(value: object) -> list[Citation]:
    if not isinstance(value, list):
        return []
    found: list[Citation] = []
    for item in value:
        if isinstance(item, str):
            citation = _citation(item, "")
        elif isinstance(item, dict):
            title = item.get("title")
            citation = _citation(item.get("url"), title if isinstance(title, str) else "")
        else:
            citation = None
        if citation is not None:
            found.append(citation)
    return found


def _url_list(value: object) -> list[Citation]:
    if not isinstance(value, list):
        return []
    found: list[Citation] = []
    for item in value:
        if isinstance(item, str):
            citation = _citation(item, "")
            if citation is not None:
                found.append(citation)
    return found


def _citation(url: object, title: str) -> Citation | None:
    if not isinstance(url, str):
        return None
    canonical = canonicalize(url)
    if canonical is None:
        return None
    domain = host_of(canonical)
    if domain is None:
        return None
    return Citation(url=canonical, domain=domain, title=title.strip())


def _dedupe(citations: list[Citation]) -> tuple[Citation, ...]:
    kept: list[Citation] = []
    seen: set[str] = set()
    for citation in citations:
        if citation.url in seen:
            continue
        seen.add(citation.url)
        kept.append(citation)
    return tuple(kept)


def _error_message(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()[:300]
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()[:300]
    return None
