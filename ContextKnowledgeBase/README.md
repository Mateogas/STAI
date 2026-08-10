# AISHA Context Knowledge Base

This folder is the current handoff source of truth for the AISHA v1.0 educational capstone. AISHA supports exactly three onboarding topics—Payroll, Resource Access, and HR Policies—for the fictional Hire Alyssa Reyes. It is not affiliated with or endorsed by BDO Unibank and uses no real employee data.

Start with `ContextCatalog.md`, then read only the route-specific files it names. The final issue decisions and closed child-ticket resolutions are reflected here; historical broad-assistant ideas are not current requirements.

Core files:

- `AISHAStorySpine.md`: narrative, boundaries, and canonical journeys.
- `ProjectSynopsis.md`: product and architecture overview.
- `ProjectState.md`: implemented state and remaining limits.
- `ImplementationPlan.md`: completed dependency-ordered slices.
- `ModuleChecklist.md`: canonical module acceptance matrix.
- `UIUXBrief.md`: current Streamlit experience contract.
- `OpenQuestions.md`: settled-decision register.

Canonical engineering evidence lives in `README.md`, `docs/`, `handbook/`, `evaluation/`, production code, and tests. Run `uv run python -m stai.acceptance` for the integrated acceptance report.
