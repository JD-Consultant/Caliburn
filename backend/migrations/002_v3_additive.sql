-- v3 additive：provenance + 選定 OCS。
-- 不刪任何欄；graph_state 待 PostgresSaver 接手後（Phase ②）再 drop。
ALTER TABLE company_tasks ADD COLUMN IF NOT EXISTS source      TEXT DEFAULT 'company';
ALTER TABLE company_tasks ADD COLUMN IF NOT EXISTS indexer_ref JSONB;
ALTER TABLE job_profiles  ADD COLUMN IF NOT EXISTS selected_ocs_code TEXT;
