"""A single-file HTML report. The chart is inline SVG, so it opens offline."""

import html
import re
from typing import Literal

from aisv.charts import series_color
from aisv.reporting import SAMPLE_ALL, SAMPLE_SOME, AnswerRow, Report
from aisv.scoring import (
    arithmetic_paragraph,
    failed_answers_paragraph,
    methodology_paragraph,
    share_of_voice_paragraph,
)

_WIDTH = re.compile(r"\d+(?:\.\d+)?")


def render_html(report: Report, svg: str) -> str:
    title = f"{report.brand} · AI search visibility"
    engines = ", ".join(report.focus.providers) or "none"
    competitors = ", ".join(report.competitors) if report.competitors else "none configured"
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{esc(title)}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        _banner(report.sample),
        "<main>",
        "<header>",
        '<p class="eyebrow">aisv · AI search visibility</p>',
        f"<h1>{esc(report.brand)}</h1>",
        '<p class="meta">',
        f'<span class="domain">{esc(report.domain)}</span>',
        f"<span>{esc(report.focus.day)}</span>",
        f"<span>run {esc(report.focus.id)}</span>",
        f"<span>{esc(engines)}</span>",
        f"<span>{report.prompt_count} prompts</span>",
        "</p>",
        f'<p class="competitors">Tracked against {esc(competitors)}.</p>',
        "</header>",
        _kpis(report),
        "<section>",
        "<h2>Visibility over time</h2>",
        '<p class="lede">Mean score of successful answers, 0 to 100. '
        "The axis is the score, not traffic.</p>",
        f'<div class="chart">{svg}</div>',
        _legend(report),
        _run_table(report),
        "</section>",
        "<section>",
        "<h2>Share of voice</h2>",
        f'<p class="lede">{esc(share_of_voice_paragraph())}</p>',
        _sov(report),
        "</section>",
        "<section>",
        "<h2>Focus run</h2>",
        '<p class="lede">One row per prompt and engine. Open an answer to see the text '
        "the score was computed from, and the arithmetic.</p>",
        _results(report),
        _answers(report),
        "</section>",
        "<section>",
        "<h2>Cited domains</h2>",
        _sources(report),
        "</section>",
        '<section class="method">',
        "<h2>How the score is computed</h2>",
        f"<p>{esc(methodology_paragraph())}</p>",
        f"<p>{esc(arithmetic_paragraph())}</p>",
        f"<p>{esc(failed_answers_paragraph())}</p>",
        "<p>Sentiment reads the sentences that name the brand and scores them with a small "
        "lexicon and a three-word negation window. A result above 0.2 is positive, below "
        "−0.2 is negative, and anything in between, including no polarity words, is neutral. "
        "A numbered or bulleted list of at least two items is treated as a ranking, top to "
        "bottom. A name that appears only outside that list is a mention with no rank. "
        "Host matching is a suffix check against the configured domain: "
        "shop.brand.example belongs to brand.example, and brand.example.evil.test does not. "
        "URLs are removed before mention detection, so a cited host is not also counted "
        "as the brand name being said.</p>",
        "</section>",
        "</main>",
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(parts)


def _banner(sample: Literal["all", "some", "none"]) -> str:
    if sample == "all":
        text = SAMPLE_ALL
    elif sample == "some":
        text = SAMPLE_SOME
    else:
        return ""
    return f'<div class="banner"><p>{esc(text)}</p></div>'


def _kpis(report: Report) -> str:
    failed = ""
    if report.failed:
        failed = f'<p class="excluded">{report.failed} failed answers are excluded from these figures.</p>'
    cards = [
        _kpi("Visibility", _dash(report.visibility), "Mean of successful answers"),
        _kpi("Mention rate", _pct(report.mention_rate), _of(report.mentions, report.successful)),
        _kpi(
            "Brand domain cited",
            _pct(report.citation_rate),
            _of(report.own_domain, report.successful),
        ),
        _kpi("Mention share", _pct(report.share), "Share of tracked mentions"),
    ]
    return f'<section class="kpis">{"".join(cards)}</section>{failed}'


def _kpi(label: str, value: str, note: str) -> str:
    return (
        '<div class="kpi">'
        f'<p class="kpi-label">{esc(label)}</p>'
        f'<p class="kpi-value">{esc(value)}</p>'
        f'<p class="kpi-note">{esc(note)}</p>'
        "</div>"
    )


def _legend(report: Report) -> str:
    items = []
    for index, series in enumerate(report.series):
        color = series_color(index)
        items.append(f'<li><i style="background:{color}"></i>{esc(series.name)}</li>')
    if not items:
        return ""
    return f'<ul class="legend">{"".join(items)}</ul>'


