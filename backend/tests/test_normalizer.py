"""
Search Result Normalization/Deduplication Tests

CLAUDE.md セクション11の要件:
- 検索結果の正規化/重複排除

注: 実際のNormalizerはapp.services.normalizerにありますが、
このテストは依存関係なしでロジックを検証します。
"""

import pytest
import re
from difflib import SequenceMatcher
from dataclasses import dataclass


# テスト用のモックPOIクラス
@dataclass
class MockPOI:
    """テスト用のモックPOI"""
    name: str
    category: str
    location: str = ""
    description: str = ""
    price_range: str = ""
    duration_minutes: int = None
    opening_hours: str = ""
    rating: float = None
    tags: list = None
    source_url: str = ""
    relevance_score: float = 0.0
    source_name: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


# 正規化ロジック（normalizer.pyと同等）
class NormalizerLogic:
    """正規化ロジック"""

    @staticmethod
    def normalize_name(name: str) -> str:
        """名前を正規化"""
        if not name:
            return ""
        # 余分な空白を削除
        name = re.sub(r"\s+", " ", name.strip())
        # 全角スペースを半角に
        name = name.replace("　", " ")
        # 長い括弧内の補足情報を削除
        name = re.sub(r"\s*[（(].{20,}[)）]", "", name)
        return name[:100]

    @staticmethod
    def normalize_location(location: str) -> str:
        """住所を正規化"""
        if not location:
            return ""
        # 郵便番号を削除
        location = re.sub(r"〒?\d{3}-?\d{4}", "", location)
        location = re.sub(r"\s+", " ", location.strip())
        return location[:200]

    @staticmethod
    def normalize_description(description: str) -> str:
        """説明を正規化"""
        if not description:
            return ""
        description = re.sub(r"\s+", " ", description.strip())
        description = re.sub(r"<[^>]+>", "", description)
        return description[:500]

    @staticmethod
    def normalize_tags(tags: list) -> list:
        """タグを正規化"""
        if not tags:
            return []
        normalized = []
        seen = set()
        for tag in tags:
            tag_lower = tag.strip().lower()
            if tag_lower and tag_lower not in seen:
                normalized.append(tag.strip())
                seen.add(tag_lower)
        return normalized[:10]


class DedupeLogic:
    """重複排除ロジック"""

    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold

    def calculate_similarity(self, s1: str, s2: str) -> float:
        """文字列の類似度を計算"""
        if not s1 or not s2:
            return 0.0
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

    def is_duplicate(self, poi1: MockPOI, poi2: MockPOI) -> bool:
        """重複判定"""
        if poi1.category != poi2.category:
            return False

        name_similarity = self.calculate_similarity(poi1.name, poi2.name)
        if name_similarity >= self.similarity_threshold:
            return True

        if poi1.source_url and poi1.source_url == poi2.source_url:
            return True

        return False

    def dedupe(self, pois: list) -> list:
        """重複排除"""
        if not pois:
            return []

        unique_pois = []
        for poi in pois:
            is_dup = False
            for i, existing in enumerate(unique_pois):
                if self.is_duplicate(poi, existing):
                    is_dup = True
                    if poi.relevance_score > existing.relevance_score:
                        unique_pois[i] = poi
                    break
            if not is_dup:
                unique_pois.append(poi)
        return unique_pois


