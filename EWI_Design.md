# EWI Agent System – Updated Technical Design

## 1. Project Overview

The Early Warning Indicators (EWI) system is a 4-agent LangGraph application for monitoring loan/KPI risk and supporting analyst decision-making.

The system:
- analyzes loan KPI data,
- explains KPI signals,
- calculates an overall risk score,
- recommends policy/playbook-grounded actions, and
- provides a conversational interface for follow-up questions.

The updated architecture uses a **router-based LangGraph workflow** instead of a fixed sequential chain.

## 2. Objectives

The system should:

1. Identify and explain early warning signals for loans.
2. Calculate an explainable weighted composite risk score.
3. Classify loans into Low, Medium, High, or Critical risk.
4. Recommend policy/playbook-grounded actions.
5. Allow analysts to ask natural-language questions about loan risk and history.
6. Avoid unnecessary agent and LLM execution.
7. Reuse outputs already available in application state/session state.
8. Keep the analyst as the final decision-maker.

## 3. Architecture

### Previous Architecture

```text
START → Agent 1 → Agent 2 → Agent 3 → Agent 4 → END
```

This forced every request through the same sequence.

### Updated Architecture

```text
                    +------------------+
                    |      START       |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |      ROUTER      |
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
          v                  v                  v
   +-------------+    +-------------+    +-------------+
   |   Agent 1   |    |   Agent 2   |    |   Agent 3   |
   | Smart       |    | Risk        |    | Recommended |
   | Insights    |    | Summary     |    | Actions     |
   +------+------+    +------+------+    +------+------+
          |                  |                  |
          +------------------+------------------+
                             |
                             v
                    +------------------+
                    |     Agent 4      |
                    |      Chat        |
                    +--------+---------+
                             |
                             v
                            END
```

The diagram shows the logical architecture. At runtime, the router follows conditional paths and does not execute every agent automatically.

## 4. Core Design Principle

> **Dependency does not mean mandatory re-execution.**

Agent 3 requires Agent 1 and Agent 2 information, but if those outputs already exist in shared state/session state, Agent 1 and Agent 2 do not need to run again.

The router checks:
- what the user requested,
- which outputs already exist,
- which dependencies are missing, and
- which agent is actually required.

This reduces unnecessary processing and LLM calls.

## 5. Agent Responsibilities

### Agent 1 – Smart Insights

**Purpose:** Explain individual KPI signals.

**Inputs:**
- Loan account number
- Current KPI facts
- KPI history
- Loan context
- KPI definitions
- Peer/comparison information where available

**Output:** A concise KPI narrative grounded in available data.

The narrative should explain the KPI, describe the current signal, use actual values, consider historical/peer context where applicable, and explicitly identify healthy signals where appropriate.

Agent 1 uses an LLM for natural-language insight generation.

### Agent 2 – Risk Summary

**Purpose:** Calculate the overall loan risk.

**Inputs:**
- All six KPI values/signals
- KPI definitions
- KPI weights
- Thresholds
- Directionality

**Severity mapping:**

```text
GREEN    = 0
AMBER    = 1
RED      = 2
CRITICAL = 3
```

The weighted normalized result produces a score from 0–10.

**Risk categories:**

```text
0–2.5       LOW
>2.5–5      MEDIUM
>5–7.5      HIGH
>7.5–10     CRITICAL
```

Agent 2 performs deterministic calculation and does not require an LLM for scoring.

**Output:**
- Risk score
- Risk category

### Agent 3 – Recommended Actions

**Purpose:** Recommend policy/playbook-grounded actions.

**Inputs:**
- Agent 1 insights
- Agent 2 risk score/category
- Triggered KPI information
- Loan context
- Playbook guidance retrieved through RAG

**Processing:**
1. Identify triggered KPIs.
2. Retrieve relevant playbook guidance.
3. Consider systemic/compound risk.
4. Rank and deduplicate actions.
5. Generate concise explanations for selected actions.

**Output:** A short ranked list of recommended actions with reasons grounded in KPI/risk information and retrieved playbook guidance.

The analyst remains responsible for approving or rejecting recommendations.

### Agent 4 – Conversational Chat

**Purpose:** Answer analyst questions about a loan.

Agent 4 is the conversational/read-only layer. It can answer questions involving:
- KPI insights,
- risk score/category,
- recommended actions,
- historical trends,
- current loan/customer data, and
- other supported database information.

Agent 4 classifies the question and uses the appropriate existing agent output and/or read-only database query.

Agent 4 must not modify the database.

## 6. Router Design

The router is the entry point after `START`.

### Direct Agent Routes

```text
route = agent1
route = agent2
route = agent3
```

The router sends execution to the requested workflow while checking required dependencies.

### Chat Route

For:

```text
route = agent4
```

the router examines the question.

| User Question | Required Path |
|---|---|
| What is the risk score? | Agent 2 → Agent 4 |
| Explain the KPI signals | Agent 1 → Agent 4 |
| What actions should we take? | Agent 1 → Agent 2 → Agent 3 → Agent 4 |
| What happened to this loan over time? | Agent 4 |
| Show current outstanding exposure | Agent 4 |

If the required output is already present in state, the corresponding agent is skipped.

## 7. Shared State

LangGraph uses a shared state object to pass information between nodes.

```python
class State(TypedDict, total=False):
    loan_acct_number: str
    question: str
    route: str
    agent1_output: str
    risk_score: float
    risk_category: str
    recommended_actions: str
    answer: str
    citations: list
    queries_used: list
    tools_used: list
    chat_history: list
    execution_trace: list
```

The state acts as the shared workspace for the workflow.

## 8. State Reuse

The router checks whether outputs already exist.

