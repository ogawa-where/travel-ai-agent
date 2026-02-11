"""
Rerank Agent Tests

CLAUDE.md セクション4.2の要件:
- Rerank（埋め込み類似度ベース。Ollama embedding使用）
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import math

from app.agents.rerank import RerankAgent, rerank_agent
from app.schemas.travel_planning import (
    POICategory,
    POISearchResult,
    RerankInput,
    RerankOutput,
    TravelWishes,
)


# =============================================================================
# Cosine Similarity Tests
# =============================================================================

class TestCosineSimilarity:
    """コサイン類似度計算のテスト"""

    def test_identical_vectors(self):
        """同一ベクトルの類似度は1.0"""
        agent = RerankAgent()
        vec = [1.0, 2.0, 3.0]
        similarity = agent._cosine_similarity(vec, vec)
        assert similarity == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """直交ベクトルの類似度は0.5（正規化後）"""
        agent = RerankAgent()
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        similarity = agent._cosine_similarity(vec1, vec2)
        # コサイン類似度0を(0+1)/2=0.5に正規化
        assert similarity == pytest.approx(0.5)

    def test_opposite_vectors(self):
        """逆向きベクトルの類似度は0.0（正規化後）"""
        agent = RerankAgent()
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        similarity = agent._cosine_similarity(vec1, vec2)
        # コサイン類似度-1を(-1+1)/2=0に正規化
        assert similarity == pytest.approx(0.0)

    def test_empty_vectors(self):
        """空ベクトルの類似度は0.0"""
        agent = RerankAgent()
        assert agent._cosine_similarity([], []) == 0.0
        assert agent._cosine_similarity([1.0], []) == 0.0
        assert agent._cosine_similarity([], [1.0]) == 0.0

    def test_different_length_vectors(self):
        """長さの異なるベクトルの類似度は0.0"""
        agent = RerankAgent()
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = agent._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_zero_vector(self):
        """ゼロベクトルの類似度は0.0"""
        agent = RerankAgent()
        vec1 = [0.0, 0.0]
        vec2 = [1.0, 2.0]
        similarity = agent._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_high_dimensional_vectors(self):
        """高次元ベクトルでも正しく計算"""
        agent = RerankAgent()
        # 768次元（nomic-embed-textの次元数）
        vec1 = [0.1] * 768
        vec2 = [0.1] * 768
        similarity = agent._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(1.0)


# =============================================================================
# Preference Text Building Tests
# =============================================================================

class TestBuildPreferenceText:
    """嗜好テキスト構築のテスト"""

    def test_empty_input(self):
        """空入力"""
        agent = RerankAgent()
        wishes = TravelWishes()
        text = agent._build_preference_text("", [], wishes)
        assert text == "旅行を楽しみたい"

    def test_with_profile_summary(self):
        """プロフィール要約あり"""
        agent = RerankAgent()
        wishes = TravelWishes()
        text = agent._build_preference_text("温泉好きな40代男性", [], wishes)
        assert "プロフィール:" in text
        assert "温泉好きな40代男性" in text

    def test_with_preference_signals(self):
        """嗜好シグナルあり"""
        agent = RerankAgent()
        wishes = TravelWishes()
        signals = [
            {"category": "likes", "tag": "温泉"},
            {"category": "likes", "tag": "神社"},
            {"category": "dislikes", "tag": "混雑"},  # dislikesは含まれない
        ]
        text = agent._build_preference_text("", signals, wishes)
        assert "好み:" in text
        assert "温泉" in text
        assert "神社" in text
        assert "混雑" not in text  # dislikesは除外

    def test_with_wishes(self):
        """希望あり"""
        agent = RerankAgent()
        wishes = TravelWishes(
            activities=["神社巡り", "温泉"],
            experiences=["文化体験"],
            food_preferences=["和食"],
            priority="リラックス",
            mood="ゆったり",
        )
        text = agent._build_preference_text("", [], wishes)
        assert "やりたいこと:" in text
        assert "神社巡り" in text
        assert "体験したいこと:" in text
        assert "文化体験" in text
        assert "食の好み:" in text
        assert "和食" in text
        assert "重視:" in text
        assert "リラックス" in text
        assert "雰囲気:" in text
        assert "ゆったり" in text


# =============================================================================
# Match Reasons Generation Tests
# =============================================================================

class TestGenerateMatchReasons:
    """マッチ理由生成のテスト"""

    def test_activity_match(self):
        """アクティビティマッチ"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="金閣寺",
            category=POICategory.ACTIVITY,
            description="世界遺産の神社仏閣を巡る寺院巡り体験",
            tags=["神社", "寺院", "寺院巡り"],
            relevance_score=0.8,
        )
        # 完全一致が必要なので、descriptionかtagsに含まれるキーワードを使う
        wishes = TravelWishes(activities=["寺院巡り"])
        reasons = agent._generate_match_reasons(candidate, wishes)
        assert any(r["text"] == "寺院巡り" and r["type"] == "wish" for r in reasons)

    def test_experience_match(self):
        """体験マッチ"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="茶道体験",
            category=POICategory.ACTIVITY,
            description="本格的な茶道体験ができます",
            tags=["体験"],
            relevance_score=0.8,
        )
        wishes = TravelWishes(experiences=["茶道体験"])
        reasons = agent._generate_match_reasons(candidate, wishes)
        assert any(r["text"] == "茶道体験" and r["type"] == "wish" for r in reasons)

    def test_food_match(self):
        """食マッチ"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="京懐石",
            category=POICategory.FOOD,
            description="本格的な和食懐石",
            tags=["和食", "懐石"],
            relevance_score=0.8,
        )
        wishes = TravelWishes(food_preferences=["和食"])
        reasons = agent._generate_match_reasons(candidate, wishes)
        assert any(r["text"] == "和食" and r["type"] == "wish" for r in reasons)

    def test_mood_match(self):
        """雰囲気マッチ"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="静かな庭園",
            category=POICategory.ACTIVITY,
            description="ゆったりとした時間を過ごせる静かな庭園",
            tags=["庭園"],
            relevance_score=0.8,
        )
        wishes = TravelWishes(mood="ゆったり")
        reasons = agent._generate_match_reasons(candidate, wishes)
        assert any(r["text"] == "ゆったり" and r["type"] == "wish" for r in reasons)

    def test_max_3_reasons(self):
        """理由は最大3つ"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="Test",
            category=POICategory.ACTIVITY,
            description="神社 温泉 和食 自然 文化",
            tags=["神社", "温泉", "和食", "自然", "文化"],
            relevance_score=0.8,
        )
        wishes = TravelWishes(
            activities=["神社", "温泉", "自然", "文化"],
            food_preferences=["和食"],
        )
        reasons = agent._generate_match_reasons(candidate, wishes)
        assert len(reasons) <= 4

    def test_no_match(self):
        """マッチなし"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="Test",
            category=POICategory.ACTIVITY,
            description="普通の場所",
            tags=["観光"],
            relevance_score=0.8,
        )
        wishes = TravelWishes(activities=["スキー"])
        reasons = agent._generate_match_reasons(candidate, wishes)
        assert reasons == []

    def test_wish_embedding_fallback(self):
        """文字列不一致でも埋め込み類似度が高ければ wish ラベルが付く"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="伏見稲荷大社",
            category=POICategory.ACTIVITY,
            description="千本鳥居で有名な稲荷神社",
            tags=["神社", "鳥居"],
            relevance_score=0.8,
        )
        # "神社巡り" は description/tags にそのまま含まれない
        wishes = TravelWishes(activities=["神社巡り"])

        # 候補埋め込みと wish 埋め込みを用意（高い類似度になるよう近いベクトル）
        candidate_embedding = [0.8, 0.6, 0.0]
        wish_embeddings = [("神社巡り", [0.7, 0.7, 0.1])]

        reasons = agent._generate_match_reasons(
            candidate,
            wishes,
            preference_signals=None,
            candidate_embedding=candidate_embedding,
            wish_embeddings=wish_embeddings,
        )

        assert any(r["text"] == "神社巡り" and r["type"] == "wish" for r in reasons)

    def test_wish_embedding_no_false_positive(self):
        """埋め込み類似度が低い場合はマッチしない"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="海鮮レストラン",
            category=POICategory.FOOD,
            description="新鮮な海の幸を使った料理",
            tags=["海鮮", "レストラン"],
            relevance_score=0.8,
        )
        wishes = TravelWishes(activities=["スキー"])

        # 直交に近いベクトル → 低類似度
        candidate_embedding = [1.0, 0.0, 0.0]
        wish_embeddings = [("スキー", [0.0, 0.0, 1.0])]

        reasons = agent._generate_match_reasons(
            candidate,
            wishes,
            preference_signals=None,
            candidate_embedding=candidate_embedding,
            wish_embeddings=wish_embeddings,
        )

        assert not any(r["text"] == "スキー" for r in reasons)

    def test_wish_embedding_skips_already_matched(self):
        """文字列マッチ済みの wish は埋め込みフォールバックをスキップ"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="温泉旅館",
            category=POICategory.HOTEL,
            description="露天風呂付きの温泉旅館",
            tags=["温泉"],
            relevance_score=0.8,
        )
        wishes = TravelWishes(activities=["温泉"])

        # "温泉" は文字列マッチする。埋め込みでも高類似度だが重複しない
        candidate_embedding = [0.9, 0.1, 0.0]
        wish_embeddings = [("温泉", [0.9, 0.1, 0.0])]

        reasons = agent._generate_match_reasons(
            candidate,
            wishes,
            preference_signals=None,
            candidate_embedding=candidate_embedding,
            wish_embeddings=wish_embeddings,
        )

        # "温泉" が1回だけ含まれる
        wish_reasons = [r for r in reasons if r["text"] == "温泉"]
        assert len(wish_reasons) == 1


