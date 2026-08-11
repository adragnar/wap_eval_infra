"""The WAP eval task: single-turn generation scored by the judge panel.

Run via the experiment config script (see docs/run_eval.md), which invokes:

    inspect eval src/wap_eval/task.py@wap_eval --model <m> \
        -T dataset=... -T judges=... -T judge_model=... [-T system_prompt=...]
"""

from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import generate, system_message

from wap_eval.dataset import load_dataset
from wap_eval.judges import build_scorers, load_panel


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
