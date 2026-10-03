-- Accounts (the billing unit), their members, projects and tasks.

CREATE TABLE accounts (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    owner_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at    TEXT    NOT NULL
);

CREATE TABLE memberships (
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    user_id    INTEGER NOT NULL REFERENCES users(id),
    role       TEXT    NOT NULL,
    PRIMARY KEY (account_id, user_id)
);

CREATE TABLE projects (
    id         INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    name       TEXT    NOT NULL,
    created_at TEXT    NOT NULL
);

CREATE INDEX projects_account_id ON projects(account_id);

CREATE TABLE tasks (
    id         INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    title      TEXT    NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);

CREATE INDEX tasks_project_id ON tasks(project_id);
