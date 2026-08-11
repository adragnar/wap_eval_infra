"""End-to-end plumbing tests using mockllm (no API keys, no cost).

mockllm answers "default output" everywhere, so judge parsing fails by
design — which exercises exactly the path we care about: judges run,
failures are recorded as unscored (NaN, never silent garbage), metrics
compute. Successful parsing is covered by unit tests in test_scales.py.
"""

import json
import math

import pytest
from inspect_ai import eval as inspect_eval

from wap_eval import scoring
from wap_eval.task import wap_eval


@pytest.fixture(scope="module")
def module_assets(tmp_path_factory):
    """One shared mockllm eval run (module-scoped: eval is slowish)."""
    tmp = tmp_path_factory.mktemp("e2e")
    csv = tmp / "questions.csv"
    csv.write_text("id,prompt,genre\nq1,hello,edgy\nq2,hi there,factual\n")
    judges = tmp / "judges"
    judges.mkdir()
    (judges / "refusal.jinja2").write_text("Q {{ question }} R {{ response }}\n{{ footer }}\n")
    (judges / "quality.jinja2").write_text("G {{ metadata.genre }} R {{ response }}\n{{ footer }}\n")
    (judges / "judges.yaml").write_text(
        """
judges:
  - name: refusal
    template: refusal.jinja2
    scale: {type: binary}
  - name: quality
    template: quality.jinja2
    scale: {type: numeric, min: 1, max: 5}
"""
    )
    log_dir = tmp / "logs" / "1_realrun"
    logs = inspect_eval(
        wap_eval(
            dataset=str(csv),
            judges=str(judges / "judges.yaml"),
            judge_model="mockllm/model",
        ),
        model="mockllm/model",
        log_dir=str(log_dir),
    )
    return {"tmp": tmp, "judges_yaml": judges / "judges.yaml", "run_dir": log_dir, "logs": logs}


class TestEvalRun:
    def test_run_succeeds(self, module_assets):
        (log,) = module_assets["logs"]
        assert log.status == "success"

    def test_every_sample_scored_by_every_judge(self, module_assets):
        (log,) = module_assets["logs"]
        assert len(log.samples) == 2
        for sample in log.samples:
            assert set(sample.scores) == {"refusal", "quality"}

    def test_unparseable_judge_output_is_unscored_not_silent(self, module_assets):
        (log,) = module_assets["logs"]
        for sample in log.samples:
            for score in sample.scores.values():
                assert isinstance(score.value, float) and math.isnan(score.value)
                assert "scoring_error" in score.metadata

    def test_metadata_reaches_the_log(self, module_assets):
        (log,) = module_assets["logs"]
        genres = {s.id: s.metadata["genre"] for s in log.samples}
        assert genres == {"q1": "edgy", "q2": "factual"}

    def test_metrics_computed_per_judge(self, module_assets):
        (log,) = module_assets["logs"]
        names = {s.name for s in log.results.scores}
        assert names == {"refusal", "quality"}
        for s in log.results.scores:
            assert "mean" in s.metrics
            assert "stderr" in s.metrics
            # every sample is unscored (mockllm never parses) -> mean over none is NaN
            assert math.isnan(s.metrics["mean"].value)


@pytest.fixture(scope="module")
def workspace(module_assets):
    return scoring.cmd_init(
        str(module_assets["run_dir"]),
        name=None,
        scoring_root=str(module_assets["tmp"] / "scoring"),
    )


class TestScoringWorkspace:
    def test_init_copies_logs_and_writes_manifests(self, workspace, module_assets):
        assert workspace.name == "1_iter_realrun"
        assert len(list(workspace.glob("*.eval"))) == 1
        manifest = json.loads((workspace / "experiment.json").read_text())
        assert manifest["kind"] == "scoring_workspace"
        assert manifest["source"] == "1_realrun"
        assert json.loads((workspace / "scorer_versions.json").read_text()) == []

    def test_init_refuses_a_workspace_as_source(self, workspace, module_assets):
        with pytest.raises(scoring.ScoringError, match="generation runs"):
            scoring.cmd_init(
                str(workspace), name=None, scoring_root=str(module_assets["tmp"] / "scoring")
            )

    def test_run_refuses_non_workspace_dir(self, module_assets):
        with pytest.raises(scoring.ScoringError, match="not a scoring workspace"):
            scoring.cmd_run(
                str(module_assets["run_dir"]),
                judges_arg=None,
                judges_yaml=str(module_assets["judges_yaml"]),
                judge_model="mockllm/model",
            )

    def test_run_appends_versioned_columns(self, workspace, module_assets):
        added = scoring.cmd_run(
            str(workspace),
            judges_arg="refusal",
            judges_yaml=str(module_assets["judges_yaml"]),
            judge_model="mockllm/model",
        )
        assert added == ["refusal_v2"]
        from inspect_ai.log import read_eval_log

        (f,) = sorted(workspace.glob("*.eval"))
        log = read_eval_log(str(f))
        for sample in log.samples:
            assert set(sample.scores) == {"refusal", "quality", "refusal_v2"}
        versions = json.loads((workspace / "scorer_versions.json").read_text())
        assert versions[0]["name"] == "refusal_v2"
        assert versions[0]["judge"] == "refusal"
        assert versions[0]["judge_model"] == "mockllm/model"

    def test_source_run_untouched_by_workspace_ops(self, workspace, module_assets):
        from inspect_ai.log import read_eval_log

        (f,) = sorted(module_assets["run_dir"].glob("*.eval"))
        log = read_eval_log(str(f))
        for sample in log.samples:
            assert set(sample.scores) == {"refusal", "quality"}

    def test_drop_removes_column_and_marks_manifest(self, workspace, module_assets):
        scoring.cmd_drop(str(workspace), "refusal_v2")
        from inspect_ai.log import read_eval_log

        (f,) = sorted(workspace.glob("*.eval"))
        log = read_eval_log(str(f))
        for sample in log.samples:
            assert set(sample.scores) == {"refusal", "quality"}
        assert all(s.name != "refusal_v2" for s in log.results.scores)
        versions = json.loads((workspace / "scorer_versions.json").read_text())
        entry = next(v for v in versions if v["name"] == "refusal_v2")
        assert entry["dropped"] is True

    def test_dropped_version_number_never_reused(self, workspace, module_assets):
        added = scoring.cmd_run(
            str(workspace),
            judges_arg="refusal",
            judges_yaml=str(module_assets["judges_yaml"]),
            judge_model="mockllm/model",
        )
        assert added == ["refusal_v3"]  # v2 was dropped, its name stays retired

    def test_drop_unknown_scorer_errors(self, workspace):
        with pytest.raises(scoring.ScoringError, match="not found"):
            scoring.cmd_drop(str(workspace), "ghost_v9")
