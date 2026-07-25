"""End-to-end analysis orchestration."""

from __future__ import annotations

import importlib.metadata
import io
import json
import logging
import platform
import shutil
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from prompt_radar.analysis_binding import (
    CLUSTER_ENRICHMENT_PROMPT_VERSION,
    analysis_binding_hash,
    cluster_fingerprint,
    member_run_ids_hash,
)
from prompt_radar.attachments.registry import extract_attachment
from prompt_radar.classification.catalogs import (
    load_categories,
    load_use_case_passports,
    load_use_cases,
)
from prompt_radar.classification.classifier import KnownMatcher
from prompt_radar.clustering.hdbscan_clusterer import cluster_residual
from prompt_radar.clustering.local_labeler import provisional_label
from prompt_radar.clustering.representatives import representative_indexes
from prompt_radar.config import PipelineConfig, load_config
from prompt_radar.economics import build_local_economic_context
from prompt_radar.embeddings.base import EmbeddingService
from prompt_radar.embeddings.fake import HashingEmbeddingService
from prompt_radar.embeddings.qwen import QwenEmbeddingService
from prompt_radar.environment import load_api_env_file
from prompt_radar.ingestion.validator import validate_extracted
from prompt_radar.ingestion.zip_loader import secure_extract_zip
from prompt_radar.io_utils import (
    atomic_write_bytes,
    atomic_write_text,
    write_csv,
    write_json,
    write_jsonl,
)
from prompt_radar.naming.base import ClusterNamingRequest
from prompt_radar.naming.openai_compatible import (
    ApiSettings,
    OpenAICompatibleClusterEnrichmentProvider,
)
from prompt_radar.naming.payload_builder import build_naming_payload
from prompt_radar.naming.precomputed import (
    load_precomputed_registry,
    sha256_file,
)
from prompt_radar.errors import ExternalApiError
from prompt_radar.preprocessing.message_parser import extract_current_goal
from prompt_radar.preprocessing.prompt_router import choose_mode
from prompt_radar.preprocessing.run_builder import build_run_tasks
from prompt_radar.preprocessing.task_passport import build_task_passport
from prompt_radar.reporting.markdown_report import build_markdown_report
from prompt_radar.retrieval.rag import retrieve_top_k

LOGGER = logging.getLogger(__name__)


def _dependency_versions() -> dict[str, str]:
    names = (
        "numpy",
        "pydantic",
        "PyYAML",
        "sentence-transformers",
        "transformers",
        "torch",
        "scikit-learn",
        "hdbscan",
        "umap-learn",
        "pypdf",
        "openpyxl",
        "python-docx",
    )
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def _build_embedding_service(
    backend: str, config: PipelineConfig, offline: bool
) -> EmbeddingService:
    if backend == "fake":
        return HashingEmbeddingService()
    if backend == "qwen":
        return QwenEmbeddingService(config, offline=offline)
    raise ValueError(f"Unknown embedding backend: {backend}")


def _save_npz(path: Path, vectors: np.ndarray, run_ids: list[str]) -> None:
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer,
        embeddings=vectors.astype(np.float32, copy=False),
        run_ids=np.asarray(run_ids, dtype=str),
    )
    atomic_write_bytes(path, buffer.getvalue())


def _flat_csv_record(item: dict[str, Any]) -> dict[str, Any]:
    matches = item.get("known_use_case_matches") or []
    categories = item.get("categories") or []
    passport = item.get("economic_passport") or {}
    manual_minutes = passport.get("manual_minutes") or {}
    followup_minutes = passport.get("human_followup_minutes") or {}
    local_economics = item.get("local_economics") or {}
    manual_value = local_economics.get("manual_work_value_rub") or {}
    return {
        "run_id": item["run_id"],
        "conversation_id": item["conversation_id"],
        "user_id": item["user_id"],
        "processing_mode": item["processing_mode"],
        "current_goal": item["current_goal"],
        "discovery_status": item["discovery_status"],
        "primary_category": categories[0]["name"] if categories else "",
        "top_known_use_case": matches[0]["name"] if matches else "",
        "classification_similarity": item["classification_similarity"],
        "cluster_id": item["cluster_id"],
        "membership_probability": item["membership_probability"],
        "manual_minutes_base": manual_minutes.get("base"),
        "human_followup_minutes_base": followup_minutes.get("base"),
        "manual_work_value_rub_base": manual_value.get("base"),
    }


