# How to Run an Eval

Run a question set against a list of models, with every judge scoring every response.

## 1. Add the dataset

Copy the question CSV into `datasets/`. It must have a `prompt` column (the user message)
and an `id` column. Every other column is carried through to the logs as metadata.

## 2. Create the experiment config

```bash
cp experiments/test_config.sh my_experiment.sh
```

Edit the parameter block in `my_experiment.sh`:

```bash
models=("anthropic/claude-sonnet-4-5" "openai/gpt-5")   # models under test
dataset="datasets/my_questions.csv"
judges="judges/judges.yaml"                             # judge panel
judge_model="anthropic/claude-sonnet-4-5"               # default judge model
epochs=1                                                # responses per question
temperature=""                                          # empty = provider default
system_prompt=""                                        # empty = no system prompt
```

See `docs/evaluation_parameters.md` for the full parameter reference.

## 3. Smoke test

```bash
./my_experiment.sh test
```

Runs ~2 questions into `logs/test/` with no experiment bookkeeping — catches config,
template, and parsing errors for pennies. Inspect the output:

```bash
inspect view --log-dir logs/test
```

## 4. Real run

```bash
./my_experiment.sh <experiment_name>
```

Creates the next numbered batch dir `logs/<N>_<experiment_name>/`, snapshots the config
script, git state, dataset, and judge panel into it (plus `experiment.json`), then runs
each model — one `.eval` log file per model.

## 5. View results

```bash
inspect view --log-dir logs/<N>_<experiment_name>
```

Batch dirs are immutable: never edit a `logs/<N>_*/` dir after it is written.
