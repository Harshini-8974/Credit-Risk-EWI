from langchain_groq import ChatGroq
from db import get_kpi_context
from rag import retriever

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    max_tokens=1000
)

PLAYBOOK_PATH = "playbook.txt"

def load_playbook():
    with open(PLAYBOOK_PATH, "r", encoding="utf-8") as f:
        return f.read()

def get_trigger_kpis(loan_acct_number):
    trigger_kpis = []

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

        if kpi_data and kpi_data["ASSIGNED_TIER"] != "GREEN":
            trigger_kpis.append({
                "kpi_id": kpi_id,
                "kpi_name": kpi_data["KPI_NAME"],
                "kpi_value": kpi_data["KPI_VALUE"],
                "tier": kpi_data["ASSIGNED_TIER"],
                "risk_significance": kpi_data["RISK_SIGNIFICANCE"],
                "dda_combined_avg_bal": kpi_data["DDA_COMBINED_AVG_BAL"],
                "liquidity_ratio": kpi_data["LIQUIDITY_RATIO"]
            })

    return trigger_kpis

def get_triggered_agent1_output(agent1_output, trigger_kpis):
    if not agent1_output or not trigger_kpis:
        return ""

    triggered_output = []

    for kpi in trigger_kpis:
        kpi_id = kpi["kpi_id"]

        for line in agent1_output.splitlines():
            if line.startswith(kpi_id):
                triggered_output.append(line)
                break

    return "\n".join(triggered_output)

def get_overall_actions(playbook):
    actions = []

    start = playbook.find("OVERALL RECOMMENDED ACTIONS")

    if start == -1:
        return actions

    end = playbook.find("KPI-001:", start)

    if end == -1:
        end = len(playbook)

    section = playbook[start:end]

    for line in section.splitlines():
        line = line.strip()

        if line.startswith("ACTION:"):
            action = line.replace(
                "ACTION:","",1 ).strip()

            if action:
                actions.append(action)

    return actions

def get_kpi_section(playbook, kpi_id):
    start = playbook.find(f"{kpi_id}:")

    if start == -1:
        return ""

    next_positions = []
#marker- meaning-new sections start here-text pattern
    for marker in [
        "\nKPI-001:",
        "\nKPI-002:",
        "\nKPI-003:",
        "\nKPI-004:",
        "\nKPI-005:",
        "\nKPI-006:",
        "\nCOMPOUND SIGNAL:"
    ]:
        position = playbook.find(
            marker,
            start + 1
        )

        if position != -1:
            next_positions.append(position)

    if next_positions:
        end = min(next_positions)
    else:
        end = len(playbook)

    return playbook[start:end]

def get_tier_actions(playbook, kpi_id, tier):
    section = get_kpi_section(
        playbook,
        kpi_id
    )

    if not section:
        return []

    lines = section.splitlines()

    in_recommended_actions = False
    in_tier = False
    actions = []

    for line in lines:
        stripped = line.strip()

        if stripped == "RECOMMENDED ACTIONS":
            in_recommended_actions = True
            continue

        if not in_recommended_actions:
            continue

        if stripped in [
            "AMBER:",
            "RED:",
            "CRITICAL:"
        ]:
            current_tier = stripped.replace(
                ":",
                ""
            )

            in_tier = current_tier == tier
            continue

        if in_tier:
            if stripped.startswith("- "):
                action = stripped[2:].strip()

                if action:
                    actions.append(action)
            elif stripped in [
                "AGGRAVATING SIGNALS",
                "COMFORT SIGNALS",
                "ACTION SELECTION"
            ]:
                break

    return actions
#actions for 3+breached actions
def get_systemic_distress_actions(
    playbook,
    trigger_kpis
):
    if len(trigger_kpis) < 3:
        return []

    overall_actions = get_overall_actions(
        playbook
    )

    systemic_actions = []

    start = playbook.find(
        "3+ KPIs in Breach"
    )

    if start == -1:
        return []

    section = playbook[start:start + 1000]

    for action in overall_actions:
        if action.lower() in section.lower():
            systemic_actions.append(action)

    return systemic_actions

