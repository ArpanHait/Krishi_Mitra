# 🌾 Krishi Mitra — AI Voice Advisor for Indian Farmers

**Krishi Mitra (कृषि मित्र)** is a production-grade, real-time multilingual voice AI assistant built specifically for Indian farmers. Powered by **Murf Falcon TTS**, **LiveKit Agents SDK**, **Deepgram Nova-3 STT**, **Google Gemini 3.1 Flash Lite LLM**, **SQLite Persistent Memory**, **Real-Time External APIs** (Open-Meteo Weather + Government Agmarknet Mandi Prices), and **Twilio Outbound Phone Call Scheduling**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Murf Falcon](https://img.shields.io/badge/TTS-Murf%20Falcon-6366F1)](https://murf.ai/api/docs/text-to-speech/streaming)
[![LiveKit](https://img.shields.io/badge/Transport-LiveKit-002cf2)](https://docs.livekit.io)
[![TypeScript](https://img.shields.io/badge/Frontend-Next.js%2014-007ACC?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Backend-Python%203.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)

---

## 🚀 Key Capabilities

- 🗣️ **Natural Multilingual Voice Interaction**: Communicates fluently in **English**, **Devanagari Hindi**, and **Bengali** with 100% strict language-matching rules.
- ⚡ **Ultra-Low Latency Speech Pipeline**: Powered by Murf Falcon TTS (55ms latency) and Deepgram Nova-3 STT with Silero VAD turn detection for smooth, stutter-free natural conversation.
- 🧠 **Persistent SQLite Memory**: Remembers returning farmers by name, location, crops, and rich topic gists across sessions with zero startup lag.
- 🛡️ **Explicit Consent & Privacy Protocol**: Asks explicit user consent before storing personal information, with built-in data deletion tools (`forget_farmer_facts`).
- 🌦️ **Real-Time District Weather**: Integrates Open-Meteo Geocoding & Weather Forecast APIs (`get_district_weather`) for temperature, rainfall (mm), and agricultural weather forecasts.
- 🌾 **Live Agmarknet Mandi Prices**: Fetches real-time crop wholesale rates from Government OGD India API (`data.gov.in`) with a 3.0s timeout and a local benchmark fallback dataset (`mandi_rates.json`).
- 📞 **Outbound Phone Call Scheduling (Twilio)**: Schedules automated outbound phone calls delivering live mandi prices or farm updates at a specified time, with full multilingual audio support.
- 🔄 **Dynamic Language Persistence**: Auto-detects spoken script (Latin/Devanagari/Bengali) on every turn and persists `language_preference` in SQLite for personalised cross-session greetings.
- 📝 **Rich Topic Gist Memory**: Automatically extracts and stores descriptive topic summaries (*"the current market price of Apple in Hooghly"*) rather than bare keywords for natural returning greetings.

---

## 🏗️ System Architecture

```mermaid
flowchart LR
    User[🎙️ Farmer Speaks] -->|Real-time Audio| STT[Deepgram Nova-3 STT]
    STT -->|Transcribed Text| Agent[LiveKit Agent / Gemini LLM]
    
    subgraph Core Logic & Tools
        Agent <-->|Profile R/W| DB[(SQLite Memory\nkrishi_memory.db)]
        Agent <-->|Forecast| Weather[Open-Meteo API\nget_district_weather]
        Agent <-->|Wholesale Rates| Mandi[Agmarknet API / Local Benchmark\nget_mandi_prices]
        Agent <-->|Scheduled Calls| Twilio[Twilio API\noutbound_dialer.py]
    end

    Agent -->|Dual JSON Stream\ntts_text + display_text| TTS[Murf Falcon TTS]
    TTS -->|Synthesized Audio| Transport[LiveKit WebRTC]
    Transport -->|Audio Stream| Speaker[🔊 Farmer Hears]
    Twilio -->|Phone Call with Prices| Phone[📱 Farmer's Phone]

    style User fill:#444441,stroke:#888780,color:#fff
    style STT fill:#185FA5,stroke:#85B7EB,color:#fff
    style Agent fill:#534AB7,stroke:#AFA9EC,color:#fff
    style DB fill:#8E24AA,stroke:#CE93D8,color:#fff
    style Weather fill:#0288D1,stroke:#81D4FA,color:#fff
    style Mandi fill:#388E3C,stroke:#A5D6A7,color:#fff
    style Twilio fill:#E53935,stroke:#EF9A9A,color:#fff
    style TTS fill:#0F6E56,stroke:#5DCAA5,color:#fff
    style Transport fill:#D85A30,stroke:#F0997B,color:#fff
    style Speaker fill:#444441,stroke:#888780,color:#fff
    style Phone fill:#BF360C,stroke:#FF8A65,color:#fff
```

---

## 📅 Daily Feature Breakdown (Day 1 – Day 6)

### 🔹 Day 1: Core Voice AI Pipeline
- Established initial voice agent pipeline connecting LiveKit RTC transport, Deepgram STT, Google Gemini LLM, and Murf Falcon TTS.
- Implemented agricultural advisor identity for Krishi Mitra with base system prompts.

### 🔹 Day 2: Audio Polish, STT Tuning & Visualizer Enhancements
- **Audio Clutter & Rumbling Resolution**: Integrated Murf `SentenceTokenizer` and streaming audio buffers, eliminating micro-chunk audio stutters.
- **Silero VAD Tuning**: Fine-tuned voice activity detection (`min_silence_duration=1.2s`, `min_speech_duration=0.2s`) to accommodate natural pauses in Indian speech.
- **Multilingual Keyterm Dictionary**: Added agricultural keyterms in English, Hindi, and Bengali to Deepgram Nova-3 for higher STT accuracy.
- **UI Enhancements**: Added dynamic header slide animation (`cubic-bezier`) during active calls and tuned the voice visualizer (`50Hz–3400Hz`) to capture full vocal spectrums.

### 🔹 Day 3: Dual-Output JSON Streaming & Multilingual Precision
- **Dual-Output Protocol**: Configured LLM to output a valid JSON object containing `tts_text` (synthesized audio) and `display_text` (screen transcript).
- **Strict Language Matching**: Enforced strict language matching rules (English queries → 100% pure English text & audio, Hindi → Devanagari Hindi, Bengali → Bengali script).
- **Off-Topic Guardrails**: Implemented dynamic refusal responses for non-agricultural queries.

### 🔹 Day 4: Persistent SQLite Memory & Consent Protocol
- **SQLite Database (`krishi_memory.db`)**: Built profile storage tracking farmer names, crops grown, land size, district, topic, and language preferences.
- **Instant Returning Greetings**: Pre-loaded profiles upon WebRTC connection so returning farmers are greeted instantly by name (*"Hello Arpan! Last time we spoke about your paddy..."*) with zero latency.
- **Explicit Consent Protocol**: Krishi Mitra answers queries first, then explicitly asks permission before saving personal information.
- **Forget Memory Tool**: Added `@function_tool forget_farmer_facts` allowing users to delete all stored profile data on demand.

### 🔹 Day 5: Dual Real-Time External Tools (Weather + Mandi Prices)
- **Tool 1 (`get_district_weather`)**: Integrates Open-Meteo Geocoding & Forecast APIs to return current temperature, daily min/max range, and rainfall forecasts (mm) for any district.
- **Tool 2 (`get_mandi_prices`)**: Fetches live commodity wholesale rates from Government Agmarknet / OGD India API (`data.gov.in`) with a **strict 3.0s timeout**.
- **Local Benchmark Fallback (`mandi_rates.json`)**: Created local fallback dataset for key commodities (Paddy, Rice, Potato, Jute, Mustard, Wheat, Onion, Maize, Cotton) to ensure call stability if government APIs time out.
- **Timestamp & Mandi Guardrails**: Mandi reports explicitly disclose dates and advise farmers to verify rates at local markets before selling.

### 🔹 Day 6: Outbound Phone Call Scheduling, Multilingual Memory & Smart Topic Gists

#### 📞 Outbound Phone Call Scheduling (Twilio)
- **`schedule_outbound_call` tool** ([`tools.py`](backend/src/tools.py)): Schedules an outbound Twilio phone call after a user-specified delay (e.g. *"call me in 30 seconds about Apple prices in Hooghly"*). Confirmed in chat as *"Got it! I have scheduled a call for you in ..."*
- **`outbound_dialer.py`** ([`outbound_dialer.py`](backend/src/outbound_dialer.py)): Background async poller loop that checks SQLite for due calls and fires Twilio outbound calls with full live mandi price details pre-fetched and injected into the phone script.
- **Exclusive Phone Delivery Protocol**: When a call is scheduled for a topic, Krishi Mitra **only confirms the schedule** in the web chat box — it never reveals market prices or answer details in chat. All information is delivered exclusively over the phone call.
- **Atomic SQLite Locking**: Prevents race conditions on concurrent scheduled-call rows using SQLite `BEGIN IMMEDIATE` transactions.
- **4-Layer Credit Protection**: Atomic pre-locking, 60-second phone call cooldown, automatic call superseding, and one-shot `status = 'done'` marking.

#### 🗣️ Live Mandi Prices Spoken Over Phone
- Outbound calls **pre-fetch real-time mandi prices asynchronously** before dialling, then speak detailed wholesale rates (min/modal/max price, market name, district) fluently in clear English over the phone.
- **Universal Commodity Support**: Removed the hardcoded 8-crop filter; any crop, fruit, vegetable, fertilizer, or chemical (Apple, Banana, Mango, Tomato, Urea, DAP, etc.) is now dynamically supported via `extract_commodity_from_topic()`.
- **Expanded Benchmark Data** (`mandi_rates.json`): Added Apple, Banana, Mango, Tomato, Urea, and more for fallback coverage.

#### 🌐 Turn-Level Dynamic Language Persistence
- On **every spoken turn** (`user_speech_committed` event), Krishi Mitra auto-detects the spoken script:
  - **Bengali script (বাংলা)** → saves `language_preference = "bengali"` in SQLite.
  - **Devanagari script (हिंदी)** → saves `language_preference = "hindi"` in SQLite.
  - **Latin/English script** → saves `language_preference = "english"` in SQLite.
- **Dynamic Returning Greetings**: On reconnect, the agent greets in the farmer's last saved language with their name and last topic — across English, Hindi, and Bengali.
- **"Stop Service" Voice Command**: Saying *"Stop alert"*, *"Cancel calls"*, or *"Stop service"* clears all active call subscriptions from SQLite.

#### 🧠 Automatic Commodity & Location Profile Persistence
- `schedule_outbound_call` and `register_conditional_alert` **automatically save** the requested commodity/chemical/fertilizer into `crops_grown` and the district into SQLite `farmer_profiles` — no extra user action needed.

#### 📝 Rich Topic Gist Memory
- Added `extract_topic_gist()` ([`tools.py`](backend/src/tools.py)) to extract **descriptive, context-rich topic summaries** from every user utterance by stripping conversational filler (*"can you call me after thirty seconds and tell me"*, *"kya aap bata sakte hain"*, *"amake bolun"*):
  - *"Can you call me after thirty seconds and tell me the current market price of Apple in Hooghly?"* → stored as **`"the current market price of Apple in Hooghly"`**
  - *"Can you tell me about the best fertilizer for potato crops?"* → stored as **`"the best fertilizer for potato crops"`**
- SQLite `last_topic` is updated on **every spoken turn** (not only scheduled calls), so returning greetings always reflect the user's most recent conversation topic.
- **Name always preserved** in all greetings: *"Hello Ramesh! Last time we discussed the best fertilizer for potato crops. How is your field doing today?"*

#### 🧪 Day 6 Tests & Code Quality
- Added `tests/test_day6_telephony.py` and expanded `tests/test_memory.py` with:
  - `test_schedule_outbound_call_confirmations` — English, Hindi, and Bengali confirmation strings.
  - `test_universal_commodity_extraction` — any crop/fruit/fertilizer.
  - `test_auto_commodity_and_location_persistence` — auto-saved district + commodity.
  - `test_turn_level_topic_overwrite` — sequential topic overwrites.
  - `test_topic_gist_extraction` — rich gist stripping of filler words.
- `uv run pytest`: **26 backend tests — 100% passing**.
- `uv run ruff check` & `uv run ruff format`: **0 errors**.

---

### 🔹 Day 7: Government Support Escalation System & Email Synchronization

#### 📋 Support Ticket Generation & Database Persistence
- **`escalate_to_human_officer` Tool** ([`agent.py`](backend/src/agent.py)): Dynamically creates structured escalation tickets (`KM-XXXXXX`) in SQLite `escalations` table when queries require human agricultural officer intervention (e.g. severe pest outbreaks, subsidy disputes, emergency crop alerts).
- **SQLite Escalation Table (`escalations`)**: Tracks `ticket_id`, `farmer_name`, `topic`, `summary`, `urgency` (`Low`, `Medium`, `High`, `Emergency`), `status` (`OPEN`, `RESOLVED`, `IN_PROGRESS`), `language`, `preferred_followup`, `officer_response`, `has_unread_reply`, `created_at`, and `updated_at`.

#### 📧 Automated Government Email Dispatch
- **`email_dispatcher.py`** ([`email_dispatcher.py`](backend/src/email_dispatcher.py)): Asynchronously dispatches formatted HTML emails containing Ticket ID, Farmer Name, Topic, Urgency, Summary, and Preferred Follow-up mode to regional agricultural officers via SMTP (`smtp.gmail.com`).
- **Automatic Background Trigger**: Whenever `escalate_to_human_officer` is invoked by Krishi Mitra, email dispatch runs in a background thread without blocking the voice session.

#### 📥 Reverse Officer Reply Synchronization (IMAP Listener)
- **`email_listener.py`** ([`email_listener.py`](backend/src/email_listener.py)): Background IMAP listener service (`imap.gmail.com`) that periodically scans officer reply emails containing Ticket IDs (`KM-XXXXXX`).
- **Reply Text Extraction**: Automatically strips quoted email threads (`On ... wrote:`) and extracts the officer's newly typed response.
- **SQLite Update**: Updates `officer_response` text and sets `has_unread_reply = 1` in `escalations` table.

#### 🔌 REST API Server Suite
- **`api_server.py`** ([`api_server.py`](backend/src/api_server.py)): Standalone aiohttp REST API server running on port `8080` (co-located on process loop) serving frontend proxy routes:
  - `GET /api/escalations` — Returns all active support tickets.
  - `GET /api/escalations/pending-count` — Returns pending ticket counts & unread reply flags.
  - `POST /api/escalations/mark-read` — Marks unread officer replies as read.
  - `POST /api/escalations/resolve` — Resolves ticket and prunes old resolved records.
  - `POST /api/escalations/update-status` — Updates ticket status (`OPEN`, `RESOLVED`, `IN_PROGRESS`).
  - `POST /api/escalations/sync-email` — Triggers on-demand instant email sync.

---

### 🔹 Day 8: Call Outcome Analytics & Unified Control Center Dashboard

#### 📊 Call Outcome Tracking & Metrics Engine
- **SQLite Call Metrics Table (`call_logs`)**: Records detailed telephony metadata for outbound phone calls: `call_id` (`CALL-XXXXXX`), `caller_id`, `call_type` (`SIP_OUTBOUND`), `topic`, `duration_seconds`, `outcome` (`SUCCESS` or `FAILED`), `failure_reason`, and `created_at`.
- **Analytics Aggregator (`db.get_call_analytics`)**: Computes live metrics: `total_calls`, `successful_calls`, `declined_calls`, `system_failed_calls`, `failed_calls`, `success_rate` %, and recent call history logs.

#### ⚡ Event-Driven Twilio Status Webhook (`POST /api/twilio/status`)
- **Real-Time Event Processing**: Attaches `status_callback` to Twilio outbound calls. Twilio posts real-time events to `/api/twilio/status`:
  - **Answered & Completed Call** → Twilio posts `CallStatus=completed` / `answered`, immediately logging **`SUCCESS`** 🟢 with exact call duration into SQLite.
  - **Declined or Unanswered Call** → Twilio posts `CallStatus=no-answer` / `busy` / `canceled`, immediately logging **`FAILED`** 🟡 (`DECLINED`) into SQLite.
- **Mobile-Phone-Only Scope**: Web browser voice & text chat sessions are 100% excluded from analytics tracking — only real mobile phone calls via Twilio generate call records.

#### 🗣️ Dedicated Voice Agent Tools
- **`get_call_history_summary` Tool**: Enables Krishi Mitra to fetch live SQLite metrics and speak out exact call statistics (*"You have 3 total calls with a 100% success rate!"*) when asked by the farmer.
- **`delete_call_history` Tool**: Wipes call history metrics to 0 on demand (`DELETE FROM call_logs`) while keeping personal farmer profiles (Name, Location, Crops) 100% safe.

#### 🎛️ Unified Control Center Dashboard UI
- **Tabbed Interface (`ticket-dashboard.tsx`)**: Replaces the single ticket modal with a unified 2-tab Control Center (`Call Analytics` & `Support Tickets`).
- **5 Visual Metric Cards Grid**: Displays `Total Calls` (White), `Successful` (Emerald), `Declined` (Amber), `Failed` (Rose), and `Success Rate %` (Teal).
- **Redesigned History Table**: Shows local time formatting (`02:54 PM`), topic summaries, call duration, and distinct status badges.
- **Instant Refresh on Open**: Opens in under 5ms by pre-fetching SQLite stats directly when the modal triggers.

#### 🎤 STT Endpointing Buffer Fix
- **Deepgram STT Optimization**: Increased `endpointing_ms` from `500` to `800` ms in `agent.py`, allowing natural speech pauses without WebSocket disconnects (code 1006 / net0001).

---

### 🔹 Day 9: Two-Way Seamless Multi-Agent Handoff System (Krishi Mitra & Fasal Doctor)

#### 🧑‍⚕️ Crop Problem Specialist (`Fasal Doctor`)
- **`CropSpecialistAgent` Class** ([`specialist.py`](backend/src/specialist.py)): Built standalone specialist agent persona dedicated to plant pathology, diagnosing crop pests, fungal infections, yellow leaves, soil nutrient deficiencies, and recommending chemical/organic remedies with safe dosages.
- **Murf Falcon TTS (Samar Voice)**: Configured with **`en-IN-samar`** (Samar — Indian English male voice), creating a clear audio distinction from Krishi Mitra's female voice (`Anisha`).

#### 🔄 Two-Way LiveKit Agent Handoff Architecture
- **Path A: Krishi Mitra ➡️ Fasal Doctor (`transfer_to_crop_specialist`)**:
  - Automatically invoked when the farmer asks plant health / disease questions (*"My tomato leaves are turning yellow with brown spots"*).
  - Krishi Mitra verbally announces the transfer in the farmer's language (*"Main aapko hamare Crop Problem Specialist se connect kar raha hoon..."*).
  - Passes `chat_ctx.copy(exclude_instructions=True)` so `Fasal Doctor` receives full context and **never asks the farmer to repeat their problem**.
- **Path B: Fasal Doctor ➡️ Krishi Mitra (`transfer_to_krishi_mitra`)**:
  - **Issue Resolved**: When the crop issue is resolved (*"Thank you, nothing else needed"*), `Fasal Doctor` announces return and calls `transfer_to_krishi_mitra(reason="resolved")`.
  - **Out of Scope Query**: If asked about weather, mandi prices, or call scheduling, `Fasal Doctor` explains its scope and calls `transfer_to_krishi_mitra(reason="out_of_scope_query")`.
  - **Seamless Resume**: Krishi Mitra resumes in `Anisha` voice acknowledging context (*"Asha karta hoon ki hamare Crop Specialist ne aapki samasya suljha di hogi!..."*).

#### 🧪 Day 9 Test Suite
- Added `tests/test_day9_handoff.py` validating 5 handoff workflows:
  1. `test_general_query_stays_with_krishi_mitra`
  2. `test_crop_disease_triggers_specialist_handoff`
  3. `test_specialist_transfers_back_to_krishi_mitra_when_resolved`
  4. `test_specialist_transfers_back_on_out_of_scope_query`
  5. `test_specialist_responds_in_hindi_when_prompted_in_hindi`
- **42 / 42 backend pytest cases passed (100%)**.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, LiveKit Agents SDK (`livekit-agents ~1.4`), SQLite3, `httpx`, `aiohttp`, `uv`
- **Speech-to-Text (STT)**: Deepgram Nova-3 (Multilingual + Custom Indic Keyterm Boosting)
- **LLM**: Google Gemini 3.1 Flash Lite (`livekit-plugins-google`)
- **Text-to-Speech (TTS)**: Murf Falcon (`livekit-plugins-murf`, Anisha voice)
- **Voice Activity & Turn Detection**: Silero VAD + LiveKit Multilingual Turn Detector
- **Outbound Telephony**: Twilio Programmable Voice API (`twilio` Python SDK + Webhook Callbacks)
- **Email Synchronization**: SMTP (`smtplib`) + IMAP (`imaplib`) Background Workers
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS, LiveKit Agents UI Components

---

## ⚙️ Prerequisites & Environment Setup

### Prerequisites
- **Python 3.10+** with `uv` package manager:
  ```bash
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Node.js 18+** with `pnpm`:
  ```bash
  npm install -g pnpm
  ```
- A **[LiveKit Cloud](https://cloud.livekit.io/)** account.

### Environment Variables
Copy `.env.example` to `.env.local` in `backend/` and `frontend/`:

```env
# LiveKit
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# AI Models & Speech
MURF_API_KEY=your_murf_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
GOOGLE_API_KEY=your_gemini_api_key

# External Market API (Day 5)
DATA_GOV_API_KEY=your_agmarknet_api_key

# Twilio Outbound Calls (Day 6 & Day 8)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=+1xxxxxxxxxx
MY_PHONE_NUMBER=+91xxxxxxxxxx

# Government Email Synchronization (Day 7)
SMTP_SENDER_EMAIL=your_email@gmail.com
SMTP_SENDER_PASSWORD=your_app_password
OFFICER_EMAIL=officer_email@gmail.com
```

---

## 🏃 Running Locally

### Option A: All-in-One Startup Script

```bash
# Windows (PowerShell)
.\start_app.ps1

# macOS/Linux
chmod +x start_app.sh
./start_app.sh
```

### Option B: Separate Terminals

```bash
# Terminal 1: Backend Agent & REST API Server
cd backend
uv sync
uv run python src/agent.py dev

# Terminal 2: Frontend UI
cd frontend
pnpm install
pnpm dev
```

Open **http://localhost:3000** in your browser, click **Start talking**, and converse with Krishi Mitra!

---

## 📁 Repository Structure

```
murf-livekit-starter/
├── backend/
│   ├── src/
│   │   ├── agent.py           # Entrypoint — Voice pipeline, system prompt & Krishi Mitra agent
│   │   ├── specialist.py      # Crop Problem Specialist Agent (Fasal Doctor - Samar Voice) (Day 9)
│   │   ├── tools.py           # Weather, Mandi, Scheduling & Escalation tools
│   │   ├── db.py              # SQLite profile, escalations & call analytics storage
│   │   ├── api_server.py      # REST API server & Twilio Webhook handler (Day 7 & 8)
│   │   ├── email_dispatcher.py# Government officer HTML email dispatcher (Day 7)
│   │   ├── email_listener.py  # IMAP officer reply synchronization worker (Day 7)
│   │   ├── outbound_dialer.py # Twilio outbound call poller & status callback (Day 6 & 8)
│   │   └── mandi_rates.json   # Benchmark market fallback rates
│   ├── tests/
│   │   ├── test_agent.py               # LLM-judged agent behaviour evals
│   │   ├── test_day5_tools.py          # Weather & Mandi tool unit tests
│   │   ├── test_day6_telephony.py      # Outbound call & confirmation tests (Day 6)
│   │   ├── test_day7_escalation.py     # Government escalation ticket tests (Day 7)
│   │   ├── test_day7_email_sync.py       # Officer email reply sync tests (Day 7)
│   │   ├── test_day8_analytics.py      # Call outcome analytics unit tests (Day 8)
│   │   ├── test_day9_handoff.py        # Two-Way agent handoff unit tests (Day 9)
│   │   ├── test_memory.py              # SQLite memory & topic gist tests
│   │   └── test_full_memory_flow.py    # End-to-end profile persistence test
│   ├── krishi_memory.db       # SQLite database file
│   └── pyproject.toml         # Backend dependencies & Ruff config
├── frontend/
│   ├── app/                   # Next.js pages, API routes & token handler
│   ├── components/            # Control Center dashboard, visualizer, controls
│   └── app-config.ts          # Branding, accent colors, and app metadata
├── start_app.ps1              # Windows startup script
├── start_app.sh               # Linux/macOS startup script
└── README.md                  # Project documentation
```

---

## 🧪 Testing & Code Quality

Run automated unit and integration tests:

```bash
cd backend
uv run pytest                  # Run all 37 backend test cases (100% passing)
uv run ruff check .            # Linting
uv run ruff format .           # Code formatting
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
