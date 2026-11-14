# Streamlit Deployment Plan

Updated: 15 November 2026  
Target: Streamlit Community Cloud  
Status: Streamlit implementation completed and validated locally on Python 3.12.16. Streamlit cloud deployment remains to be done.

## Implementation status

- Implemented `app.py`, shared `src/service.py`, and API delegation.
- Added a prepared Parquet loader with schema, row-count, and SHA-256 checks; no production source download.
- Prepared 7,824 restaurant branches in an approximately 119 KB artifact, with provenance metadata.
- Added Streamlit theme configuration, a secrets example, ignored secret files, and pinned runtime/development requirements.
- All 160 tests pass on Python 3.12.16, covering form submission, persistent results, session isolation, Cloud secrets, missing credentials/data, invalid AI output, and labeled fallbacks through Streamlit AppTest.
- Verified real Groq recommendations in the Streamlit browser preview at `http://127.0.0.1:8501`. A runtime-only Python 3.12 environment also passed discovery, health, and live searches without the optional development packages; Cafe search took 2.23 seconds and relaxed BBQ search took 1.60 seconds locally.
- Python 3.12 local benchmark: prepared DataFrame about 1.54 MiB, initial AppTest render/load about 0.14 seconds, and peak process RSS about 156 MiB. These are local macOS measurements, not hosted/Linux guarantees.
- Dataset API/card has no published license metadata. See `data/README.md` before redistributing the prepared artifact.

The sections below retain the design and release checklist. Described application files are now present; hosted acceptance remains pending.

## 1. Current project and deployment approach

The working local application has a static HTML/CSS/JavaScript frontend on port 3000 and a FastAPI backend on port 8000. Its recommendation pipeline uses a historical Bangalore restaurant dataset and calls Groq. The latest local verification passed 150 tests and exercised real AI recommendations, relaxed filters, and browser rendering.

Deploy one Streamlit application that runs the UI and Python recommendation logic in the same process. Keep the existing API and static frontend available for local development. Reuse their behavior through a shared service rather than duplicating it.

The deployed request flow will be:

1. A visitor selects location, cuisine, budget, rating, and optional preferences in a Streamlit form.
2. Python validates the input and filters the prepared restaurant dataset.
3. The server sends only the shortlisted candidates and preferences to Groq.
4. Streamlit renders the ranked recommendations, explanations, trade-offs, and any fallback notices.

The deployed app must not call `localhost:8000` or start a second FastAPI server. The current `frontend/app.js` cannot be used unchanged: its localhost URL would point to the visitor's own computer. Recreate the interface with Streamlit widgets and styling; preserve the warm background, red accents, restaurant cards, and search flow where practical. An exact reproduction of the static layout is outside this deployment approach.

## 2. Required implementation work

### A. Extract a shared recommendation service

Create `src/service.py` and move framework-independent orchestration out of `src/api.py`:

- Prepare and deduplicate restaurant data.
- Build available location and cuisine options.
- Select discovery restaurants.
- Match cities and localities, keeping one unambiguous restaurant branch per name in each shortlist.
- Validate preferences, filter candidates, build prompts, call Groq, and parse results.
- Preserve the relaxed-filter explanation in the prompt and response.
- Preserve labeled rating-based fallback for timeouts, API failures, and invalid AI output.

Accept the prepared DataFrame and preferences as inputs. Return the existing result dictionary. The service must not depend on FastAPI request objects, `app.state`, Streamlit widgets, or global user preferences. Update the API routes to delegate to it so local API tests continue to verify the same behavior used in deployment.

### B. Create the Streamlit entry point

Create root-level `app.py` with:

- Page title, icon, wide layout, and a clear Bangalore dataset notice.
- Location and cuisine options derived from the actual data.
- A form containing budget, rating, and optional notes capped at 200 characters.
- One recommendation call per form submission, with a loading indicator.
- Results stored in `st.session_state` so unrelated widget changes do not repeat Groq calls or erase the shortlist.
- Discovery cards before the first search, then personalized results after submission.
- Clear no-results, invalid-input, dataset-load, missing-key, AI-unavailable, and relaxed-filter messages.

Reuse or adapt `render_streamlit(result)` in `src/output/formatter.py`. Render user input and model text through safe Streamlit text functions; reserve custom HTML for fixed application markup. Treat ambience descriptions as suggestions inferred from available data, not verified facilities.

