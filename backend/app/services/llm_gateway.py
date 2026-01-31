"""
LLM Gateway

CLAUDE.md セクション8に基づく役割ベースルーティング:
- Heavy (mafu, nubia): Planner, Explainer
- Light (qilin): Translator, Summarizer, PreferenceLearner, ProfileUpdater
- Embed (ranco): Reranker, ExperienceExtractor

エラーハンドリング (セクション8.7):
- LLM出力パース失敗: 最大3回リトライ
- Ollamaワーカー全滅時: ユーザーフレンドリーなエラー
- ヘルスチェック機能
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

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


class WorkerRole(str, Enum):
    HEAVY = "heavy"
    LIGHT = "light"
    EMBED = "embed"
    ANY = "any"  # どの役割でも可


class Settings(BaseSettings):
    model_config = {"env_file": ".env"}

    ollama_workers: str = "localhost:11434"
    ollama_model_heavy: str = "qwen2.5:32b-instruct"
    ollama_model_light: str = "gemma3:12B"
    ollama_model_embed: str = "nomic-embed-text"
    llm_max_retries: int = 3
    llm_timeout: int = 120


settings = Settings()


# ヘルスチェック間隔
HEALTH_CHECK_INTERVAL_SECONDS = 30

# エージェント名から役割へのマッピング
# 注意: モデルティアとワーカー役割を一致させる
# - HEAVY モデル使用 → HEAVY ワーカー
# - LIGHT モデル使用 → LIGHT ワーカー
# - EMBED モデル使用 → EMBED ワーカー
AGENT_ROLE_MAPPING = {
    "planner": WorkerRole.HEAVY,
    "explainer": WorkerRole.HEAVY,
    "profile_updater": WorkerRole.HEAVY,  # 複雑な統合タスクはHEAVYモデル使用
    "translator": WorkerRole.LIGHT,
    "summarizer": WorkerRole.LIGHT,
    "preference_learner": WorkerRole.LIGHT,
    "experience_extractor": WorkerRole.LIGHT,  # JSON生成はLIGHTモデル使用
    "reranker": WorkerRole.EMBED,
}


@dataclass
class Worker:
    host: str
    role: WorkerRole = WorkerRole.ANY
    max_concurrent: int = 1
    healthy: bool = True
    semaphore: asyncio.Semaphore | None = None
    last_health_check: datetime | None = None
    consecutive_failures: int = 0
    _current_load: int = field(default=0, repr=False)

    def __post_init__(self):
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(self.max_concurrent)

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
        self._worker_indices: dict[WorkerRole, int] = {
            WorkerRole.HEAVY: 0,
            WorkerRole.LIGHT: 0,
            WorkerRole.EMBED: 0,
            WorkerRole.ANY: 0,
        }
        self._initialize_workers()

    def _initialize_workers(self):
        """ワーカーを初期化（設定ファイルまたは環境変数から）"""
        # 設定ファイルを探す
        config_paths = [
            Path("config/ollama_workers.json"),
            Path("/app/config/ollama_workers.json"),
        ]

        config_loaded = False
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config = json.load(f)
                    self._load_from_config(config)
                    config_loaded = True
                    logger.info(f"Loaded worker config from {config_path}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load config from {config_path}: {e}")

        if not config_loaded:
            # 環境変数から読み込み
            self._load_from_env()

        if not self.workers:
            self.workers.append(Worker(host="localhost:11434", role=WorkerRole.ANY))

        # ワーカー情報をログ出力
        for w in self.workers:
            logger.info(f"Worker: {w.host}, role={w.role.value}, max_concurrent={w.max_concurrent}")

    def _load_from_config(self, config: dict):
        """設定ファイルからワーカーを読み込み"""
        workers_config = config.get("workers", [])
        for wc in workers_config:
            host = wc.get("host", "")
            if not host:
                continue

            role_str = wc.get("role", "any")
            try:
                role = WorkerRole(role_str)
            except ValueError:
                role = WorkerRole.ANY

            max_concurrent = wc.get("max_concurrent", 1)

            self.workers.append(Worker(
                host=host,
                role=role,
                max_concurrent=max_concurrent,
            ))

        # ルーティング設定を更新
        routing = config.get("routing", {})
        for agent_name, role_str in routing.items():
            try:
                role = WorkerRole(role_str)
                AGENT_ROLE_MAPPING[agent_name] = role
            except ValueError:
                pass

    def _load_from_env(self):
        """環境変数からワーカーを読み込み"""
        worker_hosts = settings.ollama_workers.split(",")

        # 役割ごとのワーカー設定を環境変数から取得
        heavy_workers = os.getenv("OLLAMA_WORKER_HEAVY", "").split(",")
        light_workers = os.getenv("OLLAMA_WORKER_LIGHT", "").split(",")
        embed_workers = os.getenv("OLLAMA_WORKER_EMBED", "").split(",")

        heavy_set = {h.strip() for h in heavy_workers if h.strip()}
        light_set = {h.strip() for h in light_workers if h.strip()}
        embed_set = {h.strip() for h in embed_workers if h.strip()}

        for host in worker_hosts:
            host = host.strip()
            if not host:
                continue

            # 役割を判定
            if host in heavy_set:
                role = WorkerRole.HEAVY
                max_concurrent = 1
            elif host in light_set:
                role = WorkerRole.LIGHT
                max_concurrent = 2
            elif host in embed_set:
                role = WorkerRole.EMBED
                max_concurrent = 10
            else:
                role = WorkerRole.ANY
                max_concurrent = 1

            self.workers.append(Worker(
                host=host,
                role=role,
                max_concurrent=max_concurrent,
            ))

        logger.info(f"Initialized {len(self.workers)} Ollama workers from env")

    def _get_model_name(self, tier: ModelTier) -> str:
        if tier == ModelTier.HEAVY:
            return settings.ollama_model_heavy
        elif tier == ModelTier.LIGHT:
            return settings.ollama_model_light
        elif tier == ModelTier.EMBED:
            return settings.ollama_model_embed
        return settings.ollama_model_light

    def get_role_for_agent(self, agent_name: str) -> WorkerRole:
        """エージェント名から必要な役割を取得"""
        return AGENT_ROLE_MAPPING.get(agent_name.lower(), WorkerRole.ANY)

    def _select_worker(
        self,
        role: WorkerRole = WorkerRole.ANY,
        exclude: set[str] | None = None,
        preferred_host: str | None = None,
    ) -> Worker | None:
        """
        役割に基づいてワーカーを選択（ラウンドロビン）

        Args:
            role: 必要な役割
            exclude: 除外するワーカーホストのセット
            preferred_host: 優先するワーカーホスト（指定時はそのホストを直接使用）

        Returns:
            選択されたワーカー、なければNone
        """
        exclude = exclude or set()

        # preferred_host が指定されている場合、そのホストを直接使用
        if preferred_host:
            for w in self.workers:
                if w.host == preferred_host and w.healthy and w.host not in exclude:
                    return w
            # preferred_host が見つからない/不健全な場合はフォールバック
            logger.warning(
                f"Preferred host {preferred_host} not available, falling back to role-based selection"
            )

        # 指定された役割のワーカーを優先
        candidates = [
            w for w in self.workers
            if w.healthy and w.host not in exclude and (w.role == role or role == WorkerRole.ANY)
        ]

        # 見つからない場合は ANY 役割のワーカーを探す
        if not candidates and role != WorkerRole.ANY:
            candidates = [
                w for w in self.workers
                if w.healthy and w.host not in exclude and w.role == WorkerRole.ANY
            ]

        # それでも見つからない場合は全ワーカーから探す（フェイルオーバー）
        if not candidates:
            candidates = [
                w for w in self.workers
                if w.healthy and w.host not in exclude
            ]

        if not candidates:
            return None

        # ラウンドロビンで選択
        index = self._worker_indices.get(role, 0)
        worker = candidates[index % len(candidates)]
        self._worker_indices[role] = index + 1

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
                    "role": w.role.value,
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
        agent_name: str | None = None,
        worker_host: str | None = None,
        model_override: str | None = None,
    ) -> str:
        """
        Ollamaを使用してテキストを生成

        Args:
            prompt: プロンプト
            tier: モデルティア
            system_prompt: システムプロンプト
            temperature: 温度
            max_tokens: 最大トークン数
            agent_name: エージェント名（役割ベースルーティング用）
            worker_host: 直接指定するワーカーホスト（検索フェーズ並列化用）
            model_override: モデル名を直接指定（tier設定を上書き）

        Returns:
            生成されたテキスト

        Raises:
            LLMUnavailableError: ワーカーが利用不可
            LLMGenerationError: 生成失敗
        """
        # エージェント名から役割を取得
        if agent_name:
            role = self.get_role_for_agent(agent_name)
        else:
            # ティアから役割を推定
            role = WorkerRole(tier.value)

        # まず健全なワーカーがあるか確認
        worker = self._select_worker(role=role, preferred_host=worker_host)
        if not worker:
            # 全ワーカーをチェックしてみる
            await self.check_all_workers(force=True)
            worker = self._select_worker(role=role, preferred_host=worker_host)
            if not worker:
                raise LLMUnavailableError(
                    details={"workers": [w.host for w in self.workers], "required_role": role.value}
                )

        model = model_override or self._get_model_name(tier)
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
                worker = self._select_worker(role=role, exclude=tried_workers, preferred_host=worker_host)
                if not worker:
                    # 除外なしで再選択
                    worker = self._select_worker(role=role, preferred_host=worker_host)
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
                            f"role={role.value}, agent={agent_name or 'unknown'}, "
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

    async def generate_stream(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.LIGHT,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        agent_name: str | None = None,
        worker_host: str | None = None,
        model_override: str | None = None,
    ):
        """
        ストリーミングでテキスト生成

        Ollama APIのstream: trueを使用し、チャンクごとにyieldする。

        Args:
            prompt: プロンプト
            tier: モデルティア
            system_prompt: システムプロンプト
            temperature: 温度
            max_tokens: 最大トークン数
            agent_name: エージェント名（役割ベースルーティング用）
            worker_host: 直接指定するワーカーホスト
            model_override: モデル名を直接指定

        Yields:
            str: 生成されたテキストのチャンク

        Raises:
            LLMUnavailableError: ワーカーが利用不可
            LLMGenerationError: 生成失敗
        """
        role = self.get_role_for_agent(agent_name) if agent_name else WorkerRole.ANY
        worker = self._select_worker(role=role, preferred_host=worker_host)

        if not worker:
            raise LLMUnavailableError(
                message=f"No available workers for role: {role.value}",
                details={"workers": [w.host for w in self.workers], "required_role": role.value}
            )

        model = model_override or self._get_model_name(tier)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            async with worker.semaphore:
                start_time = time.time()
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(settings.llm_timeout, connect=10.0)
                ) as client:
                    async with client.stream(
                        "POST",
                        f"http://{worker.host}/api/chat",
                        json=payload,
                    ) as response:
                        response.raise_for_status()
                        total_content = ""

                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            try:
                                chunk = json.loads(line)
                                content = chunk.get("message", {}).get("content", "")
                                if content:
                                    total_content += content
                                    yield content

                                # 完了チェック
                                if chunk.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue

                        elapsed = time.time() - start_time
                        worker.mark_healthy()

                        logger.info(
                            f"LLM generate_stream: model={model}, worker={worker.host}, "
                            f"role={role.value}, agent={agent_name or 'unknown'}, "
                            f"latency={elapsed:.2f}s, chars={len(total_content)}"
                        )

        except httpx.TimeoutException as e:
            worker.mark_unhealthy()
            raise LLMGenerationError(
                message=f"LLM streaming timeout on {worker.host}: {e}",
                attempts=1,
                details={"worker": worker.host, "error": str(e)},
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                worker.mark_unhealthy()
            raise LLMGenerationError(
                message=f"LLM streaming HTTP error on {worker.host}: {e.response.status_code}",
                attempts=1,
                details={"worker": worker.host, "status_code": e.response.status_code},
            )
        except Exception as e:
            worker.mark_unhealthy()
            raise LLMGenerationError(
                message=f"LLM streaming error on {worker.host}: {e}",
                attempts=1,
                details={"worker": worker.host, "error": str(e)},
            )

    async def generate_json(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.LIGHT,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        agent_name: str | None = None,
        worker_host: str | None = None,
        model_override: str | None = None,
    ) -> dict:
        """
        JSON出力を生成（パース失敗時にリトライ）

        CLAUDE.md 8.7: LLM出力パース失敗は最大3回リトライ

        Args:
            prompt: プロンプト
            tier: モデルティア
            system_prompt: システムプロンプト
            temperature: 温度
            agent_name: エージェント名（役割ベースルーティング用）
            worker_host: 直接指定するワーカーホスト（検索フェーズ並列化用）
            model_override: モデル名を直接指定（tier設定を上書き）

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
                    agent_name=agent_name,
                    worker_host=worker_host,
                    model_override=model_override,
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

    async def embed(
        self,
        text: str,
        agent_name: str | None = None,
    ) -> list[float]:
        """
        Ollamaを使用してエンベディングを生成

        Args:
            text: 埋め込むテキスト
            agent_name: エージェント名（役割ベースルーティング用）

        Returns:
            エンベディングベクトル

        Raises:
            LLMUnavailableError: ワーカーが利用不可
            LLMGenerationError: 生成失敗
        """
        # 埋め込みは常に EMBED 役割のワーカーを使用
        role = WorkerRole.EMBED

        worker = self._select_worker(role=role)
        if not worker:
            await self.check_all_workers(force=True)
            worker = self._select_worker(role=role)
            if not worker:
                # フォールバック: 任意のワーカーを使用
                worker = self._select_worker(role=WorkerRole.ANY)
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
        tried_workers = set()

        for attempt in range(settings.llm_max_retries):
            tried_workers.add(worker.host)

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
                            f"agent={agent_name or 'unknown'}, "
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
                    new_worker = self._select_worker(role=role, exclude=tried_workers)
                    if new_worker:
                        worker = new_worker
                    else:
                        # フォールバック
                        new_worker = self._select_worker(role=WorkerRole.ANY, exclude=tried_workers)
                        if new_worker:
                            worker = new_worker
                    await asyncio.sleep(0.5)

        raise LLMGenerationError(
            message=f"Embedding generation failed: {last_error}",
            attempts=settings.llm_max_retries,
            details={"last_error": str(last_error), "tried_workers": list(tried_workers)},
        )


# Singleton instance
llm_gateway = LLMGateway()