def get_compound_actions(
    playbook,
    trigger_kpis
):
    triggered_ids = {
        kpi["kpi_id"]
        for kpi in trigger_kpis
    }

    overall_actions = get_overall_actions(
        playbook
    )

    compound_actions = []

    if {"KPI-001", "KPI-006"}.issubset(
        triggered_ids
    ):
        start = playbook.find(
            "COMPOUND SIGNAL: KPI-001 + KPI-006"
        )

        if start != -1:
            end = playbook.find(
                "COMPOUND SIGNAL:",
                start + 1
            )

            if end == -1:
                end = len(playbook)

            section = playbook[start:end]

            for action in overall_actions:
                if action.lower() in section.lower():
                    compound_actions.append(action)

    return compound_actions

def get_allowed_actions(trigger_kpis):
    playbook = load_playbook()
    overall_actions = get_overall_actions(
        playbook
    )

    action_details = []

    for kpi in trigger_kpis:
        tier_actions = get_tier_actions(
            playbook,
            kpi["kpi_id"],
            kpi["tier"]
        )

        for action in tier_actions:
            action_details.append({
                "action": action,
                "source": "tier",
                "kpi_id": kpi["kpi_id"],
                "tier": kpi["tier"]
            })

    systemic_actions = get_systemic_distress_actions(
        playbook,
        trigger_kpis
    )

    for action in systemic_actions:
        action_details.append({
            "action": action,
            "source": "systemic_distress",
            "kpi_id": "SYSTEMIC",
            "tier": "SYSTEMIC"
        })

    compound_actions = get_compound_actions(
        playbook,
        trigger_kpis
    )

    for action in compound_actions:
        action_details.append({
            "action": action,
            "source": "compound_risk",
            "kpi_id": "COMPOUND",
            "tier": "COMPOUND"
        })

    unique_actions = {}

    for item in action_details:
        action = item["action"]

        if action not in unique_actions:
            unique_actions[action] = item

    action_details = list(
        unique_actions.values()
    )

    action_order = {
        action: index
        for index, action in enumerate(
            overall_actions
        )
    }

    source_priority = {
        "compound_risk": 0,
        "systemic_distress": 1,
        "tier": 2
    }

    tier_priority = {
        "CRITICAL": 0,
        "RED": 1,
        "AMBER": 2,
        "SYSTEMIC": 0,
        "COMPOUND": 0
    }

    action_details.sort(
        key=lambda item: (
            source_priority.get(
                item["source"],
                3
            ),
            tier_priority.get(
                item["tier"],
                3
            ),
            action_order.get(
                item["action"],
                999
            )
        )
    )

    return action_details

def get_playbook_guidance(trigger_kpis):
    guidance = []

    for kpi in trigger_kpis:
        query = f"""
Retrieve the exact playbook guidance for:

KPI: {kpi['kpi_id']} - {kpi['kpi_name']}
Current tier: {kpi['tier']}
Current value: {kpi['kpi_value']}

Retrieve:
- current-tier recommended actions
- aggravating signals
- comfort signals
- relevant compound-risk guidance

Preserve the exact wording from the playbook.
Do not invent actions.
"""

        results = retriever.invoke(query)[:3]

        for result in results:
            guidance.append(
                result.page_content
            )

    if len(trigger_kpis) >= 3:
        query = """
Retrieve the exact playbook guidance for
3+ KPIs in Breach / Systemic Distress.

Retrieve the exact recommended actions
and policy guidance.

Preserve the exact wording.
Do not invent actions.
"""

        results = retriever.invoke(query)[:3]

        for result in results:
            guidance.append(
                result.page_content
            )

    return "\n\n".join(guidance)

