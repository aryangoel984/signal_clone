# Deploying (Railway + Vercel)

Backend on **Railway** (Docker, persistent volume), frontend on **Vercel**. About 10 minutes.
You need the two public URLs at the end: `https://<backend>.up.railway.app` and `https://<project>.vercel.app`.

## 1. Backend on Railway

1. **New Project → Deploy from GitHub repo** → pick this repo.
2. Service **Settings → Source → Root Directory**: `backend`.
   Then **Settings → Config-as-code → Railway Config File**: `/backend/railway.json`. The config file path does not
   follow the Root Directory, so without this the file (health check `/api/v1/health`, 60 s timeout, 1 replica) is ignored.
3. **Add a volume**: service → right-click / **Attach Volume** → mount path **`/data`**.
   The database and uploads live there, so they survive redeploys.
4. **Variables** (service → Variables). Railway sets `PORT` itself; don't add it.

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | `sqlite+aiosqlite:////data/app.db` (four slashes: absolute path) |
   | `UPLOADS_DIR` | `/data/uploads` |
   | `CORS_ORIGINS` | `http://localhost:3000` for now, then your Vercel URL in step 3 |
   | `DEMO_BOTS_ENABLED` | `true` |

5. **Settings → Networking → Generate Domain**. If it asks for a port, enter **8080**, the `PORT` Railway gives the
   app (the deploy log shows `Uvicorn running on http://0.0.0.0:8080`). Copy the URL (`https://<backend>.up.railway.app`).
6. Check: open `https://<backend>.up.railway.app/api/v1/health`. It should show `{"status":"ok"}`.
   The first deploy log should show `Seed complete: users=11, ...`.

Keep it at **1 replica**: live connections are tracked in memory and SQLite has one writer.

## 2. Frontend on Vercel

1. **Add New → Project** → import the same repo.
2. **Root Directory**: `frontend`. Framework: Next.js (auto). Node.js 24.x is picked from `package.json`.
3. **Environment Variables**:

   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://<backend>.up.railway.app` (no trailing slash) |
   | `NEXT_PUBLIC_WS_URL` | `wss://<backend>.up.railway.app` (note `wss://`) |

4. **Deploy**. Copy the URL (`https://<project>.vercel.app`).

These two values are built into the JavaScript at build time: after changing them, **redeploy** the frontend.

## 3. Connect them (CORS)

Back in Railway → Variables, set:

```
CORS_ORIGINS=https://<project>.vercel.app,http://localhost:3000
```

Exactly the origin: `https://`, no path and **no trailing slash** (the app strips one if you paste it, but the browser
sends none). Railway redeploys the backend; the volume keeps the data.

## Order, in short

Backend (with volume) → copy backend URL → Vercel with that URL → copy Vercel URL → `CORS_ORIGINS` on Railway.

## Notes

- **Seed on boot** is the idempotent `python -m app.seed`: it fills an empty volume once and changes nothing later.
  Never put `--reset` in the start command. For a clean demo dataset, run it **once by hand** from the Railway shell:
  `python -m app.seed --reset`, then restart the service so the bots are recognised.
- **Demo login**: `+1 555 010 0001` (Alex) or `+1 555 010 0002` (Priya), code `123456`. Message **Maya (bot)** to see
  delivered → read → typing → reply on the live site.
- Send me both URLs and I'll run the live checks (health, CORS, login, WebSocket, bots, persistence across a redeploy).
