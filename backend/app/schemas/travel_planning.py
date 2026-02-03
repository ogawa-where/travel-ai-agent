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
    """POI基本情報（PTS/RealTravel形式）

    Google Local / RealTravel データセットの構造を模倣:
    - 基本情報: name, category, description
    - 位置情報: location, address, latitude, longitude
    - 評価情報: rating, review_count
    - 価格情報: price_level, price_range, budget_per_person
    - 時間情報: hours, duration_minutes
    - 特徴情報: features, tags
    """

    # === 基本情報 ===
    name: str
    category: POICategory
    description: str | None = ""

    # === 位置情報 ===
    location: str | None = ""  # 地区名・エリア名
    address: str | None = ""  # 詳細住所
    latitude: float | None = None
    longitude: float | None = None

    # === 評価・レビュー情報（PTS形式） ===
    rating: float | None = None  # 評価 (1.0-5.0)
    review_count: int | None = None  # レビュー数

    # === 価格情報 ===
    price_level: int | None = None  # 価格帯 (1=安い, 2=普通, 3=高め, 4=高級)
    price_range: str | None = ""  # 価格帯テキスト（例: "¥1,000〜2,000"）
    budget_per_person: int | None = None  # 1人あたり予算（円）

    # === 時間情報 ===
    hours: dict | None = None  # 営業時間 {"mon": "9:00-18:00", ...}
    opening_hours: str | None = ""  # 営業時間テキスト（後方互換）
    duration_minutes: int | None = None  # 所要時間（分）

    # === 特徴・タグ（PTS形式） ===
    features: list[str] | None = Field(default_factory=list)  # 特徴タグ
    tags: list[str] | None = Field(default_factory=list)  # 一般タグ

    # === ソース情報 ===
    source_url: str | None = ""

    # === マッチタグ（色分け表示用） ===
    # 形式: [{"text": "温泉好き", "type": "preference"}, {"text": "きりたんぽ", "type": "wish"}]
    match_tags: list[dict] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        """None値をデフォルト値に変換"""
        if self.description is None:
            object.__setattr__(self, "description", "")
        if self.location is None:
            object.__setattr__(self, "location", "")
        if self.address is None:
            object.__setattr__(self, "address", "")
        if self.price_range is None:
            object.__setattr__(self, "price_range", "")
        if self.opening_hours is None:
            object.__setattr__(self, "opening_hours", "")
        if self.features is None:
            object.__setattr__(self, "features", [])
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
    # マッチ理由（タイプ付き）: [{"text": "温泉", "type": "preference"}, {"text": "きりたんぽ", "type": "wish"}]
    match_reasons: list[dict] = Field(default_factory=list)


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


# =============================================================================
# 構造化フォーム入力
# =============================================================================


# =============================================================================
# 情報収集フェーズ用
# =============================================================================


class BasicTravelInfo(BaseModel):
    """旅行の基本情報（フォームから入力）"""

    user_id: str
    area: str = Field(..., description="観光エリア（例: '京都', '箱根'）")
    start_date: str = Field(..., description="出発日 (YYYY-MM-DD)")
    end_date: str = Field(..., description="帰着日 (YYYY-MM-DD)")
    num_people: int = Field(default=1, ge=1, description="人数")
    budget: int = Field(..., description="予算（円）")  # 必須

    # 4カテゴリ（任意）
    activity_preferences: str | None = Field(default=None, description="体験・観光の希望")
    food_preferences: str | None = Field(default=None, description="食の希望")
    accommodation_type: str | None = Field(default=None, description="宿泊の希望")
    transportation: str | None = Field(default=None, description="交通の希望")


class CollectedTravelInfo(BaseModel):
    """収集した旅行情報（対話から収集）"""

    # 基本情報（フォームから）
    area: str = ""
    start_date: str = ""
    end_date: str = ""
    num_people: int = 1

    # 対話で収集する情報
    budget: int | None = None  # 総予算
    budget_per_person: int | None = None  # 一人あたり予算
    transportation: str | None = None  # 移動手段
    accommodation_type: str | None = None  # 宿泊タイプ
    food_preferences: list[str] = Field(default_factory=list)  # 食の好み
    activity_preferences: list[str] = Field(default_factory=list)  # アクティビティの好み
    must_visit: list[str] = Field(default_factory=list)  # 必ず行きたい場所
    avoid: list[str] = Field(default_factory=list)  # 避けたいもの
    pace: str | None = None  # ゆっくり / 普通 / アクティブ
    special_requests: str | None = None  # 特別なリクエスト


class GatheringChatRequest(BaseModel):
    """情報収集チャットリクエスト"""

    user_id: str
    message: str
    session_id: str


