# AI Order Supervisor — System Architecture

## 1. Overview

The AI Order Supervisor is a long-running AI system that supervises a single order from creation to completion. Each order is managed by exactly **one Temporal workflow**. Events arrive as **signals**, a lightweight **wake-up policy** decides which of them matter, the **agent** decides and acts through **allowlisted activities**, and **durable timers** handle sleep. Workflow-owned lifecycle rules — never the LLM — decide when the run ends.

Stack: Next.js (App Router) + Tailwind · FastAPI · Temporal Python SDK · PostgreSQL · LLM behind a small gateway (Langfuse tracing optional).

## 2. Components

| Component | Stack | Responsibility |
|---|---|---|
| Operator console | Next.js, Tailwind | Supervisor configs, start runs, live timeline, inject events, instructions, pause/resume/terminate |
| API service | FastAPI | Validation, start/signal/query workflows, event generator endpoints, Postgres access |
| Temporal server | temporalio/auto-setup (Docker) | Durable execution: timers, retries, replay, history |
| Agent worker | Python, temporalio | Workflow (deterministic) + activities: decide, record actions, final output |
| PostgreSQL | Postgres 16 | Configs, runs, event timeline, activity log, memory, final outputs |

## 3. The pattern stack

1. **Event-driven architecture** — events enter only as signals; a deterministic wake-up policy (pure function, zero tokens) decides importance; the agent never polls.
2. **Durable workflow orchestration** — one workflow per order, alive until a terminal event, operator termination or max age.
3. **Agent–orchestrator separation** — Temporal controls WHEN; the LLM activity decides WHAT; action activities perform side effects. Workflow code is deterministic: after a crash Temporal replays history, so the LLM result is remembered, never re-rolled.
4. **Gateway/Adapter for the LLM** — one typed interface over OpenAI-compatible providers (Groq → OpenRouter → …) with fallback, retries, timeouts, token accounting and strict-JSON validation; a fake adapter keeps tests free and deterministic.
5. **Tool registry / command pattern** — the model proposes; the registry validates the action against an allowlist and bounds before any activity runs.
6. **Durable timer (sleep)** — "wake me in 60 minutes" is a Temporal timer: zero compute while asleep, survives restarts; an arriving event cancels the pending timer.
7. **Append-only event/decision log** — timeline and activity records are INSERT-only; every action is explainable and replayable.
8. **Idempotency** — activity retries are at-least-once; action records are keyed so retries are harmless.
9. **Bounded context / memory compaction** — the prompt is snapshot + recent events + compact summary; history grows in Postgres, never in the prompt.
10–13 (advanced, designed in the full design document): human-in-the-loop gates, continue-as-new, model routing/cost optimization, evaluation/replay.

## 4. The agent loop

1. Drain signals (dedup by event ID).
2. Wake policy: important → decide now; routine → log and keep sleeping; unknown → wake to be safe.
3. Deterministic pre-checks (paused? budget left?).
4. **Decide activity** — strict JSON: actions from the allowlist, optional memory refresh, sleep recommendation, reasoning. Malformed output retries once, then degrades.
5. **Act activities** — each action becomes an activity record (single activity log) and lands on the timeline.
6. Update memory, schedule the next durable timer, sleep.
7. On a terminal event / termination / max age: a **final-output activity** produces the summary, actions taken, learnings and feedback.

The five business actions (brief): `message_fulfillment_team`, `message_payments_team`, `message_logistics_team`, `message_customer`, `create_internal_note` — each persisted as an activity record. Runtime capabilities: `sleep_until`, `refresh_memory_summary`, `record_reasoning`.

## 5. Cost and safety

- Wake-on-event beats polling by ~100x; a watchdog wake that finds nothing sleeps again without calling the LLM.
- Per-run token budgets with a circuit breaker: over budget, the agent stops deciding and escalates — a human is the fallback, never an infinite loop.
- The agent holds no credentials: it only proposes allowlisted actions; model output is untrusted input; the audit trail is append-only.

## 6. Scaling path

Workers and the API replicate behind a load balancer; Postgres moves to managed hosting; Temporal moves to Temporal Cloud when one node is not enough. Real PSP integration, refunds with saga compensation, auth/multi-tenant, model tiering and a voice front door are designed as Phase 2 — the application code does not change.
