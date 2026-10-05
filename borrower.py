import streamlit as st
from db import get_connection, get_kpi_context as fetch_kpi_context
from graph import graph


@st.cache_data(ttl=300, show_spinner=False)
def get_loan_context(loan_acct_number):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM loan_context
        WHERE LOAN_ACCT_NUMBER = %s;
    """, (loan_acct_number,))

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    return result


@st.cache_data(ttl=300, show_spinner=False)
def get_loan_kpis(loan_acct_number):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            lk.KPI_ID,
            lk.KPI_NAME,
            lk.KPI_VALUE,
            lk.KPI_UNIT,
            lk.THRESHOLD_BREACHED,
            lk.ASSIGNED_TIER,
            lk.RUN_DATE,
            lk.VALUES_IN_WINDOW,
            lk.OBSERVATION_WINDOW,
            kd.THRESHOLD_AMBER,
            kd.THRESHOLD_RED,
            kd.THRESHOLD_CRITICAL,
            kd.KPI_WEIGHTAGE
        FROM loan_kpi_facts lk
        JOIN kpi_definitions kd
            ON lk.KPI_ID = kd.KPI_ID
        WHERE lk.LOAN_ACCT_NUMBER = %s
        ORDER BY lk.KPI_ID;
    """, (loan_acct_number,))

    result = cursor.fetchall()

    cursor.close()
    connection.close()

    return result


