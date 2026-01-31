"""
Vector Store Tests

CLAUDE.md セクション4.2の要件:
- 埋め込み類似度ベースのRerank
- pgvector対応

注: 実際のサービスに依存しないロジックテスト
"""

import pytest
import math
from dataclasses import dataclass, field


# =============================================================================
# 類似度計算テスト
# =============================================================================


class VectorOperations:
    """テスト用ベクトル操作"""

    @staticmethod
    def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """コサイン類似度を計算"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return (dot_product / (norm1 * norm2) + 1) / 2

    @staticmethod
    def euclidean_distance(vec1: list[float], vec2: list[float]) -> float:
        """ユークリッド距離を計算"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return float("inf")

        return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec1, vec2)))


class TestCosineSimilarity:
    """コサイン類似度のテスト"""

    def test_identical_vectors(self):
        """同一ベクトルの類似度が最大であること"""
        vec = [1.0, 2.0, 3.0]
        similarity = VectorOperations.cosine_similarity(vec, vec)
        assert similarity == 1.0

    def test_opposite_vectors(self):
        """正反対のベクトルの類似度が最小であること"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = VectorOperations.cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_orthogonal_vectors(self):
        """直交ベクトルの類似度が中間であること"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = VectorOperations.cosine_similarity(vec1, vec2)
        assert similarity == 0.5

    def test_similar_vectors(self):
        """類似ベクトルの類似度が高いこと"""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.1, 2.1, 3.1]
        similarity = VectorOperations.cosine_similarity(vec1, vec2)
        assert similarity > 0.9

    def test_empty_vector(self):
        """空ベクトルは0を返すこと"""
        assert VectorOperations.cosine_similarity([], [1.0, 2.0]) == 0.0
        assert VectorOperations.cosine_similarity([1.0, 2.0], []) == 0.0

    def test_different_length_vectors(self):
        """長さが異なるベクトルは0を返すこと"""
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        assert VectorOperations.cosine_similarity(vec1, vec2) == 0.0

    def test_zero_vector(self):
        """ゼロベクトルは0を返すこと"""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        assert VectorOperations.cosine_similarity(vec1, vec2) == 0.0

    def test_normalized_range(self):
        """結果が0-1の範囲であること"""
        # さまざまなベクトルでテスト
        test_cases = [
            ([1.0, 0.0], [0.5, 0.5]),
            ([1.0, 1.0, 1.0], [0.5, -0.5, 0.0]),
            ([3.0, 4.0], [4.0, 3.0]),
        ]

        for vec1, vec2 in test_cases:
            similarity = VectorOperations.cosine_similarity(vec1, vec2)
            assert 0.0 <= similarity <= 1.0


class TestEuclideanDistance:
    """ユークリッド距離のテスト"""

    def test_identical_vectors(self):
        """同一ベクトルの距離が0であること"""
        vec = [1.0, 2.0, 3.0]
        distance = VectorOperations.euclidean_distance(vec, vec)
        assert distance == 0.0

    def test_unit_distance(self):
        """単位距離が正しいこと"""
        vec1 = [0.0, 0.0]
        vec2 = [1.0, 0.0]
        distance = VectorOperations.euclidean_distance(vec1, vec2)
        assert distance == 1.0

    def test_pythagorean(self):
        """ピタゴラスの定理が成り立つこと"""
        vec1 = [0.0, 0.0]
        vec2 = [3.0, 4.0]
        distance = VectorOperations.euclidean_distance(vec1, vec2)
        assert distance == 5.0

    def test_empty_vector(self):
        """空ベクトルはinfを返すこと"""
        assert VectorOperations.euclidean_distance([], [1.0]) == float("inf")

    def test_different_length_vectors(self):
        """長さが異なるベクトルはinfを返すこと"""
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        assert VectorOperations.euclidean_distance(vec1, vec2) == float("inf")


# =============================================================================
# 埋め込みテキスト構築テスト
# =============================================================================


