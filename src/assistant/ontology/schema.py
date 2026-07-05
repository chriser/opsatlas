"""Declarative ontology schema registry.

The ontology schema is intentionally data-backed. Object, link and action type
definitions are loaded from JSON so the operational graph can evolve without
hard-coding every business concept into Python models.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BaseType = Literal["string", "integer", "double", "boolean", "date", "timestamp", "string_list"]
ParamType = Literal["string", "integer", "double", "boolean", "date", "timestamp", "string_list", "object"]
Cardinality = Literal["one_to_one", "one_to_many", "many_to_many"]
EditKind = Literal["create", "update", "delete", "custom"]

DEFAULT_SCHEMA_PATH = Path(__file__).with_name("registry_schema.json")


class PropertyDef(BaseModel):
    """One property on an ontology object type."""

    model_config = ConfigDict(extra="forbid")

    name: str
    base_type: BaseType
    required: bool = False
    description: str = ""


class ObjectTypeDef(BaseModel):
    """Schema for one real-world business object."""

    model_config = ConfigDict(extra="forbid")

    api_name: str
    display_name: str
    description: str = ""
    primary_key: str
    properties: list[PropertyDef] = Field(default_factory=list)
    implements: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_primary_key_property(self) -> "ObjectTypeDef":
        property_names = {item.name for item in self.properties}
        if self.primary_key not in property_names:
            raise ValueError(f"Object type {self.api_name!r} primary_key {self.primary_key!r} is not defined as a property.")
        return self


class LinkTypeDef(BaseModel):
    """Schema for a relationship between two object types."""

    model_config = ConfigDict(extra="forbid")

    api_name: str
    from_type: str
    to_type: str
    cardinality: Cardinality
    description: str = ""


class ParamDef(BaseModel):
    """Action parameter definition."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: ParamType
    object_type: str | None = None
    required: bool = True

    @model_validator(mode="after")
    def validate_object_parameter(self) -> "ParamDef":
        if self.type == "object" and not self.object_type:
            raise ValueError(f"Object parameter {self.name!r} must declare object_type.")
        if self.type != "object" and self.object_type:
            raise ValueError(f"Non-object parameter {self.name!r} cannot declare object_type.")
        return self


class ActionTypeDef(BaseModel):
    """Schema for a governed operation over ontology objects."""

    model_config = ConfigDict(extra="forbid")

    api_name: str
    display_name: str
    description: str = ""
    parameters: list[ParamDef] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)
    edit_kind: EditKind = "custom"
    side_effects: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False


class OntologySchemaDef(BaseModel):
    """Full declarative ontology schema."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "ontology-schema.v1"
    object_types: list[ObjectTypeDef] = Field(default_factory=list)
    link_types: list[LinkTypeDef] = Field(default_factory=list)
    action_types: list[ActionTypeDef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema_references(self) -> "OntologySchemaDef":
        object_names = _unique_names("object type", [item.api_name for item in self.object_types])
        _unique_names("link type", [item.api_name for item in self.link_types])
        _unique_names("action type", [item.api_name for item in self.action_types])

        for link in self.link_types:
            if link.from_type not in object_names:
                raise ValueError(f"Link type {link.api_name!r} references unknown from_type {link.from_type!r}.")
            if link.to_type not in object_names:
                raise ValueError(f"Link type {link.api_name!r} references unknown to_type {link.to_type!r}.")

        for action in self.action_types:
            for param in action.parameters:
                if param.object_type and param.object_type not in object_names:
                    raise ValueError(
                        f"Action type {action.api_name!r} parameter {param.name!r} references unknown object_type "
                        f"{param.object_type!r}."
                    )
        return self


class SchemaRegistry:
    """Validated lookup service for ontology object, link and action definitions."""

    def __init__(self, schema: OntologySchemaDef) -> None:
        self.schema = schema
        self.object_types = {item.api_name: item for item in schema.object_types}
        self.link_types = {item.api_name: item for item in schema.link_types}
        self.action_types = {item.api_name: item for item in schema.action_types}

    @classmethod
    def load(cls, path: str | Path = DEFAULT_SCHEMA_PATH) -> "SchemaRegistry":
        schema_path = Path(path)
        return cls.from_dict(json.loads(schema_path.read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, payload: dict) -> "SchemaRegistry":
        return cls(OntologySchemaDef.model_validate(payload))

    def require_object_type(self, api_name: str) -> ObjectTypeDef:
        try:
            return self.object_types[api_name]
        except KeyError as exc:
            raise KeyError(f"Unknown ontology object type: {api_name}") from exc

    def require_link_type(self, api_name: str) -> LinkTypeDef:
        try:
            return self.link_types[api_name]
        except KeyError as exc:
            raise KeyError(f"Unknown ontology link type: {api_name}") from exc

    def require_action_type(self, api_name: str) -> ActionTypeDef:
        try:
            return self.action_types[api_name]
        except KeyError as exc:
            raise KeyError(f"Unknown ontology action type: {api_name}") from exc

    def describe_for_llm(self) -> str:
        """Return a compact, deterministic schema summary for prompts/tools."""

        lines = [f"Ontology schema {self.schema.schema_version}."]
        lines.append("Object types:")
        for object_type in self.schema.object_types:
            properties = ", ".join(
                f"{prop.name}:{prop.base_type}{'*' if prop.required else ''}"
                for prop in object_type.properties
            )
            lines.append(f"- {object_type.api_name} ({object_type.display_name}); pk={object_type.primary_key}; props={properties}.")

        lines.append("Link types:")
        for link_type in self.schema.link_types:
            lines.append(f"- {link_type.api_name}: {link_type.from_type} -> {link_type.to_type} ({link_type.cardinality}).")

        if self.schema.action_types:
            lines.append("Action types:")
            for action_type in self.schema.action_types:
                params = ", ".join(
                    f"{param.name}:{param.type}{'[' + param.object_type + ']' if param.object_type else ''}"
                    f"{'*' if param.required else ''}"
                    for param in action_type.parameters
                )
                lines.append(
                    f"- {action_type.api_name} ({action_type.edit_kind}); params={params or 'none'}; "
                    f"approval={str(action_type.requires_human_approval).lower()}."
                )
        return "\n".join(lines)


def _unique_names(label: str, names: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in names:
        if name in seen:
            duplicates.add(name)
        seen.add(name)
    if duplicates:
        raise ValueError(f"Duplicate ontology {label} api_name values: {', '.join(sorted(duplicates))}.")
    return seen
