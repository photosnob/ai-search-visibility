"""Command line for aisv."""

import argparse
import os
import sys
from collections.abc import MutableMapping
from dataclasses import replace
from pathlib import Path

from aisv import __version__
from aisv.config import load_project
from aisv.dotenv import load_dotenv
from aisv.errors import ConfigError, ProviderError, StoreError
from aisv.providers.registry import description, known
from aisv.reporting import build_report, write_report
from aisv.runner import execute, format_run_summary, parse_recorded_at
from aisv.scoring import mean_scores
from aisv.store import Store

_INIT = """\
# Project file for aisv. Replace the names, then run:
#   aisv run --config brand.yaml --dry-run
#
# Domains are bare hosts, with no scheme and no path. Aliases are other names
# an answer might use. providers: openai, perplexity, mock.

brand:
  name: Example Brand
  domain: example.com
  aliases: []

competitors:
  - name: Competitor One
    domain: competitor-one.example
    aliases: []

prompts:
  - id: category-best
    category: category
    text: What are the best options for someone comparing products in this category?

providers:
  - openai
  - perplexity

settings:
  timeout_seconds: 90
"""


def main(
    argv: list[str] | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> int:
    env: MutableMapping[str, str]
    if environ is None:
        env = os.environ
        load_dotenv(Path.cwd() / ".env", env)
    else:
        env = environ
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args, env)
    except (ConfigError, ProviderError, StoreError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted; completed answers were kept", file=sys.stderr)
        return 130


def _dispatch(args: argparse.Namespace, env: MutableMapping[str, str]) -> int:
    if args.command == "init":
        return _init(Path(args.path))
    if args.command == "providers":
        return _providers()
    if args.command == "runs":
        return _runs(Path(args.db), args.brand)
    if args.command == "run":
        return _run(args, env)
    if args.command == "report":
        return _report(args)
    print("error: unknown command", file=sys.stderr)
    return 2


def _run(args: argparse.Namespace, env: MutableMapping[str, str]) -> int:
    override = _split_providers(args.providers) if args.providers else None
    project = load_project(
        Path(args.config),
        prompts_csv=Path(args.prompts) if args.prompts else None,
        providers=override,
    )
    if args.timeout is not None:
        if args.timeout <= 0:
            raise ConfigError("--timeout must be positive")
        project = replace(project, timeout_seconds=args.timeout)
    prompt_ids = set(args.prompt_id) if args.prompt_id else None
    recorded_at = parse_recorded_at(args.recorded_at)

    def progress(step: int, total: int, provider: str, prompt_id: str) -> None:
        if not args.quiet:
            print(f"[{step}/{total}] {provider}  {prompt_id}", file=sys.stderr)

    with Store(Path(args.db)) as store:
        result = execute(
            project,
            store,
            env=env,
            dry_run=args.dry_run,
            mock_seed=args.mock_seed,
            recorded_at=recorded_at,
            limit=args.limit,
            prompt_ids=prompt_ids,
            on_progress=progress,
        )
        print(format_run_summary(result))
        if args.report:
            runs = store.list_runs(project.brand.name)
            report = build_report(runs, result.run_id)
            written = write_report(report, Path(args.report), {"md", "html"}, runs)
            for path in written:
                print(f"Wrote        {path}")
    return 1 if result.failed else 0


def _report(args: argparse.Namespace) -> int:
    formats = {"md", "html"} if args.format == "both" else {args.format}
    with Store(Path(args.db)) as store:
        brand, focus = _resolve_brand(store, args.brand, args.run)
        runs = store.list_runs(brand)
        if focus is not None and all(run.id != focus for run in runs):
            raise ConfigError(f"no run with id {focus}")
        report = build_report(runs, focus)
        written = write_report(report, Path(args.out), formats, runs)
    for path in written:
        print(path)
    return 0


def _runs(db: Path, brand: str | None) -> int:
    with Store(db) as store:
        if brand is None and not store.brand_names():
            print("No runs.")
            return 0
        chosen = brand
        if chosen is None:
            names = store.brand_names()
            if len(names) == 1:
                chosen = names[0]
        runs = store.list_runs(chosen)
    if not runs:
        print("No runs.")
        return 0
    for run in runs:
        scores = [
            answer.visibility_score
            for answer in run.answers
            if answer.error is None and answer.visibility_score
        ]
        visibility = mean_scores(scores) or "—"
        kind = "sample" if run.dry_run else "live"
        print(f"{run.created_at}  {run.id}  {run.brand_name}  {visibility}  {kind}")
    return 0


def _providers() -> int:
    for name in known():
        print(f"{name:<12} {description(name)}")
    return 0


def _init(path: Path) -> int:
    if path.exists():
        raise ConfigError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_INIT, encoding="utf-8")
    print(f"Wrote {path}")
    return 0


