# VolShape

[中文 README](README.md)

VolShape is an AI-native fitness coach app built to bridge a gap that has existed for a long time between two product categories:

- General conversational LLM apps such as ChatGPT, Gemini, and DeepSeek can answer questions well, but they do not reliably store, structure, and track a user's long-term body data, training history, diet records, and evolving preferences.
- Traditional fitness apps can track weight, body fat, workouts, and meals, but they usually lack an intelligent coach that can continuously understand the user, adjust plans based on real data, explain the reasoning, and grow with the user over time.

VolShape is designed to connect the strengths of both sides.

By combining LLMs, generative UI, structured data storage, long-term memory, and domain knowledge retrieval, the project allows users to manage training plans, meal records, body-state updates, recovery questions, and expert knowledge queries through natural conversation, gradually forming an AI fitness coach agent that evolves alongside the user.

## The Experience We Want to Create

In VolShape, users do not need to split "logging" and "asking" into two separate workflows.

They can simply talk to the system like they would talk to a coach:

- "I want to train chest and shoulders today, but my left shoulder feels uncomfortable. Give me a safer plan."
- "How did I actually complete yesterday's workout?"
- "My weight dropped to 78kg recently and my sleep has been average. Should I change my training volume?"
- "Here is my dinner. Estimate the calories and macros."
- "Explain what DOMS actually is and how I should recover."

After understanding the request, the system can turn part of that conversation into:

- a workout plan
- a diet card
- profile updates
- recent event logs
- long-term memory
- expert-mode knowledge retrieval context

So this is not just a chat box that answers questions. It is a product system built around training and nutrition management.

## What Has Been Implemented

### 1. Workout planning through conversation

Users can directly describe training goals, fatigue level, injury constraints, target muscle groups, and time budget in the chat screen.

VolShape combines user profile data, recent training history, recent events, and long-term memory to generate a structured workout plan displayed as an actionable card.

### 2. Workout plans can be executed and written back

Plans do not stop at text output.

Generated workout cards can be applied to the training screen, where users can check off sets during the session. Completion data is then written back as real training events and reused in future conversations.

This means the system increasingly understands:

- what the user has trained recently
- which exercises were actually completed
- which sets were missed
- how training rhythm and recovery state are changing over time

### 3. Food photo analysis and nutrition logging

Users can upload food images and let the system estimate calories and macros, generating a structured diet card.

Those results are not only shown once in chat. They are also synchronized into persistent diet records and summary views for ongoing tracking.

### 4. Silent updates to profile and preference changes

Users do not need to open a separate profile editor to manually maintain every field.

When they naturally mention things like:

- body weight changes
- training years
- current goal
- sleep quality
- fatigue state
- injury or pain
- training preferences

the system automatically extracts the parts worth storing and updates the profile, dynamic metrics, or recent event timeline.

### 5. Expert-mode knowledge answers

In expert mode, VolShape does more than call a general LLM.

It also uses an internal sports-science RAG knowledge base to provide more grounded answers on DOMS, recovery, Omega-3, hypertrophy, fatigue management, training structure, and nutrition, while showing compact source tailnotes at the end of the message.

### 6. Streaming interaction and generative UI

The frontend does not simply wait for a black-box final response.

It shows live processing states such as:

- analyzing user intent
- syncing profile
- retrieving knowledge
- planning
- reviewing safety
- generating the final response

At the same time, the UI renders different structured objects such as workout cards, diet cards, and source tailnotes, making the product feel much closer to a real AI application than a generic IM-style chat window.

## Product Loop

VolShape can be understood as a recurring product loop:

```mermaid
flowchart LR
  A["User asks through conversation"] --> B["System reads profile / training history / recent events / long-term memory"]
  B --> C["Optionally enters expert knowledge retrieval"]
  C --> D["Builds response and structured cards"]
  D --> E["User applies workout plan or confirms meal record"]
  E --> F["Workout completion / diet results are written back"]
  F --> G["Profile and long-term memory continue to evolve"]
  G --> A
```

A typical flow looks like this:

1. The user asks for today's workout.
2. The agent reads height, goal, training years, recent workout records, fatigue state, and historical preferences.
3. If the user is in expert mode, the system retrieves relevant sports-science knowledge.
4. The system returns a structured workout plan and explanation.
5. The user applies the workout card and checks off sets on the training screen.
6. Completion data is written back into the database as real training history.
7. The next time the user asks, the system answers based on real historical data instead of hallucinated context.

This is the key difference between VolShape and ordinary conversational LLM apps:
it does not just answer a single turn, it gradually builds a real and continuously updated model of the user's training world.

## How It Is Built

The goal of VolShape is not to stack AI buzzwords together, but to connect conversation, memory, retrieval, execution, safety, and write-back into one working chain.