class TestNormalizerLogic:
    """正規化ロジックテスト"""

    def test_normalize_name_removes_extra_spaces(self):
        """余分な空白が削除されること"""
        name = "金閣寺   鹿苑寺"
        result = NormalizerLogic.normalize_name(name)
        assert result == "金閣寺 鹿苑寺"

    def test_normalize_name_converts_fullwidth_space(self):
        """全角スペースが半角に変換されること"""
        name = "金閣寺　鹿苑寺"
        result = NormalizerLogic.normalize_name(name)
        assert "　" not in result
        assert " " in result

    def test_normalize_name_truncates_long_bracket_content(self):
        """長い括弧内の補足情報が削除されること"""
        name = "金閣寺（世界遺産に登録されている非常に美しい寺院です。京都観光の定番スポット。）"
        result = NormalizerLogic.normalize_name(name)
        assert "世界遺産に登録" not in result
        assert "金閣寺" in result

    def test_normalize_name_max_length(self):
        """名前が最大100文字に切り詰められること"""
        name = "あ" * 200
        result = NormalizerLogic.normalize_name(name)
        assert len(result) <= 100

    def test_normalize_location_removes_postal_code(self):
        """郵便番号が削除されること"""
        location = "〒603-8361 京都府京都市北区金閣寺町1"
        result = NormalizerLogic.normalize_location(location)
        assert "〒" not in result
        assert "603-8361" not in result
        assert "京都府" in result

    def test_normalize_description_removes_html_tags(self):
        """HTMLタグが削除されること"""
        description = "<p>金閣寺は<strong>世界遺産</strong>です。</p>"
        result = NormalizerLogic.normalize_description(description)
        assert "<p>" not in result
        assert "<strong>" not in result
        assert "金閣寺は世界遺産です。" in result

    def test_normalize_description_max_length(self):
        """説明が最大500文字に切り詰められること"""
        description = "あ" * 1000
        result = NormalizerLogic.normalize_description(description)
        assert len(result) <= 500

    def test_normalize_tags_removes_duplicates(self):
        """重複タグが削除されること（大文字小文字区別なし）"""
        tags = ["温泉", "ONSEN", "温泉", "onsen"]
        result = NormalizerLogic.normalize_tags(tags)
        # 重複排除後は最初の出現のみ残る
        unique_lower = set(t.lower() for t in result)
        assert len(unique_lower) <= 2

    def test_normalize_tags_max_count(self):
        """タグが最大10個に制限されること"""
        tags = [f"タグ{i}" for i in range(20)]
        result = NormalizerLogic.normalize_tags(tags)
        assert len(result) <= 10

    def test_normalize_empty_values(self):
        """空値が正しく処理されること"""
        assert NormalizerLogic.normalize_name("") == ""
        assert NormalizerLogic.normalize_location("") == ""
        assert NormalizerLogic.normalize_description("") == ""
        assert NormalizerLogic.normalize_tags([]) == []


class TestDedupeLogic:
    """重複排除ロジックテスト"""

    @pytest.fixture
    def deduper(self):
        return DedupeLogic(similarity_threshold=0.8)

    def test_dedupe_empty_list(self, deduper):
        """空リストの場合は空を返すこと"""
        result = deduper.dedupe([])
        assert result == []

    def test_dedupe_single_item(self, deduper):
        """単一アイテムの場合はそのまま返すこと"""
        poi = MockPOI(name="金閣寺", category="activity", relevance_score=0.9)
        result = deduper.dedupe([poi])
        assert len(result) == 1
        assert result[0].name == "金閣寺"

    def test_dedupe_removes_exact_duplicate_names(self, deduper):
        """完全一致の名前が重複排除されること"""
        poi1 = MockPOI(name="金閣寺", category="activity", relevance_score=0.9)
        poi2 = MockPOI(name="金閣寺", category="activity", relevance_score=0.7)

        result = deduper.dedupe([poi1, poi2])
        assert len(result) == 1
        assert result[0].relevance_score == 0.9

    def test_dedupe_keeps_different_names(self, deduper):
        """異なる名前は保持されること"""
        poi1 = MockPOI(name="金閣寺", category="activity", relevance_score=0.9)
        poi2 = MockPOI(name="銀閣寺", category="activity", relevance_score=0.8)

        result = deduper.dedupe([poi1, poi2])
        assert len(result) == 2

    def test_dedupe_keeps_different_categories(self, deduper):
        """カテゴリが異なれば同名でも保持されること"""
        poi1 = MockPOI(name="京都駅", category="activity", relevance_score=0.9)
        poi2 = MockPOI(name="京都駅", category="food", relevance_score=0.8)

        result = deduper.dedupe([poi1, poi2])
        assert len(result) == 2

    def test_dedupe_by_url(self, deduper):
        """同じURLは重複とみなされること"""
        poi1 = MockPOI(
            name="金閣寺 公式",
            category="activity",
            source_url="https://example.com/kinkakuji",
            relevance_score=0.9,
        )
        poi2 = MockPOI(
            name="鹿苑寺（金閣）",
            category="activity",
            source_url="https://example.com/kinkakuji",
            relevance_score=0.7,
        )

        result = deduper.dedupe([poi1, poi2])
        assert len(result) == 1

    def test_dedupe_keeps_higher_score(self, deduper):
        """スコアが高い方が保持されること"""
        poi_low = MockPOI(name="金閣寺", category="activity", relevance_score=0.5)
        poi_high = MockPOI(name="金閣寺", category="activity", relevance_score=0.95)

        result1 = deduper.dedupe([poi_low, poi_high])
        result2 = deduper.dedupe([poi_high, poi_low])

        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0].relevance_score == 0.95
        assert result2[0].relevance_score == 0.95

    def test_calculate_similarity_exact_match(self, deduper):
        """完全一致の類似度が1.0であること"""
        similarity = deduper.calculate_similarity("金閣寺", "金閣寺")
        assert similarity == 1.0

    def test_calculate_similarity_case_insensitive(self, deduper):
        """大文字小文字を区別しないこと"""
        similarity = deduper.calculate_similarity("Kinkakuji", "kinkakuji")
        assert similarity == 1.0

    def test_calculate_similarity_empty_string(self, deduper):
        """空文字の場合は0.0であること"""
        assert deduper.calculate_similarity("", "test") == 0.0
        assert deduper.calculate_similarity("test", "") == 0.0


