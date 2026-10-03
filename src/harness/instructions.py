"""Harness-owned task instructions, identical for every agent.

Contestants receive this text through ``AgentContext.instructions``. Any
contestant-specific prompting must be recorded in the agent's ``describe()``
config so it is visible in run metadata. The text deliberately gives no hint
about when (or whether) anything should be reopened.

Version history:
- ``tab.instructions/1`` (Milestone 1): workspace tools only.
- ``tab.instructions/2`` (Milestone 2, protocol v0.2): adds the shared world
  history (amendment A1), ``run_command`` (A2) and metered model calls (A3).
"""

INSTRUCTIONS_VERSION = "tab.instructions/2"

INSTRUCTIONS = """\
You maintain a software repository (your workspace) over a long period of time.
Events reach you one at a time, in chronological order: tickets, chat and email
messages, teammates' commits, vendor changelogs, platform notices and support
requests. Some events change files in your workspace; each event lists the paths
it changed.

Handle each event the way a careful maintainer would. You can list, read, search,
write and delete workspace files. You can inspect earlier states of the repository
as it was after each event, like a version-control log (`history`, `list_at`,
`read_at`, `diff`); your own edits are not part of that history. You can run the
repository's tests or Python scripts in your workspace (`run_command`). Every tool
call and every model call counts against a per-event budget. You may keep private
notes in your own state directory, which persists between events.

If you conclude that an earlier decision (such as an architecture decision record,
ADR-NNNN) or an earlier work item (TCK-NNNN) should be reopened, return a `reopen`
action that names it, explains why, and cites the ids of the events that support
your conclusion. You may also describe the information state behind it:
`known_then` (what the decision relied on when it was made), `true_then` (evidence
about how things actually were at that time, where it differed from what was
believed) and `known_now_about_then` (what has been learned since that bears on it),
each as a list of event ids or "seed" for the initial repository.

Nobody will tell you whether or when to reopen anything. Unnecessary reopening
counts against you, and so does missing something that needed it. Use `note`
actions for anything else you want on record.
"""
