# CLAUDE.md

Evaluation harness for the Welfare Alignment Project (WAP): question CSVs are run
against LLMs via inspect-ai, a panel of LLM judges scores each response on separate
aspects, and the team iterates on both questions and judge rubrics. `repo_desirata.md`
has the project goals; `docs/project_architecture.md` has the full structure.

## Commands

```bash
uv run pytest                                  # test suite (mockllm — no API keys/cost)
./<config>.sh test                             # smoke-run an experiment config (logs/test/, ~2 samples)
./<config>.sh <name>                           # real run -> immutable logs/<N>_<name>/
uv run python -m wap_eval.scoring init|run|drop  # rubric iteration in scoring/ workspaces
uv run inspect view --log-dir <batch_dir>      # browse results
```

Experiment configs are copies of `experiments/test_config.sh` (generation) or
`experiments/replay_config.sh` (pre-generated responses) living in the repo root
(e.g. `openai_live.sh`); all run parameters are documented in
`docs/evaluation_parameters.md`. The three core workflows are step-by-step guides:
`docs/run_eval.md` (run an eval), `docs/run_replay.md` (judge responses generated
elsewhere) and `docs/run_rescoring.md` (iterate on judges).

## Hard rules

- **Never modify anything under `logs/<N>_*/`** — generation runs are immutable records.
  Rubric iteration happens only in `scoring/` workspaces, only via `wap_eval.scoring`.
- **Tests first** (`docs/testing_workflow.md`): write pytest tests before changing
  `src/`, keep `uv run pytest` green. Use `mockllm/model` in tests — never real APIs.
- **Never break the dataset contract**: CSVs have `prompt` + `id`; every other column
  must keep passing through to `Sample.metadata` untouched (arbitrary future columns).
  Replay CSVs add a response column, stripped before the contract applies so replay
  samples carry exactly the metadata a generation run would.
- **Scale registry is closed and validated**: judge scales are `{type: binary}` or
  `{type: numeric, min, max}`, checked at load (`src/wap_eval/scales.py`). New scale
  types get a registry branch + tests, never ad-hoc parsing.
- **Judging failures are never silent scores**: unparseable judge output becomes
  `Score.unscored()` (NaN + `metadata.scoring_error`) — natively excluded from metrics
  and epoch reducers. Don't "fix" this by defaulting to 0/INCORRECT.

## Conventions

- A judge = one entry in `judges/judges.yaml` (name, template, scale, optional model
  override) + one pure-prose `.jinja2` rubric in `judges/`. Rubrics end with a
  `GRADE: <x>` tail; templates may use `{{ question }}` (alias `{{ prompt }}`),
  `{{ response }}`, and `{{ metadata.<col> }}`. Adding a judge requires no Python.
- Binary grades map yes→`CORRECT`, no→`INCORRECT` — phrase binary rubrics so "yes"
  is the desirable outcome.
- Every batch dir gets an `experiment.json` provenance manifest; workspaces also
  track judge versions in `scorer_versions.json` (versioned names are never reused,
  including dropped ones).

## Gotchas (learned the hard way)

- `inspect eval` chdirs to the task file's directory — file params must be passed as
  absolute paths (`test_config.sh` does this via its `abspath` helper).
- `inspect eval` auto-loads `.env`, but the `score()` API does not — `wap_eval.scoring`
  calls `load_dotenv()` itself. New entry points that call inspect APIs must too.
- Inspect coerces score values to float and epoch-reduces them *before* metrics run —
  custom metrics cannot see raw string/sentinel values, and unscored (NaN) samples are
  filtered out before metrics entirely (an aggregate error-rate metric is impossible;
  `scoring run` prints unparseable counts instead).
- The judge scorer factory registers scorers by dynamic name (`scorer(name=...)`) —
  that's how versioned columns (`<judge>_v2`) work; don't refactor it away.
