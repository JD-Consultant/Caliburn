-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
-- users
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email       TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    company     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- job_profiles  （每份職務說明書的主檔）
-- ============================================================
CREATE TABLE IF NOT EXISTS job_profiles (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 基本資料
    job_title           TEXT NOT NULL,
    department          TEXT,
    tenure_months       INT,
    primary_stakeholders TEXT[],
    job_summary         TEXT,

    -- 流程狀態
    stage               TEXT NOT NULL DEFAULT 'basic_info',
    -- basic_info | icap_ref | interview | task_extraction |
    -- star | five_w2h | indicator | ksa | preview | completed
    completion_pct      INT NOT NULL DEFAULT 0,

    -- iCAP 對應
    icap_source_type    TEXT DEFAULT 'icap_official',
    -- icap_official | company_defined | hybrid

    -- 完整文件（JSONB 保存最終草稿）
    document_draft      JSONB,

    -- 跨 API call 持久化 graph state（extracted_tasks / indicators / ksa 等）
    graph_state         JSONB DEFAULT '{}',

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_job_profiles_user_id ON job_profiles(user_id);
CREATE INDEX idx_job_profiles_stage   ON job_profiles(stage);

-- ============================================================
-- icap_references  （RAG 命中的 iCAP 候選基準）
-- ============================================================
CREATE TABLE IF NOT EXISTS icap_references (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_profile_id  UUID NOT NULL REFERENCES job_profiles(id) ON DELETE CASCADE,

    icap_id         TEXT NOT NULL,
    icap_title      TEXT NOT NULL,
    similarity      FLOAT NOT NULL,
    match_reason    TEXT,
    mismatch_notes  TEXT,
    recommendation  TEXT,   -- 建議參考 | 部分參考 | 低信心
    is_selected     BOOLEAN DEFAULT FALSE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- interview_sessions  （原始訪談紀錄）
-- ============================================================
CREATE TABLE IF NOT EXISTS interview_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_profile_id  UUID NOT NULL REFERENCES job_profiles(id) ON DELETE CASCADE,

    role            TEXT NOT NULL,  -- 'ai' | 'user'
    phase           TEXT NOT NULL,
    -- general | star_<task_name> | five_w2h_<task_name>
    content         TEXT NOT NULL,
    extra_data      JSONB DEFAULT '{}',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_interview_sessions_job_profile ON interview_sessions(job_profile_id);

-- ============================================================
-- company_tasks  （結構化任務，對應 company_task schema）
-- ============================================================
CREATE TABLE IF NOT EXISTS company_tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_profile_id  UUID NOT NULL REFERENCES job_profiles(id) ON DELETE CASCADE,

    task_name       TEXT NOT NULL,
    description     TEXT,
    category        TEXT,
    -- 核心職責 | 例行工作 | 協作任務 | 待確認
    frequency       TEXT,
    -- 每日 | 每週 | 每月 | 專案性 | 臨時性
    importance      TEXT DEFAULT '中',  -- 高 | 中 | 低
    responsibility_type TEXT DEFAULT '主責',  -- 主責 | 協作 | 支援
    sort_order      INT DEFAULT 0,

    -- 5W2H 欄位
    situation       TEXT,   -- When/Where
    purpose         TEXT,   -- Why
    stakeholders    TEXT[],
    workflow_steps  TEXT[],
    inputs          TEXT[],
    outputs         TEXT[],
    tools           TEXT[],
    collaborators   TEXT[],
    quality_standards   TEXT[],
    time_standards      TEXT[],
    quantity_standards  TEXT[],
    risks_or_common_errors TEXT[],

    -- 追溯
    evidence_from_user  TEXT,

    -- STAR 案例
    star_case       JSONB DEFAULT '{}',
    -- { situation, task, action: [], result }

    -- 行為指標
    behavior_indicator_5w2h     TEXT,
    behavior_indicator_abcd     TEXT,

    -- iCAP mapping
    icap_mapping    JSONB DEFAULT '[]',
    -- [{ icap_id, icap_task_id, match_type, confidence, reason }]

    -- 完整度
    completeness_pct    INT DEFAULT 0,
    missing_fields      TEXT[],

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_company_tasks_job_profile ON company_tasks(job_profile_id);

-- ============================================================
-- ksa_items  （知識/技能/態度）
-- ============================================================
CREATE TABLE IF NOT EXISTS ksa_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_profile_id  UUID NOT NULL REFERENCES job_profiles(id) ON DELETE CASCADE,
    task_id         UUID REFERENCES company_tasks(id) ON DELETE SET NULL,

    ksa_type        TEXT NOT NULL,   -- K | S | A
    content         TEXT NOT NULL,
    source_type     TEXT NOT NULL DEFAULT 'icap_official',
    -- icap_official | company_defined
    icap_ref        TEXT,
    confirmed       BOOLEAN DEFAULT FALSE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- document_versions  （匯出的正式文件版本）
-- ============================================================
CREATE TABLE IF NOT EXISTS document_versions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_profile_id  UUID NOT NULL REFERENCES job_profiles(id) ON DELETE CASCADE,

    version         INT NOT NULL DEFAULT 1,
    format          TEXT NOT NULL,   -- pdf | docx | json
    file_path       TEXT,
    content         JSONB,
    status          TEXT DEFAULT 'draft',  -- draft | finalized

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- iCAP 向量表（pgvector）
-- ============================================================
CREATE TABLE IF NOT EXISTS icap_embeddings (
    id              UUID PRIMARY KEY,           -- set by parser (stable per-node UUID)
    ocs_code        TEXT NOT NULL,              -- e.g. KRM2421-001v4
    chunk_type      TEXT NOT NULL,              -- competency|unit|task|indicator|output|knowledge|skill|attitude
    chunk_text      TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    embedding       vector(1536),               -- OpenAI text-embedding-3-small

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_icap_embeddings_ocs_code  ON icap_embeddings(ocs_code);
CREATE INDEX IF NOT EXISTS idx_icap_embeddings_chunk_type ON icap_embeddings(chunk_type);
CREATE INDEX IF NOT EXISTS idx_icap_embeddings_vector
    ON icap_embeddings USING hnsw (embedding vector_cosine_ops);

-- ============================================================
-- updated_at 自動觸發器
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_job_profiles_updated_at
    BEFORE UPDATE ON job_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_company_tasks_updated_at
    BEFORE UPDATE ON company_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
