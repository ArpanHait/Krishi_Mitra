# AGENTS.md

This is a monorepo for a voice AI agent starter, powered by Murf Falcon TTS and LiveKit Agents.

## Repository structure

```
murf-livekit-starter/
├── backend/          # Python voice agent (LiveKit Agents + Murf Falcon TTS)
│   ├── src/agent.py  # Agent entrypoint — all pipeline config lives here
│   └── tests/        # LLM-judged eval tests
├── frontend/         # Next.js UI (LiveKit Agents UI components)
│   ├── app/          # Pages and API routes
│   ├── components/   # UI components (agents-ui, app, ui)
│   └── app-config.ts # Branding and feature config
├── start_app.sh      # Start all services (macOS/Linux)
└── start_app.ps1     # Start all services (Windows)
```

## Backend

### Tech stack
- **Python 3.10+** with **uv** package manager
- **LiveKit Agents SDK** (`livekit-agents ~1.4`) — voice AI agent framework
- **Murf Falcon** (`livekit-murf`) — text-to-speech
- **Deepgram Nova-3** — speech-to-text
- **Google Gemini** — LLM
- **Silero VAD** + **LiveKit Turn Detector** — voice activity and turn detection

### Key file: `backend/src/agent.py`
This is the single entrypoint. It contains:
- `SYSTEM_PROMPT` — controls the agent's behavior (change this to change the use case)
- `Assistant` class — extends `Agent`, where tools are added via `@function_tool`
- `my_agent()` — sets up the voice pipeline (STT → LLM → TTS) and connects to LiveKit
- `prewarm()` — pre-loads the Silero VAD model

### Running the backend
```bash
cd backend
uv sync
uv run python src/agent.py download-files   # first time only
uv run python src/agent.py dev              # development
uv run python src/agent.py console          # terminal-only testing
```

### Environment variables
Copy `backend/.env.example` to `backend/.env.local`. Required keys:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `MURF_API_KEY`
- `DEEPGRAM_API_KEY`
- `GOOGLE_API_KEY`

### Code style
Uses **ruff** for linting and formatting:
```bash
uv run ruff check .
uv run ruff format .
```
Config is in `pyproject.toml` — 88 char line length, double quotes, space indent.

### Testing
Tests are in `backend/tests/test_agent.py`. They use LiveKit's testing framework with LLM-as-judge evaluation (not mocks). Run with:
```bash
uv run pytest
```
Requires `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` to be set.

When modifying the system prompt or adding tools, write tests first. Use the existing tests as a pattern — they call `session.run(user_input=...)` and use `.judge()` to evaluate responses.

### Dependencies
Managed via `uv` and defined in `pyproject.toml`. Always use `uv sync` and `uv run` — never `pip install`.

## Frontend

### Tech stack
- **Next.js** (React, TypeScript)
- **pnpm** package manager
- **LiveKit Agents UI** (shadcn-based components)
- **Tailwind CSS**

### Key files
- `frontend/app-config.ts` — branding, feature flags, accent colors, visualizer config
- `frontend/app/page.tsx` — main page
- `frontend/app/api/token/route.ts` — LiveKit token endpoint
- `frontend/components/app/` — app-level logic (welcome view, view controller, theme)
- `frontend/components/agents-ui/` — voice UI components (visualizers, controls, chat)

### Running the frontend
```bash
cd frontend
pnpm install
pnpm dev
```

### Environment variables
Copy `frontend/.env.example` to `frontend/.env.local`. Required:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `AGENT_NAME` (optional — set to `my-agent` for explicit dispatch)

### Linting
```bash
pnpm lint         # ESLint
pnpm format:check # Prettier
```

## Common tasks

### Change what the agent does
Edit `SYSTEM_PROMPT` in `backend/src/agent.py`. See `backend/README.md` for example prompts.

### Change the voice
Edit the `voice` argument in `murf.TTS(...)` in `backend/src/agent.py`. Browse voices at https://murf.ai/api/docs/voices-styles/voice-library.

### Add a tool to the agent
Add a method to the `Assistant` class in `backend/src/agent.py` with the `@function_tool` decorator. There's a commented example (weather lookup) in the file. Import `function_tool` and `RunContext` from `livekit.agents`.

### Switch the LLM
Replace the `llm=google.LLM(...)` call in `agent.py`. For OpenAI: install `livekit-agents[openai]`, set `OPENAI_API_KEY`, import `openai` from `livekit.plugins`, and use `openai.LLM(...)`.

### Change frontend branding
Edit `frontend/app-config.ts` — company name, page title, logo paths, accent colors, button text, visualizer type.

## Documentation references

- Murf Falcon TTS: https://murf.ai/api/docs/text-to-speech/streaming
- Murf Voice Library: https://murf.ai/api/docs/voices-styles/voice-library
- LiveKit Agents SDK: https://docs.livekit.io/agents
- LiveKit Agents UI: https://livekit.io/ui
- Deepgram STT: https://developers.deepgram.com

## Customization Rules & Directives
- **Always present proposed thoughts and implementation plan**: Before making code edits or executing steps, always outline the thoughts, analysis, and step-by-step plan to the user.
- **120 FPS UI Animation Standard**: Always target **120 FPS** high-refresh-rate GPU hardware acceleration (`transform-gpu`, `will-change-[opacity,transform]`) for frontend UI transitions and visual components.
- **Page Transition Isolation**: Always use `mode="wait"` on Framer Motion `<AnimatePresence>` to prevent full-height (`min-h-svh`) layout stacking, scrollbar popping, and vertical reflow during screen transitions.
- **Context Management & Token-Lean Protocol**:
  - **Artifact-First Offloading**: Offload long logs, detailed plans, architecture analyses, and code diffs to Markdown artifacts (`implementation_plan.md`, `walkthrough.md`) to prevent context window bloat.
  - **Token-Lean Communication**: Keep chat responses short, precise, and direct with clickable markdown links (`[filename](file:///path/to/file)`). Avoid re-summarizing artifact contents in chat messages.
  - **Silent Command Execution**: Inspect background process outputs silently and synthesize exact findings cleanly without outputting raw log dumps into chat.
- **Core Engine & LLM Constraints**:
  - **Model**: Must strictly maintain `gemini-3.1-flash-lite` across all voice agents (`Krishi Mitra` and `Fasal Doctor`).
  - **Zero Thinking Budget**: `google.LLM` MUST be instantiated with `thinking_config=types.ThinkingConfig(thinking_budget=0)` to prevent Gemini 3.1 `504 DEADLINE_EXCEEDED` timeouts.
  - **Non-Preemptive Generation**: Maintain `preemptive_generation=False` on `AgentSession` setup.
  - **Zero Mock Baseline**: SQLite DB (`db.py`) metric counters start at 0 baseline seed data and increment strictly on authentic events.
  - **Script Matching**: Enforce 100% strict language script matching (English/Latin $\rightarrow$ pure English, Hindi/Devanagari $\rightarrow$ Devanagari Hindi, Bengali $\rightarrow$ Bengali).
