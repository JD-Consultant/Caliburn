"""Back up one installation and get it back, on real PostgreSQL.

Dumps a real fixture installation with the server's own pg_dump 18.6, restores
it into a new empty database, and then checks what actually came back: the JD's
own revisions digest for digest, the conversation checkpoints that make
continuing an interview possible, and the signed references that only the
backed-up configuration's key can resolve.

Nothing is dropped, cleared or overwritten: the restore target is a new
database created for this drill. No provider is reached.

Usage: backup_restore_drill.py <fixture directory>
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

APP = Path("S:/caliburn/experiments/jd-relational-app")
sys.path.insert(0, str(APP / "src"))
sys.path.insert(0, str(APP / "tests"))
sys.path.insert(0, str(APP / "tests" / "support"))

TARGET = Path(sys.argv[1]).resolve()
assert TARGET.parent == Path("S:/caliburn/.research-tmp") and TARGET.name.startswith("jd-ui-gate-")
HERE = Path(__file__).resolve().parent
CONTAINER = "caliburn-jd-relational-test-postgres-1"
ADMIN = dict(host="127.0.0.1", port=55436, dbname="caliburn_jd_relational_test",
             user="jd_test", password="jd-local-test-only", connect_timeout=5)
JD_TABLES = 14
report = {"format": 1, "drill": "backup_and_restore", "provider_calls": 0,
          "ran_at_utc": datetime.now(timezone.utc).isoformat()}


def psql_env():
    return ["-e", "PGPASSWORD=jd-local-test-only"]


def dump(database, path, *, only_public=False):
    """The server's own pg_dump, custom format, one whole database."""
    command = ["docker", "exec", *psql_env(), CONTAINER, "pg_dump", "-U", "jd_test",
               "-d", database, "-Fc"]
    if only_public:
        command += ["-n", "public"]
    with path.open("wb") as out:
        done = subprocess.run(command, stdout=out, stderr=subprocess.PIPE)
    assert done.returncode == 0, done.stderr.decode(errors="replace")[-600:]
    return path.stat().st_size


def create_database(name):
    from psycopg import Connection, sql
    with Connection.connect(**ADMIN, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
            sql.Identifier(name), sql.Identifier("jd_test")))
    return name


