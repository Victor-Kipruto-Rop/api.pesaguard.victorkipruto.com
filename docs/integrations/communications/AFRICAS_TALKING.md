# Africa's Talking

## Overview

Africa's Talking is PesaGuard's primary SMS provider. The integration adapts the existing bounded-timeout SMS client to the provider-neutral communication contract, so business logic never depends on Africa's Talking-specific APIs or error strings.

## Provider Adapter

`AfricasTalkingProvider` (in `providers/africas_talking.py`):

- Implements `ProviderAdapter` base class
- Supports `CommunicationChannel.SMS`
- Normalizes Kenyan mobile numbers (`0712345678` → `+254712345678`)
- Maps transport outcomes to internal error categories

## Send Flow

```
NotificationRequest
       │
       ▼
AfricasTalkingProvider.send()
       │
       ├── validate_recipient() → normalize +254...
       │
       ├── client.send_sms(recipient, message, idempotency_key)
       │
       ├── status == "sent"
       │   └── ProviderMessage(provider, message_id, "accepted")
       │
       ├── status == "skipped" → PermanentCommunicationError("not configured")
       │
       ├── reason in {timeout_ambiguous, request_error}
       │   └── TransientCommunicationError (PROVIDER_TIMEOUT / PROVIDER_REQUEST_ERROR)
       │
       └── other → PermanentCommunicationError (PROVIDER_REJECTED)
```

## Status Semantics

| Provider Status | Internal Status | Meaning |
|-----------------|-----------------|---------|
| `sent` (response) | `accepted` | Provider received the request |
| `Delivered` (webhook) | `delivered` | Confirmed delivered to recipient |
| `Failed` (webhook) | `failed` | Provider could not deliver |
| `Expired` (webhook) | `expired` | Message expired before delivery |

**Important:** Provider acceptance (`accepted`) is NOT delivery. `DELIVERED` is only assigned from an authenticated provider callback via the delivery webhook. The system never silently reports `DELIVERED`.

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `AFRICASTALKING_USERNAME` | Yes | API username |
| `AFRICASTALKING_API_KEY` | Yes | API key |
| `AFRICASTALKING_ENVIRONMENT` | Yes | `sandbox` or `production` |
| `AFRICASTALKING_WEBHOOK_SECRET` | Yes | HMAC-SHA256 webhook verification |
| `AFRICASTALKING_CALLBACK_BASE_URL` | Yes | Delivery callback base URL |
| `AFRICASTALKING_SENDER_ID` | No | Default sender ID |
| `AFRICASTALKING_SHORTCODE` | No | Default shortcode |
| `AFRICASTALKING_TIMEOUT_SECONDS` | No | Request timeout (default 10) |
| `AFRICASTALKING_MAX_RETRIES` | No | Transport retries (default 5) |

The canonical secret is `AFRICASTALKING_WEBHOOK_SECRET`. Runtime compatibility also accepts the historical `AFRICAS_TALKING_WEBHOOK_SECRET`.

## Webhook Callback

Register this endpoint with Africa's Talking:

```
POST /api/v1/webhooks/africastalking/delivery
```

**Header:** `X-Africa-Talking-Signature: <hmac-sha256 hex>`

The callback includes provider message ID and delivery status. The platform verifies the signature, validates the timestamp, deduplicates, and updates the notification lifecycle.

## Error Classification

Africa's Talking errors are mapped to internal categories:

| Africa's Talking | Internal Category |
|------------------|-------------------|
| Timeout | `TIMEOUT` |
| Network/DNS failure | `NETWORK_ERROR` |
| 401/403 auth | `AUTHENTICATION_ERROR` |
| 429 rate limit | `RATE_LIMITED` |
| Invalid recipient | `INVALID_RECIPIENT` |
| Insufficient balance | `INSUFFICIENT_BALANCE` |
| Unknown rejection | `MESSAGE_REJECTED` |

Business logic uses internal categories only.

## Feature Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `PESAGUARD_FLAG_AFRICASTALKING_SMS` | true | Enable SMS sends |
| `PESAGUARD_FLAG_AFRICASTALKING_USSD` | false | Enable USSD (future) |
| `PESAGUARD_FLAG_AFRICASTALKING_VOICE` | false | Enable voice (future) |
| `PESAGUARD_FLAG_AFRICASTALKING_WHATSAPP` | false | Enable WhatsApp (future) |

## Best Practices

1. Start in `sandbox` until delivery is verified
2. Rotate credentials through the secret manager
3. Test with one controlled sandbox send + callback before production
4. Monitor provider health score and circuit breaker state
5. Never expose API keys in source, logs, or frontend bundles
