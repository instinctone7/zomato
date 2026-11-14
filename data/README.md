# Prepared restaurant data

`restaurants.parquet` is the compact deployment input. It contains 7,824 restaurant branches and only the fields used by the application. Reviews, phone numbers, addresses, menus, and source tracking URLs are excluded. `metadata.json` records the source commit, schema, row count, preparation timestamp, and SHA-256 checksum.

Source: [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation), revision `5738e9eda2fad49ad51c6e0ed26e761d9b947133`.

The source dataset card/API does not specify a license. This project does not assert a license over that source data. Confirm the right to redistribute the derived artifact before publishing it in a repository or public deployment. The artifact was prepared locally; its metadata records provenance and does not establish redistribution permission.

To rebuild with the pinned source revision:

```bash
python -m pip install -r requirements-dev.txt
python scripts/prepare_dataset.py
```

Rebuild the Parquet file and metadata together. The application checks their schema, row count, and checksum at startup and never downloads the full source as a fallback. `cuisines` is normalized to Python lists after Parquet loading. Prepared data contains historical Bangalore information; it is not a live restaurant directory.