def _run_table(report: Report) -> str:
    rows = []
    for run in report.runs:
        sample = "sample" if run.dry_run else "live"
        mark = " focus" if run.id == report.focus.id else ""
        rows.append(
            '<tr class="' + mark.strip() + '">'
            f"<td>{esc(run.day)}</td>"
            f"<td><code>{esc(run.id)}</code></td>"
            f'<td class="num">{esc(_dash(run.visibility))}</td>'
            f'<td class="num">{run.mentions} of {run.successful}</td>'
            f"<td>{sample}</td>"
            "</tr>"
        )
    return (
        "<table>"
        "<thead><tr><th>Recorded</th><th>Run</th><th>Visibility</th>"
        "<th>Mentions</th><th>Sample</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _sov(report: Report) -> str:
    if not report.sov:
        return "<p>No tracked names.</p>"
    rows = []
    for row in report.sov:
        kind = "brand" if row.role == "brand" else "competitor"
        rows.append(
            f'<div class="sov {kind}">'
            f'<div class="sov-name"><span>{esc(row.name)}</span>'
            f'<span class="role">{esc(row.role)}</span></div>'
            '<div class="track"><div class="fill" style="width:'
            f'{_width(row.mention_share)}%"></div></div>'
            f'<div class="sov-value">{esc(_pct(row.mention_share))}'
            f"<span>{row.mentions} mentions</span></div>"
            "</div>"
        )
    note = (
        f'<p class="fine">Citation share uses {report.tracked_citations} citations '
        f"to tracked domains. {report.other_citations} citations point somewhere else "
        "and are listed below, outside the share.</p>"
    )
    return f'<div class="sov-list">{"".join(rows)}</div>{note}'


def _results(report: Report) -> str:
    body = []
    for row in report.rows:
        body.append(
            "<tr>"
            f'<td><span class="pid">{esc(row.prompt_id)}</span>'
            f'<span class="cat">{esc(row.category)}</span></td>'
            f"<td>{esc(row.provider)}</td>"
            f"<td>{esc(_mentioned(row))}</td>"
            f"<td>{esc(_position(row))}</td>"
            f'<td class="{esc(_sentiment_class(row))}">{esc(row.sentiment or "—")}</td>'
            f'<td class="num">{esc(_dash(row.visibility))}</td>'
            "</tr>"
        )
    return (
        "<table>"
        "<thead><tr><th>Prompt</th><th>Engine</th><th>Mentioned</th>"
        "<th>Position</th><th>Sentiment</th><th>Score</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def _answers(report: Report) -> str:
    blocks = []
    for row in report.rows:
        label = f"{row.prompt_id} · {row.provider} · {_dash(row.visibility)}"
        if row.error:
            body = f'<p class="error">{esc(row.error)}</p>'
        else:
            cites = ""
            if row.citation_urls:
                links = " ".join(
                    f'<a href="{esc(url)}">{esc(url)}</a>' for url in row.citation_urls
                )
                cites = f'<p class="cites">{links}</p>'
            formula = f'<p class="formula">{esc(row.formula)}</p>' if row.formula else ""
            body = (
                f"<p><strong>Prompt.</strong> {esc(row.prompt_text)}</p>"
                f"{formula}{cites}"
                f'<pre class="answer">{esc(row.answer_text)}</pre>'
            )
        blocks.append(f"<details><summary>{esc(label)}</summary>{body}</details>")
    return "".join(blocks)


def _sources(report: Report) -> str:
    if not report.sources:
        return "<p>No citations were recorded.</p>"
    body = []
    for source in report.sources:
        body.append(
            "<tr>"
            f"<td>{esc(source.domain)}</td>"
            f"<td>{esc(source.owner)}</td>"
            f'<td class="num">{source.answers}</td>'
            f'<td class="num">{source.urls}</td>'
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Domain</th><th>Owner</th><th>Answers</th>"
        f"<th>URLs</th></tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


def _mentioned(row: AnswerRow) -> str:
    if row.error:
        return "—"
    return "yes" if row.mentioned else "no"


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


def _sentiment_class(row: AnswerRow) -> str:
    if row.sentiment in {"positive", "neutral", "negative"}:
        return row.sentiment
    return "neutral"


def _dash(value: str | None) -> str:
    return value if value else "—"


def _pct(value: str | None) -> str:
    if value is None:
        return "—"
    return f"{value}%"


def _of(count: int, total: int) -> str:
    if total == 0:
        return "No successful answers"
    return f"{count} of {total} answers"


def _width(value: str | None) -> str:
    if value and _WIDTH.fullmatch(value):
        return value
    return "0"


def esc(value: str) -> str:
    return html.escape(value, quote=True)


_CSS = """
:root {
  --paper: #f3efe6;
  --ink: #1c1915;
  --soft: #5c564c;
  --line: #d9d2c5;
  --accent: #8f3d1b;
  --navy: #1f4e79;
  --good: #1d6b45;
  --bad: #8d2f39;
  --banner: #2a211c;
  --serif: "Iowan Old Style", Palatino, "Palatino Linotype", "Liberation Serif", "DejaVu Serif", Georgia, serif;
  --sans: "Avenir Next", "Segoe UI", "Liberation Sans", "DejaVu Sans", sans-serif;
  --mono: ui-monospace, "SFMono-Regular", "Liberation Mono", "DejaVu Sans Mono", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.5;
}
.banner {
  background: var(--banner);
  color: var(--paper);
}
.banner p {
  max-width: 880px;
  margin: 0 auto;
  padding: 14px 28px;
  font-size: 0.92rem;
}
main { max-width: 880px; margin: 0 auto; padding: 40px 28px 88px; }
.eyebrow {
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
h1 {
  margin: 0;
  font-family: var(--serif);
  font-size: 3.4rem;
  font-weight: 560;
  letter-spacing: -0.03em;
  line-height: 0.95;
}
h2 {
  margin: 0 0 8px;
  font-family: var(--serif);
  font-size: 1.7rem;
  font-weight: 560;
}
.meta, .competitors, .lede, .fine, .method p { color: var(--soft); }
.meta { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 18px 0 0; }
.meta span { font-family: var(--mono); font-size: 0.82rem; }
.domain { color: var(--ink); }
.competitors { margin-top: 8px; }
.kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-top: 1px solid var(--ink);
  border-bottom: 1px solid var(--ink);
  margin: 28px 0 8px;
}
.kpi { padding: 14px 16px 16px 0; }
.kpi + .kpi { padding-left: 16px; border-left: 1px solid var(--line); }
.kpi-label {
  margin: 0;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--soft);
}
.kpi-value {
  margin: 4px 0 0;
  font-family: var(--serif);
  font-size: 2.4rem;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
  line-height: 1;
}
.kpi-note { margin: 6px 0 0; color: var(--soft); font-size: 0.82rem; }
.excluded { color: var(--bad); font-size: 0.9rem; }
section { margin-top: 40px; }
.lede { margin-top: 0; }
.chart svg { width: 100%; height: auto; display: block; }
.legend { display: flex; flex-wrap: wrap; gap: 8px 18px; padding: 0; margin: 8px 0 18px; list-style: none; }
.legend li { display: flex; align-items: center; gap: 8px; font-family: var(--mono); font-size: 0.82rem; }
.legend i { width: 14px; height: 3px; display: inline-block; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; }
th {
  text-align: left;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--soft);
  font-weight: 600;
  padding: 8px 12px 8px 0;
  border-bottom: 1px solid var(--ink);
}
td { padding: 9px 12px 9px 0; border-bottom: 1px solid var(--line); vertical-align: top; }
.num { font-variant-numeric: tabular-nums; font-family: var(--mono); font-size: 0.88rem; }
tr.focus td { background: #efe6d6; }
code { font-family: var(--mono); font-size: 0.82rem; }
.pid { display: block; font-weight: 600; }
.cat { color: var(--soft); font-size: 0.78rem; letter-spacing: 0.04em; text-transform: uppercase; }
.positive { color: var(--good); }
.negative { color: var(--bad); }
.neutral { color: var(--soft); }
.sov { display: grid; grid-template-columns: 180px 1fr 110px; gap: 12px; align-items: center; margin: 10px 0; }
.sov-name { display: flex; flex-direction: column; }
.role { color: var(--soft); font-size: 0.75rem; letter-spacing: 0.06em; text-transform: uppercase; }
.track { background: #e4ddd0; height: 8px; }
.fill { height: 8px; background: var(--navy); }
.sov.brand .fill { background: var(--accent); }
.sov-value { text-align: right; font-variant-numeric: tabular-nums; }
.sov-value span { display: block; color: var(--soft); font-size: 0.75rem; }
details { border-top: 1px solid var(--line); padding: 8px 0; }
details:last-of-type { border-bottom: 1px solid var(--line); }
summary { cursor: pointer; font-weight: 600; }
.formula { font-family: var(--mono); font-size: 0.82rem; color: var(--soft); }
.cites { display: flex; flex-direction: column; gap: 2px; font-size: 0.85rem; }
.cites a { color: var(--navy); }
pre.answer {
  white-space: pre-wrap;
  font-family: var(--serif);
  font-size: 1rem;
  line-height: 1.45;
  background: #eae4d8;
  padding: 12px 14px;
  margin: 8px 0 4px;
}
.error { color: var(--bad); }
.method p { max-width: 68ch; }
@media (max-width: 720px) {
  h1 { font-size: 2.5rem; }
  .kpis, .sov { grid-template-columns: 1fr 1fr; }
  .kpi + .kpi { border-left: 0; }
  .sov { grid-template-columns: 1fr; gap: 4px; }
}
"""
