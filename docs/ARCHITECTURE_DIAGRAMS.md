# AISHA Architecture Diagrams

Use these Mermaid diagrams in the technical write-up, module checklist, or
presentation deck. They describe the current implemented prototype, not future
production integrations.

AISHA is an educational capstone prototype for a fictionalized BDO onboarding
story. It is not affiliated with, endorsed by, or representative of BDO
Unibank.

## System Architecture

```mermaid
flowchart LR
    subgraph Inputs["Input knowledge and state"]
        HRDocs["Fictionalized onboarding docs<br/>data/hr_docs/*.md"]
        SeedData["Employee, plan, org seed data<br/>data/*.json"]
        ChatMemory["Persisted chat memory<br/>SQLite chat_messages"]
        PulseHistory["Pulse history and escalations<br/>SQLite state"]
        UserMsg["New-hire or API message"]
        SimDate["Simulated date<br/>demo clock"]
    end

    subgraph Processing["Local-first agentic AI stack"]
        Ingestion["ingestion.py<br/>load markdown, parse metadata, chunk"]
        Chroma["Chroma vector store<br/>Ollama embeddings<br/>nomic-embed-text"]
        GuardrailLLM["Input guardrail classifier<br/>ChatOllama qwen2.5:3b-instruct"]
        Agent["ReAct agent<br/>LangChain/LangGraph create_agent<br/>ChatOllama llama3.1:8b"]
        Tools["Agent tools<br/>search_knowledge_base<br/>get_my_plan<br/>complete_task<br/>find_person<br/>escalate_to_hr"]
        Repo["state.py Repo<br/>SQLite connection-per-op"]
        OutputGuardrails["Output guardrails<br/>citation enforcement<br/>PII redaction"]
        Observability["observability.py<br/>privacy-preserving JSONL run log"]
    end

    subgraph Outputs["Supported capabilities"]
        GroundedAnswers["Grounded onboarding and policy answers<br/>with [source: filename.md] citations"]
        PlanSupport["Personal ramp plan reading<br/>and task completion"]
        PeopleRouting["Human-owner routing<br/>manager, buddy, IT, payroll, benefits, compliance"]
        Escalations["People Experience escalation tickets"]
        PulseSignals["Pulse trends and HR support signals<br/>without raw private chat transcripts by default"]
        UIAPI["Streamlit chat and HR dashboard<br/>FastAPI /health and /chat"]
    end

    HRDocs --> Ingestion --> Chroma
    SeedData --> Repo
    ChatMemory --> Repo
    PulseHistory --> Repo
    UserMsg --> GuardrailLLM
    SimDate --> Agent
    GuardrailLLM --> Agent
    Chroma --> Tools
    Repo --> Tools
    Agent <--> Tools
    Agent --> OutputGuardrails
    Tools --> Observability
    OutputGuardrails --> Observability
    OutputGuardrails --> GroundedAnswers
    Tools --> PlanSupport
    Tools --> PeopleRouting
    Tools --> Escalations
    Repo --> PulseSignals
    GroundedAnswers --> UIAPI
    PlanSupport --> UIAPI
    PeopleRouting --> UIAPI
    Escalations --> UIAPI
    PulseSignals --> UIAPI
```

### What This Shows

| Layer | Implemented modules | Module checklist evidence |
|---|---|---|
| Knowledge input | `data/hr_docs/*.md`, `data/*.json`, SQLite state | RAG, memory, state |
| Retrieval processing | `ingestion.py`, `retriever.py`, Chroma, Ollama embeddings | RAG with citations |
| Agent reasoning | `agent.py`, ChatOllama, LangChain/LangGraph ReAct loop | Prompt engineering, ReAct agent |
| Tools | `tools.py` internal tools over KB, plan, org, escalation state | Tool use, disambiguation |
| Guardrails | `guardrails.py`, pulse JSON parsing in `pulse.py` | Structured outputs, guardrails |
| Surfaces | `app.py`, `api.py`, `service.py` | Chat UI, REST API |
| Monitoring | `observability.py`, `data/observability.jsonl` | Basic LLMOps monitoring |

## Agentic AI Turn Flow

