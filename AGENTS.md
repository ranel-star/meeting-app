# Meeting App — Agent Context

## Project

**Meeting App** is a dating / partner-matching application. Users create profiles, browse other users, swipe (like or pass), get matched on mutual interest, and message each other.

## Data model

Five core tables (see `db/schema.sql`):

| Table | Purpose |
|-------|---------|
| `users` | Accounts and profile basics |
| `photos` | Profile photos per user |
| `swipes` | Like/pass actions between users |
| `matches` | Mutual likes between two users |
| `messages` | Chat messages within a match |

## Conventions

- SQL schema lives in `db/schema.sql`; no seed/fake data unless explicitly requested.
- Max 10 columns per table unless the user asks to extend the model.
- Prefer simple, readable schema over premature normalization.
- Do not commit secrets (`.env`, API keys, credentials).

## Stack

- **Database:** SQLite (`db/schema.sql`)
- Enable foreign keys in app code or per connection: `PRAGMA foreign_keys = ON;`
- Dates and timestamps are stored as `TEXT` (ISO-8601, e.g. `YYYY-MM-DD`, `datetime('now')`)
- Booleans are `INTEGER` with `0` / `1`
