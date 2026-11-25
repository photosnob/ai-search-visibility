"""Load a project from YAML, with prompts optionally coming from CSV."""

import csv
import re
from pathlib import Path

import yaml

from aisv.errors import ConfigError
from aisv.models import Entity, Project, Prompt

_ID = re.compile(r"[^a-z0-9]+")


def load_project(
    path: Path,
    *,
    prompts_csv: Path | None = None,
    providers: tuple[str, ...] | None = None,
) -> Project:
    payload = _read_yaml(path)
    brand = _entity(_require_mapping(payload.get("brand"), "brand"), role="brand")
    competitors = tuple(
        _entity(_require_mapping(item, "competitors"), role="competitor")
        for item in _sequence(payload.get("competitors", []), "competitors")
    )
    _check_entities(brand, competitors)

    prompts = list(_prompts_from_yaml(payload.get("prompts", [])))
    file_value = payload.get("prompts_file")
    if file_value is not None:
        if not isinstance(file_value, str) or not file_value.strip():
            raise ConfigError("prompts_file must be a path")
        prompts.extend(_prompts_from_csv((path.parent / file_value).resolve()))
    if prompts_csv is not None:
        prompts.extend(_prompts_from_csv(prompts_csv))
    if not prompts:
        raise ConfigError("add at least one prompt, in the YAML or in a CSV file")
    _check_prompt_ids(prompts)

    configured = providers if providers is not None else _providers(payload.get("providers"))
    if not configured:
        raise ConfigError("add at least one provider")

    timeout = _timeout(payload.get("settings", {}))
    return Project(
        brand=brand,
        competitors=competitors,
        prompts=tuple(prompts),
        providers=configured,
        timeout_seconds=timeout,
        source=str(path),
    )


def _read_yaml(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ConfigError(f"config not found: {path}")
    try:
        loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    if loaded is None:
        raise ConfigError(f"{path} is empty")
    if not isinstance(loaded, dict):
        raise ConfigError("the config file must be a mapping")
    return {str(key): value for key, value in loaded.items()}


def _require_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _sequence(value: object, label: str) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"{label} must be a list")
    return list(value)


def _entity(payload: dict[str, object], *, role: str) -> Entity:
    name = _text(payload.get("name"), f"{role} name")
    domain = _domain(_text(payload.get("domain"), f"{role} domain"))
    aliases_value = payload.get("aliases", [])
    aliases = tuple(_text(item, f"{role} alias") for item in _sequence(aliases_value, "aliases"))
    if role == "competitor":
        return Entity(name=name, domain=domain, aliases=aliases, role="competitor")
    return Entity(name=name, domain=domain, aliases=aliases, role="brand")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} must be a non-empty string")
    return value.strip()


def _domain(value: str) -> str:
    raw = value.strip().lower()
    if "://" in raw:
        raise ConfigError(f"domain must be a host, not a URL: {value}")
    if "/" in raw or " " in raw:
        raise ConfigError(f"domain must be a bare host: {value}")
    raw = raw.rstrip(".")
    if raw.startswith("www."):
        raw = raw[4:]
    if "." not in raw or not raw:
        raise ConfigError(f"domain must contain a dot: {value}")
    return raw


def _check_entities(brand: Entity, competitors: tuple[Entity, ...]) -> None:
    names = [brand.name.casefold()]
    domains = [brand.domain]
    for competitor in competitors:
        if competitor.name.casefold() in names:
            raise ConfigError(f"duplicate name: {competitor.name}")
        if competitor.domain in domains:
            raise ConfigError(f"duplicate domain: {competitor.domain}")
        names.append(competitor.name.casefold())
        domains.append(competitor.domain)


def _prompts_from_yaml(value: object) -> tuple[Prompt, ...]:
    prompts: list[Prompt] = []
    for index, item in enumerate(_sequence(value, "prompts"), start=1):
        payload = _require_mapping(item, f"prompts[{index}]")
        text = _text(payload.get("text"), f"prompts[{index}].text")
        prompt_id = payload.get("id")
        category = payload.get("category", "general")
        if not isinstance(category, str) or not category.strip():
            raise ConfigError(f"prompts[{index}].category must be a string")
        ident = (
            _text(prompt_id, f"prompts[{index}].id")
            if prompt_id is not None
            else _slug(text, fallback=f"prompt-{index}")
        )
        prompts.append(Prompt(id=ident, text=text, category=category.strip()))
    return tuple(prompts)


def _prompts_from_csv(path: Path) -> tuple[Prompt, ...]:
    if not path.is_file():
        raise ConfigError(f"prompts CSV not found: {path}")
    prompts: list[Prompt] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ConfigError(f"{path}: CSV needs a header row")
        fields = {(name or "").strip().lower() for name in reader.fieldnames}
        if "text" not in fields:
            raise ConfigError(f"{path}: CSV needs a text column")
        for index, row in enumerate(reader, start=1):
            normalized = {
                (key or "").strip().lower(): (value or "").strip() for key, value in row.items()
            }
            text = normalized.get("text", "")
            if not text:
                continue
            ident = normalized.get("id") or _slug(text, fallback=f"prompt-{index}")
            category = normalized.get("category") or "general"
            prompts.append(Prompt(id=ident, text=text, category=category))
    return tuple(prompts)


def _check_prompt_ids(prompts: list[Prompt]) -> None:
    seen: set[str] = set()
    for prompt in prompts:
        if prompt.id in seen:
            raise ConfigError(f"duplicate prompt id: {prompt.id}")
        seen.add(prompt.id)


def _providers(value: object) -> tuple[str, ...]:
    names: list[str] = []
    for item in _sequence(value, "providers"):
        if not isinstance(item, str) or not item.strip():
            raise ConfigError("provider names must be strings")
        names.append(item.strip().lower())
    return tuple(names)


def _timeout(value: object) -> float:
    if value is None:
        return 90.0
    payload = _require_mapping(value, "settings")
    raw = payload.get("timeout_seconds", 90)
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ConfigError("settings.timeout_seconds must be a number")
    if raw <= 0:
        raise ConfigError("settings.timeout_seconds must be positive")
    return float(raw)


def _slug(text: str, *, fallback: str) -> str:
    slug = _ID.sub("-", text.casefold()).strip("-")[:40].strip("-")
    return slug or fallback
