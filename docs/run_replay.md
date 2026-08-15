# How to Replay Pre-Generated Responses

Judge responses that were collected by hand — pasted from a chat UI, produced by a
provider with no inspect integration, or written by a person — instead of generating them.
The result is an ordinary batch dir under `logs/<N>_<name>/`, so everything downstream
(`inspect view`, the judge panel, `docs/run_rescoring.md`) works with no changes.

No model under test is ever called. Only the judges cost anything.

## 1. Build the replay CSV

Same contract as a question CSV — a `prompt` column and an `id` column — plus one column
holding the response, `model_response` by default. Put it in `datasets/`.

```csv
id,prompt,model_response,taxon,framing
q1,Are lobsters sentient?,"Evidence suggests lobsters can feel pain...",crustacean,direct
```

**Carry the question set's metadata columns through.** Rubrics render with
`StrictUndefined`, so a judge template referencing `{{ metadata.taxon }}` fails at scoring
time on a CSV that only has `[id, prompt, model_response]`. The easiest path is to start
from the original question CSV and add a response column to it.

Every row needs a non-empty response; blank cells are rejected at load rather than judged
as an empty answer.

## 2. Create the experiment config

```bash
cp experiments/replay_config.sh my_replay.sh
```

Edit the parameter block:

```bash
dataset="datasets/my_responses.csv"     # the CSV from step 1
response_column="model_response"        # column holding the pre-generated response
model_label="none/gpt-5-handwritten"    # recorded as the log's model; never called
judges="judges/judges.yaml"             # judge panel
judge_model="anthropic/claude-sonnet-4-5"
system_prompt=""                        # set a filepath if responses were collected under one
```

`model_label` should stay on inspect's `none/` provider. It needs no API key and raises if
anything tries to generate, so a replay run can never quietly become a real API call — the
label after the slash is yours to name (`none/gpt-5-handwritten`, `none/human-baseline`).

There is no `models`, `epochs`, or `temperature` here: nothing is generated, and `epochs`
would just duplicate identical rows.

See `docs/evaluation_parameters.md` for the full parameter reference.

## 3. Smoke test

```bash
./my_replay.sh test
```

Runs ~2 rows into `logs/test/` with no experiment bookkeeping — catches CSV, template, and
parsing errors for pennies. Inspect the output:

```bash
uv run inspect view --log-dir logs/test
```

Each sample should show your CSV text as the assistant turn, and the model as
`none/<label>`.

## 4. Real run

```bash
./my_replay.sh <experiment_name>
```

Creates the next numbered batch dir `logs/<N>_<experiment_name>/`, snapshots the config
script, git state, replay CSV, and judge panel into it, then judges every response — one
`.eval` log. Its `experiment.json` records `"kind": "replay"`, which is how a replayed run
stays distinguishable from a generated one forever after.

## 5. View results

```bash
uv run inspect view --log-dir logs/<N>_<experiment_name>
```

Batch dirs are immutable: never edit a `logs/<N>_*/` dir after it is written.

## 6. Iterate on rubrics

Replay batches are valid sources for a scoring workspace, so `docs/run_rescoring.md`
applies verbatim:

```bash
uv run python -m wap_eval.scoring init logs/<N>_<experiment_name>
```

## Notes

- One CSV carries one model's responses. To compare several hand-collected models, make
  one CSV each and run the config once per CSV — or point copies of the config at
  different `response_column`s of the same CSV.
- The response column never lands in sample metadata, so rubrics see exactly the metadata
  shape a generated run produces.
