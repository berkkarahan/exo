---
unit: pc1
feature: Windows Distributed-Collectives Abstraction & Placement Integration
priority: P1
---
# Dropped activation-exchange connection surfaces as a terminal failure

## Scenario
During an in-progress `POST /v1/chat/completions` request against a Windows-involved pipeline instance, forcibly terminate the network connection between two adjacent ranks (e.g. stop the `exo` process on one non-first, non-last rank node) mid-generation.

## Expected
The in-flight chat completion request terminates with an error/failure response within a bounded time (not an indefinite hang).
The cluster's `/state` reflects the affected instance/runner as failed or degraded rather than silently appearing healthy.
