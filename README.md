# Credit Risk Early Warning Indicators (EWI) Agent System

An Agentic AI system built with **Python and LangGraph** to monitor loan/KPI risk, generate explainable risk insights, recommend policy/playbook-grounded actions, and support analysts through a conversational interface.

The system uses a **4-agent router-based LangGraph architecture** that dynamically selects the minimum execution path required for each request and reuses outputs already available in application state.

---

## 📌 Project Overview

The Credit Risk Early Warning Indicators (EWI) system helps analysts identify and understand early warning signals associated with loans.

The system:

- Analyzes loan and KPI data
- Explains individual KPI signals
- Calculates an overall weighted risk score
- Classifies loans into Low, Medium, High, or Critical risk
- Recommends policy/playbook-grounded actions
- Supports natural-language questions about loan risk and history
- Reuses previously generated outputs
- Avoids unnecessary agent and LLM execution
- Keeps the analyst as the final decision-maker

---

## ✨ Key Features

- 4-agent LangGraph architecture
- Conditional router-based execution
- Shared state between agents
- State and session-state reuse
- Explainable weighted risk scoring
- Low, Medium, High, and Critical risk classification
- KPI insight generation
- Playbook-grounded recommendations using RAG
- Conversational loan-risk analysis
- Read-only database querying
- Execution trace for agent visibility
- Streamlit portfolio and borrower interfaces
- Human-in-the-loop decision support

---

## 🏗️ Architecture

### Router-Based Architecture

Unlike a fixed sequential workflow, the system uses a router to determine which agent or combination of agents is required for each request.

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
                +---------------+---------------+
                |               |               |
                v               v               v
          +---------+      +---------+      +---------+
          | Agent 1 |      | Agent 2 |      | Agent 3 |
          | Insights|      |  Risk   |      | Actions |
          +----+----+      +----+----+      +----+----+
                |               |               |
                +---------------+---------------+
                                |
                                v
                         +-------------+
                         |   Agent 4   |
                         |    Chat     |
                         +------+------+
                                |
                                v
                               END

The router checks:
- What the user requested
- Which outputs already exist
- Which dependencies are missing
- Which agent is actually required
This reduces unnecessary processing and LLM calls.
Core Design Principle
Dependency does not mean mandatory re-execution.

If an agent's output already exists in shared state or Streamlit session state, that agent does not need to execute again.
🤖 Agents
Agent 1 - Smart Insights
Purpose
The Smart Insights Agent explains individual KPI signals and generates a concise narrative based on available loan data.
Inputs
- Loan account number
- Current KPI facts
- KPI history
- Loan context
- KPI definitions
- Peer/comparison information where available
Responsibilities
- Explains the KPI
- Describes the current signal
- Uses actual KPI values
- Considers historical context where applicable
- Considers peer/comparison information where available
- Identifies healthy signals when appropriate
Output
A concise KPI narrative grounded in the available data.
Agent 1 uses an LLM for natural-language insight generation.
Agent 2 - Risk Summary
Purpose
The Risk Summary Agent calculates the overall risk of a loan using KPI signals, thresholds, weights, and directionality.
Inputs
- Six KPI values/signals
- KPI definitions
- KPI weights
- Thresholds
- KPI directionality
Severity Mapping
GREEN    = 0
AMBER    = 1
RED      = 2
CRITICAL = 3

The weighted normalized result produces a risk score from 0 to 10.
Risk Categories
0–2.5        LOW
>2.5–5       MEDIUM
>5–7.5       HIGH
>7.5–10      CRITICAL