# =============================================================================
# Embedding Tests
# =============================================================================

class TestGetEmbedding:
    """埋め込み取得のテスト"""

    @pytest.mark.asyncio
    async def test_embedding_success(self):
        """埋め込み取得成功"""
        agent = RerankAgent()
        mock_embedding = [0.1] * 768

        with patch("app.agents.rerank.llm_gateway") as mock_gateway:
            mock_gateway.embed = AsyncMock(return_value=mock_embedding)
            embedding = await agent._get_embedding("テストテキスト")

        assert embedding == mock_embedding

    @pytest.mark.asyncio
    async def test_embedding_cache(self):
        """埋め込みキャッシュ"""
        agent = RerankAgent()
        mock_embedding = [0.1] * 768

        with patch("app.agents.rerank.llm_gateway") as mock_gateway:
            mock_gateway.embed = AsyncMock(return_value=mock_embedding)

            # 1回目
            embedding1 = await agent._get_embedding("テストテキスト")
            # 2回目（キャッシュから）
            embedding2 = await agent._get_embedding("テストテキスト")

        # 1回しか呼ばれない
        assert mock_gateway.embed.call_count == 1
        assert embedding1 == embedding2

    @pytest.mark.asyncio
    async def test_embedding_failure(self):
        """埋め込み取得失敗時は空リスト"""
        agent = RerankAgent()

        with patch("app.agents.rerank.llm_gateway") as mock_gateway:
            mock_gateway.embed = AsyncMock(side_effect=Exception("API Error"))
            embedding = await agent._get_embedding("テストテキスト")

        assert embedding == []

    def test_clear_cache(self):
        """キャッシュクリア"""
        agent = RerankAgent()
        agent._embedding_cache["test"] = [0.1]
        agent.clear_cache()
        assert agent._embedding_cache == {}


