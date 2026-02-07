# Travel AI Agent

体験型旅行企画マルチエージェントシステム

ユーザーの**長期嗜好（長期記憶）**、今回の**要求（短期記憶）**、およびオンラインから取得した**実世界情報（Tavily）**を用いて、体験型かつパーソナライズされた旅行計画を自動生成するマルチエージェントシステムです。

![ログイン画面](docs/screenshots/login.png)

## 参考研究

**Personal Travel Solver (PTS)**: Shao et al., "Personal Travel Solver: A Preference-Driven LLM-Solver System for Travel Planning", ACL 2025

本システムはPTSの5モジュール構成を参考に、リアルタイム検索（Tavily）・体験ベース埋め込み・動的嗜好学習を独自に組み込んでいます。

## 機能

### 嗜好学習モード

チャット形式のQ&Aにより、ユーザーの嗜好を学習しプロフィールを構築します。

- 対話を通じて好み・嫌いを抽出（Preference Learner Agent）
- 体験軸の嗜好（文化/自然/学び/参加型/ウェルネス等）を把握
- 予算傾向、歩行耐性、混雑耐性などの特性を記録
- 学習結果をプロフィール要約 + 構造化シグナル（JSONB）として永続化

### 旅行企画モード

長期嗜好 + 短期要望 + 検索結果を統合し、体験型旅程を生成します。

- Tavily APIによるリアルタイム検索
- 4カテゴリ並列検索（観光・食・宿・交通）＋推論ループ
- 体験ベース埋め込みによるPOIリランキング
- パーソナライズされた旅程と根拠説明の生成
- OSRMによる実距離・所要時間計算
- Leafletによる旅程マップ可視化

### 統合チャットモード

自動的に意図分類（旅行企画 vs 一般会話）を行い、会話中に嗜好を継続学習します。

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| フロントエンド | Vue 3 + TypeScript + Vite |
| バックエンド | Python + FastAPI |
| データベース | PostgreSQL（asyncpg） |
| ローカルLLM | Ollama（マルチホスト4台） |
| 検索API | Tavily |
| ルーティング | OSRM（日本地図） |
| ジオコーディング | Nominatim |
| 地図表示 | Leaflet |
| コンテナ | Docker / Docker Compose |

## システム構成

```
┌─────────────────────────────────────────────────────────────────┐
│    mafu (Orchestrator + Transportation Search)                   │
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
│    nubia      │ │    qilin      │ │    gouin      │
│  RTX 3090 Ti  │ │   RTX 3090    │ │   RTX 3090    │
│  Heavy LLM    │ │  Light LLM    │ │  Embedding    │
│  qwen:32b     │ │  gemma3:12b   │ │ nomic-embed   │
│  同時実行: 1  │ │  同時実行: 2  │ │  同時実行: 10 │
└───────────────┘ └───────────────┘ └───────────────┘
```

## 旅程生成オーケストレーションフロー

```
ユーザー入力
  │
  ▼
Translator Agent ─── 自然言語 → 制約/嗜好JSON
  │
  ▼
SearchReasoningLoop x4（並列）
  ├── Activity Search (nubia)
  ├── Food Search (qilin)
  ├── Hotel Search (gouin)
  └── Transportation Search (mafu)
  │
  ▼
Normalizer / Deduper ─── 正規化・重複排除
  │
  ▼
Rerank Agent ─── 体験ベース埋め込みでスコアリング
  │
  ▼
Search Evaluator Agent ─── 4カテゴリ横断評価
  │
  ▼
Planner Agent ─── 制約充足＋旅程生成
  │
  ▼
Explainer Agent ─── 根拠説明生成
  │
  ▼
旅程 + 説明 + マップ
```

## エージェント設計

本システムのエージェントは、必要な計算資源と役割に応じて **5つの種類** に分類されます。

### エージェント種類

