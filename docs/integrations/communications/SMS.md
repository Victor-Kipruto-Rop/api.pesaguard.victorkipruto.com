# SMS Messaging

## Overview

SMS is the primary communication channel for PesaGuard, delivered through Africa's Talking. The SMS system handles transaction receipts, fraud alerts, security notifications, and marketing messages.

## SMS Architecture

```
Business Event
       │
       ▼
Policy Engine → SMS channel selected
       │
       ▼
CommunicationNotification (channel=sms)
       │
       ▼
CommunicationOutboxEntry (queued)
       │
       ▼
Worker leases entry → AfricasTalkingProvider.send()
       │
       ▼
Africa's Talking API → Telco → Customer
       │
       ▼
Delivery callback → Webhook → Status update
```

## Message Segmentation

SMS messages are segmented based on character encoding:

| Encoding | Single Segment | Multi-Segment |
|----------|---------------|---------------|
| GSM-7 | 160 chars | 153 chars/segment |
| Unicode | 70 chars | 67 chars/segment |

The cost engine calculates segments for accurate cost attribution.

### GSM-7 Character Set

Standard GSM-7 includes: `@£$¥èéùìòÇØøÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ!\"#¤%&'()*+,-./0-9:;<=>?¡A-Z§¿a-zäöñüà^{}\[~]|€`

Any character outside this set triggers Unicode encoding (70 char limit).

## Cost Calculation

Default cost: KES 0.80 per segment (configurable via `PESAGUARD_COMMUNICATION_UNIT_COSTS`).

```python
cost = build_cost(CommunicationChannel.SMS, message)
# {
#     "provider_channel": "sms",
#     "segments": 2,
#     "unit_cost": 0.8,
#     "total_cost": 1.6,
#     "currency": "KES"
# }
```

## Template System

Templates support variable substitution with version control:

```python
template = create_template(
    session,
    tenant_id="tenant-a",
    slug="transaction_receipt",
    channel=CommunicationChannel.SMS,
    body="Payment of {amount} {currency} received. Ref: {ref}",
    variables=["amount", "currency", "ref"],
)

# Approve for use
approve_template(session, template, approver="operator-1")

# Render
message = render_template(template, {"amount": "1500", "currency": "KES", "ref": "PG-123"})
# "Payment of 1500 KES received. Ref: PG-123"
```

## Delivery Flow

### 1. Send Request
```
POST /api/v1/communications/sms
{
    "recipient": "+254700000001",
    "message": "Payment received",
    "idempotency_key": "unique-key",
    "priority": "normal"
}
```

### 2. Queuing
- Notification persisted with status `QUEUED`
- Outbox entry created in same transaction
- Idempotency key prevents duplicate sends

### 3. Worker Processing
- Worker leases entry (priority-aware)
- Calls `AfricasTalkingProvider.send()`
- Records attempt with cost and latency
- On success: status → `ACCEPTED`
- On failure: retry with backoff or dead-letter

### 4. Delivery Confirmation
```
POST /api/v1/webhooks/africastalking/delivery
{
    "id": "event-123",
    "messageId": "AT-456",
    "status": "Delivered"
}
```

- HMAC-SHA256 signature verified
- Timestamp validated (replay protection)
- Notification status → `DELIVERED`

## Status Lifecycle

```
CREATED → QUEUED → PROCESSING → ACCEPTED → SUBMITTED → DELIVERED
                         │
                         ↓
                      FAILED → RETRYING → PROCESSING
                         │
                         ↓
                      DEAD_LETTER
```

## Error Handling

| Error | Category | Action |
|-------|----------|--------|
| Timeout | TIMEOUT | Retry with backoff |
| Network failure | NETWORK_ERROR | Retry with backoff |
| Rate limited | RATE_LIMITED | Retry with backoff |
| Invalid recipient | INVALID_RECIPIENT | Dead letter |
| Auth failure | AUTHENTICATION_ERROR | Raise immediately |
| Insufficient balance | INSUFFICIENT_BALANCE | Alert operator |

## Configuration

```bash
# Required
export AFRICASTALKING_USERNAME="your-username"
export AFRICASTALKING_API_KEY="your-api-key"
export AFRICASTALKING_ENVIRONMENT="sandbox"
export AFRICASTALKING_WEBHOOK_SECRET="your-secret"
export AFRICASTALKING_CALLBACK_BASE_URL="https://your-domain.com"

# Optional
export AFRICASTALKING_SENDER_ID="PesaGuard"
export AFRICASTALKING_TIMEOUT_SECONDS="10"
export AFRICASTALKING_MAX_RETRIES="5"
```

## Monitoring

Key metrics:
- Send success rate
- Delivery rate (confirmed sends)
- Average latency
- Segments per message
- Cost per day/week/month
- Dead-letter count
- Retry rate