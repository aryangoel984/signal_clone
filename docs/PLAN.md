# Signal Clone: Technical Plan

> Source of truth for the schema, API, WebSocket contract and build order. Update this file whenever any of them changes.

## 0. Key decisions (summary)

| Decision | Choice | Why |
|---|---|---|
| Primary keys | `INTEGER PRIMARY KEY AUTOINCREMENT` on every table that has a surrogate `id` | Simple to explain and debug. Message ids always increase, so the id works directly as the pagination cursor and the "catch up after reconnect" cursor. Ids are guessable, but every endpoint checks membership, so that doesn't matter. |
| Id reuse | **Every** table puts `SQLITE_TABLE_ARGS = {"sqlite_autoincrement": True}` (from `models/base.py`) in its `__table_args__`, so **ids are never reused**. A test fails if any table is missing it. | Without `AUTOINCREMENT`, SQLite may hand out the id of the most recently deleted row again. A reused message id would break cursors, watermarks (`last_read_message_id`) and client caches keyed by id. SQLAlchemy emits `AUTOINCREMENT` only for a single integer, non-FK primary key, so in the DDL it appears on the 5 surrogate-id tables (`users`, `sessions`, `conversations`, `messages`, `attachments`). On the composite- or FK-keyed tables the option is a verified no-op. |
| ORM mode | **Async SQLAlchemy 2.x** (`AsyncSession` + `aiosqlite`), `async def` endpoints | The WebSocket manager, the REST handlers that broadcast, and the seed bot's delayed tasks all run on **one asyncio event loop**. No thread pool means no locks and no thread-to-loop bridging (see "Connection manager" in section 3). Cost: lazy loading is not allowed, so relationships are loaded explicitly with `selectinload()`. Sessions use `expire_on_commit=False`. Tests use `pytest-asyncio` and `httpx.AsyncClient`. |
| Schema creation | `Base.metadata.create_all()` (run via `conn.run_sync`) + idempotent `seed.py` | The schema is greenfield and owned by one person. Alembic adds ceremony we don't need yet. If we need it after deploy, we add it then. |
| Timestamps | UTC, via the `UTCDateTime` column type (`core/time.py`): stored as naive UTC text, returned as timezone-aware UTC. Naive datetimes are rejected on write. | SQLite has no timezone support, and mixing naive and aware datetimes causes comparison bugs. Python code only ever sees aware UTC. The frontend formats times for display. |
| Message status | Not stored on `messages`. Derived from `message_receipts` | One source of truth. Groups need per-member status anyway. `sending` exists only on the client. |
| Auth token storage | `Authorization: Bearer` + `localStorage` (not an httpOnly cookie). See "Auth token storage" in section 2. | Frontend and API are on different sites, so a cookie would be a third-party cookie: it needs `SameSite=None`, CSRF protection, and can be blocked by the browser. WebSockets can't send an `Authorization` header and need the token explicitly anyway. |
| Writes vs push | REST for every persisted mutation. WS for server push and short-lived client events (typing) | REST gives validation, status codes and idempotency. WS stays a simple broadcast channel. |
| Real-time scale | One process, in-memory connection manager (`uvicorn --workers 1`) | Enough for the demo. Stated as an assumption in the README. Redis pub/sub would be the next step. |
| SQLite settings | A sync `"connect"` listener on `engine.sync_engine` (`core/db.py`) runs, in order: `busy_timeout=5000`, `foreign_keys=ON`, `journal_mode=WAL`, `synchronous=NORMAL`, on **every** connection | `busy_timeout` comes first so the later pragmas wait for a lock instead of failing. `foreign_keys` is per-connection and off by default. WAL lets reads run while a write is in progress. The listener is sync because pool events fire on the sync engine; with aiosqlite it receives SQLAlchemy's sync-style adapter connection. |

## 1. SQLite schema

Every table has `created_at`. Mutable tables also have `updated_at`. All FKs declare `ON DELETE` explicitly.

Conventions (`app/models/`, one file per model):
- **Constraint names** come from a naming convention (`pk_`, `fk_`, `uq_`, `ck_<table>_<name>`, `ix_`). Error messages and tests can refer to them.
- **Enums** (`type`, `role`, `kind`, `theme`) are TEXT columns with a CHECK. They store the **lowercase values** (`'direct'`, `'group'`), not the Python member names (`values_callable` in `models/enums.py`).
- **Relationships** are `lazy="raise"`. Queries load what they need with `selectinload()`. Parents use `passive_deletes=True`, so the database's `ON DELETE` rules do the deleting.
- **Not a CHECK on purpose:** "text messages must have a sender". `messages.sender_id` is `ON DELETE SET NULL`, so that CHECK would make deleting a user fail.

### 1.1 `users`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| phone_number | TEXT NOT NULL **UNIQUE** | E.164 (`+919876543210`). The registration/login identity, as in Signal. |
| username | TEXT UNIQUE NULL | Optional handle for discovery. Stored lowercased. |
| display_name | TEXT NULL | NULL until onboarding finishes. Lets the frontend send unfinished users to `/onboarding`. |
| about | TEXT NULL | Signal's "About" line. |
| avatar_url | TEXT NULL | Uploaded image path. NULL means show the initials avatar. |
| avatar_color | TEXT NOT NULL | Signal color token (`A100`…`A210`) picked deterministically from the phone number (`core/avatar_colors.py`). Stored so the color stays the same if the hash function ever changes. The actual colors live in the frontend theme. |
| last_seen_at | DATETIME NULL | Set when the user's last socket disconnects. Shown as "last seen". |
| created_at, updated_at | DATETIME | |

Indexes: the unique indexes on `phone_number` and `username` cover login and search lookups.

### 1.2 `sessions`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER NOT NULL FK → users **ON DELETE CASCADE** | A session can't outlive its user. |
| token_hash | TEXT NOT NULL **UNIQUE** | SHA-256 of a random 32-byte token. The raw token is never stored, so a leaked DB doesn't leak working sessions. |
| expires_at | DATETIME NOT NULL | 30 days. Expiry is checked on each request. |
| last_used_at | DATETIME NOT NULL | |
| created_at | DATETIME | |

Indexes: `UNIQUE(token_hash)` handles the per-request auth lookup. `ix_sessions_user_id` handles "log out all sessions" and the cascade delete.
Why server-side sessions instead of JWT: logout really revokes the token, and the code is easier to explain.

