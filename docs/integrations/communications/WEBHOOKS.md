# Delivery Webhooks

## Overview

Delivery webhooks provide the confirmation channel that turns "sent" into "delivered". The endpoint authenticates callbacks, validates timestamps, deduplicates events, and updates notification lifecycle status.

## Endpoint

```
POST /api/v1/webhooks/africastalking/delivery
```

**Required headers:**
- `X-Africa-Talking-Signature`: HMAC-SHA256 hex digest of the raw request body
- Legacy alias: `X-Webhook-Signature`

## Processing Pipeline

```
Webhook Request
       │
       ▼
1. Verify HMAC-SHA256 signature
       │
       ▼
2. Parse JSON, validate object shape
       │
       ▼
3. Timestamp validation (replay protection)
   - Skew window: 60 seconds in the future
   - Max age: PESAGUARD_WEBHOOK_MAX_AGE_SECONDS (default 300s)
       │
       ▼
4. Idempotency check (provider_event_id + event_type)
   - Duplicate → return {"status": "duplicate"}
       │
       ▼
5. Resolve notification by provider_message_id
       │
       ▼
6. Store webhook event (inbox pattern)
   - payload_hash: SHA-256 of raw body
   - processing_status: pending → processed
       │
       ▼
7. Apply delivery status to notification
   - Create delivery report
   - Update notification status via state machine
       │
       ▼
8. Emit notification.status lifecycle event (best-effort)
```

## Payload Schema

```json
{
  "id": "event-123",                    // Required: provider event ID
  "messageId": "AT-456",                // Required: provider message ID
  "status": "Delivered",                // delivery/sent/submitted/delivered/failed/expired/rejected
  "eventType": "sms.delivery",          // Optional
  "timestamp": "2026-09-08T01:23:45Z"   // Optional: replay protection
}
```

## Status Mapping

| Provider Status | Notification Status |
|-----------------|---------------------|
| `delivered` / `delivery` / `success` | DELIVERED |
| `sent` / `submitted` | SUBMITTED |
| `expired` | EXPIRED |
| `failed` / `rejected` / `undelivered` | FAILED |

## Unknown Notification Handling

Callbacks referencing unknown notifications are stored as `unprocessed` in the inbox and return `{"status": "pending_review"}`. This prevents provider retry storms while allowing administrative investigation.

## Admin Replay

Stored webhook events can be replayed or ignored by administrators:

```
POST /api/v1/communications/webhook-events/<event_id>/replay   (requires manage:communications)
POST /api/v1/communications/webhook-events/<event_id>/ignore   (requires manage:communications)
```

## Security Controls

1. **HMAC-SHA256 signature** - Required, verified against `AFRICASTALKING_WEBHOOK_SECRET`
2. **Timestamp validation** - Rejects stale/future callbacks
3. **Payload hashing** - SHA-256 recorded for tamper evidence
4. **Idempotency** - Unique `(provider, provider_event_id, event_type)` constraint
5. **Size limits** - Body limited by `PESAGUARD_WEBHOOK_MAX_BODY_BYTES`
6. **No sensitive logging** - Payloads stored, never logged in plaintext logs

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AFRICASTALKING_WEBHOOK_SECRET` | (required) | HMAC verification secret |
| `PESAGUARD_WEBHOOK_MAX_BODY_BYTES` | (app config) | Max payload size |
| `PESAGUARD_WEBHOOK_MAX_AGE_SECONDS` | 300 | Max callback age |

## Troubleshooting

| Symptom | Cause | Action |
|---------|-------|--------|
| 401 Unauthorized | Invalid HMAC signature | Verify `AFRICASTALKING_WEBHOOK_SECRET` matches provider config |
| 413 Payload too large | Body exceeds limit | Increase `PESAGUARD_WEBHOOK_MAX_BODY_BYTES` |
| Pending review events | Unknown message ID | Check provider_message_id matching |
| Duplicate events | Provider retries | Expected; deduplication handles it |
