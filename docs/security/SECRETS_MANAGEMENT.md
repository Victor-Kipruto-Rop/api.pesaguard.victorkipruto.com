# Secrets rotation

## Recommended cadence

- Database credentials: every 90 days (placeholder pending provider/ops policy confirmation).
- Daraja API keys: every 90 days (placeholder pending provider guidance).
- Slack and SMS webhook tokens: every 90 days (placeholder pending provider guidance).

## Rotation procedure

1. Generate a new secret value in the provider or host environment.
2. Add the new value to the deployment environment without removing the old one.
3. Roll the service to use the new value.
4. Verify the service can authenticate successfully.
5. Remove the old secret after a brief overlap window.
6. Record the rotation event in the audit log and release notes.
