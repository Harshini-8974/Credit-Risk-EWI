from langchain_groq import ChatGroq
from db import get_kpi_context

llm = ChatGroq(
    model="qwen/qwen3.8-27b",
    temperature=0,
    max_tokens=150
)

def generate_kpi_narrative(kpi_data):
    prompt = f"""
You are the Smart Insights Agent in a credit-risk Early Warning Indicator system.

Your task is to generate ONE very short KPI insight for a Relationship Manager.

Use ONLY the information provided below.

Do not invent any values, thresholds, benchmarks, scores, or conclusions.

BORROWER CONTEXT:

Loan Account: {kpi_data['LOAN_ACCT_NUMBER']}
Loan Type: {kpi_data['LOAN_TYPE']}
Loan Amount: {kpi_data['LOAN_AMT']}
Outstanding Balance: {kpi_data['OUTSTANDING_BAL']}
Remaining Tenure: {kpi_data['REMAINING_TENURE_MONTHS']} months
Interest Rate: {kpi_data['INTEREST_RATE']}
Interest Rate Type: {kpi_data['INTEREST_RATE_TYPE']}
Risk Ranking: {kpi_data['RISK_RANKING']}
Collateral Value: {kpi_data['COLLATERAL_VALUE']}
Collateral Coverage: {kpi_data['COLLATERAL_COVERAGE_PCT']}
Customer: {kpi_data['PRIMARY_CUSTOMER_NAME']}
MCC: {kpi_data['MCC']}
Tenure Bucket: {kpi_data['TENURE_BUCKET']}
Region: {kpi_data['REGION']}

KPI INFORMATION:

KPI ID: {kpi_data['KPI_ID']}
KPI Name: {kpi_data['KPI_NAME']}
Current KPI Value: {kpi_data['KPI_VALUE']}
KPI Unit: {kpi_data['KPI_UNIT']}
Historical/Window Values: {kpi_data['VALUES_IN_WINDOW']}
Observation Window: {kpi_data['OBSERVATION_WINDOW']}
Threshold Breached: {kpi_data['THRESHOLD_BREACHED']}
Assigned Tier: {kpi_data['ASSIGNED_TIER']}

KPI DEFINITION:

Description: {kpi_data['KPI_DESCRIPTION']}
Interpretation: {kpi_data['INTERPRETATION']}
Directionality: {kpi_data['DIRECTIONALITY']}
Risk Significance: {kpi_data['RISK_SIGNIFICANCE']}

RULES:

1. Maximum 3 sentences.
2. Use simple and clear business language.
3. Mention the current KPI value.
4. Compare the current value with the historical/window values when available.
5. Clearly state whether the KPI is healthy or adverse based only on the supplied KPI information.
6. Use actual numbers from the supplied data.
7. Do not invent a peer, MCC, or tenure benchmark if no benchmark value is provided.
8. Do not calculate or mention the composite risk score.
9. Do not recommend any actions.
10. Do not use vague phrases such as "looks concerning" without explaining why.
11. Do not create headings or bullet points.
12. Return ONLY the final KPI narrative.
13. Include the assigned tier naturally in the sentence and write in ALL CAPS.

Generate the KPI insight now.
"""
    response = llm.invoke(prompt)
    return response.content.strip()

def generate_compact_kpi_insight(kpi_data):
    prompt = f"""
You are the Smart Insights Agent in a credit-risk Early Warning Indicator system.

Generate a compact KPI insight for Agent 3, which will use it to select playbook-supported recommended actions.

Use ONLY the supplied data.

KPI ID: {kpi_data['KPI_ID']}
KPI Name: {kpi_data['KPI_NAME']}
Current Value: {kpi_data['KPI_VALUE']}
Unit: {kpi_data['KPI_UNIT']}
Window Values: {kpi_data['VALUES_IN_WINDOW']}
Observation Window: {kpi_data['OBSERVATION_WINDOW']}
Threshold Breached: {kpi_data['THRESHOLD_BREACHED']}
Assigned Tier: {kpi_data['ASSIGNED_TIER']}
Interpretation: {kpi_data['INTERPRETATION']}
Directionality: {kpi_data['DIRECTIONALITY']}
Risk Significance: {kpi_data['RISK_SIGNIFICANCE']}

RULES:
1. Maximum 2 sentences.
2. Mention the KPI value and assigned tier.
3. State whether the KPI is healthy or adverse based only on the supplied information.
4. Mention the window/trend only when supplied data supports it.
5. Use actual values only.
6. Do not invent thresholds, benchmarks, scores or recommendations.
7. Return only the insight.
"""
    response = llm.invoke(prompt)
    return response.content.strip()

def agent1(state):
    loan_acct_number = state["loan_acct_number"]
    compact = state.get("compact", False)
    narratives = []

    for kpi_id in [
        "KPI-001",
        "KPI-002",
        "KPI-003",
        "KPI-004",
        "KPI-005",
        "KPI-006"
    ]:
        kpi_data = get_kpi_context(
            loan_acct_number,
            kpi_id
        )
        if kpi_data:
            if compact:
                narrative = generate_compact_kpi_insight(kpi_data)
            else:
                narrative = generate_kpi_narrative(kpi_data)

            narratives.append(
                f"{kpi_id} - {kpi_data['KPI_NAME']}: {narrative}"
            )

    agent1_output = "\n".join(narratives)

    return {
        "agent1_output": agent1_output
    }
#testing block
if __name__ == "__main__":
    loan_acct_number = input("Enter loan account number: ")

    print("=" * 25)
    print("SMART INSIGHTS AGENT")
    print("=" * 25)
    print(f"LOAN ACCOUNT: {loan_acct_number}")
    print("=" * 25)

    kpi_ids = [
        "KPI-001",
        "KPI-002",
        "KPI-003",
        "KPI-004",
        "KPI-005",
        "KPI-006"
    ]

    total_processed = 0

    for kpi_id in kpi_ids:
        print(f"\n{kpi_id}")

        kpi_data = get_kpi_context(
            loan_acct_number,
            kpi_id
        )

        if kpi_data:
            narrative = generate_kpi_narrative(kpi_data)
            print(narrative)
            total_processed += 1
        else:
            print("No KPI data found.")

    print("\n" + "=" * 25)
    print(f"TOTAL KPIs PROCESSED: {total_processed}")
    print("=" * 25)