def analyze_dataset(
    *,
    input_path: Path,
    output_root: Path,
    config_path: Path,
    categories_path: Path,
    use_cases_path: Path,
    use_case_passports_path: Path = Path(
        "configs/known_use_case_passports.yaml"
    ),
    embedding_backend: str = "qwen",
    offline: bool = True,
    keep_work: bool = False,
    enrich_clusters: bool = False,
    api_env_file: Path | None = Path(".env"),
    precomputed_enrichments_path: Path | None = Path(
        "configs/precomputed_cluster_enrichments.json"
    ),
) -> Path:
    """Run secure ingestion, run-level analysis and atomic output writing."""
    analysis_started_at = datetime.now(timezone.utc)
    analysis_started_monotonic = time.perf_counter()
    config = load_config(config_path)
    precomputed_registry = load_precomputed_registry(
        precomputed_enrichments_path
    )
    archive_sha256 = sha256_file(input_path)
    enrichment_provider = None

    def get_enrichment_provider() -> (
        OpenAICompatibleClusterEnrichmentProvider
    ):
        nonlocal enrichment_provider
        if enrichment_provider is not None:
            return enrichment_provider
        if api_env_file is not None:
            load_api_env_file(api_env_file)
        enrichment_provider = OpenAICompatibleClusterEnrichmentProvider(
            settings=ApiSettings.from_environment(),
            config=config.cluster_enrichment,
            cache_dir=Path(config.cluster_enrichment.cache_dir),
        )
        return enrichment_provider
    work_root = Path("data/work") / (
        input_path.stem
        + "-"
        + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    )
    try:
        secure_extract_zip(input_path, work_root, config.resources)
        bundle, validation = validate_extracted(work_root)
        if bundle is None:
            raise ValueError(
                "Dataset validation failed: "
                + "; ".join(issue.message for issue in validation.issues[:5])
            )
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = output_root / f"{bundle.manifest.dataset_id}_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=False)
        write_json(
            output_dir / "validation_report.json",
            validation.model_dump(mode="json"),
        )
        user_by_id = {user.user_id: user for user in bundle.users}
        write_json(
            output_dir / "users_summary.json",
            [
                {
                    "user_id": user.user_id,
                    "display_name": user.display_name,
                    "department": user.department,
                    "role": user.role,
                }
                for user in sorted(bundle.users, key=lambda item: item.user_id)
            ],
        )

        embeddings = _build_embedding_service(
            embedding_backend, config, offline=offline
        )
        enrichment_source_model = embeddings.model_id
        enrichment_source_revision = embeddings.model_revision
        categories = load_categories(categories_path)
        use_cases = load_use_cases(use_cases_path)
        use_case_passports = load_use_case_passports(
            use_case_passports_path, use_cases
        )
        matcher = KnownMatcher(
            categories, use_cases, embeddings, config.classification
        )
        attachment_by_id = {
            attachment.attachment_id: attachment for attachment in bundle.attachments
        }
        extraction_by_id = {
            attachment_id: extract_attachment(
                attachment, Path(bundle.root), config.attachments
            )
            for attachment_id, attachment in attachment_by_id.items()
        }
        warnings: list[dict[str, Any]] = []
        for extraction in extraction_by_id.values():
            for warning in extraction.warnings:
                warnings.append(
                    {
                        "attachment_id": extraction.attachment_id,
                        "filename": extraction.filename,
                        "warning": warning,
                        "extraction_status": extraction.extraction_status,
                    }
                )
            if (
                extraction.extraction_status not in {"success"}
                and not extraction.warnings
            ):
                warnings.append(
                    {
                        "attachment_id": extraction.attachment_id,
                        "filename": extraction.filename,
                        "warning": "Attachment was not text-extracted",
                        "extraction_status": extraction.extraction_status,
                    }
                )

        tasks = build_run_tasks(bundle, config, embeddings)
        configuration_hash = config.stable_hash()
        analysis_hash = analysis_binding_hash(
            dataset_id=bundle.manifest.dataset_id,
            configuration_hash=configuration_hash,
            model_id=embeddings.model_id,
            model_revision=embeddings.model_revision,
            preprocessing_version=embeddings.preprocessing_version,
            run_ids=[task.run_id for task in tasks],
        )
        precomputed_dataset = precomputed_registry.dataset(
            dataset_id=bundle.manifest.dataset_id,
            dataset_filename=input_path.name,
            archive_sha256=archive_sha256,
            analysis_hash=analysis_hash,
        )
        analyses: list[dict[str, Any]] = []
        retrieved_rows: list[dict[str, Any]] = []
        for task in tasks:
            task_user = user_by_id.get(task.user_id)
            goal = extract_current_goal(task.messages)
            mode, raw_tokens = choose_mode(
                task.user_prompt_text,
                task.attachment_ids,
                embeddings.tokenizer,
                config.text_processing,
            )
            task_extractions = [
                extraction_by_id[attachment_id]
                for attachment_id in task.attachment_ids
                if attachment_id in extraction_by_id
            ]
            retrieved = retrieve_top_k(
                goal.current_goal,
                task_extractions,
                embeddings,
                chunk_size=config.text_processing.chunk_size_tokens,
                overlap=config.text_processing.chunk_overlap_tokens,
                top_k=config.text_processing.rag_top_k,
            )
            for item in retrieved:
                row = item.to_dict()
                row["run_id"] = task.run_id
                retrieved_rows.append(row)
            passport, evidence = build_task_passport(
                task.user_prompt_text,
                goal,
                embeddings.tokenizer,
                config.text_processing,
                tool_names=task.tool_names,
                retrieved_texts=[item.text for item in retrieved],
            )
            classification = matcher.classify(passport)
            classification_dict = classification.to_dict()
            known_matches = classification_dict["known_use_case_matches"]
            categories_out = classification_dict["category_candidates"]
            attachment_tokens = sum(
                embeddings.tokenizer.count_tokens(section.text)
                for extraction in task_extractions
                for section in extraction.sections
            )
            top_similarity = (
                float(known_matches[0]["similarity_score"])
                if known_matches
                else 0.0
            )
            threshold = (
                float(known_matches[0]["threshold_used"])
                if known_matches
                else config.classification.known_use_case_threshold
            )
            known_passport = None
            known_passports: list[dict[str, Any]] = []
            known_economics = None
            if (
                classification.classification_status == "matched_known"
                and known_matches
            ):
                passport_id = str(known_matches[0]["id"])
                passport_record = use_case_passports[passport_id]
                known_passport = passport_record.model_dump(mode="json")
                known_economics = build_local_economic_context(
                    passport_record
                )
                known_passports = [
                    use_case_passports[str(match["id"])].model_dump(
                        mode="json"
                    )
                    for match in known_matches
                    if bool(match.get("accepted"))
                ]
            analyses.append(
                {
                    "run_id": task.run_id,
                    "conversation_id": task.conversation_id,
                    "user_id": task.user_id,
                    "user_display_name": (
                        task_user.display_name if task_user else None
                    ),
                    "user_department": (
                        task_user.department if task_user else None
                    ),
                    "user_role": task_user.role if task_user else None,
                    "message_ids": [message.message_id for message in task.messages],
                    "processing_mode": str(mode),
                    "raw_prompt_token_count": raw_tokens,
                    "attachment_token_count": attachment_tokens,
                    "current_goal": goal.current_goal,
                    "task_passport_text": passport,
                    "goal_evidence_message_ids": goal.evidence_message_ids,
                    "goal_evidence_spans": goal.evidence_spans,
                    "goal_extraction_method": goal.method,
                    "goal_confidence": goal.confidence,
                    "multiple_goals": goal.multiple_goals,
                    "ambiguity_reason": goal.ambiguity_reason,
                    "summary_mode": "extractive",
                    "api_summary_used": False,
                    "attachment_ids": task.attachment_ids,
                    "tool_names": task.tool_names,
                    "run_metadata": task.run_metadata,
                    "categories": categories_out,
                    "primary_category": classification_dict["primary_category"],
                    "additional_categories": classification_dict[
                        "additional_categories"
                    ],
                    "known_use_case_matches": known_matches,
                    "economic_passport": known_passport,
                    "economic_passports": known_passports,
                    "local_economics": known_economics,
                    "classification_status": classification.classification_status,
                    "classification_similarity": top_similarity,
                    "classification_threshold": threshold,
                    "classification_explanation": classification.explanation,
                    "discovery_status": classification.discovery_status,
                    "retrieved_chunk_ids": [item.chunk_id for item in retrieved],
                    "evidence_chunk_ids": [item.chunk_id for item in evidence],
                    "cluster_id": -1,
                    "membership_probability": 0.0,
                    "outlier_score": 1.0,
                }
            )

        task_vectors = embeddings.encode(
            [item["task_passport_text"] for item in analyses], mode="query"
        )
        residual_indexes = [
            index
            for index, item in enumerate(analyses)
            if item["classification_status"] == "residual"
        ]
        residual_vectors = (
            task_vectors[residual_indexes]
            if residual_indexes
            else np.empty((0, task_vectors.shape[1]), dtype=np.float32)
        )
        clustering = cluster_residual(residual_vectors, config.clustering)
        for residual_index, assignment in zip(
            residual_indexes, clustering.assignments, strict=True
        ):
            item = analyses[residual_index]
            item["cluster_id"] = assignment.cluster_id
            item["membership_probability"] = assignment.membership_probability
            item["outlier_score"] = assignment.outlier_score
            item["discovery_status"] = (
                "emerging" if assignment.cluster_id >= 0 else "unresolved"
            )

        cluster_members: list[dict[str, Any]] = []
        clusters: list[dict[str, Any]] = []
        payloads: list[dict[str, Any]] = []
        enrichments: list[dict[str, Any]] = []
        external_api_call_count = 0
        external_api_failure_count = 0
        external_api_cache_hit_count = 0
        external_api_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        precomputed_enrichment_count = 0
        precomputed_abstention_count = 0
        assignments_by_cluster: dict[int, list[int]] = defaultdict(list)
        for index in residual_indexes:
            cluster_id = int(analyses[index]["cluster_id"])
            if cluster_id >= 0:
                assignments_by_cluster[cluster_id].append(index)
        for cluster_id, member_indexes in sorted(assignments_by_cluster.items()):
            vectors = task_vectors[member_indexes]
            member_run_ids = [
                str(analyses[index]["run_id"]) for index in member_indexes
            ]
            members_hash = member_run_ids_hash(member_run_ids)
            fingerprint = cluster_fingerprint(
                analysis_hash=analysis_hash,
                member_ids_hash=members_hash,
                task_passport_texts=[
                    str(analyses[index]["task_passport_text"])
                    for index in member_indexes
                ],
            )
            for index in member_indexes:
                analyses[index]["cluster_fingerprint"] = fingerprint
                analyses[index]["analysis_hash"] = analysis_hash
            representatives, boundaries = representative_indexes(
                vectors,
                representative_count=config.clustering.representative_count,
                boundary_count=config.clustering.boundary_count,
            )
            representative_global = [
                member_indexes[index] for index, _ in representatives
            ]
            broad = next(
                (
                    analyses[index]["categories"][0]["name"]
                    for index in member_indexes
                    if analyses[index]["categories"]
                ),
                None,
            )
            label, keywords = provisional_label(
                [analyses[index]["task_passport_text"] for index in member_indexes],
                broad,
            )
            representative_records = [
                {
                    "run_id": analyses[member_indexes[local_index]]["run_id"],
                    "task_passport_text": analyses[member_indexes[local_index]][
                        "task_passport_text"
                    ],
                    "distance_to_medoid": distance,
                    "category": (
                        analyses[member_indexes[local_index]]["categories"][0]["name"]
                        if analyses[member_indexes[local_index]]["categories"]
                        else None
                    ),
                    "similarity_score": analyses[member_indexes[local_index]][
                        "classification_similarity"
                    ],
                }
                for local_index, distance in representatives
            ]
            boundary_records = [
                {
                    "run_id": analyses[member_indexes[local_index]]["run_id"],
                    "distance_to_medoid": distance,
                }
                for local_index, distance in boundaries
            ]
            cluster_record = {
                "cluster_id": cluster_id,
                "analysis_dataset_id": bundle.manifest.dataset_id,
                "analysis_hash": analysis_hash,
                "analysis_configuration_hash": configuration_hash,
                "cluster_fingerprint": fingerprint,
                "member_run_ids_hash": members_hash,
                "source_model": enrichment_source_model,
                "source_model_revision": enrichment_source_revision,
                "source_prompt_version": CLUSTER_ENRICHMENT_PROMPT_VERSION,
                "member_count": len(member_indexes),
                "provisional_label": label,
                "cluster_name": label,
                "label_source": "local_heuristic",
                "label_is_final": False,
                "keywords": keywords,
                "representative_examples": representative_records,
                "boundary_examples": boundary_records,
                "api_enrichment_status": "not_requested",
            }
            request = ClusterNamingRequest(
                cluster_id=cluster_id,
                known_categories=[broad] if broad else [],
                representative_examples=[
                    analyses[index]["current_goal"]
                    for index in representative_global
                ],
                local_keywords=keywords,
                member_count=len(member_indexes),
                analysis_dataset_id=bundle.manifest.dataset_id,
                analysis_hash=analysis_hash,
                analysis_configuration_hash=configuration_hash,
                cluster_fingerprint=fingerprint,
                member_run_ids_hash=members_hash,
                source_model=enrichment_source_model,
                source_model_revision=enrichment_source_revision,
                source_prompt_version=CLUSTER_ENRICHMENT_PROMPT_VERSION,
            )
            eligible = (
                len(member_indexes)
                >= config.cluster_enrichment.min_cluster_members
            )
            precomputed = (
                precomputed_dataset.cluster(fingerprint, members_hash)
                if precomputed_dataset is not None
                else None
            )
            payload = build_naming_payload(
                request,
                eligible=eligible,
                minimum_members=config.cluster_enrichment.min_cluster_members,
                max_payload_chars=config.cluster_enrichment.max_api_payload_chars,
            )
            if eligible and precomputed is not None:
                precomputed_enrichment_count += 1
                source_fields = {
                    "source_model": precomputed.source_model,
                    "source_model_revision": (
                        precomputed.source_model_revision
                    ),
                    "source_prompt_version": (
                        precomputed.source_prompt_version
                    ),
                }
                cluster_record.update(source_fields)
                request.source_model = precomputed.source_model
                request.source_model_revision = (
                    precomputed.source_model_revision
                )
                request.source_prompt_version = (
                    precomputed.source_prompt_version
                )
                payload.update(
                    {
                        **source_fields,
                        "api_called": False,
                        "api_status": (
                            "precomputed_local"
                            if precomputed.action == "enrich"
                            else "precomputed_abstained"
                        ),
                    }
                )
                if precomputed.action == "enrich":
                    result = precomputed.result
                    if result is None:  # protected by registry validation
                        raise ValueError("precomputed enrichment has no result")
                    enrichment = result.model_dump(mode="json")
                    local_economics = build_local_economic_context(result)
                    cluster_record.update(
                        {
                            "cluster_name": result.cluster_name,
                            "label_source": "local_precomputed",
                            "label_is_final": True,
                            "api_enrichment_status": "precomputed_success",
                            "economic_passport": enrichment,
                            "local_economics": local_economics,
                        }
                    )
                else:
                    precomputed_abstention_count += 1
                    enrichment = None
                    local_economics = None
                    cluster_record.update(
                        {
                            "cluster_name": precomputed.cluster_name,
                            "label_source": "local_precomputed",
                            "label_is_final": True,
                            "api_enrichment_status": (
                                "precomputed_abstained"
                            ),
                            "enrichment_abstention_reason": (
                                precomputed.abstention_reason
                            ),
                        }
                    )
                enrichments.append(
                    {
                        "cluster_id": cluster_id,
                        "analysis_dataset_id": bundle.manifest.dataset_id,
                        "analysis_hash": analysis_hash,
                        "analysis_configuration_hash": configuration_hash,
                        "cluster_fingerprint": fingerprint,
                        "member_run_ids_hash": members_hash,
                        **source_fields,
                        "member_count": len(member_indexes),
                        "provider_protocol": "local_precomputed",
                        "action": precomputed.action,
                        "abstention_reason": (
                            precomputed.abstention_reason
                        ),
                        "result": enrichment,
                        "local_economics": local_economics,
                    }
                )
            elif not eligible:
                cluster_record["api_enrichment_status"] = (
                    "skipped_below_minimum"
                )
            elif not enrich_clusters:
                cluster_record["api_enrichment_status"] = "prepared_not_called"
            else:
                provider = get_enrichment_provider()
                enrichment_source_model = provider.settings.model
                enrichment_source_revision = provider.settings.model_revision
                cluster_record.update(
                    {
                        "source_model": enrichment_source_model,
                        "source_model_revision": enrichment_source_revision,
                    }
                )
                request.source_model = enrichment_source_model
                request.source_model_revision = enrichment_source_revision
                payload["api_status"] = "request_attempted"
                try:
                    result = provider.name_cluster(request)
                    call_metadata = provider.last_call_metadata.copy()
                    payload["api_called"] = bool(
                        call_metadata.get("http_called")
                    )
                    if call_metadata.get("http_called"):
                        external_api_call_count += 1
                    if call_metadata.get("cache_hit"):
                        external_api_cache_hit_count += 1
                    if call_metadata.get("http_called"):
                        for usage_name in external_api_usage:
                            external_api_usage[usage_name] += int(
                                (call_metadata.get("usage") or {}).get(
                                    usage_name, 0
                                )
                            )
                    enrichment = result.model_dump(mode="json")
                    local_economics = build_local_economic_context(result)
                    cluster_record.update(
                        {
                            "cluster_name": result.cluster_name,
                            "label_source": "external_api",
                            "label_is_final": False,
                            "api_enrichment_status": (
                                "cache_success"
                                if call_metadata.get("cache_hit")
                                else "success"
                            ),
                            "economic_passport": enrichment,
                            "local_economics": local_economics,
                        }
                    )
                    payload["api_status"] = (
                        "cache_success"
                        if call_metadata.get("cache_hit")
                        else "success"
                    )
                    payload["api_telemetry"] = call_metadata
                    enrichments.append(
                        {
                            "cluster_id": cluster_id,
                            "analysis_dataset_id": bundle.manifest.dataset_id,
                            "analysis_hash": analysis_hash,
                            "analysis_configuration_hash": configuration_hash,
                            "cluster_fingerprint": fingerprint,
                            "member_run_ids_hash": members_hash,
                            "source_model": enrichment_source_model,
                            "source_model_revision": enrichment_source_revision,
                            "source_prompt_version": (
                                CLUSTER_ENRICHMENT_PROMPT_VERSION
                            ),
                            "member_count": len(member_indexes),
                            "provider_protocol": "openai_compatible",
                            "api_telemetry": call_metadata,
                            "result": enrichment,
                            "local_economics": local_economics,
                        }
                    )
                except ExternalApiError as exc:
                    call_metadata = provider.last_call_metadata.copy()
                    payload["api_called"] = bool(
                        call_metadata.get("http_called")
                    )
                    if call_metadata.get("http_called"):
                        external_api_call_count += 1
                    external_api_failure_count += 1
                    cluster_record["api_enrichment_status"] = "failed"
                    payload["api_status"] = "failed"
                    payload["api_telemetry"] = call_metadata
                    warnings.append(
                        {
                            "cluster_id": cluster_id,
                            "warning": str(exc),
                            "extraction_status": (
                                "optional_cluster_enrichment_failed"
                            ),
                        }
                    )
            payloads.append(payload)
            clusters.append(cluster_record)
            for index in member_indexes:
                analyses[index]["cluster_name"] = cluster_record[
                    "cluster_name"
                ]
                analyses[index]["cluster_enrichment_status"] = cluster_record[
                    "api_enrichment_status"
                ]
                if cluster_record.get("enrichment_abstention_reason"):
                    analyses[index]["economic_abstention_reason"] = (
                        cluster_record["enrichment_abstention_reason"]
                    )
                cluster_members.append(
                    {
                        "cluster_id": cluster_id,
                        "cluster_fingerprint": fingerprint,
                        "member_run_ids_hash": members_hash,
                        "analysis_hash": analysis_hash,
                        "run_id": analyses[index]["run_id"],
                        "membership_probability": analyses[index][
                            "membership_probability"
                        ],
                        "outlier_score": analyses[index]["outlier_score"],
                    }
                )

        write_jsonl(output_dir / "runs_analysis.jsonl", analyses)
        write_jsonl(
            output_dir / "classification_results.jsonl",
            [
                {
                    "run_id": item["run_id"],
                    "primary_category": item["primary_category"],
                    "additional_categories": item["additional_categories"],
                    "known_use_case_matches": item["known_use_case_matches"],
                    "classification_similarity": item[
                        "classification_similarity"
                    ],
                    "classification_threshold": item[
                        "classification_threshold"
                    ],
                    "classification_status": item["classification_status"],
                    "discovery_status": item["discovery_status"],
                }
                for item in analyses
            ],
        )
        write_json(output_dir / "clusters.json", clusters)
        write_json(
            output_dir / "known_use_case_passports.json",
            [
                {
                    **passport.model_dump(mode="json"),
                    "local_economics": build_local_economic_context(passport),
                }
                for passport in use_case_passports.values()
            ],
        )
        write_jsonl(output_dir / "cluster_members.jsonl", cluster_members)
        write_json(output_dir / "cluster_naming_payloads.json", payloads)
        write_json(output_dir / "cluster_enrichments.json", enrichments)
        write_jsonl(output_dir / "retrieved_chunks.jsonl", retrieved_rows)
        write_jsonl(output_dir / "warnings.jsonl", warnings)
        write_csv(
            output_dir / "runs_analysis.csv",
            [_flat_csv_record(item) for item in analyses],
        )
        _save_npz(
            output_dir / "embeddings.npz",
            task_vectors,
            [item["run_id"] for item in analyses],
        )
        try:
            import pandas as pd

            pd.DataFrame(
                [_flat_csv_record(item) for item in analyses]
            ).to_parquet(output_dir / "runs_analysis.parquet", index=False)
        except Exception as exc:
            warnings.append(
                {
                    "warning": f"Parquet output not written: {exc}",
                    "extraction_status": "optional_output_skipped",
                }
            )
            write_jsonl(output_dir / "warnings.jsonl", warnings)
        analysis_finished_at = datetime.now(timezone.utc)
        metadata = {
            "dataset_id": bundle.manifest.dataset_id,
            "schema_version": bundle.manifest.schema_version,
            "timestamp": timestamp,
            "analysis_started_at": analysis_started_at.isoformat(),
            "analysis_finished_at": analysis_finished_at.isoformat(),
            "analysis_runtime_seconds": round(
                time.perf_counter() - analysis_started_monotonic, 6
            ),
            "git_commit": _git_commit(),
            "python_version": platform.python_version(),
            "dependency_versions": _dependency_versions(),
            "model_id": embeddings.model_id,
            "model_revision": embeddings.model_revision,
            "tokenizer_version": embeddings.tokenizer.version,
            "preprocessing_version": embeddings.preprocessing_version,
            "configuration_hash": configuration_hash,
            "analysis_hash": analysis_hash,
            "random_seed": config.random_seed,
            "device": embeddings.device,
            "offline": offline,
            "embedding_backend": embedding_backend,
            "effective_parameters": {
                "resources": config.resources.model_dump(),
                "text_processing": config.text_processing.model_dump(),
                "classification": config.classification.model_dump(),
                "clustering": clustering.parameters,
                "cluster_enrichment": config.cluster_enrichment.model_dump(),
                "economics": config.economics.model_dump(),
            },
            "clustering_status": clustering.status,
            "processed_records": len(analyses),
            "known_use_case_passport_count": len(use_case_passports),
            "skipped_records": validation.skipped_records,
            "warning_count": len(warnings),
            "external_generative_api_called": external_api_call_count > 0,
            "external_generative_api_call_count": external_api_call_count,
            "external_generative_api_failure_count": (
                external_api_failure_count
            ),
            "external_generative_api_cache_hit_count": (
                external_api_cache_hit_count
            ),
            "external_generative_api_usage": external_api_usage,
            "precomputed_enrichment_count": precomputed_enrichment_count,
            "precomputed_abstention_count": precomputed_abstention_count,
            "precomputed_dataset_matched": precomputed_dataset is not None,
            "input_archive_sha256": archive_sha256,
            "ground_truth_loaded": False,
        }
        write_json(output_dir / "pipeline_metadata.json", metadata)
        report = build_markdown_report(
            dataset_id=bundle.manifest.dataset_id,
            analyses=analyses,
            clusters=clusters,
            warnings=warnings,
            model_id=embeddings.model_id,
            model_revision=embeddings.model_revision,
            external_api_call_count=external_api_call_count,
        )
        atomic_write_text(output_dir / "report.md", report)
        LOGGER.info("Analysis complete: %s", output_dir)
        return output_dir
    finally:
        if not keep_work:
            shutil.rmtree(work_root, ignore_errors=True)


def _git_commit() -> str | None:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
