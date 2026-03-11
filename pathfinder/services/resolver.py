"""Deterministic resolution of LLM-proposed file groups into grounded services."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath

from pathfinder.llm.models import LLMInvocationRecord
from pathfinder.services.enums import ServiceAssignmentKind, ServiceKind, ServiceLayer, ServiceResolutionSource, ServiceTemplateVersion
from pathfinder.services.ids import SHARED_UTILITY_SERVICE_ID, UNCLASSIFIED_SERVICE_ID, service_grouping_id_for_graph, service_id_from_name
from pathfinder.services.models import LLMServiceGroupingPayload, ServiceDefinition, ServiceFileAssignment, ServiceGroupingArtifact, ServiceGroupingDiagnostics, ServiceGroupingSummary
from pathfinder.structural.models import StructuralGraphArtifact


@dataclass(frozen=True, slots=True)
class _ProposedService:
    id: str
    name: str
    layer: ServiceLayer
    summary: str
    file_paths: tuple[str, ...]
    confidence: float | None
    rationale: str | None


@dataclass(slots=True)
class _AssignmentState:
    file_path: str
    assigned_service_id: str
    assignment_kind: ServiceAssignmentKind
    resolution_source: ServiceResolutionSource
    proposed_service_ids: list[str]
    confidence: float | None
    rationale: str | None


class ServiceGroupingResolver:
    def resolve(
        self,
        *,
        structural_graph: StructuralGraphArtifact,
        payload: LLMServiceGroupingPayload,
        template_version: ServiceTemplateVersion,
        llm_invocation: LLMInvocationRecord,
    ) -> ServiceGroupingArtifact:
        known_file_paths = [node.path for node in structural_graph.nodes]
        known_file_set = set(known_file_paths)
        files_by_directory_bucket = self._files_by_directory_bucket(known_file_paths)
        invented_file_paths: set[str] = set()
        empty_service_names: list[str] = []
        dropped_service_names: list[str] = []

        proposed_services: list[_ProposedService] = []
        existing_ids: set[str] = set()
        for service in payload.services:
            valid_paths: list[str] = []
            for path in service.file_paths:
                if path in known_file_set:
                    valid_paths.append(path)
                else:
                    invented_file_paths.add(path)
            if not valid_paths:
                valid_paths.extend(
                    self._ground_service_from_directory_buckets(
                        service_name=service.name,
                        files_by_directory_bucket=files_by_directory_bucket,
                    )
                )
            valid_paths = self._expand_paths_to_directory_bucket(
                service_name=service.name,
                valid_paths=valid_paths,
                files_by_directory_bucket=files_by_directory_bucket,
            )
            unique_valid_paths = tuple(sorted(set(valid_paths)))
            if not unique_valid_paths:
                empty_service_names.append(service.name)
                dropped_service_names.append(service.name)
                continue
            service_id = self._unique_service_id(service.name, existing_ids)
            proposed_services.append(
                _ProposedService(
                    id=service_id,
                    name=service.name,
                    layer=service.layer,
                    summary=service.summary,
                    file_paths=unique_valid_paths,
                    confidence=service.confidence,
                    rationale=service.rationale,
                )
            )

        proposals_by_file: dict[str, list[_ProposedService]] = {path: [] for path in known_file_paths}
        for service in proposed_services:
            for path in service.file_paths:
                proposals_by_file[path].append(service)

        explicit_shared = sorted(path for path in payload.shared_file_paths if path in known_file_set)
        explicit_unclassified = sorted(path for path in payload.unclassified_file_paths if path in known_file_set)
        explicit_shared_set = set(explicit_shared)
        explicit_unclassified_set = set(explicit_unclassified)
        for path in payload.shared_file_paths + payload.unclassified_file_paths:
            if path not in known_file_set:
                invented_file_paths.add(path)

        overlap_file_paths: list[str] = []
        assignments: list[_AssignmentState] = []

        for file_path in known_file_paths:
            proposals = sorted(proposals_by_file[file_path], key=lambda item: (len(item.file_paths), item.id))
            proposed_ids = [item.id for item in proposals]
            if file_path in explicit_shared_set:
                service_id = SHARED_UTILITY_SERVICE_ID
                assignment_kind = ServiceAssignmentKind.SHARED
                resolution_source = ServiceResolutionSource.EXPLICIT_SHARED
                rationale = "Explicitly marked as shared by the LLM output."
                confidence = None
            elif len(proposals) > 1:
                service_id = SHARED_UTILITY_SERVICE_ID
                assignment_kind = ServiceAssignmentKind.SHARED
                resolution_source = ServiceResolutionSource.OVERLAP_SHARED
                overlap_file_paths.append(file_path)
                rationale = "Multiple inferred services claimed this file; resolved conservatively into the shared utility bucket."
                confidence = None
            elif len(proposals) == 1:
                proposal = proposals[0]
                service_id = proposal.id
                assignment_kind = ServiceAssignmentKind.PRIMARY
                resolution_source = ServiceResolutionSource.LLM_PRIMARY
                rationale = proposal.rationale
                confidence = proposal.confidence
            else:
                service_id = UNCLASSIFIED_SERVICE_ID
                assignment_kind = ServiceAssignmentKind.UNCLASSIFIED
                resolution_source = ServiceResolutionSource.FALLBACK_UNCLASSIFIED
                rationale = "No grounded inferred service claimed this file."
                confidence = None

            if file_path in explicit_unclassified_set and assignment_kind != ServiceAssignmentKind.SHARED:
                service_id = UNCLASSIFIED_SERVICE_ID
                assignment_kind = ServiceAssignmentKind.UNCLASSIFIED
                resolution_source = ServiceResolutionSource.EXPLICIT_UNCLASSIFIED
                rationale = "Explicitly marked as unclassified by the LLM output."
                confidence = None

            assignments.append(
                _AssignmentState(
                    file_path=file_path,
                    assigned_service_id=service_id,
                    assignment_kind=assignment_kind,
                    resolution_source=resolution_source,
                    proposed_service_ids=proposed_ids,
                    confidence=confidence,
                    rationale=rationale,
                )
            )

        connectivity_promoted_file_paths, directory_promoted_file_paths = self._promote_unclassified_assignments(
            assignments=assignments,
            structural_graph=structural_graph,
            explicit_unclassified_paths=explicit_unclassified_set,
            proposed_services=proposed_services,
        )
        cluster_services, cluster_promoted_file_paths = self._cluster_remaining_unclassified_assignments(
            assignments=assignments,
            explicit_unclassified_paths=explicit_unclassified_set,
            existing_ids=existing_ids,
        )

        assigned_members_by_service: dict[str, list[str]] = {}
        file_assignments = [
            ServiceFileAssignment(
                file_path=assignment.file_path,
                assigned_service_id=assignment.assigned_service_id,
                assignment_kind=assignment.assignment_kind,
                resolution_source=assignment.resolution_source,
                proposed_service_ids=assignment.proposed_service_ids,
                confidence=assignment.confidence,
                rationale=assignment.rationale,
            )
            for assignment in assignments
        ]
        for assignment in file_assignments:
            assigned_members_by_service.setdefault(assignment.assigned_service_id, []).append(assignment.file_path)

        services: list[ServiceDefinition] = []
        for proposal in sorted(proposed_services, key=lambda item: item.id):
            members = sorted(assigned_members_by_service.get(proposal.id, []))
            if not members:
                dropped_service_names.append(proposal.name)
                continue
            services.append(
                ServiceDefinition(
                    id=proposal.id,
                    name=proposal.name,
                    kind=ServiceKind.INFERRED,
                    layer=proposal.layer,
                    summary=proposal.summary,
                    member_file_paths=members,
                    confidence=proposal.confidence,
                    rationale=proposal.rationale,
                )
            )

        services.extend(cluster_services)

        shared_members = sorted(assigned_members_by_service.get(SHARED_UTILITY_SERVICE_ID, []))
        if shared_members:
            services.append(
                ServiceDefinition(
                    id=SHARED_UTILITY_SERVICE_ID,
                    name="Shared Utility",
                    kind=ServiceKind.SHARED_BUCKET,
                    layer=ServiceLayer.SHARED,
                    summary="Files used across multiple inferred services or explicitly marked as shared.",
                    member_file_paths=shared_members,
                    rationale="Deterministic shared bucket produced during service-group resolution.",
                )
            )

        unclassified_members = sorted(assigned_members_by_service.get(UNCLASSIFIED_SERVICE_ID, []))
        if unclassified_members:
            services.append(
                ServiceDefinition(
                    id=UNCLASSIFIED_SERVICE_ID,
                    name="Unclassified",
                    kind=ServiceKind.UNCLASSIFIED_BUCKET,
                    layer=ServiceLayer.UNKNOWN,
                    summary="Files that were not grounded in any inferred service proposal.",
                    member_file_paths=unclassified_members,
                    rationale="Deterministic fallback bucket for files without a grounded service assignment.",
                )
            )

        return ServiceGroupingArtifact(
            grouping_id=service_grouping_id_for_graph(structural_graph.graph_id),
            template_version=template_version,
            structural_graph_id=structural_graph.graph_id,
            repo_path=structural_graph.repo_path,
            known_file_paths=known_file_paths,
            architecture_summary=payload.architecture_summary,
            services=services,
            file_assignments=file_assignments,
            llm_invocation=llm_invocation,
            summary=ServiceGroupingSummary(
                service_count=len(services),
                inferred_service_count=sum(1 for item in services if item.kind == ServiceKind.INFERRED),
                file_count=len(known_file_paths),
                shared_file_count=len(shared_members),
                unclassified_file_count=len(unclassified_members),
                ambiguous_file_count=len(overlap_file_paths),
                invented_file_reference_count=len(invented_file_paths),
                dropped_service_count=len(set(dropped_service_names)),
            ),
            diagnostics=ServiceGroupingDiagnostics(
                prompt_file_count=len(structural_graph.nodes),
                prompt_edge_count=len(structural_graph.structural_edges),
                total_prompt_chars=llm_invocation.system_prompt_chars + llm_invocation.user_prompt_chars,
                invented_file_paths=sorted(invented_file_paths),
                overlap_file_paths=overlap_file_paths,
                shared_file_paths=shared_members,
                unclassified_file_paths=unclassified_members,
                connectivity_promoted_file_paths=connectivity_promoted_file_paths,
                directory_promoted_file_paths=directory_promoted_file_paths,
                cluster_promoted_file_paths=cluster_promoted_file_paths,
                empty_service_names=sorted(set(empty_service_names)),
                dropped_service_names=sorted(set(dropped_service_names)),
            ),
        )

    def _promote_unclassified_assignments(
        self,
        *,
        assignments: list[_AssignmentState],
        structural_graph: StructuralGraphArtifact,
        explicit_unclassified_paths: set[str],
        proposed_services: list[_ProposedService],
    ) -> tuple[list[str], list[str]]:
        inferred_service_ids = {service.id for service in proposed_services}
        if not inferred_service_ids:
            return [], []

        assignments_by_file = {assignment.file_path: assignment for assignment in assignments}
        neighbors_by_file = self._neighbors_by_file(structural_graph)
        dominant_bucket_by_service = self._dominant_directory_bucket_by_service(assignments)
        connectivity_promoted: list[str] = []

        for assignment in assignments:
            if assignment.assignment_kind != ServiceAssignmentKind.UNCLASSIFIED:
                continue
            if assignment.file_path in explicit_unclassified_paths:
                continue
            winner = self._single_best_service(
                self._connectivity_service_votes(
                    file_path=assignment.file_path,
                    neighbors=neighbors_by_file.get(assignment.file_path, []),
                    assignments_by_file=assignments_by_file,
                    inferred_service_ids=inferred_service_ids,
                    dominant_bucket_by_service=dominant_bucket_by_service,
                )
            )
            if winner is None:
                continue
            assignment.assigned_service_id = winner
            assignment.assignment_kind = ServiceAssignmentKind.PRIMARY
            assignment.resolution_source = ServiceResolutionSource.CONNECTIVITY_PRIMARY
            assignment.rationale = "Deterministically assigned to the strongest neighboring inferred service based on structural connectivity."
            connectivity_promoted.append(assignment.file_path)

        directory_promoted: list[str] = []
        assignments_by_file = {assignment.file_path: assignment for assignment in assignments}
        for assignment in assignments:
            if assignment.assignment_kind != ServiceAssignmentKind.UNCLASSIFIED:
                continue
            if assignment.file_path in explicit_unclassified_paths:
                continue
            winner = self._single_best_service(self._directory_service_votes(assignment.file_path, assignments_by_file, inferred_service_ids))
            if winner is None:
                continue
            assignment.assigned_service_id = winner
            assignment.assignment_kind = ServiceAssignmentKind.PRIMARY
            assignment.resolution_source = ServiceResolutionSource.DIRECTORY_PRIMARY
            assignment.rationale = "Deterministically assigned to the dominant inferred service in the nearest grounded directory cluster."
            directory_promoted.append(assignment.file_path)

        return sorted(connectivity_promoted), sorted(directory_promoted)

    def _connectivity_service_votes(
        self,
        *,
        file_path: str,
        neighbors: set[str],
        assignments_by_file: dict[str, _AssignmentState],
        inferred_service_ids: set[str],
        dominant_bucket_by_service: dict[str, str],
    ) -> Counter[str]:
        file_bucket = self._directory_bucket(file_path)
        counts: Counter[str] = Counter()
        for neighbor in neighbors:
            assigned_service_id = assignments_by_file[neighbor].assigned_service_id
            if assigned_service_id not in inferred_service_ids:
                continue
            dominant_bucket = dominant_bucket_by_service.get(assigned_service_id)
            if dominant_bucket is None:
                continue
            if "/" in dominant_bucket and "/" in file_bucket:
                if dominant_bucket != file_bucket:
                    continue
            elif ("/" in dominant_bucket) != ("/" in file_bucket):
                continue
            elif "/" not in dominant_bucket and "/" not in file_bucket:
                pass
            elif dominant_bucket != file_bucket and self._top_level_prefix(dominant_bucket) != self._top_level_prefix(file_bucket):
                continue
            counts[assigned_service_id] += 1
        return counts

    def _cluster_remaining_unclassified_assignments(
        self,
        *,
        assignments: list[_AssignmentState],
        explicit_unclassified_paths: set[str],
        existing_ids: set[str],
    ) -> tuple[list[ServiceDefinition], list[str]]:
        cluster_candidates: dict[str, list[_AssignmentState]] = {}
        for assignment in assignments:
            if assignment.assignment_kind != ServiceAssignmentKind.UNCLASSIFIED:
                continue
            if assignment.file_path in explicit_unclassified_paths:
                continue
            prefix = self._cluster_prefix(assignment.file_path)
            cluster_candidates.setdefault(prefix, []).append(assignment)

        cluster_services: list[ServiceDefinition] = []
        cluster_promoted: list[str] = []
        for prefix in sorted(cluster_candidates):
            items = sorted(cluster_candidates[prefix], key=lambda item: item.file_path)
            display_prefix = "root" if prefix == "." else prefix
            service_name = f"{display_prefix.replace('/', ' ').replace('-', ' ').replace('_', ' ').title()} Cluster"
            service_id = self._unique_service_id(service_name, existing_ids)
            for assignment in items:
                assignment.assigned_service_id = service_id
                assignment.assignment_kind = ServiceAssignmentKind.PRIMARY
                assignment.resolution_source = ServiceResolutionSource.CLUSTER_PRIMARY
                assignment.rationale = f"Deterministically grouped into a residual directory cluster for the top-level path prefix '{prefix}'."
                cluster_promoted.append(assignment.file_path)
            cluster_services.append(
                ServiceDefinition(
                    id=service_id,
                    name=service_name,
                    kind=ServiceKind.DETERMINISTIC_CLUSTER,
                    layer=self._layer_for_prefix(prefix),
                    summary=f"Deterministic residual cluster for files under the top-level path prefix '{prefix}'.",
                    member_file_paths=[assignment.file_path for assignment in items],
                    rationale="Created deterministically to avoid leaving a cohesive residual directory subtree ungrouped.",
                )
            )
        return cluster_services, sorted(cluster_promoted)

    def _neighbors_by_file(self, structural_graph: StructuralGraphArtifact) -> dict[str, set[str]]:
        neighbors_by_file: dict[str, set[str]] = {node.path: set() for node in structural_graph.nodes}
        for edge in structural_graph.structural_edges:
            neighbors_by_file.setdefault(edge.source, set()).add(edge.target)
            neighbors_by_file.setdefault(edge.target, set()).add(edge.source)
        return neighbors_by_file

    def _directory_service_votes(
        self,
        file_path: str,
        assignments_by_file: dict[str, _AssignmentState],
        inferred_service_ids: set[str],
    ) -> Counter[str]:
        path = PurePosixPath(file_path)
        parents = [str(parent) for parent in path.parents if str(parent) not in {".", ""}]
        file_bucket = self._directory_bucket(file_path)
        for parent in parents:
            counts: Counter[str] = Counter(
                assignment.assigned_service_id
                for other_path, assignment in assignments_by_file.items()
                if other_path != file_path
                and self._is_in_directory(other_path, parent)
                and assignment.assigned_service_id in inferred_service_ids
                and self._directory_vote_allowed(
                    file_path=file_path,
                    other_path=other_path,
                )
            )
            if counts:
                if parent != file_bucket and max(counts.values()) < 2:
                    continue
                return counts
        return Counter()

    def _is_in_directory(self, file_path: str, directory: str) -> bool:
        return file_path == directory or file_path.startswith(f"{directory}/")

    def _single_best_service(self, counts: Counter[str]) -> str | None:
        if not counts:
            return None
        best_count = max(counts.values())
        winners = sorted(service_id for service_id, count in counts.items() if count == best_count)
        if len(winners) != 1:
            return None
        return winners[0]

    def _top_level_prefix(self, file_path: str) -> str:
        return PurePosixPath(file_path).parts[0]

    def _cluster_prefix(self, file_path: str) -> str:
        return self._directory_bucket(file_path)

    def _layer_for_prefix(self, prefix: str) -> ServiceLayer:
        normalized = prefix.lower()
        if any(token in normalized for token in {"frontend", "client", "web", "ui", "dashboard", "api"}):
            return ServiceLayer.EDGE
        if any(token in normalized for token in {"backend", "server", "pipeline", "reporting", "service"}):
            return ServiceLayer.APPLICATION
        if any(token in normalized for token in {"data", "db", "database", "migration", "model"}):
            return ServiceLayer.DATA
        if any(token in normalized for token in {"llm", "structural", "security", "graph"}):
            return ServiceLayer.DOMAIN
        if any(token in normalized for token in {"adapter", "observability", "shared", "util"}):
            return ServiceLayer.SHARED
        if normalized in {"tests", "test", "fixtures"}:
            return ServiceLayer.UNKNOWN
        return ServiceLayer.UNKNOWN

    def _unique_service_id(self, name: str, existing_ids: set[str]) -> str:
        base = service_id_from_name(name)
        candidate = base
        counter = 2
        while candidate in existing_ids or candidate in {SHARED_UTILITY_SERVICE_ID, UNCLASSIFIED_SERVICE_ID}:
            candidate = f"{base}-{counter}"
            counter += 1
        existing_ids.add(candidate)
        return candidate

    def _files_by_directory_bucket(self, known_file_paths: list[str]) -> dict[str, list[str]]:
        buckets: dict[str, list[str]] = {}
        for path in known_file_paths:
            bucket = self._directory_bucket(path)
            buckets.setdefault(bucket, []).append(path)
        return {bucket: sorted(paths) for bucket, paths in buckets.items()}

    def _ground_service_from_directory_buckets(
        self,
        *,
        service_name: str,
        files_by_directory_bucket: dict[str, list[str]],
    ) -> list[str]:
        service_tokens = self._normalized_tokens(service_name)
        if not service_tokens:
            return []

        best_bucket: str | None = None
        best_score: tuple[int, int, int] | None = None
        for bucket, paths in files_by_directory_bucket.items():
            bucket_tokens = self._normalized_tokens(bucket)
            overlap = service_tokens & bucket_tokens
            if not overlap:
                continue
            exact_segment_matches = sum(1 for token in service_tokens if token in bucket_tokens)
            score = (len(overlap), exact_segment_matches, -len(paths))
            if best_score is None or score > best_score:
                best_bucket = bucket
                best_score = score
        return [] if best_bucket is None else files_by_directory_bucket[best_bucket]

    def _expand_paths_to_directory_bucket(
        self,
        *,
        service_name: str,
        valid_paths: list[str],
        files_by_directory_bucket: dict[str, list[str]],
    ) -> list[str]:
        if not valid_paths:
            return valid_paths
        buckets = {self._directory_bucket(path) for path in valid_paths}
        if len(buckets) != 1:
            return valid_paths
        bucket = next(iter(buckets))
        bucket_tokens = self._normalized_tokens(bucket)
        service_tokens = self._normalized_tokens(service_name)
        if not (bucket_tokens & service_tokens):
            return valid_paths
        return list(files_by_directory_bucket.get(bucket, valid_paths))

    def _normalized_tokens(self, value: str) -> set[str]:
        spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", value.replace("/", " ").replace("_", " ").replace("-", " "))
        raw_tokens = [token.lower() for token in spaced.split() if token]
        normalized: set[str] = set()
        for token in raw_tokens:
            normalized.add(token)
            if token.endswith("s") and len(token) > 3:
                normalized.add(token[:-1])
            if token.endswith("service") and len(token) > len("service"):
                normalized.add(token.removesuffix("service"))
        return normalized

    def _directory_vote_allowed(self, *, file_path: str, other_path: str) -> bool:
        file_bucket = self._directory_bucket(file_path)
        other_bucket = self._directory_bucket(other_path)
        if "/" in file_bucket and "/" in other_bucket:
            return file_bucket == other_bucket
        if ("/" in file_bucket) != ("/" in other_bucket):
            return False
        return True

    def _directory_bucket(self, file_path: str) -> str:
        parts = PurePosixPath(file_path).parts
        if len(parts) >= 3:
            return "/".join(parts[:2])
        if len(parts) >= 2:
            return parts[0]
        return "."

    def _dominant_directory_bucket_by_service(self, assignments: list[_AssignmentState]) -> dict[str, str]:
        buckets_by_service: dict[str, Counter[str]] = {}
        for assignment in assignments:
            if assignment.assignment_kind != ServiceAssignmentKind.PRIMARY:
                continue
            buckets_by_service.setdefault(assignment.assigned_service_id, Counter())[self._directory_bucket(assignment.file_path)] += 1
        return {
            service_id: sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]
            for service_id, counter in buckets_by_service.items()
            if counter
        }
