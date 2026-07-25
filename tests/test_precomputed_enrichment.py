from __future__ import annotations

from pathlib import Path

from prompt_radar.naming.precomputed import (
    load_precomputed_registry,
    sha256_file,
)


def test_generated_200_registry_requires_all_dataset_fingerprints() -> None:
    registry = load_precomputed_registry(
        Path("configs/precomputed_cluster_enrichments.json")
    )
    archive = Path("data/generated_200/dataset.zip")
    dataset = registry.dataset(
        dataset_id="prompt_radar_generated_200",
        dataset_filename="dataset.zip",
        archive_sha256=sha256_file(archive),
        analysis_hash=(
            "210f68123c9fa3a110f86ce55f2e483ae8281af2d348bac6d21f17abe0cf9668"
        ),
    )
    assert dataset is not None
    decision = dataset.cluster(
        "9b34fa5326d0f169aa04a575044d174abeefa3a90908346af718a75f6e98bba8",
        "152c9ef8da6f5de1116bd128f97d480b128981128317022604b775b1b04af030",
    )
    assert decision is not None
    assert decision.action == "abstain"

    assert (
        registry.dataset(
            dataset_id="prompt_radar_generated_200",
            dataset_filename="dataset.zip",
            archive_sha256="0" * 64,
            analysis_hash=dataset.analysis_hash,
        )
        is None
    )
