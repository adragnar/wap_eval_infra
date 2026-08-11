"""Load question CSVs as inspect datasets.

Contract: the CSV must have a `prompt` column (the user message) and an `id`
column. Every other column, present or future, passes through verbatim into
Sample.metadata — analysis and rubrics can rely on arbitrary metadata columns
without code changes here.
"""

from __future__ import annotations

from inspect_ai.dataset import Dataset, Sample, csv_dataset

RESERVED_COLUMNS = ("prompt", "id")


class DatasetError(ValueError):
    """The CSV does not satisfy the dataset contract."""


def record_to_sample(record: dict) -> Sample:
    missing = [c for c in RESERVED_COLUMNS if c not in record]
    if missing:
        raise DatasetError(
            f"dataset row missing required column(s) {missing}; "
            f"CSV must have 'prompt' and 'id' columns (row: {record!r})"
        )
    return Sample(
        input=record["prompt"],
        id=record["id"],
        metadata={k: v for k, v in record.items() if k not in RESERVED_COLUMNS},
    )


def load_dataset(path: str) -> Dataset:
    return csv_dataset(path, sample_fields=record_to_sample)
