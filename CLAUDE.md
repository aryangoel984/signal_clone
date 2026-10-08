# Signal Clone: Project Instructions

## Project overview
A full-stack clone of the Signal Desktop messaging app, built as an SDE assignment.
The goal is to replicate Signal's look, feel, and core messaging workflows.
Real end-to-end encryption and real phone verification are NOT required; mock them.

Read these before starting any task:
- `docs/ASSIGNMENT.md`: the full assignment and evaluation criteria
- `docs/PLAN.md`: the schema, API, WebSocket contract, and build phases
- `docs/reference/`: Signal Desktop screenshots (light and dark). This is the UI source of truth.

## Tech stack
- **Frontend:** Next.js (App Router) + TypeScript, Tailwind CSS, Zustand for client state
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.x, Pydantic v2
- **Database:** SQLite (file: `backend/app.db`), migrations via Alembic or `create_all` (decide in PLAN.md)
- **Real-time:** native FastAPI WebSockets (no Socket.IO)
- **Auth:** mocked OTP (fixed code `123456`), session token stored server-side (hashed), sent as `Authorization: Bearer <token>`. The frontend keeps it in `localStorage`, not an httpOnly cookie (decided; reasons in PLAN.md "Auth token storage")

## Repo structure
```
signal-clone/
├── CLAUDE.md
├── README.md
├── docs/
│   ├── ASSIGNMENT.md
│   ├── PLAN.md
│   └── reference/            # Signal screenshots
├── backend/
│   ├── app/
│   │   ├── main.py           # app factory, CORS, router registration
│   │   ├── core/             # config, security, db session, dependencies
│   │   ├── models/           # SQLAlchemy models (one file per entity)
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── routers/          # thin HTTP handlers (auth, users, contacts, conversations, messages, groups)
│   │   ├── services/         # business logic (routers call services, never the reverse)
│   │   ├── ws/               # WebSocket connection manager and event handlers
│   │   └── seed.py           # seed script
│   ├── tests/
│   ├── requirements.txt      # runtime only (Docker image)
│   ├── requirements-dev.txt  # + test tools
│   ├── Dockerfile
│   └── railway.json
└── frontend/
    ├── src/
    │   ├── app/              # routes (login, verify, onboarding, main app shell)
    │   ├── components/       # reusable UI (Avatar, MessageBubble, ConversationItem, Modal, Toast...)
    │   ├── features/         # feature folders (chat, conversations, groups, settings)
    │   ├── hooks/            # useWebSocket, useTyping, usePresence...
    │   ├── store/            # Zustand stores
    │   ├── lib/              # api client, ws client, utils, date formatting
    │   ├── styles/           # theme tokens (colors, fonts, spacing)
    │   └── types/            # shared TypeScript types
    └── package.json
```

## Core rules
1. **Original code only.** Do not copy from existing Signal clones or GitHub repos. Write everything from scratch.
2. **Separation of concerns.** Routers only validate input and call services. Services hold logic. Models only define persistence. Do not put DB queries in routers or components.
3. **Type everything.** Full type hints in Python, strict TypeScript on the frontend, with no `any`.
4. **Small, readable functions.** Prefer clear names over comments. Add a short docstring or comment only where the logic is non-obvious.
5. **I must be able to explain every line.** Do not add clever abstractions or libraries I haven't approved. Prefer simple and explicit over clever.
6. **No hardcoded secrets or URLs.** Use environment variables (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, `CORS_ORIGINS`, `DATABASE_URL`) and keep `.env.example` files up to date.

## Workflow (important)
- Work **one phase at a time**, following `docs/PLAN.md`. Do not jump ahead.
- **Before coding each phase, show me a short plan and wait for my approval.**
- After each phase: run the code, test it (curl, pytest, or the browser), fix errors, then summarize what changed and which files were touched.
- Do not make large unrelated refactors. If you spot a problem outside the current task, tell me instead of fixing it silently.
- Suggest a commit message at the end of each phase. I will commit myself.
- When a decision affects the schema, API, or WebSocket contract, update `docs/PLAN.md` in the same change.

## Database conventions
- Primary keys: UUID strings (or integer autoincrement; follow PLAN.md consistently)
- Every table has `created_at`; mutable tables also have `updated_at`
- Use proper foreign keys with `ON DELETE` behavior defined explicitly
- Index columns used for lookups and sorting (e.g. `messages(conversation_id, created_at)`)
- Enable `PRAGMA foreign_keys=ON` for SQLite
- Core tables: `users`, `contacts`, `conversations`, `conversation_members`, `messages`, `message_receipts`, `reactions`, `attachments`, `sessions`

