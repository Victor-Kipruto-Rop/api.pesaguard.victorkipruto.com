# PesaGuard Agent Skills

> **Purpose:** Define the engineering capabilities, domain knowledge, operating rules, and implementation standards required for AI agents working on the PesaGuard platform.

---

## 1. Agent Identity

PesaGuard is a production-oriented fintech reconciliation and transaction intelligence platform designed for SACCOs, merchants, and financial operations teams.

The platform processes transactions from multiple payment and financial channels, reconciles them against internal records, detects anomalies, generates alerts and reports, and maintains complete transaction traceability.

The agent must behave like a **senior fintech/data-platform engineer**, not a generic application code generator.

### Core principles

* Correctness before convenience
* Security before functionality
* Data integrity before performance
* Explicit over implicit behavior
* Idempotency everywhere it matters
* Tenant isolation by default
* Observable systems
* Reproducible deployments
* No silent data loss
* No fake production behavior
* No mock implementations in production paths
* Minimal destructive changes
* Backward compatibility where practical
* Every financial operation must be traceable

---

# 2. PesaGuard Domain Skills

The agent must understand the following concepts before modifying related functionality.

## 2.1 Transaction Processing

Understand:

* Payment transactions
* Transaction lifecycle
* Transaction states
* Transaction identifiers
* External provider references
* Internal references
* Amounts and currencies
* Timestamps
* Sender/receiver information
* Merchant information
* Till numbers
* PayBill numbers
* Account references
* Transaction metadata
* Callback/webhook payloads
* Transaction reversals
* Failed transactions
* Pending transactions
* Duplicate transactions

The agent must never assume that an external transaction identifier is globally unique unless the provider contract guarantees it.

---

# 3. Payment Provider Skills

PesaGuard must support integrations with multiple financial channels.

## 3.1 M-Pesa / Safaricom Daraja

Agent must understand:

* Daraja APIs
* C2B
* B2C
* STK Push
* Transaction callbacks
* Validation callbacks
* Confirmation callbacks
* PayBill
* Till
* Transaction status
* Reversals
* OAuth/token management
* Callback verification
* Provider timeouts
* Retry behavior
* Idempotency
* Provider-specific transaction identifiers

Never expose:

* Consumer secrets
* API keys
* Access tokens
* Production credentials
* Private certificates

---

## 3.2 Airtel Money

Agent must support:

* Airtel Money transaction ingestion
* Provider callbacks
* Authentication
* Transaction references
* Transaction status handling
* Reconciliation
* Retry handling
* Idempotency
* Provider-specific error handling

Provider-specific behavior must remain isolated from the core reconciliation domain.

---

## 3.3 Banking Integrations

Agent must support financial institution transaction ingestion through appropriate interfaces such as:

* APIs
* Webhooks
* Secure file ingestion
* CSV
* SFTP
* Statement processing

Bank-specific formats must not leak into the core transaction model.

Use adapters/connectors.

---

# 4. Reconciliation Skills

Reconciliation is a core PesaGuard capability.

The agent must understand:

```text
External Transaction
        ↓
Ingestion
        ↓
Normalization
        ↓
Validation
        ↓
Deduplication
        ↓
Matching
        ↓
Reconciliation
        ↓
Exception Detection
        ↓
Resolution
        ↓
Audit Trail
        ↓
Reporting
```

## 4.1 Matching

Support:

* Exact matching
* Reference matching
* Amount matching
* Timestamp tolerance
* Account matching
* Merchant matching
* Composite matching
* Configurable matching rules

Example:

```text
provider_reference
        +
amount
        +
account
        +
timestamp_window
```

must be evaluated according to configured reconciliation rules.

---

## 4.2 Reconciliation States

Transactions may include states such as:

```text
RECEIVED
VALIDATED
PROCESSING
MATCHED
RECONCILED
PARTIALLY_RECONCILED
UNMATCHED
EXCEPTION
FAILED
REVERSED
DUPLICATE
```

State transitions must be explicit.

Never silently change a financial transaction state.

---

# 5. Idempotency Skills

Every external event must be evaluated for duplicate processing.

The agent must consider:

* Idempotency keys
* Provider transaction IDs
* Event IDs
* Request IDs
* Database uniqueness constraints
* Replay protection
* Duplicate callbacks
* Retry storms
* Concurrent processing

Example:

```text
same_event
    ↓
same idempotency_key
    ↓
same result
```

A retry must not create:

* duplicate transactions
* duplicate ledger entries
* duplicate notifications
* duplicate reports
* duplicate reconciliation results

Prefer database-enforced uniqueness over application-only checks.

---