| 種類 | 説明 | 使用モデル | 配置サーバー |
|------|------|-----------|-------------|
| **Heavy LLM** | 複雑な推論・生成を行うエージェント。制約充足、旅程構成、根拠説明など高い言語能力が求められるタスクを担当。32Bクラスのモデルを使用するため同時実行は1。 | qwen2.5-bakeneko-32b | nubia |
| **Light LLM** | 要約・抽出・短文生成など比較的単純なLLMタスクを担当。応答速度を重視し、12Bクラスの軽量モデルで同時2つまで実行可能。 | gemma3:12b | qilin |
| **Embedding** | テキストをベクトル化し、嗜好と候補POIの類似度計算・リランキングを行う。埋め込みモデルは軽量なため多数並列実行が可能。 | nomic-embed-text | gouin |
| **検索推論** | カテゴリごとに「推論→検索クエリ生成→Tavily検索→結果検証」の自律ループを実行。検索フェーズでは4サーバーすべてが並列で稼働し、各サーバーが1カテゴリを専任。 | qwen2.5:32b-instruct | 全4台 |
| **I/Oツール** | LLMを使わない決定論的処理。検索結果の正規化・重複排除、POIキャッシュなど。純粋なコードロジックで実行。 | なし | mafu |

### エージェント一覧

#### Heavy LLM エージェント（nubia / qwen2.5-bakeneko-32b）

| エージェント | ファイル | 役割 |
|-------------|---------|------|
| Planner | `planner.py` | 制約（時間・予算・営業時間）を充足しながらタイムスロット付き旅程を生成。スコアリングで最適化。 |
| Explainer | `explainer.py` | 生成された旅程に対して「なぜこのPOIを選んだか」をユーザーの嗜好・体験軸に紐づけて説明文を生成。 |
| Profile Updater | `profile_updater.py` | 嗜好学習の完了時やフィードバック後に、長期記憶（プロフィール要約 + 嗜好シグナル）を統合更新。 |
| Search Evaluator | `search_evaluator.py` | 4カテゴリの検索結果を横断的に評価し、カテゴリ間のバランスや体験の多様性をスコアリング。 |

#### Light LLM エージェント（qilin / gemma3:12b）

| エージェント | ファイル | 役割 |
|-------------|---------|------|
| Translator | `translator.py` | 自然言語の旅行要求を構造化JSON（TravelConstraints + TravelWishes）に変換。 |
| Summarizer | `summarizer.py` | 3ターンを超えた古い会話履歴を session_summary に圧縮。決定事項・制約・未解決事項を保持。 |
| Preference Learner | `preference_learner.py` | ユーザー発話から嗜好シグナル（category / tag / weight / evidence）を抽出。会話中に常時稼働。 |
| Gathering Agent | `gathering_agent.py` | 旅行企画に必要な情報（日程・人数・予算等）が不足している場合に対話で収集。 |

#### Embedding エージェント（gouin / nomic-embed-text）

| エージェント | ファイル | 役割 |
|-------------|---------|------|
| Reranker | `rerank.py` | POIから抽出した「体験の本質」と、ユーザーの嗜好をそれぞれ埋め込みベクトル化し、コサイン類似度でリランキング。 |

#### 検索推論エージェント（4サーバー並列 / qwen2.5:32b-instruct）

| エージェント | ファイル | 役割 |
|-------------|---------|------|
| SearchReasoningLoop | `search_agents.py` | カテゴリごとに自律的な推論ループを実行。LLMが検索クエリを生成→Tavilyで検索→結果を検証→不足があれば再検索。 |
| ActivitySearchAgent | `search_agents.py` | 体験・観光カテゴリの検索（nubia で実行） |
| FoodSearchAgent | `search_agents.py` | 食カテゴリの検索（qilin で実行） |
| HotelSearchAgent | `search_agents.py` | 宿泊カテゴリの検索（gouin で実行） |
| TransportationSearchAgent | `search_agents.py` | 交通・アクセスカテゴリの検索（mafu で実行） |

#### I/O ツールエージェント（決定論コード）

| エージェント | ファイル | 役割 |
|-------------|---------|------|
| Normalizer / Deduper | `services/normalizer.py` | 4カテゴリの検索結果を統一フォーマットに正規化し、重複POIを排除。 |
| Experience Extractor | `services/experience_extractor.py` | POIの生データから「体験の本質」（場所名ではなく体験タイプ）を抽出。 |
| POI Cache | `services/poi_cache.py` | 正規化済みPOIと体験抽出結果をキャッシュし、再検索を抑制。 |

