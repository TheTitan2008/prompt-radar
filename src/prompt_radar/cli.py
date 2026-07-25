"""Typer command-line interface."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from prompt_radar.classification.catalogs import load_use_cases
from prompt_radar.config import load_config
from prompt_radar.demo import generate_demo
from prompt_radar.embeddings.qwen import download_model
from prompt_radar.economics_analysis.service import run_economics
from prompt_radar.errors import PromptRadarError
from prompt_radar.evaluation.metrics import evaluate_predictions
from prompt_radar.ingestion.validator import validate_extracted
from prompt_radar.ingestion.zip_loader import secure_extract_zip
from prompt_radar.io_utils import write_json
from prompt_radar.naming.known_requests import build_known_passport_requests
from prompt_radar.pipeline import analyze_dataset

app = typer.Typer(
    help="Prompt Radar: secure offline run-level prompt analytics.",
    no_args_is_help=True,
)
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_path=False)],
)


def _fail(exc: BaseException) -> None:
    console.print(f"[bold red]Error:[/bold red] {exc}")
    raise typer.Exit(code=1)


@app.command("download-model")
def download_model_command(
    config: Annotated[
        Path, typer.Option("--config", help="Pipeline YAML.")
    ] = Path("configs/pipeline.yaml"),
) -> None:
    """Explicitly download the pinned Qwen embedding snapshot."""
    try:
        pipeline_config = load_config(config)
        path = download_model(pipeline_config)
        console.print(
            f"[green]Pinned model downloaded.[/green]\n"
            f"ID: {pipeline_config.model.id}\n"
            f"Revision: {pipeline_config.model.revision}\n"
            f"Cache: {path}"
        )
    except (PromptRadarError, OSError, ValueError) as exc:
        _fail(exc)


@app.command("generate-demo")
def generate_demo_command(
    output: Annotated[
        Path, typer.Option("--output", help="Destination dataset.zip.")
    ] = Path("data/sample/dataset.zip"),
    ground_truth: Annotated[
        Path,
        typer.Option("--ground-truth", help="Separate evaluation labels."),
    ] = Path("data/sample/ground_truth.jsonl"),
    seed: Annotated[int, typer.Option("--seed")] = 42,
) -> None:
    """Generate deterministic synthetic JSONL plus XLSX/PDF/image attachments."""
    try:
        generate_demo(output, ground_truth, seed)
        console.print(
            f"[green]Demo generated.[/green]\nZIP: {output}\n"
            f"Ground truth (outside ZIP): {ground_truth}"
        )
    except (OSError, RuntimeError, ValueError) as exc:
        _fail(exc)


@app.command("validate")
def validate_command(
    input_path: Annotated[
        Path, typer.Option("--input", exists=True, dir_okay=False)
    ],
    config: Annotated[Path, typer.Option("--config")] = Path(
        "configs/pipeline.yaml"
    ),
    output: Annotated[
        Path | None, typer.Option("--output", help="Optional report JSON path.")
    ] = None,
) -> None:
    """Securely extract and validate a dataset without analyzing it."""
    pipeline_config = load_config(config)
    work = Path("data/work") / (
        "validate-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    )
    try:
        secure_extract_zip(input_path, work, pipeline_config.resources)
        _, report = validate_extracted(work)
        if output:
            write_json(output, report.model_dump(mode="json"))
        table = Table(title="Dataset validation")
        table.add_column("Field")
        table.add_column("Value")
        table.add_row("valid", str(report.valid))
        table.add_row("dataset_id", str(report.dataset_id))
        table.add_row("schema_version", str(report.schema_version))
        table.add_row("records", json.dumps(report.record_counts, ensure_ascii=False))
        table.add_row("issues", str(len(report.issues)))
        console.print(table)
        for issue in report.issues:
            color = "red" if issue.severity == "error" else "yellow"
            console.print(f"[{color}]{issue.code}:[/{color}] {issue.message}")
        if not report.valid:
            raise typer.Exit(code=2)
    except typer.Exit:
        raise
    except (PromptRadarError, OSError, ValueError) as exc:
        _fail(exc)
    finally:
        shutil.rmtree(work, ignore_errors=True)


@app.command("prepare-known-passport-requests")
def prepare_known_passport_requests_command(
    use_cases: Annotated[Path, typer.Option("--use-cases")] = Path(
        "configs/known_use_cases.yaml"
    ),
    output: Annotated[Path, typer.Option("--output")] = Path(
        "outputs/known_use_case_passport_requests.json"
    ),
    model: Annotated[str, typer.Option("--model")] = (
        "<configured-qwen-or-deepseek-model>"
    ),
) -> None:
    """Prepare 31 unsent API request bodies for known-passport review."""
    try:
        catalog = load_use_cases(use_cases)
        requests = build_known_passport_requests(catalog, model=model)
        write_json(output, requests)
        console.print(
            f"[green]Prepared {len(requests)} unsent requests.[/green] {output}"
        )
    except (OSError, ValueError) as exc:
        _fail(exc)


@app.command("analyze")
def analyze_command(
    input_path: Annotated[
        Path, typer.Option("--input", exists=True, dir_okay=False)
    ],
    output: Annotated[Path, typer.Option("--output")] = Path("outputs"),
    config: Annotated[Path, typer.Option("--config")] = Path(
        "configs/pipeline.yaml"
    ),
    categories: Annotated[Path, typer.Option("--categories")] = Path(
        "configs/categories.yaml"
    ),
    use_cases: Annotated[Path, typer.Option("--use-cases")] = Path(
        "configs/known_use_cases.yaml"
    ),
    use_case_passports: Annotated[
        Path, typer.Option("--use-case-passports")
    ] = Path("configs/known_use_case_passports.yaml"),
    offline: Annotated[
        bool,
        typer.Option(
            "--offline/--online",
            help="Offline forbids model downloads and uses the local cache only.",
        ),
    ] = True,
    embedding_backend: Annotated[
        str,
        typer.Option(
            "--embedding-backend",
            help="qwen for real analysis; fake only for tests/mechanical smoke runs.",
        ),
    ] = "qwen",
    keep_work: Annotated[bool, typer.Option("--keep-work")] = False,
    enrich_clusters: Annotated[
        bool,
        typer.Option(
            "--enrich-clusters/--no-enrich-clusters",
            help=(
                "Explicitly send only eligible emerging clusters to a configured "
                "Qwen/DeepSeek chat-completions endpoint."
            ),
        ),
    ] = False,
    api_env_file: Annotated[
        Path,
        typer.Option(
            "--api-env-file",
            help="Local ignored .env file containing Qwen/DeepSeek settings.",
        ),
    ] = Path(".env"),
    precomputed_enrichments: Annotated[
        Path | None,
        typer.Option(
            "--precomputed-enrichments",
            help=(
                "Strict local enrichment registry for immutable demo datasets."
            ),
        ),
    ] = Path("configs/precomputed_cluster_enrichments.json"),
) -> None:
    """Run the complete pipeline; ground truth is never accepted here."""
    try:
        output_dir = analyze_dataset(
            input_path=input_path,
            output_root=output,
            config_path=config,
            categories_path=categories,
            use_cases_path=use_cases,
            use_case_passports_path=use_case_passports,
            embedding_backend=embedding_backend,
            offline=offline,
            keep_work=keep_work,
            enrich_clusters=enrich_clusters,
            api_env_file=api_env_file,
            precomputed_enrichments_path=precomputed_enrichments,
        )
        console.print(f"[green]Analysis complete.[/green] {output_dir}")
    except (PromptRadarError, OSError, ValueError) as exc:
        _fail(exc)


@app.command("evaluate")
def evaluate_command(
    predictions: Annotated[
        Path, typer.Option("--predictions", exists=True, dir_okay=False)
    ],
    ground_truth: Annotated[
        Path, typer.Option("--ground-truth", exists=True, dir_okay=False)
    ],
    output: Annotated[
        Path | None, typer.Option("--output", help="Evaluation JSON path.")
    ] = None,
) -> None:
    """Evaluate predictions against labels kept separate from `analyze`."""
    try:
        target = output or predictions.parent / "evaluation.json"
        report = evaluate_predictions(predictions, ground_truth, target)
        console.print_json(json.dumps(report, ensure_ascii=False))
        console.print(f"[green]Evaluation written:[/green] {target}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _fail(exc)


@app.command("economics")
def economics_command(
    analysis: Annotated[
        Path, typer.Option("--analysis", exists=True, file_okay=False)
    ],
    cost_config: Annotated[
        Path, typer.Option("--cost-config", exists=True, dir_okay=False)
    ],
    passports: Annotated[
        Path | None,
        typer.Option(
            "--passports",
            exists=True,
            dir_okay=False,
            help=(
                "Optional reviewed overrides. Embedded known/API passports "
                "are loaded from --analysis automatically."
            ),
        ),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
    quality: Annotated[
        Path | None,
        typer.Option("--quality", exists=True, dir_okay=False),
    ] = None,
) -> None:
    """Calculate evidence-aware economics fully offline."""
    try:
        target = output or analysis / "economics"
        result = run_economics(
            analysis_dir=analysis,
            passports_path=passports,
            quality_path=quality,
            cost_config_path=cost_config,
            output_dir=target,
        )
        console.print(f"[green]Economics complete.[/green] {result}")
    except (PromptRadarError, OSError, ValueError, json.JSONDecodeError) as exc:
        _fail(exc)


if __name__ == "__main__":
    app()