### 1.3 `user_settings` (1:1 with users)
| Column | Type | Notes |
|---|---|---|
| user_id | INTEGER **PK** FK → users ON DELETE CASCADE | Using the FK as the PK enforces 1:1. |
| theme | TEXT NOT NULL DEFAULT 'system' | CHECK IN ('system','light','dark') |
| read_receipts_enabled | BOOLEAN NOT NULL DEFAULT 1 | Privacy setting, same as Signal: if off, the user neither sends nor sees read receipts. |
| typing_indicators_enabled | BOOLEAN NOT NULL DEFAULT 1 | |
| notifications_enabled | BOOLEAN NOT NULL DEFAULT 1 | |
| enter_key_sends | BOOLEAN NOT NULL DEFAULT 1 | Chats setting. |
| created_at, updated_at | DATETIME | |

Why a separate table: settings change on their own schedule, and keeping them apart stops `users` turning into a catch-all. The row is created at signup.

### 1.4 `contacts`
| Column | Type | Notes |
|---|---|---|
| owner_id | INTEGER FK → users ON DELETE CASCADE | Whose address book it is |
| contact_user_id | INTEGER FK → users ON DELETE CASCADE | The person saved |
| nickname | TEXT NULL | Local alias that overrides display_name for the owner only |
| created_at, updated_at | DATETIME | |

Keys: **composite PK (owner_id, contact_user_id)**, so the same contact can't be added twice and no surrogate id is needed. `CHECK(owner_id <> contact_user_id)`.
Index: the PK covers "list my contacts". `ix_contacts_contact_user_id` covers reverse lookups (who has me as a contact, used for presence fan-out).
Why one-directional: contacts are personal, as in Signal. A can save B without B saving A.

### 1.5 `conversations`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| type | TEXT NOT NULL | CHECK IN ('direct','group') |
| name | TEXT NULL | Groups only. A DM's title comes from the other member. |
| description | TEXT NULL | Group description |
| avatar_url | TEXT NULL | Group avatar |
| avatar_color | TEXT NOT NULL | Fallback color for the group's avatar |
| direct_key | TEXT NULL **UNIQUE** | For DMs: `"{min_user_id}:{max_user_id}"`. NULL for groups. SQLite allows many NULLs in a UNIQUE column. The **database** guarantees one DM per pair, even if two "start chat" requests race. |
| created_by | INTEGER NULL FK → users ON DELETE SET NULL | For the "X created the group" message. The conversation survives if the creator is removed. |
| disappearing_seconds | INTEGER NULL | Bonus. NULL means off. |
| last_message_at | DATETIME NULL | **Denormalized.** Updated in the same transaction as each new message. The chat list sorts on it, so we avoid a `MAX()` over messages for every conversation. |
| created_at, updated_at | DATETIME | |

Indexes: `ix_conversations_last_message_at`. `UNIQUE(direct_key)`.
CHECKs: `(type = 'direct') = (direct_key IS NOT NULL)` (only DMs have a key), and `type = 'direct' OR name IS NOT NULL` (groups have a name).
`last_message_at` is the conversation-wide newest message. Each member's chat-list position uses their own last *visible* message (1.6).
Why one table for DMs and groups: messages, receipts and membership work the same for both, so one `messages.conversation_id` FK covers everything. Only the group admin rules differ.

### 1.6 `conversation_members`
| Column | Type | Notes |
|---|---|---|
| conversation_id | INTEGER FK → conversations ON DELETE CASCADE | |
| user_id | INTEGER FK → users ON DELETE CASCADE | |
| role | TEXT NOT NULL DEFAULT 'member' | CHECK IN ('admin','member'). DM members are always 'member'. |
| last_read_message_id | INTEGER NOT NULL DEFAULT 0 (**no FK**) | **Read watermark.** Unread count = *visible* messages (see "Visibility" below) with `id > watermark AND sender_id <> me AND kind = 'text'`. One integer per member, far cheaper than counting receipt rows. Sending a message also moves the sender's watermark to that message. It is deliberately **not** a foreign key. With `ON DELETE SET NULL`, the disappearing-message sweeper deleting the watermark message would reset it to NULL and mark the whole history unread. As a plain integer it keeps its value. Ids are never reused (section 0), so a watermark pointing at a deleted id still splits read from unread correctly. It only moves forward (`max(current, new)`). On **join or re-add**, it is set to the conversation's current latest message id (`MAX(messages.id)`, or 0 if there are none), so a new member doesn't start with a pile of unread messages. |
| history_start_id | INTEGER NOT NULL DEFAULT 0 | Exclusive lower bound on the message ids this member can see. 0 for DM members and founding group members. When someone is added (or re-added), it's set to the latest message id *before* the "member_added" system message, so they see that message and everything after it (see 7.1). |
| history_end_id | INTEGER NULL | Inclusive upper bound. Set to the id of the "member_removed" / "member_left" system message, so the member sees their own removal and nothing after it. NULL while active. |
| is_pinned | BOOLEAN NOT NULL DEFAULT 0 | Per-user chat list preference |
| is_archived | BOOLEAN NOT NULL DEFAULT 0 | Per-user |
| muted_until | DATETIME NULL | Per-user. Controls notifications. |
| joined_at | DATETIME NOT NULL | |
| left_at | DATETIME NULL | **Soft removal.** A removed member keeps old history read-only (up to `history_end_id`) and can't send, as in Signal. Re-adding sets it back to NULL. "Active member" means `left_at IS NULL`. |
| created_at, updated_at | DATETIME | |

Keys: **composite PK (conversation_id, user_id)**. A user is in a conversation at most once, and re-adding is an UPDATE, not a new row.
CHECKs: `(left_at IS NULL) = (history_end_id IS NULL)` and `history_end_id IS NULL OR history_end_id >= history_start_id`.

**Visibility** (`services/message_queries.py: visible_to`). A member sees a message only if:
- `id > history_start_id AND (history_end_id IS NULL OR id <= history_end_id)`, **and**
- it isn't from a user they blocked, sent at or after the block (7.2).

The following are **all** bounded by this rule, never by the raw conversation:
- history and pagination
- the **unread count**
- the **last-message preview**
- **chat-list ordering**: a member's sort key is the `created_at` of their last visible message. A removed member's group stops moving up the list when others post.

`conversations.last_message_at` is only a cheap shortcut for active members with no blocks. Checked by tests: Daniel, removed from "Weekend Trip", has unread = 0, and his preview is his own removal message.

