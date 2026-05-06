"""Client for the QC_model_store LLM endpoint (Open WebUI).

The server at the configured base_url exposes an OpenAI-compatible API.

Authentication
--------------
Two options:

1. **API key** – pass ``api_key`` directly (preferred for scripts):
   ```python
   client = QCModelStoreClient(api_key="sk-...")
   ```

2. **Email / password** – let the client exchange credentials for a JWT:
   ```python
   client = QCModelStoreClient()
   client.login("you@example.com", "yourpassword")
   ```

Quick start
-----------
```python
client = QCModelStoreClient(api_key="sk-...")
print(client.list_models())
response = client.chat("Describe what MRIQC measures in one sentence.")
print(response)
```
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Generator, Iterator

import requests

_AGENT_DIR = Path(__file__).parent
_CONFIG_PATH = _AGENT_DIR / "llm_config.json"
_LOCAL_CONFIG_PATH = _AGENT_DIR / "llm_config.local.json"


def _load_config() -> dict:
    """Merge llm_config.json with optional llm_config.local.json.

    llm_config.local.json is gitignored and may contain secrets (e.g. api_key).
    Values in the local file take precedence over the base config.
    """
    with open(_CONFIG_PATH) as f:
        cfg = json.load(f)
    if _LOCAL_CONFIG_PATH.exists():
        with open(_LOCAL_CONFIG_PATH) as f:
            local = json.load(f)
        # Strip comment key and merge non-empty values only
        for k, v in local.items():
            if not k.startswith("_") and v not in ("", None):
                cfg[k] = v
    return cfg


_CFG = _load_config()
BASE_URL: str = _CFG["base_url"]
DEFAULT_MODEL: str = _CFG["default_model"]


class QCModelStoreClient:
    """Minimal client for the QC_model_store Open WebUI LLM endpoint.

    Parameters
    ----------
    api_key:
        Bearer token / API key.  Falls back to the environment variable
        ``QC_MODEL_STORE_API_KEY`` if not provided.
    base_url:
        Override the server URL (useful for testing against a local instance).
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        timeout: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout if timeout is not None else _CFG.get("timeout", 120)
        self._token: str | None = (
            api_key
            or os.environ.get("QC_MODEL_STORE_API_KEY")
            or _CFG.get("api_key") or None
        )
        self._endpoints: dict = _CFG.get("endpoints", {})

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def login(self, email: str, password: str) -> str:
        """Exchange email/password for a JWT and store it internally.

        Returns
        -------
        str
            The token (also accessible as ``client.token``).
        """
        resp = requests.post(
            self.base_url + self._endpoints["signin"],
            json={"email": email, "password": password},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["token"]
        return self._token

    @property
    def token(self) -> str | None:
        return self._token

    def _auth_headers(self) -> dict[str, str]:
        if not self._token:
            raise RuntimeError(
                "No API key or token set.  Call login() first, pass api_key= "
                "to the constructor, or set QC_MODEL_STORE_API_KEY."
            )
        return {"Authorization": f"Bearer {self._token}"}

    # ------------------------------------------------------------------
    # Model discovery
    # ------------------------------------------------------------------

    def list_models(self) -> list[str]:
        """Return a list of model IDs available on the server."""
        resp = requests.get(
            self.base_url + self._endpoints["models"],
            headers=self._auth_headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        # Open WebUI returns {"data": [...]} (OpenAI schema)
        models = data.get("data", data) if isinstance(data, dict) else data
        return [m.get("id", m.get("name", str(m))) for m in models]

    # ------------------------------------------------------------------
    # Chat completions
    # ------------------------------------------------------------------

    def chat(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> str | Iterator[str]:
        """Send a single user prompt and return the assistant reply.

        Parameters
        ----------
        prompt:
            The user message.
        model:
            Model ID to use.  Defaults to ``gemma3:27b``.
        system:
            Optional system prompt prepended before the user message.
        temperature:
            Sampling temperature (0 = deterministic, 1 = creative).
        max_tokens:
            Maximum tokens in the response.  ``None`` uses the model default.
        stream:
            If ``True`` returns a generator that yields text chunks as they
            arrive (server-sent events).

        Returns
        -------
        str
            Full assistant reply (when ``stream=False``).
        Iterator[str]
            Generator of text chunks (when ``stream=True``).
        """
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        resp = requests.post(
            self.base_url + self._endpoints["chat_completions"],
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
            stream=stream,
        )
        resp.raise_for_status()

        if stream:
            return self._iter_stream(resp)
        return resp.json()["choices"][0]["message"]["content"]

    def chat_messages(
        self,
        messages: list[dict],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> str | Iterator[str]:
        """Send a full messages list (role/content dicts) to the API.

        Useful for multi-turn conversations where you manage the history
        yourself.
        """
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        resp = requests.post(
            self.base_url + self._endpoints["chat_completions"],
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
            stream=stream,
        )
        resp.raise_for_status()

        if stream:
            return self._iter_stream(resp)
        return resp.json()["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _iter_stream(response: requests.Response) -> Generator[str, None, None]:
        """Parse server-sent events and yield text deltas."""
        for raw_line in response.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                delta = chunk["choices"][0].get("delta", {})
                text = delta.get("content")
                if text:
                    yield text
            except (json.JSONDecodeError, KeyError, IndexError):
                continue


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Send a prompt to the QC_model_store LLM endpoint.",
    )
    parser.add_argument("prompt", nargs="?", help="Prompt text (or omit to read from stdin)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--system", default=None, help="System prompt")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--stream", action="store_true", help="Stream response tokens")
    parser.add_argument("--list-models", action="store_true", help="List available models and exit")
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key (falls back to QC_MODEL_STORE_API_KEY env var)",
    )
    parser.add_argument("--email", default=None, help="Login email (alternative to API key)")
    parser.add_argument("--password", default=None, help="Login password")
    args = parser.parse_args()

    client = QCModelStoreClient(api_key=args.api_key)

    if args.email and args.password:
        client.login(args.email, args.password)

    if args.list_models:
        for m in client.list_models():
            print(m)
        return

    import sys
    prompt = args.prompt or sys.stdin.read()
    if not prompt.strip():
        parser.error("Provide a prompt as an argument or via stdin.")

    if args.stream:
        for chunk in client.chat(
            prompt,
            model=args.model,
            system=args.system,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            stream=True,
        ):
            print(chunk, end="", flush=True)
        print()
    else:
        reply = client.chat(
            prompt,
            model=args.model,
            system=args.system,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        print(reply)


if __name__ == "__main__":
    _cli()