def generate_action_reasons(
    loan_acct_number,
    trigger_kpis,
    agent1_output,
    risk_score,
    risk_category,
    playbook_guidance,
    action_details
):
    actions = [
        item["action"]
        for item in action_details
    ]

    action_list = "\n".join(
        f"{index + 1}. {action}"
        for index, action in enumerate(actions)
    )

    prompt = f"""
You are the explanation component of a credit-risk
Early Warning Indicator system.

IMPORTANT:

You are NOT selecting actions.

The actions have already been selected by Python
from the official playbook.

You must ONLY provide a short reason for each
provided action.

LOAN ACCOUNT:
{loan_acct_number}

RISK SCORE:
{risk_score}

RISK CATEGORY:
{risk_category}

TRIGGERED KPIs:
{trigger_kpis}

AGENT 1 INSIGHTS:
{agent1_output}

PLAYBOOK GUIDANCE:
{playbook_guidance}

SELECTED PLAYBOOK ACTIONS:

{action_list}

STRICT RULES:

1. Do not add any new action.

2. Do not remove any action.

3. Do not rename any action.

4. Do not change the order of the actions.

5. Do not repeat the action text.

6. Generate ONLY one reason for each supplied action.

7. Use only the supplied KPI values, tiers,
risk score, risk category, Agent 1 information,
and playbook guidance.

8. Do not invent facts.

9. Do not invent policies.

10. Do not invent thresholds.

11. Do not invent procedures.

12. Do not introduce another recommendation
inside the reason.

13. Keep each reason to one concise sentence.

14. Return exactly the same number of reasons
as the number of supplied actions.

OUTPUT FORMAT:

Reason 1: ...

Reason 2: ...

Reason 3: ...

Reason 4: ...

Do not add anything else.
"""

    try:
        response = llm.invoke(prompt)
    except Exception:
        return [
            "This action is supported by the applicable playbook guidance for the current risk condition."
            for _ in actions
        ]

    reasons = []

    for line in response.content.strip().splitlines():
        line = line.strip()

        if line.startswith("Reason"):
            if ":" in line:
                reason = line.split(
                    ":",
                    1
                )[1].strip()

                if reason:
                    reasons.append(reason)

    while len(reasons) < len(actions):
        reasons.append(
            "This action is supported by the applicable playbook guidance for the current risk condition."
        )

    return reasons[:len(actions)]

def build_final_output(
    action_details,
    reasons
):
    if not action_details:
        return "No playbook-supported action available."

    output = []

    for index, item in enumerate(
        action_details
    ):
        action = item["action"]
        reason = reasons[index]

        output.append(
            f"{index + 1}. {action}\n\n"
            f"Reason: {reason}"
        )

    return "\n\n".join(output)

def agent3(state):
    if state.get("recommended_actions"):
        return {
            "recommended_actions": state["recommended_actions"]
        }

    loan_acct_number = state["loan_acct_number"]
    agent1_output = state["agent1_output"]
    risk_score = state["risk_score"]
    risk_category = state["risk_category"]

    trigger_kpis = get_trigger_kpis(
        loan_acct_number
    )

    triggered_agent1_output = get_triggered_agent1_output(
        agent1_output,
        trigger_kpis
    )

    action_details = get_allowed_actions(
    trigger_kpis
)[:4]

    playbook_guidance = get_playbook_guidance(
        trigger_kpis
    )

    reasons = generate_action_reasons(
        loan_acct_number,
        trigger_kpis,
        triggered_agent1_output,
        risk_score,
        risk_category,
        playbook_guidance,
        action_details
    )

    recommended_actions = build_final_output(
        action_details,
        reasons
    )

    return {
        "recommended_actions": recommended_actions
    }

if __name__ == "__main__":
    from agent1 import agent1
    from agent2 import agent2

    loan_acct_number = input(
        "Enter loan account number: "
    )

    print("\nRunning Agents 1 and 2...")
    print("Please wait...\n")

    state = {
        "loan_acct_number": loan_acct_number,
        "agent1_output": "",
        "risk_score": 0.0,
        "risk_category": ""
    }

    state.update(agent1(state))
    state.update(agent2(state))

    result = agent3(state)

    print("=" * 60)
    print("AGENT 3 - RECOMMENDED ACTIONS")
    print("=" * 60)
    print(
        f"LOAN ACCOUNT: {loan_acct_number}"
    )
    print(
        f"RISK SCORE: {state['risk_score']}"
    )
    print(
        f"RISK CATEGORY: {state['risk_category']}"
    )
    print("\nRECOMMENDED ACTIONS")
    print("-" * 60)
    print(result["recommended_actions"])
    print("=" * 60)