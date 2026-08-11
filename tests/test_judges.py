import pytest
from jinja2.exceptions import UndefinedError

from wap_eval.judges import (
    JudgesConfigError,
    build_judge_prompt,
    build_scorers,
    load_panel,
    render_prompt,
)
from wap_eval.scales import BinaryScale, NumericScale


class TestLoadPanel:
    def test_valid_panel(self, judges_dir):
        panel = load_panel(judges_dir / "judges.yaml")
        assert [s.name for s in panel] == ["refusal", "quality"]
        assert panel[0].scale == BinaryScale()
        assert panel[1].scale == NumericScale(1, 5)

    def test_model_override_captured(self, judges_dir):
        panel = load_panel(judges_dir / "judges.yaml")
        assert panel[0].model is None
        assert panel[1].model == "mockllm/model"

    def test_missing_file(self, tmp_path):
        with pytest.raises(JudgesConfigError, match="not found"):
            load_panel(tmp_path / "nope.yaml")

    def test_invalid_scale_fails_at_load(self, judges_dir):
        bad = judges_dir / "bad.yaml"
        bad.write_text(
            "judges:\n  - name: j\n    template: refusal.jinja2\n    scale: {type: likert}\n"
        )
        with pytest.raises(JudgesConfigError, match="invalid scale"):
            load_panel(bad)

    def test_missing_required_key(self, judges_dir):
        bad = judges_dir / "bad.yaml"
        bad.write_text("judges:\n  - name: j\n    scale: {type: binary}\n")
        with pytest.raises(JudgesConfigError, match="template"):
            load_panel(bad)

    def test_unknown_key_rejected(self, judges_dir):
        bad = judges_dir / "bad.yaml"
        bad.write_text(
            "judges:\n  - name: j\n    template: refusal.jinja2\n"
            "    scale: {type: binary}\n    temperture: 0\n"
        )
        with pytest.raises(JudgesConfigError, match="unknown key"):
            load_panel(bad)

    def test_duplicate_names_rejected(self, judges_dir):
        bad = judges_dir / "bad.yaml"
        bad.write_text(
            "judges:\n"
            "  - {name: j, template: refusal.jinja2, scale: {type: binary}}\n"
            "  - {name: j, template: quality.jinja2, scale: {type: binary}}\n"
        )
        with pytest.raises(JudgesConfigError, match="duplicate"):
            load_panel(bad)

    def test_template_without_footer_placeholder_rejected(self, judges_dir):
        (judges_dir / "nofooter.jinja2").write_text("Q: {{ question }} R: {{ response }}\n")
        bad = judges_dir / "bad.yaml"
        bad.write_text(
            "judges:\n  - {name: j, template: nofooter.jinja2, scale: {type: binary}}\n"
        )
        with pytest.raises(JudgesConfigError, match="footer"):
            load_panel(bad)

    def test_missing_template_file_rejected(self, judges_dir):
        bad = judges_dir / "bad.yaml"
        bad.write_text(
            "judges:\n  - {name: j, template: ghost.jinja2, scale: {type: binary}}\n"
        )
        with pytest.raises(JudgesConfigError, match="template not found"):
            load_panel(bad)

    def test_empty_list_rejected(self, judges_dir):
        bad = judges_dir / "bad.yaml"
        bad.write_text("judges: []\n")
        with pytest.raises(JudgesConfigError, match="empty"):
            load_panel(bad)


class TestBuildScorers:
    def test_whole_panel(self, judges_dir):
        panel = load_panel(judges_dir / "judges.yaml")
        scorers = build_scorers(panel, default_model="mockllm/model")
        assert len(scorers) == 2

    def test_subset_by_name(self, judges_dir):
        panel = load_panel(judges_dir / "judges.yaml")
        scorers = build_scorers(panel, default_model="mockllm/model", names=["quality"])
        assert len(scorers) == 1

    def test_unknown_name_rejected(self, judges_dir):
        panel = load_panel(judges_dir / "judges.yaml")
        with pytest.raises(JudgesConfigError, match="unknown judge"):
            build_scorers(panel, default_model="mockllm/model", names=["ghost"])

    def test_no_model_anywhere_rejected(self, judges_dir):
        panel = load_panel(judges_dir / "judges.yaml")
        # 'refusal' has no per-judge model, and no default is given
        with pytest.raises(JudgesConfigError, match="has no model"):
            build_scorers(panel, default_model=None, names=["refusal"])

    def test_per_judge_override_needs_no_default(self, judges_dir):
        panel = load_panel(judges_dir / "judges.yaml")
        # 'quality' declares model: mockllm/model in the yaml
        scorers = build_scorers(panel, default_model=None, names=["quality"])
        assert len(scorers) == 1


class TestRenderPrompt:
    def test_variables_rendered(self):
        out = render_prompt(
            "Q: {{ question }} R: {{ response }} G: {{ metadata.genre }}",
            "why?",
            "because",
            {"genre": "edgy"},
        )
        assert out == "Q: why? R: because G: edgy"

    def test_metadata_optional(self):
        out = render_prompt("{{ question }}/{{ response }}", "a", "b", None)
        assert out == "a/b"

    def test_prompt_is_an_alias_for_question(self):
        out = render_prompt("{{ prompt }}/{{ response }}", "why?", "because", None)
        assert out == "why?/because"

    def test_undefined_variable_errors_loudly(self):
        with pytest.raises(UndefinedError):
            render_prompt("{{ nonexistent }}", "a", "b", {})


class TestBuildJudgePrompt:
    def test_footer_substituted_with_binary_tag(self):
        out = build_judge_prompt("rubric\n{{ footer }}", BinaryScale(), "q", "r", None)
        assert "GRADE: <yes|no>" in out
        assert "<reasoning>" in out

    def test_footer_substituted_with_numeric_tag(self):
        out = build_judge_prompt("rubric\n{{ footer }}", NumericScale(0, 100), "q", "r", None)
        assert "GRADE: <0-100>" in out

    def test_footer_lands_where_placed(self):
        out = build_judge_prompt("BEFORE\n{{ footer }}\nAFTER", BinaryScale(), "q", "r", None)
        assert out.index("BEFORE") < out.index("GRADE: <yes|no>") < out.index("AFTER")

    def test_rubric_variables_still_render(self):
        out = build_judge_prompt(
            "Q {{ prompt }} R {{ response }} G {{ metadata.genre }}\n{{ footer }}",
            NumericScale(1, 5),
            "why?",
            "because",
            {"genre": "edgy"},
        )
        assert "Q why? R because G edgy" in out
        assert "GRADE: <1-5>" in out
