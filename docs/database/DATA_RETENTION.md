# PesaGuard Data Retention

## Retention Policy
- Transaction payloads and reconciliation records: retain for 90 days.
- Discrepancy records and incident history: retain for 180 days.
- Audit log entries: retain for 365 days.
- Application logs: retain according to the logging/storage provider policy, but keep at least 90 days of operational logs for incident investigation.

> Note: These retention periods are placeholders. Confirm final retention periods with customers and compliance requirements.

## What is retained
- Raw transaction callbacks from M-Pesa.
- Matched and unmatched transaction reconciliation records.
- Discrepancy details and resolution history.
- Audit trails of changes to discrepancies and settings.

## Deletion / Archival Process
### Automatic retention enforcement
- Run a periodic cleanup job that deletes records older than the configured retention window.
- Example SQL cleanup for Postgres:
  ```sql
  DELETE FROM discrepancy WHERE detected_at < NOW() - INTERVAL '180 days';
  DELETE FROM transaction WHERE created_at < NOW() - INTERVAL '90 days';
  DELETE FROM action_audit WHERE created_at < NOW() - INTERVAL '365 days';
  ```

### Suggested archive approach
- If historical data needs to be preserved beyond retention, export older records to object storage before deletion.
- Keep the archive file naming convention like `pesaguard-archive-YYYY-MM-DD.json`.

## Tenant Offboarding
### Offboarding process
1. Verify the tenant has no active reconciliation workloads.
2. Export tenant transaction and discrepancy data:
   - `tenant_id`
   - transaction records
   - discrepancy records
   - audit trail entries
3. Delete tenant data from the production database.
4. Confirm deletion and provide a copy of the exported data to the customer if requested.

### Grace period
- Hold tenant data for 30 days after churn for recovery or export requests.
- After the grace period, purge the tenant data permanently.

### Offboarding verification
- Confirm no remaining records exist for the tenant:
  ```sql
  SELECT count(*) FROM discrepancy WHERE tenant_id = 'tenant-a';
  SELECT count(*) FROM transaction WHERE tenant_id = 'tenant-a';
  SELECT count(*) FROM action_audit WHERE tenant_id = 'tenant-a';
  ```

## Audit Log Retention
- Keep audit logs separately from operational reconciliation data.
- Suggested audit retention: 365 days.
- Example cleanup command:
  ```sql
  DELETE FROM action_audit WHERE created_at < NOW() - INTERVAL '365 days';
  ```

## Notes
- If a tenant requests full deletion, handle the export and deletion within the 30-day grace period.
- Document any retention exceptions in the customer agreement.
