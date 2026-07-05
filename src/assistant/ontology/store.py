"""SQLite-backed ontology object and link store."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .schema import ObjectTypeDef, PropertyDef, SchemaRegistry

Direction = Literal["out", "in"]
DEFAULT_ONTOLOGY_DB_PATH = Path("data") / "ontology.db"


class OntologyObject(BaseModel):
    """One persisted ontology object."""

    model_config = ConfigDict(extra="forbid")

    id: str
    object_type: str
    primary_key_value: str
    properties: dict[str, Any] = Field(default_factory=dict)
    source_ref: str = ""
    created_at: str = ""
    updated_at: str = ""


class OntologyLink(BaseModel):
    """One persisted relationship between ontology objects."""

    model_config = ConfigDict(extra="forbid")

    id: str
    link_type: str
    from_id: str
    to_id: str
    created_at: str = ""


class OntologyStore:
    """A rebuildable object/link graph stored in SQLite."""

    def __init__(self, db_path: str | Path = DEFAULT_ONTOLOGY_DB_PATH, registry: SchemaRegistry | None = None) -> None:
        self.db_path = Path(db_path)
        self.registry = registry or SchemaRegistry.load()
        self._lock = threading.Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def upsert_object(
        self,
        object_type: str,
        primary_key_value: str,
        properties: dict[str, Any] | None = None,
        *,
        source_ref: str = "",
    ) -> OntologyObject:
        object_def = self.registry.require_object_type(object_type)
        clean_properties = self._validate_properties(object_def, str(primary_key_value), properties or {})
        object_id = object_id_for(object_type, str(primary_key_value))
        now = _now()

        with self._lock, self._connect() as conn:
            existing = conn.execute("SELECT created_at FROM objects WHERE id = ?", (object_id,)).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """
                INSERT INTO objects (id, object_type, primary_key_value, properties, source_ref, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    primary_key_value = excluded.primary_key_value,
                    properties = excluded.properties,
                    source_ref = excluded.source_ref,
                    updated_at = excluded.updated_at
                """,
                (
                    object_id,
                    object_type,
                    str(primary_key_value),
                    json.dumps(clean_properties, sort_keys=True),
                    source_ref,
                    created_at,
                    now,
                ),
            )
        found = self.get(object_id)
        if found is None:
            raise RuntimeError(f"Ontology object {object_id} was not persisted.")
        return found

    def get(self, object_id: str) -> OntologyObject | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM objects WHERE id = ?", (object_id,)).fetchone()
        return _object_from_row(row) if row else None

    def find(
        self,
        object_type: str,
        filters: dict[str, Any] | None = None,
        *,
        contains: str = "",
    ) -> list[OntologyObject]:
        object_def = self.registry.require_object_type(object_type)
        filters = filters or {}
        property_names = {prop.name for prop in object_def.properties}
        unknown = sorted(set(filters) - property_names)
        if unknown:
            raise ValueError(f"Unknown properties for ontology object type {object_type}: {', '.join(unknown)}")

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM objects WHERE object_type = ? ORDER BY primary_key_value",
                (object_type,),
            ).fetchall()

        needle = _normalise_text(contains)
        objects = [_object_from_row(row) for row in rows]
        results: list[OntologyObject] = []
        for item in objects:
            if any(item.properties.get(key) != value for key, value in filters.items()):
                continue
            if needle and needle not in _normalise_text(_display_text(item.properties)):
                continue
            results.append(item)
        return results

    def link(self, link_type: str, from_id: str, to_id: str) -> OntologyLink:
        link_def = self.registry.require_link_type(link_type)
        from_object = self.get(from_id)
        to_object = self.get(to_id)
        if from_object is None:
            raise KeyError(f"Unknown ontology object id for link from_id: {from_id}")
        if to_object is None:
            raise KeyError(f"Unknown ontology object id for link to_id: {to_id}")
        if from_object.object_type != link_def.from_type:
            raise ValueError(
                f"Link type {link_type} expects from_type {link_def.from_type}, got {from_object.object_type}."
            )
        if to_object.object_type != link_def.to_type:
            raise ValueError(f"Link type {link_type} expects to_type {link_def.to_type}, got {to_object.object_type}.")

        link_id = _link_id(link_type, from_id, to_id)
        now = _now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO links (id, link_type, from_id, to_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(link_type, from_id, to_id) DO NOTHING
                """,
                (link_id, link_type, from_id, to_id, now),
            )
            row = conn.execute(
                "SELECT * FROM links WHERE link_type = ? AND from_id = ? AND to_id = ?",
                (link_type, from_id, to_id),
            ).fetchone()
        if row is None:
            raise RuntimeError(f"Ontology link {link_id} was not persisted.")
        return _link_from_row(row)

    def traverse(self, object_id: str, link_type: str, direction: Direction = "out") -> list[OntologyObject]:
        self.registry.require_link_type(link_type)
        if direction not in {"out", "in"}:
            raise ValueError("direction must be 'out' or 'in'.")
        if direction == "out":
            sql = """
                SELECT objects.* FROM links
                JOIN objects ON objects.id = links.to_id
                WHERE links.from_id = ? AND links.link_type = ?
                ORDER BY objects.object_type, objects.primary_key_value
            """
        else:
            sql = """
                SELECT objects.* FROM links
                JOIN objects ON objects.id = links.from_id
                WHERE links.to_id = ? AND links.link_type = ?
                ORDER BY objects.object_type, objects.primary_key_value
            """
        with self._connect() as conn:
            rows = conn.execute(sql, (object_id, link_type)).fetchall()
        return [_object_from_row(row) for row in rows]

    def neighbors(self, object_id: str) -> dict[str, dict[str, list[OntologyObject]]]:
        with self._connect() as conn:
            out_rows = conn.execute(
                """
                SELECT links.link_type, objects.* FROM links
                JOIN objects ON objects.id = links.to_id
                WHERE links.from_id = ?
                ORDER BY links.link_type, objects.object_type, objects.primary_key_value
                """,
                (object_id,),
            ).fetchall()
            in_rows = conn.execute(
                """
                SELECT links.link_type, objects.* FROM links
                JOIN objects ON objects.id = links.from_id
                WHERE links.to_id = ?
                ORDER BY links.link_type, objects.object_type, objects.primary_key_value
                """,
                (object_id,),
            ).fetchall()
        grouped: dict[str, dict[str, list[OntologyObject]]] = {}
        for row in out_rows:
            grouped.setdefault(row["link_type"], {"out": [], "in": []})["out"].append(_object_from_row(row))
        for row in in_rows:
            grouped.setdefault(row["link_type"], {"out": [], "in": []})["in"].append(_object_from_row(row))
        return grouped

    def delete_object(self, object_id: str) -> bool:
        with self._lock, self._connect() as conn:
            links = conn.execute("DELETE FROM links WHERE from_id = ? OR to_id = ?", (object_id, object_id)).rowcount
            objects = conn.execute("DELETE FROM objects WHERE id = ?", (object_id,)).rowcount
        return bool(objects or links)

    def counts(self) -> dict[str, dict[str, int] | int]:
        with self._connect() as conn:
            object_rows = conn.execute("SELECT object_type, COUNT(*) AS count FROM objects GROUP BY object_type").fetchall()
            link_rows = conn.execute("SELECT link_type, COUNT(*) AS count FROM links GROUP BY link_type").fetchall()
        object_counts = {row["object_type"]: int(row["count"]) for row in object_rows}
        link_counts = {row["link_type"]: int(row["count"]) for row in link_rows}
        return {
            "objects": object_counts,
            "links": link_counts,
            "total_objects": sum(object_counts.values()),
            "total_links": sum(link_counts.values()),
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS objects (
                    id TEXT PRIMARY KEY,
                    object_type TEXT NOT NULL,
                    primary_key_value TEXT NOT NULL,
                    properties TEXT NOT NULL,
                    source_ref TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(object_type, primary_key_value)
                );
                CREATE INDEX IF NOT EXISTS idx_ontology_objects_type ON objects(object_type);

                CREATE TABLE IF NOT EXISTS links (
                    id TEXT PRIMARY KEY,
                    link_type TEXT NOT NULL,
                    from_id TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(link_type, from_id, to_id),
                    FOREIGN KEY(from_id) REFERENCES objects(id) ON DELETE CASCADE,
                    FOREIGN KEY(to_id) REFERENCES objects(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_ontology_links_from ON links(link_type, from_id);
                CREATE INDEX IF NOT EXISTS idx_ontology_links_to ON links(link_type, to_id);
                """
            )

    def _validate_properties(
        self,
        object_def: ObjectTypeDef,
        primary_key_value: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        property_defs = {prop.name: prop for prop in object_def.properties}
        unknown = sorted(set(properties) - set(property_defs))
        if unknown:
            raise ValueError(f"Unknown properties for ontology object type {object_def.api_name}: {', '.join(unknown)}")

        clean = dict(properties)
        existing_pk = clean.get(object_def.primary_key)
        if existing_pk is not None and str(existing_pk) != primary_key_value:
            raise ValueError(
                f"Primary key property {object_def.primary_key} for {object_def.api_name} does not match "
                f"primary_key_value {primary_key_value!r}."
            )
        clean[object_def.primary_key] = primary_key_value

        missing = [prop.name for prop in object_def.properties if prop.required and prop.name not in clean]
        if missing:
            raise ValueError(f"Missing required properties for ontology object type {object_def.api_name}: {', '.join(missing)}")

        for name, value in clean.items():
            self._validate_property_type(object_def.api_name, property_defs[name], value)
        return clean

    @staticmethod
    def _validate_property_type(object_type: str, property_def: PropertyDef, value: Any) -> None:
        if value is None:
            return
        base_type = property_def.base_type
        valid = True
        if base_type in {"string", "date", "timestamp"}:
            valid = isinstance(value, str)
        elif base_type == "integer":
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif base_type == "double":
            valid = isinstance(value, int | float) and not isinstance(value, bool)
        elif base_type == "boolean":
            valid = isinstance(value, bool)
        elif base_type == "string_list":
            valid = isinstance(value, list) and all(isinstance(item, str) for item in value)
        if not valid:
            raise ValueError(
                f"Property {property_def.name} on ontology object type {object_type} must be {base_type}, "
                f"got {type(value).__name__}."
            )


def object_id_for(object_type: str, primary_key_value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", primary_key_value.lower()).strip("_")
    if not slug:
        slug = hashlib.sha1(primary_key_value.encode("utf-8")).hexdigest()[:12]
    return f"{object_type}:{slug[:96]}"


def _object_from_row(row: sqlite3.Row) -> OntologyObject:
    return OntologyObject(
        id=row["id"],
        object_type=row["object_type"],
        primary_key_value=row["primary_key_value"],
        properties=json.loads(row["properties"] or "{}"),
        source_ref=row["source_ref"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _link_from_row(row: sqlite3.Row) -> OntologyLink:
    return OntologyLink(
        id=row["id"],
        link_type=row["link_type"],
        from_id=row["from_id"],
        to_id=row["to_id"],
        created_at=row["created_at"],
    )


def _link_id(link_type: str, from_id: str, to_id: str) -> str:
    digest = hashlib.sha1(f"{link_type}|{from_id}|{to_id}".encode("utf-8")).hexdigest()[:16]
    return f"{link_type}:{digest}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _normalise_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _display_text(properties: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in properties.values():
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return " ".join(parts)
