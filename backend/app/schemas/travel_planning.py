"""旅行企画モード用スキーマ"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# 列挙型
# =============================================================================


class POICategory(str, Enum):
    ACTIVITY = "activity"  # 体験・観光
    FOOD = "food"  # 食
    HOTEL = "hotel"  # 宿


class PlanRequestStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# 制約・希望の構造化
# =============================================================================


class TravelConstraints(BaseModel):
    """旅行の制約条件"""

    destination: str = Field(default="", description="目的地・地域")
    start_date: str | None = Field(default=None, description="開始日 (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="終了日 (YYYY-MM-DD)")
    duration_days: int | None = Field(default=None, description="日数")
    budget_total: int | None = Field(default=None, description="総予算（円）")
    budget_per_day: int | None = Field(default=None, description="1日あたり予算（円）")
    num_people: int = Field(default=1, description="人数")
    transportation: str = Field(default="", description="移動手段の制約")
    accommodation_type: str = Field(default="", description="宿泊タイプの希望")
    other: dict = Field(default_factory=dict, description="その他の制約")


class TravelWishes(BaseModel):
    """旅行の希望・やりたいこと"""

    activities: list[str] = Field(
        default_factory=list, description="やりたいアクティビティ"
    )
    experiences: list[str] = Field(default_factory=list, description="体験したいこと")
    food_preferences: list[str] = Field(
        default_factory=list, description="食べたいもの"
    )
    avoid: list[str] = Field(default_factory=list, description="避けたいこと")
    priority: str = Field(default="", description="最も重視すること")
    mood: str = Field(default="", description="旅の雰囲気・テーマ")
    other: dict = Field(default_factory=dict, description="その他の希望")


# =============================================================================
# POI（Point of Interest）
# =============================================================================


class POIBase(BaseModel):
    """POI基本情報"""

    name: str
    category: POICategory
    location: str = ""
    description: str = ""
    price_range: str = ""  # 例: "¥1,000-2,000"
    duration_minutes: int | None = None  # 所要時間
    opening_hours: str = ""
    rating: float | None = None
    tags: list[str] = Field(default_factory=list)
    source_url: str = ""


class POISearchResult(POIBase):
    """検索結果のPOI"""

    relevance_score: float = 0.0  # 検索との関連度
    source_name: str = ""  # 検索ソース


class POIRanked(POIBase):
    """リランク後のPOI"""

    relevance_score: float = 0.0
    preference_score: float = 0.0  # 嗜好との適合度
    final_score: float = 0.0  # 最終スコア
    match_reasons: list[str] = Field(default_factory=list)  # マッチ理由


# =============================================================================
# 旅程（Itinerary）
# =============================================================================


class ItineraryItem(BaseModel):
    """旅程の1項目"""

    time_start: str = ""  # "09:00"
    time_end: str = ""  # "11:00"
    poi: POIBase
    notes: str = ""  # 補足説明
    travel_from_previous: str = ""  # 前の場所からの移動方法・時間


class DayPlan(BaseModel):
    """1日の旅程"""

    day_number: int
    date: str | None = None  # YYYY-MM-DD
    theme: str = ""  # この日のテーマ
    items: list[ItineraryItem] = Field(default_factory=list)
    accommodation: POIBase | None = None  # 宿泊先


class Itinerary(BaseModel):
    """旅程全体"""

    title: str = ""
    summary: str = ""
    days: list[DayPlan] = Field(default_factory=list)
    total_budget_estimate: int | None = None
    highlights: list[str] = Field(default_factory=list)  # ハイライト


# =============================================================================
# API リクエスト/レスポンス
# =============================================================================


class TravelPlanRequestCreate(BaseModel):
    """旅行企画リクエスト作成"""

    user_id: str
    session_id: str | None = None
    raw_request: str  # ユーザーの自然言語入力


class TravelPlanRequestResponse(BaseModel):
    """旅行企画リクエストレスポンス"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    user_id: str
    raw_request: str
    constraints: dict
    wishes: dict
    status: str
    created_at: datetime
    updated_at: datetime


class TravelPlanResponse(BaseModel):
    """旅程レスポンス"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    itinerary: dict
    rationale: str
    score: float
    score_breakdown: dict
    version: int
    is_selected: bool
    created_at: datetime


class TranslateRequestInput(BaseModel):
    """Translator Agent入力"""

    raw_request: str
    user_profile_summary: str = ""
    preference_signals: list[dict] = Field(default_factory=list)


class TranslateRequestOutput(BaseModel):
    """Translator Agent出力"""

    constraints: TravelConstraints
    wishes: TravelWishes
    clarification_needed: list[str] = Field(
        default_factory=list, description="確認が必要な項目"
    )


class SearchQuery(BaseModel):
    """検索クエリ"""

    category: POICategory
    destination: str
    keywords: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)


class SearchResult(BaseModel):
    """検索結果"""

    category: POICategory
    query: str
    items: list[POISearchResult] = Field(default_factory=list)
    source: str = ""
    search_time_ms: int = 0


class RerankInput(BaseModel):
    """Rerank入力"""

    candidates: list[POISearchResult]
    user_profile_summary: str = ""
    preference_signals: list[dict] = Field(default_factory=list)
    wishes: TravelWishes


class RerankOutput(BaseModel):
    """Rerank出力"""

    ranked_items: list[POIRanked]


class PlannerInput(BaseModel):
    """Planner Agent入力"""

    constraints: TravelConstraints
    wishes: TravelWishes
    activities: list[POIRanked] = Field(default_factory=list)
    foods: list[POIRanked] = Field(default_factory=list)
    hotels: list[POIRanked] = Field(default_factory=list)
    user_profile_summary: str = ""


class PlannerOutput(BaseModel):
    """Planner Agent出力"""

    itinerary: Itinerary
    score: float = 0.0
    score_breakdown: dict = Field(default_factory=dict)


class ExplainerInput(BaseModel):
    """Explainer Agent入力"""

    itinerary: Itinerary
    user_profile_summary: str = ""
    preference_signals: list[dict] = Field(default_factory=list)
    wishes: TravelWishes


class ExplainerOutput(BaseModel):
    """Explainer Agent出力"""

    rationale: str  # 全体の説明
    highlights: list[str] = Field(default_factory=list)  # ハイライト
    preference_matches: list[dict] = Field(
        default_factory=list
    )  # どの嗜好にマッチしたか


# =============================================================================
# チャット用
# =============================================================================


class TravelChatRequest(BaseModel):
    """旅行企画チャットリクエスト"""

    user_id: str
    message: str
    session_id: str | None = None


class TravelChatResponse(BaseModel):
    """旅行企画チャットレスポンス"""

    user_id: str
    session_id: str
    assistant_message: str
    plan_request_id: str | None = None  # 企画リクエストが作成された場合
    plan: TravelPlanResponse | None = None  # プランが生成された場合
    status: str = "chatting"  # chatting, planning, completed
