import csv
from pathlib import Path

import pytest

from aisv.cli import main
from aisv.demo import SAMPLE_RUNS, write_sample
from aisv.dotenv import parse_env_file
from aisv.errors import ProviderError
from aisv.providers.mock import MockProvider
from aisv.runner import execute
from aisv.scoring import score_from_factors
from aisv.store import Store

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "examples" / "northwind.yaml"


def test_env_file_parser() -> None:
    parsed = parse_env_file(
        """
# comment
export OPENAI_API_KEY="abc"
PERPLEXITY_API_KEY='xyz'
BROKEN
"""
    )
    assert parsed == {"OPENAI_API_KEY": "abc", "PERPLEXITY_API_KEY": "xyz"}


def test_mock_is_deterministic_and_changes_with_the_seed() -> None:
    from aisv.models import Entity

    brand = Entity("Northwind", "northwind.example")
    competitors = (Entity("Contoso", "contoso.example", role="competitor"),)
    one = MockProvider(name="openai", seed=1, brand=brand, competitors=competitors)
    again = MockProvider(name="openai", seed=1, brand=brand, competitors=competitors)
    prompt = "What are the best hiking apparel brands?"
    assert one.ask(prompt).text == again.ask(prompt).text
    texts = {
        MockProvider(name="openai", seed=seed, brand=brand, competitors=competitors)
        .ask(prompt)
        .text
        for seed in range(8)
    }
    assert len(texts) > 1


def test_dry_run_does_not_touch_the_network(tmp_path: Path) -> None:
    from aisv.config import load_project

    class Boom:
        def post_json(self, *_args: object, **_kwargs: object) -> object:
            raise AssertionError("dry-run called the network")

    project = load_project(CONFIG)
    db = tmp_path / "runs.sqlite"
    with Store(db) as store:
        result = execute(
            project,
            store,
            env={},
            dry_run=True,
            mock_seed=1,
            recorded_at="2026-10-01T00:00:00Z",
            transport=Boom(),  # type: ignore[arg-type]
        )
        saved = store.get_run(result.run_id)
    assert result.dry_run is True
    assert result.failed == 0
    assert result.successful == 12
    assert saved.answers[0].model == "mock"
    assert saved.answers[0].provider == "openai"
    assert saved.answers[0].visibility_score is not None


def test_live_provider_missing_key_does_not_store_a_run(tmp_path: Path) -> None:
    from aisv.config import load_project

    project = load_project(CONFIG, providers=("openai",))
    db = tmp_path / "runs.sqlite"
    with Store(db) as store:
        with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
            execute(
                project,
                store,
                env={},
                dry_run=False,
                mock_seed=0,
                recorded_at="2026-10-01T00:00:00Z",
            )
        assert store.list_runs() == []


def test_provider_error_is_stored_and_excluded_from_the_mean(tmp_path: Path) -> None:
    from collections.abc import Mapping

    from aisv.config import load_project

    class Failing:
        def post_json(
            self,
            url: str,
            *,
            headers: Mapping[str, str],
            json_body: Mapping[str, object],
            timeout: float,
        ) -> object:
            del url, headers, json_body, timeout
            raise ProviderError("openai", "upstream timed out")

    project = load_project(_write_two_prompts(tmp_path), providers=("mock", "openai"))
    with Store(tmp_path / "runs.sqlite") as store:
        result = execute(
            project,
            store,
            env={"OPENAI_API_KEY": "test-key"},
            dry_run=False,
            mock_seed=0,
            recorded_at="2026-10-01T00:00:00Z",
            transport=Failing(),  # type: ignore[arg-type]
        )
        run = store.get_run(result.run_id)
    assert result.failed == 2
    assert result.successful == 2
    assert result.visibility is not None
    failed = [answer for answer in run.answers if answer.error]
    assert len(failed) == 2
    assert failed[0].visibility_score is None
    assert "upstream timed out" in (failed[0].error or "")


def test_cli_dry_run_report_and_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "aisv.sqlite"
    out = tmp_path / "report"
    code = main(
        [
            "run",
            "--config",
            str(CONFIG),
            "--dry-run",
            "--db",
            str(db),
            "--recorded-at",
            "2026-10-01",
            "--mock-seed",
            "1",
            "--quiet",
            "--limit",
            "2",
            "--report",
            str(out),
        ],
        environ={},
    )
    assert code == 0
    summary = capsys.readouterr().out
    assert "Sample" in summary
    assert "Visibility" in summary
    assert (out / "report.html").exists()
    assert (out / "report.md").exists()
    assert (out / "answers.csv").exists()
    html = (out / "report.html").read_text(encoding="utf-8")
    assert "Sample data" in html
    assert "Northwind" in html
    assert "<svg" in html

    code = main(["runs", "--db", str(db)], environ={})
    listed = capsys.readouterr().out
    assert code == 0
    assert "Northwind" in listed
    assert "sample" in listed

    code = main(["providers"], environ={})
    assert "OPENAI_API_KEY" in capsys.readouterr().out
    assert code == 0


def test_init_refuses_to_overwrite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "brand.yaml"
    assert main(["init", str(path)], environ={}) == 0
    assert "Example Brand" in path.read_text(encoding="utf-8")
    capsys.readouterr()
    assert main(["init", str(path)], environ={}) == 2
    assert "already exists" in capsys.readouterr().err


def test_unknown_provider_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "run",
            "--config",
            str(CONFIG),
            "--providers",
            "not-an-engine",
            "--db",
            str(tmp_path / "x.sqlite"),
        ],
        environ={},
    )
    assert code == 2
    assert "unknown provider" in capsys.readouterr().err


def test_sample_answers_recompute_and_match_a_fresh_run(tmp_path: Path) -> None:
    committed = ROOT / "examples" / "sample-report" / "answers.csv"
    assert committed.is_file(), "generate the sample report before running this test"
    out = tmp_path / "sample"
    write_sample(CONFIG, tmp_path / "sample.sqlite", out)
    assert _measurable(committed) == _measurable(out / "answers.csv")
    assert len(SAMPLE_RUNS) == 3
    with committed.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not row["visibility_score"]:
                continue
            assert row["dry_run"] == "1"
            assert (
                score_from_factors(
                    row["mention_factor"],
                    row["position_factor"],
                    row["sentiment_factor"],
                    row["citation_factor"],
                )
                == row["visibility_score"]
            )


def _measurable(path: Path) -> list[tuple[str, ...]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            (
                row["recorded_at"],
                row["provider"],
                row["prompt_id"],
                row["mentioned"],
                row["position"],
                row["sentiment"],
                row["visibility_score"],
                row["mention_factor"],
                row["position_factor"],
                row["sentiment_factor"],
                row["citation_factor"],
            )
            for row in csv.DictReader(handle)
        ]


def _write_two_prompts(tmp_path: Path) -> Path:
    path = tmp_path / "two.yaml"
    path.write_text(
        """
brand:
  name: Northwind
  domain: northwind.example
competitors:
  - name: Contoso
    domain: contoso.example
prompts:
  - id: one
    text: What is a good jacket?
  - id: two
    text: Is Northwind worth it?
providers: [mock]
""",
        encoding="utf-8",
    )
    return path