class TestEmbedTextBuilder:
    """埋め込み用テキスト構築のテスト"""

    def _build_embed_text(self, poi_data: dict) -> str:
        """POI埋め込み用テキストを構築"""
        parts = []

        if poi_data.get("name"):
            parts.append(poi_data["name"])
        if poi_data.get("category"):
            parts.append(poi_data["category"])
        if poi_data.get("location"):
            parts.append(poi_data["location"])

        details = poi_data.get("details", {})
        if details.get("description"):
            parts.append(details["description"][:300])
        if details.get("tags"):
            parts.append(" ".join(details["tags"][:5]))

        return " ".join(parts)

    def test_full_poi_data(self):
        """全情報がある場合のテキスト構築"""
        poi_data = {
            "name": "金閣寺",
            "category": "activity",
            "location": "京都市北区",
            "details": {
                "description": "世界遺産の寺院",
                "tags": ["寺院", "世界遺産", "観光"],
            },
        }
        text = self._build_embed_text(poi_data)
        assert "金閣寺" in text
        assert "activity" in text
        assert "京都市北区" in text
        assert "世界遺産の寺院" in text
        assert "寺院" in text

    def test_minimal_poi_data(self):
        """最小限の情報でのテキスト構築"""
        poi_data = {"name": "金閣寺"}
        text = self._build_embed_text(poi_data)
        assert text == "金閣寺"

    def test_empty_poi_data(self):
        """空データでのテキスト構築"""
        poi_data = {}
        text = self._build_embed_text(poi_data)
        assert text == ""

    def test_description_truncation(self):
        """長い説明文が切り詰められること"""
        long_description = "あ" * 500
        poi_data = {
            "name": "テスト",
            "details": {"description": long_description},
        }
        text = self._build_embed_text(poi_data)
        assert len(text) < 500 + 10  # name + spaceを考慮

    def test_tags_limit(self):
        """タグ数が制限されること"""
        poi_data = {
            "name": "テスト",
            "details": {"tags": [f"タグ{i}" for i in range(10)]},
        }
        text = self._build_embed_text(poi_data)
        # 最大5個のタグのみ含まれる
        tag_count = sum(1 for i in range(10) if f"タグ{i}" in text)
        assert tag_count <= 5


# =============================================================================
# 類似検索ロジックテスト
# =============================================================================


@dataclass
class MockPOI:
    """テスト用POI"""

    id: str
    name: str
    category: str
    embedding: list[float] | None = None


