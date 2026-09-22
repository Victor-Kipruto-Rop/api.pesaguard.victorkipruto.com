---

name: rules
description: Non-negotiable engineering, security, data integrity, financial correctness, tenant isolation, testing, and operational rules for the PesaGuard AI agent.
----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# PesaGuard Agent Rules

## 1. Purpose

These rules define the mandatory behavior of every AI agent working on PesaGuard.

The agent must follow these rules regardless of whether the task involves:

* Backend
* APIs
* Databases
* Data engineering
* Reconciliation
* Fraud detection
* Payment providers
* Authentication
* Infrastructure
* Testing
* Security
* Documentation
* Deployment

When rules conflict with convenience, speed, or implementation simplicity, **the rules take priority**.

---

# 2. Core Principles

The agent must prioritize:

```text
1. Financial correctness
2. Data integrity
3. Security
4. Tenant isolation
5. Reliability
6. Traceability
7. Observability
8. Maintainability
9. Performance
10. Cost
11. Convenience
```

Never reverse this order without explicit authorization.

---

# 3. Never Guess

The agent must not invent:

* Requirements
* APIs
* Provider behavior
* Database schemas
* Credentials
* Configuration values
* Financial rules
* Reconciliation rules
* Transaction states
* Production infrastructure
* Test results

If a critical requirement is ambiguous, stop and request clarification.

For non-critical ambiguity, choose the safest reasonable interpretation and document the assumption.

---

# 4. Inspect Before Modifying

Never modify a repository blindly.

Before substantial changes:

```text
Inspect
 ↓
Understand
 ↓
Identify dependencies
 ↓
Plan
 ↓
Modify
```

Inspect relevant:

* Files
* Modules
* Services
* Database models
* Migrations
* Tests
* Configuration
* CI/CD
* Documentation

Do not rewrite architecture simply because another architecture appears cleaner.

---

# 5. Preserve Existing Functionality

Existing working functionality must be preserved unless the requested change explicitly modifies it.

Before removing behavior, determine:

* Why it exists
* Who uses it
* What depends on it
* Whether tests cover it
* Whether documentation references it

Avoid unrelated refactoring.

---

# 6. No Fake Production Functionality

Never implement fake production behavior.

Do not use fake:

* Transactions
* Payment responses
* Fraud decisions
* Reconciliation results
* Customer data
* Provider callbacks
* Balances
* Notifications
* API responses

Mocks and fixtures are permitted only in explicitly isolated:

```text
tests
development
local integration environments
```

They must never be accidentally reachable from production code.

---

# 7. Financial Data Rule

Treat all financial information as high-risk.

Before changing transaction-related code, consider:

```text
Can this duplicate money?
Can this lose money?
Can this misattribute money?
Can this reconcile incorrectly?
Can this hide an exception?
Can this create an incorrect balance?
Can this break traceability?
```

If yes, perform additional testing and review.

---

# 8. Transaction Integrity

Financial operations must be:

* Atomic where required
* Idempotent
* Auditable
* Validated
* Traceable

Avoid partial financial state.

Where multiple related writes must succeed together, use an appropriate database transaction.

---

# 9. Idempotency Is Mandatory

Retryable financial operations must be idempotent.

The agent must account for:

* Duplicate webhooks
* Provider retries
* Network retries
* Consumer retries
* Manual reprocessing
* Event replay
* Concurrent requests

A repeated event must not produce unintended repeated financial effects.

---

# 10. Never Silently Drop Data

The agent must never silently discard:

* Transactions
* Events
* Provider callbacks
* Failed records
* Reconciliation exceptions
* Fraud signals

Invalid or failed records must be:

```text
rejected
quarantined
retried
or
sent to a DLQ
```

according to the appropriate pipeline design.

---

# 11. Tenant Isolation

Tenant boundaries are mandatory.

Every tenant-owned resource must be evaluated against the authenticated tenant context.

Never trust:

```text
tenant_id
```

from a user-controlled request without validating authorization.

The agent must prevent:

```text
Tenant A → Tenant B data
```

through:

* APIs
* Database queries
* Reports
* Exports
* Background jobs
* Events
* Caches
* Notifications

---

# 12. Authentication

Authentication must be enforced server-side.

Never:

* Trust frontend authentication alone
* Accept expired credentials
* Store passwords in plaintext
* Log authentication secrets
* Bypass authentication for convenience

Authentication changes require regression testing.

---

# 13. Authorization

Authentication does not equal authorization.

Every protected resource must have appropriate authorization.

Do not rely on UI restrictions.

Verify:

```text
Identity
+
Role
+
Tenant
+
Resource ownership
+
Requested action
```

where applicable.

---

# 14. Secrets

Never commit secrets to source control.

Never expose:

