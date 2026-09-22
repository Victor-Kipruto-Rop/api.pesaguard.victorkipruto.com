# Transactions API

## GET /api/v1/transactions

Authentication:
Bearer JWT

Permissions:
transactions:read

Query parameters:
- page
- limit
- search
- status
- source
- customer
- transaction_id
- mpesa_receipt
- phone
- amount_min
- amount_max
- date_from
- date_to
- risk_level
- reconciliation_state
- sort
- order

Response:

```json
{
  "items": [
    {
      "id": "<uuid>",
      "transaction_id": "<txn>",
      "mpesa_receipt": "<receipt>",
      "customer": "<customer>",
      "phone": "+254...",
      "amount": "100.00",
      "currency": "KES",
      "status": "completed",
      "type": "paybill",
      "source": "daraja",
      "risk_level": "low",
      "reconciliation_state": "matched",
      "timestamp": "2026-09-09T00:00:00Z"
    }
  ],
  "page": 1,
  "limit": 25,
  "total": 1,
  "total_pages": 1
}
```

## GET /api/v1/transactions/{id}

Returns transaction detail with timeline and audit context.

## POST /api/v1/transactions

Authentication:
Bearer JWT

Permissions:
transactions:write

Creates a transaction record. Reserved for internal or admin-only ingestion events.

## PATCH /api/v1/transactions/{id}

Authentication:
Bearer JWT

Permissions:
transactions:write

## DELETE /api/v1/transactions/{id}

Authentication:
Bearer JWT

Permissions:
transactions:write

## POST /api/v1/transactions/{id}/reconcile

## POST /api/v1/transactions/{id}/retry

## POST /api/v1/transactions/{id}/mark-reviewed

## POST /api/v1/transactions/{id}/flag

## POST /api/v1/transactions/{id}/unflag

These endpoints must write an audit entry and require appropriate permissions.
