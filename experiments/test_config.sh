#!/bin/bash

#region Setup
set -eou pipefail

# === Experiment name (passed as argument) ===
expname=${1:?Usage: $0 <experiment_name>}

# === Setup experiment directory ===
log_dir=./logs
testdir=./logs/test

if [ "$expname" = "test" ]; then
  batch_dir="$testdir"
  mkdir -p "$batch_dir"
  echo "TEST MODE: Using test directory: $batch_dir"
else
  batch_dir=$(./experiments/setup_experiment.sh "$expname" "$log_dir")
  echo "Creating experiment directory: $batch_dir"
  # === Save this script for reproducibility ===
  cp "$0" "$batch_dir/run_script.sh"
fi
#endregion


# ============================================
# === PARAMETERS - EDIT THESE FOR YOUR RUN ===
# ============================================
models=("openai/gpt-4o-mini")  

# ============================================

#region Run Experiment
# === Run batch ===

#endregion
