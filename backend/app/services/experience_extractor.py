"""
体験抽出サービス

POIへのフィードバックから、その場所が持つ「体験の本質」を抽出し、
将来の旅行企画に活用できる形で保存する。
"""

import logging
from dataclasses import dataclass

from app.services.llm_gateway import ModelTier, llm_gateway

logger = logging.getLogger(__name__)


@dataclass
class ExtractedExperience:
    """抽出された体験"""
    tag: str  # 体験タグ（例: "歴史的建造物", "自然散策", "地元グルメ"）
    weight: float  # 重み（0.0-1.0）
    reason: str  # 抽出理由


class ExperienceExtractor:
    """POIから体験を抽出するサービス"""

    async def extract_experiences(
        self,
        poi_name: str,
        poi_category: str,
        poi_tags: list[str],
        feedback_type: str,  # "good" or "bad"
    ) -> list[ExtractedExperience]:
        """
        POIから体験を抽出

        Args:
            poi_name: POI名（例: "清水寺"）
            poi_category: カテゴリ（"activity", "food", "hotel"）
            poi_tags: POIのタグ
            feedback_type: フィードバックタイプ（"good" or "bad"）

        Returns:
            抽出された体験のリスト
        """
        category_label = {
            "activity": "観光・体験スポット",
            "food": "飲食店",
            "hotel": "宿泊施設",
        }.get(poi_category, poi_category)

        tags_str = "、".join(poi_tags) if poi_tags else "なし"

        prompt = f"""以下のPOI（観光スポット/飲食店/宿泊施設）について、ユーザーが{'気に入った' if feedback_type == 'good' else '気に入らなかった'}理由として考えられる「体験の特徴」を3〜5個抽出してください。

## POI情報
- 名前: {poi_name}
- カテゴリ: {category_label}
- タグ: {tags_str}

## 出力形式
以下のJSON形式で出力してください。体験の特徴は具体的な場所名ではなく、他の場所にも適用できる一般的な体験タイプで表現してください。

```json
{{
  "experiences": [
    {{
      "tag": "歴史的建造物巡り",
      "weight": 0.9,
      "reason": "〇〇という理由"
    }},
    {{
      "tag": "写真映えスポット",
      "weight": 0.7,
      "reason": "〇〇という理由"
    }}
  ]
}}
```

## 体験タイプの例
観光・体験: 歴史的建造物巡り, 自然散策, 文化体験, アート鑑賞, 写真映えスポット, パワースポット, 地元交流, アウトドア体験, 伝統工芸体験, 季節の風景
食事: 地元グルメ, 高級料理, カジュアルダイニング, 伝統料理, 創作料理, 地酒・地ビール, カフェ巡り, 食べ歩き, 老舗の味
宿泊: 温泉, 和風旅館, モダンホテル, 景観重視, おもてなし重視, 料理自慢, 静かな環境, アクセス重視

重みは0.5〜1.0の範囲で、その体験がどれだけこのPOIを特徴づけるかを表します。"""

        system_prompt = "あなたは旅行体験の分析専門家です。POIの特徴から、ユーザーが求めている体験の本質を抽出します。"

        try:
            result = await llm_gateway.generate_json(
                prompt=prompt,
                tier=ModelTier.LIGHT,
                system_prompt=system_prompt,
                temperature=0.3,
                agent_name="experience_extractor",
            )

            experiences = []
            for exp in result.get("experiences", []):
                tag = exp.get("tag", "")
                weight = exp.get("weight", 0.5)
                reason = exp.get("reason", "")

                if tag:
                    # 重みを0.5〜1.0に正規化
                    weight = max(0.5, min(1.0, float(weight)))
                    experiences.append(ExtractedExperience(
                        tag=tag,
                        weight=weight,
                        reason=reason,
                    ))

            logger.info(
                f"Experience extraction for {poi_name}: {len(experiences)} experiences extracted"
            )
            return experiences

        except Exception as e:
            logger.error(f"Failed to extract experiences from {poi_name}: {e}")
            # エラー時は空リストを返す（フィードバック処理は継続）
            return []


# シングルトンインスタンス
experience_extractor = ExperienceExtractor()
