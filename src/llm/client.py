"""
LLM client for the Zomato AI Recommender.

Uses the Groq API (OpenAI-compatible SDK) for ultra-fast LLM inference.
Dispatches on the LLM_PROVIDER environment variable (default: groq).
Implements exponential-backoff retry and a hard 15-second timeout.
"""

import os
import time
import threading
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Raised when the LLM call fails after all retries."""


class LLMTimeoutError(LLMError):
    """Raised when the LLM call exceeds the timeout threshold (15 s)."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_RETRY_WAITS = [2, 4, 8]       # seconds between attempts
_TIMEOUT_SECONDS = 15
_DEFAULT_PROVIDER = "groq"
_DEFAULT_TEMPERATURE = 0.3
_DEFAULT_MAX_TOKENS = 4096
_GROQ_MODEL = "openai/gpt-oss-120b"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Call the configured LLM provider and return the raw response text.

    Reads LLM_PROVIDER from the environment (default: "groq").
    Retries up to 3 times on rate-limit errors with exponential backoff (2s, 4s, 8s).
    Raises LLMTimeoutError if the call takes longer than 15 seconds.
    Raises LLMError after all retries are exhausted.

    Args:
        system_prompt: Static system/instruction prompt.
        user_prompt:   Dynamic user prompt containing preferences + candidates.

    Returns:
        Raw response string from the LLM (expected to be JSON).

    Raises:
        LLMTimeoutError: Call took longer than 15 seconds.
        LLMError:        All retries exhausted, missing API key, or unknown provider.
    """
    provider = os.getenv("LLM_PROVIDER", _DEFAULT_PROVIDER).lower().strip()

    _assert_api_key(provider)

    if provider == "groq":
        caller = lambda: _call_groq(system_prompt, user_prompt)
    else:
        raise LLMError(
            f"Unknown LLM_PROVIDER '{provider}'. Currently supported: 'groq'."
        )

    return _with_retry(_with_timeout(caller))


# ---------------------------------------------------------------------------
# Private — provider implementation
# ---------------------------------------------------------------------------

def _call_groq(system_prompt: str, user_prompt: str) -> str:
    """
    Call the Groq API using the groq SDK (OpenAI-compatible interface).

    Model: openai/gpt-oss-120b
        — Fast, capable, and available on Groq's free tier.

    Args:
        system_prompt: System message content.
        user_prompt:   User message content.

    Returns:
        Raw response text from Groq.
    """
    from groq import Groq  # lazy import — only when needed

    client = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=_TIMEOUT_SECONDS, max_retries=0)
    model = os.getenv("GROQ_MODEL", _GROQ_MODEL)
    options = {"reasoning_effort": "low"} if model.startswith("openai/gpt-oss-") else {}

    response = client.chat.completions.create(
        model=model,
        temperature=float(os.getenv("LLM_TEMPERATURE", _DEFAULT_TEMPERATURE)),
        max_tokens=_DEFAULT_MAX_TOKENS,
        response_format={"type": "json_object"},
        **options,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Private — retry and timeout wrappers
# ---------------------------------------------------------------------------

def _with_timeout(fn):
    """
    Wrap a zero-argument callable so it raises LLMTimeoutError if it
    does not return within _TIMEOUT_SECONDS seconds.

    Uses a background thread so it works on all platforms (including macOS,
    where signal.alarm is unavailable on non-main threads).

    Args:
        fn: Zero-argument callable to execute.

    Returns:
        A new zero-argument callable that enforces the timeout.
    """
    def wrapper():
        result = [None]
        error  = [None]

        def target():
            try:
                result[0] = fn()
            except Exception as exc:
                error[0] = exc

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=_TIMEOUT_SECONDS)

        if thread.is_alive():
            raise LLMTimeoutError(
                f"LLM call timed out after {_TIMEOUT_SECONDS} seconds."
            )
        if error[0] is not None:
            raise error[0]
        return result[0]

    return wrapper


def _with_retry(fn, max_attempts: int = _MAX_RETRIES):
    """
    Retry a zero-argument callable on rate-limit or transient errors.

    Waits _RETRY_WAITS[attempt] seconds between attempts (2 s, 4 s, 8 s).
    Passes through LLMTimeoutError immediately — no retry on timeout.
    Raises LLMError after all attempts are exhausted.

    Args:
        fn:           Zero-argument callable (the API call, pre-wrapped with timeout).
        max_attempts: Maximum number of attempts (default: 3).

    Returns:
        Return value of fn() on success.

    Raises:
        LLMTimeoutError: If fn() raises LLMTimeoutError.
        LLMError:        If all attempts fail.
    """
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except LLMTimeoutError:
            raise  # never retry a timeout
        except Exception as exc:
            last_exc = exc
            exc_name = type(exc).__name__
            is_rate_limit = (
                "rate" in str(exc).lower()
                or "429" in str(exc)
                or "quota" in str(exc).lower()
                or "RateLimitError" in exc_name
                or "ResourceExhausted" in exc_name
            )
            wait = _RETRY_WAITS[attempt] if attempt < len(_RETRY_WAITS) else _RETRY_WAITS[-1]

            if attempt < max_attempts - 1:
                reason = "rate limit" if is_rate_limit else exc_name
                print(
                    f"   ⚠️  LLM call failed ({reason}). "
                    f"Retry {attempt + 1}/{max_attempts - 1} in {wait}s..."
                )
                time.sleep(wait)
            else:
                print(f"   ❌ LLM call failed after {max_attempts} attempts: {exc}")

    raise LLMError(
        f"LLM call failed after {max_attempts} attempts. "
        f"Last error: {type(last_exc).__name__}: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Private — startup key validation
# ---------------------------------------------------------------------------

def _assert_api_key(provider: str) -> None:
    """
    Check that the required API key environment variable is set.

    Args:
        provider: LLM provider name (e.g. "groq").

    Raises:
        LLMError: If the required key is missing or empty.
    """
    key_map = {
        "groq": ("GROQ_API_KEY", "https://console.groq.com/keys"),
    }
    if provider not in key_map:
        return  # unknown provider — let _call_* handle it
    env_var, url = key_map[provider]
    key = os.getenv(env_var, "").strip()
    if not key:
        raise LLMError(
            f"❌ {env_var} is not set.\n"
            f"   Add it to your .env file: {env_var}=your_key_here\n"
            f"   Get a free key at: {url}"
        )
