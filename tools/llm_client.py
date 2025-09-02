from dotenv import load_dotenv
import os

load_dotenv()

# Simple lazy-initialized GenAI client wrapper. Reads GEMINI_API_KEY from env.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_client = None


def get_client():
    """Return a singleton genai.Client configured from environment.

    This lazily imports the GenAI SDK so importing this module doesn't fail when
    the SDK is not installed. Callers should handle ModuleNotFoundError or
    RuntimeError if the SDK / API key is missing.
    """
    global _client
    if _client is not None:
        return _client

    try:
        # Lazy import so importing this module is safe in environments where the SDK
        # isn't yet installed.
        from google import genai
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "GenAI SDK not installed. Install with: pip install google-genai"
        ) from e

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment")

    _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def generate_content(model: str, contents, config: dict | None = None, retries: int = 3, backoff: float = 1.0):
    """Call client.models.generate_content with basic retry/backoff for transient errors.

    Returns the SDK response object or raises the last exception.
    """
    import time

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            client = get_client()
            if config:
                return client.models.generate_content(model=model, contents=contents, config=config)
            return client.models.generate_content(model=model, contents=contents)
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            # Retry on common transient conditions
            if any(tok in msg for tok in ("503", "unavailable", "rate limit", "rate_limit", "overloaded", "timeout")) and attempt < retries:
                sleep_for = backoff * (2 ** (attempt - 1))
                time.sleep(sleep_for)
                continue
            # Not a transient error or max attempts reached
            raise

    # If loop completes without returning, raise last exception
    if last_exc:
        raise last_exc
