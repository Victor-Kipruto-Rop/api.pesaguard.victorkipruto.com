# Webhooks API

## GET /api/v1/webhooks

Authentication:
Bearer JWT

Permissions:
integrations:read

Returns webhook delivery events with fields:

- event_id
- event_type
- source
- received_time
- processing_time
- status
- http_status
- retry_count
- error
- transaction_id

## GET /api/v1/webhooks/{id}

## POST /api/v1/webhooks/{id}/retry

Authentication:
Bearer JWT

Permissions:
integrations:manage

Webhook processing must be idempotent and safe against replayed callbacks. Existing repository idempotency and transaction event management patterns should be preserved.
