"""統合チャットシステム用スキーマ

モード切替を廃止し、自然な会話の中で自動的に
嗜好学習と旅行企画を行う統合チャットシステム。
"""

from enum import Enum

from pydantic import BaseModel, Field

from .preference import PreferenceCategory
from .travel_planning import TravelPlanResponse


class ChatIntent(str, Enum):
    """会話の意図分類"""

    TRAVEL_PLANNING = "travel_planning"  # 旅行相談・企画
    GENERAL_CHAT = "general_chat"  # 一般会話（嗜好学習含む）


class LearnedPreference(BaseModel):
    """学習した嗜好（トースト通知用）"""

    category: PreferenceCategory
    tag: str
    weight: float = 1.0
    is_new: bool = True  # 新規か更新か


class UnifiedChatRequest(BaseModel):
    """統合チャットリクエスト"""

    user_id: str
    message: str
    session_id: str | None = None


class UnifiedChatResponse(BaseModel):
    """統合チャットレスポンス"""

    user_id: str
    session_id: str
    assistant_message: str
    intent: ChatIntent  # 判定された意図
    learned_preferences: list[LearnedPreference] = Field(
        default_factory=list, description="今回学習した嗜好（トースト通知用）"
    )
    plan: TravelPlanResponse | None = Field(
        default=None, description="生成されたプラン（旅行企画完了時のみ）"
    )
    plan_status: str | None = Field(
        default=None, description="プラン生成状況: chatting, planning, completed"
    )


class IntentClassificationResult(BaseModel):
    """意図分類結果"""

    intent: ChatIntent
    confidence: float = Field(ge=0.0, le=1.0)
    keywords_matched: list[str] = Field(default_factory=list)
    reasoning: str = ""