**Re-add rule.** Re-adding is an UPDATE that sets:
- `left_at` and `history_end_id` back to NULL
- `history_start_id` and `last_read_message_id` to the latest message id before the new "member_added" message

So a re-added member does **not** see messages from the gap while they were away, and their history from before is hidden too (one visible range per member, 7.1).
Indexes: the PK covers "members of conversation X". `ix_members_user_id` covers "all conversations of user Y", which is the chat list query.
Why per-user prefs live here: pinned, archived, muted and unread are properties of *my membership*, not of the conversation.

### 1.7 `messages`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | Always increasing, so it's the pagination cursor, the sync cursor and the watermark unit. `sqlite_autoincrement` stops ids being reused after the sweeper or a cascade deletes rows. |
| conversation_id | INTEGER NOT NULL FK → conversations ON DELETE CASCADE | |
| sender_id | INTEGER NULL FK → users ON DELETE SET NULL | NULL renders as "Deleted user". Group history stays intact. |
| kind | TEXT NOT NULL DEFAULT 'text' | CHECK IN ('text','system'). System rows ("Alice added Bob", "You created the group") sit in the timeline like in Signal. |
| body | TEXT NOT NULL | For system rows: a machine event (`member_added`) plus JSON metadata in `system_data`, rendered per viewer ("You" vs a name). |
| system_data | TEXT NULL | JSON, system messages only, e.g. `{"event":"member_added","actor_id":1,"target_ids":[4]}` |
| client_id | TEXT NULL | UUID generated by the sender's client. Used for **idempotent retries** and to match the optimistic bubble with the server's copy. |
| reply_to_id | INTEGER NULL FK → messages ON DELETE SET NULL | Bonus: quoted replies. |
| expires_at | DATETIME NULL | Bonus: disappearing messages. Computed at insert from `disappearing_seconds`. |
| created_at | DATETIME NOT NULL | Server time, which sets the order. |
| deleted_at | DATETIME NULL | "Delete for everyone" leaves a tombstone instead of a hole. |

Keys and constraints: `UNIQUE(sender_id, client_id)`. If a client retries a send after a network blip, the server returns the existing row instead of a duplicate. NULL `client_id`s (system messages) never collide. CHECK `kind = 'system' OR system_data IS NULL`.
Indexes:
- `ix_messages_conversation_id_id (conversation_id, id)`. Serves history pagination (`WHERE conversation_id=? AND id<? ORDER BY id DESC LIMIT 50`), reconnect sync (`id > ?`), the last-message preview, and unread counts. Ids increase with time, so this index also gives time order. We don't need a separate `created_at` index.
- `ix_messages_expires_at` partial `WHERE expires_at IS NOT NULL`. Used by the disappearing-message sweeper.

### 1.8 `message_receipts`
| Column | Type | Notes |
|---|---|---|
| message_id | INTEGER FK → messages ON DELETE CASCADE | |
| user_id | INTEGER FK → users ON DELETE CASCADE | The **recipient** (never the sender) |
| delivered_at | DATETIME NULL | Set when the server pushes the message to one of the recipient's open sockets, or when the recipient next connects or fetches. |
| read_at | DATETIME NULL | Set when the recipient's client reports the message as visible, **only if the reader has read receipts on** (see 7.4). |
| created_at | DATETIME | |

Keys: **composite PK (message_id, user_id)**. One row per recipient per message. Rows are created at send time for every active member except the sender, and only for `kind = 'text'` (system messages have no ticks). CHECK `read_at IS NULL OR delivered_at IS NOT NULL` (read implies delivered).
Indexes: `ix_receipts_user_undelivered (user_id) WHERE delivered_at IS NULL` is a partial index. When a user connects, we find their pending deliveries without scanning delivered rows.
Rows are **not** created for a recipient who has blocked the sender (see 7.2). With zero receipt rows, the status stays `sent`.
Status the sender sees (computed): `sent` if there are no rows or any recipient has no `delivered_at`. `delivered` if all are delivered and any is unread. `read` if all have `read_at`. Groups work the same way, and per-member detail backs the "Message details" screen.
Why both a watermark and receipts: the watermark (1.6) answers "how many unread?" cheaply. Receipts answer "who has read *this* message?". Marking messages read updates both in one transaction.

### 1.9 `reactions` (bonus)
| Column | Type | Notes |
|---|---|---|
| message_id | INTEGER FK → messages ON DELETE CASCADE | |
| user_id | INTEGER FK → users ON DELETE CASCADE | |
| emoji | TEXT NOT NULL | |
| created_at, updated_at | DATETIME | |

Keys: **PK (message_id, user_id)**. Signal allows one reaction per user per message, and reacting again replaces it (upsert).

### 1.10 `attachments` (bonus)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| message_id | INTEGER NULL FK → messages ON DELETE CASCADE | NULL between upload and send. Uploading first lets the composer show a preview. |
| uploader_id | INTEGER NOT NULL FK → users ON DELETE CASCADE | Only the uploader can attach it to a message. |
| file_name, mime_type | TEXT NOT NULL | |
| size_bytes | INTEGER NOT NULL | CHECK ≤ 25 MB |
| storage_path | TEXT NOT NULL | Path on disk under `backend/uploads/`. Files stay out of SQLite to keep the DB small. |
| width, height | INTEGER NULL | Images only. The bubble can reserve space before the image loads, so there's no layout jump. |
| created_at | DATETIME | |

Index: `ix_attachments_message_id`.

### 1.11 `blocks`
| Column | Type | Notes |
|---|---|---|
| blocker_id | INTEGER FK → users ON DELETE CASCADE | The person who blocked |
| blocked_id | INTEGER FK → users ON DELETE CASCADE | The person blocked |
| created_at | DATETIME NOT NULL | Messages from the blocked user sent after this time are hidden from the blocker (see 7.2). |

Keys: **composite PK (blocker_id, blocked_id)**. `CHECK(blocker_id <> blocked_id)`.
Index: the PK covers "my blocked list" and the per-send check "has the recipient blocked me?". `ix_blocks_blocked_id` covers the reverse lookup.
Why a separate table rather than `contacts.is_blocked`: in Signal you can block **anyone**, including a stranger who messaged you. As a flag on `contacts`, blocking a non-contact would force a contact row and make them show up in the contact list. Keeping it separate means being a contact and being blocked don't depend on each other.

