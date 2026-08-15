"""Solvers other than plain generate().

replay_response() is the whole of the replay path: it fills in the assistant
turn from a CSV column instead of calling a model. Everything downstream — the
judge panel, metrics, .eval serialization, the scoring/ workspaces — reads
state.output.completion and cannot tell the difference.
"""

from __future__ import annotations

from inspect_ai.model import ModelOutput
from inspect_ai.solver import Generate, Solver, TaskState, solver

from wap_eval.dataset import REPLAY_RESPONSE_KEY


class ReplayError(RuntimeError):
    """A replay sample did not carry a pre-generated response."""


@solver
def replay_response() -> Solver:
    """Set the model output from the dataset instead of generating it.

    Pairs with dataset.load_replay_dataset, which stashes the response under
    REPLAY_RESPONSE_KEY. Popping it here matters: inspect logs the sample with
    the *final* state.metadata, so the response never lands in the written log's
    metadata (where it would also be visible to rubrics as {{ metadata.* }}).
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        response = state.metadata.pop(REPLAY_RESPONSE_KEY, None)
        if response is None:
            raise ReplayError(
                f"sample {state.sample_id!r} has no replayed response; the replay "
                f"task must load its dataset with load_replay_dataset()"
            )
        state.output = ModelOutput.from_content(model=str(state.model), content=response)
        state.messages.append(state.output.message)
        return state

    return solve
