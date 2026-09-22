# Reconciliation API

## GET /api/v1/reconciliation/overview

Authentication:
Bearer JWT

Permissions:
reconciliation:read

Returns reconciliation status totals and productivity indicators.

## GET /api/v1/reconciliation/runs

Returns all recent reconciliation runs with pagination and sorting.

## GET /api/v1/reconciliation/runs/{id}

Returns a reconciliation run detail, including totals, failures, exceptions, and duration.

## POST /api/v1/reconciliation/runs

Authentication:
Bearer JWT

Permissions:
reconciliation:create

Starts a reconciliation run.

## GET /api/v1/reconciliation/exceptions

Authentication:
Bearer JWT

Permissions:
reconciliation:read

Returns a queue of reconciliation exceptions.

## GET /api/v1/reconciliation/exceptions/{id}

Returns exception fields:

- id
- transaction_id
- type
- severity
- expected_value
- actual_value
- difference
- status
- assigned_to
- created_at
- updated_at
- resolution
- resolved_by
- resolved_at

## POST /api/v1/reconciliation/exceptions/{id}/resolve

## POST /api/v1/reconciliation/exceptions/{id}/assign

## POST /api/v1/reconciliation/exceptions/{id}/escalate

These endpoints must be audit logged and permission checked.