Output
- Risk score
- Risk category
Risk scoring is performed using deterministic calculations and does not require an LLM.
Agent 3 - Recommended Actions
Purpose
The Recommended Actions Agent generates policy/playbook-grounded actions based on the identified risk.
Inputs
- Agent 1 insights
- Agent 2 risk score and category
- Triggered KPI information
- Loan context
- Playbook guidance retrieved through RAG
Processing
1. Identifies triggered KPIs
2. Retrieves relevant playbook guidance
3. Considers systemic or compound risk
4. Ranks and deduplicates actions
5. Generates concise explanations for selected actions
Output
A short ranked list of recommended actions with reasons grounded in KPI/risk information and retrieved playbook guidance.
The analyst remains responsible for approving or rejecting recommendations.
Agent 4 - Conversational Chat
Purpose
The Conversational Chat Agent provides a natural-language interface for analysts to ask questions about a loan.
It can answer questions involving:
- KPI insights
- Risk score and category
- Recommended actions
- Historical trends
- Current loan/customer information
- Other supported database information
Agent 4 can use existing agent outputs and/or read-only database queries depending on the question.
The agent does not modify the database.
🔀 Intelligent Routing
The router acts as the entry point after START.
For direct requests, it can route to:
route = agent1
route = agent2
route = agent3

For conversational questions:
route = agent4

The router then determines whether additional agents are required as dependencies.
Example Routing
User Question	Required Path
What is the risk score?	Agent 2 → Agent 4
Explain the KPI signals	Agent 1 → Agent 4
What actions should we take?	Agent 1 → Agent 2 → Agent 3 → Agent 4
What happened to this loan over time?	Agent 4
Show current outstanding exposure	Agent 4


If the required output is already available in state, the corresponding agent is skipped.
🧠 Shared State & State Reuse
LangGraph uses a shared state object to pass information between nodes.
The state contains information such as:
class State(TypedDict, total=False):    loan_acct_number: str    question: str    route: str    agent1_output: str    risk_score: float    risk_category: str    recommended_actions: str    answer: str    citations: list    queries_used: list    tools_used: list    chat_history: list    execution_trace: list


Previously generated outputs can be reused instead of executing the same agent again.
Agent 1 output exists
        ↓
Skip Agent 1

Risk score + category exist
        ↓
Skip Agent 2

Recommended actions exist
        ↓
Skip Agent 3

This allows the system to execute only what is required for the current request.
🔄 Runtime Flows
Risk Score
User
 ↓
Router
 ↓
Agent 2
 ↓
END

KPI Insight
User
 ↓
Router
 ↓
Agent 1
 ↓
END

Recommended Actions
If Agent 1 and Agent 2 outputs are missing:
User
 ↓
Router
 ↓
Agent 1
 ↓
Agent 2
 ↓
Agent 3
 ↓
END

If Agent 1 and Agent 2 outputs are already available:
User
 ↓
Router
 ↓
Agent 3
 ↓
END

Chat Risk Question
User Question
 ↓
Router
 ↓
Agent 2 if required
 ↓
Agent 4
 ↓
Answer

Historical Question
User Question
 ↓
Router
 ↓
Agent 4
 ↓
Read-only SQL
 ↓
Answer

🗄️ Database Integration
The system uses loan and KPI data for:
- Current KPI facts
- KPI history
- Loan context
- Customer/loan information
- Risk calculation inputs
- Historical questions
Agent 4 uses read-only database access.
Only supported SELECT / WITH queries are permitted.
📚 Playbook RAG
The Recommended Actions Agent uses Retrieval-Augmented Generation (RAG) to retrieve relevant playbook guidance.
The retrieved guidance is used to ground recommended actions.
Triggered KPIs
      ↓
Playbook Retrieval
      ↓
Relevant Guidance
      ↓
Recommended Actions

This helps ensure that recommended actions are supported by the retrieved playbook guidance.
💰 Exposure Calculation
For current loan/customer exposure:
Exposure = SUM(OUTSTANDING_BAL)

LOAN_AMT represents the original/sanctioned loan amount and should not be used for current exposure.
Therefore, when a question asks for current loan exposure, the system uses:
SUM(OUTSTANDING_BAL)

📊 Streamlit Interface
The project includes two Streamlit interfaces.
Portfolio Dashboard
Implemented in:
portfolio.py

