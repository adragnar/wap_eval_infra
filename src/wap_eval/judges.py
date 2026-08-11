"""Judge panel: manifest loading and scorer factory.

A judge = one rubric template (pure prose, jinja2) + one entry in the panel
manifest (judges.yaml) declaring its name, template, scale, and optionally a
model override. The factory turns each entry into an ordinary inspect scorer
that renders the rubric, calls the judge model, and parses the structured
'GRADE: <x>' tail per the declared scale.

Judging failures (out-of-contract output) are recorded via Score.unscored():
the judge's raw output and the failure reason (metadata["scoring_error"])
are preserved per-sample, while the NaN value is natively excluded from all
metrics and epoch reducers — failures never pollute means, and never become
silent in-range scores. Failure counts are surfaced by the scoring CLI and
by inspecting samples with NaN scores in the log viewer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined
from inspect_ai.model import Model, get_model
from inspect_ai.scorer import (
    Score,
    Scorer,
    Target,
    mean,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState

from wap_eval.scales import GradeParseError, Scale, parse_grade, parse_scale

REQUIRED_KEYS = {"name", "template", "scale"}
OPTIONAL_KEYS = {"model"}


class JudgesConfigError(ValueError):
    """The judges yaml is malformed."""


@dataclass(frozen=True)
class JudgeSpec:
    name: str
    template: Path
    scale: Scale
    model: str | None = None


def load_panel(path: str | Path) -> list[JudgeSpec]:
    """Load and validate a judges.yaml. Raises JudgesConfigError / ScaleError."""
    yaml_path = Path(path)
    if not yaml_path.exists():
        raise JudgesConfigError(f"judges yaml not found: {yaml_path}")
    data = yaml.safe_load(yaml_path.read_text())
    if not isinstance(data, dict) or not isinstance(data.get("judges"), list):
        raise JudgesConfigError(
            f"{yaml_path}: top level must be a mapping with a 'judges' list"
        )
    if not data["judges"]:
        raise JudgesConfigError(f"{yaml_path}: 'judges' list is empty")

    specs: list[JudgeSpec] = []
    seen: set[str] = set()
    for i, entry in enumerate(data["judges"]):
        where = f"{yaml_path}: judges[{i}]"
        if not isinstance(entry, dict):
            raise JudgesConfigError(f"{where}: each judge must be a mapping")
        missing = REQUIRED_KEYS - set(entry)
        if missing:
            raise JudgesConfigError(f"{where}: missing required key(s) {sorted(missing)}")
        unknown = set(entry) - REQUIRED_KEYS - OPTIONAL_KEYS
        if unknown:
            raise JudgesConfigError(f"{where}: unknown key(s) {sorted(unknown)}")
        name = entry["name"]
        if not isinstance(name, str) or not name:
            raise JudgesConfigError(f"{where}: 'name' must be a non-empty string")
        if name in seen:
            raise JudgesConfigError(f"{yaml_path}: duplicate judge name '{name}'")
        seen.add(name)
        template = yaml_path.parent / entry["template"]
        if not template.exists():
            raise JudgesConfigError(f"{where}: template not found: {template}")
        try:
            scale = parse_scale(entry["scale"])
        except ValueError as e:
            raise JudgesConfigError(f"{where}: invalid scale: {e}") from e
        model = entry.get("model")
        if model is not None and (not isinstance(model, str) or not model):
            raise JudgesConfigError(f"{where}: 'model' must be a non-empty string")
        specs.append(JudgeSpec(name=name, template=template, scale=scale, model=model))
    return specs


_jinja = Environment(undefined=StrictUndefined, keep_trailing_newline=True)


def render_prompt(template_text: str, question: str, response: str, metadata: dict | None) -> str:
    # `prompt` is an alias for `question` (it matches the CSV column name)
    return _jinja.from_string(template_text).render(
        question=question, prompt=question, response=response, metadata=metadata or {}
    )


def judge_scorer(
    spec: JudgeSpec,
    default_model: str | Model | None = None,
    register_as: str | None = None,
) -> Scorer:
    """Build one inspect scorer for a judge.

    register_as overrides the scorer's registered name (used by the scoring
    workspace tool to append versioned columns like '<judge>_v2').
    """
    model_ref = spec.model or default_model
    if not model_ref:
        raise JudgesConfigError(
            f"judge '{spec.name}' has no model: pass judge_model for the run "
            f"or set model: in the judges yaml"
        )
    template_text = spec.template.read_text()

    async def score_fn(state: TaskState, target: Target) -> Score:
        prompt = render_prompt(
            template_text, state.input_text, state.output.completion, state.metadata
        )
        model = get_model(model_ref)
        output = await model.generate(prompt)
        completion = output.completion
        base_meta = {"judge": spec.name, "judge_model": str(model)}
        try:
            value = parse_grade(completion, spec.scale)
        except GradeParseError as e:
            return Score.unscored(
                explanation=completion,
                metadata={**base_meta, "scoring_error": str(e)},
            )
        return Score(value=value, explanation=completion, metadata=base_meta)

    factory = scorer(metrics=[mean(), stderr()], name=register_as or spec.name)(
        lambda: score_fn
    )
    return factory()


def build_scorers(
    panel: list[JudgeSpec],
    default_model: str | Model | None = None,
    names: list[str] | None = None,
    rename: dict[str, str] | None = None,
) -> list[Scorer]:
    """Build scorers for the whole panel or a named subset.

    rename maps judge name -> registered scorer name (for versioned appends).
    """
    if names is not None:
        known = {s.name for s in panel}
        unknown = sorted(set(names) - known)
        if unknown:
            raise JudgesConfigError(
                f"unknown judge(s) {unknown}; panel has: {sorted(known)}"
            )
        panel = [s for s in panel if s.name in set(names)]
    rename = rename or {}
    return [
        judge_scorer(spec, default_model, register_as=rename.get(spec.name))
        for spec in panel
    ]