def contents(path):
    """What objects a dump actually carries, from pg_restore's own listing."""
    with path.open("rb") as source:
        done = subprocess.run(["docker", "exec", "-i", CONTAINER, "pg_restore", "-l"],
                              stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert done.returncode == 0, done.stderr.decode(errors="replace")[-600:]
    return done.stdout.decode("utf-8", errors="replace")


def restore(database, path):
    with path.open("rb") as source:
        done = subprocess.run(
            ["docker", "exec", "-i", *psql_env(), CONTAINER, "pg_restore", "-U", "jd_test",
             "-d", database, "--no-owner"],
            stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # pg_restore reports non-fatal notices on stderr; a non-zero code is the failure.
    assert done.returncode == 0, done.stderr.decode(errors="replace")[-800:]


def read(database, statement, arguments=()):
    from psycopg import Connection
    with Connection.connect(**{**ADMIN, "dbname": database}) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            return connection.execute(statement, arguments).fetchall()


def shape(database, document=None):
    """What is actually in this database, read only."""
    jd = read(database, "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name LIKE %s",
              ("jd\\_%",))[0][0]
    runtime = {}
    for table in ("checkpoints", "checkpoint_writes", "store"):
        try:
            runtime[table] = read(database, f"SELECT count(*) FROM jd_runtime.{table}")[0][0]
        except Exception:
            runtime[table] = None  # The schema is not there at all.
    answer = {"jd_tables": jd, "runtime": runtime}
    if document:
        answer["revisions"] = [
            {"number": row[0], "digest": row[1], "origin": row[2]}
            for row in read(database,
                            "SELECT revision_number, content_digest, origin FROM jd_revision "
                            "WHERE document_id=%s ORDER BY revision_number", (document,))]
        answer["operations"] = read(
            database, "SELECT count(*) FROM jd_operation WHERE document_id=%s", (document,))[0][0]
        answer["title"] = read(database, "SELECT title FROM jd_document WHERE id=%s",
                               (document,))[0][0]
    return answer


def main():
    from jd_relational.local_configuration import parse_configuration
    from jd_relational.references import ReferenceCodec, ReferenceValidationError, SignedReference
    from ui_response_gate_server import fixture_file, manifest

    value = manifest(TARGET)
    database = value["database"]
    settings = parse_configuration(fixture_file(TARGET, value).read())
    document = read(database, "SELECT id FROM jd_document ORDER BY created_at LIMIT 1")[0][0]
    head = read(database, "SELECT current_revision_id FROM jd_head WHERE document_id=%s",
                (document,))[0][0]

    # A reference the employee's page really holds, issued before the backup.
    codec = ReferenceCodec(settings.signing_key_bytes(), settings.dataset_id)
    issued = codec.issue(SignedReference(document_id=document, revision_id=str(head),
                                         purpose="history", role="revision", kind="revision"))

    before = shape(database, document)
    assert before["jd_tables"] == JD_TABLES, before["jd_tables"]
    assert before["runtime"]["checkpoints"], "the drill needs a real conversation to lose"

    backups = TARGET / "backup"
    backups.mkdir(exist_ok=True)
    whole, public_only = backups / "whole.dump", backups / "public-only.dump"
    report["backup_bytes"] = dump(database, whole)
    report["public_only_backup_bytes"] = dump(database, public_only, only_public=True)

    # 1. A whole-database backup restored into a new, empty database.
    restored = create_database(database[:40] + "_restored_" + uuid4().hex[:8])
    restore(restored, whole)
    after = shape(restored, document)
    report["restored_database"] = restored
    report["before"], report["after"] = before, after
    assert after["jd_tables"] == before["jd_tables"]
    assert after["revisions"] == before["revisions"], "a revision came back different"
    assert after["operations"] == before["operations"] and after["title"] == before["title"]
    assert after["runtime"] == before["runtime"], "the conversation did not come back"
    report["jd_and_conversation_both_restored"] = True

    # 2. Backing up only the JD leaves nothing to continue the interview from.
    #    Read what each dump carries from pg_restore's own listing rather than
    #    restoring a knowingly incomplete backup over anything.
    whole_listing, thin_listing = contents(whole), contents(public_only)
    report["whole_backup_carries_runtime_objects"] = sum(
        1 for line in whole_listing.splitlines() if " jd_runtime " in line)
    report["public_only_backup_carries_runtime_objects"] = sum(
        1 for line in thin_listing.splitlines() if " jd_runtime " in line)
    assert report["whole_backup_carries_runtime_objects"] > 0
    assert report["public_only_backup_carries_runtime_objects"] == 0
    assert "jd_revision" in thin_listing, "the JD itself is in there"
    assert "checkpoints" not in thin_listing, thin_listing[:400]
    report["public_only_backup_loses_the_conversation"] = True

    # 3. The configuration file is part of the backup: only its key resolves
    #    what the employee's page is already holding.
    resolved = codec.resolve(issued, document_id=document, roles={"revision"},
                             purposes={"history"})
    assert resolved.revision_id == str(head)
    stranger = ReferenceCodec(bytes(32), str(uuid4()))
    for wrong, why in ((ReferenceCodec(bytes(32), settings.dataset_id), "another signing key"),
                       (ReferenceCodec(settings.signing_key_bytes(), str(uuid4())),
                        "another dataset"),
                       (stranger, "a fresh installation")):
        try:
            wrong.resolve(issued, document_id=document, roles={"revision"}, purposes={"history"})
            raise AssertionError(f"{why} must not resolve a reference it never issued")
        except ReferenceValidationError:
            pass
    report["only_the_backed_up_configuration_resolves_old_references"] = True

    # 4. No provider key material travels in the backup.
    for path in (whole, public_only):
        blob = path.read_bytes()
        for marker in (b"sk-ant", b"sk-proj", b"ANTHROPIC_API_KEY", b"OPENAI_API_KEY",
                       b"Caliburn JD/anthropic", b"Caliburn JD/openai"):
            assert marker not in blob, marker
    report["backup_contains_no_provider_key"] = True

    (HERE / "drill.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    print("backup and restore drill OK")


main()