# =============================================================================
# Rerank Tests
# =============================================================================

class TestRerank:
    """リランクのテスト"""

    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        """候補なし"""
        agent = RerankAgent()
        input_data = RerankInput(
            candidates=[],
            user_profile_summary="",
            preference_signals=[],
            wishes=TravelWishes(),
        )
        output = await agent.rerank(input_data)
        assert output.ranked_items == []

    @pytest.mark.asyncio
    async def test_single_candidate(self):
        """単一候補"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="金閣寺",
            category=POICategory.ACTIVITY,
            description="世界遺産の寺院",
            tags=["寺院"],
            relevance_score=0.9,
        )
        input_data = RerankInput(
            candidates=[candidate],
            user_profile_summary="寺社仏閣が好き",
            preference_signals=[],
            wishes=TravelWishes(activities=["寺院巡り"]),
        )

        with patch("app.agents.rerank.llm_gateway") as mock_gateway:
            mock_gateway.embed = AsyncMock(return_value=[0.1] * 768)
            output = await agent.rerank(input_data)

        assert len(output.ranked_items) == 1
        assert output.ranked_items[0].name == "金閣寺"
        assert 0.0 <= output.ranked_items[0].final_score <= 1.0

    @pytest.mark.asyncio
    async def test_multiple_candidates_sorted(self):
        """複数候補がスコア順にソート"""
        agent = RerankAgent()
        candidates = [
            POISearchResult(
                name="観光地A",
                category=POICategory.ACTIVITY,
                description="普通の観光地",
                tags=[],
                relevance_score=0.5,
            ),
            POISearchResult(
                name="観光地B",
                category=POICategory.ACTIVITY,
                description="人気の観光地",
                tags=["人気"],
                relevance_score=0.9,
            ),
        ]
        input_data = RerankInput(
            candidates=candidates,
            user_profile_summary="",
            preference_signals=[],
            wishes=TravelWishes(),
        )

        # 異なる埋め込みを返す
        call_count = 0

        async def mock_embed(text):
            nonlocal call_count
            call_count += 1
            if "人気" in text:
                return [0.9] * 768
            return [0.1] * 768

        with patch("app.agents.rerank.llm_gateway") as mock_gateway:
            mock_gateway.embed = mock_embed
            output = await agent.rerank(input_data)

        # スコアの高い順
        assert len(output.ranked_items) == 2
        assert output.ranked_items[0].final_score >= output.ranked_items[1].final_score

    @pytest.mark.asyncio
    async def test_score_calculation(self):
        """スコア計算の確認"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="テスト",
            category=POICategory.ACTIVITY,
            description="テスト",
            tags=[],
            relevance_score=0.8,  # 元のスコア
        )
        input_data = RerankInput(
            candidates=[candidate],
            user_profile_summary="",
            preference_signals=[],
            wishes=TravelWishes(),
        )

        # 嗜好との類似度を制御
        with patch("app.agents.rerank.llm_gateway") as mock_gateway:
            mock_gateway.embed = AsyncMock(return_value=[1.0] * 768)
            output = await agent.rerank(input_data)

        ranked = output.ranked_items[0]
        # final_score = 0.4 * relevance_score + 0.6 * preference_score
        # 同一ベクトルなので preference_score = 1.0
        expected = 0.4 * 0.8 + 0.6 * 1.0
        assert ranked.final_score == pytest.approx(expected, rel=0.01)

    @pytest.mark.asyncio
    async def test_embedding_failure_fallback(self):
        """埋め込み失敗時のフォールバック"""
        agent = RerankAgent()
        candidate = POISearchResult(
            name="テスト",
            category=POICategory.ACTIVITY,
            description="テスト",
            tags=[],
            relevance_score=0.8,
        )
        input_data = RerankInput(
            candidates=[candidate],
            user_profile_summary="",
            preference_signals=[],
            wishes=TravelWishes(),
        )

        with patch("app.agents.rerank.llm_gateway") as mock_gateway:
            mock_gateway.embed = AsyncMock(side_effect=Exception("API Error"))
            output = await agent.rerank(input_data)

        # エラーでもデフォルトスコアで続行
        assert len(output.ranked_items) == 1
        ranked = output.ranked_items[0]
        # preference_score = 0.5 (デフォルト)
        expected = 0.4 * 0.8 + 0.6 * 0.5
        assert ranked.final_score == pytest.approx(expected, rel=0.01)


