"""Unit tests for evaluation dataset_source."""

import json

import pytest

from evaluation.dataset_source import (
    create_langfuse_dataset_from_path,
    get_langfuse_dataset_by_name,
    load_local_dataset,
)
from schemas.evaluation import EvalDatasetItem


def _make_item(
    item_id: str = "item-1",
    input_text: str = "What is the revenue?",
    expected_output: str | None = None,
) -> EvalDatasetItem:
    return EvalDatasetItem(
        id=item_id,
        input=input_text,
        chat_history=[],
        expected_output=expected_output,
    )


class TestCreateLangfuseDatasetFromPath:
    """Tests for create_langfuse_dataset_from_path."""

    def test_raises_when_file_not_found(self, tmp_path):
        """Raises FileNotFoundError when path does not exist."""
        path = tmp_path / "nonexistent.jsonl"
        assert not path.exists()
        with pytest.raises(FileNotFoundError, match="Dataset file not found"):
            create_langfuse_dataset_from_path(path)

    def test_raises_when_langfuse_disabled(self, mocker, tmp_path):
        """Raises RuntimeError when Langfuse is not configured."""
        mocker.patch("evaluation.dataset_source.get_langfuse_client", return_value=None)
        path = tmp_path / "items.jsonl"
        path.write_text(
            json.dumps({"id": "1", "input": "Hi", "chat_history": []}) + "\n"
        )
        with pytest.raises(RuntimeError, match="Langfuse is not configured"):
            create_langfuse_dataset_from_path(path)

    def test_creates_dataset_and_appends_items(self, mocker, tmp_path):
        """Creates dataset if not exists and creates items from JSONL."""
        mock_client = mocker.MagicMock()
        mock_dataset = mocker.MagicMock()
        mock_dataset.name = "my-ds"
        mock_dataset.items = []
        # First call 404, then after create_dataset, then refresh at end
        mock_client.get_dataset.side_effect = [
            Exception("404"),
            mock_dataset,
            mock_dataset,
        ]
        mocker.patch(
            "evaluation.dataset_source.get_langfuse_client", return_value=mock_client
        )
        path = tmp_path / "items.jsonl"
        path.write_text(
            json.dumps({"id": "a", "input": "Hi", "chat_history": []}) + "\n"
        )
        mocker.patch(
            "evaluation.dataset_source.load_jsonl",
            return_value=[_make_item(item_id="a", input_text="Hi")],
        )

        result = create_langfuse_dataset_from_path(path, dataset_name="my-ds")

        assert result.type == "langfuse_dataset"
        assert result.dataset.name == "my-ds"
        mock_client.create_dataset.assert_called_once()
        mock_client.create_dataset_item.assert_called_once()
        assert mock_client.get_dataset.call_count >= 2
        mock_client.get_dataset.assert_any_call("my-ds")


class TestGetLangfuseDatasetByName:
    """Tests for get_langfuse_dataset_by_name."""

    def test_raises_when_langfuse_disabled(self, mocker):
        """Raises RuntimeError when Langfuse is not configured."""
        mocker.patch("evaluation.dataset_source.get_langfuse_client", return_value=None)
        with pytest.raises(RuntimeError, match="Langfuse is not configured"):
            get_langfuse_dataset_by_name("my-ds")

    def test_raises_when_dataset_not_found(self, mocker):
        """Raises FileNotFoundError when dataset does not exist (404)."""
        mock_client = mocker.MagicMock()
        mock_client.get_dataset.side_effect = Exception("404 Not Found")
        mocker.patch(
            "evaluation.dataset_source.get_langfuse_client", return_value=mock_client
        )
        with pytest.raises(FileNotFoundError, match="Langfuse dataset not found"):
            get_langfuse_dataset_by_name("missing-ds")

    def test_returns_langfuse_dataset_when_found(self, mocker):
        """Returns LangfuseEvalDataset when dataset exists."""
        mock_client = mocker.MagicMock()
        mock_dataset = mocker.MagicMock()
        mock_dataset.name = "my-ds"
        mock_client.get_dataset.return_value = mock_dataset
        mocker.patch(
            "evaluation.dataset_source.get_langfuse_client", return_value=mock_client
        )

        result = get_langfuse_dataset_by_name("my-ds")

        assert result.type == "langfuse_dataset"
        assert result.dataset.name == "my-ds"
        mock_client.get_dataset.assert_called_once_with("my-ds")


class TestLoadLocalDataset:
    """Tests for load_local_dataset."""

    def test_raises_when_file_not_found(self, tmp_path):
        """Raises FileNotFoundError when path does not exist."""
        path = tmp_path / "nonexistent.jsonl"
        assert not path.exists()
        with pytest.raises(FileNotFoundError, match="Dataset file not found"):
            load_local_dataset(dataset_name="nonexistent", dataset_path=path)

    def test_returns_items_from_jsonl(self, tmp_path):
        """Returns LocalEvalDataset with items from JSONL."""
        path = tmp_path / "items.jsonl"
        path.write_text(
            json.dumps({"id": "1", "input": "Hi", "chat_history": []})
            + "\n"
            + json.dumps({"id": "2", "input": "Bye", "chat_history": []})
            + "\n"
        )
        result = load_local_dataset(dataset_name="items", dataset_path=path)
        assert result.type == "local_dataset"
        assert len(result.items) == 2
        assert result.items[0].id == "1"
        assert result.items[1].id == "2"

    def test_applies_limit(self, tmp_path):
        """Limit restricts number of items."""
        path = tmp_path / "items.jsonl"
        path.write_text(
            json.dumps({"id": "1", "input": "A", "chat_history": []})
            + "\n"
            + json.dumps({"id": "2", "input": "B", "chat_history": []})
            + "\n"
            + json.dumps({"id": "3", "input": "C", "chat_history": []})
            + "\n"
        )
        result = load_local_dataset(dataset_name="items", dataset_path=path, limit=2)
        assert len(result.items) == 2
        assert result.items[0].id == "1"
        assert result.items[1].id == "2"
