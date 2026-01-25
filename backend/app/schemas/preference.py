from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PreferenceCategory(str, Enum):
    """嗜好カテゴリ（長期記憶用）

    - LIKES: 好きなもの（食事、アクティビティなど）
    - DISLIKES: 嫌いなもの・避けたいもの
    - EXPERIENCE_AXIS: 体験軸の嗜好（文化/自然/冒険/リラックスなど）
    - TENDENCY: 旅行傾向（計画派か即興派か、ゆっくり派かアクティブ派かなど）

    Note: 短期的な制約（予算3万円、2泊3日など）は TravelConstraints で扱う
    Note: 「体験重視」はプラットフォームの前提なので抽出しない
    """

    LIKES = "likes"
    DISLIKES = "dislikes"
    EXPERIENCE_AXIS = "experience_axis"
    TENDENCY = "tendency"


class PreferenceSignalBase(BaseModel):
    category: PreferenceCategory
    tag: str = Field(..., max_length=100)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: str = ""
    extra_data: dict = Field(default_factory=dict)


class PreferenceSignalCreate(PreferenceSignalBase):
    pass


class PreferenceSignalResponse(PreferenceSignalBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class UserProfileBase(BaseModel):
    summary: str = ""


class UserProfileResponse(UserProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    profile: UserProfileResponse | None = None
    preference_signals: list[PreferenceSignalResponse] = []


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: str | None = None  # 指定しない場合はアクティブなセッションを使用


class ChatResponse(BaseModel):
    user_id: str
    session_id: str  # セッションID
    assistant_message: str
    updated_signals: list[PreferenceSignalResponse] = []


class LearningCompletionRequest(BaseModel):
    """嗜好学習完了リクエスト"""

    user_id: str
    session_id: str


class LearningCompletionResponse(BaseModel):
    """嗜好学習完了レスポンス"""

    user_id: str
    session_id: str
    profile_summary: str
    total_signals: int
    consolidated_signals: int
    removed_signals: list[str] = []
    message: str = "嗜好学習が完了しました"


class MemoryConsolidationResponse(BaseModel):
    """メモリ統合レスポンス"""

    user_id: str
    profile_summary: str
    signals_count: int
    cleaned_signals: int = 0
    limited_signals: int = 0


class FeedbackRequest(BaseModel):
    """フィードバックリクエスト（旅行プランへのフィードバック）"""

    user_id: str
    plan_id: str
    feedback: str


class FeedbackResponse(BaseModel):
    """フィードバックレスポンス"""

    user_id: str
    updated_signals_count: int
    profile_updated: bool
    message: str = "フィードバックを反映しました"