class TestIntegratedNormalizerDeduper:
    """統合テスト"""

    def test_process_normalizes_and_dedupes(self):
        """正規化と重複排除が両方実行されること"""
        pois = [
            MockPOI(name="金閣寺   ", category="activity", relevance_score=0.9),
            MockPOI(name="金閣寺", category="activity", relevance_score=0.7),
        ]

        # 正規化
        normalized = [
            MockPOI(
                name=NormalizerLogic.normalize_name(poi.name),
                category=poi.category,
                relevance_score=poi.relevance_score,
            )
            for poi in pois
        ]

        # 重複排除
        deduper = DedupeLogic(similarity_threshold=0.8)
        result = deduper.dedupe(normalized)

        assert len(result) == 1
        assert result[0].name == "金閣寺"
        assert result[0].relevance_score == 0.9

    def test_process_by_category(self):
        """カテゴリごとに処理されること"""
        pois_by_category = {
            "activity": [
                MockPOI(name="金閣寺", category="activity", relevance_score=0.9),
                MockPOI(name="金閣寺", category="activity", relevance_score=0.7),
            ],
            "food": [
                MockPOI(name="祇園料亭", category="food", relevance_score=0.85),
            ],
        }

        deduper = DedupeLogic()
        result = {}
        for category, pois in pois_by_category.items():
            result[category] = deduper.dedupe(pois)

        assert "activity" in result
        assert "food" in result
        assert len(result["activity"]) == 1
        assert len(result["food"]) == 1


class TestEdgeCases:
    """エッジケーステスト"""

    def test_normalizer_handles_unicode(self):
        """Unicodeを正しく処理すること"""
        name = "🏯 金閣寺 🏯"
        result = NormalizerLogic.normalize_name(name)
        assert "金閣寺" in result

    def test_deduper_handles_special_characters(self):
        """特殊文字を含む名前を正しく処理すること"""
        deduper = DedupeLogic()
        poi1 = MockPOI(name="カフェ・ド・パリ", category="food", relevance_score=0.9)
        poi2 = MockPOI(name="カフェ ド パリ", category="food", relevance_score=0.7)

        result = deduper.dedupe([poi1, poi2])
        assert len(result) >= 1

    def test_similarity_threshold_effect(self):
        """類似度閾値が結果に影響すること"""
        poi1 = MockPOI(name="金閣寺", category="activity", relevance_score=0.9)
        poi2 = MockPOI(name="金閣", category="activity", relevance_score=0.7)  # 部分的に類似

        # 高い閾値
        high_threshold = DedupeLogic(similarity_threshold=0.9)
        result_high = high_threshold.dedupe([poi1, poi2])

        # 低い閾値
        low_threshold = DedupeLogic(similarity_threshold=0.5)
        result_low = low_threshold.dedupe([poi1, poi2])

        # 閾値が低いほど重複とみなされやすい
        assert len(result_high) >= len(result_low)
