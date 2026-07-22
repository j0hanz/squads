# AGENTS.md

`CLAUDE.md` and `GEMINI.md` are pointers to this file — put shared instructions here, not in them.

Skills under `skills/` own their own behavior. Read a skill's `SKILL.md` before changing it, and don't restate skill behavior here or in the README — a second copy drifts.

`skills/` holds one directory per shipped plugin skill and nothing else. Repo-local skills (`release-plugin`) live in `.claude/skills/` and never move into `skills/`.