## API conventions
- REST under `/api/v1`, with plural nouns, correct status codes, and consistent error shape `{ "detail": "..." }`
- Pagination on message history (cursor-based, by message id or timestamp)
- All endpoints except `/auth/*` require authentication
- WebSocket endpoint: `/ws?token=...`. Events are JSON `{ "type": "...", "payload": {...} }`
- Event types: `message.new`, `message.status`, `typing.start`, `typing.stop`, `presence.update`, `group.updated`, `reaction.updated`
- The server is the source of truth for message status: `sending → sent → delivered → read`

## Mocking rules
- OTP is always `123456`
- "Encryption" is a visual placeholder only (e.g. a "Messages are end-to-end encrypted" notice). Do not implement real crypto.
- Presence and last-seen are derived from WebSocket connect/disconnect, with sensible mocked values for seeded users
- Voice/video calls, Stories, and Linked devices are "Coming soon" placeholder screens

## UI/UX target: Signal Desktop
The UI must match Signal Desktop as closely as possible. Always compare against `docs/reference/` screenshots.

- **Layout:** left sidebar (~320-380px) with header (avatar, search, compose button) and conversation list, plus a main chat pane on the right. An empty state with the Signal logo shows when no chat is selected.
- **Colors:** primary Signal blue `#2C6BED`. Define ALL colors as tokens in one theme file (CSS variables or the Tailwind config). Never hardcode hex values in components.
- **Light and dark mode:** both themes use the same tokens. Dark mode follows the system preference and has a manual toggle.
- **Typography:** Inter (the closest available match to Signal's font), with a system font fallback. Sizes and weights come from the theme tokens.
- **Message bubbles:** outgoing bubbles use the primary blue with white text. Incoming bubbles use a neutral gray. Rounded corners, grouped consecutive messages, a timestamp and status ticks inside the bubble's bottom-right, and date separators between days.
- **Conversation list item:** avatar with an online dot, name, last-message preview (truncated), time, an unread count badge (blue pill), and a bold name and preview when unread.
- **Components to match:** modals (new message, new group, add members), toasts, context menus, the settings pages (Privacy, Notifications, Appearance, Chats), and the onboarding/registration screens.
- **Avatars:** colored circle with initials as the fallback when there is no photo. Use a deterministic color per user.
- **Responsive:** desktop is two-pane; on mobile show the list or the chat as a single pane with a back button.
- Smooth, subtle transitions only. No flashy animations.

## Real-time behavior checklist
- Sending a message shows it immediately (optimistic, status "sending"), then updates to sent, delivered, and read from server events.
- Typing indicator appears within about 300ms and clears after about 3s of inactivity.
- Read receipts are sent when a message is visible in the open chat.
- In groups, "delivered" and "read" are tracked per member in `message_receipts`.
- The WebSocket client auto-reconnects with backoff and refetches missed messages on reconnect.

## Seed data
`backend/app/seed.py` must be idempotent and create:
- 8+ users with names, avatars, and statuses
- 5+ direct conversations and 2+ groups with realistic message history (different timestamps, mixed statuses, some unread)
- a login shortcut documented in the README (demo user phone number + OTP `123456`)

## Testing and verification
- Backend: write pytest tests for auth, message send, receipts, and group permissions
- Always run the backend (`uvicorn app.main:app --reload`) and the frontend (`npm run dev`) to verify changes before reporting done
- For UI work, take a screenshot and list the differences vs. the reference screenshot, then fix them

## Commands
```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt     # runtime deps + pytest (requirements.txt is runtime only, for Docker)
python -m app.seed
uvicorn app.main:app --reload --port 8000
pytest -q                               # tests

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:3000
```

## Definition of done (per phase)
- [ ] Feature works end-to-end (verified by running it)
- [ ] No TypeScript or Python type errors, no console errors
- [ ] `docs/PLAN.md` updated if schema, API, or events changed
- [ ] Summary of changes given, with a suggested commit message

## Deliverables reminder
Final repo must include a README with: setup instructions, tech stack, architecture overview, DB schema (ER diagram or table list), API overview, assumptions, and the deployed demo link.