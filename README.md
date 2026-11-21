# Lyftr AI - LLM Chatbot with Key Failover and Response Caching

A resilient, production-ready full-stack AI chatbot built with **React**, **FastAPI**, **LiteLLM**, and **SQLite**. Features automatic multi-key fallback across LLM providers, exact per-request token usage tracking, response caching, and a failover test hook.

---

## 1. Live URLs

- **Frontend Application (Live UI):** `https://lyftr-ai-frontend.vercel.app` *(Placeholder - deploy URL)*
- **Backend API (Base URL):** `https://lyftr-ai-backend.onrender.com` *(Placeholder - deploy URL)*
- **Backend Health Check:** `https://lyftr-ai-backend.onrender.com/health`
- **Public GitHub Repository:** `https://github.com/SHANUTYAGI123/lytrAI`
- **Demo Video (2–3 minutes):** `https://youtu.be/<video_id>` *(Screen recording with voice explaining live endpoints, cache hit, and failover)*

> **Note on Deployment:** The backend has `ENABLE_FAILURE_SIMULATION=true` set, allowing verification of the failover hook in production. The backend allows CORS origins from the deployed frontend.

---

## 2. Run locally: with Docker and without

### A. Run with Docker (Recommended)

Prerequisites: [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)

1. **Clone the repository and prepare environment variables:**
   ```bash
   git clone https://github.com/<username>/lyftr-ai-gateway.git
   cd lyftr-ai-gateway
   cp .env.example .env
   ```

2. **Configure your API keys in `.env`:**
   ```env
   LLM_API_KEYS=your_first_gemini_or_openai_key,your_second_gemini_or_openai_key
   LLM_MODEL=gemini/gemini-2.0-flash
   ENABLE_FAILURE_SIMULATION=true
   ```

