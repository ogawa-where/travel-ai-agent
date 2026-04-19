-- Migration: PTS POI Fields
-- Date: 2026-02-03
-- Description: Add PTS-style structured fields to poi_cache

-- 基本情報
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '';

-- 位置情報
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS address TEXT DEFAULT '';
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;

-- 評価・レビュー情報
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS rating DOUBLE PRECISION;
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS review_count INTEGER;

-- 価格情報
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS price_level INTEGER;
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS price_range VARCHAR(100) DEFAULT '';
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS budget_per_person INTEGER;

-- 時間情報
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS hours JSONB;
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS duration_minutes INTEGER;

-- 特徴・タグ
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS features JSONB DEFAULT '[]'::jsonb;
ALTER TABLE poi_cache ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb;

-- インデックス作成
CREATE INDEX IF NOT EXISTS ix_poi_cache_rating ON poi_cache(rating DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_poi_cache_price_level ON poi_cache(price_level);
CREATE INDEX IF NOT EXISTS ix_poi_cache_review_count ON poi_cache(review_count DESC NULLS LAST);