```mermaid
flowchart TD
    Start["User sends message<br/>Streamlit chat or POST /chat"] --> SaveUser["Persist user turn<br/>SQLite chat memory"]
    SaveUser --> PulseCheck{"Is this a pending<br/>pulse check-in reply?"}

    PulseCheck -- Yes --> ScorePulse["classify_pulse<br/>structured JSON sentiment, concerns, summary"]
    ScorePulse --> StorePulse["Store pulse in SQLite"]
    StorePulse --> AgentStart["Continue to agent response<br/>with empathy and next step"]

    PulseCheck -- No --> InputGuardrail["classify_input<br/>on_topic / off_topic / injection"]
    InputGuardrail --> Allowed{"Allowed?"}
    Allowed -- No --> Refusal["Return scoped refusal<br/>no agent/tool call"]
    Refusal --> LogRefusal["Log turn metadata<br/>no message text"]

    Allowed -- Yes --> AgentStart
    AgentStart --> BuildAgent["Build per-turn agent<br/>persona, role, simulated date, recent history"]
    BuildAgent --> Intent["LLM infers intent from message + system prompt"]

    Intent --> NeedPolicy{"Needs company fact,<br/>policy, benefits, payroll,<br/>IT, branch logistics,<br/>compliance, or docs?"}
    NeedPolicy -- Yes --> SearchTool["search_knowledge_base"]
    SearchTool --> Retrieval{"Relevant chunks found?"}
    Retrieval -- Yes --> CiteAnswer["Answer from retrieved chunks<br/>must cite [source: file]"]
    Retrieval -- No --> HandbookFallback["Say handbook does not cover it<br/>offer People Experience escalation"]

    Intent --> NeedPlan{"Asks what is next,<br/>progress, tasks, or Day 30 readiness?"}
    NeedPlan -- Yes --> PlanTool["get_my_plan"]

    Intent --> CompleteIntent{"Asks to mark<br/>a task done?"}
    CompleteIntent -- Yes --> MatchTask["find_task_matches<br/>deterministic scoring"]
    MatchTask --> Ambiguous{"Multiple open task<br/>matches within margin?"}
    Ambiguous -- Yes --> Clarify["Do not mutate state<br/>ask which task id/title"]
    Ambiguous -- No --> CompleteTool["complete_task<br/>update SQLite plan state"]

    Intent --> PersonIntent{"Asks who handles<br/>a topic or needs an owner?"}
    PersonIntent -- Yes --> PersonTool["find_person<br/>org-directory routing"]
    PersonTool --> PersonFound{"Person found?"}
    PersonFound -- No --> PersonFallback["Offer escalation"]
    PersonFound -- Yes --> OwnerAnswer["Suggest contact and intro"]

    Intent --> SeriousOrHuman{"Human support requested,<br/>handbook gap, sensitive/serious blocker?"}
    SeriousOrHuman -- Yes --> EscalateTool["escalate_to_hr<br/>create People Experience ticket"]

    CiteAnswer --> Capture["RunCapture records<br/>tools, sources, escalation id, plan changes"]
    HandbookFallback --> Capture
    PlanTool --> Capture
    Clarify --> Capture
    CompleteTool --> Capture
    OwnerAnswer --> Capture
    PersonFallback --> Capture
    EscalateTool --> Capture

    Capture --> OutputGuardrails["apply_output_guardrails<br/>enforce citations if KB searched<br/>redact number-shaped PII"]
    OutputGuardrails --> PersistAnswer["Persist assistant answer<br/>with source metadata"]
    PersistAnswer --> Render["Render answer, sources,<br/>plan refresh, escalation toast"]
    Render --> LogTurn["Log privacy-preserving run record<br/>latency, estimated tokens, tools, sources, errors"]
```

### Trigger Rules In Plain English

- **Input guardrail triggers before the agent** for every normal chat message.
  Off-topic and prompt-injection messages receive a refusal without tool use.
- **Pulse check-in replies bypass the topic classifier** because they are
  expected to be emotional or broad work reflections. They are scored by
  `pulse.classify_pulse`, stored, then the agent can respond supportively.
- **RAG is required** whenever the answer makes factual claims about company
  policy, benefits, pay, IT, branch logistics, compliance learning, or handbook
  content.
- **Plan tools trigger** when the user asks what to do next, asks about Day 30
  readiness, checks progress, or asks to complete a task.
- **Disambiguation blocks mutation** when a fuzzy task request matches multiple
  open tasks too closely. AISHA asks one clarifying question instead of marking
  the wrong item complete.
- **People routing triggers** when the user asks who handles a blocker, system,
  process, manager/buddy touchpoint, or workplace topic.
- **Escalation triggers** when the handbook has no answer, the user explicitly
  asks for human help, or the issue sounds sensitive or serious.
- **Output guardrails always run after the agent**. If the KB was searched but
  the model forgot citations, citations are appended from retrieved sources; if
  no sources exist, AISHA falls back to a handbook-gap answer.
- **Observability logs metadata only**: route, models, latency, estimated token
  counts, guardrail category, tools used, sources, escalation id, plan changes,
  and errors. It deliberately does not log raw chat text.

## Slide-Friendly Short Version

```mermaid
flowchart LR
    KB["Knowledge bases<br/>HR docs, employee state,<br/>plan, org directory, pulse history"] --> Stack["AISHA stack<br/>Ollama + Chroma RAG<br/>LangChain ReAct agent<br/>SQLite tools + guardrails"]
    Stack --> Caps["Capabilities<br/>cited answers, task updates,<br/>people routing, escalations,<br/>pulse support signals, HR dashboard"]
```

One-line speaker note:

> AISHA is agentic because it does not only answer questions; it retrieves
> grounded context, reads and updates ramp state, routes to human owners,
> initiates pulse check-ins, escalates gaps, and logs privacy-preserving
> operational signals.
