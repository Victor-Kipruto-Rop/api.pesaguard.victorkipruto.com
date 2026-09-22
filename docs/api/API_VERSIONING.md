# API versioning

All dashboard APIs should be served under the /v1 namespace from the start.

## Deprecation policy

- A version remains supported for at least 90 days after a deprecation notice is published.
- Breaking changes require a new versioned route prefix.
- Deprecations are announced in release notes and the OpenAPI spec.