def show_borrower():
    st.markdown("""
    <style>
    .stApp {
        background-color: #f8f9fb;
    }

    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 3rem;
    }

    .metric-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 18px;
        height: 115px;
    }

    .metric-label {
        font-size: 14px;
        color: #555;
        margin-bottom: 8px;
    }

    .metric-number {
        font-size: 30px;
        font-weight: 700;
    }

    .critical {
        color: #f97316;
    }

    .high {
        color: #dc2626;
    }

    .medium {
        color: #eab308;
    }

    .low {
        color: #16a34a;
    }

    .risk-badge {
        padding: 5px 10px;
        border-radius: 6px;
        color: white;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }

    .badge-critical {
        background-color: #f97316;
    }

    .badge-high {
        background-color: #dc2626;
    }

    .badge-medium {
        background-color: #eab308;
    }

    .badge-low {
        background-color: #16a34a;
    }

    .kpi-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }

    .kpi-title {
        font-size: 16px;
        font-weight: 600;
        color: #222;
    }

    .kpi-value {
        font-size: 18px;
        font-weight: 700;
        color: #333;
    }
    </style>
    """, unsafe_allow_html=True)

    loan_acct_number = st.session_state["selected_loan"]

    if st.button("← Back to Portfolio"):
        st.session_state["page"] = "portfolio"
        st.rerun()

    context = get_loan_context(loan_acct_number)
    kpis = get_loan_kpis(loan_acct_number)

    if not context:
        st.error("Loan information not found.")
        st.stop()

    risk_key = f"risk_result_{loan_acct_number}"

    if risk_key not in st.session_state:
        with st.spinner("Calculating risk..."):
            st.session_state[risk_key] = graph.invoke({
                "loan_acct_number": loan_acct_number,
                "route": "agent2",
                "question": "",
                "chat_history": [],
                "execution_trace": []
            })

    risk_result = st.session_state[risk_key]

    risk_score = risk_result["risk_score"]
    risk_category = risk_result["risk_category"]

    st.title(context["PRIMARY_CUSTOMER_NAME"])
    st.caption(f"Loan Account: {loan_acct_number}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Composite Risk Score</div>
                <div class="metric-number">{risk_score}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        category_class = risk_category.lower()

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Risk Category</div>
                <div class="metric-number {category_class}">
                    {risk_category}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("Borrower Information")

    info_col1, info_col2, info_col3 = st.columns(3)

    with info_col1:
        st.write("**Loan Type**")
        st.write(context["LOAN_TYPE"])

        st.write("**Loan Amount**")
        st.write(context["LOAN_AMT"])

        st.write("**Outstanding Balance**")
        st.write(context["OUTSTANDING_BAL"])

    with info_col2:
        st.write("**Remaining Tenure**")
        st.write(f'{context["REMAINING_TENURE_MONTHS"]} months')

        st.write("**Interest Rate**")
        st.write(context["INTEREST_RATE"])

        st.write("**Collateral Value**")
        st.write(context["COLLATERAL_VALUE"])

    with info_col3:
        st.write("**Collateral Coverage**")
        st.write(context["COLLATERAL_COVERAGE_PCT"])

        st.write("**MCC**")
        st.write(context["MCC"])

        st.write("**Region**")
        st.write(context["REGION"])

    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("KPI Details")

    for kpi in kpis:
        tier = kpi["ASSIGNED_TIER"]

        if tier == "CRITICAL":
            badge_class = "badge-critical"
        elif tier == "RED":
            badge_class = "badge-high"
        elif tier == "AMBER":
            badge_class = "badge-medium"
        else:
            badge_class = "badge-low"

        col1, col2, col3 = st.columns([3, 1.5, 1.5])

        with col1:
            st.markdown(
                f"""<div class="kpi-card">
<div class="kpi-title">{kpi["KPI_ID"]} - {kpi["KPI_NAME"]}</div>
<div style="margin-top:8px;">
<span class="risk-badge {badge_class}">{tier}</span>
</div>
<div style="margin-top:12px; font-size:13px; color:#555; line-height:1.6;">
<b>Threshold:</b>
Amber ≥ {kpi["THRESHOLD_AMBER"]} |
Red ≥ {kpi["THRESHOLD_RED"]} |
Critical ≥ {kpi["THRESHOLD_CRITICAL"]}
</div>
</div>""",
                unsafe_allow_html=True
            )

        with col2:
            st.markdown(
                f"""<div class="kpi-card">
<div class="kpi-title">KPI Value</div>
<div class="kpi-value">{kpi["KPI_VALUE"]} {kpi["KPI_UNIT"]}</div>
<div style="margin-top:12px; font-size:13px; color:#555;">
<b>Weight:</b> {kpi["KPI_WEIGHTAGE"]}%
</div>
</div>""",
                unsafe_allow_html=True
            )

        with col3:
            st.markdown(
                '<div style="height:15px;"></div>',
                unsafe_allow_html=True
            )

            if st.button(
                "View KPI Insights",
                key=f"insight_{kpi['KPI_ID']}"
            ):
                insight_result = graph.invoke({
                    "loan_acct_number": loan_acct_number,
                    "route": "agent1",
                    "question": "",
                    "chat_history": [],
                    "execution_trace": []
                })
                insight = ""
                agent1_output = insight_result.get("agent1_output", "")
                for line in agent1_output.splitlines():
                    if kpi["KPI_ID"] in line:
                        insight = line.strip()
                        break
                if not insight:
                    insight = agent1_output
                insight_key = f"insight_output_{loan_acct_number}_{kpi['KPI_ID']}"
                st.session_state[insight_key] = insight
                with st.expander("Execution Trace"):
                    for step in insight_result.get("execution_trace", []):
                        st.write(f"✓ {step}")

        insight_key = (
            f"insight_output_{loan_acct_number}_{kpi['KPI_ID']}"
        )

        if insight_key in st.session_state:
            st.markdown(
                """
                <div style="
                    background:#ffffff;
                    border:1px solid #e5e7eb;
                    border-radius:10px;
                    padding:16px;
                    margin-bottom:12px;
                ">
                    <strong>Smart Insights Agent</strong>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.write(st.session_state[insight_key])

    st.markdown("<br>", unsafe_allow_html=True)

    if risk_category in ["MEDIUM", "HIGH", "CRITICAL"]:
        st.subheader("Recommended Actions")

        recommended_key = (
            f"recommended_actions_output_{loan_acct_number}"
        )

        if st.button(
            "View Recommended Actions",
            key=f"recommended_actions_{loan_acct_number}"
        ):
            state = {
                "loan_acct_number": loan_acct_number,
                "question": "",
                "route": "agent3",
                "agent1_output": st.session_state.get(f"agent1_output_{loan_acct_number}", ""),
                "risk_score": risk_score,
                "risk_category": risk_category,
                "recommended_actions": st.session_state.get(recommended_key, ""),
                "answer": "",
                "citations": [],
                "queries_used": [],
                "tools_used": [],
                "chat_history": [],
                "execution_trace": []
            }
            with st.spinner("Generating recommended actions..."):
                result = graph.invoke(state)
            st.session_state[recommended_key] = result.get("recommended_actions", "")
            st.session_state[f"agent1_output_{loan_acct_number}"] = result.get("agent1_output", state.get("agent1_output", ""))
            st.session_state[f"agent2_output_{loan_acct_number}"] = {
                "risk_score": result.get("risk_score", risk_score),
                "risk_category": result.get("risk_category", risk_category)
            }
            with st.expander("Execution Trace"):
                for step in result.get("execution_trace", []):
                    st.write(f"✓ {step}")

        if recommended_key in st.session_state:
            st.markdown(
                """
                <div style="
                    background:white;
                    border:1px solid #e5e7eb;
                    border-radius:10px;
                    padding:16px;
                    margin-top:12px;
                ">
                """,
                unsafe_allow_html=True
            )

            st.write(st.session_state[recommended_key])

            st.markdown(
                "</div>",
                unsafe_allow_html=True
            )