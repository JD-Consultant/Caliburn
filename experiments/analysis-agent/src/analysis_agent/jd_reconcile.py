"""Finite stopped-writer evidence and original-identity reconciliation ports."""
from dataclasses import dataclass
from uuid import UUID
from analysis_agent.jd_types import JdScope
from analysis_agent.publication import PublicationUncertain


@dataclass(frozen=True)
class JdWriterStopped:
    scope: JdScope
    native_calls: object
    writer_idle: object
    prior_lifecycle: object = None
    prior_execution: bool = False

    def require(self, scope):
        if scope != self.scope or not self.native_calls.quiescent or not self.writer_idle():
            raise PublicationUncertain('JD writer/native cleanup is not confirmed')
        if self.prior_execution:
            if self.prior_lifecycle is None:
                raise PublicationUncertain('Prior API containment proof is unavailable')
            self.prior_lifecycle.verify()


@dataclass(frozen=True)
class JdAdmittedIdentity:
    """No candidate: permits only terminal failure for a persisted admission."""
    scope: JdScope
    operation_id: UUID
    base_id: UUID
    digest: str
    origin: str


def reconcile_identity(store, identity, proof):
    """One lock/lookup attempt, then a separate failure-only closure if absent."""
    from analysis_agent.jd_store import failure
    proof.require(identity.scope)
    try:
        result = store.reconcile_after_writer_stopped(identity, proof)
        if result is None:
            result = store.publish(identity, error=failure(identity, 'save_failed', base_id=identity.base_id))
    except Exception as exc:
        raise PublicationUncertain('JD receipt/transaction boundary is unavailable') from exc
    if result.durability != 'confirmed' or result.status == 'operation_conflict':
        raise PublicationUncertain('Original JD identity is not terminal')
    return result
