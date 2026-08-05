-- Meeting App — core schema (SQLite, tables only, no seed data)

PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    birth_date    TEXT NOT NULL,
    gender        TEXT,
    bio           TEXT,
    city          TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE photos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_primary  INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE swipes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    swiper_id   INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    swiped_id   INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    is_like     INTEGER NOT NULL CHECK (is_like IN (0, 1)),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (swiper_id, swiped_id),
    CHECK (swiper_id <> swiped_id)
);

CREATE TABLE matches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user1_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    user2_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    matched_at  TEXT NOT NULL DEFAULT (datetime('now')),
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    CHECK (user1_id < user2_id),
    UNIQUE (user1_id, user2_id)
);

CREATE TABLE messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches (id) ON DELETE CASCADE,
    sender_id   INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    body        TEXT NOT NULL,
    sent_at     TEXT NOT NULL DEFAULT (datetime('now')),
    read_at     TEXT
);

CREATE TABLE preferences (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    gender_preference   TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_photos_user_id ON photos (user_id);
CREATE INDEX idx_swipes_swiper_id ON swipes (swiper_id);
CREATE INDEX idx_swipes_swiped_id ON swipes (swiped_id);
CREATE INDEX idx_matches_user1_id ON matches (user1_id);
CREATE INDEX idx_matches_user2_id ON matches (user2_id);
CREATE INDEX idx_messages_match_id ON messages (match_id);