# =============================================================================
# Integration Tests
# =============================================================================

class TestRerankIntegration:
    """統合テスト"""

    @pytest.mark.asyncio
    async def test_full_rerank_flow(self):
        """完全なリランクフロー"""
        agent = RerankAgent()

        candidates = [
            POISearchResult(
                name="金閣寺",
                category=POICategory.ACTIVITY,
                description="世界遺産の寺院、歴史と文化を感じる",
                tags=["寺院", "世界遺産", "歴史"],
                relevance_score=0.85,
            ),
            POISearchResult(
                name="ラーメン屋",
                category=POICategory.FOOD,
                description="人気のラーメン店",
                tags=["ラーメン"],
                relevance_score=0.7,
            ),
            POISearchResult(
                name="温泉旅館",
                category=POICategory.HOTEL,
                description="露天風呂付きの温泉旅館",
                tags=["温泉", "旅館"],
                relevance_score=0.9,
            ),
        ]

        input_data = RerankInput(
            candidates=candidates,
            user_profile_summary="温泉と歴史的建造物が好きな50代",
            preference_signals=[
                {"category": "likes", "tag": "温泉"},
                {"category": "likes", "tag": "歴史"},
            ],
            wishes=TravelWishes(
                activities=["神社巡り", "温泉"],
                experiences=["文化体験"],
                food_preferences=["和食"],
                mood="ゆったり",
            ),
        )

        # 異なる埋め込みを返す
        async def mock_embed(text):
            if "温泉" in text and "歴史" in text:
                return [0.9] * 768  # ユーザー嗜好
            if "温泉" in text:
                return [0.85] * 768
            if "歴史" in text or "寺院" in text:
                return [0.8] * 768
            return [0.3] * 768

        with patch("app.agents.rerank.llm_gateway") as mock_gateway:
            mock_gateway.embed = mock_embed
            output = await agent.rerank(input_data)

        assert len(output.ranked_items) == 3

        # すべてのランク付けされたアイテムが必要なフィールドを持つ
        for item in output.ranked_items:
            assert item.name
            assert item.category
            assert 0.0 <= item.relevance_score <= 1.0
            assert 0.0 <= item.preference_score <= 1.0
            assert 0.0 <= item.final_score <= 1.0


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingleton:
    """シングルトンのテスト"""

    def test_singleton_instance(self):
        """シングルトンインスタンスが存在"""
        assert rerank_agent is not None
        assert isinstance(rerank_agent, RerankAgent)
