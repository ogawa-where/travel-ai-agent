from datetime import datetime, timezone
from uuid import uuid4


def _utcnow() -> datetime:
    """timezone-naive な UTC 現在時刻を返す（TIMESTAMP WITHOUT TIME ZONE 用）"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    username: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    profile: Mapped["UserProfile"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    preference_signals: Mapped[list["PreferenceSignal"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserProfile(Base):
    """人間可読のプロフィール要約（文章）"""

    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class PreferenceSignal(Base):
    """構造化された嗜好シグナル"""

    __tablename__ = "preference_signals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    category: Mapped[str] = mapped_column(
        String(50),
    )  # likes, dislikes, experience_axis, constraints
    tag: Mapped[str] = mapped_column(
        String(100),
    )  # e.g., "文化体験", "自然", "予算"
    weight: Mapped[float] = mapped_column(
        default=1.0,
    )  # 重み（0.0〜1.0）
    evidence: Mapped[str] = mapped_column(
        Text,
        default="",
    )  # 根拠（ユーザーの発言等）
    extra_data: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )  # 追加情報
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    user: Mapped["User"] = relationship(back_populates="preference_signals")


class Session(Base):
    """チャットセッション（短期記憶の単位）"""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    mode: Mapped[str] = mapped_column(
        String(50),
        default="preference_learning",
    )  # preference_learning, travel_planning
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    extra_data: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )  # 追加情報（collected_info など）
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.turn_index",
    )
    summary: Mapped["SessionSummary"] = relationship(
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Message(Base):
    """チャットメッセージ（生ログ）"""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sessions.id", ondelete="CASCADE"),
    )
    role: Mapped[str] = mapped_column(
        String(20),
    )  # user, assistant
    content: Mapped[str] = mapped_column(
        Text,
    )
    turn_index: Mapped[int] = mapped_column(
        Integer,
    )  # ターン番号（ユーザー発言を1ターンの開始とする）
    is_summarized: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )  # 要約に吸収済みか
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )

    session: Mapped["Session"] = relationship(back_populates="messages")


class SessionSummary(Base):
    """セッション要約（古いターンの圧縮）"""

    __tablename__ = "session_summaries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        unique=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        default="",
    )  # 要約内容
    last_summarized_turn: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )  # 最後に要約したターン番号
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    session: Mapped["Session"] = relationship(back_populates="summary")


# =============================================================================
# 旅行企画モード用モデル
# =============================================================================


class TravelPlanRequest(Base):
    """旅行企画リクエスト"""

    __tablename__ = "travel_plan_requests"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sessions.id", ondelete="CASCADE"),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    # 元のユーザー入力
    raw_request: Mapped[str] = mapped_column(
        Text,
    )
    # 構造化された制約（Translator Agentが生成）
    constraints: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )  # 日程、予算、人数、地域など
    # 構造化された希望（Translator Agentが生成）
    wishes: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )  # やりたいこと、体験したいこと
    # ステータス
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
    )  # pending, processing, completed, failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    plans: Mapped[list["TravelPlan"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )
    plan_runs: Mapped[list["PlanRun"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )
    search_results: Mapped[list["TravelSearchResult"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )


class TravelPlan(Base):
    """生成された旅程"""

    __tablename__ = "travel_plans"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("travel_plan_requests.id", ondelete="CASCADE"),
    )
    # 旅程データ
    itinerary: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )  # 日ごとのスケジュール、POI、移動など
    # 説明・根拠
    rationale: Mapped[str] = mapped_column(
        Text,
        default="",
    )  # なぜこの旅程を選んだか
    # スコア
    score: Mapped[float] = mapped_column(
        default=0.0,
    )  # 総合スコア
    score_breakdown: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )  # スコアの内訳
    # バージョン（複数案生成時）
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )
    is_selected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )  # ユーザーが選択した案か
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )

    request: Mapped["TravelPlanRequest"] = relationship(back_populates="plans")


class POICache(Base):
    """POI（Point of Interest）キャッシュ

    PTSアーキテクチャ対応（RealTravel/Google Local形式）:
    - destination（検索目的地）でPOIをグループ化
    - 同じ(destination, category, name)の組み合わせで一意
    - 検索のたびに上書き更新可能
    - 構造化されたPOIメタデータ（rating, price_level, hours等）
    """

    __tablename__ = "poi_cache"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    # 検索目的地（京都、箱根など）
    destination: Mapped[str] = mapped_column(
        String(255),
        default="",
        index=True,
    )
    # === 基本情報 ===
    name: Mapped[str] = mapped_column(
        String(255),
    )
    category: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )  # activity, food, hotel, transportation
    description: Mapped[str] = mapped_column(
        Text,
        default="",
    )  # POIの説明文

    # === 位置情報 ===
    location: Mapped[str] = mapped_column(
        String(255),
        default="",
    )  # 地区名・エリア名
    address: Mapped[str] = mapped_column(
        Text,
        default="",
    )  # 詳細住所
    latitude: Mapped[float | None] = mapped_column(
        nullable=True,
    )  # 緯度
    longitude: Mapped[float | None] = mapped_column(
        nullable=True,
    )  # 経度

    # === 評価・レビュー情報（PTS形式） ===
    rating: Mapped[float | None] = mapped_column(
        nullable=True,
    )  # 評価 (1.0-5.0)
    review_count: Mapped[int | None] = mapped_column(
        nullable=True,
    )  # レビュー数

    # === 価格情報 ===
    price_level: Mapped[int | None] = mapped_column(
        nullable=True,
    )  # 価格帯 (1=安い, 2=普通, 3=高め, 4=高級)
    price_range: Mapped[str] = mapped_column(
        String(100),
        default="",
    )  # 価格帯テキスト（例: "¥1,000〜2,000"）
    budget_per_person: Mapped[int | None] = mapped_column(
        nullable=True,
    )  # 1人あたり予算（円）

    # === 時間情報 ===
    hours: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # 営業時間 {"mon": "9:00-18:00", "tue": "9:00-18:00", ...}
    duration_minutes: Mapped[int | None] = mapped_column(
        nullable=True,
    )  # 所要時間（分）

    # === 特徴・タグ（PTS形式） ===
    features: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )  # 特徴タグ ["WiFi", "駐車場", "クレジットカード可", ...]
    tags: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )  # 一般タグ ["観光名所", "歴史", "自然", ...]

    # === 体験情報（本システム独自） ===
    experiences: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )  # 体験タグ ["歴史的建造物巡り", "写真映えスポット", ...]
    embedding: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # 体験ベースの埋め込みベクトル

    # === ソース情報 ===
    source_url: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    source_name: Mapped[str] = mapped_column(
        String(100),
        default="",
    )  # tavily, etc.

    # === メタデータ ===
    details: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )  # その他の詳細情報（後方互換性）
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )
    experiences_extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )


class TravelSearchResult(Base):
    """旅行検索結果（TravelPlanRequestとPOIの紐付け）

    PTSアーキテクチャ対応:
    - 検索リクエストごとに見つかったPOIを記録
    - Rerankerによるスコアを保存
    - Plannerが参照するPOIプールとして機能
    """

    __tablename__ = "travel_search_results"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("travel_plan_requests.id", ondelete="CASCADE"),
        index=True,
    )
    poi_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("poi_cache.id", ondelete="CASCADE"),
        index=True,
    )
    # カテゴリ（検索時のカテゴリ）
    category: Mapped[str] = mapped_column(
        String(50),
    )  # activity, food, hotel, transportation
    # Rerankerによるスコア
    rerank_score: Mapped[float] = mapped_column(
        default=0.0,
    )  # 嗜好ベースのスコア（0.0〜1.0）
    # 制約充足スコア
    constraint_score: Mapped[float] = mapped_column(
        default=0.0,
    )  # 制約を満たす度合い（0.0〜1.0）
    # 総合スコア
    total_score: Mapped[float] = mapped_column(
        default=0.0,
    )  # rerank_score * weight + constraint_score * weight
    # Plannerで選択されたか
    is_selected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    # 選択理由（Explainer用）
    selection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )

    # リレーション
    request: Mapped["TravelPlanRequest"] = relationship(back_populates="search_results")
    poi: Mapped["POICache"] = relationship()


class PlanRun(Base):
    """旅程生成の実行記録（観測性・再現性）"""

    __tablename__ = "plan_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("travel_plan_requests.id", ondelete="CASCADE"),
    )
    # 実行情報
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="running",
    )  # running, completed, failed
    # メトリクス
    metrics: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )  # 処理時間、LLM呼び出し回数など
    # 設定スナップショット
    config_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )  # 使用したモデル、パラメータなど
    # エラー情報
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    request: Mapped["TravelPlanRequest"] = relationship(back_populates="plan_runs")
    events: Mapped[list["SessionEvent"]] = relationship(
        back_populates="plan_run",
        cascade="all, delete-orphan",
    )


class SessionEvent(Base):
    """セッションイベント（各ステップのトレース）"""

    __tablename__ = "session_events"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    plan_run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("plan_runs.id", ondelete="CASCADE"),
    )
    # ステップ情報
    step_name: Mapped[str] = mapped_column(
        String(100),
    )  # translate, search_activity, normalize, etc.
    agent_name: Mapped[str] = mapped_column(
        String(100),
    )  # TranslatorAgent, SearchAgent, etc.
    # 入出力要約（フルログは保存しない）
    input_summary: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    output_summary: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    # メトリクス
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    # ステータス
    status: Mapped[str] = mapped_column(
        String(20),
        default="completed",
    )  # completed, failed, skipped
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )

    plan_run: Mapped["PlanRun"] = relationship(back_populates="events")
