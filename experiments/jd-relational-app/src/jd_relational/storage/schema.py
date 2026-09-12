"""SQLAlchemy Core metadata for the thirteen JD business tables.

This module defines no engine, connection, repository or write transaction. Text
normalization, immutable-history ports, source checks and receipt durability remain
App responsibilities. Alembic's version table is separate technical metadata.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


metadata = sa.MetaData()

jd_document = sa.Table(
    "jd_document", metadata,
    sa.Column("id", sa.String(), nullable=False),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("metadata_version", sa.BigInteger(), nullable=False),
    sa.Column("create_request_key", sa.String(), nullable=False),
    sa.Column("create_payload_digest", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id", name="pk_jd_document"),
    sa.UniqueConstraint("create_request_key", name="uq_jd_document_create_request"),
    sa.CheckConstraint("metadata_version >= 1", name="ck_jd_document_metadata_version"),
)

jd_profile = sa.Table(
    "jd_profile", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("job_title", sa.Text()),
    sa.Column("organization_unit", sa.Text()),
    sa.Column("employee_name", sa.Text()),
    sa.Column("reports_to", sa.Text()),
    sa.Column("purpose", sa.Text()),
    sa.PrimaryKeyConstraint("document_id", name="pk_jd_profile"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_profile_document", ondelete="RESTRICT"),
)

jd_collaborator = sa.Table(
    "jd_collaborator", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("collaborator_id", UUID(as_uuid=True), nullable=False),
    sa.Column("name", sa.Text()),
    sa.Column("scope_text", sa.Text()),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint("document_id", "collaborator_id", name="pk_jd_collaborator"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_collaborator_document", ondelete="RESTRICT"),
    sa.CheckConstraint("name IS NOT NULL OR scope_text IS NOT NULL", name="ck_jd_collaborator_content"),
    sa.CheckConstraint("position >= 0", name="ck_jd_collaborator_position"),
)

jd_duty = sa.Table(
    "jd_duty", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("duty_id", UUID(as_uuid=True), nullable=False),
    sa.Column("name", sa.Text()),
    sa.Column("scope_text", sa.Text()),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint("document_id", "duty_id", name="pk_jd_duty"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_duty_document", ondelete="RESTRICT"),
    sa.CheckConstraint("name IS NOT NULL OR scope_text IS NOT NULL", name="ck_jd_duty_content"),
    sa.CheckConstraint("position >= 0", name="ck_jd_duty_position"),
)

jd_task = sa.Table(
    "jd_task", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("task_id", UUID(as_uuid=True), nullable=False),
    sa.Column("duty_id", UUID(as_uuid=True)),
    sa.Column("name", sa.Text()),
    sa.Column("description", sa.Text()),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint("document_id", "task_id", name="pk_jd_task"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_task_document", ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["document_id", "duty_id"], ["jd_duty.document_id", "jd_duty.duty_id"],
                            name="fk_jd_task_duty", ondelete="RESTRICT"),
    sa.CheckConstraint("name IS NOT NULL OR description IS NOT NULL", name="ck_jd_task_content"),
    sa.CheckConstraint("position >= 0", name="ck_jd_task_position"),
)

jd_task_detail = sa.Table(
    "jd_task_detail", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("detail_id", UUID(as_uuid=True), nullable=False),
    sa.Column("task_id", UUID(as_uuid=True), nullable=False),
    sa.Column("kind", sa.Text(), nullable=False),
    sa.Column("text", sa.Text(), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint("document_id", "detail_id", name="pk_jd_task_detail"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_task_detail_document", ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["document_id", "task_id"], ["jd_task.document_id", "jd_task.task_id"],
                            name="fk_jd_task_detail_task", ondelete="CASCADE"),
    sa.CheckConstraint("kind IN ('outcome', 'requirement')", name="ck_jd_task_detail_kind"),
    sa.CheckConstraint("position >= 0", name="ck_jd_task_detail_position"),
)

jd_capability = sa.Table(
    "jd_capability", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("capability_id", UUID(as_uuid=True), nullable=False),
    sa.Column("kind", sa.Text(), nullable=False),
    sa.Column("name", sa.Text()),
    sa.Column("description", sa.Text()),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint("document_id", "capability_id", name="pk_jd_capability"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_capability_document", ondelete="RESTRICT"),
    sa.CheckConstraint("kind IN ('knowledge', 'skill')", name="ck_jd_capability_kind"),
    sa.CheckConstraint("name IS NOT NULL OR description IS NOT NULL", name="ck_jd_capability_content"),
    sa.CheckConstraint("position >= 0", name="ck_jd_capability_position"),
)

jd_task_capability = sa.Table(
    "jd_task_capability", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("task_id", UUID(as_uuid=True), nullable=False),
    sa.Column("capability_id", UUID(as_uuid=True), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint("document_id", "task_id", "capability_id", name="pk_jd_task_capability"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_task_capability_document", ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["document_id", "task_id"], ["jd_task.document_id", "jd_task.task_id"],
                            name="fk_jd_task_capability_task", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["document_id", "capability_id"], ["jd_capability.document_id", "jd_capability.capability_id"],
                            name="fk_jd_task_capability_capability", ondelete="RESTRICT"),
    sa.CheckConstraint("position >= 0", name="ck_jd_task_capability_position"),
)

jd_condition = sa.Table(
    "jd_condition", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("condition_id", UUID(as_uuid=True), nullable=False),
    sa.Column("kind", sa.Text(), nullable=False),
    sa.Column("text", sa.Text(), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint("document_id", "condition_id", name="pk_jd_condition"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_condition_document", ondelete="RESTRICT"),
    sa.CheckConstraint("kind IN ('work_environment', 'schedule_travel', 'shared_authority', 'shared_collaboration', 'qualification')",
                       name="ck_jd_condition_kind"),
    sa.CheckConstraint("position >= 0", name="ck_jd_condition_position"),
)

jd_source_link = sa.Table(
    "jd_source_link", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("source_link_id", UUID(as_uuid=True), nullable=False),
    sa.Column("source_ref", sa.Text(), nullable=False),
    sa.Column("basis_digest", sa.CHAR(64), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.Column("profile_field", sa.Text()),
    sa.Column("collaborator_id", UUID(as_uuid=True)),
    sa.Column("duty_id", UUID(as_uuid=True)),
    sa.Column("task_id", UUID(as_uuid=True)),
    sa.Column("detail_id", UUID(as_uuid=True)),
    sa.Column("capability_id", UUID(as_uuid=True)),
    sa.Column("condition_id", UUID(as_uuid=True)),
    sa.Column("linked_task_id", UUID(as_uuid=True)),
    sa.Column("linked_capability_id", UUID(as_uuid=True)),
    sa.PrimaryKeyConstraint("document_id", "source_link_id", name="pk_jd_source_link"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_source_link_document", ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["document_id", "collaborator_id"], ["jd_collaborator.document_id", "jd_collaborator.collaborator_id"],
                            name="fk_jd_source_link_collaborator", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["document_id", "duty_id"], ["jd_duty.document_id", "jd_duty.duty_id"],
                            name="fk_jd_source_link_duty", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["document_id", "task_id"], ["jd_task.document_id", "jd_task.task_id"],
                            name="fk_jd_source_link_task", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["document_id", "detail_id"], ["jd_task_detail.document_id", "jd_task_detail.detail_id"],
                            name="fk_jd_source_link_detail", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["document_id", "capability_id"], ["jd_capability.document_id", "jd_capability.capability_id"],
                            name="fk_jd_source_link_capability", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["document_id", "condition_id"], ["jd_condition.document_id", "jd_condition.condition_id"],
                            name="fk_jd_source_link_condition", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["document_id", "linked_task_id", "linked_capability_id"],
                            ["jd_task_capability.document_id", "jd_task_capability.task_id", "jd_task_capability.capability_id"],
                            name="fk_jd_source_link_relation", ondelete="CASCADE"),
    sa.CheckConstraint("position >= 0", name="ck_jd_source_link_position"),
    sa.CheckConstraint("profile_field IN ('job_title', 'organization_unit', 'employee_name', 'reports_to', 'purpose')",
                       name="ck_jd_source_link_profile_field"),
    sa.CheckConstraint("(linked_task_id IS NULL) = (linked_capability_id IS NULL)", name="ck_jd_source_link_relation_pair"),
    sa.CheckConstraint("num_nonnulls(profile_field, collaborator_id, duty_id, task_id, detail_id, capability_id, condition_id, linked_task_id) = 1",
                       name="ck_jd_source_link_one_target"),
)

jd_revision = sa.Table(
    "jd_revision", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("revision_id", UUID(as_uuid=True), nullable=False),
    sa.Column("revision_number", sa.BigInteger(), nullable=False),
    sa.Column("parent_revision_id", UUID(as_uuid=True)),
    sa.Column("origin", sa.Text(), nullable=False),
    sa.Column("format_version", sa.Integer(), nullable=False),
    sa.Column("engine_profile", sa.Text(), nullable=False),
    sa.Column("snapshot", JSONB(), nullable=False),
    sa.Column("content_digest", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("document_id", "revision_id", name="pk_jd_revision"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_revision_document", ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["document_id", "parent_revision_id"], ["jd_revision.document_id", "jd_revision.revision_id"],
                            name="fk_jd_revision_parent", ondelete="RESTRICT"),
    sa.UniqueConstraint("document_id", "revision_number", name="uq_jd_revision_number"),
    sa.UniqueConstraint("document_id", "parent_revision_id", name="uq_jd_revision_parent"),
    sa.CheckConstraint("revision_number >= 1", name="ck_jd_revision_number"),
    sa.CheckConstraint("origin IN ('initial', 'manual', 'ai')", name="ck_jd_revision_origin"),
    sa.CheckConstraint("(origin = 'initial') = (parent_revision_id IS NULL)", name="ck_jd_revision_initial_parent"),
    sa.CheckConstraint("format_version = 3", name="ck_jd_revision_format_version"),
    sa.CheckConstraint("engine_profile = 'jd-relational-v1'", name="ck_jd_revision_engine_profile"),
)

jd_head = sa.Table(
    "jd_head", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("current_revision_id", UUID(as_uuid=True), nullable=False),
    sa.Column("revision_number", sa.BigInteger(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("document_id", name="pk_jd_head"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_head_document", ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["document_id", "current_revision_id"], ["jd_revision.document_id", "jd_revision.revision_id"],
                            name="fk_jd_head_revision", ondelete="RESTRICT"),
    sa.CheckConstraint("revision_number >= 1", name="ck_jd_head_revision_number"),
)

jd_operation = sa.Table(
    "jd_operation", metadata,
    sa.Column("document_id", sa.String(), nullable=False),
    sa.Column("operation_id", UUID(as_uuid=True), nullable=False),
    sa.Column("request_digest", sa.CHAR(64), nullable=False),
    sa.Column("origin", sa.Text(), nullable=False),
    sa.Column("ai_run_id", sa.String()),
    sa.Column("base_revision_id", UUID(as_uuid=True)),
    sa.Column("result_revision_id", UUID(as_uuid=True)),
    sa.Column("status", sa.Text(), nullable=False),
    sa.Column("receipt", JSONB(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("document_id", "operation_id", name="pk_jd_operation"),
    sa.ForeignKeyConstraint(["document_id"], ["jd_document.id"], name="fk_jd_operation_document", ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["document_id", "base_revision_id"], ["jd_revision.document_id", "jd_revision.revision_id"],
                            name="fk_jd_operation_base", ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["document_id", "result_revision_id"], ["jd_revision.document_id", "jd_revision.revision_id"],
                            name="fk_jd_operation_result", ondelete="RESTRICT"),
    sa.CheckConstraint("origin IN ('manual', 'ai')", name="ck_jd_operation_origin"),
    sa.CheckConstraint("(origin = 'ai') = (ai_run_id IS NOT NULL)", name="ck_jd_operation_origin_run"),
    sa.CheckConstraint("status IN ('committed', 'no_change', 'invalid_input', 'target_missing', 'stale_view', 'relationship_conflict', 'dependent_items', 'save_failed')",
                       name="ck_jd_operation_status"),
    sa.CheckConstraint("(status = 'committed' AND base_revision_id IS NOT NULL AND result_revision_id IS NOT NULL AND result_revision_id <> base_revision_id) "
                       "OR (status = 'no_change' AND base_revision_id IS NOT NULL AND result_revision_id IS NOT NULL AND result_revision_id = base_revision_id) "
                       "OR (status NOT IN ('committed', 'no_change') AND result_revision_id IS NULL)", name="ck_jd_operation_result"),
)

sa.Index("ix_jd_duty_order", jd_duty.c.document_id, jd_duty.c.position, jd_duty.c.duty_id)
sa.Index("ix_jd_task_order", jd_task.c.document_id, jd_task.c.duty_id, jd_task.c.position, jd_task.c.task_id)
sa.Index("ix_jd_task_unassigned", jd_task.c.document_id, jd_task.c.position, jd_task.c.task_id,
         postgresql_where=sa.text("duty_id IS NULL"))
sa.Index("ix_jd_task_detail_order", jd_task_detail.c.document_id, jd_task_detail.c.task_id,
         jd_task_detail.c.kind, jd_task_detail.c.position, jd_task_detail.c.detail_id)
sa.Index("ix_jd_capability_order", jd_capability.c.document_id, jd_capability.c.kind,
         jd_capability.c.position, jd_capability.c.capability_id)
sa.Index("ix_jd_task_capability_reverse", jd_task_capability.c.document_id, jd_task_capability.c.capability_id, jd_task_capability.c.task_id)
sa.Index("ix_jd_condition_order", jd_condition.c.document_id, jd_condition.c.kind, jd_condition.c.position, jd_condition.c.condition_id)
sa.Index("ix_jd_revision_number", jd_revision.c.document_id, jd_revision.c.revision_number.desc())
sa.Index("uq_jd_revision_initial", jd_revision.c.document_id, unique=True, postgresql_where=sa.text("origin = 'initial'"))
sa.Index("ix_jd_operation_created", jd_operation.c.document_id, jd_operation.c.created_at.desc())
sa.Index("ix_jd_operation_ai_run", jd_operation.c.document_id, jd_operation.c.ai_run_id, postgresql_where=sa.text("ai_run_id IS NOT NULL"))
sa.Index("uq_jd_operation_committed_result", jd_operation.c.document_id, jd_operation.c.result_revision_id,
         unique=True, postgresql_where=sa.text("status = 'committed'"))
for target in ("profile_field", "collaborator_id", "duty_id", "task_id", "detail_id", "capability_id", "condition_id"):
    sa.Index(f"ix_jd_source_link_{target}", jd_source_link.c.document_id, jd_source_link.c[target],
             jd_source_link.c.position, jd_source_link.c.source_link_id, postgresql_where=jd_source_link.c[target].is_not(None))
sa.Index("ix_jd_source_link_relation", jd_source_link.c.document_id, jd_source_link.c.linked_task_id,
         jd_source_link.c.linked_capability_id, jd_source_link.c.position, jd_source_link.c.source_link_id,
         postgresql_where=sa.text("linked_task_id IS NOT NULL"))

JD_TABLE_NAMES = frozenset(metadata.tables)