* Passwords
* API keys
* Client secrets
* Access tokens
* Refresh tokens
* Private keys
* Database credentials
* Encryption keys

Do not place secrets in:

* Source code
* Logs
* Error messages
* Documentation
* Screenshots
* Test fixtures

Use appropriate environment or secret-management mechanisms.

---

# 15. Exposed Secret Rule

If a credential is discovered in source control or logs:

```text
1. Treat it as compromised.
2. Stop further exposure.
3. Recommend/requires revocation.
4. Rotate the credential.
5. Remove the secret from the exposed location.
6. Audit usage.
```

Do not simply delete the visible secret and assume the credential is safe.

---

# 16. Sensitive Data

Protect:

* Phone numbers
* Customer identifiers
* Account numbers
* Financial information
* Transaction metadata
* Authentication information
* Provider credentials

Use:

* Encryption
* Access control
* Redaction
* Data minimization
* Secure logging

Do not expose sensitive information unnecessarily.

---

# 17. Logging Rules

Logs must help diagnose problems without exposing sensitive data.

Never log:

```text
password
API key
access token
refresh token
private key
full authentication headers
```

Avoid unnecessarily logging complete financial payloads.

Prefer structured logs containing:

```text
request_id
correlation_id
tenant_id
service
operation
status
duration
error_code
```

---

# 18. Error Handling

Errors must be:

* Structured
* Safe
* Actionable
* Observable

Never expose internal details to external clients.

Do not return:

* Stack traces
* SQL queries
* Credentials
* Internal filesystem paths
* Infrastructure secrets

to users.

---

# 19. Webhook Rules

All external webhooks are untrusted input.

Where supported, verify:

* Signature
* Authentication
* Timestamp
* Replay protection
* Schema
* Provider identity

Persist important events before asynchronous processing where appropriate.

Never trust a webhook merely because it came from an expected endpoint.

---

# 20. External API Rules

External providers must be treated as unreliable dependencies.

Account for:

* Timeout
* Rate limits
* Retries
* Invalid responses
* Partial outages
* Authentication failure
* Provider schema changes
* Duplicate callbacks

Use bounded retries and appropriate backoff.

---

# 21. Provider Isolation

Provider-specific logic must not contaminate the core domain.

Prefer:

```text
M-Pesa Adapter
Airtel Adapter
Bank Adapter
       ↓
Canonical PesaGuard Transaction
```

rather than embedding provider-specific logic throughout the application.

---

# 22. Database Rules

Database changes must be deliberate.

Do not casually:

* Drop tables
* Drop columns
* Remove constraints
* Remove indexes
* Change financial precision
* Change transaction semantics
* Rewrite production records

Use migrations for schema changes.

---

# 23. Database Constraints

Where appropriate, enforce important business invariants at the database layer.

Examples:

* Foreign keys
* Unique constraints
* Check constraints
* Not-null constraints

Do not rely exclusively on application-level validation for critical integrity rules.

---

# 24. Migration Rules

Every migration must consider:

* Existing data
* Compatibility
* Locking
* Runtime
* Index creation
* Rollback
* Deployment ordering

Large migrations should be tested against realistic data volumes.

Never assume rollback is automatically safe.

---

# 25. SQL Rules

Never construct SQL using unsafe string concatenation with user input.

Use:

* Parameterized queries
* ORM query builders
* Safe database APIs

Always consider:

* SQL injection
* Query performance
* Index usage
* Pagination
* Locking

---

# 26. Reconciliation Rules

Reconciliation logic must be deterministic where the business rules require determinism.

Never silently:

* Match unrelated transactions
* Override mismatches
* Ignore exceptions
* Delete unmatched transactions
* Change reconciliation outcomes without auditability

Every important reconciliation decision should be explainable.

---

# 27. Reconciliation Rule Changes

Any change to matching logic must include tests for:

* Exact matches
* Near matches
* Mismatches
* Duplicates
* Missing records
* Reversals
* Partial payments
* Multiple candidates

Do not modify financial matching logic casually.

---

# 28. Fraud Detection Rules

Fraud detection must distinguish between:

```text
Anomaly
Suspicion
High Risk
Confirmed Fraud
```

Do not automatically declare fraud solely because a model or rule produces a high anomaly score.

Fraud decisions must remain traceable.

---

# 29. Event-Driven Rules

Consumers must assume events can be delivered more than once.

The agent must account for:

* Duplicate events
* Out-of-order events
* Consumer crashes
* Offset replay
* Poison messages
* Consumer lag

Consumers must be designed for safe reprocessing.

---

# 30. Kafka Rules

When Kafka is used:

* Define clear topic ownership.
* Define event schemas.
* Choose partition keys deliberately.
* Monitor consumer lag.
* Avoid unnecessary global ordering.
* Handle poison messages.
* Use DLQs where appropriate.
* Make consumers idempotent.

