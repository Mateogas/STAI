# Domain Docs

This is a single-context repository. Engineering skills should read the root
`CONTEXT.md` before naming domain concepts and consult relevant decisions under
`docs/adr/` before changing architecture.

## Consumer rules

- Use the glossary's canonical vocabulary in issue titles, specifications,
  tests, and implementation notes.
- Do not add implementation details to `CONTEXT.md`; it defines the product's
  ubiquitous language only.
- Create ADRs only for decisions that are hard to reverse, surprising without
  context, and the result of a real trade-off.
- Surface conflicts with an existing ADR instead of silently overriding it.
