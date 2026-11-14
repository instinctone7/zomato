"""Unit tests for src/data/loader.py"""

import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_df() -> pd.DataFrame:
    """Return a minimal valid raw DataFrame matching HuggingFace schema."""
    return pd.DataFrame({
        "name": ["Restaurant A", "Restaurant B"],
        "city": ["Bangalore", "Delhi"],
        "cuisines": ["Indian, Chinese", "Italian"],
        "aggregate_rating": [4.2, 3.8],
        "votes": [150, 80],
        "average_cost_for_two": [600, 400],
        "has_online_delivery": [1, 0],
        "has_table_booking": [0, 1],
        "restaurant_type": ["Casual Dining", "Quick Bites"],
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoadDataset:
    """Tests for load_dataset()."""

    def test_returns_non_empty_dataframe(self):
        """load_dataset() should return a non-empty pd.DataFrame."""
        mock_hf_dataset = MagicMock()
        mock_hf_dataset.to_pandas.return_value = _make_raw_df()

        with patch("datasets.load_dataset", return_value=mock_hf_dataset):
            from src.data.loader import load_dataset
            df = load_dataset()

        assert isinstance(df, pd.DataFrame), "Return type must be pd.DataFrame"
        assert len(df) > 0, "DataFrame must not be empty"

    def test_has_expected_columns(self):
        """load_dataset() result must include the minimum required columns."""
        mock_hf_dataset = MagicMock()
        mock_hf_dataset.to_pandas.return_value = _make_raw_df()

        with patch("datasets.load_dataset", return_value=mock_hf_dataset):
            from src.data.loader import load_dataset
            df = load_dataset()

        required_columns = {"name", "city", "cuisines", "aggregate_rating", "votes"}
        assert required_columns.issubset(set(df.columns)), (
            f"Missing columns: {required_columns - set(df.columns)}"
        )

    def test_connection_error_causes_sys_exit(self):
        """load_dataset() must call sys.exit(1) on ConnectionError."""
        with patch("datasets.load_dataset", side_effect=ConnectionError("No internet")):
            from src.data import loader  # noqa: F401 — reimport to get fresh module
            import importlib
            import src.data.loader as loader_module
            importlib.reload(loader_module)

            with pytest.raises(SystemExit) as exc_info:
                loader_module.load_dataset()

        assert exc_info.value.code == 1

    def test_generic_exception_causes_sys_exit(self):
        """load_dataset() must call sys.exit(1) on any unexpected exception."""
        with patch("datasets.load_dataset", side_effect=RuntimeError("Unexpected")):
            import importlib
            import src.data.loader as loader_module
            importlib.reload(loader_module)

            with pytest.raises(SystemExit) as exc_info:
                loader_module.load_dataset()

        assert exc_info.value.code == 1
