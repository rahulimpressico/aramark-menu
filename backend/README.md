# Menu Analysis Backend

FastAPI app and menu analyzer experiments.

## Dependency management (uv)

This project uses [uv](https://docs.astral.sh/uv/) for installs and locking.

- **Install uv**: <https://docs.astral.sh/uv/getting-started/installation/>
- **Sync dependencies** (create/update `.venv`, install packages):
  ```bash
  uv sync
  ```
- **Include experiments** (deepagents, langchain, langgraph, Google Gemini):
  ```bash
  uv sync --extra experiments
  ```
  For experiments, set **`GOOGLE_API_KEY`** (or `GEMINI_API_KEY`) for the Gemini Developer API. The agent uses `google_genai:gemini-2.0-flash` by default; for other Gemini models use the `google_genai:` prefix (e.g. `google_genai:gemini-1.5-pro`) so LangChain uses the correct package instead of Vertex AI.
- **Tracing (optional)**: To see tool and LLM traces in [Langfuse](https://langfuse.com/docs/observability/get-started), set **`LANGFUSE_SECRET_KEY`**, **`LANGFUSE_PUBLIC_KEY`**, and optionally **`LANGFUSE_BASE_URL`** (default `https://cloud.langfuse.com`). With these set, the menu analyzer will send traces to Langfuse so you can see which tools ran and when.
- **Reports**: Running the menu analyzer writes the executive summary markdown to `backend/experiments/reports/menu_report_<timestamp>.md` and `menu_report_latest.md`.
- **Run the API**:
  ```bash
  uv run uvicorn app.main:app --reload
  ```
- **Regenerate lockfile** after editing `pyproject.toml`:
  ```bash
  uv lock
  ```

Python version is pinned in `.python-version` (3.12).
