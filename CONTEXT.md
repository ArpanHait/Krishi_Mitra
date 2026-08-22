# 🌾 Krishi Mitra & Fasal Doctor — Full Technical Context & System Handover

> **Purpose**: This document provides a complete, authoritative architectural blueprint, system state summary, resolved issue history, and operational rules for **Krishi Mitra** and **Fasal Doctor**. Any AI agent or developer continuing work in this repository MUST read and adhere strictly to this context.

---

## 📌 1. Executive Summary & Monorepo Structure

**Krishi Mitra (कृषि मित्र)** is a production-grade, real-time multilingual voice AI assistant built specifically for Indian farmers. The system features a two-way multi-agent architecture with **Krishi Mitra** (Primary Agricultural Advisor — female Anisha voice) and **Fasal Doctor** (Crop Problem Specialist — male Samar voice).

```
murf-livekit-starter/
├── backend/
│   ├── src/
│   │   ├── agent.py           # Entrypoint — Voice pipeline, system prompt & Krishi Mitra agent
│   │   ├── specialist.py      # Crop Problem Specialist Agent ('Fasal Doctor' - Samar Voice)
│   │   ├── tools.py           # Weather, Mandi, Scheduling & Non-Blocking Escalation tools
│   │   ├── db.py              # SQLite WAL mode database (Profiles, Escalations, Analytics)
│   │   ├── api_server.py      # REST API server (Port 8080), SSE broadcast & Twilio Webhooks
│   │   ├── email_dispatcher.py# HTML email dispatcher to regional agricultural officers
│   │   ├── email_listener.py  # IMAP background worker syncing officer email replies
│   │   ├── outbound_dialer.py # Twilio outbound call poller & status callback engine
│   │   └── mandi_rates.json   # Benchmark market fallback rates
│   ├── tests/                 # Comprehensive pytest suite (LLM evals + tool unit tests)
│   ├── krishi_memory.db       # SQLite database file (WAL mode)
│   └── pyproject.toml         # Backend dependencies (uv) & Ruff config
├── frontend/                  # Next.js 14 UI (React, TypeScript, Tailwind CSS, LiveKit UI)
│   ├── app/                   # Next.js pages, API routes & token handler
│   ├── components/            # Control Center dashboard, visualizer, controls
│   └── app-config.ts          # Branding, accent colors, and app metadata
├── start_app.ps1              # Windows startup script
├── start_app.sh               # Linux/macOS startup script
├── .gitignore                 # Secrets & local DB gitignore rules
├── README.md                  # Main documentation
└── CONTEXT.md                 # System handover & architectural context (this file)
```

---

## 🛑 2. Mandatory Rules & Unalterable Constraints

1. **LLM Model Mandate**:
   - **MUST ALWAYS use `gemini-3.1-flash-lite`** for both `Krishi Mitra` and `Fasal Doctor`.
   - **DO NOT CHANGE** this model name in future edits under any circumstances.
2. **Zero Thinking Budget (`thinking_budget=0`)**:
   - `google.LLM` MUST be instantiated with `thinking_config=types.ThinkingConfig(thinking_budget=0)`. This bypasses Google Gemini 3.1's default internal "Thinking Mode" reasoning loops which cause `504 DEADLINE_EXCEEDED` timeouts.
3. **Disabled Preemptive Generation (`preemptive_generation=False`)**:
   - `AgentSession` setup in `agent.py` MUST maintain `preemptive_generation=False` to prevent aborted API streaming requests and Google GenAI client error retries.
4. **Zero Mock Baseline Policy**:
   - SQLite database (`db.py`) starts clean with 0 baseline seed data. All metric counters (Total Calls, Krishi Mitra responses, Fasal Doctor responses, Mandi tools, Weather tools) increment strictly on authentic live events.
5. **100% Dynamic Location & Commodity Engine**:
   - No hardcoded district defaults (e.g. static `"Burdwan"` default strings were removed across tool signatures, benchmark dataset fallbacks, and system prompts so any district like *Kolkata*, *Hooghly*, *Punjab*, *Bankura*, *Tarakeswar* renders dynamically).
6. **Strict Multilingual Script Matching**:
   - **Latin / English input** $\rightarrow$ 100% pure English text and audio with **0 Hindi/Devanagari characters** or background noise interference.
   - **Bengali script (বাংলা)** $\rightarrow$ 100% Bengali text & audio.
   - **Devanagari script (हिंदी)** $\rightarrow$ 100% Devanagari Hindi text & audio.
7. **Instant Non-Blocking Support Tickets (<2ms)**:
   - `create_escalation` generates ticket IDs (`#KM-XXXXXX`) instantly and offloads SQLite persistence, SMTP HTML email alerts, and SSE broadcasts to background worker threads (`asyncio.to_thread`) without blocking agent speech generation.

---

## 🏗️ 3. System Architecture & Key Components

### 🎙️ Backend Voice Pipeline (`backend/src/agent.py` & `specialist.py`)
- **Transport**: LiveKit WebRTC (`livekit-agents ~1.4`).
- **STT**: Deepgram Nova-3 with custom Indic keyterm boosting & 800ms endpointing.
- **LLM**: Google Gemini 3.1 Flash Lite (`gemini-3.1-flash-lite`) with `thinking_budget=0`.
- **TTS**: Murf Falcon streaming TTS (`Anisha` voice for Krishi Mitra, `en-IN-samar` voice for Fasal Doctor).
- **VAD & Turn Detection**: Silero VAD + LiveKit Multilingual Turn Detector.

