-- Speed up the per-project task list (ordered by creation time).
CREATE INDEX IF NOT EXISTS idx_tasks_project_created
    ON tasks (project_id, created_at, id);
