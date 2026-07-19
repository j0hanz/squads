---
name: using-squads
description: Router preamble injected by the session-start hook — routes every incoming task to dispatch-agents for triage and workflow selection. Never invoked directly.
user-invocable: false
disable-model-invocation: true
---

# using-squads

Route every incoming task or user request to [dispatch-agents](../dispatch-agents/SKILL.md); its Step 0 Triage classifies the request (first match wins) and picks the workflow + fleet shape. Skip only for pure conversation or a one-shot edit answerable direct.