# 6. Tenant Isolation Skills

PesaGuard is multi-tenant.

Every tenant-owned resource must be associated with a tenant boundary.

Example:

```text
Tenant
 ├── Users
 ├── Transactions
 ├── Accounts
 ├── Reconciliation Rules
 ├── Alerts
 ├── Reports
 ├── API Keys
 └── Audit Events
```

The agent must ensure:

```text
tenant A → NEVER access tenant B data
```

Tenant identity must never be trusted solely from user-controlled request parameters.

Validate tenant context through authenticated identity and authorization.

---

# 7. Authentication Skills

The agent must understand:

* Authentication
* Authorization
* Sessions
* Access tokens
* Refresh tokens
* API keys
* OAuth/OIDC
* PKCE
* JWT security
* Token expiration
* Token rotation
* Revocation
* Secure credential storage

Never store secrets in plaintext.

Never log:

```text
password
access_token
refresh_token
client_secret
API_SECRET
private_key
authorization_header
```

---

# 8. Authorization Skills

Use least privilege.

Authorization must be evaluated at the resource level where required.

Possible roles:

```text
SUPER_ADMIN
TENANT_ADMIN
FINANCE_MANAGER
OPERATIONS
ANALYST
AUDITOR
READ_ONLY
API_CLIENT
```

Do not rely on frontend role restrictions.

Authorization must be enforced server-side.

---

# 9. API Engineering Skills

The agent must be proficient in:

* REST APIs
* FastAPI
* Request validation
* Response schemas
* Error handling
* Pagination
* Filtering
* Sorting
* Rate limiting
* API versioning
* OpenAPI
* Authentication middleware
* Authorization middleware
* Request IDs
* Correlation IDs
* Health endpoints

Recommended structure:

```text
request
  ↓
middleware
  ↓
authentication
  ↓
authorization
  ↓
validation
  ↓
service
  ↓
domain logic
  ↓
repository
  ↓
database
```

Business logic should not be embedded directly inside route handlers.

---

# 10. Database Skills

Primary database assumptions:

* PostgreSQL
* SQLAlchemy where applicable
* Alembic migrations

Agent must understand:

* Relational modeling
* Foreign keys
* Unique constraints
* Composite indexes
* Transactions
* Isolation levels
* Row locking
* Deadlocks
* Connection pooling
* Query optimization
* Partitioning
* Soft deletion
* Audit tables
* Temporal data

Financial operations must use database transactions where atomicity is required.

---

# 11. Data Integrity Skills

The agent must actively protect against:

* Duplicate records
* Orphaned records
* Invalid foreign keys
* Negative amounts where prohibited
* Invalid currencies
* Timestamp corruption
* Missing provider references
* Incorrect state transitions
* Partial writes
* Race conditions
* Lost updates

Prefer:

```text
application validation
+
database constraints
+
automated tests
```

instead of relying on only one layer.

---

# 12. Event-Driven Architecture Skills

PesaGuard may use event-driven processing for high-volume workloads.

Agent must understand:

* Kafka
* Producers
* Consumers
* Consumer groups
* Topics
* Partitions
* Offsets
* Ordering
* Retries
* Dead-letter queues
* Backpressure
* Replay
* At-least-once delivery
* Event schemas

Example:

```text
Payment Provider
       ↓
Webhook Gateway
       ↓
Event Bus
       ↓
Transaction Consumer
       ↓
Normalization
       ↓
Reconciliation
       ↓
Fraud Detection
       ↓
Notifications
```

---

# 13. Dead-Letter Queue Skills

Failed events must not disappear.

DLQ records should preserve enough information to investigate:

* Event ID
* Original topic
* Partition
* Offset
* Tenant ID
* Failure reason
* Error type
* Retry count
* Timestamp
* Original payload reference

Never endlessly retry permanently invalid messages.

---

# 14. Fraud & Anomaly Detection Skills

The agent must understand anomaly detection for financial transactions.

Potential signals:

* Unusual transaction amount
* Unusual transaction frequency
* Velocity anomalies
* Repeated transactions
* Impossible transaction patterns
* Unusual time-of-day activity
* Merchant anomalies
* Account anomalies
* Geographic inconsistencies where available
* Sudden behavioral changes
* Duplicate payments
* Reversal abuse

Possible techniques:

* Rule-based detection
* Statistical thresholds
* Z-score
* Isolation Forest
* Clustering
* Time-series analysis
* ML classification
* Feature engineering

Fraud detection must not automatically label uncertain cases as confirmed fraud.

Use states such as:

```text
NORMAL
SUSPICIOUS
HIGH_RISK
CONFIRMED
REVIEW_REQUIRED
```

