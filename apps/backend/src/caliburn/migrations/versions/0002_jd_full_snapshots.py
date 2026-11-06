"""Create final JD relational content and full version snapshots.

Frozen DDL for fresh databases; no migration from retired JD schemas.
Whitespace checks freeze the Python 3.14 str.strip() character set.
"""

from alembic import op

revision = "0002_jd_full_snapshots"
down_revision = "0001_create_workspaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""CREATE TABLE job_descriptions (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    job_title TEXT,
    organization_unit TEXT,
    reports_to TEXT,
    purpose TEXT,
    baseline_competency_level INTEGER,
    version INTEGER DEFAULT '1' NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_job_descriptions_workspace_id UNIQUE (workspace_id),
    CONSTRAINT ck_job_descriptions_version_positive CHECK (version > 0),
    CONSTRAINT ck_job_descriptions_baseline_competency_level CHECK
        (baseline_competency_level BETWEEN 1 AND 6),
    CONSTRAINT fk_job_descriptions_workspace_id FOREIGN KEY(workspace_id) REFERENCES
        workspaces (id)
)""")
    op.execute(r"""CREATE TABLE collaboration_entries (
    id UUID NOT NULL,
    job_description_id UUID NOT NULL,
    collaborator_name TEXT NOT NULL,
    scope TEXT,
    position INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_collaboration_entries_collaborator_name_required CHECK
        (btrim(collaborator_name,
        U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020' ||
        U&'\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006' ||
        U&'\2007\2008\2009\200a\2028\2029\202f\205f\3000') <> ''),
    CONSTRAINT uq_collaboration_entries_position UNIQUE (job_description_id,
        position) DEFERRABLE INITIALLY IMMEDIATE,
    CONSTRAINT ck_collaboration_entries_position CHECK (position >= 0),
    CONSTRAINT fk_collaboration_entries_jd FOREIGN KEY(job_description_id)
        REFERENCES job_descriptions (id) ON DELETE CASCADE
)""")
    op.execute(r"""CREATE TABLE duties (
    id UUID NOT NULL,
    job_description_id UUID NOT NULL,
    name TEXT COLLATE "C" NOT NULL,
    scope TEXT,
    position INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_duties_name_required CHECK (btrim(name,
        U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020' ||
        U&'\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006' ||
        U&'\2007\2008\2009\200a\2028\2029\202f\205f\3000') <> ''),
    CONSTRAINT uq_duties_id_jd UNIQUE (id, job_description_id),
    CONSTRAINT uq_duties_name UNIQUE (job_description_id, name) DEFERRABLE INITIALLY
        DEFERRED,
    CONSTRAINT ck_duties_name_length CHECK (char_length(name) BETWEEN 1 AND 200),
    CONSTRAINT uq_duties_position UNIQUE (job_description_id, position) DEFERRABLE
        INITIALLY IMMEDIATE,
    CONSTRAINT ck_duties_position CHECK (position >= 0),
    CONSTRAINT fk_duties_jd FOREIGN KEY(job_description_id) REFERENCES
        job_descriptions (id)
)""")
    op.execute(r"""CREATE TABLE job_conditions (
    id UUID NOT NULL,
    job_description_id UUID NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_job_conditions_text_required CHECK (btrim(text,
        U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020' ||
        U&'\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006' ||
        U&'\2007\2008\2009\200a\2028\2029\202f\205f\3000') <> ''),
    CONSTRAINT uq_job_conditions_position UNIQUE (job_description_id, kind,
        position) DEFERRABLE INITIALLY IMMEDIATE,
    CONSTRAINT ck_job_conditions_position CHECK (position >= 0),
    CONSTRAINT ck_job_conditions_kind CHECK (kind IN ('work_environment',
        'schedule_travel', 'shared_authority', 'shared_collaboration',
        'qualification')),
    CONSTRAINT fk_job_conditions_jd FOREIGN KEY(job_description_id) REFERENCES
        job_descriptions (id) ON DELETE CASCADE
)""")
    op.execute(r"""CREATE TABLE job_description_snapshots (
    job_description_id UUID NOT NULL,
    version INTEGER NOT NULL,
    schema_version INTEGER NOT NULL,
    content JSONB NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    kind TEXT NOT NULL,
    restored_from_version INTEGER,
    correlation_id TEXT,
    reverts_correlation_id TEXT,
    PRIMARY KEY (job_description_id, version),
    CONSTRAINT ck_jd_snapshots_correlation_id CHECK (correlation_id IS NULL OR
        (char_length(correlation_id) <= 200 AND btrim(correlation_id,
        U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020' ||
        U&'\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006' ||
        U&'\2007\2008\2009\200a\2028\2029\202f\205f\3000') <> '')),
    CONSTRAINT ck_jd_snapshots_reverts_correlation_id CHECK (reverts_correlation_id
        IS NULL OR (char_length(reverts_correlation_id) <= 200 AND
        btrim(reverts_correlation_id,
        U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020' ||
        U&'\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006' ||
        U&'\2007\2008\2009\200a\2028\2029\202f\205f\3000') <> '')),
    CONSTRAINT ck_jd_snapshots_version CHECK (version > 0),
    CONSTRAINT ck_jd_snapshots_schema_version CHECK (schema_version > 0),
    CONSTRAINT ck_jd_snapshots_content CHECK (jsonb_typeof(content) = 'object'),
    CONSTRAINT ck_jd_snapshots_kind CHECK ((kind = 'created' AND version = 1 AND
        restored_from_version IS NULL AND reverts_correlation_id IS NULL) OR (kind =
        'edited' AND version > 1 AND restored_from_version IS NULL AND
        reverts_correlation_id IS NULL) OR (kind = 'restored' AND
        restored_from_version IS NOT NULL AND restored_from_version < version)),
    CONSTRAINT fk_jd_snapshots_restore_target FOREIGN KEY(job_description_id,
        restored_from_version) REFERENCES job_description_snapshots
        (job_description_id, version),
    CONSTRAINT fk_jd_snapshots_jd FOREIGN KEY(job_description_id) REFERENCES
        job_descriptions (id)
)""")
    op.execute(r"""CREATE TABLE knowledge (
    id UUID NOT NULL,
    job_description_id UUID NOT NULL,
    name TEXT COLLATE "C" NOT NULL,
    description TEXT,
    position INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_knowledge_name_required CHECK (btrim(name,
        U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020' ||
        U&'\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006' ||
        U&'\2007\2008\2009\200a\2028\2029\202f\205f\3000') <> ''),
    CONSTRAINT uq_knowledge_id_jd UNIQUE (id, job_description_id),
    CONSTRAINT uq_knowledge_name UNIQUE (job_description_id, name) DEFERRABLE
        INITIALLY DEFERRED,
    CONSTRAINT ck_knowledge_name_length CHECK (char_length(name) BETWEEN 1 AND 200),
    CONSTRAINT uq_knowledge_position UNIQUE (job_description_id, position)
        DEFERRABLE INITIALLY IMMEDIATE,
    CONSTRAINT ck_knowledge_position CHECK (position >= 0),
    CONSTRAINT fk_knowledge_jd FOREIGN KEY(job_description_id) REFERENCES
        job_descriptions (id)
)""")
    op.execute(r"""CREATE TABLE skills (
    id UUID NOT NULL,
    job_description_id UUID NOT NULL,
    name TEXT COLLATE "C" NOT NULL,
    description TEXT,
    position INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_skills_name_required CHECK (btrim(name,
        U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020' ||
        U&'\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006' ||
        U&'\2007\2008\2009\200a\2028\2029\202f\205f\3000') <> ''),
    CONSTRAINT uq_skills_id_jd UNIQUE (id, job_description_id),
    CONSTRAINT uq_skills_name UNIQUE (job_description_id, name) DEFERRABLE INITIALLY
        DEFERRED,
    CONSTRAINT ck_skills_name_length CHECK (char_length(name) BETWEEN 1 AND 200),
    CONSTRAINT uq_skills_position UNIQUE (job_description_id, position) DEFERRABLE
        INITIALLY IMMEDIATE,
    CONSTRAINT ck_skills_position CHECK (position >= 0),
    CONSTRAINT fk_skills_jd FOREIGN KEY(job_description_id) REFERENCES
        job_descriptions (id)
)""")
    op.execute(r"""CREATE TABLE job_tasks (
    id UUID NOT NULL,
    job_description_id UUID NOT NULL,
    duty_id UUID,
    name TEXT COLLATE "C" NOT NULL,
    description TEXT,
    competency_level INTEGER,
    position INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_job_tasks_name_required CHECK (btrim(name,
        U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020' ||
        U&'\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006' ||
        U&'\2007\2008\2009\200a\2028\2029\202f\205f\3000') <> ''),
    CONSTRAINT uq_job_tasks_id_jd UNIQUE (id, job_description_id),
    CONSTRAINT uq_job_tasks_name UNIQUE (job_description_id, name) DEFERRABLE
        INITIALLY DEFERRED,
    CONSTRAINT ck_job_tasks_name_length CHECK (char_length(name) BETWEEN 1 AND 200),
    CONSTRAINT fk_job_tasks_duty FOREIGN KEY(duty_id, job_description_id) REFERENCES
        duties (id, job_description_id),
    CONSTRAINT uq_job_tasks_position UNIQUE NULLS NOT DISTINCT (job_description_id,
        duty_id, position) DEFERRABLE INITIALLY IMMEDIATE,
    CONSTRAINT ck_job_tasks_position CHECK (position >= 0),
    CONSTRAINT ck_job_tasks_competency_level CHECK (competency_level BETWEEN 1 AND 6),
    CONSTRAINT fk_job_tasks_jd FOREIGN KEY(job_description_id) REFERENCES
        job_descriptions (id)
)""")
    op.execute(r"""CREATE TABLE task_knowledge (
    task_id UUID NOT NULL,
    knowledge_id UUID NOT NULL,
    job_description_id UUID NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (task_id, knowledge_id),
    CONSTRAINT fk_task_knowledge_task FOREIGN KEY(task_id, job_description_id)
        REFERENCES job_tasks (id, job_description_id) ON DELETE CASCADE,
    CONSTRAINT fk_task_knowledge_definition FOREIGN KEY(knowledge_id,
        job_description_id) REFERENCES knowledge (id, job_description_id),
    CONSTRAINT uq_task_knowledge_position UNIQUE (task_id, position) DEFERRABLE
        INITIALLY IMMEDIATE,
    CONSTRAINT ck_task_knowledge_position CHECK (position >= 0)
)""")
    op.execute(r"""CREATE TABLE task_outcomes (
    id UUID NOT NULL,
    task_id UUID NOT NULL,
    text TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_task_outcomes_text_required CHECK (btrim(text,
        U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020' ||
        U&'\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006' ||
        U&'\2007\2008\2009\200a\2028\2029\202f\205f\3000') <> ''),
    CONSTRAINT uq_task_outcomes_position UNIQUE (task_id, position) DEFERRABLE
        INITIALLY IMMEDIATE,
    CONSTRAINT ck_task_outcomes_position CHECK (position >= 0),
    CONSTRAINT fk_task_outcomes_task FOREIGN KEY(task_id) REFERENCES job_tasks (id)
        ON DELETE CASCADE
)""")
    op.execute(r"""CREATE TABLE task_requirements (
    id UUID NOT NULL,
    task_id UUID NOT NULL,
    text TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_task_requirements_text_required CHECK (btrim(text,
        U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020' ||
        U&'\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006' ||
        U&'\2007\2008\2009\200a\2028\2029\202f\205f\3000') <> ''),
    CONSTRAINT uq_task_requirements_position UNIQUE (task_id, position) DEFERRABLE
        INITIALLY IMMEDIATE,
    CONSTRAINT ck_task_requirements_position CHECK (position >= 0),
    CONSTRAINT fk_task_requirements_task FOREIGN KEY(task_id) REFERENCES job_tasks
        (id) ON DELETE CASCADE
)""")
    op.execute(r"""CREATE TABLE task_skills (
    task_id UUID NOT NULL,
    skill_id UUID NOT NULL,
    job_description_id UUID NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (task_id, skill_id),
    CONSTRAINT fk_task_skills_task FOREIGN KEY(task_id, job_description_id)
        REFERENCES job_tasks (id, job_description_id) ON DELETE CASCADE,
    CONSTRAINT fk_task_skills_definition FOREIGN KEY(skill_id, job_description_id)
        REFERENCES skills (id, job_description_id),
    CONSTRAINT uq_task_skills_position UNIQUE (task_id, position) DEFERRABLE
        INITIALLY IMMEDIATE,
    CONSTRAINT ck_task_skills_position CHECK (position >= 0)
)""")


def downgrade() -> None:
    op.drop_table("task_skills")
    op.drop_table("task_requirements")
    op.drop_table("task_outcomes")
    op.drop_table("task_knowledge")
    op.drop_table("job_tasks")
    op.drop_table("skills")
    op.drop_table("knowledge")
    op.drop_table("job_description_snapshots")
    op.drop_table("job_conditions")
    op.drop_table("duties")
    op.drop_table("collaboration_entries")
    op.drop_table("job_descriptions")
