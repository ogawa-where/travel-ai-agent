"""
Custom Exceptions

CLAUDE.md セクション8.7に基づくカスタム例外。
エラーハンドリングを統一し、ユーザーフレンドリーなメッセージを提供。
"""


class TravelAgentError(Exception):
    """アプリケーション基底例外"""

    def __init__(
        self,
        message: str,
        user_message: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.user_message = user_message or message
        self.details = details or {}


# =============================================================================
# LLM関連エラー
# =============================================================================


class LLMError(TravelAgentError):
    """LLM関連の基底エラー"""

    pass


class LLMUnavailableError(LLMError):
    """LLMサービスが利用不可"""

    def __init__(
        self,
        message: str = "No healthy Ollama workers available",
        details: dict | None = None,
    ):
        super().__init__(
            message=message,
            user_message="現在LLMサービスが利用できません。しばらくしてから再度お試しください。",
            details=details,
        )


class LLMGenerationError(LLMError):
    """LLM生成失敗"""

    def __init__(
        self,
        message: str = "LLM generation failed",
        attempts: int = 0,
        details: dict | None = None,
    ):
        super().__init__(
            message=message,
            user_message="応答の生成に失敗しました。もう一度お試しください。",
            details={"attempts": attempts, **(details or {})},
        )


class LLMParseError(LLMError):
    """LLM出力のパースエラー"""

    def __init__(
        self,
        message: str = "Failed to parse LLM output",
        raw_output: str | None = None,
        attempts: int = 0,
        details: dict | None = None,
    ):
        super().__init__(
            message=message,
            user_message="応答の解析に失敗しました。もう一度お試しください。",
            details={
                "raw_output_preview": raw_output[:200] if raw_output else None,
                "attempts": attempts,
                **(details or {}),
            },
        )


# =============================================================================
# 検索関連エラー
# =============================================================================


class SearchError(TravelAgentError):
    """検索関連の基底エラー"""

    pass


class SearchPartialFailureError(SearchError):
    """検索の部分的失敗（一部のエージェントが失敗）"""

    def __init__(
        self,
        message: str = "Some search agents failed",
        failed_categories: list[str] | None = None,
        successful_categories: list[str] | None = None,
        details: dict | None = None,
    ):
        super().__init__(
            message=message,
            user_message="一部の検索で問題が発生しましたが、他の結果で続行します。",
            details={
                "failed_categories": failed_categories or [],
                "successful_categories": successful_categories or [],
                **(details or {}),
            },
        )


class SearchAllFailedError(SearchError):
    """全ての検索が失敗"""

    def __init__(
        self,
        message: str = "All search agents failed",
        details: dict | None = None,
    ):
        super().__init__(
            message=message,
            user_message="検索サービスに問題が発生しています。しばらくしてから再度お試しください。",
            details=details,
        )


# =============================================================================
# メモリ関連エラー
# =============================================================================


class MemoryError(TravelAgentError):
    """メモリ関連の基底エラー"""

    pass


class SessionNotFoundError(MemoryError):
    """セッションが見つからない"""

    def __init__(
        self,
        session_id: str,
        details: dict | None = None,
    ):
        super().__init__(
            message=f"Session not found: {session_id}",
            user_message="セッションが見つかりません。新しいセッションを開始してください。",
            details={"session_id": session_id, **(details or {})},
        )


class UserNotFoundError(MemoryError):
    """ユーザーが見つからない"""

    def __init__(
        self,
        user_id: str,
        details: dict | None = None,
    ):
        super().__init__(
            message=f"User not found: {user_id}",
            user_message="ユーザーが見つかりません。",
            details={"user_id": user_id, **(details or {})},
        )


# =============================================================================
# バリデーションエラー
# =============================================================================


class ValidationError(TravelAgentError):
    """バリデーションエラー"""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(
            message=message,
            user_message=f"入力内容に問題があります: {message}",
            details={"field": field, **(details or {})},
        )
