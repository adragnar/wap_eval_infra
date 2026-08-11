import pytest
from inspect_ai.scorer import CORRECT, INCORRECT

from wap_eval.scales import (
    BinaryScale,
    GradeParseError,
    NumericScale,
    ScaleError,
    parse_grade,
    parse_scale,
)


class TestParseScale:
    def test_binary(self):
        assert parse_scale({"type": "binary"}) == BinaryScale()

    def test_numeric(self):
        assert parse_scale({"type": "numeric", "min": 1, "max": 5}) == NumericScale(1, 5)

    def test_numeric_0_100(self):
        assert parse_scale({"type": "numeric", "min": 0, "max": 100}) == NumericScale(0, 100)

    def test_unknown_type_rejected(self):
        with pytest.raises(ScaleError, match="unknown scale type 'likert'"):
            parse_scale({"type": "likert", "points": 7})

    def test_missing_type_rejected(self):
        with pytest.raises(ScaleError, match="unknown scale type"):
            parse_scale({"min": 1, "max": 5})

    def test_non_dict_rejected(self):
        with pytest.raises(ScaleError, match="must be a mapping"):
            parse_scale("binary")

    def test_numeric_missing_bounds_rejected(self):
        with pytest.raises(ScaleError, match="requires integer min and max"):
            parse_scale({"type": "numeric", "min": 1})

    def test_numeric_non_int_bounds_rejected(self):
        with pytest.raises(ScaleError, match="requires integer min and max"):
            parse_scale({"type": "numeric", "min": 1.5, "max": 5})

    def test_numeric_inverted_bounds_rejected(self):
        with pytest.raises(ScaleError, match="min < max"):
            parse_scale({"type": "numeric", "min": 5, "max": 1})

    def test_negative_range_allowed(self):
        assert parse_scale({"type": "numeric", "min": -5, "max": 5}) == NumericScale(-5, 5)

    def test_binary_extra_keys_rejected(self):
        with pytest.raises(ScaleError, match="no extra keys"):
            parse_scale({"type": "binary", "min": 0})

    def test_numeric_extra_keys_rejected(self):
        with pytest.raises(ScaleError, match="extra keys"):
            parse_scale({"type": "numeric", "min": 1, "max": 5, "step": 1})


class TestParseGradeBinary:
    scale = BinaryScale()

    def test_yes_is_correct(self):
        assert parse_grade("Reasoning...\nGRADE: yes", self.scale) == CORRECT

    def test_no_is_incorrect(self):
        assert parse_grade("GRADE: no", self.scale) == INCORRECT

    def test_case_insensitive(self):
        assert parse_grade("grade: YES", self.scale) == CORRECT

    def test_last_occurrence_wins(self):
        text = "I could say GRADE: no but on reflection...\nGRADE: yes"
        assert parse_grade(text, self.scale) == CORRECT

    def test_non_binary_token_rejected(self):
        with pytest.raises(GradeParseError, match="maybe"):
            parse_grade("GRADE: maybe", self.scale)

    def test_missing_grade_rejected(self):
        with pytest.raises(GradeParseError, match="no 'GRADE:"):
            parse_grade("The response was fine.", self.scale)

    def test_empty_rejected(self):
        with pytest.raises(GradeParseError):
            parse_grade("", self.scale)


class TestParseGradeNumeric:
    scale = NumericScale(min=1, max=5)

    def test_in_range(self):
        assert parse_grade("Thinking...\nGRADE: 4", self.scale) == 4

    def test_bounds_inclusive(self):
        assert parse_grade("GRADE: 1", self.scale) == 1
        assert parse_grade("GRADE: 5", self.scale) == 5

    def test_out_of_range_rejected(self):
        with pytest.raises(GradeParseError, match="outside range"):
            parse_grade("GRADE: 7", self.scale)

    def test_non_integer_rejected(self):
        with pytest.raises(GradeParseError, match="non-integer"):
            parse_grade("GRADE: high", self.scale)

    def test_zero_to_hundred(self):
        assert parse_grade("GRADE: 73", NumericScale(0, 100)) == 73

    def test_negative_grade_in_negative_range(self):
        assert parse_grade("GRADE: -3", NumericScale(-5, 5)) == -3


class TestReasoningStripping:
    scale = NumericScale(0, 100)

    def test_grade_mentions_inside_reasoning_ignored(self):
        text = (
            "<reasoning>\nThe format says GRADE: 0 means cruel. I think GRADE: 12 fits.\n"
            "</reasoning>\n\nGRADE: 85"
        )
        assert parse_grade(text, self.scale) == 85

    def test_grade_only_inside_reasoning_is_unparseable(self):
        text = "<reasoning>\nI'd give this GRADE: 40 but I forgot to output it.\n</reasoning>\n"
        with pytest.raises(GradeParseError, match="no 'GRADE:"):
            parse_grade(text, self.scale)

    def test_multiple_reasoning_blocks_all_stripped(self):
        text = (
            "<reasoning>GRADE: 1</reasoning>\nGRADE: 70\n<reasoning>GRADE: 2</reasoning>"
        )
        assert parse_grade(text, self.scale) == 70

    def test_unclosed_reasoning_falls_back_to_last_match(self):
        # sloppy judge never closes the tag but still outputs a grade at the end
        text = "<reasoning>\nThinking about GRADE: 10 ...\n\nGRADE: 90"
        assert parse_grade(text, self.scale) == 90

    def test_case_insensitive_tags(self):
        text = "<Reasoning>GRADE: 5</Reasoning>\nGRADE: 60"
        assert parse_grade(text, self.scale) == 60

    def test_binary_grade_inside_reasoning_ignored(self):
        text = "<reasoning>Could be GRADE: yes or no...</reasoning>\nGRADE: no"
        assert parse_grade(text, BinaryScale()) == INCORRECT