### 検索フェーズのサーバー割り当て

| カテゴリ | サーバー | モデル |
|---------|---------|--------|
| Activity（体験・観光） | nubia | qwen2.5:32b-instruct |
| Food（食） | qilin | qwen2.5:32b-instruct |
| Hotel（宿） | gouin | qwen2.5:32b-instruct |
| Transportation（交通） | mafu | qwen2.5:32b-instruct |

## 記憶設計

### 短期記憶（セッション内）

- **直近3ターン**をそのまま保持
- それ以前は **session_summary** として圧縮（Summarizer Agent）
- すべてのLLM呼び出しに system + summary + last_3_turns + task を渡す

### 長期記憶（ユーザー横断）

- **プロフィール要約**（人間可読テキスト）
- **嗜好シグナル**（構造化JSON: category / tag / weight / evidence）

## API エンドポイント

### 認証

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/auth/login` | ユーザー名でログイン（新規自動作成） |

### 統合チャット

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/chat/start` | チャットセッション開始 |
| POST | `/api/chat` | メッセージ送信（意図分類＋嗜好学習） |

### 嗜好学習

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/preference/users` | ユーザー作成 |
| GET | `/preference/users/{user_id}` | プロフィール・嗜好取得 |
| POST | `/preference/chat/start` | 嗜好学習チャット開始 |
| POST | `/preference/chat` | 嗜好学習会話 |
| POST | `/preference/chat/complete` | 嗜好学習完了・記憶統合 |

### 旅行企画

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/travel/plan` | 自然言語から旅程生成 |
| POST | `/api/travel/plan-with-form` | 構造化フォームから旅程生成 |
| POST | `/api/travel/plan/{plan_id}/feedback` | 旅程フィードバック送信 |

### 地理情報

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/geo/geocode` | POI/地名の座標取得 |
| POST | `/api/geo/route` | 2点間ルート距離・時間計算 |
| POST | `/api/geo/enrich-itinerary` | 旅程全体に地理情報付与 |

### 観測性

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/health` | APIヘルスチェック |
| GET | `/api/observability/health/llm` | LLMワーカー状態 |
| GET | `/api/observability/runs` | 実行一覧 |
| GET | `/api/observability/runs/{run_id}` | 実行トレース詳細 |
| GET | `/api/observability/metrics` | エージェントメトリクス |

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd travel-ai-agent
```

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集し、必要な値を設定します:

```bash
# Ollama（4サーバー構成）
OLLAMA_WORKERS=nubia:11434,qilin:11434,gouin:11434,mafu:11434
OLLAMA_WORKER_HEAVY=nubia:11434
OLLAMA_WORKER_LIGHT=qilin:11434
OLLAMA_WORKER_EMBED=gouin:11434
OLLAMA_WORKER_MAFU=mafu:11434
OLLAMA_MODEL_HEAVY=qwen2.5-bakeneko-32b-instruct-v2
OLLAMA_MODEL_LIGHT=gemma3:12B
OLLAMA_MODEL_EMBED=nomic-embed-text

# Database
DATABASE_URL=postgresql://travel:travel@postgres:5432/travel_agent

# External APIs
TAVILY_API_KEY=your_tavily_api_key_here

# Geo Services
OSRM_BASE_URL=http://osrm:5000
NOMINATIM_USER_AGENT=travel-ai-agent/1.0

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

### 3. OSRM データの準備

OSRMで日本地図のルート計算を行うため、地図データをダウンロードし前処理します。

```bash
./scripts/setup-osrm.sh
```

- Geofabrikから日本の地図データ（PBF: ~1.5GB）をダウンロード
- OSRM用に前処理（extract → partition → customize）
- 処理時間: 30分〜1時間（マシンスペック依存）

### 4. mafu の IP アドレス設定

オーケストレーターサーバーのIPを `ollama_workers.json` に反映します。

```bash
./scripts/update-mafu-ip.sh           # 自動検出
./scripts/update-mafu-ip.sh 192.168.1.100  # 手動指定
```

### 5. 起動

