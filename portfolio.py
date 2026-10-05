import streamlit as st
import re
from db import get_connection
from graph import graph
from borrower import show_borrower

st.set_page_config(
    page_title="EWI Portfolio Dashboard",
    layout="wide"
)
#style

st.markdown("""
<style>
.stApp{background:#f7f9fc}
.block-container{max-width:1400px;padding-top:2rem;padding-bottom:3rem}
h1,h2,h3{color:#172033;letter-spacing:-.02em}
h3{margin-top:1.6rem;margin-bottom:.9rem}
p,label,.stMarkdown{color:#526071}
.summary-card{background:#fff;border:1px solid #e6eaf0;border-radius:16px;padding:20px 22px;min-height:108px;box-shadow:0 3px 12px rgba(23,32,51,.05)}
.summary-label{font-size:13px;font-weight:600;color:#7a8595;margin-bottom:10px;text-transform:uppercase;letter-spacing:.04em}
.summary-number{font-size:32px;line-height:1;font-weight:750}
.borrower-number{color:#3157d5}.critical-number{color:#d64545}.high-number{color:#e16a32}.watchlist-number{color:#d49a18}
.critical-badge,.high-badge,.medium-badge,.low-badge{display:inline-block;padding:5px 12px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.04em}
.critical-badge{background:#fde8e8;color:#b42318}.high-badge{background:#fff0e8;color:#c2410c}.medium-badge{background:#fff7d6;color:#9a6700}.low-badge{background:#e8f6ee;color:#18794e}
.stButton>button{border:1px solid #dfe5ee;background:#fff;color:#1f4fbf;border-radius:9px;font-weight:650;text-align:left;padding:8px 12px;min-height:38px;transition:all .15s ease}
.stButton>button:hover{border-color:#3157d5;color:#2347b2;background:#f4f7ff}
div[data-testid="stExpander"]{margin-top:18px;margin-bottom:22px;border:1px solid #e1e6ef;border-radius:14px;background:#fff;box-shadow:0 2px 10px rgba(23,32,51,.04);overflow:hidden}
div[data-testid="stExpander"] details{background:#fff;border-radius:14px}
div[data-testid="stExpander"] summary{padding:16px 20px;font-weight:700;color:#25324a;background:#fff}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"]{padding:4px 20px 20px;background:#fff}
div[data-testid="column"]{padding-left:.35rem;padding-right:.35rem}
.chat-button{text-align:center}
.chat-button button{font-size:24px!important;padding:5px 10px!important;min-height:42px!important;text-align:center!important}
.chat-label{text-align:center;font-size:13px;font-weight:650;color:#526071;margin-top:-5px}
div[data-baseweb="select"]>div{border-radius:9px;border-color:#dfe5ee;background:#fff}
hr{border-color:#e6eaf0}
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state["page"] = "portfolio"

if "selected_loan" not in st.session_state:
    st.session_state["selected_loan"] = None

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

if "last_chat_loan" not in st.session_state:
    st.session_state["last_chat_loan"] = ""

@st.cache_data(ttl=300, show_spinner=False)
#data
def get_portfolio_data():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    query = """
        SELECT
            lc.LOAN_ACCT_NUMBER,
            lc.PRIMARY_CUSTOMER_NAME,
            lk.KPI_ID,
            lk.KPI_NAME,
            lk.KPI_VALUE,
            lk.ASSIGNED_TIER,
            kd.KPI_WEIGHTAGE
        FROM loan_context lc
        LEFT JOIN loan_kpi_facts lk
            ON lc.LOAN_ACCT_NUMBER = lk.LOAN_ACCT_NUMBER
        LEFT JOIN kpi_definitions kd
            ON lk.KPI_ID = kd.KPI_ID
        ORDER BY lc.PRIMARY_CUSTOMER_NAME, lc.LOAN_ACCT_NUMBER, lk.KPI_ID;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    borrowers = {}
    risk_data = []
    for row in rows:
        loan_acct_number = row["LOAN_ACCT_NUMBER"]
        if loan_acct_number not in borrowers:
            borrowers[loan_acct_number] = {
                "LOAN_ACCT_NUMBER": loan_acct_number,
                "PRIMARY_CUSTOMER_NAME": row["PRIMARY_CUSTOMER_NAME"]
            }
        if row["KPI_ID"] is not None:
            risk_data.append({
                "LOAN_ACCT_NUMBER": loan_acct_number,
                "KPI_ID": row["KPI_ID"],
                "KPI_NAME": row["KPI_NAME"],
                "KPI_VALUE": row["KPI_VALUE"],
                "ASSIGNED_TIER": row["ASSIGNED_TIER"],
                "KPI_WEIGHTAGE": row["KPI_WEIGHTAGE"]
            })
    return list(borrowers.values()), risk_data

def get_loan_for_customer(customer_name):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    query = """
        SELECT
            LOAN_ACCT_NUMBER
        FROM loan_context
        WHERE PRIMARY_CUSTOMER_NAME = %s
        LIMIT 1;
    """
    cursor.execute(query, (customer_name,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    if result:
        return result["LOAN_ACCT_NUMBER"]
    return ""

def find_customer_loan(question):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    query = """
        SELECT
            LOAN_ACCT_NUMBER,
            PRIMARY_CUSTOMER_NAME
        FROM loan_context
        WHERE LOWER(%s) LIKE CONCAT(
            '%',
            LOWER(PRIMARY_CUSTOMER_NAME),
            '%'
        )
        LIMIT 1;
    """
    cursor.execute(query, (question,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    if result:
        return (
            result["LOAN_ACCT_NUMBER"],
            result["PRIMARY_CUSTOMER_NAME"]
        )
    return "", ""
#agent2 
def calculate_portfolio_risk(risk_data):
    total_weight = 0
    weighted_score = 0
    for row in risk_data:
        tier = row["ASSIGNED_TIER"]
        if tier == "GREEN":
            severity_score = 0
        elif tier == "AMBER":
            severity_score = 1
        elif tier == "RED":
            severity_score = 2
        elif tier == "CRITICAL":
            severity_score = 3
        else:
            severity_score = 0
        weight = float(row["KPI_WEIGHTAGE"])
        weighted_score += severity_score * weight
        total_weight += weight
    if total_weight == 0:
        risk_score = 0.0
    else:
        normalized_score = weighted_score / total_weight
        risk_score = round((normalized_score / 3) * 10, 2)
    if risk_score <= 2.5:
        risk_category = "LOW"
    elif risk_score <= 5.0:
        risk_category = "MEDIUM"
    elif risk_score <= 7.5:
        risk_category = "HIGH"
    else:
        risk_category = "CRITICAL"
    return risk_score, risk_category

def get_portfolio_analysis(borrowers, risk_data):
    loan_risk_data = {}
    for row in risk_data:
        loan_acct_number = row["LOAN_ACCT_NUMBER"]
        if loan_acct_number not in loan_risk_data:
            loan_risk_data[loan_acct_number] = []
        loan_risk_data[loan_acct_number].append(row)
    analyzed_borrowers = []
    for borrower in borrowers:
        loan_acct_number = borrower["LOAN_ACCT_NUMBER"]
        risk_data_for_loan = loan_risk_data.get(loan_acct_number, [])
        risk_score, risk_category = calculate_portfolio_risk(risk_data_for_loan)
        borrower["risk_score"] = risk_score
        borrower["risk_category"] = risk_category
        borrower["loan_acct_number"] = loan_acct_number
        borrower["name"] = borrower["PRIMARY_CUSTOMER_NAME"]
        analyzed_borrowers.append(borrower)
    return analyzed_borrowers, loan_risk_data

if st.session_state["page"] == "chat":
    st.title("Chat Agent")
    st.caption("Ask questions about loans, KPIs, alerts and recommendations.")
    if st.button("← Back to Portfolio"):
        st.session_state["page"] = "portfolio"
        st.rerun()

    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("citations"):
                st.caption("Sources: " + ", ".join(message["citations"]))
            if message.get("queries"):
                with st.expander("View query"):
                    for query in message["queries"]:
                        st.code(query, language="sql")
            if message.get("execution_trace"):
                with st.expander("Execution Trace"):
                    for step in message["execution_trace"]:
                        st.write(f"✓ {step}")

    question = st.chat_input("Ask the Relationship Manager question...")

    if question:
        st.session_state["chat_history"].append({
            "role": "user",
            "content": question
        })

        loan_acct_number = ""
        loan_match = re.search(r"\b(?:loan\s*)?(\d{4,})\b", question, re.IGNORECASE)

        if loan_match:
            loan_acct_number = loan_match.group(1)
            st.session_state["last_chat_loan"] = loan_acct_number
        else:
            loan_acct_number, customer_name = find_customer_loan(question)
            if loan_acct_number:
                st.session_state["last_chat_loan"] = loan_acct_number
            else:
                loan_acct_number = st.session_state.get("last_chat_loan", "")

        existing_agent1_output = st.session_state.get(f"agent1_output_{loan_acct_number}", "")
        existing_agent2_output = st.session_state.get(f"agent2_output_{loan_acct_number}", {})
        existing_recommended_actions = st.session_state.get(f"recommended_actions_output_{loan_acct_number}", "")

        state = {
            "loan_acct_number": loan_acct_number,
            "question": question,
            "route": "agent4",
            "agent1_output": existing_agent1_output,
            "risk_score": existing_agent2_output.get("risk_score") if existing_agent2_output else None,
            "risk_category": existing_agent2_output.get("risk_category") if existing_agent2_output else None,
            "recommended_actions": existing_recommended_actions,
            "answer": "",
            "citations": [],
            "queries_used": [],
            "tools_used": [],
            "chat_history": st.session_state["chat_history"],
            "execution_trace": []
        }

        with st.spinner("Thinking..."):
            result = graph.invoke(state)

        if result.get("agent1_output"):
            st.session_state[f"agent1_output_{loan_acct_number}"] = result["agent1_output"]

        if result.get("risk_score") is not None and result.get("risk_category"):
            st.session_state[f"agent2_output_{loan_acct_number}"] = {
                "risk_score": result["risk_score"],
                "risk_category": result["risk_category"]
            }

        if result.get("recommended_actions"):
            st.session_state[f"recommended_actions_output_{loan_acct_number}"] = result["recommended_actions"]

        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": result.get("answer", ""),
            "citations": result.get("citations", []),
            "queries": result.get("queries_used", result.get("tools_used", [])),
            "execution_trace": result.get("execution_trace", [])
        })

        st.rerun()

elif st.session_state["page"] == "borrower":
    show_borrower()

else:
    chat_col1, chat_col2, chat_col3 = st.columns([8, 1, 1])

    with chat_col1:
        st.title("Early Warning Indicators")
        st.subheader("Hello, Sarah Chen")
        st.write("Relationship Manager")

    with chat_col3:
        st.markdown(
            '<div class="chat-button">',
            unsafe_allow_html=True
        )
        if st.button("💬", key="portfolio_chat"):
            st.session_state["page"] = "chat"
            st.rerun()
        st.markdown(
            '<div class="chat-label">Chat Agent</div>',
            unsafe_allow_html=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

    borrowers, portfolio_risk_data = get_portfolio_data()

    borrowers, loan_risk_data = get_portfolio_analysis(
        borrowers,
        portfolio_risk_data
    )

    critical_count = sum(
        1
        for borrower in borrowers
        if borrower["risk_category"] == "CRITICAL"
    )

    high_count = sum(
        1
        for borrower in borrowers
        if borrower["risk_category"] == "HIGH"
    )

    watchlist_borrowers = [
        borrower
        for borrower in borrowers
        if borrower["risk_category"] == "MEDIUM"
    ]

    watchlist_count = len(watchlist_borrowers)

    low_count = sum(
        1
        for borrower in borrowers
        if borrower["risk_category"] == "LOW"
    )

    st.markdown("### Portfolio Summary")

    card1, card2, card3, card4 = st.columns(4)

    with card1:
        st.markdown(
            f"""
            <div class="summary-card">
                <div class="summary-label">Borrowers Monitored</div>
                <div class="summary-number borrower-number">{len(borrowers)}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with card2:
        st.markdown(
            f"""
            <div class="summary-card">
                <div class="summary-label">Critical Alerts</div>
                <div class="summary-number critical-number">{critical_count}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with card3:
        st.markdown(
            f"""
            <div class="summary-card">
                <div class="summary-label">High Alerts</div>
                <div class="summary-number high-number">{high_count}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with card4:
        st.markdown(
            f"""
            <div class="summary-card">
                <div class="summary-label">Watchlist Customers</div>
                <div class="summary-number watchlist-number">{watchlist_count}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with st.expander("How Risk Score & Category Are Calculated"):
        st.markdown("#### 1. KPI Severity Score")
        severity_col1, severity_col2 = st.columns(2)

        with severity_col1:
            st.write("🟢 **GREEN** → Severity Score = **0**")
            st.write("🟡 **AMBER** → Severity Score = **1**")

        with severity_col2:
            st.write("🔴 **RED** → Severity Score = **2**")
            st.write("🔴 **CRITICAL** → Severity Score = **3**")

        st.markdown("#### 2. Weighted Score")
        st.code(
            "Weighted Score = Σ (KPI Severity Score × KPI Weightage)",
            language="text"
        )

        st.markdown("#### 3. Normalize the Score")
        st.code(
            "Normalized Score = Weighted Score ÷ Total KPI Weightage",
            language="text"
        )

        st.markdown("#### 4. Final Risk Score")
        st.code(
            "Risk Score = (Normalized Score ÷ 3) × 10",
            language="text"
        )

        st.markdown("#### 5. Risk Category")
        category_col1, category_col2, category_col3, category_col4 = st.columns(4)

        with category_col1:
            st.markdown("**0 – 2.5**")
            st.write("LOW")

        with category_col2:
            st.markdown("**>2.5 – 5.0**")
            st.write("MEDIUM")

        with category_col3:
            st.markdown("**>5.0 – 7.5**")
            st.write("HIGH")

        with category_col4:
            st.markdown("**>7.5 – 10.0**")
            st.write("CRITICAL")

    st.markdown("### Prioritized Alert Queue")

    prioritized_borrowers = [
        borrower
        for borrower in borrowers
        if borrower["risk_category"] in [
            "CRITICAL",
            "HIGH",
            "MEDIUM"
        ]
    ]

    prioritized_borrowers.sort(
        key=lambda x: x["risk_score"],
        reverse=True
    )

    header1, header2, header3, header4 = st.columns(
        [5, 2, 2, 4],
        gap="small"
    )

    with header1:
        st.write("**Borrower**")

    with header2:
        st.write("**Risk Score**")

    with header3:
        st.write("**Category**")

    with header4:
        st.write("**Top Trigger KPI**")

    for borrower in prioritized_borrowers:
        col1, col2, col3, col4 = st.columns(
            [5, 2, 2, 4],
            gap="small"
        )

        kpis = loan_risk_data.get(
            borrower["loan_acct_number"],
            []
        )

        breached_kpis = [
            kpi
            for kpi in kpis
            if kpi["ASSIGNED_TIER"] in [
                "AMBER",
                "RED",
                "CRITICAL"
            ]
        ]

        top_trigger = (
            breached_kpis[0]["KPI_NAME"]
            if breached_kpis
            else "No active breach"
        )

        with col1:
            if st.button(
                borrower["name"],
                key=f"queue_{borrower['loan_acct_number']}"
            ):
                st.session_state["selected_loan"] = borrower["loan_acct_number"]
                st.session_state["page"] = "borrower"
                st.rerun()

        with col2:
            st.write(borrower["risk_score"])

        with col3:
            category = borrower["risk_category"]

            if category == "CRITICAL":
                st.markdown(
                    '<span class="critical-badge">CRITICAL</span>',
                    unsafe_allow_html=True
                )
            elif category == "HIGH":
                st.markdown(
                    '<span class="high-badge">HIGH</span>',
                    unsafe_allow_html=True
                )
            elif category == "MEDIUM":
                st.markdown(
                    '<span class="medium-badge">MEDIUM</span>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    '<span class="low-badge">LOW</span>',
                    unsafe_allow_html=True
                )

        with col4:
            st.write(top_trigger)

    st.markdown("### All Borrowers")

    filter_col1, filter_col2 = st.columns([7, 2])

    with filter_col1:
        st.write("View and filter the complete portfolio.")

    with filter_col2:
        selected_filter = st.selectbox(
            "Filter",
            [
                "All Borrowers",
                "Critical",
                "High",
                "Watchlist",
                "Low"
            ],
            label_visibility="collapsed"
        )

    if selected_filter == "All Borrowers":
        filtered_borrowers = borrowers
    elif selected_filter == "Critical":
        filtered_borrowers = [
            borrower
            for borrower in borrowers
            if borrower["risk_category"] == "CRITICAL"
        ]
    elif selected_filter == "High":
        filtered_borrowers = [
            borrower
            for borrower in borrowers
            if borrower["risk_category"] == "HIGH"
        ]
    elif selected_filter == "Watchlist":
        filtered_borrowers = [
            borrower
            for borrower in borrowers
            if borrower["risk_category"] == "MEDIUM"
        ]
    else:
        filtered_borrowers = [
            borrower
            for borrower in borrowers
            if borrower["risk_category"] == "LOW"
        ]

    header1, header2, header3 = st.columns(
        [5, 2, 2],
        gap="small"
    )

    with header1:
        st.write("**Borrower**")

    with header2:
        st.write("**Risk Score**")

    with header3:
        st.write("**Category**")

    for borrower in filtered_borrowers:
        col1, col2, col3 = st.columns(
            [5, 2, 2],
            gap="small"
        )

        with col1:
            if st.button(
                borrower["name"],
                key=f"all_{selected_filter}_{borrower['loan_acct_number']}"
            ):
                st.session_state["selected_loan"] = borrower["loan_acct_number"]
                st.session_state["page"] = "borrower"
                st.rerun()

        with col2:
            st.write(borrower["risk_score"])

        with col3:
            category = borrower["risk_category"]

            if category == "CRITICAL":
                st.markdown(
                    '<span class="critical-badge">CRITICAL</span>',
                    unsafe_allow_html=True
                )
            elif category == "HIGH":
                st.markdown(
                    '<span class="high-badge">HIGH</span>',
                    unsafe_allow_html=True
                )
            elif category == "MEDIUM":
                st.markdown(
                    '<span class="medium-badge">MEDIUM</span>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    '<span class="low-badge">LOW</span>',
                    unsafe_allow_html=True
                )

