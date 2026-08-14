# Issue tracker: GitHub

Issues and specs for this repository live as GitHub issues. Use the `gh` CLI
for tracker operations and infer `Mateogas/STAI` from the repository remote.

## Conventions

- Create an issue with `gh issue create --title "..." --body "..."`.
- Read an issue with `gh issue view <number> --comments` and include labels.
- List issues with `gh issue list --state open --json number,title,body,labels,comments`.
- Comment, label, assign, and close issues with the corresponding `gh issue`
  commands.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Wayfinding operations

- **Map:** one issue labelled `wayfinder:map`, containing Destination, Notes,
  Decisions so far, Not yet specified, and Out of scope.
- **Child ticket:** a GitHub sub-issue of the map, labelled
  `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or
  `wayfinder:task`. If sub-issues are unavailable, link it from a task list in
  the map and begin its body with `Part of #<map>`.
- **Blocking:** use GitHub's native issue dependencies. If unavailable, put a
  `Blocked by: #<n>, #<n>` line at the top of the child body.
- **Frontier:** open map children that have no open blocker and no assignee,
  ordered as listed by the map.
- **Claim:** assign the ticket to the driving developer before any work.
- **Resolve:** post the answer as a resolution comment, close the ticket, then
  append a one-line linked gist to the map's Decisions so far.
