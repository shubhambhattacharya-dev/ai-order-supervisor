# AI Order Supervisor — System Architecture

## 1. Overview

The AI Order Supervisor is a long-running system that supervises one
e-commerce order from creation to completion.

Each order has exactly **one Temporal workflow**.

Events arrive as **signals**. The workflow controls **when** the agent
should wake, the LLM decides **what** to do, and separate activities
perform the allowed actions.

PostgreSQL stores the activity history and final output.

The workflow owns the lifecycle. The LLM never decides when the run ends.

---

## 2. Architecture

```text
                    ┌─────────────────────────┐
                    │   Next.js Operator UI   │
                    │                         │
                    │ • Supervisor config     │
                    │ • Start / control run   │
                    │ • Inject events         │
                    │ • View timeline         │
                    └────────────┬────────────┘
                                 │
                              HTTP
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      FastAPI API        │
                    │                         │
                    │ • Validate requests     │
                    │ • Start workflow        │
                    │ • Send signals          │
                    │ • Query run state       │
                    └────────────┬────────────┘
                                 │
                      Start / Signal / Query
                                 │
                                 ▼
              ┌─────────────────────────────────────┐
              │          Temporal Server             │
              │                                     │
              │     One workflow per order          │
              └────────────────┬────────────────────┘
                               │
                               ▼
              ┌─────────────────────────────────────┐
              │     Order Supervisor Workflow       │
              │                                     │
              │  Event → Decide → Act / Sleep       │
              │                                     │
              │  • Receives signals                 │
              │  • Controls lifecycle               │
              │  • Schedules durable timers         │
              │  • Handles pause / resume           │
              └──────────────┬──────────┬───────────┘
                             │          │
                    Decide   │          │ Sleep / Wake
                             │          │
                             ▼          ▼
                 ┌────────────────┐   ┌───────────────┐
                 │ Decide Activity│   │ Durable Timer │
                 │                │   │               │
                 │ Current event  │   │ Temporal      │
                 │ + context      │   │ sleep / wake  │
                 └───────┬────────┘   └───────┬───────┘
                         │                    │
                         ▼                    │
                 ┌────────────────┐           │
                 │  LLM Gateway   │           │
                 │                │           │
                 │ Provider       │           │
                 │ fallback       │           │
                 │ JSON validation│           │
                 └───────┬────────┘           │
                         │                    │
                         ▼                    │
                 ┌────────────────┐           │
                 │   LLM Provider │           │
                 └────────────────┘           │
                         │                    │
                  Proposed action             │
                         │                    │
                         ▼                    │
                 ┌────────────────┐           │
                 │ Action Activity│           │
                 │                │           │
                 │ Allowlist      │           │
                 │ validation     │           │
                 │                │           │
                 │ Execute action │           │
                 └───────┬────────┘           │
                         │                    │
                         └────────┬───────────┘
                                  │
                                  ▼
                       ┌────────────────────┐
                       │    PostgreSQL      │
                       │                    │
                       │ • Supervisor data  │
                       │ • Activity records │
                       │ • Final output     │
                       └─────────┬──────────┘
                                 │
                                 ▼
                       ┌────────────────────┐
                       │    Final Output    │
                       │                    │
                       │ • Summary          │
                       │ • Actions          │
                       │ • Learnings        │
                       │ • Feedback         │
                       └────────────────────┘