Run using:
streamlit run portfolio.py

Borrower Dashboard
Implemented in:
borrower.py

Run using:
streamlit run borrower.py

Streamlit + LangGraph
The Streamlit application stores generated outputs in session state.
Streamlit Session State
          |
          v
     LangGraph State
          |
          v
        Router

This allows the router to determine which outputs are already available before executing additional agents.
🔍 Execution Trace
The graph records which agents actually executed for a request.
Risk-Only Request
✓ Agent 2 - Risk Summary

Recommendation Request
When dependencies are missing:
✓ Agent 1 - Smart Insights
✓ Agent 2 - Risk Summary
✓ Agent 3 - Recommended Actions

Historical Database Question
✓ Agent 4 - Chat

The execution trace makes the conditional architecture visible during testing and demonstrations.
🧩 LLM Usage
Agent	LLM Usage
Agent 1	LLM for KPI narrative generation
Agent 2	Deterministic calculation; no LLM required for scoring
Agent 3	LLM where required for explanations after deterministic action selection
Agent 4	LLM for conversational interpretation and response generation when required


The router prevents agents that are not required for a particular request from being executed.
🛡️ Error & Edge-Case Handling
The architecture is designed to handle:
- Missing loan account number
- Missing agent outputs
- Missing KPI data
- Missing risk information
- Missing playbook guidance
- Invalid or read-write SQL requests
- Unsupported questions
- Empty recommendations
- Already-generated outputs
When an output is missing but required by a downstream agent, the router executes the required dependency.
👩‍💼 Human-in-the-Loop
The system supports analyst decision-making rather than replacing it.
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

The Recommended Actions Agent provides recommendations, while the analyst remains the final decision-maker.
🛠️ Technology Stack
- Python
- LangGraph
- LangChain
- LLMs
- RAG
- Vector Database
- SQL / Database
- Streamlit
- Conditional Routing
- Shared State Management
- Playbook-based Retrieval
⚙️ Installation
Clone the repository:
git clone https://github.com/Harshini-8974/Credit-Risk-EWI.git
cd Credit-Risk-EWI

Create a virtual environment:
python -m venv venv

Activate the virtual environment on Windows:
venv\Scripts\activate

Install the required dependencies:
pip install -r requirements.txt

🔐 Environment Variables
The project uses environment variables for configuration and credentials.
Create a local .env file containing the required environment variables.
Do not commit .env or API keys to GitHub.
Make sure .env is included in .gitignore.
▶️ Running the Application
Portfolio UI
streamlit run portfolio.py

Borrower UI
streamlit run borrower.py

📖 Design Documentation
The detailed technical architecture and design decisions are documented in:
design.md

The design document provides additional details about:
- Router architecture
- Agent responsibilities
- Shared state
- Conditional routing
- State reuse
- Streamlit integration
- Database integration
- Playbook RAG
- Execution trace
- Runtime flows
- LLM usage
- Error handling
- Human-in-the-loop design
✨ Key Benefits
Reduced Unnecessary Execution
The system does not force every request through all four agents.
Instead, the router determines the minimum execution path required.
Reusable Outputs
Previously generated outputs can be reused from LangGraph state and Streamlit session state.
Fewer LLM Calls
Only the agents required for the current task are executed.
Better Explainability
The execution trace shows which agents actually ran for a request.
Better Scalability
Additional agents and routes can be added without forcing every request through the entire workflow.
Analyst-Centered Design
The system provides insights, risk assessment, and recommendations while keeping the analyst as the final decision-maker.
📌 Core Architecture Principle
The agents are available as independent capabilities, while the router decides the minimum execution path required for each request and reuses outputs already present in state.

👤 Author
Harshini Akula
B.Tech Computer Science Engineering
AI / Generative AI / Agentic AI
- LinkedIn: https://www.linkedin.com/in/harshini-akula
- GitHub: https://github.com/Harshini-8974
