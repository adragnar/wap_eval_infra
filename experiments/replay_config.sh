#!/bin/bash

#region Setup
set -eou pipefail

# === Experiment name (passed as argument) ===
expname=${1:?Usage: $0 <experiment_name>}

# === Setup experiment directory ===
log_dir=./logs
testdir=./logs/test

# ============================================
# === PARAMETERS - EDIT THESE FOR YOUR RUN ===
# ============================================
dataset="datasets/workshop_annotations.csv"     # replay CSV: prompt, id, response column, + metadata
response_column="model_response"        # column holding the pre-generated response
model_label="none/handwritten"    # recorded as the log's model; never called
judges="judges/judges.yaml"             # judge panel manifest
judge_model="openrouter/anthropic/claude-sonnet-5"  # default judge model (per-judge override in yaml)
system_prompt=""                        # empty = none (set a filepath to record one)
limit=""                                # empty = all questions
# ============================================
#
# No models/epochs/temperature here: nothing is generated. Keep model_label on
# the none/ provider — it needs no API key and raises if anything tries to
# generate, so a replay run can never quietly become a real API call.

if [ "$expname" = "test" ]; then
  batch_dir="$testdir"
  mkdir -p "$batch_dir"
  if [ -z "$limit" ]; then
    limit=2
  fi
  echo "TEST MODE: Using test directory: $batch_dir (limit=$limit)"
else
  batch_dir=$(./experiments/setup_experiment.sh "$expname" "$log_dir")
  echo "Creating experiment directory: $batch_dir"
  # === Save inputs for reproducibility ===
  cp "$0" "$batch_dir/run_script.sh"
  cp "$dataset" "$batch_dir/"
  cp "$judges" "$batch_dir/"
  if [ -n "$system_prompt" ]; then
    cp "$system_prompt" "$batch_dir/"
  fi
  uv run python -m wap_eval.manifest "$batch_dir" --kind replay \
    --dataset "$dataset" --judges "$judges" \
    --models "$model_label" --judge-model "$judge_model" \
    --response-column "$response_column" \
    ${system_prompt:+--system-prompt "$system_prompt"}
fi
#endregion


#region Run Experiment
# inspect runs the task with cwd set to the task file's directory, so file
# parameters must be passed as absolute paths
abspath() { case "$1" in /*) printf '%s\n' "$1";; *) printf '%s/%s\n' "$PWD" "$1";; esac; }

echo "=== Replaying $response_column as $model_label ==="
args=(eval src/wap_eval/task.py@wap_replay
      --model "$model_label"
      --log-dir "$batch_dir"
      -T "dataset=$(abspath "$dataset")"
      -T "judges=$(abspath "$judges")"
      -T "judge_model=$judge_model"
      -T "response_column=$response_column")
if [ -n "$limit" ]; then
  args+=(--limit "$limit")
fi
if [ -n "$system_prompt" ]; then
  args+=(-T "system_prompt=$(abspath "$system_prompt")")
fi
uv run inspect "${args[@]}"

echo "✅ Done. View results with: uv run inspect view --log-dir $batch_dir"
#endregion
