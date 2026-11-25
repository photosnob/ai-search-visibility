"""Assemble a report and write Markdown, CSV, and the files around the HTML."""

import csv
import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from aisv.charts import Point, Series, line_chart_svg, text_chart
from aisv.errors import ConfigError
from aisv.models import StoredAnswer, StoredRun
from aisv.scoring import (
    CITATION_WEIGHT,
    MENTION_WEIGHT,
    POSITION_WEIGHT,
    SENTIMENT_WEIGHT,
    arithmetic_paragraph,
    failed_answers_paragraph,
    format_score,
    methodology_paragraph,
    score_from_factors,
    share_of_voice_paragraph,
)
from aisv.scoring import mean_scores as average

SampleMode = Literal["all", "some", "none"]

SAMPLE_ALL = (
    "Sample data. Every figure below was computed from synthetic answers written by "
    "the mock provider. No answer engine was called. These numbers are not measurements "
    "of a live brand."
)
SAMPLE_SOME = (
    "This report includes synthetic answers from the mock provider. Rows and runs marked "
    "sample are not measurements of a live brand."
)


@dataclass(frozen=True)
class RunLine:
    id: str
    created_at: str
    label: str
    day: str
    dry_run: bool
    visibility: str | None
    mentions: int
    successful: int
    failed: int
    providers: tuple[str, ...]


@dataclass(frozen=True)
class SovRow:
    name: str
    role: str
    mentions: int
    mention_share: str | None
    citations: int
    citation_share: str | None


@dataclass(frozen=True)
class SourceRow:
    domain: str
    owner: str
    role: str
    answers: int
    urls: int


@dataclass(frozen=True)
class AnswerRow:
    prompt_id: str
    category: str
    prompt_text: str
    provider: str
    model: str
    synthetic: bool
    mentioned: bool | None
    position: int | None
    position_scale: int | None
    position_method: str | None
    sentiment: str | None
    sentiment_score: str | None
    visibility: str | None
    cited_brand: bool | None
    error: str | None
    answer_text: str
    formula: str | None
    citation_urls: tuple[str, ...]


@dataclass(frozen=True)
class Report:
    brand: str
    domain: str
    competitors: tuple[str, ...]
    focus: RunLine
    runs: tuple[RunLine, ...]
    sample: SampleMode
    visibility: str | None
    mentions: int
    mention_rate: str | None
    own_domain: int
    citation_rate: str | None
    successful: int
    failed: int
    share: str | None
    series: tuple[Series, ...]
    sov: tuple[SovRow, ...]
    rows: tuple[AnswerRow, ...]
    sources: tuple[SourceRow, ...]
    tracked_citations: int
    other_citations: int
    prompt_count: int


def build_report(runs: Sequence[StoredRun], focus_id: str | None) -> Report:
    if not runs:
        raise ConfigError("nothing to report")
    ordered = tuple(sorted(runs, key=lambda run: (run.created_at, run.id)))
    brands = {run.brand_name for run in ordered}
    if len(brands) != 1:
        raise ConfigError("a report covers one brand")
    if focus_id is None:
        focus = ordered[-1]
    else:
        matched = [run for run in ordered if run.id == focus_id]
        if not matched:
            raise ConfigError(f"no run with id {focus_id}")
        focus = matched[0]

    ambiguous = len({run.created_at[:10] for run in ordered}) != len(ordered)
    lines = tuple(_run_line(run, ambiguous=ambiguous) for run in ordered)
    focus_line = next(line for line in lines if line.id == focus.id)
    successes = [answer for answer in focus.answers if answer.error is None]
    visibility_values = [answer.visibility_score for answer in successes if answer.visibility_score]
    mentions = sum(1 for answer in successes if answer.mentioned)
    own_domain = sum(1 for answer in successes if answer.cited_brand_domain)
    successful = len(successes)
    failed = sum(1 for answer in focus.answers if answer.error is not None)
    sov, share = _sov(focus)
    sample = _sample_mode(ordered)
    return Report(
        brand=focus.brand_name,
        domain=focus.brand_domain,
        competitors=tuple(entity.name for entity in focus.competitors),
        focus=focus_line,
        runs=lines,
        sample=sample,
        visibility=average(visibility_values),
        mentions=mentions,
        mention_rate=_percent(mentions, successful),
        own_domain=own_domain,
        citation_rate=_percent(own_domain, successful),
        successful=successful,
        failed=failed,
        share=share,
        series=_series(ordered, ambiguous=ambiguous),
        sov=sov,
        rows=tuple(_answer_row(answer) for answer in focus.answers),
        sources=_sources(focus),
        tracked_citations=_tracked_citations(focus),
        other_citations=_other_citations(focus),
        prompt_count=len({answer.prompt_id for answer in focus.answers}),
    )


