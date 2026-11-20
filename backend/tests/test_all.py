import os
import pytest
from httpx import AsyncClient, ASGITransport

os.environ["DATABASE_URL"] = "sqlite:///./test_data/test_app.db"
os.environ["LLM_API_KEYS"] = "test-key-1,test-key-2"
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"
os.environ["LLM_MODEL"] = "gemini/gemini-2.0-flash"

from app.main import app
from app.database import init_db


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield
    db_file = "./test_data/test_app.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except OSError:
            pass


@pytest.mark.anyio
async def test_health_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["keys_configured"] >= 2
        assert data["cache_enabled"] is True


@pytest.mark.anyio
async def test_validation_errors():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Missing message
        r1 = await ac.post("/chat", json={"session_id": "s-1"})
        assert r1.status_code == 422
        assert "detail" in r1.json()

        # Empty message after trimming
        r2 = await ac.post("/chat", json={"session_id": "s-1", "message": "   "})
        assert r2.status_code == 422
        assert "detail" in r2.json()

        # Missing session_id
        r3 = await ac.post("/chat", json={"message": "hello"})
        assert r3.status_code == 422

        # Message over 4000 characters
        r4 = await ac.post("/chat", json={"session_id": "s-1", "message": "a" * 4001})
        assert r4.status_code == 422

        # Malformed JSON
        r5 = await ac.post(
            "/chat",
            content="invalid json text",
            headers={"Content-Type": "application/json"}
        )
        assert r5.status_code == 422

        # Unknown session returns 404
        r6 = await ac.get("/sessions/s-1/messages")
        assert r6.status_code == 404
        assert r6.json()["detail"] == "session not found"


@pytest.mark.anyio
async def test_caching_and_history():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # First request in session A -> LIVE_INFERENCE
        res1 = await ac.post(
            "/chat",
            json={"session_id": "s-cache-1", "message": "What is the capital of France?"}
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["session_id"] == "s-cache-1"
        assert data1["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert data1["metadata"]["key_id"] == "key_1"
        assert data1["metadata"]["fallback_attempts"] == 0
        assert data1["metadata"]["input_tokens"] > 0
        assert data1["metadata"]["output_tokens"] > 0

        # Identical first request in a new session B -> LLM_CACHE
        res2 = await ac.post(
            "/chat",
            json={"session_id": "s-cache-2", "message": "What is the capital of France?"}
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["session_id"] == "s-cache-2"
        assert data2["metadata"]["resolution_source"] == "LLM_CACHE"
        assert data2["metadata"]["key_id"] is None
        assert data2["metadata"]["fallback_attempts"] == 0
        assert data2["reply"] == data1["reply"]
        assert data2["metadata"]["input_tokens"] == data1["metadata"]["input_tokens"]
        assert data2["metadata"]["output_tokens"] == data1["metadata"]["output_tokens"]
        assert data2["metadata"]["latency_ms"] <= data1["metadata"]["latency_ms"]

        # Different message in session B -> LIVE_INFERENCE
        res3 = await ac.post(
            "/chat",
            json={"session_id": "s-cache-2", "message": "Tell me a joke."}
        )
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["metadata"]["resolution_source"] == "LIVE_INFERENCE"

        # Check stored history for s-cache-2
        hist = await ac.get("/sessions/s-cache-2/messages")
        assert hist.status_code == 200
        hdata = hist.json()
        assert hdata["session_id"] == "s-cache-2"
        assert len(hdata["messages"]) == 4  # 2 user messages + 2 assistant messages
        assert hdata["messages"][0]["role"] == "user"
        assert hdata["messages"][0]["content"] == "What is the capital of France?"
        assert hdata["messages"][1]["role"] == "assistant"
        assert hdata["messages"][1]["metadata"]["resolution_source"] == "LLM_CACHE"
        assert hdata["messages"][2]["role"] == "user"
        assert hdata["messages"][2]["content"] == "Tell me a joke."
        assert hdata["messages"][3]["role"] == "assistant"
        assert hdata["messages"][3]["metadata"]["resolution_source"] == "LIVE_INFERENCE"


@pytest.mark.anyio
async def test_failover_hook():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Simulate key_1=429 -> should fall back to key_2
        res1 = await ac.post(
            "/chat",
            json={"session_id": "s-failover-1", "message": "Explain quantum computing."},
            headers={"X-Simulate-Failure": "key_1=429"}
        )
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["metadata"]["key_id"] == "key_2"
        assert d1["metadata"]["fallback_attempts"] == 1
        assert d1["metadata"]["resolution_source"] == "LIVE_INFERENCE"

        # Simulate key_1=500 -> should fall back to key_2
        res2 = await ac.post(
            "/chat",
            json={"session_id": "s-failover-2", "message": "Explain photosynthesis."},
            headers={"X-Simulate-Failure": "key_1=500"}
        )
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["metadata"]["key_id"] == "key_2"
        assert d2["metadata"]["fallback_attempts"] == 1

        # Simulate key_1=502, key_1=503
        res2b = await ac.post(
            "/chat",
            json={"session_id": "s-failover-2b", "message": "Explain cellular respiration."},
            headers={"X-Simulate-Failure": "key_1=502"}
        )
        assert res2b.status_code == 200
        assert res2b.json()["metadata"]["key_id"] == "key_2"

        # Simulate *=429 -> all keys fail -> 503 {"detail": "all providers unavailable"}
        res3 = await ac.post(
            "/chat",
            json={"session_id": "s-failover-3", "message": "This should fail completely."},
            headers={"X-Simulate-Failure": "*=429"}
        )
        assert res3.status_code == 503
        assert res3.json() == {"detail": "all providers unavailable"}

        # Verify nothing was added to SQLite for s-failover-3
        res4 = await ac.get("/sessions/s-failover-3/messages")
        assert res4.status_code == 404
        assert res4.json() == {"detail": "session not found"}


@pytest.mark.anyio
async def test_system_prompt_and_tokens():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Test custom system prompt
        res1 = await ac.post(
            "/chat",
            json={
                "session_id": "s-sys-1",
                "message": "Hello world",
                "system_prompt": "You are a pirate AI."
            }
        )
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        pirate_tokens = d1["metadata"]["input_tokens"]

        # Different system prompt should NOT hit cache even if message is identical
        res2 = await ac.post(
            "/chat",
            json={
                "session_id": "s-sys-2",
                "message": "Hello world",
                "system_prompt": "You are a serious medical doctor."
            }
        )
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["metadata"]["resolution_source"] == "LIVE_INFERENCE"

        # Identical system prompt and message should hit cache
        res3 = await ac.post(
            "/chat",
            json={
                "session_id": "s-sys-3",
                "message": "Hello world",
                "system_prompt": "You are a pirate AI."
            }
        )
        assert res3.status_code == 200
        d3 = res3.json()
        assert d3["metadata"]["resolution_source"] == "LLM_CACHE"
        assert d3["metadata"]["input_tokens"] == pirate_tokens
