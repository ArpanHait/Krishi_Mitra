# How to Run the Krishi Mitra Voice Agent

You can start both servers either using the **one-command script** or by opening **two separate terminal windows**.

---

## Option 1: One-Command Startup (Recommended)

Run this single command from the project root directory (`murf-livekit-starter`):

```powershell
.\start_app.ps1
```

This will automatically open two separate PowerShell windows:
1. One for the **Backend Python Agent**
2. One for the **Frontend Next.js UI**

---

## Option 2: Run in Separate Terminals

### Terminal 1: Backend Agent (Python + LiveKit + Murf Falcon)

```powershell
cd backend
$env:PATH += ";$env:USERPROFILE\.local\bin"
uv run python src/agent.py dev
```

---

### Terminal 2: Frontend UI (Next.js + LiveKit React Components)

```powershell
cd frontend
$env:PATH += ";$env:APPDATA\npm"
pnpm dev
```

---
### Whenever you want Vercel to connect to your backend, just run:

npx localtunnel --port 8080 --subdomain krishi-backend


## Access the App

Once both terminals are running, open your web browser at:

👉 **[http://localhost:3000](http://localhost:3000)**

Click **Start talking**, grant microphone permissions, and speak to **Krishi Mitra**!