def write_report(
    report: Report, out: Path, formats: set[str], runs: Sequence[StoredRun]
) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    from aisv.html_report import render_html

    written: list[Path] = []
    svg = line_chart_svg(report.series)
    if "md" in formats:
        svg_path = out / "visibility.svg"
        svg_path.write_text(svg, encoding="utf-8")
        md_path = out / "report.md"
        md_path.write_text(render_markdown(report), encoding="utf-8")
        written.extend([svg_path, md_path])
    if "html" in formats:
        html_path = out / "report.html"
        html_path.write_text(render_html(report, svg), encoding="utf-8")
        written.append(html_path)
    written.extend(_write_csv(runs, out))
    return written


def render_markdown(report: Report) -> str:
    engines = ", ".join(report.focus.providers) or "none"
    lines = [
        f"# {report.brand} AI search visibility",
        "",
    ]
    banner = _banner(report.sample)
    if banner:
        lines.extend([f"> **{banner}**", ""])
    lines.extend(
        [
            f"- Domain: `{report.domain}`",
            f"- Focus run: {report.focus.created_at} (`{report.focus.id}`)",
            f"- Engines: {engines}",
            f"- Prompts in the focus run: {report.prompt_count}",
        ]
    )
    if report.competitors:
        lines.append("- Competitors: " + ", ".join(report.competitors))
    lines.extend(["", "## Focus run", ""])
    lines.extend(
        [
            f"- Visibility: {_dash(report.visibility)}",
            f"- Mention rate: {_rate(report.mentions, report.successful, report.mention_rate)}",
            "- Brand domain cited: "
            + _rate(report.own_domain, report.successful, report.citation_rate),
            f"- Mention share of voice: {_share_text(report.share)}",
            f"- Failed answers excluded: {report.failed}",
            "",
            "## Visibility over time",
            "",
            "```text",
            text_chart(report.series),
            "```",
            "",
            "The same chart is in `visibility.svg`.",
            "",
            "## Runs",
            "",
            "| Recorded | Run | Visibility | Mentions | Sample |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for run in report.runs:
        sample = "sample" if run.dry_run else "live"
        mentions = f"{run.mentions} of {run.successful}"
        lines.append(
            f"| {run.created_at} | `{run.id}` | {_dash(run.visibility)} | {mentions} | {sample} |"
        )
    lines.extend(["", "## Share of voice", "", share_of_voice_paragraph(), ""])
    lines.extend(
        [
            "| Name | Role | Mention share | Mentions | Citation share | Citations |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for sov_row in report.sov:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(sov_row.name),
                    sov_row.role,
                    _share_text(sov_row.mention_share),
                    str(sov_row.mentions),
                    _share_text(sov_row.citation_share),
                    str(sov_row.citations),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Tracked citations: "
            f"{report.tracked_citations}. Other citations: {report.other_citations}.",
            "",
            "## Prompt results",
            "",
            "Detail is the focus run. `answers.csv` includes every run in this report.",
            "",
            "| Prompt | Engine | Mentioned | Position | Sentiment | Score | Brand domain |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for answer in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(answer.prompt_id),
                    _cell(answer.provider),
                    _mentioned(answer),
                    _cell(_position(answer)),
                    _cell(answer.sentiment or "—"),
                    _dash(answer.visibility),
                    _yes_no(answer.cited_brand),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Answers", ""])
    for answer in report.rows:
        lines.append(f"### {answer.prompt_id} · {answer.provider}")
        lines.append("")
        lines.append(f"Prompt: {answer.prompt_text}")
        lines.append("")
        if answer.error:
            lines.append(f"Error: {answer.error}")
            lines.append("")
            continue
        if answer.formula:
            lines.append(f"Score: {answer.formula}")
            lines.append("")
        if answer.citation_urls:
            lines.append("Citations: " + ", ".join(answer.citation_urls))
            lines.append("")
        lines.append(_fence(answer.answer_text))
        lines.append("")
    lines.extend(["## Cited domains", ""])
    if report.sources:
        lines.extend(
            [
                "| Domain | Owner | Answers | URLs |",
                "| --- | --- | ---: | ---: |",
            ]
        )
        for source in report.sources:
            lines.append(
                f"| {_cell(source.domain)} | {_cell(source.owner)} | "
                f"{source.answers} | {source.urls} |"
            )
    else:
        lines.append("No citations were recorded.")
    lines.extend(
        [
            "",
            "## How the score is computed",
            "",
            methodology_paragraph(),
            "",
            arithmetic_paragraph(),
            "",
            failed_answers_paragraph(),
            "",
            "Sentiment reads the sentences that name the brand and scores them with a small "
            "lexicon and a three-word negation window. A result above 0.2 is positive, below "
            "-0.2 is negative, and anything in between, including no polarity words, is neutral. "
            "A numbered or bulleted list of at least two items is treated as a ranking, top to "
            "bottom. A name that appears only outside that list is a mention with no rank. "
            "Host matching is a suffix check against the configured domain: "
            "`shop.brand.example` belongs to `brand.example`, and `brand.example.evil.test` "
            "does not.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_csv(runs: Sequence[StoredRun], out: Path) -> list[Path]:
    ordered = sorted(runs, key=lambda run: (run.created_at, run.id))
    answers_path = out / "answers.csv"
    sources_path = out / "sources.csv"
    mentions_path = out / "mentions.csv"
    with answers_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "recorded_at",
                "run_id",
                "dry_run",
                "synthetic",
                "provider",
                "model",
                "prompt_id",
                "category",
                "mentioned",
                "position",
                "position_scale",
                "position_method",
                "sentiment",
                "sentiment_score",
                "mention_factor",
                "position_factor",
                "sentiment_factor",
                "citation_factor",
                "visibility_score",
                "cited_brand_domain",
                "error",
                "prompt",
                "answer",
            ]
        )
        for run in ordered:
            for answer in run.answers:
                writer.writerow(
                    [
                        run.created_at,
                        run.id,
                        int(run.dry_run),
                        int(answer.synthetic),
                        answer.provider,
                        answer.model,
                        answer.prompt_id,
                        answer.category,
                        _csv_bool(answer.mentioned),
                        _csv_optional(answer.position),
                        _csv_optional(answer.position_scale),
                        answer.position_method or "",
                        answer.sentiment or "",
                        answer.sentiment_score or "",
                        answer.mention_factor or "",
                        answer.position_factor or "",
                        answer.sentiment_factor or "",
                        answer.citation_factor or "",
                        answer.visibility_score or "",
                        _csv_bool(answer.cited_brand_domain),
                        answer.error or "",
                        answer.prompt_text,
                        answer.answer_text,
                    ]
                )
    with sources_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "recorded_at",
                "run_id",
                "provider",
                "prompt_id",
                "url",
                "domain",
                "title",
                "owner",
                "role",
            ]
        )
        for run in ordered:
            for answer in run.answers:
                for citation in answer.citations:
                    writer.writerow(
                        [
                            run.created_at,
                            run.id,
                            answer.provider,
                            answer.prompt_id,
                            citation.url,
                            citation.domain,
                            citation.title,
                            citation.owner,
                            citation.role,
                        ]
                    )
    with mentions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "recorded_at",
                "run_id",
                "provider",
                "prompt_id",
                "entity",
                "role",
                "mentioned",
                "position",
                "position_method",
            ]
        )
        for run in ordered:
            for answer in run.answers:
                for mention in answer.mentions:
                    writer.writerow(
                        [
                            run.created_at,
                            run.id,
                            answer.provider,
                            answer.prompt_id,
                            mention.entity_name,
                            mention.role,
                            int(mention.mentioned),
                            _csv_optional(mention.position),
                            mention.position_method,
                        ]
                    )
    return [answers_path, sources_path, mentions_path]


