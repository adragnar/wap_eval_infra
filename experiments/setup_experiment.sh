#!/bin/bash
set -eou pipefail

# Setup script for experiments
# Creates numbered experiment directory, saves git info
# Usage: batch_dir=$(./experiments/setup_experiment.sh <experiment_name> [log_dir])
#
# Arguments:
#   experiment_name  - Name for this experiment (required)
#   log_dir          - Base directory for logs (default: ./logs)
#
# Outputs:
#   Prints the created batch_dir path to stdout

expname=${1:?Usage: $0 <experiment_name> [log_dir]}
log_dir=${2:-./logs}

# === Find next experiment number ===
mkdir -p "$log_dir"
last_num=$(ls -d "$log_dir"/[0-9]*_* 2>/dev/null | sed 's/.*\/\([0-9]*\)_.*/\1/' | sort -n | tail -1 || echo "0")
next_num=$((last_num + 1))
batch_dir="$log_dir/${next_num}_${expname}"
mkdir -p "$batch_dir"

# === Save git info ===
echo "commit: $(git rev-parse HEAD)" > "$batch_dir/git_status.txt"
git status --porcelain >> "$batch_dir/git_status.txt"

# === Output the batch_dir for the caller ===
echo "$batch_dir"