3. **Start the stack using `make up`:**
   ```bash
   make up
   ```
   - **Frontend UI:** [http://localhost:3000](http://localhost:3000)
   - **Backend API:** [http://localhost:8000](http://localhost:8000)
   - **API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - SQLite database is persisted under Docker named volume `lyftr_sqlite_data` mounted at `/data/app.db`.

4. **Stop the stack:**
   ```bash
   make down
   ```

---

### B. Run locally without Docker

Prerequisites: Python 3.10+ and Node.js 18+

#### 1. Start the Backend:
```bash
# In repo root
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# Run backend from the backend directory
cd backend
export DATABASE_URL="sqlite:///./data/app.db"
export LLM_API_KEYS="test-key-1,test-key-2"
export ENABLE_FAILURE_SIMULATION="true"
export ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Start the Frontend:
```bash
# In a new terminal
cd frontend
npm install
npm run dev -- --port 3000
```
Visit [http://localhost:3000](http://localhost:3000).

#### 3. Run Backend Test Suite:
```bash
# In repo root or backend folder
make test
# OR
cd backend && PYTHONPATH=. pytest -v
```

---

## 3. Design decisions: key fallback, caching, SQLite session storage

### A. Key Fallback Architecture
- **Key Pool Order:** API keys are supplied as a comma-separated list via `LLM_API_KEYS` and loaded into an ordered pool `[("key_1", key1), ("key_2", key2), ...]`.
- **Automatic Failover:** When a request is processed, the gateway attempts inference using `key_1`. If the key raises an error (HTTP 429 rate limit, quota exhaustion, or 5xx server errors), the gateway logs the exception, increments `fallback_attempts`, and automatically retries the request using the subsequent key in the pool (`key_2`, etc.).
- **Zero Broken Screens:** If every key fails, the endpoint cleanly returns an HTTP `503 Service Unavailable` with body `{"detail": "all providers unavailable"}`. The failed attempt is **never** added to the session history, ensuring database integrity.
- **Failover Simulation Hook (`X-Simulate-Failure`):** For on-demand demonstration without exhausting real quotas, the request header `X-Simulate-Failure` is parsed into key-status mappings (e.g. `key_1=429`, `key_1=500`, or `*=429`). When `ENABLE_FAILURE_SIMULATION=true`, the specified key simulates that error for that request only. When a simulation header is active, cache lookup is bypassed to ensure failover mechanics are tested deterministically.

### B. Response Caching (LiteLLM)
- **Cache Engine:** Utilizes LiteLLM's cache engine initialized via `litellm.enable_cache(type="local")` for low-latency in-memory response caching.
- **Cache Key Design:** The cache key is deterministically generated from `model + full message list sent to the LLM (effective system prompt + multi-turn history + new user message)`.
- **Accuracy Guarantee:**
  - Sending the identical first message in a new session returns `LLM_CACHE` on the second call.
  - Adding subsequent messages or changing the system prompt creates a different message list and cache key, ensuring that new prompts never return false cached hits.
  - Cache hits return identical reply text and preserved token usage, reporting `resolution_source: "LLM_CACHE"`, `key_id: null`, `fallback_attempts: 0`, and latency under 10ms.

### C. SQLite Session Storage
- **Zero External Dependencies:** Stored strictly in SQLite (no Redis, no PostgreSQL).
- **Persistent Storage:** Stored at the path defined by `DATABASE_URL` (e.g. `sqlite:////data/app.db`). In Docker, the path `/data` is backed by a named Docker volume (`lyftr_sqlite_data`), surviving container restarts.
- **Atomic Transactions:** Both user messages and assistant messages are committed in a single atomic transaction.
- **Data Model:**
  ```sql
  CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,       -- 'user' or 'assistant'
    content TEXT NOT NULL,
    metadata TEXT,            -- JSON string (assistant messages only)
    created_at TEXT NOT NULL  -- ISO-8601 UTC server timestamp
  );
  CREATE INDEX idx_messages_session_id ON messages (session_id);
  ```
- **Session History Retrieval:** `GET /sessions/{session_id}/messages` retrieves stored history ordered oldest-first, omitting the system prompt. If the session has no records, it returns HTTP 404 `{"detail": "session not found"}`.

---

## 4. Verification: how to see failover, cache hits and per-message token usage

You can verify all behavior either through the **Web UI** or via **curl**:

### A. Verify Cache Hit (`LIVE_INFERENCE` vs `LLM_CACHE`)

#### Via Web UI:
1. Open [http://localhost:3000](http://localhost:3000). A new session (e.g. `s-a1b2`) is created.
2. Send message: `"What is the capital of France?"`
   - UI shows badge: `LIVE_INFERENCE`
   - Key: `key_1`, Latency: e.g. `812 ms`, Tokens: input and output tokens shown.
3. Click **"New Chat"** to start a new session (e.g. `s-c3d4`).
4. Send identical message: `"What is the capital of France?"`
   - UI shows badge: `LLM_CACHE` (green lightning bolt)
   - Latency: `< 10 ms` (sub-millisecond in-memory cache)
   - Key: `null` (not shown)
   - Tokens: Identical input and output tokens as stored with the cache.

#### Via curl:
```bash
# 1. First request -> LIVE_INFERENCE
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "s-test-1", "message": "What is the capital of France?"}'

# Expected response:
# {"session_id":"s-test-1","reply":"...","metadata":{"resolution_source":"LIVE_INFERENCE","model":"gemini/gemini-2.0-flash","latency_ms":812,"input_tokens":...,"output_tokens":...,"key_id":"key_1","fallback_attempts":0}}

# 2. Identical request in new session -> LLM_CACHE
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "s-test-2", "message": "What is the capital of France?"}'

# Expected response:
# {"session_id":"s-test-2","reply":"...","metadata":{"resolution_source":"LLM_CACHE","model":"gemini/gemini-2.0-flash","latency_ms":2,"input_tokens":...,"output_tokens":...,"key_id":null,"fallback_attempts":0}}
```

---

### B. Verify Failover Hook (`X-Simulate-Failure`)

#### Via Web UI:
1. Click the **"Failover Test"** button in the header to open the simulation toolbar.
2. Select preset **"Key 1 Rate Limit (429)"** (which sets `X-Simulate-Failure: key_1=429`).
3. Send: `"Explain quantum computing."`
   - Notice the assistant reply metadata: `key_id` is **`key_2`** and `1 fallback attempt` is displayed!
4. Select preset **"All Keys Fail (*=429)"**.
5. Send: `"This should fail."`
   - The UI displays a readable error alert: `all providers unavailable (HTTP 503)`. No blank screen or crash.

#### Via curl:
```bash
# 1. Simulate key_1 rate limit (429) -> falls back to key_2
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id": "s-failover-1", "message": "Explain quantum computing."}'

# Expected response:
# {"session_id":"s-failover-1",...,"metadata":{...,"key_id":"key_2","fallback_attempts":1}}

# 2. Simulate all keys failing (*=429) -> returns 503
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id": "s-failover-2", "message": "Fail all."}'

# Expected response:
# HTTP 503: {"detail": "all providers unavailable"}

# 3. Verify session was NOT saved to SQLite:
curl http://localhost:8000/sessions/s-failover-2/messages
# Expected response:
# HTTP 404: {"detail": "session not found"}
```

---

### C. Verify Per-Message Token Usage & Multi-turn History

```bash
# Get stored history for session s-test-1:
curl http://localhost:8000/sessions/s-test-1/messages

# Expected response:
# {
#   "session_id": "s-test-1",
#   "messages": [
#     { "role": "user", "content": "What is the capital of France?" },
#     {
#       "role": "assistant",
#       "content": "...",
#       "metadata": { "resolution_source": "LIVE_INFERENCE", "input_tokens": 42, "output_tokens": 9 }
#     }
#   ]
# }
```

---

## 5. Setup Used: your editor and AI tools

- **Editor & IDE:** VS Code / Antigravity IDE with TypeScript and Python LSP.
- **AI Tooling & Coding Assistants:** Used for architectural scaffolding, Dockerfile optimization, and comprehensive test suite authoring.
- **Backend Framework:** FastAPI with Starlette, Pydantic v2 settings, and aiosqlite for non-blocking asynchronous SQLite I/O.
- **LLM Gateway:** LiteLLM (`litellm.completion`, `litellm.enable_cache`, and `litellm.token_counter`).
- **Frontend Framework:** React 19 + TypeScript + Vite + Tailwind CSS v4 + Lucide React icons.

---

## 6. Bonus features (if any): what you added beyond the requirements and why

1. **Interactive Failover Simulation Toolbar in UI:**
   - Instead of forcing evaluators to open curl or Postman to test `X-Simulate-Failure`, the web interface includes a toggleable simulation toolbar with presets for `key_1=429`, `key_1=500`, and `*=429`, as well as a custom header field. This enables 1-click live failover demonstrations in demo videos.
2. **Backend Health Check Pulse & Key Pool Indicator:**
   - Real-time indicator in the navigation bar querying `GET /health`, showing live status (`Pool: 2 keys | Cache: ON`) with pulse feedback.
3. **Session Management Controls:**
   - Visual session ID pill with instant clipboard copy and a "New Chat" button to seamlessly spin up new multi-turn conversations without manual URL manipulation.
4. **Resilient Offline / Mock Fallback:**
   - The gateway gracefully detects placeholder keys (e.g. `test-key-*`) and produces deterministic mock completions with accurate token counts, allowing complete end-to-end local testing and CI/CD testing without spending live API credits.
5. **Session System Prompt Drawer (`system-prompt-input`):**
   - Full implementation of the optional system prompt feature, letting users customize the assistant persona per session while keeping the SQLite messages history clean of system messages.