def _resolve_brand(store: Store, brand: str | None, run_id: str | None) -> tuple[str, str | None]:
    if run_id is not None:
        run = store.get_run(run_id)
        if brand is not None and brand != run.brand_name:
            raise ConfigError(f"run {run_id} belongs to {run.brand_name}, not {brand}")
        return run.brand_name, run_id
    if brand is not None:
        if brand not in store.brand_names():
            raise ConfigError(f"no runs for {brand}")
        return brand, None
    names = store.brand_names()
    if not names:
        raise ConfigError("the database has no runs")
    if len(names) > 1:
        raise ConfigError("pass --brand. This database has: " + ", ".join(names))
    return names[0], None


def _split_providers(value: str) -> tuple[str, ...]:
    names = tuple(part.strip().lower() for part in value.split(",") if part.strip())
    if not names:
        raise ConfigError("--providers did not include a name")
    return names


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aisv",
        description="Track whether AI answer engines mention, rank, and cite a brand.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  aisv init brand.yaml\n"
            "  aisv run --config brand.yaml --dry-run\n"
            "  aisv report --db aisv.sqlite --out report\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"aisv {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="write a starter config file")
    init.add_argument("path", help="where to write the YAML")

    run = commands.add_parser("run", help="ask the configured engines and store the run")
    run.add_argument("--config", required=True, help="YAML project file")
    run.add_argument("--prompts", help="CSV of extra prompts (id,text,category)")
    run.add_argument("--db", default="aisv.sqlite", help="SQLite file (default: aisv.sqlite)")
    run.add_argument("--providers", help="comma-separated provider names, overriding the config")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="answer with the mock provider and do not call the network",
    )
    run.add_argument(
        "--mock-seed",
        type=int,
        default=0,
        help="repeatable seed for the mock provider (default: 0)",
    )
    run.add_argument(
        "--recorded-at",
        help="store this ISO date or timestamp instead of the current time",
    )
    run.add_argument("--timeout", type=float, help="HTTP timeout in seconds")
    run.add_argument("--limit", type=int, help="only run the first N prompts")
    run.add_argument(
        "--prompt-id",
        action="append",
        help="only run this prompt id (repeat the flag to run several)",
    )
    run.add_argument("--report", help="also write Markdown and HTML into this directory")
    run.add_argument("--quiet", action="store_true", help="do not print per-prompt progress")

    report = commands.add_parser("report", help="write a report from stored runs")
    report.add_argument("--db", default="aisv.sqlite")
    report.add_argument("--brand", help="brand name, when the database holds more than one")
    report.add_argument(
        "--run", help="focus this run; the chart still includes the brand's history"
    )
    report.add_argument("--out", required=True, help="directory to write")
    report.add_argument(
        "--format",
        choices=("md", "html", "both"),
        default="both",
        help="default: both. CSV extracts are always written",
    )

    runs = commands.add_parser("runs", help="list stored runs")
    runs.add_argument("--db", default="aisv.sqlite")
    runs.add_argument("--brand")

    commands.add_parser("providers", help="list answer engines")
    return parser