```text
agent1_output exists
        ↓
Do not run Agent 1 again
```

```text
risk_score + risk_category exist
        ↓
Do not run Agent 2 again
```

```text
recommended_actions exists
        ↓
Do not run Agent 3 again
```

This allows the system to reuse previous work.

## 9. Streamlit Integration

The Streamlit UI stores generated outputs in session state.

The main cached outputs are:
- Agent 1 output
- Agent 2 risk score/category
- Agent 3 recommended actions

When a new request is submitted, these values are passed into the LangGraph state.

```text
Streamlit Session State
          |
          v
     LangGraph State
          |
          v
       Router
```

This allows the router to determine which outputs are already available.

## 10. Execution Trace

The graph records which agents actually executed.

Example for a risk-only request:

```text
✓ Agent 2 - Risk Summary
```

For a recommendation request where dependencies are missing:

```text
✓ Agent 1 - Smart Insights
✓ Agent 2 - Risk Summary
✓ Agent 3 - Recommended Actions
✓ Agent 4 - Chat
```

For a historical database question:

```text
✓ Agent 4 - Chat
```

The execution trace makes the conditional architecture visible during demos/testing.

## 11. Runtime Flows

### Risk Score

```text
User → Router → Agent 2 → END
```

### KPI Insight

```text
User → Router → Agent 1 → END
```

### Recommended Actions

If A1/A2 are missing:

```text
User → Router → Agent 1 → Agent 2 → Agent 3 → END
```

If A1/A2 are already cached:

```text
User → Router → Agent 3 → END
```

### Chat Risk Question

```text
User Question → Router → Agent 2 if required → Agent 4 → Answer
```

### Historical Question

```text
User Question → Router → Agent 4 → Read-only SQL → Answer
```

## 12. Database and RAG

### Database

The system uses loan/KPI data for:
- current KPI facts,
- KPI history,
- loan context,
- customer/loan information,
- risk calculation inputs, and
- historical questions.

Database access for Agent 4 is read-only. Only supported `SELECT`/`WITH` queries are permitted.

### Playbook RAG

Agent 3 retrieves relevant playbook guidance and uses it to ground recommended actions. Actions should not be invented independently of the retrieved guidance.

## 13. Exposure Definition

For current loan/customer exposure:

```text
Exposure = SUM(OUTSTANDING_BAL)
```

`LOAN_AMT` represents the original/sanctioned loan amount and should not be used for current exposure.

Therefore, when a question asks for current loan exposure:

```sql
SUM(OUTSTANDING_BAL)
```

should be used.

## 14. LLM Usage

**Agent 1**
- LLM for KPI narrative generation.

**Agent 2**
- Deterministic calculation.
- No LLM required for scoring.

**Agent 3**
- LLM where required for explanations after deterministic action selection.

**Agent 4**
- LLM for conversational interpretation/response generation when required.
- Database tools for live data questions.

The router prevents agents that are not needed from being executed.

## 15. Error and Edge-Case Handling

The architecture should handle:
- missing loan account number,
- missing agent outputs,
- missing KPI data,
- missing risk information,
- missing playbook guidance,
- invalid/read-write SQL requests,
- unsupported questions,
- empty recommendations, and
- already-generated outputs.

When an output is missing but required by a downstream agent, the router executes the required dependency.

## 16. Human-in-the-Loop

The system supports analyst decision-making rather than replacing it.

```text
Data
  ↓
KPI Insights
  ↓
Risk Assessment
  ↓
Recommended Actions
  ↓
Analyst Review
  ↓
Decision
```

Agent 3 provides recommendations, but the analyst remains the final decision-maker.

## 17. Benefits of the Updated Architecture

### Reduced Unnecessary Execution

The system no longer forces:

```text
Agent 1 → Agent 2 → Agent 3 → Agent 4
```

for every request.

### Reusable Outputs

Previously generated outputs can be reused from state/session state.

### Fewer LLM Calls

Only agents required for the current task are executed.

### Better Scalability

Additional agents/routes can be added without making every request execute the entire chain.

### Better Explainability

The execution trace shows exactly which agents ran.

### Better Alignment

The architecture supports surfacing, prioritizing, recommending, and analyst follow-up while avoiding unnecessary execution.

## 18. File/Module Structure

```text
EWI/
├── graph.py
├── agent1.py
├── agent2.py
├── agent3.py
├── agent4.py
├── borrower.py
├── portfolio.py
├── database/
├── playbook/
└── requirements/
```

| File | Responsibility |
|---|---|
| `graph.py` | Shared state, router, nodes, conditional routing, execution trace, compiled graph |
| `agent1.py` | Smart Insights Agent |
| `agent2.py` | Deterministic Risk Summary Agent |
| `agent3.py` | Recommended Actions and playbook/RAG logic |
| `agent4.py` | Conversational read-only Agent |
| `borrower.py` | Borrower-level UI |
| `portfolio.py` | Portfolio/chat UI |

## 19. Final Architecture Summary

```text
                         +-------------+
                         |    START    |
                         +------+------+
                                |
                                v
                         +-------------+
                         |   ROUTER    |
                         +------+------+
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
        +---------+        +---------+        +---------+
        | Agent 1 |        | Agent 2 |        | Agent 3 |
        | Insights|        |  Risk   |        | Actions |
        +----+----+        +----+----+        +----+----+
             |                  |                  |
             +------------------+------------------+
                                |
                                v
                         +-------------+
                         |   Agent 4   |
                         |    Chat     |
                         +------+------+
                                |
                                v
                              END
```

**Core principle:**

> The agents are available as independent capabilities, while the router decides the minimum execution path required for each request and reuses outputs already present in state.
