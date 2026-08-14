---
status: accepted
---

# Use bounded Agent Plans and mediate HR cases through AISHA

AISHA resolves each turn into a typed Agent Plan whose allowed actions are discovery, clarification, policy retrieval, case-status reading, or preparation of an evidence-gated HR offer; deterministic executors retain authority over validation, consent, and writes. HR does not join a Hire thread by default: it works in a Mediated Case, asks for missing facts through structured Case Information Requests that AISHA relays, and supplies a typed Case Resolution that AISHA communicates. Direct human conversation is an exceptional mode that requires a separate HR offer and Hire consent. This preserves agentic observe-plan-act-verify behavior and continuity without reducing AISHA to email or allowing the model to mutate authoritative state.
