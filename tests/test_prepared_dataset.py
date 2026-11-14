import hashlib
import json
from pathlib import Path

import pytest

from src.data.loader import DEFAULT_ARTIFACT, load_prepared_dataset
from src.service import get_options, get_discovery


def test_packaged_artifact_is_complete_and_small():
    data = load_prepared_dataset()
    assert len(data) > 7000
    assert DEFAULT_ARTIFACT.stat().st_size < 2_000_000
    assert all(isinstance(value, list) for value in data['cuisines'])
    assert not data.duplicated(['name','location']).any()
    assert any('Santé Spa Cuisine' == name for name in data['name'])
    assert 'Indiranagar' in get_options(data)['locations']
    assert len(get_discovery(data)) == 6


def test_missing_data_never_downloads_source(tmp_path):
    with pytest.raises(FileNotFoundError, match='Prepared restaurant data is missing'):
        load_prepared_dataset(tmp_path/'missing.parquet')


def test_checksum_mismatch_is_rejected(tmp_path):
    path = tmp_path/'restaurants.parquet'
    path.write_bytes(b'invalid')
    (tmp_path/'metadata.json').write_text(json.dumps({'schema_version':1,'sha256':'wrong'}))
    with pytest.raises(ValueError, match='checksum'):
        load_prepared_dataset(path)


def test_schema_mismatch_is_rejected(tmp_path):
    path = tmp_path/'restaurants.parquet'
    path.write_bytes(b'invalid')
    (tmp_path/'metadata.json').write_text(json.dumps({'schema_version':99}))
    with pytest.raises(ValueError, match='schema'):
        load_prepared_dataset(path)