def _run_line(run: StoredRun, *, ambiguous: bool) -> RunLine:
    successes = [answer for answer in run.answers if answer.error is None]
    scores = [answer.visibility_score for answer in successes if answer.visibility_score]
    label = run.created_at[:16].replace("T", " ") if ambiguous else run.created_at[:10]
    return RunLine(
        id=run.id,
        created_at=run.created_at,
        label=label,
        day=_day(run.created_at),
        dry_run=run.dry_run,
        visibility=average(scores),
        mentions=sum(1 for answer in successes if answer.mentioned),
        successful=len(successes),
        failed=sum(1 for answer in run.answers if answer.error is not None),
        providers=run.providers,
    )


def _series(runs: Sequence[StoredRun], *, ambiguous: bool) -> tuple[Series, ...]:
    def label(run: StoredRun) -> str:
        if ambiguous:
            return run.created_at[:16].replace("T", " ")
        return run.created_at[:10]

    overall: list[Point] = []
    for run in runs:
        score = average(
            [
                answer.visibility_score
                for answer in run.answers
                if answer.error is None and answer.visibility_score
            ]
        )
        if score is not None:
            overall.append(Point(label(run), score))
    series = [Series("Overall", tuple(overall))]
    providers: list[str] = []
    for run in runs:
        for provider in run.providers:
            if provider not in providers:
                providers.append(provider)
    for provider in providers:
        points: list[Point] = []
        for run in runs:
            score = average(
                [
                    answer.visibility_score
                    for answer in run.answers
                    if answer.provider == provider
                    and answer.error is None
                    and answer.visibility_score
                ]
            )
            if score is not None:
                points.append(Point(label(run), score))
        if points:
            series.append(Series(provider, tuple(points)))
    return tuple(series)


