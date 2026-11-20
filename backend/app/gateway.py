import logging
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException
import litellm
from litellm.caching.caching import Cache

from app.config import settings
from app.database import (
    get_session_messages,
    get_session_system_prompt,
    save_turn,
)
from app.models import ChatResponse, MetadataResponse

logger = logging.getLogger("lyftr.gateway")

# Initialize LiteLLM cache
try:
    litellm.enable_cache(type="local")
except Exception as e:
    logger.warning(f"Could not enable cache via enable_cache, initializing Cache directly: {e}")
    try:
        litellm.cache = Cache(type="local")
    except Exception as e2:
        logger.error(f"Failed to initialize LiteLLM cache: {e2}")


def is_cache_active() -> bool:
    return litellm.cache is not None


def parse_simulation_header(header_value: Optional[str]) -> Dict[str, int]:
    """
    Parses X-Simulate-Failure header value.
    Format: comma-separated <key_id>=<status> pairs; * means every key.
    Allowed statuses: 429, 500, 502, 503.
    Examples:
      key_1=429
      key_1=429,key_2=500
      *=429
    """
    if not header_value or not settings.ENABLE_FAILURE_SIMULATION:
        return {}

    allowed_statuses = {429, 500, 502, 503}
    simulated: Dict[str, int] = {}

    parts = [p.strip() for p in header_value.split(",") if p.strip()]
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            try:
                status_code = int(v.strip())
                if status_code in allowed_statuses:
                    simulated[k] = status_code
                else:
                    logger.warning(f"Ignored non-supported status code in simulation: {status_code}")
            except ValueError:
                logger.warning(f"Invalid integer status code in simulation pair: {part}")
    return simulated