### C. Prepare a compact data artifact

The existing loader downloads approximately 574 MB and materializes all source columns, including reviews and menus that the app does not need. This creates avoidable startup and memory risk.

Create `scripts/prepare_dataset.py` to run locally before deployment:

1. Load the existing Hugging Face dataset and run the verified preprocessing steps, including rating parsing, comma-separated prices, boolean conversion, and corrupted-name repair.
2. Keep only `name`, `city`, `location`, `cuisines`, `rating`, `votes`, `cost_for_two`, `budget_tier`, `restaurant_type`, `has_online_delivery`, and `has_table_booking`.
3. Apply the same branch deduplication used by the current API.
4. Write `data/restaurants.parquet` and a small metadata file containing source dataset ID/revision, preparation date, schema version, and row count.
5. Verify the source dataset's license and redistribution terms before including a derived artifact in GitHub. If redistribution is unsuitable, keep the compact artifact in an authorized external store and download that artifact instead.

Add a loader for the prepared artifact. When loading Parquet, normalize `cuisines` back to ordinary Python lists if the reader returns arrays. Fail with a useful UI message when the artifact is missing or invalid; do not silently download the full source during production startup.

Cache the compact DataFrame with `st.cache_data`, using an artifact/schema version to invalidate stale data. Cache options and discovery output where useful. Keep personal search results in session state, not a shared cache. Cached data can be shared across sessions and each caller receives a copy, so profile memory with multiple sessions. [Streamlit caching reference](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data)

## 3. Files to prepare

Implemented additions:

- `app.py`: Streamlit application entry point.
- `src/service.py`: shared application orchestration.
- `scripts/prepare_dataset.py`: reproducible compact dataset preparation.
- `data/restaurants.parquet` and `data/metadata.json`: approved prepared data.
- `.streamlit/config.toml`: committed visual configuration.
- `.streamlit/secrets.toml.example`: placeholders only.
- `requirements-dev.txt`: test tooling and local API dependencies if split from runtime dependencies.
- Streamlit smoke tests and shared-service regression tests.

Implemented updates:

- `src/api.py`: delegate to the shared service.
- `src/data/loader.py`: support the prepared production artifact.
- `requirements.txt`: tested deployment dependencies.
- `.gitignore`: ignore `.streamlit/secrets.toml` in addition to the existing `.env` exclusions.
- `README.md`: Streamlit setup, local launch, and deployment instructions.

Do not commit `.env`, `.streamlit/secrets.toml`, `.venv`, source dataset caches, or generated logs.

## 4. Runtime and dependencies

Use Python **3.12** as the initial deployment target, selected explicitly in Community Cloud Advanced settings. Rebuild and test a clean environment with that version; success in the existing local Python 3.15 environment does not establish Python 3.12 compatibility. Community Cloud's deployment dialog supports selecting the Python version. [Deployment settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

Keep `requirements.txt` at the repository root beside `app.py`. Include Streamlit, pandas, pyarrow for Parquet, Groq, python-dotenv, and ftfy wherever imported. Retain any additional packages imported by the chosen runtime path. The full-dataset preparation tool needs `datasets`; tests need pytest, and the optional local API needs FastAPI, Uvicorn, and its test dependencies.

Resolve and pin exact package versions after clean Python 3.12 validation. Do not freeze the entire machine environment or retain unbounded minimum-only versions for the release. Streamlit documents root-level requirements discovery and recommends pinning its version. [Dependency configuration](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies), [Application maintenance](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)

Suggested theme for `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#e7394e"
backgroundColor = "#fffcf9"
secondaryBackgroundColor = "#ffffff"
textColor = "#262326"
font = "sans serif"
```

## 5. Groq configuration and secrets

Configure these as **root-level TOML keys** in Community Cloud's Secrets settings:

```toml
GROQ_API_KEY = "REPLACE_WITH_DEPLOYMENT_KEY"
LLM_PROVIDER = "groq"
GROQ_MODEL = "openai/gpt-oss-120b"
LLM_TEMPERATURE = "0.3"
MAX_CANDIDATES = "15"
TOP_N_RESULTS = "5"
```

