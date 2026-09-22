# Data Dictionary

## Overview

This dictionary defines the most important business and operational data elements used in PesaGuard. It is intended as a practical reference for engineering, audit, and product review.

## Core entity definitions

### Transaction

Represents a financial transaction received from a provider or internal system.

| Field | Type | Required | Description |
|---|---|---:|---|
| tenant_id | string | yes | Tenant or customer boundary for the transaction |
| provider_account_id | string | yes | Provider account instance used for the transaction |
| provider | string | yes | Source provider, e.g. mpesa |
| trans_id | string | yes | Unique provider transaction id |
| provider_transaction_id | string | yes | Canonical provider transaction identifier |
| external_reference | string | no | Business or merchant-side reference |
| trans_amount | decimal | yes | Transaction amount in the currency unit |
| currency | string | yes | ISO 4217 code, usually KES |
| msisdn | string | yes | Mobile number associated with the transaction |
| business_short_code | string | yes | M-Pesa short code or provider business identifier |
| trans_time | string | yes | Raw provider timestamp |
| status | string | yes | Lifecycle state of the transaction |
| raw_payload | json | yes | Original payload for replay and forensic audit |
| idempotency_key | string | yes | Scope-specific dedupe key |
| created_at | datetime | yes | Creation timestamp in UTC |

### IdempotencyRecord

Tracks durable deduplication identity for request processing.

| Field | Type | Required | Description |
|---|---|---:|---|
| tenant_id | string | yes | Tenant owning the operation |
| provider | string | yes | Source provider or platform |
| idempotency_key | string | yes | Stable dedupe identity |
| provider_transaction_id | string | yes | Provider-level identifier |
| request_hash | string | yes | Hash for verifying payload identity |
| response | json | no | Stored result for safe replay |
| created_at | datetime | yes | Time the record was created |

### AuditEvent

Append-only evidence of important business and operational events.

| Field | Type | Required | Description |
|---|---|---:|---|
| tenant_id | string | yes | Tenant scope |
| event_key | string | yes | Stable event identifier |
| event_type | string | yes | event category or action |
| aggregate_type | string | yes | Domain entity type |
| aggregate_id | string | yes | Domain entity instance |
| actor | string | yes | Actor or caller responsible |
| payload_hash | string | yes | Hash of payload for evidence preservation |
| details | json | yes | Event-specific metadata |
| created_at | datetime | yes | Timestamp of the audit record |

### ReconciliationMatch

Stores the outcome of a reconciliation decision.

| Field | Type | Required | Description |
|---|---|---:|---|
| tenant_id | string | yes | Tenant scope |
| transaction_id | string | yes | Matching transaction record |
| matched_record | json | no | Candidate internal record |
| matching_rules | json | yes | Rules that produced this outcome |
| match_score | numeric | yes | Confidence score between 0 and 1 |
| status | string | yes | One of matched/unmatched/partial/etc. |
| engine_version | string | yes | Version of the engine used |
| processing_latency_ms | numeric | yes | Processing time measure |
| created_at | datetime | yes | Time of reconciliation |

### TransactionEvent

Tracks state transitions through a transaction lifecycle.

| Field | Type | Required | Description |
|---|---|---:|---|
| tenant_id | string | yes | Tenant scope |
| transaction_id | string | no | Related transaction |
| trans_id | string | yes | Transaction id for traceability |
| event_key | string | yes | Unique event identifier |
| event_type | string | yes | Event type or lifecycle step |
| from_state | string | no | Prior state |
| to_state | string | yes | New state |
| actor | string | yes | Responsible actor |
| reason | string | no | Explainable reason code |
| payload_hash | string | no | Hash to validate payload integrity |
| correlation_id | string | no | End-to-end correlation trace |
| details | json | yes | Additional details |
| created_at | datetime | yes | Time of the state transition |

## Shared governance rules

- All tenant-scoped data must carry `tenant_id` and must be queried with correct access policy.
- All raw financial payloads should be preserved with a hash and correlation metadata.
- All status values should come from approved enums and versioned logic.
- All sensitive fields should be redacted before logs and operational traces.
- All data changes should be auditable and traceable to an actor or system process.

## Data quality expectations

The platform should validate the following before data is treated as authoritative:

- required fields are present and non-empty
- amount is positive and in the correct currency format
- duplicates are detected before processing continues
- timestamps are normalized and timezone-aware
- correlation IDs exist for operational troubleshooting
- audit context is available for business decisions
