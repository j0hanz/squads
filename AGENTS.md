# AGENTS.md

`squads` is a Claude Code plugin: markdown skills for collaborative software-development workflows — brainstorming, planning, dispatch, TDD, debugging, and code review. There is no build step and no runtime; the repo is skills plus one Node hook.

Skills under `skills/` are the source of truth for their own behavior. Read a skill's `SKILL.md` before changing it, and don't restate skill behavior here — that duplicates and rots.

When two rules conflict, the most specific written instruction wins: an explicit user instruction beats this file, and this file beats a skill's `SKILL.md`.