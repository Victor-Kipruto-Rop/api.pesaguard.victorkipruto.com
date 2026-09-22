# Communications Troubleshooting

## Queue backlog

**Symptoms:** Queue depth growing, old `available_at`, high latency

**Check:**
1. Outbox status distribution (`pending` vs `retrying` vs `dead_letter`)
2. Oldest `available_at` (is anything stuck with an expired lease?)
3. Worker health (is the worker process running? Restart if crashed)
4. Database connectivity (connection pool exhaustion, locks)
5. Provider circuit state (is circuit OPEN? Wait for recovery)

**Actions:**
- Scale workers horizontally (leases prevent duplicate processing)
- Verify provider rate limits (`PESAGUARD_COMMUNICATION_PROVIDER_RATE_PER_MINUTE`)
- Do NOT manually re-enqueue rows with active leases (causes duplicates)
- Check Kafka/Redis dependencies

## Provider failures

**Symptoms:** Rising failure rate, timeout errors, dead-letter growth

**Check:**
1. Provider credentials (username, API key, environment)
2. Sandbox vs production environment mismatch
3. Rate limits (are we being throttled?)
4. Balance (insufficient funds?)
5. Timeout/error metrics
6. Dead-letter entries for error patterns

**Actions:**
- Correct the cause before replay (permanent errors are not retried automatically)
- Replay dead-letter entries via `POST /api/v1/communications/dead-letters/<id>/replay`
- Verify circuit breaker state via `GET /api/v1/communications/providers/health`
- Monitor provider health score trend

## Webhook failures

**Symptoms:** Pending-review events, duplicated delivery reports, missed status updates

**Check:**
1. HTTPS routing (is the endpoint reachable?)
2. Canonical webhook secret (`AFRICASTALKING_WEBHOOK_SECRET`)
3. Signature header (`X-Africa-Talking-Signature`)
4. Body size limit (`PESAGUARD_WEBHOOK_MAX_BODY_BYTES`)
5. Provider message ID matching (does the callback reference a known notification?)
6. Duplicate-event records (are there unique constraint violations?)

**Actions:**
- Never bypass signature checks in production
- Replay authenticated inbox records via `POST /api/v1/communications/webhook-events/<id>/replay` (audited)
- Check `processing_status` distribution in the inbox

## SLA breaches

**Symptoms:** Incident created with category `sla`

**Check:**
1. Queue latency by priority (`communication_notifications` timestamps)
2. Worker throughput
3. Provider response time
4. Rate governor configuration

**Actions:**
- Review `/api/v1/communications/incidents?category=sla`
- Adjust worker count or rate limits after root-cause analysis
- Tune `PESAGUARD_COMMUNICATION_SLA_TARGETS` if misconfigured

## OTP abuse

**Symptoms:** Incident created with category OTP, flood/enumeration findings

**Check:**
1. `detect_otp_abuse` findings (recipient flood, IP enumeration)
2. Recipient/IP hourly request counts
3. Geographically unusual activity
4. Consecutive failed attempts

**Actions:**
- Apply temporary block on the recipient/IP
- Review rate limits (`PESAGUARD_OTP_RECIPIENT_HOURLY_LIMIT`, `PESAGUARD_OTP_IP_HOURLY_LIMIT`)
- Escalate to security incident response
- Preserve audit evidence

## High error rate

**Symptoms:** Error rate > 5% of attempts, delivery rate < 95%

**Check:**
1. Error category distribution (`TIMEOUT` vs `NETWORK_ERROR` vs `INVALID_RECIPIENT`)
2. Provider health score trend
3. Recent incidents
4. Webhook processing health

**Actions:**
- If timeout/network: check network path, consider failover
- If invalid recipient: correct the data source
- If auth: rotate credentials
- Use provider health endpoint to guide decisions