### 1.12 Relationships (ER sketch)
```
users 1─* sessions
users 1─1 user_settings
users 1─* contacts (owner) *─1 users (contact)
users 1─* blocks (blocker) *─1 users (blocked)
users *─* conversations   via conversation_members (role, watermark, history_start_id/history_end_id, prefs)
conversations 1─* messages *─1 users (sender)
messages 1─* message_receipts *─1 users (recipient)
messages 1─* reactions, 1─* attachments, 0..1 reply_to → messages
```

## 2. REST API (`/api/v1`)

Conventions: JSON throughout. Errors are `{ "detail": "..." }`. Every endpoint except `/auth/otp/*` and `/health` needs `Authorization: Bearer <token>`. 401 = no or invalid session, 403 = not a member or not an admin, 404 = not found **or not visible to you** (so we don't leak that a resource exists), 409 = conflict, 422 = validation.

### Auth
| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/otp/request` | `{phone_number}` | 202 `{ "sent": true }` (mocked, OTP is always `123456`) |
| POST | `/auth/otp/verify` | `{phone_number, code}` | 200 `{token, user, is_new_user}`. Creates the user and settings on first verify. 400 if the code is wrong. |
| POST | `/auth/logout` | — | 204, deletes the current session |

**Auth details (implemented in phase 2)**
- **Phone numbers:**
  - Normalized by stripping spaces, dashes, brackets and dots, then must be **E.164** (`^\+[1-9]\d{7,14}$`). Otherwise 422.
  - One shared type, `PhoneNumber` in `schemas/common.py`.
  - The frontend builds the number from a country dial code plus the national number, and drops a trunk `0`.
- **Unknown number = registration** (Signal has no separate sign-up):
  - The first verify creates the `users` and `user_settings` rows, with `display_name` NULL. The frontend then shows `/onboarding`.
  - `otp/request` answers 202 for any valid number. `otp/verify`'s `is_new_user` *does* reveal whether a number was registered. That's accepted for the mock and noted in the README.
- **Sessions:**
  - The token is `secrets.token_urlsafe(32)`, returned once. Only its SHA-256 is stored.
  - Fixed **30-day** expiry (`SESSION_TTL_DAYS`).
  - `last_used_at` is refreshed at most once an hour.
- **`get_current_user`:** a Bearer token that's missing, unknown or expired gives 401 with `WWW-Authenticate: Bearer`.
- **Logout:** revokes only the current session.
- **CORS:**
  - Explicit `allow_headers=["Authorization", "Content-Type"]`. A preflight with `Access-Control-Request-Headers: authorization` is tested.
  - `allow_credentials=False`, since there are no cookies.

**Auth token storage: Bearer + `localStorage`**
- **Why not an httpOnly cookie:**
  - **Cross-site:** the frontend (`*.vercel.app`) and the API (`*.up.railway.app`) are different sites. A cookie would need `SameSite=None; Secure` and requests sent with credentials, plus CSRF protection.
  - **Blocked cookies:** browsers increasingly block third-party cookies, so login could silently fail.
  - **No same-origin proxy:** proxying the API through Next.js rewrites would make it same-origin, but Vercel can't proxy WebSockets.
  - **WebSockets:** browsers can't set an `Authorization` header on them, so `/ws?token=` needs the token in JavaScript regardless.
- **The cost:** an XSS bug could read the token. A cookie would only let it make requests while the page is open, not steal the token.
- **Mitigations:**
  - React escapes all output, and user content is never rendered with `dangerouslySetInnerHTML`.
  - Uploads are type-checked and served with `nosniff`.
  - Logout really revokes the token server-side.
  - Only hashes are stored server-side.
  - **Planned for phase 9:** a nonce-based Content-Security-Policy. It needs `proxy.ts`, because Next's inline hydration scripts break a plain `script-src 'self'`.
- **`localStorage`, not `sessionStorage`:** the session must survive reloads and new tabs.
- **Reloads:**
  - The server render and the first client render show a neutral splash.
  - After mount, `store/auth.ts` restores the token and **cached profile** from storage synchronously and shows the right screen at once. `/users/me` revalidates in the background.
  - Any 401 clears the session.
  - Guards (`features/auth/guards.tsx`) are client-side, because `proxy.ts` can't read `localStorage`.

### Users & profile
| Method | Path | Notes |
|---|---|---|
| GET | `/users/me` | Current profile (includes own phone number) |
| PATCH | `/users/me` | `{display_name?, about?, username?}`, PATCH semantics (only sent fields change, unknown fields → 422). Onboarding uses this. `display_name` 1–64 characters after trimming. `about` ≤ 140. `username` lowercased, `^[a-z0-9_.]{3,32}$`. 409 if the username is taken. |
| PUT | `/users/me/avatar` | multipart field `file`. Type detected from the **first bytes** (JPEG/PNG/WebP only, no SVG), so a spoofed `Content-Type` → 415. Max **5 MB**, read in chunks → 413. Saved as `UPLOADS_DIR/avatars/{user_id}-{random}.{ext}` (server-chosen name). The old file is deleted. Returns the profile with `avatar_url = "/media/avatars/…"`. |
| DELETE | `/users/me/avatar` | Back to the initials avatar (file deleted) |

Media: `/media/*` serves `UPLOADS_DIR` through `MediaFiles` (`core/media.py`), a `StaticFiles` subclass that adds `X-Content-Type-Options: nosniff`, which `StaticFiles` doesn't send. Avatars are public to anyone with the (unguessable) URL. Attachments (phase 8) get an authenticated endpoint instead.
| GET | `/users/me/settings` · PATCH `/users/me/settings` | Theme, privacy and notification toggles |
| GET | `/users/search?q=` | Matches an **exact** phone number (separators stripped), a **username prefix** (`@` optional, LIKE wildcards escaped), or a **name among my contacts only** (strangers can't be found by name). Excludes me and users who haven't finished onboarding. Contacts first, max 20. |
| GET | `/users/{id}` | Public profile (`UserPublic`): name as the viewer sees it (nickname > display name > phone), username, about, avatar, `is_contact`. **`phone_number` only if they're my contact.** Presence (`online`, `last_seen_at`) is added in phase 5. |

### Contacts
| Method | Path | Notes |
|---|---|---|
| GET | `/contacts` | My contacts with profile + presence, sorted by name |
| POST | `/contacts` | `{phone_number}` or `{user_id}`, plus `nickname?`. Returns 201, 404 if no such user, 409 if already a contact. |
| PATCH | `/contacts/{user_id}` | `{nickname?}` |
| DELETE | `/contacts/{user_id}` | 204 |

### Blocks
| Method | Path | Notes |
|---|---|---|
| GET | `/blocks` | My blocked users (Privacy → Blocked) |
| PUT | `/blocks/{user_id}` | Block anyone, contact or not. Idempotent, returns 204. 400 if blocking yourself. |
| DELETE | `/blocks/{user_id}` | Unblock, returns 204 |

### Conversations
| Method | Path | Notes |
|---|---|---|
| GET | `/conversations?archived=false` | Chat list (`ConversationSummary`): `id, type, title, avatar_url, avatar_color, other_user_id, is_contact` (DMs), `member_count, is_pinned, is_archived, muted_until, is_active, unread_count, sort_at`, and `last_message {id, kind, text, sender_id, sender_name, created_at, status}`. `status` is only set on my own text messages (capped at `delivered` if my read receipts are off). `sender_name` is null for mine. System-message `text` is worded for the viewer on the server (`services/names.py`: "You created the group.", "Alex Rivera removed you."). Preview, unread count and `sort_at` use only messages visible to me (1.6). Sorted pinned first, then `sort_at` desc. Empty DMs are hidden (7.3). About 3 small indexed queries per conversation, fine at demo scale. **Loading the list also marks all my pending receipts delivered** (`receipt_service.mark_all_delivered`, uses the partial index). That's the "client received it" signal until the WebSocket connect/push paths exist in phase 5. |
| POST | `/conversations/direct` | `{user_id}`, get-or-create via `direct_key`. 201 if created, 200 if it already existed. 400 for yourself, 404 for an unknown user. A race on the UNIQUE key is caught and returns the existing DM. The new DM can be opened right away but only appears in either user's list after the first message. |
| GET | `/conversations/{id}` | Summary fields plus `last_read_message_id` (my watermark, for the unread divider), active members (`name` is "You" for me), `my_role`, and for DMs `groups_in_common` (names of groups both people are active in, for the "Member of …" line). Works for former members too (`is_active: false`). 404 if never a member. |
| PATCH | `/conversations/{id}/preferences` | `{is_pinned?, is_archived?, muted_until?}` (my membership only) |
| POST | `/conversations/{id}/read` | `{up_to_message_id}`, clamped to the newest message visible to me, and the watermark never moves backward. Always sets `delivered_at` on my receipts up to there (a message on screen has been delivered). Sets `read_at` (and, from phase 5, pushes `message.status`) **only if my read receipts are on** (7.4). Returns 204. |

### Messages
| Method | Path | Notes |
|---|---|---|
| GET | `/conversations/{id}/messages?before=<id>&limit=50` | One page of messages **visible to me** (1.6), oldest first, as `{items, next_cursor}`. `next_cursor` is the oldest id in the page (pass it as `before`), or null when nothing is older. `limit` 1–100. Former members can read up to their removal. Items are `MessageOut`: `id, conversation_id, client_id` (mine only), `kind, text` (system text worded for the viewer), `sender_id, sender_name` (null for mine/system), `sender_avatar_color, sender_avatar_url, created_at, status` (mine only, computed for the whole page in one receipts query). |
| GET | `/conversations/{id}/messages?after=<id>` | Messages newer than `after`, oldest first (catch-up after a reconnect), up to `limit`. |
| POST | `/conversations/{id}/messages` | `{client_id, body}`. `body` trimmed, 1–4000 characters, inner newlines kept. `client_id` `^[A-Za-z0-9_\-:]{8,64}$`. One transaction: insert the message, add a receipt row for each active member except me (and anyone who blocked me), update `last_message_at`, move **my** watermark to the new id. Returns 201 with the message (`status: "sent"`). Same `client_id` again → 200 with the original message (also when two retries race: the UNIQUE violation is caught). The same `client_id` in another conversation → 409. Not an active member → 403. `reply_to_id` and `attachment_ids` come with the phase 8 bonuses. |
| DELETE | `/messages/{id}` | Delete for everyone (sender only), sets `deleted_at` |
| GET | `/messages/{id}/receipts` | Per-member delivered/read times ("Message details", sender only) |
| PUT | `/messages/{id}/reaction` | `{emoji}`, upsert (bonus) |
| DELETE | `/messages/{id}/reaction` | Remove my reaction (bonus) |

### Groups (a group is a conversation with `type='group'`, same id)
| Method | Path | Notes |
|---|---|---|
| POST | `/groups` | `{name, member_ids[], description?}`. Creator becomes admin. Returns 201 with the conversation. Adds a system message. |
| PATCH | `/groups/{id}` | `{name?, description?, disappearing_seconds?}` (admin only) |
| PUT | `/groups/{id}/avatar` | multipart (admin only) |
| GET | `/groups/{id}/members` | Active members with role + presence |
| POST | `/groups/{id}/members` | `{user_ids[]}` (admin only) |
| DELETE | `/groups/{id}/members/{user_id}` | Admin removes someone, or anyone removes themselves (= leave). 409 if the last admin tries to leave without promoting someone. |
| PATCH | `/groups/{id}/members/{user_id}` | `{role}` promote/demote (admin only) |

### Attachments (bonus) & misc
| Method | Path | Notes |
|---|---|---|
| POST | `/attachments` | multipart, returns `{id, url, mime_type, width, height}` |
| GET | `/attachments/{id}` | Streams the file. The caller must be a member of the message's conversation. |
| GET | `/health` | `{ "status": "ok" }` |

Layering: routers parse the request, call a service, and return a schema. Services (`auth_service`, `conversation_service`, `message_service`, `group_service`, `receipt_service`) hold all queries and permission checks. They then call `ws.manager` to broadcast **after** the DB commit, so clients never see an event for data that was rolled back.

## 3. WebSocket contract

**Endpoint:** `GET /ws?token=<session token>`. A bad or expired token closes the socket with code **4401**.
**Envelope:** every frame in both directions is `{ "type": string, "payload": object }`. Timestamps are ISO-8601 UTC.
**Manager:** `user_id → set[WebSocket]`, so several tabs work. A user is "online" while the set is non-empty.

### Connection manager (consequences of async SQLAlchemy)
- **Single event loop, no locks.** REST handlers, WS handlers and bot tasks all run as coroutines on the same loop. The manager is a plain `dict[int, set[WebSocket]]`, and register/unregister never `await` between reading and changing it. So it needs no `threading.Lock` or `asyncio.Lock`.
- **Broadcast is a plain `await`.** Services commit, then `await manager.send_to_users(user_ids, event)`. There's no `run_in_threadpool` or `anyio.from_thread` bridging, which a sync ORM would need.
- **A slow socket can't block the others.** Each send is wrapped in `asyncio.wait_for(ws.send_json(...), timeout=5)`, and sends fan out with `asyncio.gather(..., return_exceptions=True)`. A socket that fails or times out is dropped from the manager.
- **One short-lived `AsyncSession` per WS frame**, never one held for the whole connection. That keeps SQLite write locks short and avoids stale data across a long-lived socket.
- **Never block the loop.** No sync file or DB I/O inside handlers (attachment writes use `anyio.Path`, which already ships with Starlette, so no new dependency), and CPU-heavy work (none planned) would go to a thread.
- **Background tasks** (seed bot replies, the disappearing-message sweeper) are `asyncio.create_task(...)` and `asyncio.sleep`, started and cancelled in the FastAPI `lifespan`.

### Client → server
| type | payload | Server behaviour |
|---|---|---|
| `typing.start` | `{conversation_id}` | Checks active membership and the sender's `typing_indicators_enabled`, then relays to the other active members. Clients send it once, then repeat at most every 3 s while the user keeps typing. |
| `typing.stop` | `{conversation_id}` | Relays. The client sends it after 3 s idle, on send, or when the chat loses focus. |
| `ping` | `{}` | Replies `pong`. Keepalive every 25 s so proxies don't drop idle sockets. |

Messages and read receipts are **not** sent over WS. They go through REST (section 2) so they're persisted, validated and idempotent.

### Server → client
**`message.new`**: sent to every active member, including the sender's *other* tabs.
```json
{ "type": "message.new", "payload": {
  "message": { "id": 812, "conversation_id": 7, "client_id": "6f1c…", "sender_id": 3,
               "kind": "text", "body": "hey", "reply_to": null, "attachments": [],
               "created_at": "2026-10-07T15:04:05Z", "status": "sent" },
  "conversation": { "id": 7, "last_message_at": "2026-10-07T15:04:05Z" } } }
```
Server side: right after pushing to a recipient's open socket, it sets that recipient's `delivered_at` and emits `message.status` to the sender. Client side: if `client_id` matches an optimistic bubble, the bubble is replaced. Otherwise the message is appended and the chat list entry is bumped and its unread count increased.

**`message.status`**: sent to the **sender** of the affected messages only.
```json
{ "type": "message.status", "payload": {
  "conversation_id": 7,
  "updates": [ { "message_id": 812, "status": "delivered" },
               { "message_id": 813, "status": "read" } ] } }
```
`status` is the aggregated status for the sender (section 1.8 rules), one of `sent | delivered | read`. It only ever moves forward. The client ignores anything that would move a status backward. It's batched because one `/read` call can cover many messages.

**`typing.start` / `typing.stop`**: relayed to other members.
```json
{ "type": "typing.start", "payload": { "conversation_id": 7, "user_id": 3 } }
```
The client shows "…" in the header and timeline, and in a group, the typist's avatar. It clears on `typing.stop`, on `message.new` from that user, or after a **5 s safety timeout**.

**`presence.update`**: sent to everyone who shares a conversation with the user or has them as a contact.
```json
{ "type": "presence.update", "payload": { "user_id": 3, "online": false, "last_seen_at": "2026-10-07T15:10:00Z" } }
```
Emitted on the first socket connect (online) and when the last socket closes (offline, `last_seen_at` stored).

**`group.updated`**: sent to every active member, **plus** any member just removed, so their UI can switch to read-only.
```json
{ "type": "group.updated", "payload": {
  "conversation_id": 9,
  "change": "members_added",
  "actor_id": 1,
  "target_ids": [4, 5],
  "conversation": { "id": 9, "name": "Weekend Trip", "avatar_url": null,
                    "members": [ { "user_id": 1, "role": "admin" } ] } } }
```
`change` is one of `created | renamed | details_changed | avatar_changed | members_added | member_removed | member_left | role_changed`. The payload includes a full `conversation` snapshot, so clients replace their copy instead of patching it. A matching `kind='system'` message is sent separately as `message.new`.

**`reaction.updated`** (bonus): `{message_id, conversation_id, user_id, emoji | null}`.
**`error`**: `{detail, ref_type?}` for invalid client frames. The socket stays open.

### Connection lifecycle
1. On connect: authenticate, register the socket, broadcast `presence.update` (online), then mark every pending receipt for this user as delivered (partial index, section 1.8) and send `message.status` to the affected senders.
2. Client reconnect: exponential backoff 1 s, 2 s, 4 s … capped at 30 s, with jitter. On reopen it refetches `/conversations` and, for the open chat, `/messages?after=<last id>`.
3. On disconnect: unregister. If it was the last socket, store `last_seen_at` and broadcast offline.

## 4. Frontend pages & component tree

### Routes (Next.js App Router, `src/app/`)
```
/                         → redirect to /chats or /register based on session
/register                 Phone number entry (country code + number)
/verify                   6-digit OTP entry (hint: 123456)
/onboarding               Set display name + avatar (required before the app)
/(app)/layout.tsx         AuthGuard + WebSocketProvider + AppShell
  /chats                  Chat list + empty state ("Welcome to Signal" logo)
  /chats/[conversationId] Chat list + open conversation
  /calls                  Coming Soon placeholder (in the nav rail)
  /stories                Coming Soon placeholder (in the nav rail)
  /settings/[section]     general | appearance | chats | notifications | privacy | linked-devices (coming soon)
```

### Component tree
```
AppShell
├── NavRail                      ☰ menu · Chats · Calls · Stories … · Settings ⚙ (bottom) · profile avatar
├── LeftPane
│   ├── LeftPaneHeader           "Chats" title · ComposeButton (✎) · OverflowMenu (⋯: archived, mark all read)
│   ├── SearchBar + FilterButton (filter: unread only)
│   ├── ConversationList
│   │   └── ConversationListItem   Avatar(+PresenceDot) · title · "You: " preview · time · UnreadBadge | StatusTicks · pinned/muted icons
│   ├── SearchResults            sections: Chats · Contacts · "Find by phone number"
│   ├── ComposePanel             replaces the list: "New group" · "Find by phone number" · ContactPicker
│   └── NewGroupFlow             step 1 MemberPicker (chips) → step 2 GroupNameForm (name + avatar)
├── MainPane
│   ├── EmptyState               Signal logo + "Welcome to Signal"
│   └── ChatView
│       ├── ChatHeader           Avatar · title · subtitle (online / last seen / typing / N members) · video · call (Coming Soon toast) · search · ⋯
│       ├── MessageTimeline      scrolls up for older pages, sticks to bottom when new messages arrive
│       │   ├── ConversationHero card: big avatar, name ›, "No groups in common" / "X and you"
│       │   ├── DateSeparator    "Today" / "Yesterday" / date
│       │   ├── SystemMessage    "You created the group." with icon
│       │   ├── MessageCluster   consecutive messages from the same sender within 3 min
│       │   │   └── MessageBubble  SenderName (groups, colored) · QuotedMessage · body · AttachmentPreview ·
│       │   │                      MessageMeta(time + StatusTicks) · ReactionPills · HoverActions(⋯ reply react)
│       │   └── TypingIndicator  animated dots in an incoming bubble (+ avatar in groups)
│       ├── Composer             EmojiButton · auto-growing textarea "Message" · MicButton/SendButton · ＋ AttachMenu (Photos & videos, File)
│       └── ConversationDetailsPanel (slide-in)
│           ├── profile/group header, edit name (admin), disappearing messages
│           ├── MemberList → MemberRow (role badge, ContextMenu: make admin, remove)
│           ├── AddMembersModal (MemberPicker)
│           └── Leave group / Block contact
├── SettingsView                 SettingsNav + SettingsSection (toggles bound to user_settings)
└── ComingSoon                   shared placeholder for Calls, Stories, Linked devices
```

### Shared UI (`src/components/`)
`Avatar` (image or initials on a deterministic color), `PresenceDot`, `StatusTicks` (sending clock · sent ✓ · delivered ✓✓ · read filled ✓✓), `UnreadBadge`, `Modal`, `Toaster`/`Toast`, `ContextMenu`, `DropdownMenu`, `Button`, `IconButton`, `TextInput`, `Toggle`, `Spinner`, `Chip`.

### State, hooks, lib
- **Stores (Zustand):** `authStore` (user, token), `conversationsStore` (by id + sorted ids), `messagesStore` (per conversation: items, cursor, hasMore, and optimistic messages keyed by `client_id`), `presenceStore`, `typingStore` (conversation → user ids + timeouts), `uiStore` (theme, toasts, open panels).
- **Hooks:** `useWebSocket` (connect, backoff, dispatch to stores), `useTyping` (throttled start/stop), `useReadReceipts` (IntersectionObserver, debounced `POST /read`), `useMessagesPagination`, `usePresence`, `useTheme`.
- **lib:** `api.ts` (typed fetch wrapper, Bearer token, error parsing), `ws.ts` (envelope types as a discriminated union), `format-date.ts` ("Now", "2m", "Yesterday", date separators), `avatar-color.ts`.
- **types:** `User`, `Conversation`, `Message`, `MessageStatus`, `WsEvent` (mirrors the Pydantic schemas).
- **styles:** `theme.css` with all color, font and spacing tokens as CSS variables for light and dark. Tailwind maps to these variables. Components contain no hex values.

## 5. Build phases (in order; each ends with run, test, summary, suggested commit)

| # | Phase | Scope | Done when |
|---|---|---|---|
| 0 | **Scaffolding** | FastAPI app factory, config/env, CORS, `/health`. Next.js + TS strict + Tailwind + Inter. `theme.css` tokens (light/dark). `.env.example` files. | Both servers start. The frontend calls `/health`. |
| 1 | **Schema & seed** | All SQLAlchemy models (section 1) with `SQLITE_TABLE_ARGS`, async engine + SQLite pragmas, `create_all` on startup. `python -m app.seed` (idempotent) and `python -m app.seed --reset` (destructive, manual only). Data is declared in `app/seed_data.py`, and receipts, watermarks and history ranges are *derived* from it. Messages are seeded only into conversations with none yet, so system messages (NULL `client_id`) can't duplicate. Includes the 2 bot users (section 8). | Seed runs twice (and with `--reset`) with identical row counts. pytest covers pragmas, autoincrement, enums, DM uniqueness, `client_id` idempotency, id reuse, cascades/SET NULL, CHECKs, receipts vs watermarks, unread counts, and history bounds. |
| 2 | **Auth & onboarding** | OTP request/verify, sessions, `get_current_user` dependency, logout. Register/Verify/Onboarding pages, auth store, guard. | Log in as a seed user and as a new user. Session survives a reload. pytest auth tests pass. |
| 2b | **Thin deploy (milestone)** | Deploy what exists so far. Backend on a host with a **persistent volume** (Railway volume or Fly.io volume mounted at `/data`, `DATABASE_URL=sqlite+aiosqlite:////data/app.db`). **Seed on boot = the idempotent `python -m app.seed`**: it fills an empty DB completely and changes nothing in an existing one. A reset is allowed only when the `users` table is empty, and **never** as an unconditional `--reset` in the start command, which would wipe real data on every redeploy. Frontend on Vercel. Set `CORS_ORIGINS`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`. No new features. | On the public URLs: `/health` responds, login with a seed phone + `123456` works, the session survives a reload, and data survives a backend redeploy (proves the volume works). This catches CORS, env, HTTPS and volume problems early instead of on the last day. |
| 3 | **Shell, chat list & contacts** | NavRail/LeftPane/MainPane layout, conversation list endpoint (preview, unread, sorting), search, contacts CRUD, compose panel, get-or-create DM, empty state. | Matches the reference screenshots for the list and empty state. Adding a contact and starting a chat works. |
| 4 | **1:1 messaging (REST)** | History pagination, send with `client_id`, optimistic bubbles, clusters, date separators, ConversationHero, composer, `/read` endpoint and watermark. | Messages persist and paginate. Retrying with the same client_id doesn't duplicate. pytest send/read tests pass. |
| 5 | **Real-time** | WS manager + auth, `message.new`, delivery on push/connect, `message.status`, typing, presence, client reconnect + catch-up. Seed bot (section 8). Redeploy to the 2b hosts to confirm `wss://` works. | Two browsers: instant delivery, ✓ → ✓✓ → read, typing within ~300 ms, online/last-seen update, reconnect recovers missed messages. One browser: messaging a bot shows ✓✓ → read → typing → reply. |
| 6 | **Groups** | Create group flow, members panel, add/remove/promote/leave with admin checks, system messages, `group.updated`, per-member receipts + Message details. | Three users in a group with everything in sync. pytest group permission tests pass. |
| 7 | **Signal polish** | Settings pages (bound to `user_settings`), Coming Soon screens, toasts, context menus, hover actions, dark mode toggle, responsive single-pane mobile layout, screenshot diff against `docs/reference/`. | A side-by-side review against the references shows no obvious differences. |
| 8 | **Bonus** (by value) | Reply/quote → reactions → attachments → disappearing messages (sweeper task) → keyboard shortcuts. | Each bonus feature works end to end. |
| 9 | **Ship (final deploy)** | README (setup, architecture, ER/table list, API overview, assumptions, demo login, bot accounts). Final deploy to the same hosts as 2b: `app.db` and `uploads/` on the persistent volume. Boot runs the idempotent seed. If a clean demo dataset is wanted, run `--reset` once **by hand** before submitting (never on boot). Then a smoke test of every core feature on the public URLs. | The public link works with seeded data, logging in with phone + `123456`, and a single-browser demo with a bot works end to end. |

## 6. Assumptions
- One backend process (the in-memory WS manager). Horizontal scaling would need Redis pub/sub.
- "Encryption" appears only as UI notices. There's no cryptography.
- OTP is fixed at `123456`. No SMS is sent.
- Read receipts off: see 7.4.

## 7. Behaviour notes

### 7.1 Do new group members see earlier history?
**No**, which matches Signal. A member added to an existing group gets `history_start_id` = the latest message id just before the "member_added" system message. They see "Alice added you" and everything after it. A **removed or departed** member keeps read-only access up to `history_end_id` (their own removal message). A **re-added** member gets `history_start_id` reset to the latest message id at the re-add, so they **don't see messages from the gap** while they were away. The history from their earlier stint is hidden too. That's a deliberate simplification: a single visible range per member keeps the query to one indexed range. Founding members (`POST /groups`) have `history_start_id = 0`.

### 7.2 Blocking (including non-contacts)
Anyone can be blocked through `PUT /blocks/{user_id}`, from the chat header ⋯ menu or the conversation details panel, whether or not they're a contact. Effects, all enforced in services:
- **Blocked user sends to me:** the send succeeds from their side (201, Signal doesn't reveal blocks). No receipt row is created for me, it isn't pushed to me, and it stays at ✓ `sent` for them forever.
- **My views:** history, the last-message preview and unread counts exclude messages from users I've blocked with `created_at >= blocks.created_at`. Messages from before the block stay visible. This applies to DMs and groups.
- **Me sending to a blocked user in a DM:** 403 "Unblock to send". The composer is replaced by an Unblock banner. In groups I can still send, and they still receive.
- **Ephemeral events:** `typing.*` and `presence.update` from a blocked user are not relayed to the blocker, and the blocker's aren't relayed to them.
- Unblocking deletes the row. Messages sent during the block stay hidden, because they were never delivered.

### 7.3 Do empty DMs appear in the chat list?
**No.** `POST /conversations/direct` creates the row with `last_message_at = NULL`, and the frontend navigates straight to it. The chat list filters out `last_message_at IS NULL`, so a DM shows up in both users' lists only once the first message is sent. That stops "I clicked a contact by accident" clutter, and the recipient doesn't see a conversation that has nothing in it. Groups always appear immediately, because the "created the group" system message sets `last_message_at`. System messages bump `last_message_at`. Unread counts still only count `kind='text'`.

### 7.4 What happens to `read_at` when read receipts are off?
When the **reader** has `read_receipts_enabled = false`, `POST /conversations/{id}/read` still moves their own watermark, so their unread badge clears. But it **does not set `read_at`** and does not emit `message.status`. Nothing is recorded, so turning receipts back on later never reveals past reads. It only affects messages read from then on. `delivered_at` is unaffected, so senders still see ✓✓ delivered.
That user also **doesn't see** others' read status (Signal's two-way rule). The API caps the status of their own outgoing messages at `delivered` in responses, and `message.status` events with `read` are not sent to them.
In groups, a member with receipts off never gets a `read_at`, so the sender's aggregate for that message stays at `delivered`. That's expected, and per-member detail in "Message details" shows who did read it.

## 8. Demo seed bot

Lets a reviewer test real-time behaviour with **one browser**.

- **Who:** two seeded users, e.g. "Maya (bot)" `+15550000001` and "Leo (bot)" `+15550000002`, each with an existing DM with the demo login user. Identified by config, not schema: `DEMO_BOT_PHONES` (comma-separated) and `DEMO_BOTS_ENABLED=true`. That keeps demo logic out of the data model. Tests set `DEMO_BOTS_ENABLED=false`.
- **Where:** `app/services/demo_bot.py`. `message_service` calls `demo_bot.on_message_committed(message)` after commit and broadcast. It returns immediately and schedules `asyncio.create_task(...)`.
- **Trigger:** a `kind='text'` message from a non-bot user in a conversation that has a bot as an active member. Bots never react to bots or system messages.
- **Sequence**, going through the **same services** a real client uses, so every normal event fires:
  1. ~0.4 s: `receipt_service.mark_delivered` → sender sees ✓✓ (bots have no socket, so this stands in for push delivery).
  2. ~1.0 s: `receipt_service.mark_read` (bots have read receipts on) → sender sees read.
  3. DMs only, ~1.3 s: broadcast `typing.start` from the bot. Wait 1.5–3 s, scaled by reply length.
  4. Broadcast `typing.stop`, then `message_service.send_message(bot, conversation, body)` → `message.new` to the user.
  In groups, bots only do steps 1–2, so group ticks move forward. They don't reply, which would get noisy.
- **Replies:** a canned list chosen round-robin per conversation, plus a few keyword responses ("hi"/"hello" → greeting, "?" → "Good question 🤔"). No LLM, no external calls.
- **Debounce:** one pending task per (bot, conversation), held in a dict. A new user message cancels and restarts it, so a burst of 3 messages gets 1 reply.
- **Presence:** bot ids always report `online: true` in presence lookups, so the header shows "Online".
- **Lifecycle:** pending tasks are cancelled in the FastAPI `lifespan` shutdown. Exceptions are logged and never reach the user's request.

