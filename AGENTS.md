# AGENTS.md

`squads` — a Claude Code plugin of skills for multi-agent planning, review, and TDD workflows. No build, no package manager; the repo is markdown skills plus notes.

The skills under `skills/` are the source of truth for their own behavior — read a skill's `SKILL.md` before changing it; don't restate skill behavior here.

When two rules conflict, the most specific written instruction wins: an explicit user instruction beats this file, and this file beats a skill's `SKILL.md`.
