from datetime import datetime
from uuid import uuid4

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
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
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
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
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
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
        default=datetime.utcnow,
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
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    session: Mapped["Session"] = relationship(back_populates="summary")