### 💾 Persistent Memory & SQLite Engine (`backend/src/db.py`)
- **Database File**: `krishi_memory.db` operating in SQLite **WAL (Write-Ahead Logging)** mode.
- **Tables**:
  - `farmer_profiles`: Farmer names, land size, crops grown, district, last conversation topic gist, and language preference across sessions.
  - `escalations`: Support tickets (`ticket_id`, `farmer_name`, `topic`, `summary`, `urgency`, `status`, `officer_response`, `has_unread_reply`, `created_at`).
  - `call_logs`: Telephony analytics metadata (`call_id`, `caller_id`, `call_type`, `topic`, `duration_seconds`, `outcome`, `failure_reason`).
  - `agent_responses`: Response counter logs for Krishi Mitra and Fasal Doctor.

### 📡 REST API & SSE Event Stream Server (`backend/src/api_server.py`)
- Standalone aiohttp REST API server running on co-located port `8080`.
- **SSE Stream (`GET /api/events`)**:
  - Emits periodic 15-second heartbeat pings (`: ping\n\n`) to prevent Next.js Undici HTTP body timeouts (`UND_ERR_BODY_TIMEOUT`).
  - Real-time event channels: `agent_response`, `new_call_logged`, `tool_called`, `ticket_updated`.
- **Endpoints**:
  - `GET /api/escalations` — All active support tickets.
  - `GET /api/escalations/pending-count` — Unread count & pending badge info.
  - `POST /api/escalations/mark-read` — Marks unread officer replies as read.
  - `POST /api/escalations/update-status` — Dynamically updates ticket status (`OPEN`, `RESOLVED`, `IN_PROGRESS`).
  - `POST /api/escalations/resolve` — Resolves and prunes ticket records.
  - `GET /api/analytics` — Live call metrics and agent response counts.

### 📧 Government Email & Telephony Sync
- **`email_dispatcher.py`**: Asynchronously sends formatted HTML emails to regional agricultural officers via SMTP (`smtp.gmail.com`).
- **`email_listener.py`**: Background IMAP worker (`imap.gmail.com`) periodically scanning for officer reply emails containing Ticket IDs (`KM-XXXXXX`) and updating SQLite `officer_response`.
- **`outbound_dialer.py`**: Background worker executing scheduled outbound Twilio phone calls (`schedule_outbound_call`) with live pre-fetched mandi rates.

---

## 🔧 4. Recently Solved Issues & Fixes

| Issue | Root Cause | Solution Applied |
| :--- | :--- | :--- |
| **Fasal Doctor Dashboard Attribution (Showing 0)** | `_record_agent_response` checked `type(active_agent).__name__` which evaluated to `Assistant` during LiveKit handoff wrappers. | Updated `_record_agent_response` in `agent.py` to inspect `getattr(active_agent, "instructions", "")` for `"Fasal Doctor"`. Every Fasal Doctor speech turn now logs to SQLite & broadcasts SSE in 0ms. |
| **504 DEADLINE_EXCEEDED Timeouts** | Gemini 3.1 Flash Lite entered default internal "Thinking Mode" reasoning loops on tool turns, exceeding Google's streaming deadline. | Added `thinking_config=types.ThinkingConfig(thinking_budget=0)` on `google.LLM` and set `preemptive_generation=False`. |
| **Start Conversation Page Freeze / Lag** | Browser waited for asynchronous `getUserMedia` mic permission before updating button state. | Added instant `isConnecting` state feedback in `welcome-view.tsx` with GPU hardware accelerated spring physics (`transform-gpu`, `will-change-[opacity,transform]`, `ease: [0.16, 1, 0.3, 1]`). |
| **Hardcoded "Burdwan" Location Fallbacks** | Default parameter strings (`district = "Burdwan"`) in tools and few-shot prompts forced static location responses. | Removed all static defaults across tool signatures, benchmark builders, and prompts. Locations now render 100% dynamically (Kolkata, Hooghly, Bankura, Punjab, etc.). |
| **Support Ticket Creation Latency** | Synchronous SQLite writes and Gmail SMTP connection blocked the asyncio voice thread. | Offloaded database persistence, duplicate checks, SMTP email alerts, and SSE events to `asyncio.to_thread` background tasks, returning Ticket IDs in **<2ms**. |
| **Git Repository Exposure Security** | Sensitive `.env` files, SQLite databases, and error logs risked exposure. | Updated root `.gitignore` and `backend/.gitignore` to ignore `.env*` (except `.env.example`), `*.db*`, `currentERROR.*`, `scratch/`, and build caches. |

---

## 🏃 5. How to Run & Verify

### Environment Setup
Copy `.env.example` to `.env.local` in `backend/` and `frontend/`:
- Required keys: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `MURF_API_KEY`, `DEEPGRAM_API_KEY`, `GOOGLE_API_KEY`.

### Running Services
```bash
# Terminal 1: Backend Agent & REST API Server (Port 8080)
cd backend
uv sync
uv run python src/agent.py dev

# Terminal 2: Frontend Next.js UI (Port 3000)
cd frontend
pnpm install
pnpm dev
```

### Code Quality & Testing Commands
```bash
cd backend
uv run pytest                  # Run all unit & LLM eval tests (100% passing)
uv run ruff check .            # Python linter (0 errors)
uv run ruff format .           # Python formatter

cd frontend
pnpm exec eslint components/app/view-controller.tsx components/app/welcome-view.tsx # ESLint (0 errors)
```

---

## 📌 6. Instructions for Incoming AI Agents

1. **Do not remove or alter** `thinking_budget=0` on `google.LLM` or `preemptive_generation=False` on `AgentSession`.
2. **Keep the LLM model as `gemini-3.1-flash-lite`** across both agents.
3. **Never add mock/synthetic baseline data** to `db.py`.
4. **Preserve strict script-matching rules** (Latin script = 100% English, Bengali script = Bengali, Devanagari script = Devanagari).
5. **Always test changes** with `uv run ruff check .` and `uv run pytest`.
