"""Provider names the CLI knows about.

Registering a new engine is a factory plus a call to `register`.
The factory receives a ProviderContext and returns an object with `ask`.
"""

from collections.abc import Callable

from aisv.errors import ConfigError
from aisv.providers.base import AnswerProvider, ProviderContext
from aisv.providers.mock import MockProvider
from aisv.providers.mock import describe as describe_mock
from aisv.providers.mock import factory as mock_factory
from aisv.providers.openai import describe as describe_openai
from aisv.providers.openai import factory as openai_factory
from aisv.providers.perplexity import describe as describe_perplexity
from aisv.providers.perplexity import factory as perplexity_factory

Factory = Callable[[ProviderContext], AnswerProvider]
CatalogEntry = tuple[Factory, str]

_FACTORIES: dict[str, CatalogEntry] = {}


def register(name: str, factory: Factory, description: str) -> None:
    _FACTORIES[name.strip().lower()] = (factory, description)


def known() -> tuple[str, ...]:
    _ensure()
    return tuple(sorted(_FACTORIES))


def description(name: str) -> str:
    _ensure()
    return _lookup(name)[1]


def build(name: str, ctx: ProviderContext) -> AnswerProvider:
    _ensure()
    factory, _blurb = _lookup(name)
    return factory(ctx)


def build_mock(ctx: ProviderContext) -> MockProvider:
    return mock_factory(ctx)


def _lookup(name: str) -> CatalogEntry:
    key = name.strip().lower()
    if key not in _FACTORIES:
        known_names = ", ".join(sorted(_FACTORIES)) or "(none)"
        raise ConfigError(f"unknown provider {name!r}. Known providers: {known_names}.")
    return _FACTORIES[key]


def _ensure() -> None:
    if _FACTORIES:
        return
    register("openai", openai_factory, describe_openai())
    register("perplexity", perplexity_factory, describe_perplexity())
    register("mock", mock_factory, describe_mock())
