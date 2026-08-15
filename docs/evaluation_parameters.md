# Evaluation Parameters

Every evaluation run is fully described by the parameters below. They are all set in the
experiment config script (a renamed copy of `experiments/test_config.sh` living in the repo
root), and are snapshotted into the run's batch dir (`logs/<N>_<name>/`) via the frozen script
copy and `experiment.json`, so any run can be reproduced from its batch dir alone.

## Run-level parameters (the config script's parameter block)


| Parameter       | Type / format                                                                          | Default                                                          | What it does                                                                                                                                                                                                           |
| --------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `expname`       | string (positional arg to the script)                                                  | — (required)                                                     | Names the run; becomes the batch dir suffix (`logs/<N>_<expname>`). The special value `test` skips reproducibility/logging and writes to `logs/test/` with a small sample limit.                                       |
| `models`        | bash array of inspect model IDs, e.g. `("anthropic/claude-sonnet-4-5" "openai/gpt-5")` | — (required)                                                     | The models under test. The script loops over this array, one `inspect eval` (and one `.eval` log file) per model.                                                                                                      |
| `dataset`       | filepath to CSV                                                                        | — (required)                                                     | The question dataset. Required columns: `prompt` (becomes the input), `id` (sample id). **All other columns** (e.g. `genre`) pass through to sample metadata untouched — arbitrary future columns need no code change. |
| `judges`        | filepath to a judges yaml                                                              | `judges/judges.yaml`                                             | The judge panel manifest (see below). Validated at startup; unknown scale types fail before any model call.                                                                                                            |
| `judge_model`   | inspect model ID                                                                       | — (required)                                                     | The default model used by all judges. Individual judges may override it in the yaml.                                                                                                                                   |
| `epochs`        | int ≥ 1                                                                                | `1`                                                              | Responses generated (and judged) per question. Raise to measure response variance on a question set.                                                                                                                   |
| `temperature`   | float, or empty string                                                                 | `""` (empty)                                                     | Sampling temperature for the models under test. Empty = each provider's own default (measures what real users get).                                                                                                    |
| `system_prompt` | filepath, or empty string                                                              | `""` (empty)                                                     | System prompt for the models under test. Empty = no system prompt. When set, the file's text is used verbatim and a copy is snapshotted into the batch dir.                                                            |
| `limit`         | int, or empty                                                                          | empty (all questions); test mode forces a small value (e.g. `2`) | Caps how many dataset rows run. Mainly for cheap smoke tests.                                                                                                                                                          |
| `log_dir`       | dirpath                                                                                | `./logs`                                                         | Base directory for numbered batch dirs. Rarely changed.                                                                                                                                                                |




## Replay parameters (`experiments/replay_config.sh`)

A replay run judges responses that were generated outside this harness (see
`docs/run_replay.md`). It uses the same config-script shape, dropping the parameters that
only make sense when generating — `models`, `epochs`, `temperature` — and adding the three
below. `dataset`, `judges`, `judge_model`, `system_prompt`, `limit`, `expname`, and
`log_dir` behave exactly as above.

| Parameter         | Type / format                   | Default            | What it does                                                                                                                                                                                                 |
| ----------------- | ------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `dataset`         | filepath to CSV                 | — (required)       | The replay CSV. Required columns: `prompt`, `id`, **and the response column**. All other columns pass through to metadata as usual; the response column does not. Empty responses are rejected at load.       |
| `response_column` | string                          | `model_response`   | Which column holds the pre-generated response. It becomes the assistant turn — everything downstream reads it exactly as it would a generated one.                                                            |
| `model_label`     | inspect model ID, `none/<label>` | — (required)       | Recorded as the log's model. Keep it on the `none/` provider: it needs no API key and raises if anything tries to generate, so a replay run can never quietly become a real API call. The label is yours to name. |

`system_prompt` here is recorded for fidelity (when the responses were collected under
one) and is not sent anywhere. `experiment.json` gets `"kind": "replay"` plus
`params.response_column`; such runs are valid sources for a scoring workspace.

## Re-scoring parameters (`python -m wap_eval.scoring`)

Re-scoring applies revised judge rubrics to the responses of an existing run, without
re-generating anything. It happens in a *scoring workspace* under `scoring/` — a copy of
the run's logs mutated only by this tool. Source runs are never modified. See
`docs/run_rescoring.md` for the workflow.

### `init <source_dir>` — create a workspace

| Parameter    | Type                                        | Default          | What it does                                                     |
| ------------ | ------------------------------------------- | ---------------- | ---------------------------------------------------------------- |
| `source_dir` | existing run dir (e.g. `logs/1_realrun`)    | — (required)     | The run whose logs are copied; recorded as `source` provenance.  |
| `--name`     | string                                      | `iter_<source>`  | Workspace name; becomes `scoring/<N>_<name>`.                    |

### `run <workspace>` — append re-scored judges as versioned columns

| Parameter       | Type                        | Default              | What it does                                                              |
| --------------- | --------------------------- | -------------------- | ------------------------------------------------------------------------- |
| `workspace`     | workspace dir               | — (required)         | e.g. `scoring/1_iter_realrun`.                                            |
| `--judges`      | comma-separated judge names | whole panel          | Which judges to re-score, e.g. `harm_refusal,welfare_consideration`.      |
| `--judges-yaml` | filepath                    | `judges/judges.yaml` | The panel manifest to build judges from.                                  |
| `--judge-model` | inspect model ID            | — (required*)        | Default judge model. *Optional if every selected judge has a yaml `model:` override. |

Each run appends scores under auto-versioned names (`<judge>_v2`, `_v3`, ...) and records
them in the workspace's `scorer_versions.json` (versioned name, judge, git commit, judge
model, timestamp). Versioned names are never reused, including dropped ones.

### `drop <workspace> <scorer_name>` — remove a scorer column

| Parameter     | Type                 | Default      | What it does                                                                 |
| ------------- | -------------------- | ------------ | ---------------------------------------------------------------------------- |
| `scorer_name` | versioned scorer name | — (required) | Removes that column's scores and metrics from the workspace logs; its `scorer_versions.json` entry is kept, marked `dropped: true`. |


