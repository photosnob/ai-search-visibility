from pathlib import Path

import pytest

from aisv.config import load_project
from aisv.errors import ConfigError

ROOT = Path(__file__).resolve().parents[1]


def test_example_config_loads() -> None:
    project = load_project(ROOT / "examples" / "northwind.yaml")
    assert project.brand.name == "Northwind"
    assert project.brand.domain == "northwind.example"
    assert project.brand.aliases == ("Northwind Outfitters",)
    assert [item.name for item in project.competitors] == ["Contoso", "Fabrikam"]
    assert len(project.prompts) == 6
    assert project.providers == ("openai", "perplexity")


def test_csv_prompts_are_appended(tmp_path: Path) -> None:
    yaml_path = tmp_path / "brand.yaml"
    yaml_path.write_text(
        """
brand:
  name: Northwind
  domain: www.northwind.example
competitors: []
prompts:
  - id: one
    text: First question?
providers:
  - mock
""",
        encoding="utf-8",
    )
    csv_path = tmp_path / "more.csv"
    csv_path.write_text(
        "id,text,category\ntwo,Second question?,local\n",
        encoding="utf-8",
    )
    project = load_project(yaml_path, prompts_csv=csv_path)
    assert project.brand.domain == "northwind.example"
    assert [prompt.id for prompt in project.prompts] == ["one", "two"]
    assert project.prompts[1].category == "local"


def test_prompts_file_is_relative_to_the_yaml(tmp_path: Path) -> None:
    nested = tmp_path / "proj"
    nested.mkdir()
    (nested / "prompts.csv").write_text("text\nWho is best?\n", encoding="utf-8")
    (nested / "brand.yaml").write_text(
        """
brand:
  name: Northwind
  domain: northwind.example
prompts_file: prompts.csv
providers: [mock]
""",
        encoding="utf-8",
    )
    project = load_project(nested / "brand.yaml")
    assert project.prompts[0].text == "Who is best?"
    assert project.prompts[0].id


def test_rejects_a_url_domain(tmp_path: Path) -> None:
    path = tmp_path / "brand.yaml"
    path.write_text(
        """
brand:
  name: Northwind
  domain: https://northwind.example
prompts:
  - text: Hi?
providers: [mock]
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="not a URL"):
        load_project(path)


def test_rejects_duplicate_prompt_ids(tmp_path: Path) -> None:
    path = tmp_path / "brand.yaml"
    path.write_text(
        """
brand:
  name: Northwind
  domain: northwind.example
prompts:
  - id: same
    text: One?
  - id: same
    text: Two?
providers: [mock]
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="duplicate prompt id"):
        load_project(path)
