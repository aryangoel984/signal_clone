# Signal Clone

A Signal Desktop clone built with Next.js, FastAPI, SQLite and WebSockets.
Work in progress. Setup, architecture and the API overview are added as phases land; see [docs/PLAN.md](docs/PLAN.md).

## Run locally

```bash
# Backend (Python 3.11)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt     # runtime deps + test tools
cp .env.example .env
python -m app.seed                      # idempotent demo data
uvicorn app.main:app --reload --port 8000
pytest -q                               # tests

# Frontend (Node 24)
cd frontend && nvm use && npm install
cp .env.example .env.local
npm run dev                             # http://localhost:3000
```

Deploying: see [docs/DEPLOY.md](docs/DEPLOY.md).

## Demo login

Phone `+1 555 010 0001` (Alex Rivera) or `+1 555 010 0002` (Priya Sharma), verification code `123456`.
The register screen has a "Demo accounts" panel that fills these in.

## Known limitations of the mocked auth

- **Account enumeration:** the OTP is a fixed mock code (`123456`), and `POST /api/v1/auth/otp/verify` returns `is_new_user`. Anyone can therefore find out whether a phone number has an account. `otp/request` answers the same way for every number, but that doesn't prevent this. A real deployment would send a real one-time code and not reveal account existence before the code is proven.
