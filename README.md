# WAP Eval Infrastructure

Evaluation harness for the Welfare Alignment Project: run question datasets against
LLMs, score every response with a panel of LLM judges, and iterate on both questions
and judge rubrics. Built on [inspect-ai](https://inspect.aisi.org.uk/).

## Setup

1. Clone the repo and `cd` into it
2. Run `./setup.sh` (installs dependencies via `uv sync`)
3. Add a `.env` file with your API keys

## Workflows

- **Run an eval** — [docs/run_eval.md](docs/run_eval.md): drop a question CSV in
  `datasets/`, copy `experiments/test_config.sh`, edit the parameter block, run.
- **Replay pre-generated responses** — [docs/run_replay.md](docs/run_replay.md): judge
  responses collected by hand from a CSV, with no model under test ever called.
- **Iterate on scorers** — [docs/run_rescoring.md](docs/run_rescoring.md): revise
  judge rubrics and re-score an existing run's responses in a scoring workspace,
  without re-running any model under test.

## Reference

- [docs/project_architecture.md](docs/project_architecture.md) — repo structure and design
- [docs/evaluation_parameters.md](docs/evaluation_parameters.md) — every run parameter
- [docs/testing_workflow.md](docs/testing_workflow.md) — tests-first development workflow
  (`uv run pytest` must stay green)
