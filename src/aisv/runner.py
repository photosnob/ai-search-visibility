"""Run every prompt through the selected providers and store the scores."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from aisv.analysis import analyze_answer
from aisv.errors import ConfigError, ProviderError
from aisv.models import Project, Prompt, StoredAnswer, StoredCitation, StoredMention
from aisv.providers.base import AnswerProvider, ProviderContext, Transport
from aisv.providers.registry import build, build_mock, known
from aisv.scoring import mean_scores
from aisv.store import Store

Progress = Callable[[int, int, str, str], None]


@dataclass(frozen=True)
class FinishedRun:
    run_id: str
    created_at: str
    brand: str
    providers: tuple[str, ...]
    prompt_count: int
    visibility: str | None
    mentions: int
    own_domain: int
    successful: int
    failed: int
    dry_run: bool
    db_path: str


def execute(
    project: Project,
    store: Store,
    *,
    env: Mapping[str, str],
    dry_run: bool,
    mock_seed: int,
    recorded_at: str,
    transport: Transport | None = None,
    limit: int | None = None,
    prompt_ids: set[str] | None = None,
    on_progress: Progress | None = None,
) -> FinishedRun:
    prompts = _select_prompts(project, limit=limit, prompt_ids=prompt_ids)
    engines = [
        _engine(name, project, env=env, dry_run=dry_run, mock_seed=mock_seed, transport=transport)
        for name in project.providers
    ]
    synthetic_run = dry_run or all(engine.model == "mock" for engine in engines)
    run_id = store.create_run(
        created_at=recorded_at,
        brand_name=project.brand.name,
        brand_domain=project.brand.domain,
        competitors=project.competitors,
        providers=project.providers,
        dry_run=synthetic_run,
        mock_seed=mock_seed
        if synthetic_run or any(engine.model == "mock" for engine in engines)
        else None,
    )
    total = len(prompts) * len(engines)
    step = 0
    successes: list[StoredAnswer] = []
    failures = 0
    for prompt_index, prompt in enumerate(prompts):
        for provider_index, engine in enumerate(engines):
            step += 1
            if on_progress is not None:
                on_progress(step, total, engine.name, prompt.id)
            try:
                response = engine.ask(prompt.text)
            except ProviderError as exc:
                failures += 1
                store.add_answer(
                    run_id,
                    _failed(
                        prompt,
                        prompt_index,
                        engine.name,
                        provider_index,
                        engine.model,
                        engine.model == "mock",
                        str(exc),
                    ),
                )
                continue
            analysis = analyze_answer(
                response.text,
                response.citations,
                project.brand,
                project.competitors,
            )
            stored = StoredAnswer(
                prompt_id=prompt.id,
                prompt_text=prompt.text,
                category=prompt.category,
                prompt_index=prompt_index,
                provider=engine.name,
                provider_index=provider_index,
                model=response.model,
                answer_text=response.text,
                synthetic=engine.model == "mock",
                mentioned=analysis.mentioned,
                position=analysis.position,
                position_scale=analysis.position_scale,
                position_method=analysis.position_method,
                sentiment=analysis.sentiment,
                sentiment_score=analysis.sentiment_score,
                visibility_score=analysis.parts.visibility,
                mention_factor=analysis.parts.mention_factor,
                position_factor=analysis.parts.position_factor,
                sentiment_factor=analysis.parts.sentiment_factor,
                citation_factor=analysis.parts.citation_factor,
                cited_brand_domain=analysis.cited_brand_domain,
                error=None,
                citations=tuple(
                    StoredCitation(
                        url=item.url,
                        domain=item.domain,
                        title=item.title,
                        owner=item.owner,
                        role=item.role,
                    )
                    for item in analysis.citations
                ),
                mentions=tuple(
                    StoredMention(
                        entity_name=item.name,
                        role=item.role,
                        mentioned=item.mentioned,
                        position=item.position,
                        position_method=item.position_method,
                    )
                    for item in analysis.entities
                ),
            )
            store.add_answer(run_id, stored)
            successes.append(stored)
    mentions = sum(1 for answer in successes if answer.mentioned)
    own_domain = sum(1 for answer in successes if answer.cited_brand_domain)
    return FinishedRun(
        run_id=run_id,
        created_at=recorded_at,
        brand=project.brand.name,
        providers=project.providers,
        prompt_count=len(prompts),
        visibility=mean_scores(
            [answer.visibility_score for answer in successes if answer.visibility_score]
        ),
        mentions=mentions,
        own_domain=own_domain,
        successful=len(successes),
        failed=failures,
        dry_run=synthetic_run,
        db_path=str(store.path),
    )


def format_run_summary(result: FinishedRun) -> str:
    visibility = result.visibility if result.visibility is not None else "—"
    lines = [
        f"Run          {result.run_id}",
        f"Recorded     {result.created_at}",
        f"Brand        {result.brand}",
        f"Providers    {', '.join(result.providers)}",
        f"Prompts      {result.prompt_count}",
        f"Visibility   {visibility}",
        f"Mentions     {result.mentions} of {result.successful}",
        f"Own domain   {result.own_domain} of {result.successful}",
        f"Failed       {result.failed}",
        f"Stored       {result.db_path}",
    ]
    if result.dry_run:
        lines.append("Sample       yes — mock provider, not a live measurement")
    return "\n".join(lines)


def parse_recorded_at(value: str | None) -> str:
    if value is None:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = value.strip()
    if len(raw) == 10:
        raw = f"{raw}T00:00:00Z"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConfigError(
            "--recorded-at must be a date (YYYY-MM-DD) or an ISO-8601 timestamp"
        ) from exc
    normalized = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _select_prompts(
    project: Project, *, limit: int | None, prompt_ids: set[str] | None
) -> tuple[Prompt, ...]:
    prompts = list(project.prompts)
    if prompt_ids:
        known_ids = {prompt.id for prompt in prompts}
        unknown = sorted(prompt_ids - known_ids)
        if unknown:
            raise ConfigError("unknown prompt id: " + ", ".join(unknown))
        prompts = [prompt for prompt in prompts if prompt.id in prompt_ids]
    if limit is not None:
        if limit < 1:
            raise ConfigError("--limit must be at least 1")
        prompts = prompts[:limit]
    if not prompts:
        raise ConfigError("no prompts selected")
    return tuple(prompts)


def _engine(
    name: str,
    project: Project,
    *,
    env: Mapping[str, str],
    dry_run: bool,
    mock_seed: int,
    transport: Transport | None,
) -> AnswerProvider:
    if name not in known():
        known_names = ", ".join(known())
        raise ConfigError(f"unknown provider {name!r}. Known providers: {known_names}.")
    ctx = ProviderContext(
        recorded_name=name,
        timeout=project.timeout_seconds,
        mock_seed=mock_seed,
        brand=project.brand,
        competitors=project.competitors,
        transport=transport,
        env=env,
    )
    if dry_run or name == "mock":
        return build_mock(ctx)
    return build(name, ctx)


def _failed(
    prompt: Prompt,
    prompt_index: int,
    provider: str,
    provider_index: int,
    model: str,
    synthetic: bool,
    error: str,
) -> StoredAnswer:
    return StoredAnswer(
        prompt_id=prompt.id,
        prompt_text=prompt.text,
        category=prompt.category,
        prompt_index=prompt_index,
        provider=provider,
        provider_index=provider_index,
        model=model,
        answer_text="",
        synthetic=synthetic,
        mentioned=None,
        position=None,
        position_scale=None,
        position_method=None,
        sentiment=None,
        sentiment_score=None,
        visibility_score=None,
        mention_factor=None,
        position_factor=None,
        sentiment_factor=None,
        citation_factor=None,
        cited_brand_domain=None,
        error=error,
        citations=(),
        mentions=(),
    )