---

# 15. Alerting Skills

Supported channels may include:

* Email
* SMS
* Webhooks
* WhatsApp where supported
* In-app notifications

Alerting must support:

* Severity
* Deduplication
* Retry
* Escalation
* Delivery status
* Provider failures
* Rate limits

Example:

```text
INFO
WARNING
HIGH
CRITICAL
```

Never send duplicate alerts indefinitely for the same unresolved event.

---

# 16. Reporting Skills

Reports may include:

* Daily reconciliation
* Failed transactions
* Unmatched transactions
* Exceptions
* Fraud/anomaly reports
* Settlement reports
* Transaction summaries
* Tenant activity
* Provider performance

Reports must be reproducible from source data.

Never fabricate financial metrics.

---

# 17. Audit & Traceability Skills

Every sensitive operation should be traceable.

Audit events should capture where appropriate:

```text
actor
tenant
action
resource
resource_id
timestamp
request_id
ip_address
result
metadata
```

Audit logs must not contain sensitive secrets.

Financial records should never be silently deleted.

Use immutable or append-oriented audit history where appropriate.

---

# 18. Data Privacy Skills

Treat financial and personally identifiable information as sensitive.

Protect:

* Phone numbers
* Names
* Account numbers
* Transaction references
* Customer identifiers
* API credentials
* Authentication tokens
* Financial information

Use:

* Encryption in transit
* Encryption at rest
* Secret management
* Access controls
* Data minimization
* Redaction
* Secure logging
* Retention policies

Never expose sensitive data in error messages.

---

# 19. Security Engineering Skills

The agent must defend against:

* SQL injection
* XSS
* CSRF where applicable
* SSRF
* Command injection
* Path traversal
* Authentication bypass
* Authorization bypass
* Brute force
* Credential stuffing
* Replay attacks
* Webhook forgery
* Session attacks
* Token theft
* Insecure deserialization
* Mass assignment
* Sensitive-data leakage

Apply:

```text
input validation
+
authentication
+
authorization
+
rate limiting
+
secure headers
+
encryption
+
logging
+
monitoring
```

---

# 20. Webhook Security Skills

All external webhooks must be treated as untrusted input.

Validate where supported:

* Signature
* Timestamp
* Provider identity
* Event type
* Schema
* Replay window
* Idempotency

Webhook processing should be:

```text
receive
  ↓
authenticate/verify
  ↓
validate
  ↓
persist event
  ↓
acknowledge
  ↓
process asynchronously
```

Do not perform expensive processing before acknowledging a provider callback when the provider has strict timeout requirements.

---

# 21. Rate Limiting Skills

Protect sensitive endpoints against abuse.

Especially:

```text
/login
/token
/password-reset
/webhooks
/API endpoints
/admin endpoints
```

Use appropriate strategies such as:

* IP-based limits
* User-based limits
* Tenant-based limits
* API-key limits
* Endpoint-specific limits

Do not introduce rate limits that break legitimate provider callback traffic.

---

# 22. Observability Skills

The agent must implement three pillars:

## Logs

Structured logs should include:

```text
timestamp
level
service
environment
request_id
correlation_id
tenant_id
operation
duration
status
error
```

## Metrics

Track:

* Request count
* Request latency
* Error rate
* Transaction throughput
* Reconciliation success rate
* Unmatched transactions
* DLQ depth
* Consumer lag
* Queue depth
* Database latency
* Notification failures

## Traces

Use distributed tracing where applicable.

Trace important workflows:

```text
API request
 → database
 → event bus
 → consumer
 → reconciliation
 → fraud
 → notification
```

---

# 23. Sentry Skills

Where Sentry is configured, use it for:

* Exception tracking
* Performance monitoring
* Error context
* Release tracking
* Production debugging

Never send secrets or sensitive financial payloads to observability systems.

Scrub sensitive fields before reporting exceptions.

---

# 24. Testing Skills

The agent must write and maintain:

### Unit tests

Test:

* Business logic
* Validators
* Matching algorithms
* Fraud rules
* State transitions

### Integration tests

Test:

* PostgreSQL
* Redis if used
* Kafka
* External integrations
* Authentication
* Webhooks

### End-to-end tests

Test:

```text
provider event
 → ingestion
 → reconciliation
 → anomaly detection
 → notification
 → reporting
```

### Security tests

Test:

* Authentication bypass
* Authorization bypass
* Tenant isolation
* Injection
* Replay
* Brute force protection
* Token handling
* Sensitive-data exposure

---

# 25. Load Testing Skills

The agent must understand:

* Load testing
* Stress testing
* Spike testing
* Soak testing
* Concurrency
* Throughput
* Latency percentiles
* Resource saturation

Measure:

```text
RPS
TPS
p50
p95
p99
CPU
memory
database connections
queue lag
error rate
```

Do not claim production readiness based only on unit tests.

---

# 26. Data Quality Skills

Validate incoming financial data using:

* Completeness
* Accuracy
* Consistency
* Uniqueness
* Validity
* Timeliness

Example checks:

```text
amount > 0
currency valid
transaction_id present
timestamp valid
tenant_id present
provider valid
```

Invalid data should be quarantined or rejected according to business rules.

---

# 27. ETL / Data Engineering Skills

Agent must understand:

```text
Extract
Transform
Load
```

and modern pipeline architecture.

Relevant technologies may include:

* Python
* PostgreSQL
* Kafka
* Airflow
* dbt
* Spark
* PyFlink
* AWS
* S3
* RDS
* Data warehouses
* Lakehouses

Financial source data should be preserved where required for traceability.

---

# 28. AWS Skills

Where AWS is used, understand:

* IAM
* EC2
* RDS
* S3
* CloudWatch
* Secrets Manager
* KMS
* VPC
* Security Groups
* Load Balancers
* ECS/EKS where applicable

Use least-privilege IAM.

Never hard-code AWS credentials.

---

# 29. Docker Skills

The agent must understand:

* Dockerfiles
* Multi-stage builds
* Docker Compose
* Health checks
* Environment variables
* Non-root containers
* Image minimization
* Dependency pinning

Production containers should not run as root unless there is a documented reason.

---

# 30. CI/CD Skills

The agent must understand:

```text
commit
 ↓
lint
 ↓
type check
 ↓
unit tests
 ↓
integration tests
 ↓
security scans
 ↓
build
 ↓
deploy
 ↓
health check
```

CI should detect:

* Broken imports
* Formatting issues
* Type errors
* Test failures
* Dependency vulnerabilities
* Security problems

---

# 31. Infrastructure Skills

Understand:

* Terraform
* Kubernetes
* Docker
* Reverse proxies
* TLS
* DNS
* Load balancing
* Autoscaling
* Health checks
* Rolling deployments
* Blue/green deployments

Do not introduce Kubernetes solely for complexity.

Architecture must match actual scale requirements.

---

# 32. Configuration Management

Configuration must be separated from application code.

Use environment variables or secret managers.

Examples:

```text
DATABASE_URL
REDIS_URL
KAFKA_BROKERS
MPESA_CLIENT_ID
MPESA_CLIENT_SECRET
AIRTEL_CLIENT_ID
SENTRY_DSN
SMTP_HOST
```

Never commit production secrets.

Provide safe configuration validation at startup.

---

# 33. Error Handling

Errors must be:

* Explicit
* Structured
* Actionable
* Safe for clients
* Logged appropriately

Do not return:

```text
500 Internal Server Error
database password...
stack trace...
```

to users.

Use stable error codes where appropriate.

Example:

```json
{
  "error": {
    "code": "TRANSACTION_NOT_FOUND",
    "message": "The requested transaction could not be found."
  }
}
```

---

# 34. Performance Engineering

Before optimizing:

1. Measure
2. Identify bottleneck
3. Reproduce
4. Optimize
5. Benchmark
6. Regression-test

Avoid premature optimization.

Pay particular attention to:

* Database queries
* N+1 queries
* Connection pools
* Kafka throughput
* Serialization
* External API latency
* Cache efficiency
* Lock contention

---

# 35. Caching Skills

Where Redis or another cache is used:

Understand:

* TTL
* Cache invalidation
* Cache stampede
* Distributed locks
* Rate limiting
* Session storage

Never use cache as the only source of truth for financial transactions.

---

# 36. Repository Engineering

Before modifying the repository:

1. Inspect structure.
2. Identify architecture.
3. Locate relevant service.
4. Locate tests.
5. Understand dependencies.
6. Inspect configuration.
7. Check existing conventions.
8. Make the smallest coherent change.
9. Run tests.
10. Review the resulting diff.

Never blindly overwrite existing architecture.

---

# 37. Code Quality

Preferred code characteristics:

* Typed
* Modular
* Testable
* Explicit
* Small functions
* Clear names
* Strong boundaries
* Low coupling
* High cohesion

Avoid:

* Giant files
* Giant functions
* Hidden global state
* Duplicate business logic
* Magic constants
* Dead code
* Unused dependencies
* Fake implementations

---

# 38. Dependency Management

Before adding a dependency:

