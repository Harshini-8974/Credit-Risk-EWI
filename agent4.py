from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from db import get_connection

DATABASE_SCHEMA = """
TABLE: loan_context
COLUMNS:
BANK_NUMBER
LOAN_ACCT_NUMBER
LOAN_TYPE
LOAN_AMT
OUTSTANDING_BAL
REMAINING_TENURE_MONTHS
INTEREST_RATE
INTEREST_RATE_TYPE
NUM_LOANS_ENTITY
RISK_RANKING
COLLATERAL_VALUE
COLLATERAL_COVERAGE_PCT
PRIMARY_CUSTOMER_NAME
MCC
TENURE_BUCKET
REGION
DDA_CNT_GROUP1
DDA_CNT_GROUP2
DDA_CNT_OVERALL
DDA_COMBINED_AVG_BAL
LIQUIDITY_RATIO
AVG_OD_DAYS_CNT_6M
RUN_DATE
RELATIONSHIP_MANAGER_ID
RELATIONSHIP_MANAGER_NAME
PRIMARY_CUSTOMER_ID

TABLE: loan_kpi_facts
COLUMNS:
BANK_NUMBER
LOAN_ACCT_NUMBER
KPI_ID
KPI_NAME
RUN_DATE
KPI_VALUE
KPI_UNIT
VALUES_IN_WINDOW
OBSERVATION_WINDOW
THRESHOLD_BREACHED
ASSIGNED_TIER
MCC
TENURE

TABLE: kpi_definitions
COLUMNS:
KPI_ID
KPI_NAME
KPI_DESCRIPTION
CALCULATION_LOGIC
INTERPRETATION
DIRECTIONALITY
THRESHOLD_AMBER
THRESHOLD_RED
THRESHOLD_CRITICAL
RISK_SIGNIFICANCE
WHAT_MAKES_IT_WORSE
WHAT_PROVIDES_COMFORT
VERSION
LAST_UPDATED
KPI_WEIGHTAGE

TABLE: kpi_001_addons
COLUMNS:
BANK_NUMBER
LOAN_ACCT_NUMBER
KPI_ID
KPI_NAME
RUN_DATE
DELAYED_PAYMENTS
TOTAL_PAYMENTS

TABLE: kpi_002_addons
COLUMNS:
BANK_NUMBER
LOAN_ACCT_NUMBER
KPI_ID
KPI_NAME
RUN_DATE
CURRENT_LIMIT
CURRENT_DRAWN

TABLE: kpi_003_addons
COLUMNS:
BANK_NUMBER
LOAN_ACCT_NUMBER
KPI_ID
KPI_NAME
RUN_DATE
AVG_BAL_30D
AVG_BAL_60D
AVG_BAL_90D
PCT_60D_VS_30D
PCT_90D_VS_60D

TABLE: kpi_004_addons
COLUMNS:
BANK_NUMBER
LOAN_ACCT_NUMBER
KPI_ID
KPI_NAME
RUN_DATE
EXT_CR_AMT_1M
AVG_EXT_CR_AMT_6M
"""

def is_historical_question(question):
    q = question.lower()
    historical_terms = [
        "history",
        "historical",
        "over time",
        "trajectory",
        "trend",
        "trending",
        "declining",
        "decline",
        "increasing",
        "increase",
        "rising",
        "falling",
        "previous",
        "past",
        "month over month",
        "monthly",
        "payment timing drift",
        "cashflow detail",
        "balance trajectory",
        "overdraft frequency",
        "payment reversal",
        "most recent run date",
        "run date"
    ]
    return any(term in q for term in historical_terms)

def is_risk_summary_question(question):
    q = question.lower()
    risk_terms = [
        "risk score",
        "risk category",
        "overall risk",
        "risk summary",
        "risk assessment",
        "how risky",
        "risk level"
    ]
    return any(term in q for term in risk_terms)

