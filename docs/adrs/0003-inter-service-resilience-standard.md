# ADR 0003 - Inter-service Resilience Standard

Date: 2026-06-02
Status: PROPOSED
Deciders: Pair 1 (grants-management)

## Context

Synchronous service calls currently rely on direct HTTP client usage with inconsistent timeout, retry, and fallback behavior. This increases risk of cascading failures and duplicate side effects during retries.

## Decision

Adopt one resilience baseline for all synchronous inter-service HTTP calls.

1. Timeouts
- Connect timeout: 1 second
- Read timeout: 3 seconds
- End-to-end request cap: 4 seconds for downstream dependency calls

2. Retry policy
- Retry only idempotent reads by default
- Maximum retries: 2
- Exponential backoff with jitter
- Non-idempotent writes require explicit idempotency contract before retry is allowed

3. Circuit breaker policy
- Per downstream dependency
- Open on sustained failure threshold
- Half-open probe before close

4. Fallback policy
- Read paths may return typed degraded responses where contract allows
- Mutating paths fail fast with explicit error and correlation metadata

5. Idempotency policy
- New create/update endpoints that may be retried by clients must support Idempotency-Key
- Persist key and outcome for safe replay

6. Observability policy
- Emit timeout, retry, circuit-open, and fallback metrics
- Include correlation metadata in all resilience logs

## Consequences

Positive:
- Lower blast radius during dependency slowness/outage
- More predictable failure semantics for frontend and operators
- Fewer duplicate writes on client retry storms

Tradeoffs:
- Additional complexity in client wrappers and configuration
- More integration testing scenarios required

## Rollout

1. Standardize HTTP client configuration across services.
2. Add resilience wrappers for all external calls.
3. Introduce Idempotency-Key support on high-risk mutating endpoints.
4. Add integration tests for timeout, retry, open-circuit, and replay-safe paths.

## Non-goals

- This ADR does not migrate from sync REST to full asynchronous architecture.
- This ADR does not define retrieval strategy or HITL gating.
