# StackSync Assessment — Python Code Execution Sandbox (Flask + React)

A small full‑stack project that safely executes user‑submitted Python snippets. The backend exposes a minimal API (Flask) that validates and runs code in a constrained environment (optionally via nsjail). The frontend (React + Vite + TypeScript) provides a simple UI to enter a script, run it, and view both the return value and captured stdout.

## 🚀 Live Demo

**Frontend**: [https://stacksync-assessment.vercel.app/](https://stacksync-assessment.vercel.app/)

---

## Features

- **Safe execution**: Requires a `main()` function, enforces size/time limits, blocks dangerous patterns.
- **Secure sandboxing**: Uses `nsjail` when built for cloud to chroot and restrict the runtime with no fallback modes.
- **Cloud-native**: Optimized for Cloud Run/gVisor environments with direct nsjail execution.
- **Batteries included**: Supports common libraries like `numpy` and `pandas` (see limits below).
- **Simple UI**: Web editor with example scripts and instant results.

---

## Architecture

- **Backend**: Flask app exposing REST endpoints. Runs scripts either directly (local/dev) or inside `nsjail` sandbox (`BUILD=cloud`).
  - Code: `backend/main.py`
  - Images: `backend/Dockerfile.local` (local/dev), `backend/Dockerfile.cloud` (cloud with nsjail)
  - Sandbox config: `backend/nsjail.cfg` (defines chroot environment and security policies)
- **Frontend**: React + Vite + TypeScript single‑page app.
  - Code: `frontend/src/`
  - Dev server: Vite on port 3000

Default ports:

- Backend: `8080`
- Frontend: `3000`

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm 9+
- Docker (optional)

---

## Quick start (local, no Docker)

### 1) Backend

```bash
# from project root
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# optional envs; defaults shown
export BUILD=local
export PORT=8080
export FLASK_DEBUG=true
export SCRIPT_TIMEOUT=10
export MAX_SCRIPT_SIZE=10000

python backend/main.py
# API: http://localhost:8080
```

Health check:

```bash
curl -s http://localhost:8080/health | jq
```

### 2) Frontend

```bash
cd frontend
npm install
# optionally configure API origin
echo "VITE_API_URL=http://localhost:8080" > .env.local
npm run dev
# UI: http://localhost:3000
```

---

## Docker

There are two Dockerfiles for the backend. Contexts differ between them.

### Local/dev image (no nsjail)

- Dockerfile: `backend/Dockerfile.local`
- Build context: project root (.)

```bash
# from project root
docker build -f backend/Dockerfile.local -t stacksync-backend:local .
docker run --rm -p 8080:8080 -e BUILD=local stacksync-backend:local
```

### Cloud image (with nsjail)

- Dockerfile: `backend/Dockerfile.cloud`
- Build context: backend directory (./backend)

```bash
# from project root
docker build -f backend/Dockerfile.cloud -t stacksync-backend:cloud ./backend
# runs gunicorn by default
docker run --rm -p 8080:8080 stacksync-backend:cloud
```

### docker-compose

A `docker-compose.yml` is present, but the frontend service expects a `frontend/Dockerfile.dev` which is not included. You can either:

- Run only the backend with the commands above and start the frontend via `npm run dev`, or
- Add/create a suitable `frontend/Dockerfile.dev` before using `docker compose up`.

---

## Environment variables

### Backend

- `BUILD` (local|cloud): toggles execution mode (`cloud` enables strict nsjail sandboxing, `local` uses direct execution). Default varies by image.
- `PORT` (default: 8080)
- `FLASK_DEBUG` (default: false)
- `SCRIPT_TIMEOUT` seconds (default: 10)
- `MAX_SCRIPT_SIZE` characters (default: 10000)

### Frontend

- `VITE_API_URL` (default: `http://localhost:8080`)

Create `frontend/.env.local` with:

```bash
VITE_API_URL=http://localhost:8080
```

---

## API

Base URL: `http://localhost:8080`

### GET `/`

Returns API metadata, environment, and usage info.

### GET `/health`

Liveness/health probe.

### POST `/execute`

Execute a Python script that defines a `main()` and returns a JSON‑serializable value.

Request:

```json
{
  "script": "def main():\n    return {\"message\": \"Hello, World!\"}"
}
```

Successful response:

```json
{
  "result": { "message": "Hello, World!" },
  "stdout": ""
}
```

On error (examples):

```json
{ "error": "Script must contain a main() function" }
```

```json
{ "error": "Dangerous operation detected: import os" }
```

---

## Validation, sandboxing, and limits

The backend enforces several safety checks before execution (`backend/main.py`):

- Requires a `main()` function; returns 400 if missing.
- Rejects scripts larger than `MAX_SCRIPT_SIZE`.
- Blocks dangerous patterns: `import os`, `import sys`, `import subprocess`, `import shutil`, `__import__`, `eval(`, `exec(`, `compile(`, `open(`, `file(`, `input(`, `raw_input(`, `exit(`, `quit(`, `reload(`).
- Execution timeout enforced by `SCRIPT_TIMEOUT`.

When `BUILD=cloud`, the app runs code via `nsjail` using `backend/nsjail.cfg`:

- **Secure isolation**: Scripts execute in a chroot environment at `/sandbox` with minimal libraries
- **Resource limits**: Restricted file descriptors, CPU, memory, and execution time
- **Cloud-compatible**: Configured for Cloud Run/gVisor environments with simplified security policies
- **No fallbacks**: Direct nsjail execution only - no fallback to unsandboxed execution for maximum security

Allowed libraries (typical usage): `numpy`, `pandas`, `json`, `math`, `random`, `datetime`.

---

## Frontend UI

- Configure the API base URL at the top of the page or via `VITE_API_URL`.
- Editor requires a valid `main()`.
- Shows both the returned JSON and captured `stdout`.
- Includes example scripts demonstrating math, stdout capture, `numpy`/`pandas`, and error handling.

---

## Project structure

```text
backend/
  Dockerfile.cloud
  Dockerfile.local
  main.py
  nsjail.cfg
  requirements.txt
frontend/
  src/
  package.json
  vite.config.ts
  README.md (template)
```

---

## Deployment notes

- The cloud image (`Dockerfile.cloud`) compiles and embeds `nsjail`, copies a minimal Python runtime into `/sandbox`, and runs via gunicorn.
- **Security-first**: No fallback execution modes - scripts run exclusively in nsjail sandbox when `BUILD=cloud`
- **Cloud Run ready**: Optimized for managed container environments with appropriate security restrictions
- You can adapt `backend/deploy-cloud.sh` or your platform's workflow (e.g., Cloud Run) to push and deploy the `:cloud` image.

Health probe example:

```bash
curl -f http://YOUR_SERVICE_URL/health
```

---

## Testing the flow end‑to‑end

1) Start backend (local or Docker) on `:8080`.
2) Start frontend (`npm run dev`) on `:3000`.
3) In the UI, paste a script like:

    ```python
    def main():
        print("hello from stdout")
        return {"ok": True}
    ```

4) Run and confirm you see `stdout` and the parsed JSON `result`.
