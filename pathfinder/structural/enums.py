"""Typed enums for structural graph artifacts."""

from enum import StrEnum


class GraphVersion(StrEnum):
    MVP_V1 = "mvp-v1"


class NodeType(StrEnum):
    FILE = "file"


class EdgeType(StrEnum):
    STRUCTURAL = "structural"
    ATTACK_TRANSITION = "attack_transition"


class RelationshipType(StrEnum):
    IMPORTS = "imports"
    CALLS = "calls"
    REFERENCES = "references"
    INCLUDES = "includes"
    SHARED_UTILITY = "shared_utility"
