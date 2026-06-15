---
title: "Roadmap"
description: "OsuRender API development roadmap — upcoming features, planned improvements, and long-term vision for the rendering platform."
---

# Big Tech Readiness Roadmap

OsuRender API already demonstrates architecture quality significantly above the average open-source backend (event-driven architecture, outbox pattern, advisory locking, stateless tier). 

The primary gap between OsuRender and systems at companies like Stripe, Cloudflare, or Google is **Observability, Operations, and Engineering Process Maturity**.

## Current Assessment

| Category | Score |
|----------|-------|
| Architecture | 9.0 |
| Reliability | 8.0 |
| Security | 8.5 |
| Observability | 7.0 |
| **Production Readiness** | **8.4** |

---

## Phase 1 — Full Observability (In Progress)

**Goal:** Every render should be traceable end-to-end.

- [x] Prometheus metrics (`prometheus-fastapi-instrumentator`)
- [x] Custom metrics for queue depth, dispatch latency, and storage failures
- [x] Grafana dashboards
- [ ] Distributed Tracing (OpenTelemetry)
- [ ] Structured JSON Logging across all components

## Phase 2 — Reliability Hardening (Completed)

**Goal:** No job can be silently lost.

- [x] Outbox state machine fixes
- [x] Worker explicit acknowledgements
- [x] Dead Letter Queue implementation
- [x] DLQ Operations script
- [x] Orphan job recovery via Celery Beat

## Phase 3 — Security Maturity (Completed)

**Goal:** Pass a professional security review.

- [x] CI/CD Gates (Trivy, pip-audit)
- [x] Secret scanning and Dependabot
- [x] Zip bomb protection and archive validation
- [x] Cloudflare origin protection strategy
- [x] SBOM generation via CycloneDX

## Phase 4 — SLO Program (Completed)

**Goal:** Define and alert on Service Level Objectives.

- [x] Define API Availability SLO (99.9%)
- [x] Define Dispatch Latency SLO (99% < 60s)
- [x] Define Render Duration SLO (95% < 15m)
- [x] Implement Prometheus recording rules
- [x] Configure alert routing

## Phase 5 — Chaos Engineering (Completed)

**Goal:** Prove reliability guarantees programmatically.

- [x] Automated failure injection suite
- [x] Worker death recovery test
- [x] PostgreSQL restart recovery test
- [x] Notification loss (LISTEN/NOTIFY) recovery test
- [x] Duplicate claim race condition test

## Phase 6 — Internal Operations Platform (Planned)

**Goal:** Most incidents resolved without touching PostgreSQL directly.

- [ ] Admin Dashboard UI
- [ ] Job Management (Search, View, Retry, Cancel)
- [ ] Queue Management visualization
- [ ] Worker health visualization
- [ ] Trace explorer

## Ideal End State

An engineer should be able to:
1. Trace any render end-to-end in seconds.
2. Recover from worker crashes automatically without intervention.
3. Diagnose incidents using dashboards, not raw SQL.
4. Deploy changes confidently with full CI/CD backing.
