# Production Response-Time Optimization Note

## Status

This is a design note, not an approved implementation decision. Production
stage timings must be collected before changing the live turn pipeline.

## Current bottleneck hypothesis

The main response-time bottleneck is likely sequential Ollama inference rather
than SQLite persistence, Streamlit rendering, or deterministic policy
validation. An ordinary supported grounded turn can currently require:

1. one Qwen input-classifier generation;
2. two or more Llama ReAct generations around tool execution;
3. one or more Nomic embedding calls for handbook retrieval;
4. one Llama typed-plan generation; and
5. one Llama response-type generation.

More complex turns can consume up to six ReAct model calls and additional
structured-output repair calls. The 90-second request timeout applies to each
model request rather than to the complete user turn. Model loading or swapping
among Qwen, Llama, and Nomic may further increase latency when the production
host cannot keep all three resident.

Current telemetry defines top-level and retrieval timing fields but is not
wired into the Streamlit/API policy-turn path with classifier, ReAct-round,
embedding, finalizer, and model-load breakdowns. The bottleneck therefore
remains a strong code-level hypothesis rather than a production measurement.

## Side-by-side options

| Measure | Current pipeline | Safe optimization | Balanced redesign (recommended) |
|---|---|---|---|
| Ordinary turn | About 5–6 model generations and 1–2 embeddings | Same generation count, one embedding, less loading and setup | About 3–4 generations and one embedding |
| Expected latency change | Baseline | Approximately 15–35% faster | Approximately 35–55% faster |
| Expected effectiveness risk | Known current behavior | Near zero if behavioral contracts remain unchanged | Estimated 0–2 percentage points, concentrated in ambiguous multi-step turns |
| Implementation time | None | 1–2 working days | 3–5 working days including regression and production validation |
| Main changes | None | Stage timings, model residency, cached readiness/Chroma adapters, exact-ID retrieval | Safe work plus merged finalizers and a two-round normal ReAct path with one optional query-revision round |

All percentages are engineering estimates. The existing frozen benchmark is a
deterministic contract benchmark and does not measure live Ollama response
quality or production latency.

## Recommended design

Preserve the public `AishaService.send_message()` and
`PolicyTurnEngine.handle_turn()` interfaces and deterministic safety authority.
Deepen the internal turn and retrieval implementations so that an ordinary
turn follows:

`classifier -> ReAct plan/tool request -> one retrieval -> ReAct typed synthesis -> deterministic validation/persistence`

The recommended changes are:

1. Add privacy-safe production timings for classification, availability
   probes, every ReAct round, embedding/retrieval, finalization, deterministic
   validation, and persistence.
2. Cache readiness results briefly instead of calling `/api/tags` twice per
   supported turn.
3. Cache the Chroma store and embedding adapter instead of recreating them per
   search.
4. Resolve exact policy IDs through an in-memory map without an embedding call.
5. Prevent redundant `search_handbook` and `read_policy_bundle` retrieval for
   the same policy goal.
6. Merge the typed plan and response-type finalizers into one small schema.
7. Make two ReAct rounds the normal path and permit one additional round only
   when retrieval genuinely requires query revision.
8. Reduce repeated conversational context only after production token metrics
   prove that the structured turn context is sufficient.
9. Keep required models resident when production RAM/VRAM allows it. Benchmark
   a smaller finalizer before enabling it because model swapping can erase its
   inference advantage.
10. Show privacy-safe UI progress stages, but never stream unvalidated policy
    claims.

## Effectiveness gate

Do not release the balanced redesign unless all of the following pass:

- no new safety-critical failure;
- the complete Python test suite;
- the frozen 60-case benchmark and its existing thresholds;
- the six-turn production dialogue regression;
- a live side-by-side evaluation using representative questions from all three
  supported topics; and
- a rollback threshold of no more than a two-percentage-point live
  effectiveness decrease.

Grounding, citation identity, applicability, privacy, consent, and persistence
remain deterministic and must not be weakened for latency.

## Resource and credential impact

AISHA runtime inference remains local through Ollama. These changes require no
new OpenAI API key, paid inference API, or external service credential. Work on
the production deployment does require authorized host access, permission to
inspect Ollama and application metrics, and permission to rebuild or restart
the application. Development through Codex consumes the user's Codex allowance,
whose remaining balance is not visible from the repository or this task.
