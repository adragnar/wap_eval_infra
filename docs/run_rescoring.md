# How to Iterate on Scorers (Re-scoring)

Revise judge rubrics and re-score an existing run's responses — without re-running any
model under test. Iteration happens in a *scoring workspace*: a mutable copy of the run's
logs under `scoring/`. The original run under `logs/` is never touched.

## 1. (Optional) branch

```bash
git checkout -b scorer-iteration
```

Pure convention — the tooling doesn't require it.

## 2. Create a workspace

```bash
uv run python -m wap_eval.scoring init logs/1_realrun
```

Creates `scoring/1_iter_realrun/` containing copies of the run's `.eval` logs (responses +
original scores), an `experiment.json` (`kind: scoring_workspace, source: 1_realrun`), and
an empty `scorer_versions.json`.

## 3. Edit rubric(s)

Edit the template(s) in `judges/`, e.g. `judges/cruelty.jinja2`.
No yaml changes or commits needed while iterating.

## 4. Re-score the judges you changed

```bash
uv run python -m wap_eval.scoring run scoring/1_iter_realrun \
    --judges harm_refusal,cruelty
```

- `--judges` takes one judge, a comma-separated subset, or omit it to re-run the whole panel.
- Each judge's new scores are appended under an auto-versioned name (`cruelty_v2`,
  `_v3`, ...); version counters are independent per judge.
- Only judge models are called — cheap and fast.
- Each version is recorded in `scorer_versions.json` (versioned name, judge, git commit,
  judge model, timestamp).

## 5. Compare, sample by sample

```bash
inspect view --log-dir scoring/1_iter_realrun
```

Every sample shows all versions side by side on the same responses, each with its own
aggregate metrics.

## 6. Loop

Repeat steps 3–4 until a rubric behaves the way you want.

## 7. Drop failed attempts

```bash
uv run python -m wap_eval.scoring drop scoring/1_iter_realrun cruelty_v3
```

Removes that version's scores and metrics from the workspace logs. Its
`scorer_versions.json` entry is kept, marked `dropped: true`. If a workspace gets into a
bad state, delete it and `init` a fresh one — the source run is pristine.

## 8. Converge and commit the milestone

The winning rubric is already the current text in `judges/` — commit it. Future runs and
re-scores pick it up automatically. Keep or delete the workspace as you like.