### 1. Multi-node agent workflow

The backend uses LangGraph to build a multi-node workflow instead of a single large prompt.

A typical request is split into stages such as:

- intent recognition
- profile aggregation
- knowledge retrieval
- strategy planning
- exercise detailing
- plan evaluation
- correction
- final response building

### 2. Layered memory instead of dumping all history into the prompt

VolShape uses a layered memory design, including:

- stable user profile
- dynamic body metrics
- recent events
- semantic long-term memory
- periodic summaries

This solves the problem of how the system can build a long-term understanding of a user over time.

### 3. Structured cards powering generative UI

LLM output is not always shown as plain text.

Some results are transformed into structured objects such as:

- `WorkoutCard`
- `DietCard`

The frontend then renders them into actionable UI, allowing AI output to directly enter real business flows rather than remaining as passive suggestions.

### 4. Expert-mode RAG

To make answers on sports science, nutrition, and recovery more reliable, VolShape adds domain retrieval in expert mode.

Expert mode is not just "using a different prompt." It actually injects evidence before the response is generated.

### 5. Training safety review

Training advice is a risk-sensitive domain.

After generating a training plan, VolShape adds a safety layer that includes:

- ACWR-based workload floor checks
- an independent evaluator node
- a corrector loop when the score is too low

This helps reduce the chance of the model directly producing an inappropriate training load or recovery recommendation.

### 6. Sessions, quota, and observability

Beyond the AI itself, the project also includes product-level infrastructure such as:

- login and registration
- multi-session chat
- user quota management via NewAPI
- model request logging
- full Langfuse observability

## System Overview

```mermaid
flowchart TB
  User["User"]

  subgraph FE["Frontend · Expo / React Native"]
    Chat["Coach Screen<br/>Streaming Chat + Generative UI"]
    Train["Training Screen<br/>Apply Plan + Check-ins"]
    Explore["Profile / Explore<br/>Memory / Diet / Quota"]
  end

  subgraph API["Backend · FastAPI"]
    Stream["Chat Stream API"]
    Workout["Workout API"]
    Media["Media API"]
    Auth["Auth / Session / Quota"]
  end

  subgraph Agent["Agent Workflow"]
    Intent["Intent"]
    Profile["Profile"]
    Knowledge["Knowledge"]
    Planner["Planner"]
    Executor["Executor"]
    Evaluator["Evaluator"]
    Response["Response Builder"]
  end

  subgraph Data["Data and Retrieval"]
    SQL["PostgreSQL / SQLite"]
    Mem["Mem0 + Qdrant"]
    RAG["Qdrant + BM25"]
  end

  subgraph Obs["Observability"]
    Trace["Langfuse"]
  end

  User --> Chat
  User --> Train
  User --> Explore

  Chat --> Stream
  Train --> Workout
  Explore --> Auth
  Chat --> Media

  Stream --> Intent --> Profile --> Knowledge --> Planner --> Executor --> Evaluator --> Response

  Profile --> SQL
  Profile --> Mem
  Knowledge --> RAG
  Response --> SQL
  Workout --> SQL

  Stream --> Trace
  Executor --> Trace
  Response --> Trace
```

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If you already have PostgreSQL locally, using PostgreSQL is recommended:

```bash
set DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/volshape
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

If you just want a quick local demo, you can also run it with SQLite:

```bash
set DATABASE_URL=sqlite+aiosqlite:///volshape_local.db
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npx expo start
```

If you test with Expo Go on a phone, use LAN mode and point the frontend API configuration to a backend address reachable by the phone.

## Useful Commands

### Preview the RAG corpus

```bash
backend\.venv\Scripts\python.exe backend/ingest_rag.py --preview --json
```

### Run incremental RAG ingest

```bash
backend\.venv\Scripts\python.exe backend/ingest_rag.py --json
```

### Inspect local RAG retrieval

```bash
backend\.venv\Scripts\python.exe backend/query_rag.py "DOMS recovery fatigue" --json
```

### Run offline evals

```bash
backend\.venv\Scripts\python.exe backend/evals/run_evals.py --no-report
```

## Repo Structure

```text
backend/
  app/
    api/              FastAPI routes
    graphs/           Agent workflow and state
    services/         memory / rag / llm / tracing / quota / media
    database/         ORM models and DB sessions
  ingest_rag.py       Offline RAG ingestion entry
  query_rag.py        Retrieval inspection entry
  evals/              Offline evaluation bundle

frontend/
  src/
    app/              Chat / Train / Profile screens
    contexts/         Auth and workout state
    services/         SSE and API clients

ragdata/
  Sports-science and nutrition knowledge sources

docs/
  More detailed architecture and implementation documents
```

## License

MIT