Do not commit offsets before required processing is safely completed.

---

# 31. DLQ Rules

A DLQ is not a trash bin.

Every DLQ event should be:

* Observable
* Investigable
* Recoverable
* Replayable where appropriate

Never automatically delete DLQ records without an explicit retention policy.

---

# 32. Data Quality Rules

Critical datasets must be evaluated for:

```text
Completeness
Accuracy
Consistency
Validity
Uniqueness
Timeliness
```

Bad data must be visible.

Never manipulate quality metrics to make a pipeline appear healthy.

---

# 33. Data Transformation Rules

Transformations must be:

* Deterministic where possible
* Documented
* Testable
* Reproducible

Do not silently change source values unless the transformation is explicitly defined.

Preserve source information where auditability requires it.

---

# 34. Data Lineage

Important financial data must remain traceable.

The system should be able to establish:

```text
Provider Event
 ↓
Raw Event
 ↓
Canonical Transaction
 ↓
Reconciliation
 ↓
Fraud Signal
 ↓
Alert
 ↓
Report
```

Do not create transformations that make source provenance impossible to determine.

---

# 35. Data Deletion

Deletion of financial or audit data is high risk.

Never delete production financial records without explicit authorization and a documented retention/deletion policy.

Prefer appropriate archival or soft-delete strategies where required.

---

# 36. Testing Rules

Do not consider code complete merely because it compiles.

Testing should cover the relevant layers:

```text
Unit
Integration
End-to-End
Security
Performance
Failure Recovery
```

The level of testing must match the risk.

---

# 37. Regression Testing

Every significant bug fix should add or update a regression test.

Do not remove failing tests simply to make CI pass.

If behavior intentionally changes, update the requirement, implementation, and tests together.

---

# 38. Test Evidence

Never claim:

* Tests passed
* Security verified
* Integration verified
* Load tested
* Deployment succeeded

unless the agent actually has evidence that the relevant action was performed.

Use:

```text
TESTED
NOT TESTED
PARTIALLY TESTED
BLOCKED
REQUIRES HUMAN VERIFICATION
```

when appropriate.

---

# 39. Performance Rules

Never optimize purely from assumptions.

Use:

```text
Measure
 ↓
Profile
 ↓
Optimize
 ↓
Benchmark
 ↓
Verify correctness
```

Never sacrifice financial correctness for performance.

---

# 40. Observability Rules

Production functionality should be observable.

Important systems should expose appropriate:

* Logs
* Metrics
* Traces
* Health checks
* Alerts

At minimum, operators should be able to determine:

```text
What happened?
Where?
When?
For which tenant?
For which transaction?
Why?
What was the result?
```

---

# 41. Monitoring Rules

Monitor important business and technical signals.

Examples:

```text
Transaction throughput
Reconciliation success
Unmatched transactions
DLQ depth
Consumer lag
API latency
Error rate
Database health
Notification failures
Data-quality failures
```

Monitoring should detect both technical failures and business anomalies.

---

# 42. Dependency Rules

Before adding a dependency:

1. Check whether existing functionality can solve the problem.
2. Evaluate maintenance status.
3. Evaluate security.
4. Evaluate compatibility.
5. Evaluate operational cost.
6. Add only when justified.

Do not add dependencies merely because they are popular.

---

# 43. Architecture Rules

Architecture must solve actual requirements.

Do not introduce:

* Microservices
* Kubernetes
* Kafka
* Distributed databases
* Complex event systems

solely to make the project appear enterprise-grade.

Use complexity only when justified by:

* Scale
* Reliability
* Isolation
* Operational requirements
* Business requirements

---

# 44. Simplicity Rule

Prefer the simplest architecture that satisfies:

```text
Security
+
Correctness
+
Reliability
+
Scalability
+
Maintainability
```

Simple does not mean careless.

---

# 45. No Unrelated Changes

When implementing a feature or fix:

Do not modify unrelated:

* Services
* APIs
* Dependencies
* Formatting
* Architecture
* Configuration

unless the change is necessary.

Keep diffs focused.

---

# 46. Refactoring Rule

Refactoring must preserve behavior unless behavior change is explicitly requested.

Before refactoring:

```text
Understand existing behavior
 ↓
Identify dependencies
 ↓
Check tests
 ↓
Refactor
 ↓
Run regression tests
```

Do not combine massive refactors with high-risk financial changes unless necessary.

---

# 47. Documentation Rules

Documentation must describe the real system.

Never document:

* Features that do not exist
* Integrations that are not verified
* Security controls that are not implemented
* Performance numbers that were not measured

Update documentation when behavior or architecture changes.

---

# 48. Git Rules

Before committing:

```text
git status
git diff
tests
security checks
secret scan
```

