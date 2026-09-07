# AI Order Supervisor — System Architecture

## 1. Overview

The AI Order Supervisor is a long-running AI system that supervises a single order from creation to completion.

Each order is managed by one Temporal workflow. The workflow receives order events through Temporal Signals, wakes the agent when action may be required, executes tools when necessary, and sleeps until the next event or scheduled wake-up.

The system uses Next.js for the operator UI, FastAPI for the backend API, Temporal for durable workflow execution, PostgreSQL for persistence, and an LLM for agent decision-making.