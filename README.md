# Ecommerce Project

A basic ecommerce stack: **FastAPI** backend and **React** (TypeScript + Vite) frontend, ready to run locally or with Docker Compose.

## Structure

- **`backend/`** — FastAPI app (`app/`, `app/routers/`, `app/dependencies.py`, Pydantic models, `main.py`). Health/root endpoints at `/` and `/health`.
- **`frontend/`** — React + TypeScript + Vite app with `src/components/`, `src/pages/`, `src/features/`, `src/hooks/`, `src/types/`.

## Run without Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API: <http://localhost:8000>  
Docs: <http://localhost:8000/docs>

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: <http://localhost:5173>

The frontend uses `/api` as the API base (proxied to `http://localhost:8000` in dev). To point at another backend, set `VITE_API_URL` (e.g. `VITE_API_URL=http://localhost:8000`).

## Run with Docker Compose

From the project root:

```bash
docker compose up --build
```

- **Backend**: <http://localhost:8000>
- **Frontend**: <http://localhost:5173>

The frontend dev server proxies `/api` to the backend service using `VITE_PROXY_TARGET=http://backend:8000` (set in `docker-compose.yml`). No extra env vars are required for the default setup.

**Note:** The frontend container runs `npm install` on every start so that `node_modules` inside the container stays correct when using the bind mount. The first time you run `docker compose up`, allow a minute for the dev server to become available at http://localhost:5173.

## Env vars (optional)

| Where        | Variable            | Purpose                                      |
|-------------|---------------------|----------------------------------------------|
| Frontend    | `VITE_API_URL`      | API base URL (default: `/api` for proxy)     |
| Frontend (Docker) | `VITE_PROXY_TARGET` | Proxy target for `/api` (default in compose: `http://backend:8000`) |