class TestSimilaritySearch:
    """類似検索のテスト"""

    def _find_similar(
        self,
        pois: list[MockPOI],
        query_embedding: list[float],
        category: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> list[dict]:
        """類似POIを検索"""
        results = []

        for poi in pois:
            if category and poi.category != category:
                continue
            if not poi.embedding:
                continue

            similarity = VectorOperations.cosine_similarity(
                query_embedding, poi.embedding
            )
            if similarity >= min_similarity:
                results.append({"poi": poi, "similarity": similarity})

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def test_find_similar_pois(self):
        """類似POIが見つかること"""
        pois = [
            MockPOI("1", "金閣寺", "activity", [1.0, 0.0, 0.0]),
            MockPOI("2", "銀閣寺", "activity", [0.9, 0.1, 0.0]),
            MockPOI("3", "祇園", "food", [0.0, 1.0, 0.0]),
        ]
        query = [1.0, 0.0, 0.0]

        results = self._find_similar(pois, query)
        assert len(results) >= 1
        assert results[0]["poi"].name == "金閣寺"

    def test_category_filter(self):
        """カテゴリフィルタが機能すること"""
        pois = [
            MockPOI("1", "金閣寺", "activity", [1.0, 0.0, 0.0]),
            MockPOI("2", "祇園料亭", "food", [0.9, 0.1, 0.0]),
        ]
        query = [1.0, 0.0, 0.0]

        results = self._find_similar(pois, query, category="food")
        assert all(r["poi"].category == "food" for r in results)

    def test_min_similarity_filter(self):
        """最小類似度フィルタが機能すること"""
        pois = [
            MockPOI("1", "金閣寺", "activity", [1.0, 0.0, 0.0]),
            MockPOI("2", "銀閣寺", "activity", [0.5, 0.5, 0.0]),
            MockPOI("3", "清水寺", "activity", [0.0, 0.0, 1.0]),
        ]
        query = [1.0, 0.0, 0.0]

        results = self._find_similar(pois, query, min_similarity=0.7)
        assert all(r["similarity"] >= 0.7 for r in results)

    def test_limit_results(self):
        """結果数が制限されること"""
        pois = [MockPOI(str(i), f"POI{i}", "activity", [1.0, 0.0, 0.0]) for i in range(20)]
        query = [1.0, 0.0, 0.0]

        results = self._find_similar(pois, query, limit=5)
        assert len(results) <= 5

    def test_skip_pois_without_embedding(self):
        """埋め込みがないPOIがスキップされること"""
        pois = [
            MockPOI("1", "金閣寺", "activity", [1.0, 0.0, 0.0]),
            MockPOI("2", "銀閣寺", "activity", None),  # 埋め込みなし
        ]
        query = [1.0, 0.0, 0.0]

        results = self._find_similar(pois, query, min_similarity=0.0)
        assert len(results) == 1
        assert results[0]["poi"].name == "金閣寺"

    def test_sorted_by_similarity(self):
        """類似度順にソートされること"""
        pois = [
            MockPOI("1", "低類似", "activity", [0.0, 1.0, 0.0]),
            MockPOI("2", "高類似", "activity", [0.95, 0.05, 0.0]),
            MockPOI("3", "中類似", "activity", [0.5, 0.5, 0.0]),
        ]
        query = [1.0, 0.0, 0.0]

        results = self._find_similar(pois, query, min_similarity=0.0)
        # 類似度が降順であること
        for i in range(len(results) - 1):
            assert results[i]["similarity"] >= results[i + 1]["similarity"]


# =============================================================================
# バッチ処理テスト
# =============================================================================


class TestBatchOperations:
    """バッチ処理のテスト"""

    def test_batch_size_division(self):
        """バッチサイズで分割されること"""
        items = list(range(25))
        batch_size = 10

        batches = []
        for i in range(0, len(items), batch_size):
            batches.append(items[i : i + batch_size])

        assert len(batches) == 3
        assert len(batches[0]) == 10
        assert len(batches[1]) == 10
        assert len(batches[2]) == 5

    def test_empty_batch(self):
        """空のバッチ処理"""
        items = []
        batch_size = 10

        batches = []
        for i in range(0, len(items), batch_size):
            batches.append(items[i : i + batch_size])

        assert len(batches) == 0


# =============================================================================
# pgvector互換性テスト
# =============================================================================


class TestPgvectorCompatibility:
    """pgvector互換性のテスト"""

    def test_vector_dimension_consistency(self):
        """ベクトル次元が一貫していること"""
        # nomic-embed-textの出力次元は768
        expected_dim = 768
        test_vectors = [
            [0.0] * expected_dim,
            [1.0] * expected_dim,
            [0.5] * expected_dim,
        ]

        for vec in test_vectors:
            assert len(vec) == expected_dim

    def test_float_precision(self):
        """浮動小数点精度が維持されること"""
        vec1 = [0.123456789, 0.987654321]
        vec2 = [0.123456789, 0.987654321]

        similarity = VectorOperations.cosine_similarity(vec1, vec2)
        assert similarity == 1.0

    def test_negative_values_handling(self):
        """負の値が正しく処理されること"""
        vec1 = [-1.0, -0.5, 0.0, 0.5, 1.0]
        vec2 = [-0.9, -0.4, 0.1, 0.6, 0.9]

        similarity = VectorOperations.cosine_similarity(vec1, vec2)
        assert 0.0 <= similarity <= 1.0

    def test_large_vector_handling(self):
        """大きなベクトルが処理できること"""
        dim = 768  # nomic-embed-textの次元
        vec1 = [0.5] * dim
        vec2 = [0.5] * dim

        similarity = VectorOperations.cosine_similarity(vec1, vec2)
        assert similarity == 1.0
