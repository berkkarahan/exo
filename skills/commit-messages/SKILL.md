---
name: commit-messages
description: Write wEXO commit messages following the repository's imperative, prefixed format. Use when creating a git commit, writing a commit message, or when the user asks how commits should be formatted.
---

# Commit Messages

Format is defined in `RULES.md`. Follow it exactly.

## Rules

- Use the **imperative mood** in the subject line (e.g. "Add", not "Added").
- Prefix the subject with a change type:
  - `documentation` - documentation changes.
  - `feature` - a new feature.
  - `refactor` - a change that neither fixes a bug nor adds a feature.
  - `bugfix` - a bug fix.
  - `chore` - routine tasks, maintenance, or tooling changes.
  - `test` - adding or correcting tests.
- Keep the subject line to **50 characters or less**.
- **Capitalize** the subject line.
- Do **not** end the subject line with a period.
- Separate the subject from the body with a blank line.

## Example

```
feature: Add Zenoh peer discovery backoff
```

```
bugfix: Correct election timeout on resume

The bully algorithm could restart an election while a master was
still alive after a node resumed from an older event log.
```
