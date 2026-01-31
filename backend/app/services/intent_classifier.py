"""意図分類サービス

ユーザーメッセージから会話の意図を判定する。
旅行相談（TRAVEL_PLANNING）か一般会話（GENERAL_CHAT）かを分類。
"""

import logging
import re

from app.schemas.unified_chat import ChatIntent, IntentClassificationResult

logger = logging.getLogger(__name__)


# 旅行企画の意図を示すキーワード（優先度高い順）
TRAVEL_PLANNING_KEYWORDS = [
    # 明確な旅行相談
    "旅行",
    "旅",
    "行きたい",
    "訪れたい",
    "観光",
    "旅程",
    "プラン",
    "スケジュール",
    "日程",
    # 目的地
    "に行く",
    "へ行く",
    "に泊まる",
    "宿泊",
    # 具体的な計画
    "予算",
    "何日",
    "何泊",
    "いつ行",
    "どこに行",
    # 交通
    "飛行機",
    "新幹線",
    "電車で",
    "車で",
    "レンタカー",
    # 宿泊
    "ホテル",
    "旅館",
    "民宿",
    "宿",
]

# プラン生成を明示的に要求するキーワード
PLAN_GENERATION_KEYWORDS = [
    "プランを作",
    "プラン作って",
    "旅程を作",
    "計画を立て",
    "スケジュールを作",
    "作って",
    "考えて",
    "お願い",
    "提案して",
    "教えて",
]

# 地名パターン（日本の主要観光地）
DESTINATION_PATTERNS = [
    r"(東京|京都|大阪|北海道|沖縄|奈良|金沢|広島|鎌倉|箱根|伊豆|軽井沢|富士山|横浜|神戸|長野|名古屋|福岡|札幌|仙台)",
    r"(温泉|海|山|島|湖|川|滝|森|高原)",
    r"\w{2,4}(県|市|町|村)に",
]


class IntentClassifier:
    """意図分類器"""

    def classify(
        self,
        message: str,
        conversation_context: list[dict] | None = None,
    ) -> IntentClassificationResult:
        """
        メッセージから意図を分類する

        Args:
            message: ユーザーメッセージ
            conversation_context: 会話履歴（直近のメッセージリスト）

        Returns:
            IntentClassificationResult: 分類結果
        """
        keywords_matched = []
        score = 0.0

        # 1. 旅行キーワードのチェック
        for keyword in TRAVEL_PLANNING_KEYWORDS:
            if keyword in message:
                keywords_matched.append(keyword)
                score += 0.15

        # 2. 地名パターンのチェック
        for pattern in DESTINATION_PATTERNS:
            if re.search(pattern, message):
                match = re.search(pattern, message)
                if match:
                    keywords_matched.append(match.group())
                    score += 0.2

        # 3. プラン生成要求のチェック
        for keyword in PLAN_GENERATION_KEYWORDS:
            if keyword in message:
                keywords_matched.append(keyword)
                score += 0.25

        # 4. 会話コンテキストのチェック（直前が旅行相談だった場合）
        if conversation_context:
            recent_travel_context = self._check_recent_travel_context(
                conversation_context
            )
            if recent_travel_context:
                score += 0.3
                keywords_matched.append("[会話継続]")

        # スコアを0-1に正規化
        confidence = min(score, 1.0)

        # 閾値判定（0.3以上で旅行企画と判定）
        if confidence >= 0.3:
            intent = ChatIntent.TRAVEL_PLANNING
            reasoning = f"旅行関連キーワード検出: {', '.join(keywords_matched[:5])}"
        else:
            intent = ChatIntent.GENERAL_CHAT
            reasoning = "旅行関連のキーワードが少ないため一般会話として処理"

        logger.debug(
            f"Intent classification: {intent.value} (confidence={confidence:.2f}, "
            f"keywords={keywords_matched})"
        )

        return IntentClassificationResult(
            intent=intent,
            confidence=confidence,
            keywords_matched=keywords_matched[:10],  # 上位10個まで
            reasoning=reasoning,
        )

    def _check_recent_travel_context(self, context: list[dict]) -> bool:
        """直近の会話が旅行相談かどうかをチェック"""
        # 直近3メッセージを確認
        recent_messages = context[-3:] if len(context) > 3 else context

        for msg in recent_messages:
            content = msg.get("content", "")
            for keyword in TRAVEL_PLANNING_KEYWORDS[:10]:  # 主要キーワードのみ
                if keyword in content:
                    return True
        return False

    def should_generate_plan(self, message: str) -> bool:
        """プラン生成が明示的に要求されているか判定"""
        return any(keyword in message for keyword in PLAN_GENERATION_KEYWORDS)


# シングルトンインスタンス
intent_classifier = IntentClassifier()
