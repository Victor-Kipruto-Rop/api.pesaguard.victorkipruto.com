"""Controlled transaction deletion and anonymization workflow."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from action_audit import AuditLegalHold
from models import (
    AuditEvent,
    DeletionRequest,
    Discrepancy,
    FraudRiskAssessment,
    IdempotencyRecord,
    ProcessedTransaction,
    ReconciliationMatch,
    ReconciliationOutbox,
    Transaction,
    TransactionEvent,
    TransactionOutbox,
    TransformationRecord,
)
from retention_policy import RetentionPolicy, load_retention_policy


class DeletionWorkflowError(ValueError):
    """Raised when a deletion request cannot proceed safely."""


class DeletionWorkflow:
    def __init__(self, policy: RetentionPolicy | None = None):
        self.policy = policy or load_retention_policy()

    def request(self, session: Any, *, tenant_id: str, transaction_id: str, requested_by: str, reason: str) -> DeletionRequest:
        if not all(str(value).strip() for value in (tenant_id, transaction_id, requested_by, reason)):
            raise DeletionWorkflowError("tenant, transaction, requester, and reason are required")
        transaction = session.query(Transaction).filter_by(tenant_id=tenant_id, id=transaction_id).first()
        if transaction is None:
            raise DeletionWorkflowError("transaction not found in tenant scope")
        request = DeletionRequest(
            id=f"del_{uuid.uuid4().hex}",
            tenant_id=tenant_id,
            transaction_id=transaction_id,
            requested_by=requested_by,
            reason=reason,
            status="pending",
        )
        session.add(request)
        session.commit()
        return request

    def dependency_report(self, session: Any, *, tenant_id: str, transaction_id: str) -> Dict[str, int]:
        filters = lambda model: model.tenant_id == tenant_id
        return {
            "transaction_events": session.query(TransactionEvent).filter(filters(TransactionEvent), TransactionEvent.transaction_id == transaction_id).count(),
            "processed_transactions": session.query(ProcessedTransaction).filter(filters(ProcessedTransaction), ProcessedTransaction.daraja_trans_id == transaction_id).count(),
            "idempotency_records": session.query(IdempotencyRecord).filter(filters(IdempotencyRecord), IdempotencyRecord.provider_transaction_id == transaction_id).count(),
            "reconciliation_matches": session.query(ReconciliationMatch).filter(filters(ReconciliationMatch), ReconciliationMatch.transaction_id == transaction_id).count(),
            "fraud_assessments": session.query(FraudRiskAssessment).filter(filters(FraudRiskAssessment), FraudRiskAssessment.transaction_id == transaction_id).count(),
            "discrepancies": session.query(Discrepancy).filter(filters(Discrepancy), Discrepancy.trans_id == transaction_id).count(),
            "transformation_records": session.query(TransformationRecord).filter(filters(TransformationRecord), TransformationRecord.transaction_id == transaction_id).count(),
            "transaction_outbox": session.query(TransactionOutbox).filter(filters(TransactionOutbox), TransactionOutbox.payload.contains({"TransID": transaction_id})).count(),
            "reconciliation_outbox": session.query(ReconciliationOutbox).filter(filters(ReconciliationOutbox), ReconciliationOutbox.payload.contains({"trans_id": transaction_id})).count(),
            "audit_events_retained": session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id, AuditEvent.aggregate_id == transaction_id).count(),
        }

    def execute(
        self,
        session: Any,
        request_id: str,
        *,
        authorize: Callable[[DeletionRequest], bool],
        authorization_reference: str,
        now: datetime | None = None,
    ) -> DeletionRequest:
        request = session.query(DeletionRequest).filter_by(id=request_id).with_for_update().first()
        if request is None:
            raise DeletionWorkflowError("deletion request not found")
        if request.status != "pending":
            raise DeletionWorkflowError("deletion request is not pending")
        if not authorization_reference or not authorize(request):
            request.status = "rejected"
            request.decision = "authorization_denied"
            session.commit()
            return request
        transaction = session.query(Transaction).filter_by(id=request.transaction_id, tenant_id=request.tenant_id).with_for_update().first()
        if transaction is None:
            raise DeletionWorkflowError("transaction not found in tenant scope")
        report = self.dependency_report(session, tenant_id=request.tenant_id, transaction_id=request.transaction_id)
        request.dependency_report = report
        current = now or datetime.now(timezone.utc)
        created_at = transaction.created_at.astimezone(timezone.utc) if transaction.created_at.tzinfo else transaction.created_at.replace(tzinfo=timezone.utc)
        retained_until = created_at + __import__("datetime").timedelta(days=self.policy.retention_days("transactions"))
        hold = session.query(AuditLegalHold).filter(
            AuditLegalHold.tenant_id == request.tenant_id,
            AuditLegalHold.active.is_(True),
            (AuditLegalHold.expires_at.is_(None) | (AuditLegalHold.expires_at > current)),
            ((AuditLegalHold.scope_type == "tenant") | ((AuditLegalHold.scope_type == "transaction") & (AuditLegalHold.scope_id.in_([request.transaction_id, transaction.trans_id])))),
        ).first()
        retained = current < retained_until or hold is not None
        if retained:
            transaction.msisdn = "redacted:" + hashlib.sha256(str(transaction.msisdn).encode()).hexdigest()[:16]
            transaction.raw_payload = {"redacted": True, "payload_hash": hashlib.sha256(json.dumps(transaction.raw_payload, sort_keys=True, default=str).encode()).hexdigest()}
            request.status = "anonymized"
            request.decision = "retention_or_legal_hold"
        else:
            for model, column in (
                (TransactionEvent, TransactionEvent.transaction_id),
                (ProcessedTransaction, ProcessedTransaction.daraja_trans_id),
                (IdempotencyRecord, IdempotencyRecord.provider_transaction_id),
                (ReconciliationMatch, ReconciliationMatch.transaction_id),
                (FraudRiskAssessment, FraudRiskAssessment.transaction_id),
                (Discrepancy, Discrepancy.trans_id),
                (TransformationRecord, TransformationRecord.transaction_id),
            ):
                session.query(model).filter(model.tenant_id == request.tenant_id, column == request.transaction_id).delete(synchronize_session=False)
            session.query(TransactionOutbox).filter(
                TransactionOutbox.tenant_id == request.tenant_id,
                TransactionOutbox.payload.contains({"TransID": request.transaction_id}),
            ).delete(synchronize_session=False)
            session.query(ReconciliationOutbox).filter(
                ReconciliationOutbox.tenant_id == request.tenant_id,
                ReconciliationOutbox.payload.contains({"trans_id": request.transaction_id}),
            ).delete(synchronize_session=False)
            session.delete(transaction)
            request.status = "deleted"
            request.decision = "policy_eligible"
        request.authorization_reference = authorization_reference
        request.completed_at = current
        session.add(AuditEvent(
            id=f"audit_{uuid.uuid4().hex[:12]}",
            tenant_id=request.tenant_id,
            event_key=f"deletion:{request.id}",
            event_type="data.deletion_completed",
            aggregate_type="transaction",
            aggregate_id=request.transaction_id,
            actor=request.requested_by,
            payload_hash=hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest(),
            details={"request_id": request.id, "decision": request.decision, "authorization_reference": authorization_reference},
            created_at=current,
        ))
        session.commit()
        return request