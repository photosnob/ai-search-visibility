"""Write the committed sample report.

The sample is synthetic. The seeds exist so the repository can show a trend
without calling an answer engine. Nothing in the output is a measurement.
"""

from pathlib import Path

from aisv.config import load_project
from aisv.reporting import build_report, write_report
from aisv.runner import execute
from aisv.store import Store

# Three dates, three seeds. The mock provider is deterministic, so these
# values regenerate the same answers.
SAMPLE_RUNS: tuple[tuple[str, int], ...] = (
    ("2026-09-01T00:00:00Z", 1),
    ("2026-10-15T00:00:00Z", 2),
    ("2026-11-20T00:00:00Z", 3),
)


def write_sample(config: Path, db: Path, out: Path) -> None:
    if db.exists():
        db.unlink()
    project = load_project(config)
    with Store(db) as store:
        for recorded_at, seed in SAMPLE_RUNS:
            execute(
                project,
                store,
                env={},
                dry_run=True,
                mock_seed=seed,
                recorded_at=recorded_at,
            )
        runs = store.list_runs(project.brand.name)
        report = build_report(runs, None)
        write_report(report, out, {"md", "html"}, runs)
