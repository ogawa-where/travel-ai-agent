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
    TRANSPORTATION = "transportation"  # 交通・アクセス


class PlanRequestStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# 制約・希望の構造化
# =============================================================================


class TravelConstraints(BaseModel):
    """旅行の制約条件（変更不可の硬い制約）

    制約 = ユーザーが変えられない/変えたくない条件
    - 日程、予算上限、人数、移動手段の制限、身体的制限など

    Note: 宿泊タイプの希望などは TravelWishes で扱う
    """

    destination: str | None = Field(default="", description="目的地・地域")
    start_date: str | None = Field(default=None, description="開始日 (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="終了日 (YYYY-MM-DD)")
    duration_days: int | None = Field(default=None, description="日数")
    budget_total: int | None = Field(default=None, description="総予算（円）")
    budget_per_day: int | None = Field(default=None, description="1日あたり予算（円）")
    num_people: int | None = Field(default=1, description="人数")
    transportation: str | None = Field(default="", description="移動手段の制約")
    physical_limitations: list[str] | None = Field(
        default_factory=list, description="身体的制限（車椅子、足が悪いなど）"
    )
    other: dict | None = Field(default_factory=dict, description="その他の制約")

    def model_post_init(self, __context) -> None:
        """None値をデフォルト値に変換"""
        if self.destination is None:
            object.__setattr__(self, "destination", "")
        if self.num_people is None:
            object.__setattr__(self, "num_people", 1)
        if self.transportation is None:
            object.__setattr__(self, "transportation", "")
        if self.physical_limitations is None:
            object.__setattr__(self, "physical_limitations", [])
        if self.other is None:
            object.__setattr__(self, "other", {})


class TravelWishes(BaseModel):
    """旅行の希望・やりたいこと（柔軟な希望）

    希望 = できれば叶えたいが、必須ではない条件
    - やりたいこと、食べたいもの、雰囲気、宿泊タイプなど
    """

    activities: list[str] | None = Field(
        default_factory=list, description="やりたいアクティビティ"
    )
    experiences: list[str] | None = Field(default_factory=list, description="体験したいこと")
    food_preferences: list[str] | None = Field(
        default_factory=list, description="食べたいもの"
    )
    avoid: list[str] | None = Field(default_factory=list, description="避けたいこと")
    accommodation_type: str | None = Field(default="", description="宿泊タイプの希望")
    priority: str | None = Field(default="", description="最も重視すること")
    mood: str | None = Field(default="", description="旅の雰囲気・テーマ")
    other: dict | None = Field(default_factory=dict, description="その他の希望")

    def model_post_init(self, __context) -> None:
        """None値をデフォルト値に変換"""
        if self.activities is None:
            object.__setattr__(self, "activities", [])
        if self.experiences is None:
            object.__setattr__(self, "experiences", [])
        if self.food_preferences is None:
            object.__setattr__(self, "food_preferences", [])
        if self.avoid is None:
            object.__setattr__(self, "avoid", [])
        if self.accommodation_type is None:
            object.__setattr__(self, "accommodation_type", "")
        if self.priority is None:
            object.__setattr__(self, "priority", "")
        if self.mood is None:
            object.__setattr__(self, "mood", "")
        if self.other is None:
            object.__setattr__(self, "other", {})


# =============================================================================
# POI（Point of Interest）
# =============================================================================


class POIBase(BaseModel):
    """POI基本情報"""

    name: str
    category: POICategory
    location: str | None = ""
    description: str | None = ""
    price_range: str | None = ""  # 例: "¥1,000-2,000"
    duration_minutes: int | None = None  # 所要時間
    opening_hours: str | None = ""
    rating: float | None = None
    tags: list[str] | None = Field(default_factory=list)
    source_url: str | None = ""
    latitude: float | None = None
    longitude: float | None = None

    def model_post_init(self, __context) -> None:
        """None値をデフォルト値に変換"""
        if self.location is None:
            object.__setattr__(self, "location", "")
        if self.description is None:
            object.__setattr__(self, "description", "")
        if self.price_range is None:
            object.__setattr__(self, "price_range", "")
        if self.opening_hours is None:
            object.__setattr__(self, "opening_hours", "")
        if self.tags is None:
            object.__setattr__(self, "tags", [])
        if self.source_url is None:
            object.__setattr__(self, "source_url", "")


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

    time_start: str | None = ""  # "09:00"
    time_end: str | None = ""  # "11:00"
    poi: POIBase
    notes: str | None = ""  # 補足説明
    travel_from_previous: str | None = ""  # 前の場所からの移動方法・時間

    def model_post_init(self, __context) -> None:
        """None値をデフォルト値に変換"""
        if self.time_start is None:
            object.__setattr__(self, "time_start", "")
        if self.time_end is None:
            object.__setattr__(self, "time_end", "")
        if self.notes is None:
            object.__setattr__(self, "notes", "")
        if self.travel_from_previous is None:
            object.__setattr__(self, "travel_from_previous", "")


class DayPlan(BaseModel):
    """1日の旅程"""

    day_number: int
    date: str | None = None  # YYYY-MM-DD
    theme: str | None = ""  # この日のテーマ
    items: list[ItineraryItem] = Field(default_factory=list)
    accommodation: POIBase | None = None  # 宿泊先

    def model_post_init(self, __context) -> None:
        """None値をデフォルト値に変換"""
        if self.theme is None:
            object.__setattr__(self, "theme", "")


class Itinerary(BaseModel):
    """旅程全体"""

    title: str | None = ""
    summary: str | None = ""
    days: list[DayPlan] = Field(default_factory=list)
    total_budget_estimate: int | None = None
    highlights: list[str] = Field(default_factory=list)  # ハイライト

    def model_post_init(self, __context) -> None:
        """None値をデフォルト値に変換"""
        if self.title is None:
            object.__setattr__(self, "title", "")
        if self.summary is None:
            object.__setattr__(self, "summary", "")


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
    transportation: list[POIRanked] = Field(default_factory=list)
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


class TravelPlanFeedbackRequest(BaseModel):
    """旅行プランへのフィードバックリクエスト"""

    user_id: str
    plan_id: str
    feedback: str  # ユーザーのフィードバック（良かった点、改善点など）
    rating: int | None = Field(default=None, ge=1, le=5)  # 5段階評価（任意）


class TravelPlanFeedbackResponse(BaseModel):
    """フィードバックレスポンス"""

    user_id: str
    plan_id: str
    updated_signals_count: int
    profile_updated: bool
    message: str = "フィードバックを嗜好に反映しました"


# =============================================================================
# POI フィードバック（👍/👎）
# =============================================================================


class POIFeedbackType(str, Enum):
    """POIフィードバックの種類"""

    GOOD = "good"  # 👍
    BAD = "bad"  # 👎


class POIFeedbackRequest(BaseModel):
    """POI単位のフィードバックリクエスト"""

    user_id: str
    plan_id: str
    poi_name: str  # POI名
    poi_category: POICategory  # activity, food, hotel
    feedback_type: POIFeedbackType  # good or bad
    poi_tags: list[str] = Field(default_factory=list)  # POIのタグ（嗜好学習用）


class POIFeedbackResponse(BaseModel):
    """POIフィードバックレスポンス"""

    user_id: str
    plan_id: str
    poi_name: str
    feedback_type: POIFeedbackType
    learned_preference: dict | None = None  # 学習した嗜好（あれば）
    message: str = "フィードバックを受け付けました"


# =============================================================================
# 個別検索API用
# =============================================================================


class CategorySearchRequest(BaseModel):
    """カテゴリ別検索リクエスト"""

    destination: str = Field(..., description="検索先の目的地")
    keywords: list[str] = Field(default_factory=list, description="検索キーワード")
    constraints: dict = Field(default_factory=dict, description="制約条件")


class CategorySearchResponse(BaseModel):
    """カテゴリ別検索レスポンス"""

    category: POICategory
    destination: str
    items: list[POISearchResult] = Field(default_factory=list)
    total_count: int = 0
    search_time_ms: int = 0
    source: str = "tavily"


# =============================================================================
# 検索推論ループ用スキーマ
# =============================================================================


class SearchVerdict(BaseModel):
    """検索結果の評価（verifyステップの出力）"""

    sufficient: bool = False
    reason: str = ""
    missing_aspects: list[str] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)


class InsufficientCategory(BaseModel):
    """不足カテゴリの情報"""

    category: str
    reason: str = ""
    hints: list[str] = Field(default_factory=list)


class CrossCategoryEvaluation(BaseModel):
    """Phase 2: オーケストレーター横断評価の出力"""

    sufficient_categories: list[str] = Field(default_factory=list)
    insufficient_categories: list[InsufficientCategory] = Field(default_factory=list)

    @property
    def has_insufficient(self) -> bool:
        return len(self.insufficient_categories) > 0
