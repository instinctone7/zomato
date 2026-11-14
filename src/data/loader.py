"""Prepared deployment data loading and optional Hugging Face source loading."""

import hashlib
import json
from pathlib import Path
import sys

import pandas as pd


def load_dataset() -> pd.DataFrame:
    """
    Load the Zomato restaurant dataset from HuggingFace Hub.

    Returns the raw DataFrame with all original columns.
    HuggingFace caches the dataset locally at ~/.cache/huggingface/
    after the first download — subsequent calls are instant.

    Returns:
        pd.DataFrame: Raw restaurant dataset.

    Raises:
        SystemExit: If the dataset cannot be loaded (no internet, bad dataset id, etc.)
    """
    try:
        import datasets as hf_datasets  # import here to keep top-level import fast

        print("⏳ Loading Zomato dataset from HuggingFace Hub...")
        hf_dataset = hf_datasets.load_dataset(
            "ManikaSaini/zomato-restaurant-recommendation",
            split="train",
        )
        df = hf_dataset.to_pandas()
        print(f"✅ Dataset loaded: {len(df):,} rows, {len(df.columns)} columns.")
        print(f"   Columns: {df.columns.tolist()}")
        return df

    except Exception as exc:
        # Covers ConnectionError, FileNotFoundError, ValueError from HF, etc.
        print(
            f"\n❌ ERROR: Could not load the Zomato dataset.\n"
            f"   Reason: {type(exc).__name__}: {exc}\n\n"
            f"   Possible fixes:\n"
            f"   • Check your internet connection (required on first run).\n"
            f"   • Verify the dataset exists at:\n"
            f"     https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation\n"
            f"   • Try clearing the HuggingFace cache:\n"
            f"     rm -rf ~/.cache/huggingface/datasets/ManikaSaini\n",
            file=sys.stderr,
        )
        sys.exit(1)


# Streamlit and the optional API load this compact artifact, never the full source.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT = PROJECT_ROOT / 'data' / 'restaurants.parquet'
SCHEMA_VERSION = 1
REQUIRED_COLUMNS = {'name', 'city', 'location', 'cuisines', 'rating', 'votes',
                    'cost_for_two', 'budget_tier', 'restaurant_type',
                    'has_online_delivery', 'has_table_booking'}


def load_prepared_dataset(path: str | Path = DEFAULT_ARTIFACT) -> pd.DataFrame:
    """Load and validate a versioned, prepared dataset without network access."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError('Prepared restaurant data is missing. Run python scripts/prepare_dataset.py before deployment.')
    metadata_path = path.with_name('metadata.json')
    if not metadata_path.is_file():
        raise ValueError('Restaurant data metadata is missing. Rebuild the prepared dataset.')
    metadata = json.loads(metadata_path.read_text())
    if metadata.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Unsupported restaurant data schema. Rebuild the prepared dataset.')
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata.get('sha256'):
        raise ValueError('Restaurant data checksum does not match its metadata. Rebuild the prepared dataset.')
    data = pd.read_parquet(path)
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing or data.empty or len(data) != metadata.get('row_count'):
        raise ValueError('Restaurant data is empty, incomplete, or inconsistent with its metadata.')
    data['cuisines'] = data['cuisines'].map(
        lambda value: list(value) if isinstance(value, (list, tuple)) or hasattr(value, 'tolist') else []
    )
    if data[['name', 'city', 'location', 'rating', 'votes', 'cost_for_two']].isna().any().any():
        raise ValueError('Restaurant data contains missing required values.')
    if not data['rating'].between(0, 5).all() or not (data['cost_for_two'] > 0).all():
        raise ValueError('Restaurant data contains invalid ratings or prices.')
    return data
