# Travel AI Agent

体験型旅行企画マルチエージェントシステム

ユーザーの長期嗜好（長期記憶）、今回の要求（短期記憶）、およびオンラインから取得した実世界情報を用いて、体験型かつパーソナライズされた旅行計画を自動生成するマルチエージェントシステムです。

## 機能

### 嗜好学習モード
チャット形式のQ&Aにより、ユーザーの嗜好を学習しプロフィールを構築します。

- 対話を通じて好み・嫌いを抽出
- 体験軸の嗜好（文化/自然/学び/参加型/ウェルネス等）を把握
- 予算傾向、歩行耐性、混雑耐性などの特性を記録

### 旅行企画モード
長期嗜好 + 短期要望 + 検索結果を統合し、体験型旅程を生成します。

- Tavily APIによるリアルタイム検索
- 4カテゴリ並列検索（観光・食・宿・交通）
- パーソナライズされた旅程と説明の生成

## 技術スタック

- **フロントエンド**: Vue 3 + TypeScript + Vite
- **バックエンド**: Python + FastAPI
- **データベース**: PostgreSQL
- **ローカルLLM**: Ollama（マルチホスト対応）
- **検索API**: Tavily
- **ルーティング**: OSRM
- **コンテナ**: Docker / Docker Compose

## システム構成

```
┌─────────────────────────────────────────────────────────────────┐
│    mafu (Orchestrator + Transportation Search)                  │
│                        RTX 3090 Ti (24GB)                        │
│  ┌──────────┐  ┌───────────────┐  ┌──────────┐  ┌────────────┐ │
│  │ Frontend │  │  Orchestrator │  │PostgreSQL│  │   OSRM     │ │
│  │  :3000   │  │    :8000      │  │  :5432   │  │   :5001    │ │
│  └──────────┘  └───────────────┘  └──────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│    nubia      │ │    qilin      │ │    ranco      │
│  Heavy LLM    │ │  Light LLM    │ │  Embedding    │
│  qwen:32b     │ │  llama:8b     │ │ nomic-embed   │
└───────────────┘ └───────────────┘ └───────────────┘
```

## セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/your-org/travel-ai-agent.git
cd travel-ai-agent
```

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env`ファイルを編集し、必要な値を設定します：

```bash
# Ollama Configuration
OLLAMA_WORKERS=nubia:11434,qilin:11434,ranco:11434,mafu:11434
OLLAMA_MODEL_HEAVY=qwen2.5-bakeneko-32b-instruct-v2
OLLAMA_MODEL_LIGHT=okamototk/llama-swallow:8b
OLLAMA_MODEL_EMBED=nomic-embed-text

# Database
DATABASE_URL=postgresql://travel:travel@postgres:5432/travel_agent

# External APIs
TAVILY_API_KEY=your_tavily_api_key_here

# Geo Services
OSRM_BASE_URL=http://osrm:5000

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

### 3. OSRM データの準備

OSRMを使用する場合、事前にデータを準備する必要があります：

```bash
mkdir -p osrm-data
# japan-latest.osrm ファイルを osrm-data/ に配置
```

### 4. 起動

```bash
docker compose up --build
```

起動後、以下のURLでアクセスできます：

- フロントエンド: http://localhost:3000
- バックエンドAPI: http://localhost:8000
- API ドキュメント: http://localhost:8000/docs

## 開発

### バックエンドテスト

```bash
docker compose exec backend pytest -q
```

### Lint / Format

```bash
docker compose exec backend ruff check .
docker compose exec backend ruff format .
```

### フロントエンドビルド確認

```bash
docker compose exec frontend npm run build
```

### 停止

```bash
docker compose down
```

## ディレクトリ構成

```
.
├── backend/
│   ├── app/
│   │   ├── agents/          # エージェント実装
│   │   ├── domain/          # ドメインモデル
│   │   ├── orchestrator/    # オーケストレーター
│   │   ├── routers/         # APIルーター
│   │   ├── schemas/         # Pydanticスキーマ
│   │   ├── services/        # 外部サービス連携
│   │   ├── database.py
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── App.vue
│   │   └── main.ts
│   ├── Dockerfile
│   └── package.json
├── config/
├── docs/
├── osrm-data/
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

## エージェント一覧

| エージェント | 役割 | モデル |
|-------------|------|--------|
| Planner | 制約+スコアリングで旅程生成 | Heavy (32B) |
| Explainer | 嗜好と体験軸に基づく根拠説明生成 | Heavy (32B) |
| Profile Updater | 長期記憶の更新 | Heavy (32B) |
| Translator | 要求文→制約/嗜好JSON変換 | Light (8B) |
| Summarizer | 短期要約更新 | Light (8B) |
| Preference Learner | 会話から嗜好を抽出 | Light (8B) |
| Reranker | 体験ベース埋め込みでPOIランク付け | Embedding |
| Search Agents | カテゴリ別検索（4並列） | 各サーバー |

## ライセンス

Private
