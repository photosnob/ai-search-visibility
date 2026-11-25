"""Regenerate examples/sample-report from the mock provider.

Sample data only. This does not call an answer engine.

    pip install -e .
    python examples/render_sample.py
"""

from pathlib import Path

from aisv.demo import write_sample


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_sample(
        config=root / "examples" / "northwind.yaml",
        db=root / "examples" / "sample.sqlite",
        out=root / "examples" / "sample-report",
    )


if __name__ == "__main__":
    main()