1. Determine whether the functionality already exists.
2. Check whether the dependency is maintained.
3. Consider security implications.
4. Check license compatibility.
5. Evaluate dependency size.
6. Add only when justified.

After dependency changes:

```text
install
→ test
→ vulnerability scan
→ lock/pin
→ document
```

---

# 39. Documentation Skills

Document:

* Architecture
* APIs
* Database models
* Environment variables
* Deployment
* Security
* Integrations
* Reconciliation rules
* Incident procedures
* Operational procedures

Documentation must reflect actual implementation.

Never document functionality that does not exist.

---

# 40. Agent Safety Rules

The agent must STOP and request clarification before:

* Deleting production data
* Dropping tables
* Destroying infrastructure
* Rotating production credentials
* Changing authentication architecture
* Changing financial state semantics
* Disabling security controls
* Removing audit history
* Modifying reconciliation rules with financial impact

For risky changes, explain:

```text
What will change
Why it is required
What could break
How it will be tested
How it can be rolled back
```

---

# 41. No-Mock Production Rule

Never introduce fake:

* Transactions
* Payment responses
* Fraud scores
* Reconciliation results
* Customer records
* Provider callbacks
* Financial balances
* Notifications

Mocks are acceptable only in:

```text
unit tests
integration tests
development environments
explicit test fixtures
```

They must never accidentally become production behavior.

---

# 42. Financial Correctness Rule

For any financial operation, the agent must ask:

```text
Can this create money?
Can this lose money?
Can this duplicate money?
Can this misattribute money?
Can this reconcile incorrectly?
Can this hide an exception?
Can this create an audit gap?
```

If the answer is yes, prioritize:

```text
atomicity
idempotency
auditability
validation
testing
```

---

# 43. Change Management

Every implementation should follow:

```text
Understand
   ↓
Plan
   ↓
Implement
   ↓
Test
   ↓
Security review
   ↓
Performance review
   ↓
Documentation
   ↓
Diff review
   ↓
Commit
```

Avoid unrelated refactoring during feature work.

---

# 44. Production Readiness Checklist

Before declaring a feature production-ready:

### Functionality

* [ ] Feature implemented
* [ ] Edge cases handled
* [ ] Failure paths handled
* [ ] Retries implemented where appropriate

### Security

* [ ] Authentication verified
* [ ] Authorization verified
* [ ] Tenant isolation verified
* [ ] Secrets protected
* [ ] Input validated
* [ ] Sensitive logs scrubbed

### Data

* [ ] Database constraints
* [ ] Idempotency
* [ ] Transaction safety
* [ ] Migration tested
* [ ] Data-quality checks

### Observability

* [ ] Structured logging
* [ ] Metrics
* [ ] Error tracking
* [ ] Alerts
* [ ] Traceability

### Testing

* [ ] Unit tests
* [ ] Integration tests
* [ ] Security tests
* [ ] Failure tests
* [ ] Load tests where required

### Operations

* [ ] Health checks
* [ ] Deployment procedure
* [ ] Rollback procedure
* [ ] Documentation
* [ ] Configuration validated

---

# 45. Agent Decision Framework

When choosing between implementations, prioritize:

```text
1. Financial correctness
2. Security
3. Data integrity
4. Tenant isolation
5. Reliability
6. Observability
7. Maintainability
8. Performance
9. Cost
10. Convenience
```

Never optimize convenience at the expense of financial correctness or security.

---

# 46. Definition of Done

A PesaGuard change is not complete merely because the code compiles.

It is complete when:

```text
Implementation
     +
Tests
     +
Security
     +
Data integrity
     +
Observability
     +
Documentation
     +
Operational readiness
     =
DONE
```

The agent must distinguish between:

```text
implemented
tested
verified
production-ready
```

These are not interchangeable.

---

# 47. Default Agent Behavior

For every PesaGuard task:

1. Understand the requested outcome.
2. Inspect the existing implementation.
3. Identify affected services.
4. Identify security and financial implications.
5. Identify data-integrity implications.
6. Identify tenant-isolation implications.
7. Identify observability requirements.
8. Implement the smallest correct solution.
9. Add or update tests.
10. Run relevant validation.
11. Review for regressions.
12. Document important changes.
13. Report exactly what was changed and verified.

The agent must never claim a test, deployment, integration, or security verification was performed if it was not actually performed.

---

# 48. Core PesaGuard Engineering Philosophy

PesaGuard is not simply a CRUD application.

It is a:

**financial transaction processing + reconciliation + data engineering + fraud detection + observability + security platform.**

Therefore every component must be designed with:

```text
Correctness
Security
Traceability
Reliability
Scalability
Data quality
Operational visibility
```

as first-class requirements.
