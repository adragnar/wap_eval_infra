"""Load question CSVs as inspect datasets.

Contract: the CSV must have a `prompt` column (the user message) and an `id`
column. Every other column, present or future, passes through verbatim into
Sample.metadata — analysis and rubrics can rely on arbitrary metadata columns
without code changes here.

Replay CSVs (see docs/run_replay.md) add one more required column holding a
pre-generated response. It is stripped before the contract above is applied, so
replay samples carry exactly the metadata a generation run would produce; the
response rides along under REPLAY_RESPONSE_KEY until the replay solver pops it.
"""

from __future__ import annotations

from inspect_ai.dataset import Dataset, Sample, csv_dataset

RESERVED_COLUMNS = ("prompt", "id")

DEFAULT_RESPONSE_COLUMN = "model_response"

# Private hand-off from load_replay_dataset to wap_eval.solvers.replay_response.
# Dunder-ish so it cannot collide with a real CSV column name.
REPLAY_RESPONSE_KEY = "__wap_replay_response__"


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


def record_to_replay_sample(record: dict, response_column: str) -> Sample:
    if response_column not in record:
        raise DatasetError(
            f"replay row missing required column '{response_column}'; a replay CSV "
            f"must have 'prompt', 'id', and the response column (row: {record!r})"
        )
    response = record[response_column]
    if not response or not response.strip():
        raise DatasetError(
            f"replay row has an empty '{response_column}'; every question must carry "
            f"a response (row: {record!r})"
        )
    sample = record_to_sample({k: v for k, v in record.items() if k != response_column})
    sample.metadata[REPLAY_RESPONSE_KEY] = response
    return sample


def load_replay_dataset(
    path: str, response_column: str = DEFAULT_RESPONSE_COLUMN
) -> Dataset:
    return csv_dataset(
        path, sample_fields=lambda record: record_to_replay_sample(record, response_column)
    )
