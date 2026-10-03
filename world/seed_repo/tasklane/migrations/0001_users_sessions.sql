-- Users and login sessions.

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

-- Only a SHA-256 digest of each session token is stored, so a copy of the
-- database cannot be used to hijack live sessions.
CREATE TABLE sessions (
    token_sha256 TEXT    PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    created_at   TEXT,
    expires_at   TEXT    NOT NULL
);

CREATE INDEX sessions_user_id ON sessions(user_id);
