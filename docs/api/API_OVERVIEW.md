# PesaGuard API Contract

This directory documents the authoritative public API contract for the PesaGuard backend. The project is implemented as a Flask and SQLAlchemy service with REST-style blueprints and operational routes grouped around tenant, finance, reconciliation, anomaly, notification, reporting, integration, audit, user, role, settings, and health concerns.

## Base URL

The public API base path is versioned and should be routed as:

```
/api/v1
```

## Authentication

Authentication uses a bearer token pattern compatible with the existing Flask/JWT-style RBAC stack in the repository.

Example:

```
Authorization: Bearer <token>
```

The backend must validate token issuer, audience, and tenant claims where applicable.

## Permission Model

Permissions are expressed as resource-oriented scopes such as:

- dashboard:read
- transactions:read
- transactions:write
- transactions:export
- reconciliation:read
- reconciliation:create
- anomalies:read
- anomalies:investigate
- alerts:read
- alerts:acknowledge
- customers:read
- customers:write
- reports:read
- reports:create
- integrations:read
- integrations:manage
- users:read
- users:write
- audit:read
- settings:read
- settings:write

## Common Response Format

Errors should use a normalized envelope:

```json
{
  "error": {
    "code": "TRANSACTION_NOT_FOUND",
    "message": "Transaction could not be found.",
    "request_id": "<uuid>"
  }
}
```

Successful paginated responses should include metadata such as:

```json
{
  "items": [],
  "page": 1,
  "limit": 25,
  "total": 0,
  "total_pages": 0
}
```

## Core Endpoint Map

- `/api/v1/auth`
- `/api/v1/dashboard`
- `/api/v1/transactions`
- `/api/v1/reconciliation`
- `/api/v1/anomalies`
- `/api/v1/alerts`
- `/api/v1/customers`
- `/api/v1/reports`
- `/api/v1/integrations`
- `/api/v1/webhooks`
- `/api/v1/audit`
- `/api/v1/users`
- `/api/v1/roles`
- `/api/v1/settings`
- `/api/v1/health`

## Status Codes

- 200 OK
- 201 Created
- 202 Accepted
- 204 No Content
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 409 Conflict
- 422 Unprocessable Entity
- 429 Too Many Requests
- 500 Internal Server Error
- 502 Bad Gateway
- 503 Service Unavailable
- 504 Gateway Timeout