Never commit:

* Credentials
* Secrets
* Private keys
* Temporary files
* Debug files
* Local databases
* Build artifacts

Avoid force-pushing shared branches without explicit authorization.

---

# 49. CI/CD Rules

CI/CD should validate appropriate:

* Formatting
* Linting
* Type checking
* Unit tests
* Integration tests
* Security
* Dependency vulnerabilities
* Build integrity

Do not bypass CI checks merely to achieve a green pipeline.

---

# 50. Production Changes

Production changes require additional caution.

Before executing a risky operation:

```text
Understand
 ↓
Assess impact
 ↓
Backup / recovery strategy
 ↓
Dry run
 ↓
Execute
 ↓
Verify
 ↓
Monitor
```

Do not execute destructive production operations without explicit authorization.

---

# 51. Infrastructure Rules

Never destroy production infrastructure casually.

Require explicit authorization before:

* Destroying resources
* Removing databases
* Changing networking
* Changing security groups
* Disabling encryption
* Removing backups
* Deleting storage

---

# 52. Encryption Rules

Use encryption:

```text
In transit
+
At rest
```

Sensitive cryptographic keys must not be embedded in application source code.

Do not invent cryptographic implementations when established, secure libraries are available.

---

# 53. Rate Limiting

Protect sensitive endpoints against abuse.

Particularly:

```text
Authentication
Token endpoints
Password reset
Admin endpoints
Public APIs
```

Do not accidentally block legitimate provider callbacks or internal processing.

---

# 54. Brute Force Protection

Authentication systems should consider:

* Rate limiting
* Progressive delays
* Account protection
* Credential monitoring
* Suspicious activity detection

Do not implement protections that enable account enumeration.

---

# 55. Security by Default

New endpoints and services should be secure by default.

A newly created endpoint must not accidentally become:

```text
public
unauthenticated
unvalidated
unrate-limited
cross-tenant
```

unless explicitly designed that way.

---

# 56. Least Privilege

Every component should receive only the permissions it requires.

Apply least privilege to:

* Users
* Services
* Databases
* AWS IAM
* API keys
* Containers
* CI/CD
* External integrations

---

# 57. Fail Safely

When critical dependencies fail:

Do not:

* Invent data
* Skip validation
* Bypass authorization
* Mark failed transactions as successful
* Ignore errors

Prefer:

```text
fail
retry
queue
quarantine
alert
recover
```

depending on the situation.

---

# 58. Backward Compatibility

When modifying APIs, events, or schemas:

Consider:

* Existing clients
* Existing consumers
* Existing database records
* Existing integrations
* Existing deployments

Avoid breaking changes unless required and explicitly planned.

---

# 59. Configuration Rules

Configuration must be externalized where appropriate.

Never hard-code:

* Credentials
* Production URLs
* Environment-specific secrets
* Encryption keys

Validate required configuration during startup.

Fail clearly when mandatory configuration is missing.

---

# 60. Agent Communication Rules

When reporting work:

Be precise.

State:

```text
What changed
Why it changed
What was tested
What was verified
What was not tested
Known risks
Required human action
```

Do not exaggerate completion.

---

# 61. Human Approval Rules

The agent must request human approval before irreversible or high-risk actions including:

* Production database deletion
* Production data deletion
* Infrastructure destruction
* Credential rotation
* Major authentication changes
* Major authorization changes
* Reconciliation-rule changes with financial impact
* Destructive migrations
* Disabling security controls

---

# 62. Evidence Over Assumptions

When making technical claims, prefer evidence from:

* Repository contents
* Tests
* Logs
* Metrics
* Database state
* CI results
* Provider documentation
* Deployment output

Do not infer successful behavior from code existence alone.

---

# 63. Completion Rule

A task is not considered complete simply because implementation exists.

The agent should evaluate:

```text
Code
+
Tests
+
Security
+
Data Integrity
+
Tenant Isolation
+
Observability
+
Documentation
```

according to the task's scope.

---

# 64. Final Rule

The PesaGuard agent must leave the system in a state that is:

```text
More correct
More secure
More observable
More reliable
More maintainable
```

than before the change.

If a requested change would materially reduce any of these properties, the agent must identify the trade-off before proceeding.

---

# 65. Absolute Non-Negotiables

The following rules can never be bypassed for convenience:

```text
NO fabricated financial data.

NO silent data loss.

NO tenant data leakage.

NO exposed secrets.

NO unaudited financial changes.

NO unsafe duplicate processing.

NO false test claims.

NO false production-readiness claims.

NO unauthorized destructive production changes.

NO bypassing security controls to make functionality work.
```

PesaGuard is financial infrastructure.

**When in doubt: preserve data, preserve traceability, preserve security, and ask before performing irreversible actions.**
