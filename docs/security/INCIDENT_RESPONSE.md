# PesaGuard Incident Response

## Purpose
This document defines how PesaGuard declares incidents, pages operators, communicates status, and closes incidents.

## On-call and Paging
- Primary on-call: the PesaGuard operator or engineer responsible for the pilot.
- Paging channel: use the configured Slack channel, SMS gateway, or phone call depending on availability.
- If there is no dedicated PagerDuty integration yet, page via:
  1. Slack mention in `#pesaguard-ops`
  2. SMS to the operator phone number
  3. A phone call if the incident is SEV1 and immediate attention is required

## Severity Definitions
- **SEV1**: Production outage or reconciliation pipeline failure that prevents timely transaction matching, causes repeated payment reconciliation errors, or blocks customer-facing reconciliation status.
- **SEV2**: Partial degradation such as delayed reconciliation, intermittent webhook processing failures, or alerting failures where the pipeline remains functional but may miss some matching events.
- **SEV3**: Minor issue or operational anomaly that does not materially affect reconciliation accuracy, such as a dashboard UI bug, non-critical metric collection failure, or single-tenant alert threshold misconfiguration.

## Incident Declaration
An incident is declared when any of the following occurs:
- SEV1: webhook receiver down, Kafka backlog grows and cannot be processed within 15 minutes, Postgres restore needed, or reconciliation alerts fail for all tenants.
- SEV2: repeated webhook validation failures, customer-visible delay in discrepancy resolution, or a critical alerting channel outage.
- SEV3: data quality warnings, analytics endpoint malfunction, or internal tooling degraded without customer impact.

## Communication Workflow
1. Acknowledge the incident immediately in the ops channel.
2. Post a short summary with:
   - description
   - impacted customers or tenants
   - severity level
   - current status
   - next action
3. Update status at least every 30 minutes until resolved.
4. Declare the incident closed once the issue is fixed and verified.

## Customer Notification Template
Use this template when communicating a customer-facing incident or outage.

```text
Subject: PesaGuard incident update — reconciliation service disruption

Hello [Customer],

We are investigating an issue affecting PesaGuard reconciliation for your account. Impacted functionality: [webhook ingestion / transaction matching / discrepancy reporting].

Current status: [investigating / identifying root cause / mitigation in place].

What we are doing:
- [Restarting webhook receiver]
- [Replaying Kafka events]
- [Restoring the database from backup if needed]

Expected next update: within 30 minutes.

Thank you,
The PesaGuard team
```

## Postmortem Template
- **Incident title**:
- **Severity**:
- **Start time**:
- **End time**:
- **Impact**:
- **Root cause**:
- **Detection method**:
- **Actions taken**:
- **Customer communication**:
- **Follow-up actions**:
  - [ ] Fix the root cause
  - [ ] Update runbooks and monitoring
  - [ ] Review alert thresholds

## Closure Criteria
- The underlying issue has been fixed.
- Reconciliation processing and webhook ingestion are verified.
- A postmortem is drafted and shared with stakeholders.
