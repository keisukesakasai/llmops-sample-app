"""Dataset loading and Datadog Dataset registration helpers.

Usage:
    from experiments.datasets import load_budget_guru_dataset
    records = load_budget_guru_dataset("datasets/budget_guru_investment_qa.csv")
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DatasetRecord:
    """A single row from the Budget Guru evaluation dataset."""

    id: str
    input: str
    expected_output: str
    topic: str
    difficulty: str
    age_group: str


def load_budget_guru_dataset(path: str) -> list[DatasetRecord]:
    """Load the Budget Guru Q&A CSV into a list of DatasetRecord objects.

    Args:
        path: Path to the CSV file (relative or absolute).

    Returns:
        List of DatasetRecord instances, one per CSV row.

    Raises:
        FileNotFoundError: If the CSV does not exist at ``path``.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path.resolve()}")

    records: list[DatasetRecord] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            records.append(
                DatasetRecord(
                    id=row["id"],
                    input=row["input"],
                    expected_output=row["expected_output"],
                    topic=row["topic"],
                    difficulty=row["difficulty"],
                    age_group=row["age_group"],
                )
            )

    logger.info("Loaded %d records from %s", len(records), csv_path)
    return records


# ---------------------------------------------------------------------------
# Datadog Dataset registration helpers
# ---------------------------------------------------------------------------


def create_or_get_dataset_in_datadog(
    records: list[DatasetRecord],
    dataset_name: str = "budget-guru-investment-qa",
) -> str:
    """Register (or retrieve) a Dataset in Datadog LLM Experiments.

    This function is a *stub*.  Fill in the body once the Datadog
    LLM Experiments Python SDK is available in your environment.

    Expected Datadog API interaction:
        POST /api/v2/llm-obs/datasets
        Body: { "data": { "type": "datasets", "attributes": { "name": ...,
               "records": [ { "input": ..., "expected_output": ... }, ... ] } } }

    Reference: https://docs.datadoghq.com/llm_observability/experiments/

    Args:
        records: Dataset rows to upload.
        dataset_name: Human-readable name shown in the Datadog UI.

    Returns:
        The Datadog-assigned dataset ID (UUID string).
    """
    # [Datadog LLM Experiments SDK] Replace this stub with the real SDK call:
    #   from ddtrace.llmobs.experiments import Dataset
    #   ds = Dataset.get_or_create(name=dataset_name, records=[...])
    #   return ds.id
    logger.warning(
        "create_or_get_dataset_in_datadog is a stub. "
        "Returning dummy dataset_id. records=%d",
        len(records),
    )
    return "dummy-dataset-id-00000000"