Use a dedicated deployment key. Do not copy the actual key into this plan, source code, screenshots, or logs. Validate the configured model with a live request before release because provider availability can change.

Root-level Streamlit secrets are exposed as environment variables, which matches the existing client's `os.getenv` configuration. Keep these keys at the root rather than under a TOML section. For local Streamlit development, use an ignored `.streamlit/secrets.toml` or the existing ignored `.env`. [Secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management)

Show a helpful missing-key message while allowing discovery data to load. Preserve the bounded Groq timeout/retry behavior. Do not enable `HF_HUB_OFFLINE=1` in a deployment that needs to download an external artifact; the development machine's existing cache will not be present in a new cloud environment.

## 6. Local release verification

Run these steps after implementing the files above, in a fresh Python 3.12 environment:

```bash
python3.12 -m venv .venv-streamlit
source .venv-streamlit/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python scripts/prepare_dataset.py
python -m pytest -q
python -m streamlit run app.py
```

Ignore `.venv-streamlit/` before committing. The preparation script and development requirements are now implemented. Normal app startup uses the included artifact; rebuilding it is only needed when source/preprocessing changes.

Release checks:

- [x] Existing 150-test baseline and new migration tests pass on Python 3.12.
- [x] Streamlit AppTest covers initial rendering, form submission, and labeled fallbacks with mocked Groq responses.
- [x] A real Groq search works for Indiranagar, medium budget, Cafe, minimum rating 4.0.
- [x] A Bangalore BBQ search with medium budget and rating 4.5 explains the relaxed budget and returns valid alternatives.
- [x] Corrupted names display correctly, and AI output cannot replace verified prices or ratings.
- [ ] Invalid input, empty searches, missing credentials, timeout, rate-limit, and malformed-response paths are usable.
- [x] Reruns do not trigger duplicate requests; two browser sessions keep preferences/results separate.
- [ ] The app works with both local development servers stopped; browser requests contain no localhost API URL.
- [x] Cold-start time and peak memory are measured from a fresh process without the original dataset cache.
- [ ] Desktop and mobile layouts are readable and keep search controls usable.

Treat warm searches completing within roughly five seconds under normal provider conditions as a target, not a guarantee. Measure actual cloud behavior separately from the earlier local timings.

## 7. Community Cloud deployment procedure

Use the intended GitHub repository for the release, confirm its visibility and the application audience, and push only the reviewed application files, dependency files, and approved data artifact. GitHub destination: `https://github.com/instinctone7/zomato`. Streamlit deployment is configured separately.

Community Cloud uses GitHub as its source. Once the repository and implementation are ready:

1. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) and connect the intended GitHub account/repository.
2. Select **Create app** and choose the repository and release branch.
3. Set the main file path to `app.py` at the repository root.
4. Choose an available app subdomain, for example `zomato-ai-recommender`; this name is illustrative and has not been reserved.
5. In **Advanced settings**, select Python 3.12 and paste the deployment secrets.
6. Deploy, inspect installation/startup logs, and resolve any dependency, artifact, or configuration failures.
7. Verify the resulting `https://<chosen-subdomain>.streamlit.app` URL and set the intended sharing/access settings.

These deployment inputs follow the official [Community Cloud deployment workflow](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy). No cloud deployment has been created by this plan.

## 8. Post-deployment acceptance and operation

Repeat the release checks on the hosted URL, including a fresh visit, successful AI search, relaxed search, and two independent sessions. Inspect logs for unhandled exceptions and confirm that secrets and full preference payloads are not logged.

Check the current Community Cloud resource guidance during deployment. Its published limits can change; the source download size alone does not establish peak memory usage. If memory is excessive, reduce loaded columns/copies and verify use of the compact artifact before considering another hosting plan. [Resource guidance](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)

Record the deployed URL, release commit, Python version, pinned dependency versions, artifact revision, and smoke-test outcome in the README or release notes. Do not record secret values.

For updates, push a tested commit to the configured branch. Community Cloud updates from GitHub and reinstalls dependencies when relevant files change. For rollback, revert the faulty release commit, keeping code and data schema compatible, then repeat a hosted smoke test. Restore secrets separately through app settings when configuration caused the failure. [Update behavior](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)

Deployment is complete only when the hosted app passes acceptance checks and the final URL is recorded.