def _sov(run: StoredRun) -> tuple[tuple[SovRow, ...], str | None]:
    order: list[tuple[str, str]] = [(run.brand_name, "brand")]
    seen = {run.brand_name}
    for entity in run.competitors:
        if entity.name not in seen:
            seen.add(entity.name)
            order.append((entity.name, "competitor"))
    for answer in run.answers:
        for mention in answer.mentions:
            if mention.entity_name not in seen:
                seen.add(mention.entity_name)
                order.append((mention.entity_name, mention.role))
    mention_counts = dict.fromkeys((name for name, _role in order), 0)
    citation_counts = dict.fromkeys((name for name, _role in order), 0)
    for answer in run.answers:
        if answer.error is not None:
            continue
        for mention in answer.mentions:
            if mention.mentioned and mention.entity_name in mention_counts:
                mention_counts[mention.entity_name] += 1
        for citation in answer.citations:
            if citation.role in {"brand", "competitor"} and citation.owner in citation_counts:
                citation_counts[citation.owner] += 1
    mention_total = sum(mention_counts.values())
    citation_total = sum(citation_counts.values())
    rows = tuple(
        SovRow(
            name=name,
            role=role,
            mentions=mention_counts[name],
            mention_share=_percent(mention_counts[name], mention_total),
            citations=citation_counts[name],
            citation_share=_percent(citation_counts[name], citation_total),
        )
        for name, role in order
    )
    brand_share = _percent(mention_counts[run.brand_name], mention_total)
    return rows, brand_share


def _sources(run: StoredRun) -> tuple[SourceRow, ...]:
    owners: dict[str, tuple[str, str]] = {}
    urls: dict[str, set[str]] = {}
    answers: dict[str, set[int]] = {}
    for index, answer in enumerate(run.answers):
        if answer.error is not None:
            continue
        for citation in answer.citations:
            owners[citation.domain] = (citation.owner, citation.role)
            urls.setdefault(citation.domain, set()).add(citation.url)
            answers.setdefault(citation.domain, set()).add(index)
    rows = [
        SourceRow(
            domain=domain,
            owner=owner,
            role=role,
            answers=len(answers[domain]),
            urls=len(urls[domain]),
        )
        for domain, (owner, role) in owners.items()
    ]
    rows.sort(key=lambda row: (-row.answers, -row.urls, row.domain))
    return tuple(rows)


