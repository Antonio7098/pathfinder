"""Bounded graphcode evidence summaries for service-grouping prompts.

The current service-grouping Graphcode context is derived from CodeGraph file/symbol
blocks and bounded summaries of those blocks. It is code-oriented context rather than
raw repository mirroring, and it does not include `.env` file contents.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.adapters.codegraph_models import CodeGraphBlock, CodeGraphDocument
from pathfinder.structural.ids import normalize_repo_path
from pathfinder.structural.models import StructuralGraphArtifact


MAX_EXPORTED_SYMBOLS_PER_FILE = 3
MAX_INTERNAL_SYMBOLS_PER_FILE = 2
MAX_SYMBOL_LINK_SAMPLES_PER_PAIR = 4
MAX_FILE_PAIR_SUMMARIES = 24
MAX_DIRECTORY_SUMMARIES = 16
MAX_FILE_PROFILES = 24
MAX_DIRECTORY_FILE_PROFILES = 2
MAX_DIRECTORY_REPRESENTATIVE_FILES = 2


class GraphcodeSymbolSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    symbol_kind: str | None = None
    exported: bool = False


class GraphcodeFileProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    role_hints: list[str] = Field(default_factory=list)
    exported_symbols: list[GraphcodeSymbolSummary] = Field(default_factory=list)
    internal_symbols: list[GraphcodeSymbolSummary] = Field(default_factory=list)
    symbol_kind_counts: dict[str, int] = Field(default_factory=dict)
    symbol_count: int = 0
    outgoing_symbol_relation_count: int = 0
    incoming_symbol_relation_count: int = 0


class GraphcodeRepresentativeFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    role_hints: list[str] = Field(default_factory=list)
    exported_symbols: list[str] = Field(default_factory=list)


class GraphcodeDirectorySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    directory: str
    file_count: int
    symbol_count: int
    exported_symbol_count: int
    role_hint_counts: dict[str, int] = Field(default_factory=dict)
    sample_exported_symbols: list[str] = Field(default_factory=list)
    symbol_kinds: dict[str, int] = Field(default_factory=dict)
    representative_files: list[GraphcodeRepresentativeFile] = Field(default_factory=list)


class GraphcodeFilePairSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_path: str
    target_path: str
    relation_counts: dict[str, int] = Field(default_factory=dict)
    sample_symbol_links: list[str] = Field(default_factory=list)
    total_relation_count: int = 0


class ServiceGroupingGraphcodeEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    available: bool = False
    raw_block_count: int = 0
    symbol_block_count: int = 0
    file_profile_count: int = 0
    directory_summaries: list[GraphcodeDirectorySummary] = Field(default_factory=list)
    file_profiles: list[GraphcodeFileProfile] = Field(default_factory=list)
    file_pair_summaries: list[GraphcodeFilePairSummary] = Field(default_factory=list)


@dataclass(slots=True)
class _PairAccumulator:
    relation_counts: Counter[str] = field(default_factory=Counter)
    sample_symbol_links: set[str] = field(default_factory=set)


class ServiceGroupingGraphcodeContextBuilder:
    def build(self, *, structural_graph: StructuralGraphArtifact, raw_codegraph: CodeGraphDocument | None) -> ServiceGroupingGraphcodeEvidence:
        if raw_codegraph is None:
            return ServiceGroupingGraphcodeEvidence()

        known_file_paths = {node.path for node in structural_graph.nodes}
        symbol_blocks = [
            block
            for block in raw_codegraph.blocks.values()
            if block.metadata.custom.node_class == "symbol" and self._path_for_block(block) in known_file_paths
        ]

        symbols_by_file: dict[str, list[GraphcodeSymbolSummary]] = defaultdict(list)
        kind_counts_by_file: dict[str, Counter[str]] = defaultdict(Counter)
        exported_count_by_directory: Counter[str] = Counter()
        symbol_count_by_directory: Counter[str] = Counter()
        file_count_by_directory: Counter[str] = Counter(self._directory_bucket(path) for path in known_file_paths)
        sample_exports_by_directory: dict[str, set[str]] = defaultdict(set)
        kind_counts_by_directory: dict[str, Counter[str]] = defaultdict(Counter)
        role_hints_by_file: dict[str, list[str]] = {}
        role_hint_counts_by_directory: dict[str, Counter[str]] = defaultdict(Counter)

        block_by_id = {self._normalize_block_id(block_id): block for block_id, block in raw_codegraph.blocks.items()}
        file_pair_accumulators: dict[tuple[str, str], _PairAccumulator] = defaultdict(_PairAccumulator)
        outgoing_counts: Counter[str] = Counter()
        incoming_counts: Counter[str] = Counter()
        structural_degree_by_path = {
            node.path: node.in_degree_structural + node.out_degree_structural
            for node in structural_graph.nodes
        }

        for block in symbol_blocks:
            file_path = self._path_for_block(block)
            symbol = self._symbol_summary(block)
            symbols_by_file[file_path].append(symbol)
            directory = self._directory_bucket(file_path)
            if symbol.symbol_kind:
                kind_counts_by_file[file_path][symbol.symbol_kind] += 1
                kind_counts_by_directory[directory][symbol.symbol_kind] += 1
            symbol_count_by_directory[directory] += 1
            if symbol.exported:
                exported_count_by_directory[directory] += 1
                if len(sample_exports_by_directory[directory]) < MAX_EXPORTED_SYMBOLS_PER_FILE:
                    sample_exports_by_directory[directory].add(symbol.name)

            source_name = block.metadata.custom.name or self._symbol_label(block)
            for edge in block.edges:
                if edge.relation not in {"uses_symbol", "extends", "implements"}:
                    continue
                target_block = block_by_id.get(self._normalize_block_id(edge.target))
                if target_block is None:
                    continue
                target_path = self._path_for_block(target_block)
                if target_path not in known_file_paths or target_path == file_path:
                    continue
                target_name = target_block.metadata.custom.name or self._symbol_label(target_block)
                accumulator = file_pair_accumulators[(file_path, target_path)]
                accumulator.relation_counts[edge.relation] += 1
                if len(accumulator.sample_symbol_links) < MAX_SYMBOL_LINK_SAMPLES_PER_PAIR:
                    accumulator.sample_symbol_links.add(f"{source_name} -> {target_name}")
                outgoing_counts[file_path] += 1
                incoming_counts[target_path] += 1

        for path in sorted(known_file_paths):
            role_hints = self._role_hints(path=path, symbols=symbols_by_file.get(path, []))
            role_hints_by_file[path] = role_hints
            directory = self._directory_bucket(path)
            for role_hint in role_hints:
                role_hint_counts_by_directory[directory][role_hint] += 1

        symbol_count_by_file = {path: len(symbols) for path, symbols in symbols_by_file.items()}
        selected_paths = self._select_file_profile_paths(
            known_file_paths=known_file_paths,
            symbols_by_file=symbols_by_file,
            symbol_count_by_file=symbol_count_by_file,
            structural_degree_by_path=structural_degree_by_path,
            outgoing_counts=outgoing_counts,
            incoming_counts=incoming_counts,
        )

        file_profiles = [
            self._build_file_profile(
                path=path,
                role_hints=role_hints_by_file.get(path, []),
                symbols=symbols_by_file.get(path, []),
                kind_counts=kind_counts_by_file.get(path, Counter()),
                outgoing_symbol_relation_count=outgoing_counts.get(path, 0),
                incoming_symbol_relation_count=incoming_counts.get(path, 0),
            )
            for path in selected_paths
        ]

        directory_summaries = [
            GraphcodeDirectorySummary(
                directory=directory,
                file_count=file_count_by_directory[directory],
                symbol_count=symbol_count_by_directory.get(directory, 0),
                exported_symbol_count=exported_count_by_directory.get(directory, 0),
                role_hint_counts=dict(sorted(role_hint_counts_by_directory.get(directory, Counter()).items())),
                sample_exported_symbols=sorted(sample_exports_by_directory.get(directory, set())),
                symbol_kinds=dict(sorted(kind_counts_by_directory.get(directory, Counter()).items())),
                representative_files=self._representative_files_for_directory(
                    directory=directory,
                    paths_in_directory=sorted(path for path in known_file_paths if self._directory_bucket(path) == directory),
                    role_hints_by_file=role_hints_by_file,
                    symbols_by_file=symbols_by_file,
                    outgoing_counts=outgoing_counts,
                    incoming_counts=incoming_counts,
                    structural_degree_by_path=structural_degree_by_path,
                ),
            )
            for directory in sorted(file_count_by_directory, key=lambda value: (-symbol_count_by_directory.get(value, 0), value))[:MAX_DIRECTORY_SUMMARIES]
        ]

        file_pair_summaries = [
            GraphcodeFilePairSummary(
                source_path=source_path,
                target_path=target_path,
                relation_counts=dict(sorted(accumulator.relation_counts.items())),
                sample_symbol_links=sorted(accumulator.sample_symbol_links),
                total_relation_count=sum(accumulator.relation_counts.values()),
            )
            for (source_path, target_path), accumulator in sorted(
                file_pair_accumulators.items(),
                key=lambda item: (-sum(item[1].relation_counts.values()), item[0][0], item[0][1]),
            )[:MAX_FILE_PAIR_SUMMARIES]
        ]

        return ServiceGroupingGraphcodeEvidence(
            available=True,
            raw_block_count=len(raw_codegraph.blocks),
            symbol_block_count=len(symbol_blocks),
            file_profile_count=len(file_profiles),
            directory_summaries=directory_summaries,
            file_profiles=file_profiles,
            file_pair_summaries=file_pair_summaries,
        )

    def _select_file_profile_paths(
        self,
        *,
        known_file_paths: set[str],
        symbols_by_file: dict[str, list[GraphcodeSymbolSummary]],
        symbol_count_by_file: dict[str, int],
        structural_degree_by_path: dict[str, int],
        outgoing_counts: Counter[str],
        incoming_counts: Counter[str],
    ) -> list[str]:
        scored_paths = sorted(
            known_file_paths,
            key=lambda path: (
                -(
                    structural_degree_by_path.get(path, 0)
                    + outgoing_counts.get(path, 0)
                    + incoming_counts.get(path, 0)
                    + symbol_count_by_file.get(path, 0)
                ),
                path,
            ),
        )
        selected_paths: set[str] = set(scored_paths[:MAX_FILE_PROFILES])

        paths_by_directory: dict[str, list[str]] = defaultdict(list)
        for path in known_file_paths:
            paths_by_directory[self._directory_bucket(path)].append(path)
        for directory in sorted(paths_by_directory):
            ranked_paths = sorted(
                paths_by_directory[directory],
                key=lambda path: (
                    -(symbol_count_by_file.get(path, 0) + outgoing_counts.get(path, 0) + incoming_counts.get(path, 0)),
                    path,
                ),
            )
            for path in ranked_paths[:MAX_DIRECTORY_FILE_PROFILES]:
                if symbols_by_file.get(path):
                    selected_paths.add(path)

        return sorted(selected_paths, key=lambda path: (-symbol_count_by_file.get(path, 0), path))[:MAX_FILE_PROFILES]

    def _build_file_profile(
        self,
        *,
        path: str,
        role_hints: list[str],
        symbols: list[GraphcodeSymbolSummary],
        kind_counts: Counter[str],
        outgoing_symbol_relation_count: int,
        incoming_symbol_relation_count: int,
    ) -> GraphcodeFileProfile:
        exported_symbols = [symbol for symbol in symbols if symbol.exported]
        internal_symbols = [symbol for symbol in symbols if not symbol.exported]
        exported_symbols.sort(key=lambda item: ((item.symbol_kind or ""), item.name))
        internal_symbols.sort(key=lambda item: ((item.symbol_kind or ""), item.name))
        return GraphcodeFileProfile(
            path=path,
            role_hints=role_hints,
            exported_symbols=exported_symbols[:MAX_EXPORTED_SYMBOLS_PER_FILE],
            internal_symbols=internal_symbols[:MAX_INTERNAL_SYMBOLS_PER_FILE],
            symbol_kind_counts=dict(sorted(kind_counts.items())),
            symbol_count=len(symbols),
            outgoing_symbol_relation_count=outgoing_symbol_relation_count,
            incoming_symbol_relation_count=incoming_symbol_relation_count,
        )

    def _representative_files_for_directory(
        self,
        *,
        directory: str,
        paths_in_directory: list[str],
        role_hints_by_file: dict[str, list[str]],
        symbols_by_file: dict[str, list[GraphcodeSymbolSummary]],
        outgoing_counts: Counter[str],
        incoming_counts: Counter[str],
        structural_degree_by_path: dict[str, int],
    ) -> list[GraphcodeRepresentativeFile]:
        ranked_paths = sorted(
            paths_in_directory,
            key=lambda path: (
                -(
                    structural_degree_by_path.get(path, 0)
                    + outgoing_counts.get(path, 0)
                    + incoming_counts.get(path, 0)
                    + len(symbols_by_file.get(path, []))
                    + (2 if role_hints_by_file.get(path) else 0)
                ),
                path,
            ),
        )
        representatives: list[GraphcodeRepresentativeFile] = []
        for path in ranked_paths[:MAX_DIRECTORY_REPRESENTATIVE_FILES]:
            representatives.append(
                GraphcodeRepresentativeFile(
                    path=path,
                    role_hints=role_hints_by_file.get(path, []),
                    exported_symbols=[symbol.name for symbol in symbols_by_file.get(path, []) if symbol.exported][:MAX_EXPORTED_SYMBOLS_PER_FILE],
                )
            )
        return representatives

    def _role_hints(self, *, path: str, symbols: list[GraphcodeSymbolSummary]) -> list[str]:
        hints: set[str] = set()
        parts = [part.lower() for part in PurePosixPath(path).parts]
        stem = PurePosixPath(path).stem.lower()

        if any(part in {"tests", "test", "fixtures"} for part in parts) or stem.startswith("test_"):
            hints.add("test")
        if any(part in {"alembic", "migrations", "migration", "versions"} for part in parts):
            hints.add("migration")
        if stem in {"main", "app", "server", "cli"}:
            hints.add("entrypoint")
        if stem == "cli" or "cli" in parts:
            hints.add("cli")
        if "adapters" in parts or stem.endswith("adapter"):
            hints.add("adapter")
        if "prompts" in parts or "prompt" in stem:
            hints.add("prompt_template")
        if stem == "resolver" or stem.endswith("resolver"):
            hints.add("resolver")
        if "graph" in stem or stem in {"projector", "graph_builder"}:
            hints.add("graph_pipeline")
        if any(part in {"frontend", "ui", "pages", "components"} for part in parts):
            hints.add("ui")
        if "api" in parts or "route" in stem or "router" in stem:
            hints.add("api_surface")
        if "services" in parts or stem == "service":
            hints.add("service_logic")
        if any(part in {"db", "database", "models"} for part in parts) or stem in {"schema", "schemas", "session"}:
            hints.add("data_model")
        if "logging" in stem or "observability" in parts:
            hints.add("observability")
        if any(symbol.symbol_kind == "class" and symbol.name.endswith("Service") for symbol in symbols if symbol.exported):
            hints.add("service_api")

        return sorted(hints)

    def _symbol_summary(self, block: CodeGraphBlock) -> GraphcodeSymbolSummary:
        return GraphcodeSymbolSummary(
            name=block.metadata.custom.name or self._symbol_label(block),
            symbol_kind=block.metadata.custom.symbol_kind,
            exported=bool(block.metadata.custom.exported),
        )

    def _path_for_block(self, block: CodeGraphBlock) -> str:
        coderef = block.metadata.custom.coderef
        if coderef is not None and coderef.path:
            return normalize_repo_path(coderef.path)
        logical_key = block.metadata.custom.logical_key or ""
        if logical_key.startswith("file:"):
            return normalize_repo_path(logical_key.removeprefix("file:"))
        if logical_key.startswith("symbol:") and "::" in logical_key:
            return normalize_repo_path(logical_key.removeprefix("symbol:").split("::", 1)[0])
        return ""

    def _symbol_label(self, block: CodeGraphBlock) -> str:
        logical_key = block.metadata.custom.logical_key or block.id
        return logical_key.rsplit("::", 1)[-1]

    def _normalize_block_id(self, block_id: str) -> str:
        return block_id if block_id.startswith("blk_") else f"blk_{block_id}"

    def _directory_bucket(self, path: str) -> str:
        parts = path.split("/")
        if len(parts) >= 3:
            return "/".join(parts[:2])
        if len(parts) >= 2:
            return parts[0]
        return "."