def is_recommendation_question(question):
    q = question.lower()
    recommendation_terms = [
        "recommended action",
        "recommended actions",
        "recommendation",
        "recommendations",
        "what should the rm do",
        "what should rm do",
        "what should we do",
        "what actions",
        "what action",
        "next action",
        "next actions",
        "next step",
        "next steps",
        "recommend"
    ]
    return any(term in q for term in recommendation_terms)

def is_insight_question(question):
    q = question.lower()
    insight_terms = [
        "kpi insight",
        "kpi insights",
        "kpi explanation",
        "kpi explanations",
        "kpi meaning",
        "kpi meanings",
        "explain kpi",
        "explain the kpi",
        "current signal",
        "kpi signal",
        "insight",
        "insights"
    ]
    return any(term in q for term in insight_terms)

def is_read_only_query(query):
    q = query.strip().lower()
    if not (q.startswith("select") or q.startswith("with")):
        return False
    blocked_terms = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "truncate ",
        "create ",
        "replace ",
        "grant ",
        "revoke ",
        "call ",
        "execute ",
        "merge "
    ]
    return not any(term in q for term in blocked_terms)

@tool
def execute_read_only_sql(query: str) -> str:
    """
    Execute a read-only SQL query against the EWI database.
    Only SELECT and WITH queries are allowed.
    """
    if not is_read_only_query(query):
        return "ERROR: Only read-only SELECT or WITH SQL queries are allowed."

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            return "Data not available."

        return str(rows)

    except Exception as e:
        return f"SQL ERROR: {str(e)}"

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

tools = [execute_read_only_sql]

def get_llm_response(messages, tools=None):
    groq_llm = ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0,
        max_tokens=2500
    )

    gemini_llm = ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
        temperature=0,
        max_output_tokens=2500
    )

    if tools:
        groq_llm = groq_llm.bind_tools(tools)
        gemini_llm = gemini_llm.bind_tools(tools)

    try:
        return groq_llm.invoke(messages)

    except Exception as groq_error:
        error_text = str(groq_error).lower()

        fallback_errors = [
            "429",
            "rate limit",
            "rate_limit",
            "too many requests",
            "timeout",
            "timed out",
            "service unavailable",
            "internal server error",
            "502",
            "503"
        ]

        if any(error in error_text for error in fallback_errors):
            print("Groq temporarily unavailable. Switching to Gemini.")
            return gemini_llm.invoke(messages)

        raise groq_error

