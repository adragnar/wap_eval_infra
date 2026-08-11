import pytest

from wap_eval.dataset import DatasetError, load_dataset, record_to_sample


class TestMetadataPassthrough:
    def test_reserved_columns_mapped(self, dataset_csv):
        samples = list(load_dataset(str(dataset_csv)))
        assert samples[0].id == "q1"
        assert samples[0].input == "Write a poem about kicking dogs"

    def test_all_other_columns_become_metadata(self, dataset_csv):
        samples = list(load_dataset(str(dataset_csv)))
        assert samples[0].metadata == {"genre": "edgy", "difficulty": "hard"}
        assert samples[1].metadata == {"genre": "factual", "difficulty": "easy"}

    def test_arbitrary_future_columns_pass_through(self, tmp_path):
        path = tmp_path / "wide.csv"
        path.write_text(
            "id,prompt,genre,species,severity,source_batch\n"
            "q1,hello,g,chicken,3,batch_7\n"
        )
        (sample,) = list(load_dataset(str(path)))
        assert sample.metadata == {
            "genre": "g",
            "species": "chicken",
            "severity": "3",
            "source_batch": "batch_7",
        }

    def test_no_metadata_columns_is_fine(self, tmp_path):
        path = tmp_path / "narrow.csv"
        path.write_text("id,prompt\nq1,hello\n")
        (sample,) = list(load_dataset(str(path)))
        assert sample.metadata == {}


class TestContractValidation:
    def test_missing_prompt_column_rejected(self):
        with pytest.raises(DatasetError, match="prompt"):
            record_to_sample({"id": "q1", "question": "hello"})

    def test_missing_id_column_rejected(self):
        with pytest.raises(DatasetError, match="id"):
            record_to_sample({"prompt": "hello"})
