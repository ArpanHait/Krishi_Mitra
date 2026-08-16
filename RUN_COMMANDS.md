
### Terminal 1: Backend Agent (Python + LiveKit + Murf Falcon)

```

cd backend
$env:PATH += ";$env:USERPROFILE\.local\bin"
uv run python src/agent.py dev
```

---

### Terminal 2: Frontend UI (Next.js + LiveKit React Components)

```

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
