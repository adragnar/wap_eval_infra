"""Provenance manifests: experiment.json in every batch dir.

One schema for all batch dirs. kind "generate" = an immutable generation run;
kind "scoring_workspace" = a tool-mutable rubric-iteration sandbox (see
scoring.py). `source` names the immediate parent batch dir for workspaces.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_NAME = "experiment.json"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def write_manifest(
    batch_dir: str | Path,
    kind: str,
    source: str | None = None,
    dataset: str | None = None,
    judges: str | None = None,
    params: dict | None = None,
) -> dict:
    batch_dir = Path(batch_dir)
    manifest = {
        "id": batch_dir.name,
        "kind": kind,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "git_commit": git_commit(),
        "dataset": {"path": dataset, "sha256": sha256_file(dataset)} if dataset else None,
        "judges": {"path": judges, "sha256": sha256_file(judges)} if judges else None,
        "params": params or {},
    }
    (batch_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def read_manifest(batch_dir: str | Path) -> dict | None:
    path = Path(batch_dir) / MANIFEST_NAME
    if not path.exists():
        return None
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wap_eval.manifest", description="Write an experiment.json into a batch dir"
    )
    parser.add_argument("batch_dir")
    parser.add_argument("--kind", required=True, choices=["generate", "scoring_workspace"])
    parser.add_argument("--source", default=None)
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--judges", default=None)
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--temperature", default=None)
    parser.add_argument("--system-prompt", default=None)
    args = parser.parse_args()

    params = {
        "models": args.models,
        "judge_model": args.judge_model,
        "epochs": args.epochs,
        "temperature": args.temperature,
        "system_prompt": args.system_prompt,
    }
    write_manifest(
        args.batch_dir,
        kind=args.kind,
        source=args.source,
        dataset=args.dataset,
        judges=args.judges,
        params={k: v for k, v in params.items() if v is not None},
    )
    print(f"Wrote {Path(args.batch_dir) / MANIFEST_NAME}")


if __name__ == "__main__":
    main()