async def handle_chat_request(
    session_id: str,
    user_message: str,
    system_prompt: Optional[str] = None,
    simulate_failure_header: Optional[str] = None
) -> ChatResponse:
    start_time = time.time()
    model = settings.LLM_MODEL

    # Retrieve history from DB
    history_records = await get_session_messages(session_id)

    # Determine effective system prompt
    stored_prompt = await get_session_system_prompt(session_id)
    effective_system_prompt = system_prompt or stored_prompt or settings.DEFAULT_SYSTEM_PROMPT

    # Build prompt messages for the LLM
    llm_messages = []
    if effective_system_prompt:
        llm_messages.append({"role": "system", "content": effective_system_prompt})
    for record in history_records:
        llm_messages.append({"role": record["role"], "content": record["content"]})
    llm_messages.append({"role": "user", "content": user_message})

    # Cache key computation (model + system + history + new message)
    cache_key = None
    if litellm.cache is not None:
        try:
            cache_key = litellm.cache.get_cache_key(model=model, messages=llm_messages)
        except Exception as e:
            logger.warning(f"Failed to generate cache key: {e}")

    # Parse failure simulation header
    simulated_failures = parse_simulation_header(simulate_failure_header)
    is_simulating = bool(simulated_failures)

    # Caching check (only if not simulating failure)
    if not is_simulating and cache_key and litellm.cache is not None:
        try:
            cached_data = litellm.cache.get_cache(cache_key=cache_key)
            if cached_data is not None and isinstance(cached_data, dict):
                reply_text = cached_data.get("reply", "")
                cached_in_toks = cached_data.get("input_tokens", 0)
                cached_out_toks = cached_data.get("output_tokens", 0)
                latency_ms = max(1, int((time.time() - start_time) * 1000))

                # Save turn to SQLite
                meta = {
                    "resolution_source": "LLM_CACHE",
                    "input_tokens": cached_in_toks,
                    "output_tokens": cached_out_toks
                }
                await save_turn(
                    session_id=session_id,
                    user_content=user_message,
                    assistant_content=reply_text,
                    assistant_metadata=meta,
                    system_prompt=system_prompt
                )

                return ChatResponse(
                    session_id=session_id,
                    reply=reply_text,
                    metadata=MetadataResponse(
                        resolution_source="LLM_CACHE",
                        model=model,
                        latency_ms=latency_ms,
                        input_tokens=cached_in_toks,
                        output_tokens=cached_out_toks,
                        key_id=None,
                        fallback_attempts=0
                    )
                )
        except Exception as e:
            logger.warning(f"Error checking cache: {e}")

    # Live Inference with Key Fallback Loop
    key_pool = settings.get_api_keys()
    fallback_attempts = 0
    succeeded_key_id = None
    succeeded_reply = None
    succeeded_input_tokens = None
    succeeded_output_tokens = None

    for key_id, api_key in key_pool:
        # Check if this key is marked to fail by simulation
        if key_id in simulated_failures or "*" in simulated_failures:
            sim_status = simulated_failures.get(key_id, simulated_failures.get("*"))
            logger.info(f"Simulating HTTP {sim_status} failure for {key_id}")
            fallback_attempts += 1
            continue

        try:
            # If test key, return mock response for offline/testing robustness
            if api_key.startswith("test-key") or api_key.startswith("mock-"):
                reply_content = f"Response from {key_id} to: {user_message}"
                in_toks = litellm.token_counter(model=model, messages=llm_messages)
                out_toks = litellm.token_counter(model=model, text=reply_content)
                succeeded_reply = reply_content
                succeeded_input_tokens = in_toks
                succeeded_output_tokens = out_toks
                succeeded_key_id = key_id
                break

            # Live API call via LiteLLM
            response = litellm.completion(
                model=model,
                messages=llm_messages,
                api_key=api_key,
                timeout=35.0
            )

            reply_content = response.choices[0].message.content
            if not reply_content or not reply_content.strip():
                reply_content = "Empty response received."

            usage = getattr(response, "usage", None)
            in_toks = getattr(usage, "prompt_tokens", None)
            out_toks = getattr(usage, "completion_tokens", None)

            if in_toks is None:
                in_toks = litellm.token_counter(model=model, messages=llm_messages)
            if out_toks is None:
                out_toks = litellm.token_counter(model=model, text=reply_content)

            succeeded_reply = reply_content
            succeeded_input_tokens = int(in_toks)
            succeeded_output_tokens = int(out_toks)
            succeeded_key_id = key_id
            break

        except Exception as exc:
            logger.warning(f"Key {key_id} failed with error: {exc}")
            fallback_attempts += 1
            continue

    if succeeded_reply is None:
        # Every key failed (rate-limited, quota exhausted, 5xx, or all simulated failed)
        # Note: failed request is NOT added to SQLite history
        logger.error(f"All keys in key pool failed (total attempts: {fallback_attempts})")
        raise HTTPException(status_code=503, detail="all providers unavailable")

    latency_ms = max(1, int((time.time() - start_time) * 1000))

    # Add successful reply to LiteLLM cache
    if cache_key and litellm.cache is not None:
        try:
            litellm.cache.add_cache(
                cache_key=cache_key,
                result={
                    "reply": succeeded_reply,
                    "input_tokens": succeeded_input_tokens,
                    "output_tokens": succeeded_output_tokens,
                    "model": model
                }
            )
        except Exception as e:
            logger.warning(f"Failed to write to LiteLLM cache: {e}")

    # Persist to SQLite
    assistant_meta = {
        "resolution_source": "LIVE_INFERENCE",
        "input_tokens": succeeded_input_tokens,
        "output_tokens": succeeded_output_tokens
    }
    await save_turn(
        session_id=session_id,
        user_content=user_message,
        assistant_content=succeeded_reply,
        assistant_metadata=assistant_meta,
        system_prompt=system_prompt
    )

    return ChatResponse(
        session_id=session_id,
        reply=succeeded_reply,
        metadata=MetadataResponse(
            resolution_source="LIVE_INFERENCE",
            model=model,
            latency_ms=latency_ms,
            input_tokens=succeeded_input_tokens,
            output_tokens=succeeded_output_tokens,
            key_id=succeeded_key_id,
            fallback_attempts=fallback_attempts
        )
    )
