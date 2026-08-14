# CPU Certificate Agent and Judge — TDD Evidence

Date: 2026-08-15

Scope: Windows-safe persistence, bounded Certificate Agent orchestration, safe API/UI trace, CPU-only Ollama construction, local Tesseract selection, and the privacy-safe LLM-as-judge harness.

## Red evidence

The work began from focused failing tests:

- `tests/test_platform_lock.py` failed during collection because `stai.state` imported POSIX-only `fcntl` on Windows.
- `tests/test_certificate_agent.py` failed because `stai.certificate_agent` did not exist.
- `tests/test_llm_judge.py` failed because `stai.llm_judge` did not exist.
- `tests/test_cpu_ollama.py` failed because there was no shared Ollama construction seam and no `ollama_num_gpu` setting.
- `tests/test_medical_ocr.py` proved an explicit Windows Tesseract command was ignored.
- A live Qwen response exposed a second schema shape (`scores` as a closed nested object); a focused parser test reproduced that failure before the fix.
- Installing the real local models exposed two additional integration failures: ordinary Streamlit tests accidentally used Ollama, and a pending consent action could be overridden by an `off_topic` classifier verdict. Both were reproduced with focused tests before correction.

## Green evidence

- Platform locking now uses `msvcrt` on Windows and `fcntl` on POSIX; migration/cutover tests close handles explicitly.
- Every chat and embedding client is created through `stai.ollama_runtime` with `num_gpu=0`.
- Certificate Agent tests verify the exact bounded action sequence, deterministic degradation, safe persistence, and absence of filenames, OCR text, extracted values, and private reasoning.
- OCR tests verify the configured local Tesseract binary; a generated PNG was successfully read by the real installed runtime.
- Judge tests verify strict typed parsing, objective contract checks, case-specific reference criteria, fixed evaluation controls, private-key rejection before model invocation, and aggregate-only persisted output.
- The ordinary suite is explicitly isolated from live models even when Ollama is installed; contextual consent bypasses only a mistaken `off_topic` verdict, while injection blocking remains authoritative.
- The final complete project suite passed (252 tests), and the separate relay suite passed (6 tests).

## Refactor and runtime proof

Duplicate Ollama constructors were replaced by one CPU-only module used by the policy agent, guardrail, certificate agent, judge, ingestion, and retrieval. The active handbook index was rebuilt with 108 records and 768-dimensional local embeddings. `/api/v1/health` returned `ready` for SQLite, the knowledge index, the agent model, and the guardrail model. `ollama ps` reported the loaded embedding and 7B judge models as `100% CPU`. A real synthetic certificate completed through the live ReAct Certificate Agent with the four safe public actions. The final six-case local judge report passed at 1.0 pass rate with zero hard failures.

No checkpoint commits were created because the repository owner requested an uncommitted handoff for their own review, commit, and push.
