# Authentication API

## POST /api/v1/auth/login

Authentication:
Bearer JWT or session token

Permissions:
None

Request body:

```json
{
  "email": "user@example.com",
  "password": "secret"
}
```

Validation:
- Email is required and must be a valid address.
- Password is required and must satisfy configured policy.

Response:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "<uuid>",
    "name": "<name>",
    "email": "<email>",
    "role": "admin"
  },
  "permissions": ["dashboard:read", "transactions:read"]
}
```

Errors:
- 401 invalid credentials
- 423 account locked
- 429 rate limited

## POST /api/v1/auth/logout

Authentication:
Bearer JWT

Permissions:
None

## POST /api/v1/auth/refresh

Authentication:
Refresh token

## POST /api/v1/auth/password-reset

## POST /api/v1/auth/password-change

Authentication:
Bearer JWT

Permissions:
users:write

## GET /api/v1/auth/session

Authentication:
Bearer JWT

Returns current authenticated session and permission set.
