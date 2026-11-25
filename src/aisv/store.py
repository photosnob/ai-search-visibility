"""SQLite history of runs.

Each answer is committed as it finishes, so an interrupted run keeps the
answers that already succeeded. Delete the database file to drop history.
"""

import json
import sqlite3
import uuid
from collections.abc import Sequence
from pathlib import Path

from aisv.errors import StoreError
from aisv.models import (
    Entity,
    StoredAnswer,
    StoredCitation,
    StoredMention,
    StoredRun,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    brand_name TEXT NOT NULL,
    brand_domain TEXT NOT NULL,
    competitors_json TEXT NOT NULL,
    providers_json TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    mock_seed INTEGER
);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    prompt_id TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    category TEXT NOT NULL,
    prompt_index INTEGER NOT NULL,
    provider TEXT NOT NULL,
    provider_index INTEGER NOT NULL,
    model TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    synthetic INTEGER NOT NULL,
    mentioned INTEGER,
    position INTEGER,
    position_scale INTEGER,
    position_method TEXT,
    sentiment TEXT,
    sentiment_score TEXT,
    visibility_score TEXT,
    mention_factor TEXT,
    position_factor TEXT,
    sentiment_factor TEXT,
    citation_factor TEXT,
    cited_brand_domain INTEGER,
    error TEXT
);
CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY,
    answer_id INTEGER NOT NULL REFERENCES answers(id),
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    title TEXT NOT NULL,
    owner TEXT NOT NULL,
    role TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entity_mentions (
    id INTEGER PRIMARY KEY,
    answer_id INTEGER NOT NULL REFERENCES answers(id),
    entity_name TEXT NOT NULL,
    role TEXT NOT NULL,
    mentioned INTEGER NOT NULL,
    position INTEGER,
    position_method TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_brand ON runs(brand_name, created_at);
CREATE INDEX IF NOT EXISTS idx_answers_run ON answers(run_id);
"""


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def create_run(
        self,
        *,
        created_at: str,
        brand_name: str,
        brand_domain: str,
        competitors: Sequence[Entity],
        providers: Sequence[str],
        dry_run: bool,
        mock_seed: int | None,
    ) -> str:
        run_id = self._new_id()
        payload = [
            {
                "name": entity.name,
                "domain": entity.domain,
                "aliases": list(entity.aliases),
            }
            for entity in competitors
        ]
        self._conn.execute(
            """
            INSERT INTO runs (
                id, created_at, brand_name, brand_domain, competitors_json,
                providers_json, dry_run, mock_seed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                created_at,
                brand_name,
                brand_domain,
                json.dumps(payload),
                json.dumps(list(providers)),
                int(dry_run),
                mock_seed,
            ),
        )
        self._conn.commit()
        return run_id

    def add_answer(self, run_id: str, answer: StoredAnswer) -> None:
        cursor = self._conn.execute(
            """
            INSERT INTO answers (
                run_id, prompt_id, prompt_text, category, prompt_index, provider,
                provider_index, model, answer_text, synthetic, mentioned, position,
                position_scale, position_method, sentiment, sentiment_score,
                visibility_score, mention_factor, position_factor, sentiment_factor,
                citation_factor, cited_brand_domain, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                answer.prompt_id,
                answer.prompt_text,
                answer.category,
                answer.prompt_index,
                answer.provider,
                answer.provider_index,
                answer.model,
                answer.answer_text,
                int(answer.synthetic),
                _bit(answer.mentioned),
                answer.position,
                answer.position_scale,
                answer.position_method,
                answer.sentiment,
                answer.sentiment_score,
                answer.visibility_score,
                answer.mention_factor,
                answer.position_factor,
                answer.sentiment_factor,
                answer.citation_factor,
                _bit(answer.cited_brand_domain),
                answer.error,
            ),
        )
        answer_id = cursor.lastrowid
        if not isinstance(answer_id, int):
            raise StoreError("SQLite did not return an answer id")
        self._conn.executemany(
            """
            INSERT INTO citations (answer_id, url, domain, title, owner, role)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (answer_id, item.url, item.domain, item.title, item.owner, item.role)
                for item in answer.citations
            ],
        )
        self._conn.executemany(
            """
            INSERT INTO entity_mentions (
                answer_id, entity_name, role, mentioned, position, position_method
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    answer_id,
                    item.entity_name,
                    item.role,
                    int(item.mentioned),
                    item.position,
                    item.position_method,
                )
                for item in answer.mentions
            ],
        )
        self._conn.commit()

    def brand_names(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT brand_name FROM runs ORDER BY brand_name"
        ).fetchall()
        return [_text(row, "brand_name") for row in rows]

    def list_runs(self, brand: str | None = None) -> list[StoredRun]:
        if brand is None:
            rows = self._conn.execute("SELECT id FROM runs ORDER BY created_at, id").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id FROM runs WHERE brand_name = ? ORDER BY created_at, id",
                (brand,),
            ).fetchall()
        return [self.get_run(_text(row, "id")) for row in rows]

    def get_run(self, run_id: str) -> StoredRun:
        row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise StoreError(f"no run with id {run_id}")
        answers = self._conn.execute(
            """
            SELECT * FROM answers
            WHERE run_id = ?
            ORDER BY prompt_index, provider_index, id
            """,
            (run_id,),
        ).fetchall()
        return StoredRun(
            id=_text(row, "id"),
            created_at=_text(row, "created_at"),
            brand_name=_text(row, "brand_name"),
            brand_domain=_text(row, "brand_domain"),
            competitors=_competitors(row["competitors_json"]),
            providers=_providers(row["providers_json"]),
            dry_run=bool(row["dry_run"]),
            mock_seed=_optional_int(row["mock_seed"]),
            answers=tuple(self._answer(item) for item in answers),
        )

    def _answer(self, row: sqlite3.Row) -> StoredAnswer:
        answer_id = _int(row, "id")
        citations = self._conn.execute(
            "SELECT * FROM citations WHERE answer_id = ? ORDER BY id",
            (answer_id,),
        ).fetchall()
        mentions = self._conn.execute(
            "SELECT * FROM entity_mentions WHERE answer_id = ? ORDER BY id",
            (answer_id,),
        ).fetchall()
        return StoredAnswer(
            prompt_id=_text(row, "prompt_id"),
            prompt_text=_text(row, "prompt_text"),
            category=_text(row, "category"),
            prompt_index=_int(row, "prompt_index"),
            provider=_text(row, "provider"),
            provider_index=_int(row, "provider_index"),
            model=_text(row, "model"),
            answer_text=_text(row, "answer_text"),
            synthetic=bool(row["synthetic"]),
            mentioned=_optional_bool(row["mentioned"]),
            position=_optional_int(row["position"]),
            position_scale=_optional_int(row["position_scale"]),
            position_method=_optional_text(row["position_method"]),
            sentiment=_optional_text(row["sentiment"]),
            sentiment_score=_optional_text(row["sentiment_score"]),
            visibility_score=_optional_text(row["visibility_score"]),
            mention_factor=_optional_text(row["mention_factor"]),
            position_factor=_optional_text(row["position_factor"]),
            sentiment_factor=_optional_text(row["sentiment_factor"]),
            citation_factor=_optional_text(row["citation_factor"]),
            cited_brand_domain=_optional_bool(row["cited_brand_domain"]),
            error=_optional_text(row["error"]),
            citations=tuple(
                StoredCitation(
                    url=_text(item, "url"),
                    domain=_text(item, "domain"),
                    title=_text(item, "title"),
                    owner=_text(item, "owner"),
                    role=_text(item, "role"),
                )
                for item in citations
            ),
            mentions=tuple(
                StoredMention(
                    entity_name=_text(item, "entity_name"),
                    role=_text(item, "role"),
                    mentioned=bool(item["mentioned"]),
                    position=_optional_int(item["position"]),
                    position_method=_text(item, "position_method"),
                )
                for item in mentions
            ),
        )

    def _new_id(self) -> str:
        for _ in range(5):
            run_id = uuid.uuid4().hex[:16]
            found = self._conn.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone()
            if found is None:
                return run_id
        raise StoreError("could not allocate a run id")


def _bit(value: bool | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _text(row: sqlite3.Row, key: str) -> str:
    value: object = row[key]
    if not isinstance(value, str):
        raise StoreError(f"expected text in {key}")
    return value


def _int(row: sqlite3.Row, key: str) -> int:
    value: object = row[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise StoreError(f"expected an integer in {key}")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StoreError("expected text or null")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise StoreError("expected an integer or null")
    return value


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise StoreError("expected a flag or null")
    return bool(value)


def _competitors(value: object) -> tuple[Entity, ...]:
    if not isinstance(value, str):
        raise StoreError("competitors were not stored as JSON")
    loaded: object = json.loads(value)
    if not isinstance(loaded, list):
        raise StoreError("competitors JSON must be a list")
    entities: list[Entity] = []
    for item in loaded:
        if not isinstance(item, dict):
            raise StoreError("a competitor entry is not an object")
        name = item.get("name")
        domain = item.get("domain")
        aliases = item.get("aliases", [])
        if (
            not isinstance(name, str)
            or not isinstance(domain, str)
            or not isinstance(aliases, list)
        ):
            raise StoreError("a competitor entry is missing name or domain")
        alias_values = tuple(alias for alias in aliases if isinstance(alias, str))
        entities.append(Entity(name=name, domain=domain, aliases=alias_values, role="competitor"))
    return tuple(entities)


def _providers(value: object) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise StoreError("providers were not stored as JSON")
    loaded: object = json.loads(value)
    if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
        raise StoreError("providers JSON must be a list of strings")
    return tuple(item for item in loaded if isinstance(item, str))
