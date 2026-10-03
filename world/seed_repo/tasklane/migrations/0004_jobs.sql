-- Background job queue (see ADR-0001). Payload is a JSON object.

CREATE TABLE jobs (
    id         INTEGER PRIMARY KEY,
    kind       TEXT    NOT NULL,
    payload    TEXT    NOT NULL DEFAULT '{}',
    status     TEXT    NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending', 'running', 'done', 'dead')),
    attempts   INTEGER NOT NULL DEFAULT 0,
    run_at     TEXT    NOT NULL,
    last_error TEXT,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);

CREATE INDEX jobs_status_run_at ON jobs(status, run_at);
