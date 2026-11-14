# Zomato AI Recommender

A Streamlit restaurant discovery app with Groq-powered recommendations. It runs the interface and recommendation logic in one Python process. The included prepared dataset covers historical Bangalore restaurants and localities.

## Run Streamlit locally

Use Python 3.12 (validated with 3.12.16):

```bash
python3.12 -m venv .venv-streamlit
source .venv-streamlit/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open http://localhost:8501. The app reads the included `data/restaurants.parquet` (about 119 KB), so it starts without downloading the original 574 MB dataset. Neither FastAPI nor the static frontend server is needed.

For AI ranking, add your key to the existing ignored `.env` or copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and replace the placeholder. Keep the real file out of Git. Without a key, browsing and rating-based searches still work with an explanatory notice.

## Deploy on Streamlit Community Cloud

1. Review the [data provenance and redistribution note](data/README.md) before publishing the artifact.
2. Push the application, `src/`, `.streamlit/config.toml`, `requirements.txt`, and both prepared data files to your GitHub repository. Do not include `.env`, `.streamlit/secrets.toml`, or virtual environments.
3. At https://share.streamlit.io/, create an app using that repository and branch.
4. Set the main file path to **`app.py`**.
5. In Advanced settings choose **Python 3.12** and add the contents of `.streamlit/secrets.toml.example` to Secrets, replacing `GROQ_API_KEY` with a real deployment key. Keep the keys at the TOML root.
6. Deploy and test a normal search, a relaxed-filter search, and a second browser session.

Do not set a localhost API URL or start an extra server. Root-level Streamlit secrets populate the environment used by the Groq client. Exact runtime package versions are pinned in `requirements.txt`.

The project is prepared and tested locally. Streamlit cloud deployment remains a separate step. See [deploymentPlan.md](deploymentPlan.md) for implementation status, validation, release steps, and rollback.

## Tests and optional local API

Development dependencies include pytest, FastAPI/Uvicorn, the CLI renderer, and source dataset preparation tools:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The API and Streamlit app use the same recommendation service. To run the original interface:

```bash
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
# In another terminal:
python -m http.server 3000 --bind 127.0.0.1 --directory frontend
```

Frontend: http://localhost:3000. API documentation: http://localhost:8000/docs.

## Rebuild prepared data

```bash
python -m pip install -r requirements-dev.txt
python scripts/prepare_dataset.py
```

The script downloads the pinned source revision on a first run, cleans and deduplicates it, and writes Parquet plus checksum/provenance metadata. Preparation requires more memory and network access than running the app. Commit the artifact and metadata together after verifying source redistribution rights. See [data/README.md](data/README.md).