```bash
docker compose up --build
```

起動後のアクセス先:

| サービス | URL |
|---------|-----|
| フロントエンド | http://localhost:3000 |
| バックエンドAPI | http://localhost:8000 |
| APIドキュメント | http://localhost:8000/docs |

### UI フロー

```
SearchSplashScreen（IME検索アニメーション）
  → フェード遷移
  → LoginScreen（筆記体タイトル + ログインフォーム）
    → ModeSelectScreen（モード選択）
      → PreferenceLearningView / TravelPlanningView
```

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
│   │   │   ├── planner.py
│   │   │   ├── explainer.py
│   │   │   ├── translator.py
│   │   │   ├── summarizer.py
│   │   │   ├── preference_learner.py
│   │   │   ├── profile_updater.py
│   │   │   ├── search_agents.py
│   │   │   ├── search_evaluator.py
│   │   │   ├── gathering_agent.py
│   │   │   └── rerank.py
│   │   ├── domain/          # ドメインモデル（ORM）
│   │   ├── orchestrator/    # 旅程生成オーケストレーター
│   │   ├── routers/         # APIルーター
│   │   ├── schemas/         # Pydanticスキーマ
│   │   ├── services/        # 外部サービス連携
│   │   │   ├── llm_gateway.py        # LLMルーティング・同時実行制御
│   │   │   ├── session_manager.py    # セッション・コンテキスト管理
│   │   │   ├── long_term_memory.py   # 長期記憶管理
│   │   │   ├── tavily_client.py      # Tavily検索クライアント
│   │   │   ├── normalizer.py         # POI正規化・重複排除
│   │   │   ├── experience_extractor.py
│   │   │   ├── geocoder.py           # Nominatimジオコーディング
│   │   │   ├── osrm_client.py        # OSRMルート計算
│   │   │   ├── vector_store.py       # 埋め込みベクトルストア
│   │   │   ├── intent_classifier.py  # 意図分類
│   │   │   ├── observability.py      # トレース・メトリクス
│   │   │   ├── poi_cache.py
│   │   │   └── poi_repository.py
│   │   ├── core/            # 例外定義等
│   │   ├── database.py
│   │   └── main.py
│   ├── config/
│   │   └── ollama_workers.json  # Ollamaワーカー設定
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SearchSplashScreen.vue   # 検索IMEアニメーション
│   │   │   ├── LoginScreen.vue          # 筆記体タイトル＋ログイン
│   │   │   ├── ModeSelectScreen.vue     # モード選択
│   │   │   ├── PreferenceLearningView.vue
│   │   │   ├── TravelPlanningView.vue
│   │   │   ├── ItineraryDisplay.vue     # 旅程表示
│   │   │   ├── ItineraryMap.vue         # Leaflet地図
│   │   │   └── ...
│   │   ├── lib/
│   │   │   ├── api.ts       # APIクライアント
│   │   │   ├── storage.ts   # localStorage管理
│   │   │   └── errors.ts    # エラー型定義
│   │   ├── App.vue
│   │   └── main.ts
│   ├── public/
│   ├── Dockerfile
│   └── package.json
├── scripts/
│   ├── setup-osrm.sh        # OSRM日本地図セットアップ
│   └── update-mafu-ip.sh    # mafuのIPアドレス更新
├── osrm-data/               # OSRMデータ（gitignore）
├── docker-compose.yml
├── .env.example
└── CLAUDE.md                # AI開発ガイドライン
```

## データベーステーブル

| テーブル | 用途 |
|---------|------|
| `users` | ユーザーアカウント |
| `user_profiles` | プロフィール要約テキスト |
| `preference_signals` | 構造化嗜好シグナル（JSONB） |
| `sessions` | チャットセッションメタ |
| `messages` | チャット生ログ |
| `session_summaries` | 短期要約 |
| `session_events` | エージェントステップログ |
| `travel_plan_requests` | 旅行企画リクエスト |
| `travel_plans` | 生成旅程（旅程JSON / 根拠 / スコア） |
| `plan_runs` | 実行トレース（設定スナップショット含む） |
| `poi_cache` | 正規化POIキャッシュ |

## ライセンス

Private