def _tracked_citations(run: StoredRun) -> int:
    return sum(
        1
        for answer in run.answers
        if answer.error is None
        for citation in answer.citations
        if citation.role in {"brand", "competitor"}
    )


def _other_citations(run: StoredRun) -> int:
    return sum(
        1
        for answer in run.answers
        if answer.error is None
        for citation in answer.citations
        if citation.role == "other"
    )


def _answer_row(answer: StoredAnswer) -> AnswerRow:
    formula = None
    if (
        answer.error is None
        and answer.mention_factor
        and answer.position_factor
        and answer.sentiment_factor
        and answer.citation_factor
        and answer.visibility_score
    ):
        recomputed = score_from_factors(
            answer.mention_factor,
            answer.position_factor,
            answer.sentiment_factor,
            answer.citation_factor,
        )
        formula = (
            f"100 × ({MENTION_WEIGHT}×{_trim(answer.mention_factor)} + "
            f"{POSITION_WEIGHT}×{_trim(answer.position_factor)} + "
            f"{SENTIMENT_WEIGHT}×{_trim(answer.sentiment_factor)} + "
            f"{CITATION_WEIGHT}×{_trim(answer.citation_factor)}) = {recomputed}"
        )
    return AnswerRow(
        prompt_id=answer.prompt_id,
        category=answer.category,
        prompt_text=answer.prompt_text,
        provider=answer.provider,
        model=answer.model,
        synthetic=answer.synthetic,
        mentioned=answer.mentioned,
        position=answer.position,
        position_scale=answer.position_scale,
        position_method=answer.position_method,
        sentiment=answer.sentiment,
        sentiment_score=answer.sentiment_score,
        visibility=answer.visibility_score,
        cited_brand=answer.cited_brand_domain,
        error=answer.error,
        answer_text=answer.answer_text,
        formula=formula,
        citation_urls=tuple(citation.url for citation in answer.citations),
    )


def _sample_mode(runs: Sequence[StoredRun]) -> SampleMode:
    flags = [
        run.dry_run or (bool(run.answers) and all(item.synthetic for item in run.answers))
        for run in runs
    ]
    if flags and all(flags):
        return "all"
    if any(flags):
        return "some"
    return "none"


def _banner(sample: SampleMode) -> str | None:
    if sample == "all":
        return SAMPLE_ALL
    if sample == "some":
        return SAMPLE_SOME
    return None


def _percent(part: int, whole: int) -> str | None:
    if whole == 0:
        return None
    return format_score(Decimal(part) * Decimal(100) / Decimal(whole))


def _day(iso: str) -> str:
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    month = months[int(iso[5:7]) - 1]
    return f"{int(iso[8:10])} {month} {iso[0:4]}"


def _trim(value: str) -> str:
    if "." not in value:
        return value
    trimmed = value.rstrip("0").rstrip(".")
    return trimmed or "0"


def _dash(value: str | None) -> str:
    return value if value else "—"


def _share_text(value: str | None) -> str:
    if value is None:
        return "—"
    return f"{value}%"


def _rate(count: int, total: int, percent: str | None) -> str:
    if percent is None:
        return "—"
    return f"{count} of {total} ({percent}%)"


def _mentioned(row: AnswerRow) -> str:
    if row.error:
        return "—"
    return "yes" if row.mentioned else "no"


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "—"
    return "yes" if value else "no"


def _position(row: AnswerRow) -> str:
    if row.error:
        return "—"
    if row.position_method == "list" and row.position and row.position_scale:
        return f"{row.position} of {row.position_scale}"
    if row.position_method == "order" and row.position and row.position_scale:
        return f"{row.position} of {row.position_scale} named"
    if row.position_method == "unranked":
        return "mentioned, unranked"
    return "not mentioned"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _fence(text: str) -> str:
    longest = max((len(match) for match in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}\n{text}\n{ticks}"


def _csv_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return "1" if value else "0"


def _csv_optional(value: int | None) -> str:
    if value is None:
        return ""
    return str(value)
