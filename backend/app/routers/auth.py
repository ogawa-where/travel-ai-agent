"""
認証ルーター

シンプルなユーザー名ベースの認証を提供する。
パスワードなしでユーザー名のみで識別。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.domain.models import User, UserProfile, PreferenceSignal

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """ログインリクエスト"""
    username: str = Field(..., min_length=1, max_length=50, description="ユーザー名")


class UserResponse(BaseModel):
    """ユーザーレスポンス"""
    model_config = {"from_attributes": True}

    id: str
    username: str | None
    created_at: str
    updated_at: str
    profile: dict | None
    preference_signals: list[dict]


class LoginResponse(BaseModel):
    """ログインレスポンス"""
    user: UserResponse
    is_new_user: bool
    message: str


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    ユーザー名でログイン（存在しなければ新規作成）

    - username: ユーザー名（1-50文字）
    - 既存ユーザーの場合はそのユーザー情報を返す
    - 新規ユーザーの場合は作成して返す
    """
    username = request.username.strip()

    if not username:
        raise HTTPException(status_code=400, detail="ユーザー名を入力してください")

    # 既存ユーザーを検索
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    is_new_user = False

    if user is None:
        # 新規ユーザー作成
        user = User(username=username)
        db.add(user)
        await db.flush()
        is_new_user = True
        message = f"ようこそ、{username}さん！新しいアカウントを作成しました。"
    else:
        message = f"おかえりなさい、{username}さん！"

    # プロフィールと嗜好シグナルを取得
    await db.refresh(user, ["profile", "preference_signals"])

    # レスポンスを構築
    profile_dict = None
    if user.profile:
        profile_dict = {
            "id": user.profile.id,
            "user_id": user.profile.user_id,
            "summary": user.profile.summary,
            "created_at": user.profile.created_at.isoformat(),
            "updated_at": user.profile.updated_at.isoformat(),
        }

    signals_list = [
        {
            "id": sig.id,
            "user_id": sig.user_id,
            "category": sig.category,
            "tag": sig.tag,
            "weight": sig.weight,
            "evidence": sig.evidence,
            "created_at": sig.created_at.isoformat(),
            "updated_at": sig.updated_at.isoformat(),
        }
        for sig in user.preference_signals
    ]

    await db.commit()

    return LoginResponse(
        user=UserResponse(
            id=user.id,
            username=user.username,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
            profile=profile_dict,
            preference_signals=signals_list,
        ),
        is_new_user=is_new_user,
        message=message,
    )


@router.get("/check/{username}")
async def check_username(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """
    ユーザー名の存在確認

    - exists: ユーザーが存在するか
    """
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    return {"exists": user is not None}
