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
models=("mockllm/model")                # models under test (inspect model IDs)
dataset="datasets/test_dataset.csv"     # question CSV: prompt, id, + metadata columns
judges="judges/judges.yaml"             # judge panel manifest
judge_model="mockllm/model"             # default judge model (per-judge override in yaml)
epochs=1                                # responses generated per question
temperature=""                          # empty = provider default
system_prompt=""                        # empty = no system prompt (set a filepath to enable)
limit=""                                # empty = all questions
# ============================================

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
  uv run python -m wap_eval.manifest "$batch_dir" --kind generate \
    --dataset "$dataset" --judges "$judges" \
    --models "${models[@]}" --judge-model "$judge_model" --epochs "$epochs" \
    ${temperature:+--temperature "$temperature"} \
    ${system_prompt:+--system-prompt "$system_prompt"}
fi
#endregion


#region Run Experiment
# inspect runs the task with cwd set to the task file's directory, so file
# parameters must be passed as absolute paths
abspath() { case "$1" in /*) printf '%s\n' "$1";; *) printf '%s/%s\n' "$PWD" "$1";; esac; }

for model in "${models[@]}"; do
  echo "=== Evaluating $model ==="
  args=(eval src/wap_eval/task.py@wap_eval
        --model "$model"
        --log-dir "$batch_dir"
        --epochs "$epochs"
        -T "dataset=$(abspath "$dataset")"
        -T "judges=$(abspath "$judges")"
        -T "judge_model=$judge_model")
  if [ -n "$temperature" ]; then
    args+=(--temperature "$temperature")
  fi
  if [ -n "$limit" ]; then
    args+=(--limit "$limit")
  fi
  if [ -n "$system_prompt" ]; then
    args+=(-T "system_prompt=$(abspath "$system_prompt")")
  fi
  uv run inspect "${args[@]}"
done

echo "✅ Done. View results with: uv run inspect view --log-dir $batch_dir"
#endregion
