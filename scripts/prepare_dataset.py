"""Build a compact, reproducible artifact for offline application startup."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.preprocessor import preprocess
from src.data.loader import SCHEMA_VERSION
from src.service import prepare_restaurants

SOURCE_ID = 'ManikaSaini/zomato-restaurant-recommendation'
SOURCE_REVISION = '5738e9eda2fad49ad51c6e0ed26e761d9b947133'


def main():
    from datasets import load_dataset
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default=SOURCE_REVISION, help='Immutable source commit')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'data')
    args = parser.parse_args()
    dataset = load_dataset(SOURCE_ID, revision=args.revision, split='train')
    data = prepare_restaurants(preprocess(dataset.to_pandas()))
    data = data.dropna(subset=['name', 'city', 'location', 'rating', 'votes', 'cost_for_two'])
    data = data[data['cost_for_two'] > 0].reset_index(drop=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / 'restaurants.parquet'
    data.to_parquet(path, index=False, compression='zstd')
    metadata = {
        'schema_version': SCHEMA_VERSION,
        'source_dataset': SOURCE_ID,
        'source_revision': args.revision,
        'source_url': f'https://huggingface.co/datasets/{SOURCE_ID}',
        'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
        'row_count': len(data),
        'columns': list(data.columns),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'license': 'unspecified in source dataset card; verify rights before redistribution',
    }
    path.with_name('metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(f'Prepared {len(data):,} restaurants; artifact size {path.stat().st_size / 1024:.0f} KiB')


if __name__ == '__main__':
    main()
