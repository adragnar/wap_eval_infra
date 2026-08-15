"""Scoring workspace CLI: iterate on judge rubrics against an existing run.

Workspaces live under scoring/ (never logs/). A workspace is a copy of a
source run's .eval logs that is mutated ONLY by this tool:

    init <source_dir>              create a workspace from a run's logs
    run  <workspace> [--judges a,b]  append re-scored judges as <name>_vN columns
    drop <workspace> <scorer_name>   remove a scorer column from the workspace logs

The source run is never touched. Scorer versions are recorded in
scorer_versions.json (milestone-level provenance: git commit at time of run;
commits may be dirty — that is accepted). Versioned names are never reused,
including dropped ones.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai import score as inspect_score
from inspect_ai.log import EvalLog, read_eval_log, write_eval_log

from wap_eval.judges import build_scorers, load_panel
from wap_eval.manifest import git_commit, read_manifest, write_manifest

VERSIONS_NAME = "scorer_versions.json"
DEFAULT_JUDGES_YAML = "judges/judges.yaml"
DEFAULT_SCORING_ROOT = "./scoring"
SETUP_SCRIPT = "./experiments/setup_experiment.sh"


class ScoringError(RuntimeError):
    pass


def _eval_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.eval"))


def _require_workspace(workspace: str | Path) -> Path:
    ws = Path(workspace)
    manifest = read_manifest(ws)
    if manifest is None:
        raise ScoringError(
            f"{ws} has no experiment.json — not a scoring workspace. "
            f"Create one with: python -m wap_eval.scoring init <source_run_dir>"
        )
    if manifest.get("kind") != "scoring_workspace":
        raise ScoringError(
            f"{ws} is kind '{manifest.get('kind')}', refusing to mutate it. "
            f"Only scoring workspaces (under scoring/) may be modified."
        )
    if not _eval_files(ws):
        raise ScoringError(f"{ws} contains no .eval logs")
    return ws


def _read_versions(ws: Path) -> list[dict]:
    path = ws / VERSIONS_NAME
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _write_versions(ws: Path, versions: list[dict]) -> None:
    (ws / VERSIONS_NAME).write_text(json.dumps(versions, indent=2) + "\n")


def _atomic_write_log(log: EvalLog, path: Path) -> None:
    # tmp file keeps the .eval extension so format detection works
    tmp = path.parent / f".tmp_{path.name}"
    write_eval_log(log, str(tmp))
    os.replace(tmp, path)


def _existing_scorer_names(ws: Path) -> set[str]:
    names: set[str] = set()
    for f in _eval_files(ws):
        log = read_eval_log(str(f))
        for sample in log.samples or []:
            names.update((sample.scores or {}).keys())
    names.update(entry["name"] for entry in _read_versions(ws))
    return names


def _next_versioned_name(base: str, existing: set[str]) -> str:
    n = 2
    while f"{base}_v{n}" in existing:
        n += 1
    return f"{base}_v{n}"


# === init ===


def cmd_init(source_dir: str, name: str | None, scoring_root: str) -> Path:
    src = Path(source_dir)
    if not _eval_files(src):
        raise ScoringError(f"no .eval logs found in {src}")
    src_manifest = read_manifest(src)
    if src_manifest is not None and src_manifest.get("kind") not in ("generate", "replay"):
        raise ScoringError(
            f"{src} is kind '{src_manifest.get('kind')}'; workspaces must be "
            f"created from generation or replay runs"
        )
    if name is None:
        name = "iter_" + re.sub(r"^\d+_", "", src.name)

    result = subprocess.run(
        [SETUP_SCRIPT, name, scoring_root], capture_output=True, text=True, check=True
    )
    ws = Path(result.stdout.strip().splitlines()[-1])

    for f in _eval_files(src):
        shutil.copy2(f, ws / f.name)
    write_manifest(ws, kind="scoring_workspace", source=src.name)
    _write_versions(ws, [])
    print(f"Created workspace {ws} from {src.name} ({len(_eval_files(ws))} log(s))")
    return ws


# === run ===


def cmd_run(
    workspace: str,
    judges_arg: str | None,
    judges_yaml: str,
    judge_model: str | None,
) -> list[str]:
    ws = _require_workspace(workspace)
    panel = load_panel(judges_yaml)
    names = (
        [n.strip() for n in judges_arg.split(",") if n.strip()]
        if judges_arg
        else [spec.name for spec in panel]
    )
    existing = _existing_scorer_names(ws)
    rename = {n: _next_versioned_name(n, existing) for n in names}
    scorers = build_scorers(panel, default_model=judge_model, names=names, rename=rename)

    unparseable: dict[str, int] = {v: 0 for v in rename.values()}
    total_samples = 0
    for f in _eval_files(ws):
        print(f"Scoring {f.name} ...")
        log = read_eval_log(str(f))
        scored = inspect_score(log, scorers, action="append", display="plain")
        _atomic_write_log(scored, f)
        for sample in scored.samples or []:
            total_samples += 1
            for versioned in rename.values():
                value = sample.scores[versioned].value if versioned in (sample.scores or {}) else None
                if isinstance(value, float) and math.isnan(value):
                    unparseable[versioned] += 1

    versions = _read_versions(ws)
    commit = git_commit()
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for judge_name, versioned in rename.items():
        spec = next(s for s in panel if s.name == judge_name)
        versions.append(
            {
                "name": versioned,
                "judge": judge_name,
                "git_commit": commit,
                "judge_model": spec.model or judge_model,
                "created": created,
            }
        )
    _write_versions(ws, versions)
    print(f"Appended: {', '.join(rename.values())}")
    for versioned, count in unparseable.items():
        note = " <- check the rubric's GRADE instructions" if count else ""
        print(f"  {versioned}: {count}/{total_samples} unparseable{note}")
    return list(rename.values())


# === drop ===


def cmd_drop(workspace: str, scorer_name: str) -> None:
    ws = _require_workspace(workspace)
    found = False
    for f in _eval_files(ws):
        log = read_eval_log(str(f))
        changed = False
        for sample in log.samples or []:
            if sample.scores and scorer_name in sample.scores:
                del sample.scores[scorer_name]
                changed = True
        if log.results and log.results.scores:
            kept = [s for s in log.results.scores if s.name != scorer_name]
            if len(kept) != len(log.results.scores):
                log.results.scores = kept
                changed = True
        if log.reductions:
            kept_reductions = [r for r in log.reductions if r.scorer != scorer_name]
            if len(kept_reductions) != len(log.reductions):
                log.reductions = kept_reductions
                changed = True
        if changed:
            _atomic_write_log(log, f)
            found = True
    if not found:
        raise ScoringError(f"scorer '{scorer_name}' not found in {ws} logs")

    versions = _read_versions(ws)
    entry = next((v for v in versions if v["name"] == scorer_name), None)
    if entry is not None:
        entry["dropped"] = True
    else:
        # dropping a column the tool didn't create (e.g. an original run scorer)
        versions.append({"name": scorer_name, "dropped": True, "note": "pre-existing column"})
    _write_versions(ws, versions)
    print(f"Dropped {scorer_name} from {ws}")


def main() -> None:
    # inspect eval auto-loads .env; the score() API does not, so do it here
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="wap_eval.scoring",
        description="Iterate on judge rubrics in a scoring workspace (see docs/run_rescoring.md)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a workspace from a run's logs")
    p_init.add_argument("source_dir", help="generation run dir, e.g. logs/1_realrun")
    p_init.add_argument("--name", default=None, help="workspace name (default: iter_<source>)")
    p_init.add_argument("--scoring-root", default=DEFAULT_SCORING_ROOT, help=argparse.SUPPRESS)

    p_run = sub.add_parser("run", help="append re-scored judges as versioned columns")
    p_run.add_argument("workspace", help="workspace dir, e.g. scoring/1_iter_realrun")
    p_run.add_argument("--judges", default=None, help="comma-separated judge names (default: whole panel)")
    p_run.add_argument("--judges-yaml", default=DEFAULT_JUDGES_YAML)
    p_run.add_argument("--judge-model", default=None, help="default judge model")

    p_drop = sub.add_parser("drop", help="remove a scorer column from the workspace logs")
    p_drop.add_argument("workspace")
    p_drop.add_argument("scorer_name", help="versioned scorer name, e.g. my_judge_v3")

    args = parser.parse_args()
    try:
        if args.command == "init":
            cmd_init(args.source_dir, args.name, args.scoring_root)
        elif args.command == "run":
            cmd_run(args.workspace, args.judges, args.judges_yaml, args.judge_model)
        elif args.command == "drop":
            cmd_drop(args.workspace, args.scorer_name)
    except (ScoringError, subprocess.CalledProcessError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