class RequiredInfoStatus(BaseModel):
    """4カテゴリの収集状況"""

    has_activities: bool = False  # 体験・観光
    has_food: bool = False  # 食
    has_accommodation: bool = False  # 宿
    has_transportation: bool = False  # 交通

    @property
    def category_count(self) -> int:
        """収集済みカテゴリ数"""
        return sum([self.has_activities, self.has_food, self.has_accommodation, self.has_transportation])

    @property
    def is_complete(self) -> bool:
        """2カテゴリ以上揃っているか"""
        return self.category_count >= 2


class TravelGatheringResponse(BaseModel):
    """情報収集レスポンス"""

    session_id: str
    assistant_message: str
    collected_info: CollectedTravelInfo

    # 新しい必須情報管理
    required_info_status: RequiredInfoStatus = Field(default_factory=RequiredInfoStatus)
    all_required_satisfied: bool = False  # 必須情報が全て揃ったか
    missing_required_info: list[str] = Field(default_factory=list)  # 不足している必須情報
    missing_optional_info: list[str] = Field(default_factory=list)  # 不足している任意情報

    # 既存フィールド（互換性のため維持）
    is_ready: bool = False  # 情報収集が十分かどうか
    missing_info: list[str] = Field(default_factory=list)  # まだ収集していない情報


class PlanGenerationRequest(BaseModel):
    """プラン生成リクエスト"""

    user_id: str
    session_id: str
    collected_info: CollectedTravelInfo


# =============================================================================
# 構造化フォーム入力
# =============================================================================


class TravelPlanFormRequest(BaseModel):
    """構造化フォームからの旅行企画リクエスト"""

    user_id: str

    # 必須フィールド
    destination: str = Field(..., description="行き先（例: '京都府'）")
    start_date: str = Field(..., description="開始日 (YYYY-MM-DD)")
    end_date: str = Field(..., description="終了日 (YYYY-MM-DD)")

    # 任意フィールド
    departure_place: str | None = Field(default=None, description="出発地（例: '秋田県'）")
    budget_total: int | None = Field(default=None, description="総予算（円）")
    num_people: int = Field(default=1, ge=1, description="人数")
    transportation: str | None = Field(
        default=None, description="移動手段（例: '新幹線', 'レンタカー'）"
    )
    accommodation_type: str | None = Field(
        default=None, description="宿泊タイプ（例: '旅館', 'ホテル'）"
    )

    # 自由記述（Translator AgentでWishes抽出）
    free_text: str = Field(default="", description="自由な要望")

    def to_constraints(self) -> TravelConstraints:
        """フォーム入力をTravelConstraintsに直接変換（LLMバイパス）"""
        d_start = datetime.strptime(self.start_date, "%Y-%m-%d")
        d_end = datetime.strptime(self.end_date, "%Y-%m-%d")
        duration = (d_end - d_start).days + 1

        return TravelConstraints(
            destination=self.destination,
            start_date=self.start_date,
            end_date=self.end_date,
            duration_days=duration,
            budget_total=self.budget_total,
            num_people=self.num_people,
            transportation=self.transportation or "",
            other={
                k: v
                for k, v in {
                    "departure_place": self.departure_place,
                    "accommodation_type": self.accommodation_type,
                }.items()
                if v
            },
        )

    def build_raw_request(self) -> str:
        """検索エージェント向けの自然言語テキストを構築"""
        parts = [f"{self.destination}への旅行"]
        parts.append(f"期間: {self.start_date} 〜 {self.end_date}")
        if self.departure_place:
            parts.append(f"出発地: {self.departure_place}")
        if self.budget_total:
            parts.append(f"予算: {self.budget_total:,}円")
        if self.num_people > 1:
            parts.append(f"{self.num_people}人")
        if self.transportation:
            parts.append(f"移動手段: {self.transportation}")
        if self.accommodation_type:
            parts.append(f"宿泊: {self.accommodation_type}")
        if self.free_text:
            parts.append(self.free_text)
        return "。".join(parts)


# =============================================================================
# POI詳細表示
# =============================================================================


class POIDetailResponse(BaseModel):
    """POI詳細レスポンス（DBから取得した情報）

    スコア情報は含まない（フロントエンドでの詳細表示用）
    """

    model_config = ConfigDict(from_attributes=True)

    # 基本情報
    name: str
    category: str
    description: str | None = ""

    # 位置情報
    location: str | None = ""
    address: str | None = ""

    # 評価・レビュー情報
    rating: float | None = None
    review_count: int | None = None

    # 価格情報
    price_level: int | None = None
    price_range: str | None = ""
    budget_per_person: int | None = None

    # 時間情報
    hours: dict | None = None
    duration_minutes: int | None = None

    # 特徴・タグ
    features: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # 体験情報（Experience Extractorで抽出されたもの）
    experiences: list[str] = Field(default_factory=list)

    # ソース情報
    source_url: str | None = ""
    source_name: str | None = ""