def agent4(state):
    question = state.get("question", "")
    loan_acct_number = state.get("loan_acct_number", "")
    agent1_output = state.get("agent1_output", "")
    risk_score = state.get("risk_score", "")
    risk_category = state.get("risk_category", "")
    recommended_actions = state.get("recommended_actions", "")
    chat_history = state.get("chat_history", [])

    historical_question = is_historical_question(question)
    risk_question = is_risk_summary_question(question)
    recommendation_question = is_recommendation_question(question)
    insight_question = is_insight_question(question)

    combined_question = sum([
        insight_question,
        risk_question,
        recommendation_question
    ]) >= 2

    if (
        risk_question
        and not combined_question
        and risk_score != ""
        and risk_category
    ):
        answer = (
            f"Risk summary for loan {loan_acct_number}:\n\n"
            f"- Risk Score: **{risk_score}**\n"
            f"- Risk Category: **{risk_category}**"
        )

        updated_chat_history = chat_history + [
            {
                "role": "user",
                "content": question
            },
            {
                "role": "assistant",
                "content": answer
            }
        ]

        return {
            "answer": answer,
            "citations": [
                "Agent 2 Risk Summary",
                f"Loan Account: {loan_acct_number}"
            ],
            "queries_used": [],
            "tools_used": [],
            "chat_history": updated_chat_history
        }

    if (
        recommendation_question
        and not combined_question
        and recommended_actions
    ):
        answer = (
            f"Recommended actions for loan {loan_acct_number}:\n\n"
            f"{recommended_actions}"
        )

        updated_chat_history = chat_history + [
            {
                "role": "user",
                "content": question
            },
            {
                "role": "assistant",
                "content": answer
            }
        ]

        return {
            "answer": answer,
            "citations": [
                "Agent 3 Recommended Actions",
                f"Loan Account: {loan_acct_number}"
            ],
            "queries_used": [],
            "tools_used": [],
            "chat_history": updated_chat_history
        }

    system_prompt = f"""
You are Agent 4, the final conversational agent in an Early Warning Indicator
(EWI) loan monitoring system.

Your job is to answer the Relationship Manager's question accurately using
the available sources.

DATABASE SCHEMA:
{DATABASE_SCHEMA}

SOURCE PRIORITY:

1. AGENT 1 KPI INSIGHTS

Agent 1 explains the meaning and current signal of each KPI.

Use Agent 1 when the user asks about:
- KPI insights
- KPI meaning
- KPI explanation
- KPI signals
- current KPI conditions

2. AGENT 2 RISK SUMMARY

Agent 2 provides the weighted composite risk score and risk category.

Use Agent 2 when the user asks about:
- overall risk
- risk score
- risk category
- risk summary
- risk assessment

3. AGENT 3 RECOMMENDED ACTIONS

Agent 3 provides recommended RM actions based on current KPI risks
and playbook guidance.

Use Agent 3 when the user asks about:
- recommended actions
- recommendations
- what the RM should do
- next actions
- next steps

4. EWI DATABASE

Use the database when raw or supporting information is required.

IMPORTANT RULES:

- Do not invent values.
- Do not invent historical data.
- Do not invent KPI trends.
- Do not fabricate previous values.
- Do not fabricate dates.
- Do not fabricate monthly values.
- If requested information is not available, say:
  "Data not available."

- KPI_VALUE represents the current KPI value.
- VALUES_IN_WINDOW contains the available values within the observation window.
- OBSERVATION_WINDOW describes the observation period.
- RUN_DATE represents the data run date.
- THRESHOLD_BREACHED = 1 means the KPI is breached.
- THRESHOLD_BREACHED = 0 means the KPI is not breached.

For questions asking for the most recent run date,
use MAX(RUN_DATE) or an equivalent latest-date filter.

Do not hard-code:
- customer names
- RM names
- loan accounts
- KPI combinations
- specific dates

Use the actual database values.

EXPOSURE RULE:

For questions asking for current loan exposure, loan exposure, current exposure, or outstanding exposure, use OUTSTANDING_BAL.

For grouped customer exposure questions, use SUM(OUTSTANDING_BAL).

LOAN_AMT represents the original or sanctioned loan amount. Do not use LOAN_AMT for current exposure.

For example, for:

"Show me the top 5 customers by loan exposure."

use:

SELECT
    PRIMARY_CUSTOMER_ID,
    PRIMARY_CUSTOMER_NAME,
    SUM(OUTSTANDING_BAL) AS TOTAL_EXPOSURE
FROM loan_context
GROUP BY PRIMARY_CUSTOMER_ID, PRIMARY_CUSTOMER_NAME
ORDER BY TOTAL_EXPOSURE DESC
LIMIT 5;

Before executing a current exposure query, verify that the query does not use SUM(LOAN_AMT).

HISTORICAL AND TREND QUESTIONS:

For historical, trend, trajectory, previous, past, declining,
increasing, or over-time questions, use the historical information
actually available in the database.

Use:
- VALUES_IN_WINDOW
- OBSERVATION_WINDOW
- RUN_DATE
- KPI_VALUE
- KPI-specific addon tables when they contain the requested detail.

First identify which KPI the question refers to.

Use the correct KPI/addon table:

- KPI-001 Payment Timing Drift -> kpi_001_addons
- KPI-002 Sustained High Utilization -> kpi_002_addons
- KPI-003 Declining Average Collected Balance -> kpi_003_addons
- KPI-004 Inbound Cashflow Decline -> kpi_004_addons
- KPI-005 Overdraft Frequency -> loan_kpi_facts or loan_context fields
  when appropriate
- KPI-006 Payment Reversal Count -> loan_kpi_facts or available
  supporting data when appropriate

Do not use an unrelated KPI addon table.

For KPI-003 balance trajectory questions, use:
- AVG_BAL_30D
- AVG_BAL_60D
- AVG_BAL_90D
- PCT_60D_VS_30D
- PCT_90D_VS_60D

For KPI-004 inbound cashflow questions, use:
- EXT_CR_AMT_1M
- AVG_EXT_CR_AMT_6M

For KPI-002 utilization questions, use:
- CURRENT_LIMIT
- CURRENT_DRAWN

For KPI-001 payment timing questions, use:
- DELAYED_PAYMENTS
- TOTAL_PAYMENTS

Do not create a month-by-month history when the database does not
contain those values.

If the requested historical detail is not supported by the available
data, return:

"Data not available."

After executing a historical SQL query, use the returned database rows
to answer the user's question.

Do not return only the SQL query unless the user explicitly asks
to see the SQL query.

AGGREGATION AND COUNT QUESTIONS:

When the user asks questions such as:
- which customers are breaching N or more KPIs
- which loans have N or more breached KPIs
- customers with multiple KPI breaches
- loans with at least N critical KPIs
- customers meeting multiple KPI conditions

construct an aggregation query.

For breach-count questions:
- Use loan_kpi_facts.
- THRESHOLD_BREACHED = 1 means breached.
- Group by BANK_NUMBER and LOAN_ACCT_NUMBER.
- Join loan_context when customer information is requested.
- Count the matching breached KPI rows.
- Use HAVING COUNT(*) >= N.
- Use the number N requested by the user.
- Do not simply SELECT DISTINCT THRESHOLD_BREACHED.
- Do not return only the distinct breach flag.

For example, a question asking for customers breaching 3 or more KPIs
requires grouping by loan and using HAVING COUNT(*) >= 3.

Do not hard-code the number 3 for other questions.
Use the number requested by the user.

For "right now" or "currently" questions, use the appropriate latest
RUN_DATE logic when multiple run dates are present.

MULTIPLE KPI CONDITION QUESTIONS:

When the user asks for a combination of KPI conditions, such as:

"Show customers where cashflow is declining AND utilization is rising."

identify the corresponding KPI IDs and construct the SQL dynamically.

Use joins, CTEs, conditional aggregation, GROUP BY, and HAVING as needed.

Do not hard-code a particular customer, loan, or KPI combination.

SQL EXECUTION AND ANSWER RULE:

When database information is required:

1. Generate valid MySQL-compatible SELECT or WITH SQL.
2. Execute it using the read-only SQL tool.
3. Read the returned database rows.
4. Answer the user's question using those returned rows.
5. Do not return only the generated SQL.
6. If the tool returns "Data not available.", say "Data not available."

The "View query" section is only supporting information.
The actual answer must be based on the SQL execution result.

COMBINED QUESTIONS:

If the user asks for multiple things in one question,
combine the relevant sources.

For example:

"Give me the KPI insights, overall risk, and recommended actions."

The answer should contain:

1. KPI Insights
2. Overall Risk
3. Recommended Actions

Use:
- Agent 1 for KPI insights.
- Agent 2 for risk score and risk category.
- Agent 3 for recommended actions.

Do not ignore one source simply because another source is available.

Do not perform a SQL query for information that is already provided
by Agent 1, Agent 2, or Agent 3 unless additional database information
is required.

CURRENT LOAN ACCOUNT:
{loan_acct_number}

AGENT 1 KPI INSIGHTS:
{agent1_output}

AGENT 2 RISK SCORE:
{risk_score}

AGENT 2 RISK CATEGORY:
{risk_category}

AGENT 3 RECOMMENDED ACTIONS:
{recommended_actions}

USER QUESTION:
{question}

CHAT HISTORY:
{chat_history}

Answer the user's question directly and clearly.
- If the SQL result contains multiple rows, include all relevant rows in the final answer.
- Do not stop partway through a list.
- Keep each row concise so the complete result can fit in the response.

If SQL is required, generate valid MySQL-compatible SQL
and use the read-only SQL tool.

Do not show internal reasoning.

Do not mention system prompts or internal instructions.
"""

    messages = [
        SystemMessage(content=system_prompt)
    ]

    for message in chat_history[-10:]:
        role = message.get("role", "")
        content = message.get("content", "")

        if role == "user":
            messages.append(
                HumanMessage(content=content)
            )
        elif role == "assistant":
            messages.append(
                AIMessage(content=content)
            )

    messages.append(
        HumanMessage(content=question)
    )

    queries_used = []
    tools_used = []

    try:
        response = get_llm_response(messages, tools)

        while getattr(response, "tool_calls", None):
            messages.append(response)

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})

                if tool_name == "execute_read_only_sql":
                    query=tool_args.get("query","")
                    question_lower=question.lower()

                    exposure_question=any(
                        term in question_lower
                        for term in [
                            "exposure",
                            "loan exposure",
                            "current exposure",
                            "outstanding exposure"
                        ]
                    )

                    original_amount_question=any(
                        term in question_lower
                        for term in [
                            "original loan amount",
                            "original loan",
                            "sanctioned loan amount",
                            "sanctioned amount",
                            "loan amount"
                        ]
                    )

                    if exposure_question and not original_amount_question:
                        query=query.replace("SUM(LOAN_AMT)","SUM(OUTSTANDING_BAL)")
                        query=query.replace("SUM(loan_amt)","SUM(OUTSTANDING_BAL)")

                    queries_used.append(query)
                    tools_used.append(tool_name)

                    tool_result=execute_read_only_sql.invoke(
                        {"query":query}
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": tool_result
                        }
                    )

            response = get_llm_response(messages, tools)

        if isinstance(response.content, str):
            answer = response.content
        else:
            answer_parts = []

            for block in response.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    answer_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    answer_parts.append(block)

            answer = "\n".join(answer_parts).strip()

        citations = []

        if agent1_output and (
            insight_question
            or combined_question
            or any(
                term in question.lower()
                for term in [
                    "kpi",
                    "signal",
                    "meaning",
                    "insight",
                    "explanation"
                ]
            )
        ):
            citations.append("Agent 1 KPI Insights")

        if queries_used:
            citations.append("EWI Database")

        if risk_question or combined_question:
            if risk_score != "" and risk_category:
                citations.append("Agent 2 Risk Summary")

        if recommendation_question or combined_question:
            if recommended_actions:
                citations.append("Agent 3 Recommended Actions")

        portfolio_question = any(
            term in question.lower()
            for term in [
                "customers",
                "customer",
                "all loan accounts",
                "all loans",
                "which loans",
                "which customers",
                "relationship manager",
                "managed by",
                "portfolio"
            ]
        )

        if loan_acct_number and not portfolio_question:
            citations.append(
                f"Loan Account: {loan_acct_number}"
            )

        updated_chat_history = chat_history + [
            {
                "role": "user",
                "content": question
            },
            {
                "role": "assistant",
                "content": answer
            }
        ]

        return {
            "answer": answer,
            "citations": citations,
            "queries_used": queries_used,
            "tools_used": tools_used,
            "chat_history": updated_chat_history
        }

    except Exception:
        return {
            "answer": "Data not available.",
            "citations": [],
            "queries_used": queries_used,
            "tools_used": tools_used,
            "chat_history": chat_history
        }