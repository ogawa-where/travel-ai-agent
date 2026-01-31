from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PreferenceCategory(str, Enum):
    """嗜好カテゴリ（長期記憶用）

    嗜好学習モードで抽出するカテゴリ:
    - LIKES: 好きなもの・興味があるもの（食事、場所、興味分野など）
      例: 和食が好き、歴史に興味がある、静かな場所が好き、自然が好き
    - DISLIKES: 嫌いなもの・避けたいもの
      例: 混雑が苦手、辛いものNG、長時間歩くのは苦手
    - TENDENCY: 旅行傾向・スタイル
      例: 計画派、即興派、ゆっくり派、アクティブ派、朝型、夜型

    旅行企画モードで使用するカテゴリ（嗜好学習では抽出しない）:
    - EXPERIENCE_AXIS: 体験軸（旅行企画モードで好みを元に体験を提案する際に使用）

    Note: 短期的な制約（予算3万円、2泊3日など）は TravelConstraints で扱う
    Note: 「体験」は嗜好学習では抽出しない。好みを元に旅行企画モードで提案する
    """

    LIKES = "likes"
    DISLIKES = "dislikes"
    TENDENCY = "tendency"
    # 旅行企画モードで使用（嗜好学習では抽出しない）
    EXPERIENCE_AXIS = "experience_axis"


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
