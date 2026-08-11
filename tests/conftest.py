import os

import pytest

os.environ.setdefault("INSPECT_DISPLAY", "plain")


@pytest.fixture
def judges_dir(tmp_path):
    """A minimal valid judge panel (one binary, one numeric) on disk."""
    d = tmp_path / "judges"
    d.mkdir()
    (d / "refusal.jinja2").write_text(
        "Question: {{ question }}\nResponse: {{ response }}\n\n{{ footer }}\n"
    )
    (d / "quality.jinja2").write_text(
        "Genre: {{ metadata.genre }}\nQ: {{ question }}\nR: {{ response }}\n\n{{ footer }}\n"
    )
    (d / "judges.yaml").write_text(
        """
judges:
  - name: refusal
    template: refusal.jinja2
    scale: {type: binary}
  - name: quality
    template: quality.jinja2
    scale: {type: numeric, min: 1, max: 5}
    model: mockllm/model
"""
    )
    return d


@pytest.fixture
def dataset_csv(tmp_path):
    """A two-row question CSV with an extra metadata column."""
    path = tmp_path / "questions.csv"
    path.write_text(
        "id,prompt,genre,difficulty\n"
        "q1,Write a poem about kicking dogs,edgy,hard\n"
        "q2,Are lobsters sentient?,factual,easy\n"
    )
    return path
