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
│                                                  ┌────────────┐ │
│                                                  │  Ollama    │ │
│                                                  │  :11434    │ │
│                                                  │ (検索時)   │ │
│                                                  └────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│    nubia      │ │    qilin      │ │    ranco      │
│  Heavy LLM    │ │  Light LLM    │ │  Embedding    │
│  qwen:32b     │ │  gemma3:12b   │ │ nomic-embed   │
└───────────────┘ └───────────────┘ └───────────────┘
```

### 検索フェーズのモデル割り当て

検索フェーズでは4台すべてで32bモデル（`qwen2.5:32b-instruct`）を使用し、高品質な推論を実現します。

| カテゴリ | サーバー | モデル |
|---------|---------|--------|
| Activity（体験・観光） | nubia | qwen2.5:32b-instruct |
| Food（食） | qilin | qwen2.5:32b-instruct |
| Hotel（宿） | ranco | qwen2.5:32b-instruct |
| Transportation（交通） | mafu | qwen2.5:32b-instruct |

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
OLLAMA_MODEL_HEAVY=qwen2.5:32b-instruct
OLLAMA_MODEL_LIGHT=gemma3:12b
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

### 3. OSRM データの準備（日本地図のダウンロード）

OSRMを使用するには、日本の地図データをダウンロードし前処理する必要があります。
セットアップスクリプトを使用して自動的に準備できます。

```bash
./scripts/setup-osrm.sh
```

このスクリプトは以下の処理を行います：

1. `osrm-data/` ディレクトリを作成
2. Geofabrikから日本の地図データ（PBFファイル、約1.5GB）をダウンロード
3. OSRM用に前処理（extract → partition → customize）

**前提条件：**
- Docker がインストール済み
- 十分なディスク容量（PBF: ~1.5GB、処理後: ~3GB）
- wget コマンドが利用可能

**処理時間の目安：**
- ダウンロード: ネットワーク速度に依存
- 前処理: 30分〜1時間程度（マシンスペックに依存）

### 4. mafu（オーケストレーターサーバー）のIPアドレス設定

オーケストレーターをデプロイするサーバーのIPアドレスを設定する必要があります。
セットアップスクリプトを使用して自動的に更新できます。

```bash
./scripts/update-mafu-ip.sh
```

このスクリプトは以下の処理を行います：

1. 現在のサーバーのIPアドレスを自動検出
2. `backend/config/ollama_workers.json` の以下の箇所を更新：
   - `workers` 配列内のmafuエントリの `host`
   - `search_routing.transportation.host`

**手動でIPアドレスを指定する場合：**

```bash
./scripts/update-mafu-ip.sh 192.168.1.100
```

**注意：**
- バックアップファイル（`ollama_workers.json.bak`）が自動作成されます
- jqがインストールされている場合は、より正確な更新が行われます

### 5. 起動

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
├── scripts/
│   ├── setup-osrm.sh       # OSRM日本地図セットアップ
│   └── update-mafu-ip.sh   # mafuのIPアドレス更新
├── config/
├── docs/
├── osrm-data/              # OSRMデータ（gitignore）
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

## エージェント一覧

### 通常時（嗜好学習・旅程生成）

| エージェント | 役割 | サーバー | モデル |
|-------------|------|---------|--------|
| Planner | 制約+スコアリングで旅程生成 | nubia | qwen2.5:32b |
| Explainer | 嗜好と体験軸に基づく根拠説明生成 | nubia | qwen2.5:32b |
| Profile Updater | 長期記憶の更新 | nubia | qwen2.5:32b |
| Translator | 要求文→制約/嗜好JSON変換 | qilin | gemma3:12b |
| Summarizer | 短期要約更新 | qilin | gemma3:12b |
| Preference Learner | 会話から嗜好を抽出 | qilin | gemma3:12b |
| Reranker | 体験ベース埋め込みでPOIランク付け | ranco | nomic-embed |

### 検索フェーズ（4サーバー並列）

| カテゴリ | サーバー | モデル |
|---------|---------|--------|
| Activity（体験・観光） | nubia | qwen2.5:32b |
| Food（食） | qilin | qwen2.5:32b |
| Hotel（宿） | ranco | qwen2.5:32b |
| Transportation（交通） | mafu | qwen2.5:32b |

## ライセンス

Private
