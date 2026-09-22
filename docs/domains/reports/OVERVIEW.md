# Reports API

## GET /api/v1/reports

Authentication:
Bearer JWT

Permissions:
reports:read

Returns report metadata and generation state.

## GET /api/v1/reports/{id}

## POST /api/v1/reports

Authentication:
Bearer JWT

Permissions:
reports:create

Creates a report configuration.

## POST /api/v1/reports/generate

Authentication:
Bearer JWT

Permissions:
reports:create

Creates a report asynchronously when large datasets are requested.

## GET /api/v1/reports/{id}/download

Authentication:
Bearer JWT

Permissions:
reports:export

Returns CSV, JSON, or PDF where supported.

Report states:
- queued
- generating
- processing
- ready
- failed
