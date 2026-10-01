"""Typer CLI entry point."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import httpx
import typer
import yaml

from civic_data_qa import __version__
from civic_data_qa.benchmark.manifest import load_manifest
from civic_data_qa.benchmark.runner import run_benchmark
from civic_data_qa.benchmark.snapshots import download_snapshots
from civic_data_qa.config import load_ruleset
from civic_data_qa.engine import run_checks
from civic_data_qa.plugins import list_plugin_names
from civic_data_qa.reporters.backlog import write_backlog_csv, write_backlog_json
from civic_data_qa.reporters.html import write_html_report
from civic_data_qa.reporters.json_report import load_json_results, write_json_results
from civic_data_qa.sources import load_dataset
from civic_data_qa.sources.files import list_gpkg_layers

app = typer.Typer(no_args_is_help=True, add_completion=False)
plugins_app = typer.Typer(help="Plugin management")
benchmark_app = typer.Typer(help="Cross-dataset consistency benchmark")
app.add_typer(plugins_app, name="plugins")
app.add_typer(benchmark_app, name="benchmark")


class OutputFormat(str, Enum):  # noqa: UP042
    text = "text"
    json = "json"


class FailOn(str, Enum):  # noqa: UP042
    error = "error"
    warning = "warning"


def _severity_at_or_above(finding_sev: str, threshold: FailOn) -> bool:
    order = {"pass": 0, "warning": 1, "error": 2}
    return order.get(finding_sev, 0) >= order[threshold.value]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


def _handle_cli_error(exc: Exception) -> None:
    if isinstance(exc, httpx.TimeoutException):
        typer.echo("Request timed out", err=True)
    elif isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            typer.echo("Rate limited by remote server (HTTP 429)", err=True)
        elif status == 404:
            typer.echo("Remote resource not found (HTTP 404)", err=True)
        else:
            typer.echo(f"HTTP request failed with status {status}", err=True)
    elif isinstance(exc, httpx.HTTPError):
        typer.echo(f"Network error: {exc}", err=True)
    elif isinstance(exc, json.JSONDecodeError):
        typer.echo("Invalid JSON response from remote server", err=True)
    elif isinstance(exc, yaml.YAMLError):
        typer.echo(f"Invalid YAML: {exc}", err=True)
    elif isinstance(exc, ValueError):
        typer.echo(str(exc), err=True)
    else:
        raise exc
    raise typer.Exit(code=1)


@app.callback()
def main_callback(
    show_version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print package version and exit.",
    ),
) -> None:
    """OpenData Sentinel: civic open-data quality assurance."""


@app.command()
def version() -> None:
    """Print package version."""
    typer.echo(__version__)


@app.command()
def inspect(
    source: str = typer.Argument(..., help="File path or API URL"),
    layer: str | None = typer.Option(None, "--layer", help="GeoPackage layer name"),
) -> None:
    """Inspect schema, row count, and inferred types."""
    dataset = None
    try:
        if not source.startswith("http") and Path(source).suffix.lower() == ".gpkg" and layer is None:
            layers = list_gpkg_layers(Path(source))
            if len(layers) > 1:
                typer.echo(f"Multiple layers found; specify --layer. Available: {', '.join(layers)}", err=True)
                raise typer.Exit(code=1)
        dataset = load_dataset(source, layer=layer)
    except (ValueError, FileNotFoundError, ImportError, httpx.HTTPError, json.JSONDecodeError) as exc:
        _handle_cli_error(exc)

    if dataset is None:
        raise typer.Exit(code=1)
    typer.echo(f"Dataset: {dataset.id}")
    typer.echo(f"Rows: {len(dataset.frame)}")
    typer.echo(f"Source: {dataset.source_uri}")
    if dataset.crs:
        typer.echo(f"CRS: {dataset.crs}")
    typer.echo("Fields:")
    for field in dataset.fields:
        typer.echo(f"  - {field.name}: {field.dtype}")


@app.command()
def check(
    source: str = typer.Argument(..., help="File path or API URL"),
    config: Path = typer.Option(..., "--config", exists=True, readable=True),
    layer: str | None = typer.Option(None, "--layer"),
    output: Path | None = typer.Option(None, "--output", "-o"),
    format: OutputFormat = typer.Option(OutputFormat.text, "--format", "-f"),
    fail_on: FailOn = typer.Option(FailOn.error, "--fail-on"),
) -> None:
    """Run configured quality checks."""
    result = None
    try:
        ruleset = load_ruleset(config)
        dataset = load_dataset(source, layer=layer)
        result = run_checks(dataset, ruleset)
    except (ValueError, httpx.HTTPError, json.JSONDecodeError, yaml.YAMLError) as exc:
        _handle_cli_error(exc)

    if result is None:
        raise typer.Exit(code=1)
    payload = result.to_dict()
    if output:
        write_json_results(result, output)
    if format == OutputFormat.json:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(
            f"Completed checks for {result.dataset_id}: "
            f"{result.summary.error} errors, {result.summary.warning} warnings, "
            f"{result.summary.pass_count} passes"
        )

    if any(_severity_at_or_above(f["severity"], fail_on) for f in payload["findings"]):
        raise typer.Exit(code=1)


@app.command(name="report")
def report_cmd(
    results_path: Path = typer.Argument(..., exists=True, readable=True),
    output: Path = typer.Option(..., "--output", "-o"),
    locale: str = typer.Option("en", "--locale"),
) -> None:
    """Generate static HTML report from JSON results."""
    data = load_json_results(results_path)
    write_html_report(data, output, locale=locale)
    typer.echo(f"Wrote HTML report to {output}")


@app.command()
def backlog(
    results_path: Path = typer.Argument(..., exists=True, readable=True),
    output: Path = typer.Option(..., "--output", "-o"),
    format: OutputFormat = typer.Option(OutputFormat.text, "--format", "-f"),
) -> None:
    """Export prioritized correction backlog."""
    data = load_json_results(results_path)
    if output.suffix.lower() == ".json":
        write_backlog_json(data, output)
    else:
        write_backlog_csv(data, output)
    typer.echo(f"Wrote backlog to {output}")


@plugins_app.command("list")
def plugins_list() -> None:
    """List registered check plugins."""
    for name in list_plugin_names():
        typer.echo(name)


@benchmark_app.command("info")
def benchmark_info(
    manifest: Path = typer.Option(
        Path("benchmark/manifest.yml"),
        "--manifest",
        exists=False,
        readable=True,
    ),
) -> None:
    """Show benchmark manifest summary."""
    m = load_manifest(manifest)
    typer.echo(f"Benchmark version: {m.version}")
    typer.echo(f"Portal: {m.portal.name} ({m.portal.licence})")
    typer.echo(f"Datasets: {len(m.datasets)}")
    for ds in m.datasets:
        typer.echo(f"  - {ds.id} ({ds.expected_records} expected records)")
    typer.echo(f"Relations: {len(m.relations)}")
    typer.echo(f"Schema profiles: {len(m.schema_profiles)}")


@benchmark_app.command("snapshots")
def benchmark_snapshots(
    manifest: Path = typer.Option(Path("benchmark/manifest.yml"), "--manifest", exists=True),
    output: Path = typer.Option(Path("data/snapshots"), "--output", "-o"),
) -> None:
    """Download hashed dataset snapshots from the portal."""
    m = load_manifest(manifest)
    download_snapshots(m.portal.base_url, [ds.id for ds in m.datasets], output)
    typer.echo(f"Wrote snapshots to {output}")


@benchmark_app.command("run")
def benchmark_run(
    manifest: Path = typer.Option(
        Path("benchmark/manifest.yml"),
        "--manifest",
        exists=False,
        readable=True,
    ),
    adjudications: Path | None = typer.Option(
        Path("benchmark/adjudications/held_out.jsonl"),
        "--adjudications",
    ),
    output: Path = typer.Option(Path("benchmark/results"), "--output", "-o"),
    snapshots_dir: Path = typer.Option(Path("data/snapshots"), "--snapshots-dir"),
    live_fetch: bool = typer.Option(False, "--live-fetch"),
    schema_only: bool = typer.Option(False, "--schema-only"),
    relations_only: bool = typer.Option(False, "--relations-only"),
    fast: bool = typer.Option(False, "--fast", help="Skip timing/memory measurement repeats"),
) -> None:
    """Run the cross-dataset consistency benchmark."""
    adj_path = adjudications if adjudications and adjudications.exists() else None
    result = None
    try:
        result = run_benchmark(
            manifest,
            adjudication_path=adj_path,
            output_dir=output,
            skip_schema=relations_only,
            skip_relations=schema_only,
            snapshot_dir=snapshots_dir,
            live_fetch=live_fetch,
            measure_perf=not fast,
        )
    except (ValueError, FileNotFoundError, ImportError, httpx.HTTPError, json.JSONDecodeError) as exc:
        _handle_cli_error(exc)

    if result is None:
        raise typer.Exit(code=1)
    typer.echo(
        f"Benchmark complete: {len(result.findings)} findings "
        f"({result.runtime_seconds:.1f}s, peak memory {result.peak_memory_mb or 'n/a'} MB)"
    )
    if result.evaluation:
        ev = result.evaluation
        if ev.precision:
            typer.echo(
                f"Provisional report label agreement: {ev.precision.point:.3f} "
                f"[{ev.precision.ci_low:.3f}, {ev.precision.ci_high:.3f}]"
            )
        if ev.recall:
            typer.echo(
                f"Recall: {ev.recall.point:.3f} "
                f"[{ev.recall.ci_low:.3f}, {ev.recall.ci_high:.3f}]"
            )
        if ev.actionable_yield.n:
            typer.echo(
                f"Human-labelled actionable yield: {ev.actionable_yield.point:.3f} "
                f"[{ev.actionable_yield.ci_low:.3f}, {ev.actionable_yield.ci_high:.3f}]"
            )
        else:
            typer.echo("Actionable yield: unverified (no separate human/domain judgements)")
    if result.injected_evaluation:
        inj = result.injected_evaluation
        typer.echo(
            f"Evidence-confirmed injected recall: {inj['recall']['point']:.3f} "
            f"[{inj['recall']['ci_low']:.3f}, {inj['recall']['ci_high']:.3f}]"
        )
    typer.echo(f"Wrote results to {output}")


if __name__ == "__main__":
    app()
