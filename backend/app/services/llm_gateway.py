"""
LLM Gateway

CLAUDE.md セクション8.7に基づくエラーハンドリング:
- LLM出力パース失敗: 最大3回リトライ
- Ollamaワーカー全滅時: ユーザーフレンドリーなエラー
- ヘルスチェック機能
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

import httpx
from pydantic_settings import BaseSettings

from app.core.exceptions import (
    LLMGenerationError,
    LLMParseError,
    LLMUnavailableError,
)

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


# ヘルスチェック間隔
HEALTH_CHECK_INTERVAL_SECONDS = 30


@dataclass
class Worker:
    host: str
    healthy: bool = True
    semaphore: asyncio.Semaphore | None = None
    last_health_check: datetime | None = None
    consecutive_failures: int = 0

    def __post_init__(self):
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(1)

    def needs_health_check(self) -> bool:
        """ヘルスチェックが必要かどうか"""
        if self.last_health_check is None:
            return True
        elapsed = datetime.now() - self.last_health_check
        return elapsed > timedelta(seconds=HEALTH_CHECK_INTERVAL_SECONDS)

    def mark_healthy(self):
        """ワーカーを健全としてマーク"""
        self.healthy = True
        self.consecutive_failures = 0
        self.last_health_check = datetime.now()

    def mark_unhealthy(self):
        """ワーカーを不健全としてマーク"""
        self.consecutive_failures += 1
        # 3回連続失敗で不健全とマーク
        if self.consecutive_failures >= 3:
            self.healthy = False
        self.last_health_check = datetime.now()


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

    def _select_worker(self, exclude: set[str] | None = None) -> Worker | None:
        """
        ラウンドロビンでワーカーを選択

        Args:
            exclude: 除外するワーカーホストのセット

        Returns:
            選択されたワーカー、なければNone
        """
        exclude = exclude or set()
        healthy_workers = [
            w for w in self.workers
            if w.healthy and w.host not in exclude
        ]
        if not healthy_workers:
            return None
        worker = healthy_workers[self._current_worker_index % len(healthy_workers)]
        self._current_worker_index += 1
        return worker

    async def health_check(self, worker: Worker, force: bool = False) -> bool:
        """
        ワーカーの健全性をチェック

        Args:
            worker: チェック対象のワーカー
            force: 強制的にチェックする（間隔を無視）

        Returns:
            健全かどうか
        """
        if not force and not worker.needs_health_check():
            return worker.healthy

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"http://{worker.host}/api/tags")
                if response.status_code == 200:
                    worker.mark_healthy()
                    return True
                else:
                    worker.mark_unhealthy()
                    return False
        except Exception as e:
            logger.warning(f"Health check failed for {worker.host}: {e}")
            worker.mark_unhealthy()
            return False

    async def check_all_workers(self, force: bool = False) -> dict:
        """
        全ワーカーの健全性をチェック

        Args:
            force: 強制的にチェックする

        Returns:
            健全性レポート
        """
        tasks = [self.health_check(w, force) for w in self.workers]
        results = await asyncio.gather(*tasks)

        healthy_count = sum(1 for r in results if r)
        total_count = len(self.workers)

        report = {
            "healthy": healthy_count,
            "total": total_count,
            "all_healthy": healthy_count == total_count,
            "any_healthy": healthy_count > 0,
            "workers": [
                {
                    "host": w.host,
                    "healthy": w.healthy,
                    "consecutive_failures": w.consecutive_failures,
                }
                for w in self.workers
            ],
        }

        if healthy_count == 0:
            logger.error("All Ollama workers are unhealthy!")
        elif healthy_count < total_count:
            logger.warning(f"Some Ollama workers are unhealthy: {healthy_count}/{total_count}")

        return report

    async def generate(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.LIGHT,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Ollamaを使用してテキストを生成

        Args:
            prompt: プロンプト
            tier: モデルティア
            system_prompt: システムプロンプト
            temperature: 温度
            max_tokens: 最大トークン数

        Returns:
            生成されたテキスト

        Raises:
            LLMUnavailableError: ワーカーが利用不可
            LLMGenerationError: 生成失敗
        """
        # まず健全なワーカーがあるか確認
        worker = self._select_worker()
        if not worker:
            # 全ワーカーをチェックしてみる
            await self.check_all_workers(force=True)
            worker = self._select_worker()
            if not worker:
                raise LLMUnavailableError(
                    details={"workers": [w.host for w in self.workers]}
                )

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
        tried_workers = set()

        for attempt in range(settings.llm_max_retries):
            # ワーカーが変わった可能性があるので再選択
            if attempt > 0:
                worker = self._select_worker(exclude=tried_workers)
                if not worker:
                    # 除外なしで再選択
                    worker = self._select_worker()
                    if not worker:
                        break

            tried_workers.add(worker.host)

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

                        # 成功したらワーカーを健全としてマーク
                        worker.mark_healthy()

                        logger.info(
                            f"LLM generate: model={model}, worker={worker.host}, "
                            f"latency={elapsed:.2f}s, tokens={len(content.split())}"
                        )
                        return content

            except httpx.TimeoutException as e:
                last_error = e
                worker.mark_unhealthy()
                logger.warning(
                    f"LLM generate timeout on {worker.host} "
                    f"(attempt {attempt + 1}/{settings.llm_max_retries})"
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    worker.mark_unhealthy()
                logger.warning(
                    f"LLM generate HTTP error on {worker.host}: {e.response.status_code} "
                    f"(attempt {attempt + 1}/{settings.llm_max_retries})"
                )
            except Exception as e:
                last_error = e
                worker.mark_unhealthy()
                logger.warning(
                    f"LLM generate error on {worker.host}: {e} "
                    f"(attempt {attempt + 1}/{settings.llm_max_retries})"
                )

            if attempt < settings.llm_max_retries - 1:
                await asyncio.sleep(1)

        raise LLMGenerationError(
            message=f"LLM generation failed after {settings.llm_max_retries} retries: {last_error}",
            attempts=settings.llm_max_retries,
            details={"last_error": str(last_error), "tried_workers": list(tried_workers)},
        )

    async def generate_json(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.LIGHT,
        system_prompt: str | None = None,
        temperature: float = 0.3,
    ) -> dict:
        """
        JSON出力を生成（パース失敗時にリトライ）

        CLAUDE.md 8.7: LLM出力パース失敗は最大3回リトライ

        Args:
            prompt: プロンプト
            tier: モデルティア
            system_prompt: システムプロンプト
            temperature: 温度

        Returns:
            パースされたJSON辞書

        Raises:
            LLMParseError: JSONパース失敗
            LLMUnavailableError: ワーカーが利用不可
            LLMGenerationError: 生成失敗
        """
        json_system = (
            system_prompt or ""
        ) + "\n\nYou must respond with valid JSON only. Do not include any text before or after the JSON."

        raw_responses = []
        current_prompt = prompt

        for attempt in range(settings.llm_max_retries):
            try:
                response = await self.generate(
                    prompt=current_prompt,
                    tier=tier,
                    system_prompt=json_system,
                    temperature=temperature,
                )
                raw_responses.append(response)

                # JSONを抽出
                parsed = self._extract_json(response)
                if parsed is not None:
                    return parsed

                # パース失敗
                logger.warning(
                    f"JSON parse attempt {attempt + 1}/{settings.llm_max_retries} failed: "
                    f"Could not extract valid JSON from response"
                )

            except (LLMUnavailableError, LLMGenerationError):
                # これらのエラーは再スロー
                raise
            except json.JSONDecodeError as e:
                raw_responses.append(response if 'response' in locals() else "")
                logger.warning(
                    f"JSON parse attempt {attempt + 1}/{settings.llm_max_retries} failed: {e}"
                )

            if attempt < settings.llm_max_retries - 1:
                # プロンプトを修正してリトライ
                current_prompt = (
                    f"{prompt}\n\n"
                    "IMPORTANT: Your response must be valid JSON only. "
                    "Do not include any explanation, markdown formatting, or text outside the JSON object."
                )

        raise LLMParseError(
            message=f"Failed to parse JSON after {settings.llm_max_retries} attempts",
            raw_output=raw_responses[-1] if raw_responses else None,
            attempts=settings.llm_max_retries,
        )

    def _extract_json(self, response: str) -> dict | None:
        """
        レスポンスからJSONを抽出

        Args:
            response: LLMレスポンス

        Returns:
            パースされた辞書、失敗時はNone
        """
        response = response.strip()

        # マークダウンコードブロックを除去
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        response = response.strip()

        # 直接パースを試みる
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # JSONオブジェクトを探す
        start_idx = response.find("{")
        end_idx = response.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(response[start_idx:end_idx + 1])
            except json.JSONDecodeError:
                pass

        # JSON配列を探す
        start_idx = response.find("[")
        end_idx = response.rfind("]")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(response[start_idx:end_idx + 1])
            except json.JSONDecodeError:
                pass

        return None

    async def embed(self, text: str) -> list[float]:
        """
        Ollamaを使用してエンベディングを生成

        Args:
            text: 埋め込むテキスト

        Returns:
            エンベディングベクトル

        Raises:
            LLMUnavailableError: ワーカーが利用不可
            LLMGenerationError: 生成失敗
        """
        worker = self._select_worker()
        if not worker:
            await self.check_all_workers(force=True)
            worker = self._select_worker()
            if not worker:
                raise LLMUnavailableError(
                    details={"workers": [w.host for w in self.workers]}
                )

        model = self._get_model_name(ModelTier.EMBED)
        payload = {
            "model": model,
            "prompt": text,
        }

        last_error = None
        for attempt in range(settings.llm_max_retries):
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

                        worker.mark_healthy()

                        logger.info(
                            f"LLM embed: model={model}, worker={worker.host}, "
                            f"latency={elapsed:.2f}s, dims={len(embedding)}"
                        )
                        return embedding

            except Exception as e:
                last_error = e
                worker.mark_unhealthy()
                logger.warning(
                    f"Embedding generation attempt {attempt + 1} failed on {worker.host}: {e}"
                )
                if attempt < settings.llm_max_retries - 1:
                    # 別のワーカーを試す
                    new_worker = self._select_worker(exclude={worker.host})
                    if new_worker:
                        worker = new_worker
                    await asyncio.sleep(0.5)

        raise LLMGenerationError(
            message=f"Embedding generation failed: {last_error}",
            attempts=settings.llm_max_retries,
            details={"last_error": str(last_error)},
        )


# Singleton instance
llm_gateway = LLMGateway()
