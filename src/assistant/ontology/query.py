"""Read-only ontology query helpers."""

from __future__ import annotations

import re
from typing import Any

from .schema import SchemaRegistry
from .store import Direction, OntologyObject, OntologyStore


class OntologyQueryService:
    """Governed read surface over ontology schema, objects and links."""

    def __init__(self, store: OntologyStore, registry: SchemaRegistry | None = None) -> None:
        self.store = store
        self.registry = registry or store.registry

    def schema(self) -> dict[str, Any]:
        return self.registry.schema.model_dump()

    def stats(self) -> dict[str, Any]:
        counts = self.store.counts()
        return {
            **counts,
            "schema_version": self.registry.schema.schema_version,
            "object_type_count": len(self.registry.object_types),
            "link_type_count": len(self.registry.link_types),
            "action_type_count": len(self.registry.action_types),
        }

    def find_objects(
        self,
        object_type: str,
        *,
        query: str = "",
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        objects = self.store.find(object_type, filters or {})
        query_tokens = _tokens(query)
        if query_tokens:
            objects = [item for item in objects if query_tokens <= _tokens(_display_text(item))]
        return [self.object_response(item) for item in objects]

    def get_object(self, object_id: str) -> dict[str, Any] | None:
        item = self.store.get(object_id)
        if item is None:
            return None
        response = self.object_response(item)
        response["neighbors"] = {
            link_type: {
                direction: [self.object_response(neighbor) for neighbor in neighbors]
                for direction, neighbors in grouped.items()
            }
            for link_type, grouped in self.store.neighbors(object_id).items()
        }
        return response

    def traverse(self, object_id: str, link_type: str, direction: Direction = "out") -> list[dict[str, Any]]:
        return [self.object_response(item) for item in self.store.traverse(object_id, link_type, direction=direction)]

    def object_response(self, item: OntologyObject) -> dict[str, Any]:
        return {
            "id": item.id,
            "object_type": item.object_type,
            "primary_key_value": item.primary_key_value,
            "properties": item.properties,
            "source_ref": item.source_ref,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "citation": self.citation(item),
        }

    def citation(self, item: OntologyObject) -> str:
        object_def = self.registry.require_object_type(item.object_type)
        label = (
            item.properties.get("name")
            or item.properties.get("title")
            or item.properties.get("action")
            or item.primary_key_value
        )
        label_text = str(label).strip()
        if len(label_text) > 80:
            label_text = label_text[:77].rstrip() + "..."
        return f"Ontology: {object_def.display_name}/{label_text}"


def _tokens(text: str) -> set[str]:
    return {_normalise_token(token) for token in re.findall(r"[a-z0-9]+", text.lower())}


def _normalise_token(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _display_text(item: OntologyObject) -> str:
    parts = [item.object_type, item.primary_key_value]
    for value in item.properties.values():
        if isinstance(value, list):
            parts.extend(str(child) for child in value)
        else:
            parts.append(str(value))
    return " ".join(parts)
