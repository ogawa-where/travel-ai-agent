-- Migration: PTS Architecture Support
-- Date: 2026-02-03
-- Description: Add destination field to poi_cache and create travel_search_results table

-- 1. Add destination column to poi_cache
ALTER TABLE poi_cache
ADD COLUMN IF NOT EXISTS destination VARCHAR(255) DEFAULT '' NOT NULL;

-- Create index for destination
CREATE INDEX IF NOT EXISTS ix_poi_cache_destination ON poi_cache(destination);

-- Create index for category (if not exists)
CREATE INDEX IF NOT EXISTS ix_poi_cache_category ON poi_cache(category);

-- 2. Create travel_search_results table
CREATE TABLE IF NOT EXISTS travel_search_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES travel_plan_requests(id) ON DELETE CASCADE,
    poi_id UUID NOT NULL REFERENCES poi_cache(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    rerank_score FLOAT DEFAULT 0.0,
    constraint_score FLOAT DEFAULT 0.0,
    total_score FLOAT DEFAULT 0.0,
    is_selected BOOLEAN DEFAULT FALSE,
    selection_reason TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Create indexes for travel_search_results
CREATE INDEX IF NOT EXISTS ix_travel_search_results_request_id ON travel_search_results(request_id);
CREATE INDEX IF NOT EXISTS ix_travel_search_results_poi_id ON travel_search_results(poi_id);
CREATE INDEX IF NOT EXISTS ix_travel_search_results_category ON travel_search_results(category);
CREATE INDEX IF NOT EXISTS ix_travel_search_results_total_score ON travel_search_results(total_score DESC);

-- 3. Create unique constraint for poi_cache (destination + category + name)
-- First, remove duplicates if any exist
-- Then create unique index
CREATE UNIQUE INDEX IF NOT EXISTS ix_poi_cache_unique_dest_cat_name
ON poi_cache(destination, category, name);
