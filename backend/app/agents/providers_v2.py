"""LLM providers — real implementations for Ollama nodes and Open WebUI cluster.

Three providers:
- OllamaProvider: Direct calls to Ollama on Wile/Roadrunner via Tailscale
- OpenWebUIProvider: Calls to the Open WebUI cluster (OpenAI-compatible)
- EmbeddingProvider: Embedding generation via Ollama /api/embeddings
"""

import asyncio
import json
import logging
import time
from typing import AsyncIterator

import httpx

from app.config import settings
from .registry import ModelEntry, Node

logger = logging.getLogger(__name__)

# Shared HTTP client with reasonable timeouts
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=300, write=30, pool=10),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def cleanup_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


def _ollama_url(node: Node) -> str:
    """Get the Ollama base URL for a node."""
    if node == Node.WILE:
        return settings.wile_url
    elif node == Node.ROADRUNNER:
        return settings.roadrunner_url
    else:
        raise ValueError(f"No direct Ollama URL for node: {node}")


# ── Ollama Provider ──────────────────────────────────────────────────


class OllamaProvider:
    """Direct Ollama API calls to Wile or Roadrunner."""

    def __init__(self, model: str, node: Node):
        self.model = model
        self.node = node
        self.base_url = _ollama_url(node)

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> dict:
        """Generate a completion. Returns dict with 'response', 'model', 'total_duration', etc."""
        client = _get_client()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            payload["system"] = system

        start = time.monotonic()
        try:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            latency_ms = int((time.monotonic() - start) * 1000)
            data["_latency_ms"] = latency_ms
            data["_node"] = self.node.value
            logger.info(
                f"Ollama [{self.node.value}] {self.model}: "
                f"{latency_ms}ms, {data.get('eval_count', '?')} tokens"
            )
            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error [{self.node.value}]: {e.response.status_code} {e.response.text[:200]}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Cannot reach Ollama on {self.node.value} ({self.base_url}): {e}")
            raise

    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> dict:
        """Chat completion via Ollama /api/chat."""
        client = _get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        start = time.monotonic()
        resp = await client.post(f"{self.base_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        data["_latency_ms"] = int((time.monotonic() - start) * 1000)
        data["_node"] = self.node.value
        return data

    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        """Stream tokens from Ollama."""
        client = _get_client()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            payload["system"] = system

        async with client.stream(
            "POST", f"{self.base_url}/api/generate", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.strip():
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

    async def is_available(self) -> bool:
        """Ping the Ollama node."""
        try:
            client = _get_client()
            resp = await client.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False


# ── Open WebUI Provider (OpenAI-compatible) ───────────────────────────


class OpenWebUIProvider:
    """Calls to Open WebUI cluster at ai.guapo613.beer.

    Uses the OpenAI-compatible /v1/chat/completions endpoint.
    """

    def __init__(self, model: str = ""):
        self.model = model or settings.DEFAULT_FAST_MODEL
        self.base_url = settings.OPENWEBUI_URL.rstrip("/")
        self.api_key = settings.OPENWEBUI_API_KEY

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> dict:
        """Chat completion via OpenAI-compatible endpoint."""
        client = _get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        start = time.monotonic()
        resp = await client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        latency_ms = int((time.monotonic() - start) * 1000)

        # Normalize to our format
        content = ""
        if data.get("choices"):
            content = data["choices"][0].get("message", {}).get("content", "")

        result = {
            "response": content,
            "model": data.get("model", self.model),
            "_latency_ms": latency_ms,
            "_node": "cluster",
            "_usage": data.get("usage", {}),
        }
        logger.info(
            f"OpenWebUI cluster {self.model}: {latency_ms}ms"
        )
        return result

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> dict:
        """Convert prompt-style call to chat format."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages, max_tokens, temperature)

    async def chat_stream(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        """Stream tokens from OpenWebUI."""
        client = _get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        async with client.stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue

    async def is_available(self) -> bool:
        """Check if Open WebUI is reachable."""
        try:
            client = _get_client()
            resp = await client.get(
                f"{self.base_url}/v1/models",
                headers=self._headers(),
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False


# ── Embedding Provider ────────────────────────────────────────────────


class EmbeddingProvider:
    """Generate embeddings via Ollama /api/embeddings."""

    def __init__(self, model: str = "", node: Node = Node.ROADRUNNER):
        self.model = model or settings.DEFAULT_EMBEDDING_MODEL
        self.node = node
        self.base_url = _ollama_url(node)

    async def embed(self, text: str) -> list[float]:
        """Get embedding vector for a single text."""
        client = _get_client()
        resp = await client.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("embedding", [])

    async def embed_batch(self, texts: list[str], concurrency: int = 5) -> list[list[float]]:
        """Embed multiple texts with controlled concurrency."""
        sem = asyncio.Semaphore(concurrency)

        async def _embed_one(t: str) -> list[float]:
            async with sem:
                return await self.embed(t)

        return await asyncio.gather(*[_embed_one(t) for t in texts])


# ── Health check for all nodes ────────────────────────────────────────


async def check_all_nodes() -> dict:
    """Check availability of all LLM nodes."""
    wile = OllamaProvider("", Node.WILE)
    roadrunner = OllamaProvider("", Node.ROADRUNNER)
    cluster = OpenWebUIProvider()

    wile_ok, rr_ok, cl_ok = await asyncio.gather(
        wile.is_available(),
        roadrunner.is_available(),
        cluster.is_available(),
        return_exceptions=True,
    )

    return {
        "wile": {"available": wile_ok is True, "url": settings.wile_url},
        "roadrunner": {"available": rr_ok is True, "url": settings.roadrunner_url},
        "cluster": {"available": cl_ok is True, "url": settings.OPENWEBUI_URL},
    }
