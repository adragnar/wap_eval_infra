"""The WAP eval tasks: a single-turn response scored by the judge panel.

`wap_eval` generates the response. `wap_replay` imports it from a CSV column
instead — same dataset contract, same judge panel, no model call.

Run via the experiment config scripts (docs/run_eval.md, docs/run_replay.md):

    inspect eval src/wap_eval/task.py@wap_eval --model <m> \
        -T dataset=... -T judges=... -T judge_model=... [-T system_prompt=...]

    inspect eval src/wap_eval/task.py@wap_replay --model none/<label> \
        -T dataset=... -T judges=... -T judge_model=... [-T response_column=...]
"""

from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import generate, system_message

from wap_eval.dataset import DEFAULT_RESPONSE_COLUMN, load_dataset, load_replay_dataset
from wap_eval.judges import build_scorers, load_panel
from wap_eval.solvers import replay_response


@task
def wap_eval(
    dataset: str,
    judges: str = "judges/judges.yaml",
    judge_model: str = "",
    system_prompt: str = "",
) -> Task:
    panel = load_panel(judges)
    scorers = build_scorers(panel, default_model=judge_model or None)
    solver = []
    if system_prompt:
        solver.append(system_message(Path(system_prompt).read_text()))
    solver.append(generate())
    return Task(
        dataset=load_dataset(dataset),
        solver=solver,
        scorer=scorers,
    )


@task
def wap_replay(
    dataset: str,
    judges: str = "judges/judges.yaml",
    judge_model: str = "",
    response_column: str = DEFAULT_RESPONSE_COLUMN,
    system_prompt: str = "",
) -> Task:
    """Judge pre-generated responses (see docs/run_replay.md).

    Use with --model none/<label>: inspect's no-model sentinel needs no API key
    and raises if anything tries to generate, so a replay run can never quietly
    become a real API call. `system_prompt` is recorded for fidelity when the
    responses were collected under one — it is not sent anywhere.
    """
    panel = load_panel(judges)
    scorers = build_scorers(panel, default_model=judge_model or None)
    solver = []
    if system_prompt:
        solver.append(system_message(Path(system_prompt).read_text()))
    solver.append(replay_response())
    return Task(
        dataset=load_replay_dataset(dataset, response_column),
        solver=solver,
        scorer=scorers,
    )
