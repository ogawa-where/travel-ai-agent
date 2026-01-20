import asyncio
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum

import httpx
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    HEAVY = "heavy"
    LIGHT = "light"
    EMBED = "embed"


class Settings(BaseSettings):
    ollama_workers: str = "localhost:11434"
    ollama_model_heavy: str = "qwen2.5-bakeneko-32b-instruct-v2"
    ollama_model_light: str = "okamototk/llama-swallow:8b"
    ollama_model_embed: str = "nomic-embed-text"
    llm_max_retries: int = 3
    llm_timeout: int = 120

    class Config:
        env_file = ".env"


settings = Settings()


@dataclass
class Worker:
    host: str
    healthy: bool = True
    semaphore: asyncio.Semaphore | None = None

    def __post_init__(self):
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(1)


class LLMGateway:
    def __init__(self):
        self.workers: list[Worker] = []
        self._initialize_workers()
        self._current_worker_index = 0

    def _initialize_workers(self):
        worker_hosts = settings.ollama_workers.split(",")
        for host in worker_hosts:
            host = host.strip()
            if host:
                self.workers.append(Worker(host=host))
        if not self.workers:
            self.workers.append(Worker(host="localhost:11434"))
        logger.info(f"Initialized {len(self.workers)} Ollama workers")

    def _get_model_name(self, tier: ModelTier) -> str:
        if tier == ModelTier.HEAVY:
            return settings.ollama_model_heavy
        elif tier == ModelTier.LIGHT:
            return settings.ollama_model_light
        elif tier == ModelTier.EMBED:
            return settings.ollama_model_embed
        return settings.ollama_model_light

    def _select_worker(self) -> Worker | None:
        """Round-robin worker selection with health check"""
        healthy_workers = [w for w in self.workers if w.healthy]
        if not healthy_workers:
            return None
        worker = healthy_workers[self._current_worker_index % len(healthy_workers)]
        self._current_worker_index += 1
        return worker

    async def health_check(self, worker: Worker) -> bool:
        """Check if a worker is healthy"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"http://{worker.host}/api/tags")
                worker.healthy = response.status_code == 200
                return worker.healthy
        except Exception as e:
            logger.warning(f"Health check failed for {worker.host}: {e}")
            worker.healthy = False
            return False

    async def check_all_workers(self):
        """Check health of all workers"""
        tasks = [self.health_check(w) for w in self.workers]
        await asyncio.gather(*tasks)

    async def generate(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.LIGHT,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text using Ollama"""
        worker = self._select_worker()
        if not worker:
            raise RuntimeError("No healthy Ollama workers available")

        model = self._get_model_name(tier)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        last_error = None
        for attempt in range(settings.llm_max_retries):
            try:
                async with worker.semaphore:
                    start_time = time.time()
                    async with httpx.AsyncClient(
                        timeout=settings.llm_timeout
                    ) as client:
                        response = await client.post(
                            f"http://{worker.host}/api/chat",
                            json=payload,
                        )
                        response.raise_for_status()
                        elapsed = time.time() - start_time

                        result = response.json()
                        content = result.get("message", {}).get("content", "")

                        logger.info(
                            f"LLM generate: model={model}, worker={worker.host}, "
                            f"latency={elapsed:.2f}s, tokens={len(content.split())}"
                        )
                        return content

            except Exception as e:
                last_error = e
                logger.warning(f"LLM generate attempt {attempt + 1} failed: {e}")
                if attempt < settings.llm_max_retries - 1:
                    await asyncio.sleep(1)

        raise RuntimeError(f"LLM generation failed after retries: {last_error}")

    async def generate_json(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.LIGHT,
        system_prompt: str | None = None,
        temperature: float = 0.3,
    ) -> dict:
        """Generate JSON output with retry on parse failure"""
        json_system = (
            system_prompt or ""
        ) + "\n\nYou must respond with valid JSON only."

        for attempt in range(settings.llm_max_retries):
            try:
                response = await self.generate(
                    prompt=prompt,
                    tier=tier,
                    system_prompt=json_system,
                    temperature=temperature,
                )
                # Try to extract JSON from response
                response = response.strip()
                if response.startswith("```json"):
                    response = response[7:]
                if response.startswith("```"):
                    response = response[3:]
                if response.endswith("```"):
                    response = response[:-3]
                return json.loads(response.strip())

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse attempt {attempt + 1} failed: {e}")
                if attempt < settings.llm_max_retries - 1:
                    prompt = f"{prompt}\n\nIMPORTANT: Return valid JSON format only."
                continue

        raise RuntimeError("Failed to generate valid JSON after retries")

    async def embed(self, text: str) -> list[float]:
        """Generate embeddings using Ollama"""
        worker = self._select_worker()
        if not worker:
            raise RuntimeError("No healthy Ollama workers available")

        model = self._get_model_name(ModelTier.EMBED)
        payload = {
            "model": model,
            "prompt": text,
        }

        try:
            async with worker.semaphore:
                start_time = time.time()
                async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
                    response = await client.post(
                        f"http://{worker.host}/api/embeddings",
                        json=payload,
                    )
                    response.raise_for_status()
                    elapsed = time.time() - start_time

                    result = response.json()
                    embedding = result.get("embedding", [])

                    logger.info(
                        f"LLM embed: model={model}, worker={worker.host}, "
                        f"latency={elapsed:.2f}s, dims={len(embedding)}"
                    )
                    return embedding

        except Exception as e:
            raise RuntimeError(f"Embedding generation failed: {e}")


# Singleton instance
llm_gateway = LLMGateway()
