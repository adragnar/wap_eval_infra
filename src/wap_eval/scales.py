"""Scale registry for judge scores.

A scale declares a judge's output contract: what the judge is allowed to
answer and how the answer is converted to a stored score value. The set of
valid scale types is closed — an unknown or malformed scale in a judges yaml
raises ScaleError at load time, before any model call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from inspect_ai.scorer import CORRECT, INCORRECT


class ScaleError(ValueError):
    """A judges yaml declared a scale outside the registry."""


class GradeParseError(ValueError):
    """A judge's output did not conform to its declared scale."""


@dataclass(frozen=True)
class BinaryScale:
    def describe(self) -> str:
        return "binary (expects 'GRADE: yes' or 'GRADE: no')"


@dataclass(frozen=True)
class NumericScale:
    min: int
    max: int

    def describe(self) -> str:
        return f"numeric (expects 'GRADE: <integer in [{self.min}, {self.max}]>')"


Scale = BinaryScale | NumericScale

SCALE_TYPES = ("binary", "numeric")


def parse_scale(raw: object) -> Scale:
    """Validate a yaml scale declaration and return the Scale, or raise ScaleError."""
    if not isinstance(raw, dict):
        raise ScaleError(
            f"scale must be a mapping like {{type: binary}} or "
            f"{{type: numeric, min: 1, max: 5}}, got: {raw!r}"
        )
    scale_type = raw.get("type")
    if scale_type == "binary":
        extra = set(raw) - {"type"}
        if extra:
            raise ScaleError(f"binary scale takes no extra keys, got: {sorted(extra)}")
        return BinaryScale()
    if scale_type == "numeric":
        extra = set(raw) - {"type", "min", "max"}
        if extra:
            raise ScaleError(f"numeric scale takes only min/max, got extra keys: {sorted(extra)}")
        lo, hi = raw.get("min"), raw.get("max")
        if not isinstance(lo, int) or not isinstance(hi, int) or isinstance(lo, bool) or isinstance(hi, bool):
            raise ScaleError(f"numeric scale requires integer min and max, got min={lo!r} max={hi!r}")
        if lo >= hi:
            raise ScaleError(f"numeric scale requires min < max, got min={lo} max={hi}")
        return NumericScale(min=lo, max=hi)
    raise ScaleError(
        f"unknown scale type {scale_type!r}; valid types: {', '.join(SCALE_TYPES)}"
    )


GRADE_RE = re.compile(r"GRADE\s*:\s*([A-Za-z0-9+-]+)", re.IGNORECASE)


def parse_grade(text: str, scale: Scale) -> int | str:
    """Parse the structured 'GRADE: <x>' tail of a judge's output.

    Uses the LAST occurrence, since rubrics may mention GRADE earlier in
    reasoning. Raises GradeParseError on any out-of-contract output.

    Binary grades map to inspect's CORRECT/INCORRECT primitives (yes ->
    CORRECT, no -> INCORRECT), which inspect treats as 1/0 in metrics and
    renders as correct/incorrect in the log viewer. Phrase binary rubrics so
    that "yes" is the desirable outcome. Numeric grades stay integers.
    """
    matches = GRADE_RE.findall(text or "")
    if not matches:
        raise GradeParseError(f"no 'GRADE: <x>' found in judge output; {scale.describe()}")
    token = matches[-1].strip().lower()
    if isinstance(scale, BinaryScale):
        if token in ("yes", "y"):
            return CORRECT
        if token in ("no", "n"):
            return INCORRECT
        raise GradeParseError(f"got 'GRADE: {token}'; {scale.describe()}")
    try:
        value = int(token)
    except ValueError:
        raise GradeParseError(f"got non-integer 'GRADE: {token}'; {scale.describe()}") from None
    if not scale.min <= value <= scale.max:
        raise GradeParseError(f"got 'GRADE: {value}', outside range; {scale.describe()}")
    return value
