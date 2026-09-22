# Audit API

## GET /api/v1/audit

Authentication:
Bearer JWT

Permissions:
audit:read

Returns audit records with:

- actor
- action
- resource
- timestamp
- ip
- metadata
- result

End points for audit include auth, transaction, reconciliation, anomaly, alert, user, role, settings, integration, and report-related events.
